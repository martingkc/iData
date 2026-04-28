"""Optional middleware for SQL agents.

Implements the human-in-the-loop middleware pattern shown in the LangChain SQL
agent tutorial. When enabled, the agent pauses before executing `sql_db_query`
so a human can approve or reject the action.
"""

from typing import List, Optional, Tuple

from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver


def build_review_middleware(
	enabled: bool,
) -> Tuple[List[HumanInTheLoopMiddleware], Optional[InMemorySaver]]:
	"""Create middleware and checkpointer for human review.

	Returns an empty list and ``None`` when review is disabled so callers can
	pass the result directly into ``create_agent`` keyword arguments.
	"""

	if not enabled:
		return [], None

	middleware = [
		HumanInTheLoopMiddleware(
			interrupt_on={"sql_db_query": True},
			description_prefix="Tool execution pending approval",
		)
	]
	return middleware, InMemorySaver()
