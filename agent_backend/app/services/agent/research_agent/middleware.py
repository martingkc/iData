from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents import  AgentState
from langgraph.runtime import Runtime
from typing import Any
from langchain.agents.middleware import before_model
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.agents.middleware import ContextEditingMiddleware, ClearToolUsesEdit


context_editing_mw = ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=50000,
                    keep=4,
                ),
            ],
        )


tool_limit_mw = ToolCallLimitMiddleware(thread_limit=20, run_limit=10)