"""Tools for the coding subagent."""

from typing import Optional, List

from langchain_core.tools import tool

from ..skill_manager import get_coding_skill_manager


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Record strategic reflection while solving coding tasks.

    Args:
        reflection: Short reasoning summary on findings, gaps, and next action.

    Returns:
        Confirmation message.
    """
    return f"Reflection recorded: {reflection}"


@tool(parse_docstring=True)
def add_coding_skill_tool(skill_name: str, short_description: str, skill_content: str) -> str:
    """Add a reusable coding skill to the coding-agent skill library.

    Args:
        skill_name: Unique skill name (max 100 chars).
        short_description: Brief description (max 160 chars).
        skill_content: Full reusable instructions/pattern.

    Returns:
        Success or error message.
    """
    skill_manager = get_coding_skill_manager()
    success, message = skill_manager.add_skill(skill_name, short_description, skill_content)
    return message if success else f"Failed to add skill: {message}"


@tool(parse_docstring=True)
def get_coding_skill_tool(skill_name: str) -> str:
    """Retrieve one coding skill by name.

    Args:
        skill_name: Exact skill name.

    Returns:
        Formatted skill content or not-found message.
    """
    skill_manager = get_coding_skill_manager()
    skill = skill_manager.get_skill(skill_name)
    if not skill:
        return f"Skill '{skill_name}' not found. Use list_coding_skills_tool to see available skills."
    return f"**{skill.name}**\n{skill.description}\n\n---\n\n{skill.content}"


@tool(parse_docstring=True)
def list_coding_skills_tool() -> str:
    """List coding skills in most-recently-used order.

    Returns:
        A formatted skills list.
    """
    skill_manager = get_coding_skill_manager()
    skills = skill_manager.list_skills(limit=50)
    if not skills:
        return "No coding skills stored yet. Use add_coding_skill_tool to create your first skill."
    lines = [f"**Available Coding Skills ({len(skills)} total)**\n"]
    for i, skill in enumerate(skills, 1):
        lines.append(f"{i}. **{skill.name}** - {skill.description}")
    return "\n".join(lines)


@tool(parse_docstring=True)
def update_coding_skill_tool(
    skill_name: str,
    new_description: Optional[str] = None,
    new_content: Optional[str] = None,
) -> str:
    """Update a coding skill.

    Args:
        skill_name: Existing skill name.
        new_description: Optional new short description.
        new_content: Optional new skill content.

    Returns:
        Success or error message.
    """
    if new_description is None and new_content is None:
        return "Error: Must provide either new_description or new_content to update."
    skill_manager = get_coding_skill_manager()
    success, message = skill_manager.update_skill(skill_name, new_description, new_content)
    return message if success else f"Failed to update skill: {message}"


@tool(parse_docstring=True)
def delete_coding_skill_tool(skill_name: str) -> str:
    """Delete a coding skill.

    Args:
        skill_name: Skill name to delete.

    Returns:
        Success or error message.
    """
    skill_manager = get_coding_skill_manager()
    success, message = skill_manager.delete_skill(skill_name)
    return message if success else f"Failed to delete skill: {message}"


def get_coding_tools() -> List:
    """Return all coding-agent tools."""
    return [
        think_tool,
        add_coding_skill_tool,
        get_coding_skill_tool,
        list_coding_skills_tool,
        update_coding_skill_tool,
        delete_coding_skill_tool,
    ]

