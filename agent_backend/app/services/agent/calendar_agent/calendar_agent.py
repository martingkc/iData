from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from ....config.config import LMSTUDIO_BASE_URL, OPENAI_API_KEY
from ....utils.logger import get_logger
from .prompts import system_prompt
from .tools import (
    list_calendars_tool,
    list_calendar_events_tool,
    get_calendar_event_tool,
    create_calendar_event_tool,
    update_calendar_event_tool,
    delete_calendar_event_tool,
)
from ..orchestrator_agent.dataClasses import Context

logger = get_logger(__name__)


class CalendarAgent:

    def __init__(self, model: str = "gemma-4"):
        self.model = model
        self.llm = ChatOpenAI(
            model=self.model,
            base_url=LMSTUDIO_BASE_URL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
        self.tools = [
            list_calendars_tool,
            list_calendar_events_tool,
            get_calendar_event_tool,
            create_calendar_event_tool,
            update_calendar_event_tool,
            delete_calendar_event_tool,
        ]
        self._compiled = create_agent(
            self.llm,
            system_prompt=self._build_system_prompt(),
            tools=self.tools,
            context_schema=Context,
        )
        logger.info("CalendarAgent initialized with model: %s", self.model)

    def _build_system_prompt(self) -> str:
        return system_prompt.format(date=datetime.now().strftime("%Y-%m-%d"))

    def as_subagent(
        self,
        name: str = "calendar-agent",
        description: str = (
            "Manages Google Calendar events: list, create, update, and delete events. "
            "Use for any scheduling, meeting management, or calendar-related requests."
        ),
    ) -> dict:
        """Return a deepagents-compatible CompiledSubAgent dict.

        Using a pre-compiled runnable ensures context_schema=Context is set,
        so runtime.context.user_id is available inside calendar tools.
        """
        return {
            "name": name,
            "description": description,
            "runnable": self._compiled,
        }
