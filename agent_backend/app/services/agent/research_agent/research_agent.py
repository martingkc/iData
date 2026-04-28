from typing import List, Dict, Any

from langchain_openai import ChatOpenAI

from ....config.config import POSTGRES_CHECKPOINT_URL, POSTGRES_USERDB_URL

from .prompts import system_prompt_subagent, system_prompt_single_agent
from .middleware import context_editing_mw, tool_limit_mw
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.runnables import RunnableConfig
from .utils import format_messages
from ...vector_db.milvus_connector import MilvusConnector
from ....utils.logger import get_logger
from .tools import (
    chunk_retriever_tool,
    think_tool,
    save_user_info,
    retrieve_full_content_tool,
    add_skill_tool,
    get_skill_tool,
    list_skills_tool,
    update_skill_tool,
    delete_skill_tool,
    document_catalogue_search_tool,
)
from ..skill_manager import get_skill_manager
from datetime import datetime
from .dataClasses import Context, UserInfo

from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver
from typing import Optional


logger = get_logger(__name__)


class ResearchAgent:

    def __init__(
        self, model: str = "gpt-5-mini", single_agent: bool = False, checkpointer=None
    ):
        self.skill_manager = get_skill_manager()
        self.store = (
            PostgresSaver.from_conn_string(POSTGRES_CHECKPOINT_URL)
            if checkpointer is None
            else checkpointer
        )
        self.checkpointer = self.store.__enter__()
        self.checkpointer.setup()
        self.tools = [
            chunk_retriever_tool,
            think_tool,
            save_user_info,
            retrieve_full_content_tool,
            document_catalogue_search_tool,
        ]
        self.model = model
        # if single_agent is True, we add the skill management tools to the agent's toolset
        # single_agent mode is meant for when this agent is used as a standalone agent without an orchestrator delegating to it, so it needs the skill management tools to be able to learn and store skills on its own
        if single_agent:
            self.tools += [
                add_skill_tool,
                get_skill_tool,
                list_skills_tool,
                update_skill_tool,
                delete_skill_tool,
            ]

        
        self.llm = ChatOpenAI(model=self.model, temperature=0)
        self.agent = create_deep_agent(
            model=self.llm,
            tools=self.tools,
            store= self.checkpointer,
            system_prompt=self._build_system_prompt(single_agent=single_agent),
            middleware=[context_editing_mw, tool_limit_mw],
            checkpointer=self.checkpointer,
            context_schema=Context,
        )

        logger.info(f"AgenticRAG initialized with model: {self.model}")

    def shutdown(self):
        self.store.__exit__(None, None, None)

    def _build_system_prompt(self, single_agent: bool = False) -> str:
        """Build the system prompt with injected skills."""
        if single_agent:
            skills = self.skill_manager.get_skills_for_prompt()
            if not skills:
                skills = "No skills stored yet. Whenever you learn a valuable, complex new skill, use the add_skill_tool to store it."

            return system_prompt_single_agent.format(
                date=datetime.now().strftime("%Y-%m-%d"),
                skills=skills,
            )
        else:
            return system_prompt_subagent.format(
                date=datetime.now().strftime("%Y-%m-%d"),
                skills="",
            )

    def refresh_system_prompt(self) -> None:
        """Refresh the system prompt with updated skills.

        Call this when skills are modified to update the agent's context.
        """
        # Note: This would need to update the agent's system prompt
        # The exact implementation depends on how deepagents handles updates
        pass

    def as_subagent(
        self,
        name: str = "document-agent",
        description: str = "Handles document-based queries using the RAG toolkit",
    ) -> dict:
        """Return a deepagents SubAgent dictionary.

        Matches the documented `subagents` shape: name, description, system_prompt,
        tools, and optional model override (here we reuse this agent's model).
        """
        return {
            "name": name,
            "description": description,
            "system_prompt": self._build_system_prompt(),
            "tools": self.tools,
            "model": self.llm,
        }
