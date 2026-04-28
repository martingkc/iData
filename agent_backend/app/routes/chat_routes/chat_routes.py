from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from flask import g, jsonify, request

from ...config.logging_config import get_logger
from ...services.agent.research_agent.research_agent import ResearchAgent
from sqlalchemy import func

from ...services.agent.orchestrator_agent.orchestrator_agent import OrchestratorAgent
from ...db import SessionLocal
from ...models.chat_models import Chat, Message, User, UserType
from ...services.agent.orchestrator_agent.dataClasses import Context
from ...utils.chat_utils import make_thread_id
from ...routes.auth_routes.auth_extensions import token_auth
from . import chat_bp

_deep_agent: Optional[OrchestratorAgent] = None
_agent: Optional[ResearchAgent] = None

logger = get_logger(__name__)

# Singleton getters for agents to maintain state across requests. This should be fine for now, but to be replaced in the future. 
def _get_deep_agent():
    global _deep_agent
    if _deep_agent is None:
        _deep_agent = OrchestratorAgent()

    return _deep_agent

   
def _get_agent():
    global _agent
    if _agent is None:
        _agent = ResearchAgent(single_agent=True)
    return _agent


@chat_bp.get("/chats")
@token_auth.login_required
def list_chats():
    """List all chats for the authenticated user with their last message and timestamp."""

    user = g.user
    db = g.db if hasattr(g, "db") else SessionLocal()
    try:
        last_msg_subq = db.query(
            Message.chat_id.label("chat_id"),
            Message.content.label("content"),
            Message.created_at.label("created_at"),
            func.row_number()
            .over(partition_by=Message.chat_id, order_by=Message.created_at.desc())
            .label("rn"),
        ).subquery()

        rows = (
            db.query(
                Chat,
                last_msg_subq.c.content,
                last_msg_subq.c.created_at,
            )
            .outerjoin(
                last_msg_subq,
                (Chat.id == last_msg_subq.c.chat_id) & (last_msg_subq.c.rn == 1),
            )
            .filter(Chat.user_id == user.id, Chat.deleted_at.is_(None))
            .order_by(Chat.created_at.desc())
            .all()
        )

        resp = []
        for chat, last_content, last_created_at in rows:
            resp.append(
                {
                    "chat_id": str(chat.id),
                    "thread_id": chat.thread_id,
                    "created_at": (
                        chat.created_at.isoformat() if chat.created_at else None
                    ),
                    "last_message": (
                        {
                            "content": last_content,
                            "created_at": (
                                last_created_at.isoformat() if last_created_at else None
                            ),
                        }
                        if last_content is not None
                        else None
                    ),
                }
            )

        return jsonify({"chats": resp})
    finally:
        if not hasattr(g, "db"):
            db.close()


@chat_bp.post("/chats")
@token_auth.login_required
def create_chat():
    user = g.user
    db = g.db if hasattr(g, "db") else SessionLocal()
    try:
        chat_id = uuid4()
        thread_id = make_thread_id(user.id, chat_id)

        chat = Chat(
            id=chat_id,
            user_id=user.id,
            thread_id=thread_id,
            created_at=datetime.utcnow(),
        )
        db.add(chat)
        db.commit()

        return jsonify({"chat_id": str(chat.id)}), 201
    finally:
        if not hasattr(g, "db"):
            db.close()


@chat_bp.get("/chats/<chat_id>/messages")
@token_auth.login_required
def list_messages(chat_id: str):
    user = g.user
    db = g.db if hasattr(g, "db") else SessionLocal()
    try:
        chat_uuid = UUID(chat_id)
        chat = (
            db.query(Chat)
            .filter(
                Chat.id == chat_uuid, Chat.user_id == user.id, Chat.deleted_at.is_(None)
            )
            .one_or_none()
        )
        if chat is None:
            return jsonify({"error": "not found"}), 404

        msgs = (
            db.query(Message)
            .filter(Message.chat_id == chat.id)
            .order_by(Message.created_at.asc())
            .all()
        )

        return jsonify(
            {
                "chat_id": str(chat.id),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in msgs
                ],
            }
        )
    finally:
        if not hasattr(g, "db"):
            db.close()


@chat_bp.post("/chats/<chat_id>/messages")
@token_auth.login_required
def send_message(chat_id: str):
    """
    Send a message to the chat and get an agent response.

    Request body:
        text (str): The user message content (required).
        path_filters (list[str], optional): List of document paths to limit vector search scope.
            Example: ["reports/2024/q1.pdf", "contracts/vendor_a.docx"]
    """
    user = g.user
    payload = request.get_json(force=True) or {}
    text = (payload.get("text") or "").strip()
    is_deep_agent = payload.get("deep_think", False)
    if not text:
        return jsonify({"error": "missing text"}), 400

    # Optional: list of document paths to filter Milvus searches
    path_filters = payload.get("path_filters") or []
    if not isinstance(path_filters, list):
        path_filters = []

    db = g.db if hasattr(g, "db") else SessionLocal()
    try:
        chat_uuid = UUID(chat_id)
        chat = (
            db.query(Chat)
            .filter(
                Chat.id == chat_uuid, Chat.user_id == user.id, Chat.deleted_at.is_(None)
            )
            .one_or_none()
        )
        if chat is None:
            return jsonify({"error": "not found"}), 404

        db.add(Message(chat_id=chat.id, role="user", content=text))
        chat.last_message_at = datetime.utcnow()
        db.commit()

        try:
            # Build prompt with file scope context if filters provided
            if path_filters:
                scope_hint = (
                    "The user has selected the following documents/folders to scope this query:\n"
                    + "\n".join(f"- {p}" for p in path_filters)
                    + "\n\nLimit your search to these paths when retrieving documents.\n\n"
                )
                agent_prompt = scope_hint + text
            else:
                agent_prompt = text

            # 2) invoke agent with trusted thread_id and path filters
            config = {"configurable": {"thread_id": chat.thread_id}}

            agent = _get_deep_agent() if is_deep_agent else _get_agent()

            result = agent.agent.invoke(
                {"messages": [{"role": "user", "content": agent_prompt}]},
                config=config,
                context=Context(user_id=str(user.id), path_filters=path_filters),
            )

            # 3) extract assistant final text (use last message content if present)
            assistant_text = ""
            if isinstance(result, dict):
                msgs = result.get("messages") or []
                if msgs:
                    last = msgs[-1]
                    assistant_text = getattr(last, "content", "") or ""
                if not assistant_text and "output" in result:
                    assistant_text = result.get("output") or ""

            assistant_text = (assistant_text or "").strip()

            # 4) store assistant message
            db.add(Message(chat_id=chat.id, role="assistant", content=assistant_text))
            chat.last_message_at = datetime.utcnow()
            db.commit()

            return jsonify({"chat_id": str(chat.id), "answer": assistant_text})
        except Exception as exc:
            db.rollback()
            logger.error(f"Agent error: {exc}", exc_info=True)
            return jsonify({"error": "agent_failure", "details": str(exc)}), 500
    finally:
        if not hasattr(g, "db"):
            db.close()


@chat_bp.delete("/chats/<chat_id>")
@token_auth.login_required
def delete_chat(chat_id: str):
    """Soft-delete a chat (sets deleted_at timestamp)."""
    user = g.user
    db = g.db if hasattr(g, "db") else SessionLocal()
    try:
        chat_uuid = UUID(chat_id)
        chat = (
            db.query(Chat)
            .filter(
                Chat.id == chat_uuid, Chat.user_id == user.id, Chat.deleted_at.is_(None)
            )
            .one_or_none()
        )
        if chat is None:
            return jsonify({"error": "not found"}), 404

        chat.deleted_at = datetime.utcnow()
        db.commit()

        return jsonify({"message": "Chat deleted"}), 200
    finally:
        if not hasattr(g, "db"):
            db.close()
