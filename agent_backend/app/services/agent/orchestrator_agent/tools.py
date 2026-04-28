
from typing import Optional

from ..skill_manager import get_skill_manager
from ....config.config import SQL_AGENTDB_URI
from ....utils.logger import get_logger
from ..sql_agent.sql_agent import SQLAgent
from ..research_agent.research_agent import ResearchAgent
from ..coding_agent.coding_agent import CodingAgent
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from .dataClasses import Context, UserInfo

import os



logger = get_logger(__name__)
_sql_agent: Optional[SQLAgent] = None
_document_agent: Optional[ResearchAgent] = None
_coding_agent: Optional[CodingAgent] = None


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"



def _get_sql_agent() -> SQLAgent:
    """Lazy-initialize the SQL subagent using documented LangChain defaults."""

    global _sql_agent
    if _sql_agent is not None:
        return _sql_agent

    db_uri = SQL_AGENTDB_URI
    if not db_uri:
        raise RuntimeError(
            "SQL_AGENT_DB_URI is not set. Provide a SQLAlchemy URI (e.g., postgres://... or sqlite:///file.db)."
        )


    top_k = int(os.getenv("SQL_AGENT_TOP_K", "10"))
    enable_review = os.getenv("SQL_AGENT_ENABLE_REVIEW", "false").lower() == "true"
    model_name = os.getenv("SQL_AGENT_MODEL", "gpt-5-mini")

    # If using SQLite, validate the file exists to avoid connection surprises.
    if db_uri.startswith("sqlite:///"):
        sqlite_path = db_uri.replace("sqlite:///", "", 1)
        if not os.path.exists(sqlite_path):
            raise RuntimeError(
                f"SQLite file not found at {sqlite_path}. Set SQL_AGENTDB_URI to a valid path."
            )

    _sql_agent = SQLAgent(
        db_uri=db_uri,
        model_name=model_name,
        top_k=top_k,
        enable_review=enable_review,
    )
    logger.info(
        "Initialized SQL subagent with model=%s, top_k=%s, review=%s",
        model_name,
        top_k,
        enable_review,
    )
    return _sql_agent


def get_sql_subagent(
    name: str = "sql-agent",
    description: str = "Handles structured/relational queries via SQL toolkit",
) -> dict:
    """Return a deepagents-compatible subagent dict for SQL tasks."""

    agent = _get_sql_agent()
    return agent.as_subagent(name=name, description=description)



def _get_document_agent() -> ResearchAgent:
    """Lazy-initialize the Document subagent using documented LangChain defaults."""

    global _document_agent
    if _document_agent is not None:
        return _document_agent
    _document_agent = ResearchAgent()
    logger.info(
        "Initialized Document subagent"
    )
    return _document_agent

def get_document_subagent(
    name: str = "document-agent",
    description: str = "Handles document-based queries via RAG toolkit",
) -> dict:
    """Return a deepagents-compatible subagent dict for document tasks."""
    agent = _get_document_agent()
    return agent.as_subagent(name=name, description=description)


def _get_coding_agent() -> CodingAgent:
    """Lazy-initialize the coding subagent."""

    global _coding_agent
    if _coding_agent is not None:
        return _coding_agent

    model_name = os.getenv("CODING_AGENT_MODEL", "gpt-5-mini")
    _coding_agent = CodingAgent(model_name=model_name)
    logger.info("Initialized Coding subagent with model=%s", model_name)
    return _coding_agent


def get_coding_subagent(
    name: str = "coding-agent",
    description: str = "Handles coding, debugging, refactoring, and implementation tasks",
) -> dict:
    """Return a deepagents-compatible subagent dict for coding tasks."""
    agent = _get_coding_agent()
    return agent.as_subagent(name=name, description=description)

@tool(parse_docstring=True)
def add_skill_tool(skill_name: str, short_description: str, skill_content: str) -> str:
    """Add a new skill to the agent's skill library for future reference.
    
    Use this tool when you learn a new technique, workflow, or specialized knowledge
    that would be valuable to remember for future conversations. Skills are stored
    persistently and the most recently used skills are available in your context.
    
    Args:
        skill_name: Unique identifier for the skill. Must be unique across all skills.
            Can contain letters, numbers, hyphens, underscores, dots, and spaces.
            Maximum 100 characters.
        short_description: Brief description of what the skill does or when to use it.
            Maximum 160 characters. This will be shown in the skills list.
        skill_content: The full skill content including instructions, steps, examples,
            or any relevant information. This is the actual knowledge being stored.
    
    Returns:
        Success message if skill was added, or error message describing what went wrong.
    """
    skill_manager = get_skill_manager()
    success, message = skill_manager.add_skill(skill_name, short_description, skill_content)
    
    if success:
        logger.info(f"Skill added via tool: {skill_name}")
        return message
    else:
        logger.warning(f"Failed to add skill '{skill_name}': {message}")
        return f"Failed to add skill: {message}"


@tool(parse_docstring=True)
def get_skill_tool(skill_name: str) -> str:
    """Retrieve the full content of a specific skill by name.
    
    Use this when you need to recall the details of a previously stored skill.
    This also marks the skill as recently used, keeping it in your active context.
    
    Args:
        skill_name: The exact name of the skill to retrieve.
    
    Returns:
        The full skill content if found, or an error message if the skill doesn't exist.
    """
    skill_manager = get_skill_manager()
    skill = skill_manager.get_skill(skill_name)
    
    if skill:
        return f"**{skill.name}**\n{skill.description}\n\n---\n\n{skill.content}"
    else:
        return f"Skill '{skill_name}' not found. Use list_skills to see available skills."


@tool(parse_docstring=True)
def list_skills_tool() -> str:
    """List all available skills in your skill library.
    
    Returns the most recently used skills first (LRU order).
    Use this to see what skills you have available and find relevant ones to use.
    
    Returns:
        A formatted list of all skills with their names and descriptions.
    """
    skill_manager = get_skill_manager()
    skills = skill_manager.list_skills(limit=50)  # Get more for listing
    
    if not skills:
        return "No skills stored yet. Use add_skill to create your first skill."
    
    lines = [f"**Available Skills ({len(skills)} total)**\n"]
    for i, skill in enumerate(skills, 1):
        lines.append(f"{i}. **{skill.name}** - {skill.description}")
    
    return "\n".join(lines)


@tool(parse_docstring=True)
def update_skill_tool(
    skill_name: str,
    new_description: Optional[str] = None,
    new_content: Optional[str] = None,
) -> str:
    """Update an existing skill's description or content.
    
    Use this to refine or expand a skill with new information.
    At least one of new_description or new_content must be provided.
    
    Args:
        skill_name: The name of the skill to update.
        new_description: New short description (max 160 chars). Optional.
        new_content: New skill content. Optional.
    
    Returns:
        Success message if updated, or error message describing what went wrong.
    """
    if new_description is None and new_content is None:
        return "Error: Must provide either new_description or new_content to update."
    
    skill_manager = get_skill_manager()
    success, message = skill_manager.update_skill(skill_name, new_description, new_content)
    
    if success:
        logger.info(f"Skill updated via tool: {skill_name}")
        return message
    else:
        logger.warning(f"Failed to update skill '{skill_name}': {message}")
        return f"Failed to update skill: {message}"


@tool(parse_docstring=True)
def delete_skill_tool(skill_name: str) -> str:
    """Delete a skill from the skill library.
    
    Use this to remove outdated or incorrect skills.
    This action cannot be undone.
    
    Args:
        skill_name: The name of the skill to delete.
    
    Returns:
        Success message if deleted, or error message if skill wasn't found.
    """
    skill_manager = get_skill_manager()
    success, message = skill_manager.delete_skill(skill_name)
    
    if success:
        logger.info(f"Skill deleted via tool: {skill_name}")
        return message
    else:
        return f"Failed to delete skill: {message}"
        
@tool
def save_user_info(user_info: UserInfo, runtime: ToolRuntime[Context]) -> str:
    """Save user information to persistent storage.
    
    Use this tool whenever you learn new information about the user, such as:
    - User's name or personal details
    - User's preferences (likes, dislikes, interests)
    - User's goals or objectives
    - Any facts the user has shared about themselves
    
    This ensures the user's information is remembered for future conversations.
    
    Args:
        user_info: A UserInfo object containing the user's details including:
            - name: The user's name
            - preferences: What the user likes or is interested in
            - goals: What the user wants to accomplish
            - other_info: Any other relevant information about the user
    
    Returns:
        Confirmation message indicating the user info was successfully saved
    """
    # Access the store - same as that provided to `create_agent`
    store = runtime.store 
    user_id = runtime.context.user_id 
    # Store data in the store (namespace, key, data)
    store.put(("users",), user_id, user_info) 
    return f"Successfully saved user info for {user_id}: {user_info}"
