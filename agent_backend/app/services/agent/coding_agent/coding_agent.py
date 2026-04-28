"""Coding subagent with dedicated skills library."""

import asyncio
import os
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from .prompts import SYSTEM_PROMPT_TEMPLATE
from .tools import get_coding_tools
from ..skill_manager import get_coding_skill_manager
from ....utils.logger import get_logger


logger = get_logger(__name__)


class CodingAgent:
    """Subagent specialized in coding and engineering tasks."""

    def __init__(self, model_name: str = "gpt-5-mini") -> None:
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.skill_manager = get_coding_skill_manager()
        self.tools = get_coding_tools() + self._load_jupyter_mcp_tools()

    def as_subagent(
        self,
        name: str = "coding-agent",
        description: str = "Handles coding, debugging, refactoring, and implementation tasks",
    ) -> dict:
        """Return a deepagents-compatible subagent dictionary."""
        return {
            "name": name,
            "description": description,
            "system_prompt": self._build_system_prompt(),
            "tools": self.tools,
            "model": self.llm,
        }

    def _build_system_prompt(self) -> str:
        skills = self.skill_manager.get_skills_for_prompt()
        if not skills:
            skills = (
                "No coding skills stored yet. "
                "When you learn reusable coding workflows, use add_coding_skill_tool."
            )
        return SYSTEM_PROMPT_TEMPLATE.format(skills=skills)

    def _build_jupyter_server_cfg(self) -> Optional[Dict[str, Dict[str, Any]]]:

        return {
            "jupyter": {
                "transport": "stdio",
                "command": "mcp-remote",
                "args": ["http://jupyterhub:8000/user/admin/mcp","--allow-http"],
                "env": {"JUPYTERHUB_API_TOKEN": "7504d3b3244142a283bd7b5472c84a8c"},
            }
        }

    async def _collect_mcp_tools(
        self, server_cfg: Dict[str, Dict[str, Any]]
    ) -> List[Any]:
        """Fetch MCP tools from configured server(s)."""
        client = MultiServerMCPClient(server_cfg)
        return await client.get_tools()

    def _load_jupyter_mcp_tools(self) -> List[Any]:
        """Load MCP tools from JupyterHub via mcp-remote."""
        server_cfg = self._build_jupyter_server_cfg()
        if not server_cfg:
            return []
        tools = asyncio.run(self._collect_mcp_tools(server_cfg))
        logger.info("Loaded %s Jupyter MCP tools for coding-agent.", len(tools))
        return tools
