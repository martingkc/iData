import os
from typing import Optional
from ....config.config import SQL_AGENTDB_URI
from bson import ObjectId
from flask import jsonify
from langchain_openai import ChatOpenAI
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from ...vector_db.milvus_connector import MilvusConnector
from ...vector_db.document_catalogue_connector import DocumentCatalogueConnector
from ....db.mongodb_connector import MongoDBConnector
from ....config.config import FILE_DB_NAME, UNSTRUCTURED_COLLECTION
from ....utils.logger import get_logger
from ..sql_agent.sql_agent import SQLAgent
from ..skill_manager import get_skill_manager
from .dataClasses import Context, UserInfo
"""Research and delegation tools for the supervisor agent."""


logger = get_logger(__name__)

vector_store = MilvusConnector()
_document_catalogue: Optional[DocumentCatalogueConnector] = None
_sql_agent: Optional[SQLAgent] = None


def _get_document_catalogue() -> DocumentCatalogueConnector:
    """Lazy-initialize the document catalogue connector."""
    global _document_catalogue
    if _document_catalogue is None:
        _document_catalogue = DocumentCatalogueConnector()
    return _document_catalogue

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




@tool(parse_docstring=True)
def retrieve_full_content_tool(document_id: str) -> str:
    """Retrieve and read the complete full-text content of a specific document.
    
    This tool loads the entire parsed document and its summary context from the database.
    Use it when chunk search results are incomplete or don't contain enough detail.
    
    IMPORTANT: Always use this tool after chunks are found to be insufficient!
    - Extract the document_id from retrieve_documents results (e.g., "doc_id=..." from the "Source" line)
    - Pass that exact ID here to load the full document
    - Then analyze the full text to find the answer
    
    When to use:
    - Chunk search returned results but they're too short or lack context
    - You need to read the full document to find specific details
    - Multiple chunks reference the same document but don't have the full picture
    - The user needs comprehensive information from one specific document
    
    Args:
        document_id: The exact document ID from the search results metadata (e.g., "507f191e810c19729de860ea", copy exactly from "doc_id=" in chunk results)
    
    Returns:
        The complete document context summary and full parsed text.
        Returns an error message if the document ID is not found.
    """
    try:
        connector = MongoDBConnector()
        collection = connector.get_collection(FILE_DB_NAME, UNSTRUCTURED_COLLECTION)
        documents = collection.find_one({"_id": ObjectId(document_id)},
                {"_id": 1, "context": 1, "parsed": 1})
        
        if not documents:
            return f"Document with ID '{document_id}' not found in the database."
        
        doc = documents
        context = doc.get("context", "No context available")
        parsed = doc.get("parsed", "No parsed content available")
        
        # Format as readable string
        result = f"""
                Document ID: {document_id}

                Context Summary:
                {context}

                Full Parsed Content:
                {parsed}
                """
        return result
    except Exception as e:
        logger.error(f"Error in retrieve_documents: {e}", exc_info=True)
        return f"Error retrieving documents: {e}"
    



@tool
def chunk_retriever_tool(query: str, k: int, runtime: ToolRuntime[Context], filter_expr: str = "") -> str:
    """
    Search chunks to find relevant information to retrieve chunks of documents.
    Automatically applies path filters from the request context if provided.
    You can also specify custom filter expressions to narrow down results.

    Args:
        query: Search query for relevant documents.
        k: Number of documents to retrieve.
        runtime: Injected runtime context with path filters.
        filter_expr: Optional Milvus filter expression to narrow down results.
            Examples:
            - Filter by chunk type: 'chunk_type == "table"' or 'chunk_type == "text"'
            - Filter by page number: 'pages[0] == 5' or 'pages[0] >= 10 and pages[0] <= 20'
            - Filter by document ID: 'document_id == "507f1f77bcf86cd799439011"'
            - Filter by local path: 'local_path like "%Data Warehouse%"'
            - Combine filters: 'chunk_type == "table" and pages[0] >= 5'

    Returns:
        A formatted string with retrieved document chunks, their ids,
        chunk indexes, and relevance scores.
    """
    try:
        # Build Milvus filter expression from context path_filters
        expr_parts = []
        path_filters = runtime.context.path_filters if runtime.context else None
        if path_filters:
            # Filter by local_path field in metadata
            # Support both exact file matches and folder prefix matches
            # Use 'like' operator for folder paths (ending with /) and 'in' for exact file matches
            conditions = []
            
            for p in path_filters:
                escaped = p.replace('"', '\\"').replace("'", "\\'")
                # Check if this looks like a folder (no file extension or ends with /)
                # We'll use prefix matching for all paths to catch both files and folders
                # This way selecting a folder includes all files inside it
                conditions.append(f'local_path like "{escaped}%"')
            
            if conditions:
                expr_parts.append(f"({' or '.join(conditions)})")
        
        # Add user-provided filter expression
        if filter_expr and filter_expr.strip():
            expr_parts.append(f"({filter_expr.strip()})")
        
        # Combine all expressions with AND
        expr = " and ".join(expr_parts) if expr_parts else None
        
        if expr:
            logger.info(f"Applying filter expression: {expr}")

        retrieved_docs = vector_store.search(query, k=k, expr=expr)
        if not retrieved_docs:
            return "No relevant documents found in the database."
        parts = []
        for i, doc in enumerate(retrieved_docs, start=1):
            metadata = doc.metadata or {}
            doc_id = metadata.get("document_id", "Unknown")
            chunk_idx = metadata.get("chunk_index", "?")
            chunk_id = metadata.get("pk", "Unknown")  # Milvus primary key for chunk retrieval
            
            # Use bm25_text from metadata (includes tables), fallback to page_content
            text = metadata.get("bm25_text", "") or doc.page_content or ""
            
            # Debug: Log chunk size
            logger.info(f"------------------------------- {doc_id}: {len(text)} chars")
            
            parts.append(
                f"document_id: {doc_id} "
                f"chunk_id: {chunk_id} "
                f"chunk_index={chunk_idx}\n"
                f"{text}"
            )
        return "\n\n".join(parts)
    except Exception as e:
        logger.error(f"Error in retrieve_documents: {e}", exc_info=True)
        return f"Error retrieving documents: {e}"


@tool(parse_docstring=True)
def document_catalogue_search_tool(query: str, k: int = 5) -> str:
    """Search the document catalogue to discover which documents might answer the user's query.
    
    This tool searches across all indexed documents using hybrid BM25 + semantic search
    over each document's context/summary. Use this as a DISCOVERY step to identify
    relevant documents BEFORE retrieving their content.
    
    **IMPORTANT WORKFLOW:**
    1. Call this tool first to find which documents are relevant to the user's query
    2. Extract the Document IDs from the results
    3. Use those Document IDs with:
       - **chunk_retriever_tool**: Pass document_id in filter_expr to search chunks within those documents
         Example: filter_expr='document_id == "507f1f77bcf86cd799439011"'
       - **retrieve_full_content_tool**: Pass document_id to load the complete document
    
    This tool does NOT retrieve document content - it only identifies relevant documents.
    
    Args:
        query: Search query describing the topic or information you're looking for.
        k: Number of documents to retrieve (default: 5).
    
    Returns:
        A list of matching documents with their IDs (use these IDs with other tools), paths, and summaries.
    """
    try:
        catalogue = _get_document_catalogue()
        docs = catalogue.search(query, k=k)
        
        if not docs:
            return "No relevant documents found in the catalogue."
        
        parts = ["Found relevant documents. Use the Document IDs below with chunk_retriever_tool or retrieve_full_content_tool:\n"]
        for i, doc in enumerate(docs, start=1):
            metadata = doc.metadata or {}
            doc_id = metadata.get("document_id", "Unknown")
            local_path = metadata.get("local_path", "Unknown path")
            remote_path = metadata.get("remote_path", "")
            context = doc.page_content or metadata.get("bm25_text", "No summary available")
            
            # Format document info - emphasize the document_id for use with other tools
            path_display = remote_path if remote_path else local_path
            parts.append(
                f"[{i}] **Document ID: {doc_id}** (use this ID with other tools)\n"
                f"    Path: {path_display}\n"
                f"    Summary: {context}"
            )
        
        parts.append("\n**Next step:** Use chunk_retriever_tool with filter_expr='document_id == \"<ID>\"' or retrieve_full_content_tool with the document_id.")
        
        return "\n\n".join(parts)
    except Exception as e:
        logger.error(f"Error in document_catalogue_search: {e}", exc_info=True)
        return f"Error searching document catalogue: {e}"

        
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
