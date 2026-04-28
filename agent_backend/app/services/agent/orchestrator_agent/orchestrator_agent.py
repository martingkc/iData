from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
)

from ....config.config import POSTGRES_CHECKPOINT_URL, POSTGRES_USERDB_URL
from .prompts import system_prompt
from .middleware import context_editing_mw, tool_limit_mw
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.runnables import RunnableConfig
from .utils import format_messages
from ...vector_db.milvus_connector import MilvusConnector
from ....utils.logger import get_logger
from .tools import (
    get_document_subagent,
    get_sql_subagent,
    get_coding_subagent,
    think_tool,
    save_user_info,
    add_skill_tool,
    get_skill_tool,
    list_skills_tool,
    update_skill_tool,
    delete_skill_tool,
)
from ..skill_manager import get_skill_manager
from datetime import datetime
from .dataClasses import Context

from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

logger = get_logger(__name__)


class OrchestratorAgent:

    def __init__(self, model: str = "gpt-5-mini", checkpointer = None):

        self.skill_manager = get_skill_manager()
        self.store = (
            PostgresSaver.from_conn_string(POSTGRES_CHECKPOINT_URL)
            if checkpointer is None
            else checkpointer
        )

        self.checkpointer = self.store.__enter__()
        self.checkpointer.setup()
        try:
            sql_subagent = get_sql_subagent()
            subagents = [sql_subagent]
        except Exception as exc:
            logger.warning("SQL subagent unavailable: %s", exc)
            subagents = []

        try:
            document_subagent = get_document_subagent()
            subagents.append(document_subagent)
        except Exception as exc:
            logger.warning("Document subagent unavailable: %s", exc)

        try:
            coding_subagent = get_coding_subagent()
            subagents.append(coding_subagent)
        except Exception as exc:
            logger.warning("Coding subagent unavailable: %s", exc)

        self.tools = [
            think_tool,
            save_user_info,
            add_skill_tool,
            get_skill_tool,
            list_skills_tool,
            update_skill_tool,
            delete_skill_tool,
        ]
        self.agent = create_deep_agent(
            model=ChatOpenAI(model=model, temperature=0),
            tools=self.tools,
            store= self.checkpointer,
            system_prompt=self._build_system_prompt(),
            middleware=[context_editing_mw, tool_limit_mw],
            # TODO change in memory saver with postgres saver
            checkpointer=self.checkpointer,
            context_schema=Context,
            subagents=subagents,
        )

        logger.info(f"AgenticRAG initialized with model: {model}")

    def _build_system_prompt(self) -> str:
        """Build the system prompt with injected skills."""
        skills = self.skill_manager.get_skills_for_prompt()
        if not skills:
            skills = "No skills stored yet. Whenever you learn a valuable, complex new skill, use the add_skill_tool to store it."

        return system_prompt.format(
            date=datetime.now().strftime("%Y-%m-%d"),
            skills=skills,
        )

    def refresh_system_prompt(self) -> None:
        """Refresh the system prompt with updated skills.

        Call this when skills are modified to update the agent's context.
        """
        # Note: This would need to update the agent's system prompt
        # The exact implementation depends on how deepagents handles updates
        pass

    def run_cli(self) -> None:
        """Simple interactive CLI."""
        logger.info("Starting agentic RAG CLI...")
        # to have different conversation for different threads
        config: RunnableConfig = {"configurable": {"thread_id": "1"}}

        while True:
            try:
                question = input("Question: ").strip()
                if not question:
                    print("Empty query, try again.\n")
                    continue
                if question.lower() in {"exit", "quit"}:
                    print("Exiting.")
                    break
                result = self.agent.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": question,
                            }
                        ],
                    },
                    config,
                    context=Context(user_id="123"),
                )
                format_messages(result["messages"])

            except KeyboardInterrupt:
                print("\nExiting.")
                break
            except Exception as e:
                logger.error(f"Error in CLI: {e}", exc_info=True)
                print(f"Error: {e}\n")
