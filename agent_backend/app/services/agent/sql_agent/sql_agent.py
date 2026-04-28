"""LangChain SQL agent built with documented defaults."""

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig

from .middleware import build_review_middleware
from .tools import (
	prepare_sql_agent_components,
	get_schema_directory_tools,
	get_sql_query_directory_tools,
)
from ..skill_manager import get_schema_manager, get_sql_query_manager
from ....utils.logger import get_logger


logger = get_logger(__name__)


SYSTEM_PROMPT_TEMPLATE = """
You are a SQL database assistant.

Goal:
Given a user question, you must (1) decide what tables/columns are needed, (2) write a syntactically correct {dialect} SQL query, (3) execute it, (4) answer from the results.

Hard constraints:
- Read-only only: NO DML/DDL (no INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE).
- Never use SELECT * . Select only needed columns.
- Always double-check the query before execution.
- If execution errors, revise the query and retry (max 2 retries), explaining the fix briefly.

Tooling policy (MANDATORY):
You have two sources of schema knowledge:
A) Schema Directory (preferred)
B) Live database introspection (fallback)
C) Previously saved SQL queries 


Execution rules:
- Before writing a query from scratch, check saved SQL queries for reusable patterns:
  - always call list_saved_sql_queries_tool
  - then get_saved_sql_query_tool for 1-3 relevant entries
  - adapt and execute if applicable
- After schema is known, write the SQL query.
- Call think_tool again briefly to sanity-check joins, filters, grouping, and LIMIT.
- Execute the query.
- If the final query is reusable (common aggregation/filter/join pattern), save it with save_sql_query_tool.
- Answer strictly based on returned rows. If results are empty, say so and suggest a plausible next query (but do not run it unless asked).

Output format:
- Provide: (a) the SQL query you ran, (b) a concise interpretation of results, (c) the final answer.

Schema Directory Tools available:
- add_table_schema_tool(name, description<=160 chars, schema doc)
- get_table_schema_tool(name)
- list_table_schemas_tool()
- update_table_schema_tool(name, new schema doc)
- delete_table_schema_tool(name)

Saved SQL Query Tools available:
- save_sql_query_tool(name, description<=160 chars, sql query)
- get_saved_sql_query_tool(name)
- list_saved_sql_queries_tool()
- update_saved_sql_query_tool(name, description/sql)
- delete_saved_sql_query_tool(name)

Documented Tables (most recently accessed first):
{schemas}

Saved SQL Queries (most recently accessed first):
{queries}
"""


class SQLAgent:
	"""Agent that answers questions against a SQL database using LangChain tools."""

	def __init__(
		self,
		db_uri: str,
		model_name: str = "gpt-5-mini",
		top_k: int = 5,
		enable_review: bool = False,
	) -> None:
		self.db_uri = db_uri
		self.model_name = model_name
		self.top_k = top_k
		self.schema_manager = get_schema_manager()
		self.query_manager = get_sql_query_manager()

		self.db, self.llm, base_tools = prepare_sql_agent_components(
			db_uri, model_name
		)
		
		# Add schema and saved-query directory tools to the toolkit
		self.tools = (
			base_tools
			+ get_schema_directory_tools()
			+ get_sql_query_directory_tools()
		)

		middleware, checkpointer = build_review_middleware(enable_review)
		agent_kwargs = {}
		if middleware:
			agent_kwargs["middleware"] = middleware
		if checkpointer:
			agent_kwargs["checkpointer"] = checkpointer

		self.agent = create_agent(
			self.llm,
			self.tools,
			system_prompt=self._build_system_prompt(),
			**agent_kwargs,
		)

		logger.info(
			"SQL agent initialized for %s with dialect %s", model_name, self.db.dialect
		)

	def as_subagent(
		self,
		name: str = "sql-agent",
		description: str = "Handles structured/relational queries using the SQL toolkit",
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

	def _build_system_prompt(self) -> str:
		"""Build the system prompt with injected schema and saved-query directories."""
		schemas = self.schema_manager.get_schemas_for_prompt()
		if not schemas:
			schemas = "No tables documented yet. Use add_table_schema_tool to document tables."
		queries = self.query_manager.get_queries_for_prompt()
		if not queries:
			queries = "No saved SQL queries yet. Use save_sql_query_tool for reusable query patterns."
		print(queries)
		return SYSTEM_PROMPT_TEMPLATE.format(
			dialect=self.db.dialect,
			top_k=self.top_k,
			schemas=schemas,
			queries=queries,
		)
