"""Helpers for building the LangChain SQL toolkit.

These utilities mirror the patterns from the LangChain SQL agent documentation
and only rely on the default toolkit components.
"""

from typing import Tuple, List, Optional, Dict

from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import tool

from ..skill_manager import get_schema_manager, get_sql_query_manager
from ....config.config import LMSTUDIO_BASE_URL, OPENAI_API_KEY


@tool(parse_docstring=True)
def add_table_schema_tool(
    table_name: str,
    short_description: str,
    schema_documentation: str,
) -> str:
    """Add or document a database table schema to the schema directory.

    Use this tool to document table schemas in an LLM-optimized format.
    This helps you remember what each table contains, its relationships,
    and how to query it effectively.

    The schema documentation should include:
    - Column names, types, and their purposes
    - Primary and foreign key relationships
    - Common query patterns and examples
    - Business context (what data the table stores)

    Args:
        table_name: Unique identifier for the table (e.g., 'users', 'orders', 'database.schema.table').
            Maximum 100 characters.
        short_description: Brief description of what the table stores (max 160 chars).
            For example, "Stores customer order history with items, quantities, and timestamps".
        schema_documentation: Detailed LLM-optimized documentation including columns,
            relationships, constraints, and example queries.

    Returns:
        Success message if schema was added, or an error message describing what went wrong.
    """
    schema_manager = get_schema_manager()
    success, message = schema_manager.add_table_schema(
        table_name, short_description, schema_documentation
    )
    return message


@tool(parse_docstring=True)
def get_table_schema_tool(table_name: str) -> str:
    """Retrieve the detailed schema documentation for a specific table.
    
    Use this when you need to understand a table's structure before writing a query.
    This also marks the table as recently accessed for the LRU cache.
    
    Args:
        table_name: The exact name of the table to retrieve documentation for.
    
    Returns:
        The full schema documentation if found, or an error message if not found.
    """
    schema_manager = get_schema_manager()
    schema = schema_manager.get_table_schema(table_name)
    
    if schema:
        return f"## {schema.name}\n{schema.description}\n\n{schema.content}"
    else:
        available = schema_manager.list_skills(limit=10)
        if available:
            suggestion = "\n\nAvailable tables: " + ", ".join(s.name for s in available)
        else:
            suggestion = "\n\nNo table schemas documented yet."
        return f"Table schema '{table_name}' not found.{suggestion}"


@tool(parse_docstring=True)
def list_table_schemas_tool() -> str:
    """List all documented table schemas in the directory.
    
    Returns tables sorted by most recently accessed (LRU order).
    Use this to see what database knowledge is available.
    
    Returns:
        A formatted list of all documented tables with their descriptions.
    """
    schema_manager = get_schema_manager()
    schemas = schema_manager.list_skills(limit=50)
    
    if not schemas:
        return "No table schemas documented yet. Use add_table_schema to document your first table."
    
    lines = [f"**Documented Tables ({len(schemas)} total)**\n"]
    for i, schema in enumerate(schemas, 1):
        lines.append(f"{i}. **{schema.name}** - {schema.description}")
    
    return "\n".join(lines)


@tool(parse_docstring=True)
def update_table_schema_tool(
    table_name: str,
    new_description: Optional[str] = None,
    new_schema_documentation: Optional[str] = None,
) -> str:
    """Update an existing table schema's description or documentation.
    
    Use this to refine schema documentation with new insights or changes.
    At least one of new_description or new_schema_documentation must be provided.
    
    Args:
        table_name: The name of the table to update.
        new_description: New short description (max 160 chars). Optional.
        new_schema_documentation: New detailed documentation. Optional.
    
    Returns:
        Success message if updated, or error message describing what went wrong.
    """
    if new_description is None and new_schema_documentation is None:
        return "Error: Must provide either new_description or new_schema_documentation to update."
    
    schema_manager = get_schema_manager()
    success, message = schema_manager.update_table_schema(
        table_name, new_description, new_schema_documentation
    )
    return message


@tool(parse_docstring=True)
def delete_table_schema_tool(table_name: str) -> str:
    """Delete a table schema from the directory.
    
    Use this to remove outdated schema documentation.
    This action cannot be undone.
    
    Args:
        table_name: The name of the table schema to delete.
    
    Returns:
        Success message if deleted, or error message if not found.
    """
    schema_manager = get_schema_manager()
    success, message = schema_manager.delete_table_schema(table_name)
    return message


@tool(parse_docstring=True)
def save_sql_query_tool(
    query_name: str,
    short_description: str,
    sql_query: str,
) -> str:
    """Save a reusable SQL query pattern to the SQL query directory.

    Use this to persist useful queries for future tasks. Entries are kept in
    a dedicated SQL query LRU store (separate from schema and general skills).

    Args:
        query_name: Unique identifier for the saved query (max 100 chars).
        short_description: Brief description of what this query returns (max 160 chars).
        sql_query: The SQL query text to save.

    Returns:
        Success or error message.
    """
    query_manager = get_sql_query_manager()
    success, message = query_manager.add_saved_query(
        query_name, short_description, sql_query
    )
    return message


@tool(parse_docstring=True)
def get_saved_sql_query_tool(query_name: str) -> str:
    """Retrieve a saved SQL query by name.

    This marks the query as recently accessed for LRU ordering.

    Args:
        query_name: Exact saved query name.

    Returns:
        Saved query content if found, otherwise a not-found message.
    """
    query_manager = get_sql_query_manager()
    query = query_manager.get_saved_query(query_name)

    if query:
        return f"## {query.name}\n{query.description}\n\n```sql\n{query.content}\n```"

    available = query_manager.list_saved_queries(limit=10)
    if available:
        suggestion = "\n\nAvailable saved queries: " + ", ".join(q.name for q in available)
    else:
        suggestion = "\n\nNo saved SQL queries yet."
    return f"Saved SQL query '{query_name}' not found.{suggestion}"


@tool(parse_docstring=True)
def list_saved_sql_queries_tool() -> str:
    """List saved SQL queries in LRU order.

    Returns:
        A formatted list of saved query names and descriptions.
    """
    query_manager = get_sql_query_manager()
    queries = query_manager.list_saved_queries(limit=50)

    if not queries:
        return "No saved SQL queries yet. Use save_sql_query_tool to add one."

    lines = [f"**Saved SQL Queries ({len(queries)} total)**\n"]
    for i, query in enumerate(queries, 1):
        lines.append(f"{i}. **{query.name}** - {query.description}")
    return "\n".join(lines)


@tool(parse_docstring=True)
def update_saved_sql_query_tool(
    query_name: str,
    new_description: Optional[str] = None,
    new_sql_query: Optional[str] = None,
) -> str:
    """Update a saved SQL query entry.

    At least one of new_description or new_sql_query must be provided.

    Args:
        query_name: Saved query name to update.
        new_description: Optional new short description.
        new_sql_query: Optional replacement SQL query text.

    Returns:
        Success or error message.
    """
    if new_description is None and new_sql_query is None:
        return "Error: Must provide either new_description or new_sql_query to update."

    query_manager = get_sql_query_manager()
    success, message = query_manager.update_saved_query(
        query_name, new_description, new_sql_query
    )
    return message


@tool(parse_docstring=True)
def delete_saved_sql_query_tool(query_name: str) -> str:
    """Delete a saved SQL query entry.

    Args:
        query_name: Saved query name to delete.

    Returns:
        Success or error message.
    """
    query_manager = get_sql_query_manager()
    success, message = query_manager.delete_saved_query(query_name)
    return message


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





def get_schema_directory_tools() -> List:
    """Get all schema directory management tools."""
    return [
        add_table_schema_tool,
        get_table_schema_tool,
        list_table_schemas_tool,
        update_table_schema_tool,
        delete_table_schema_tool,
    ]


def get_sql_query_directory_tools() -> List:
    """Get all saved SQL query directory management tools."""
    return [
        save_sql_query_tool,
        get_saved_sql_query_tool,
        list_saved_sql_queries_tool,
        update_saved_sql_query_tool,
        delete_saved_sql_query_tool,
    ]


def create_sql_database(uri: str) -> SQLDatabase:
	"""Instantiate a `SQLDatabase` from a SQLAlchemy URI.

	This follows the documented `SQLDatabase.from_uri` usage for connecting to a
	relational database.
	"""

	return SQLDatabase.from_uri(uri)


def create_llm(model_name: str) -> BaseLanguageModel:
	"""Create a chat model suited for tool calling.

	Use ChatOpenAI directly to satisfy SQLDatabaseToolkit's BaseLanguageModel
	expectation and keep temperature at zero for deterministic SQL generation.
	"""

	return ChatOpenAI(model=model_name, base_url=LMSTUDIO_BASE_URL, api_key=OPENAI_API_KEY, temperature=0)


def create_toolkit(db: SQLDatabase, llm: BaseLanguageModel) -> SQLDatabaseToolkit:
	"""Build the SQL toolkit that provides list/schema/query/checker tools."""

	return SQLDatabaseToolkit(db=db, llm=llm)


def prepare_sql_agent_components(
	uri: str, model_name: str
) -> Tuple[SQLDatabase, BaseLanguageModel, List]:
	"""Create database, model, and tools for the SQL agent.

	Returns a tuple of `(db, llm, tools)` ready to be passed into
	`langchain.agents.create_agent`, aligning with the documented workflow.
	"""

	db = create_sql_database(uri)
	llm = create_llm(model_name)
	toolkit = create_toolkit(db, llm)
	tools = toolkit.get_tools()
	return db, llm, tools
