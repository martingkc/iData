"""Persistent LRU Cache Skill Manager for Agent Skills.

This module provides a MongoDB-backed LRU cache for storing and managing
agent skills. Skills are stored persistently and managed in an LRU manner
to prioritize recently used skills in the system prompt.
"""
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from dataclasses import dataclass

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ...db.mongodb_connector import MongoDBConnector
from ...config.config import FILE_DB_NAME
from ...utils.logger import get_logger

logger = get_logger(__name__)

SKILLS_COLLECTION = "agent_skills"
SQL_SCHEMAS_COLLECTION = "sql_agent_schemas"
SQL_QUERIES_COLLECTION = "sql_agent_queries"
CODING_SKILLS_COLLECTION = "coding_agent_skills"


@dataclass
class Skill:
    name: str
    description: str  # Max 160 chars
    content: str
    last_accessed: datetime
    created_at: datetime

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "last_accessed": self.last_accessed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Skill":
        return cls(
            name=data["name"],
            description=data["description"],
            content=data["content"],
            last_accessed=data.get("last_accessed", datetime.utcnow()),
            created_at=data.get("created_at", datetime.utcnow()),
        )


class SkillManager:
    """MongoDB-backed, timestamp-ordered LRU store.

    Keeps only the most recently accessed `max_total_skills` skills in the collection.
    The prompt injection list is separately limited by `max_prompt_skills`.
    """

    def __init__(
        self,
        collection_name: str = SKILLS_COLLECTION,
        max_prompt_skills: int = 20,
        max_total_skills: int = 10,
        db_name: str = FILE_DB_NAME,
    ):
        self.collection_name = collection_name
        self.max_prompt_skills = max_prompt_skills
        self.max_total_skills = max_total_skills
        self.db_name = db_name
        self._connector = None
        self._collection = None
        self._ensure_indexes()

        # Optional: uncomment if you want to enforce the cap on startup too
        # self._evict_excess()

    @property
    def connector(self) -> MongoDBConnector:
        if self._connector is None:
            self._connector = MongoDBConnector()
        return self._connector

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.connector.get_collection(
                self.db_name, self.collection_name
            )
        return self._collection

    @staticmethod
    def _norm_name(name: str) -> str:
        return (name or "").strip()

    def _ensure_indexes(self) -> None:
        try:
            col = self.collection
            col.create_index("name", unique=True)
            col.create_index("last_accessed")
            logger.debug(f"Indexes ensured for {self.collection_name}")
        except Exception as e:
            logger.warning(f"Could not create indexes for {self.collection_name}: {e}")

    def _evict_excess(self) -> None:
        """Evict skills beyond max_total_skills (keep newest by last_accessed)."""
        if self.max_total_skills is None:
            return
        if self.max_total_skills <= 0:
            # Extreme setting: keep nothing
            try:
                self.collection.delete_many({})
            except Exception as e:
                logger.error(f"Error clearing skills: {e}")
            return

        try:
            total = self.collection.count_documents({})
            if total <= self.max_total_skills:
                return

            # Find the skills to evict: everything after the newest max_total_skills
            cursor = (
                self.collection.find(
                    {},
                    {"name": 1},
                )
                .sort("last_accessed", -1)  # newest first
                .skip(self.max_total_skills)
            )

            evict_names = [doc["name"] for doc in cursor if "name" in doc]
            if not evict_names:
                return

            res = self.collection.delete_many({"name": {"$in": evict_names}})
            logger.info(f"Evicted {res.deleted_count} skills (LRU cap={self.max_total_skills})")
        except Exception as e:
            logger.error(f"Error during eviction: {e}")

    def validate_skill(
        self,
        name: str,
        description: str,
        content: str,
        check_uniqueness: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        name = self._norm_name(name)
        if not name:
            return False, "Skill name cannot be empty"
        if len(name) > 100:
            return False, f"Skill name too long ({len(name)} chars). Maximum is 100 characters."
        if not all(c.isalnum() or c in "-_. " for c in name):
            return False, "Skill name can only contain alphanumeric characters, hyphens, underscores, dots, and spaces"

        description = (description or "").strip()
        if not description:
            return False, "Skill description cannot be empty"
        if len(description) > 160:
            return False, f"Description too long ({len(description)} chars). Maximum is 160 characters."

        content = (content or "").strip()
        if not content:
            return False, "Skill content cannot be empty"

        if check_uniqueness:
            existing = self.collection.find_one({"name": name}, {"_id": 1})
            if existing:
                return False, f"A skill with name '{name}' already exists. Skill names must be unique."

        return True, None

    def add_skill(self, name: str, description: str, content: str) -> Tuple[bool, str]:
        is_valid, error = self.validate_skill(name, description, content, check_uniqueness=False)
        if not is_valid:
            return False, error

        name = self._norm_name(name)
        description = description.strip()
        content = content.strip()

        now = datetime.utcnow()
        skill = Skill(
            name=name,
            description=description,
            content=content,
            last_accessed=now,
            created_at=now,
        )

        try:
            self.collection.insert_one(skill.to_dict())
            self._evict_excess()
            logger.info(f"Added skill: {name}")
            return True, f"Successfully added skill '{name}'"
        except DuplicateKeyError:
            return False, f"A skill with name '{name}' already exists. Skill names must be unique."
        except Exception as e:
            logger.error(f"Error adding skill '{name}': {e}")
            return False, f"Failed to add skill: {str(e)}"

    def get_skill(self, name: str) -> Optional[Skill]:
        name = self._norm_name(name)
        if not name:
            return None

        try:
            result = self.collection.find_one_and_update(
                {"name": name},
                {"$set": {"last_accessed": datetime.utcnow()}},
                return_document=ReturnDocument.AFTER,
            )
            return Skill.from_dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting skill '{name}': {e}")
            return None

    def update_skill(
        self,
        name: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Tuple[bool, str]:
        name = self._norm_name(name)
        if not name:
            return False, "Skill name cannot be empty"

        existing = self.collection.find_one({"name": name}, {"_id": 1})
        if not existing:
            return False, f"Skill '{name}' not found"

        update_fields = {"last_accessed": datetime.utcnow()}

        if description is not None:
            description = description.strip()
            if not description:
                return False, "Description cannot be empty"
            if len(description) > 160:
                return False, f"Description too long ({len(description)} chars). Maximum is 160 characters."
            update_fields["description"] = description

        if content is not None:
            content = content.strip()
            if not content:
                return False, "Content cannot be empty"
            update_fields["content"] = content

        try:
            self.collection.update_one({"name": name}, {"$set": update_fields})
            logger.info(f"Updated skill: {name}")
            return True, f"Successfully updated skill '{name}'"
        except Exception as e:
            logger.error(f"Error updating skill '{name}': {e}")
            return False, f"Failed to update skill: {str(e)}"

    def delete_skill(self, name: str) -> Tuple[bool, str]:
        name = self._norm_name(name)
        if not name:
            return False, "Skill name cannot be empty"

        try:
            result = self.collection.delete_one({"name": name})
            if result.deleted_count > 0:
                logger.info(f"Deleted skill: {name}")
                return True, f"Successfully deleted skill '{name}'"
            return False, f"Skill '{name}' not found"
        except Exception as e:
            logger.error(f"Error deleting skill '{name}': {e}")
            return False, f"Failed to delete skill: {str(e)}"

    def list_skills(self, limit: Optional[int] = None) -> List[Skill]:
        if limit is None:
            limit = self.max_prompt_skills

        try:
            cursor = (
                self.collection.find()
                .sort("last_accessed", -1)
                .limit(limit)
            )
            return [Skill.from_dict(doc) for doc in cursor]
        except Exception as e:
            logger.error(f"Error listing skills: {e}")
            return []

    def get_skills_for_prompt(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        return "\n".join(f"- {s.name} - {s.description}" for s in skills)

    def get_skill_content(self, name: str) -> Optional[str]:
        skill = self.get_skill(name)
        return skill.content if skill else None

    def count_skills(self) -> int:
        try:
            return self.collection.count_documents({})
        except Exception as e:
            logger.error(f"Error counting skills: {e}")
            return 0

class SQLSchemaManager(SkillManager):
    """Specialized skill manager for SQL agent schema documentation.
    
    Instead of general skills, this stores database schema information
    in an LLM-optimized format, including table descriptions, column info,
    relationships, and usage examples.
    """
    
    def __init__(
        self,
        max_prompt_schemas: int = 30,
        db_name: str = FILE_DB_NAME,
    ):
        super().__init__(
            collection_name=SQL_SCHEMAS_COLLECTION,
            max_prompt_skills=max_prompt_schemas,
            db_name=db_name,
        )
    
    def add_table_schema(
        self,
        table_name: str,
        description: str,
        schema_content: str,
    ) -> Tuple[bool, str]:
        """Add or update a table schema entry.
        
        Args:
            table_name: Unique table identifier (e.g., 'database.schema.table')
            description: Brief description of what the table stores (max 160 chars)
            schema_content: LLM-optimized schema documentation including:
                - Column names and types
                - Primary/foreign keys
                - Relationships to other tables
                - Common query patterns
                - Example values
                
        Returns:
            Tuple of (success, message)
        """
        return self.add_skill(table_name, description, schema_content)
    
    def get_table_schema(self, table_name: str) -> Optional[Skill]:
        """Get a table schema by name."""
        return self.get_skill(table_name)
    
    def update_table_schema(
        self,
        table_name: str,
        description: Optional[str] = None,
        schema_content: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Update an existing table schema."""
        return self.update_skill(table_name, description, schema_content)
    
    def delete_table_schema(self, table_name: str) -> Tuple[bool, str]:
        """Delete a table schema."""
        return self.delete_skill(table_name)
    
    def get_schemas_for_prompt(self) -> str:
        """Get formatted schemas for SQL agent system prompt.
        
        Returns schemas in LLM-optimized format.
        """
        skills = self.list_skills()
        if not skills:
            return ""
        
        lines = ["### Available Database Tables"]
        for skill in skills:
            lines.append(f"- **{skill.name}**: {skill.description}")
        
        return "\n".join(lines)
    
    def get_detailed_schema(self, table_name: str) -> Optional[str]:
        """Get the full detailed schema documentation for a table."""
        return self.get_skill_content(table_name)
    
    def list_all_schemas(self) -> List[Dict]:
        """List all table schemas with basic info.
        
        Returns:
            List of dicts with table_name and description
        """
        skills = self.list_skills(limit=None)  # Get all
        return [{"table_name": s.name, "description": s.description} for s in skills]
    
    def generate_llm_optimized_schema(
        self,
        table_name: str,
        columns: List[Dict],
        primary_key: Optional[str] = None,
        foreign_keys: Optional[List[Dict]] = None,
        description: Optional[str] = None,
        example_queries: Optional[List[str]] = None,
    ) -> str:
        """Generate LLM-optimized schema documentation.
        
        Args:
            table_name: Name of the table
            columns: List of column dicts with 'name', 'type', 'nullable', 'description'
            primary_key: Primary key column name
            foreign_keys: List of dicts with 'column', 'references_table', 'references_column'
            description: Overall table description
            example_queries: Common SQL query patterns
            
        Returns:
            LLM-optimized schema string
        """
        lines = [f"## Table: {table_name}"]
        
        if description:
            lines.append(f"\n**Purpose**: {description}")
        
        lines.append("\n### Columns")
        for col in columns:
            col_desc = f"- `{col['name']}` ({col['type']})"
            if col.get('nullable') is False:
                col_desc += " NOT NULL"
            if col.get('description'):
                col_desc += f" - {col['description']}"
            lines.append(col_desc)
        
        if primary_key:
            lines.append(f"\n**Primary Key**: `{primary_key}`")
        
        if foreign_keys:
            lines.append("\n### Foreign Keys")
            for fk in foreign_keys:
                lines.append(
                    f"- `{fk['column']}` → `{fk['references_table']}.{fk['references_column']}`"
                )
        
        if example_queries:
            lines.append("\n### Common Query Patterns")
            for i, query in enumerate(example_queries, 1):
                lines.append(f"{i}. `{query}`")
        
        return "\n".join(lines)


class SQLQueryManager(SkillManager):
    """Specialized LRU manager for SQL query patterns/snippets."""

    def __init__(
        self,
        max_prompt_queries: int = 20,
        db_name: str = FILE_DB_NAME,
    ):
        super().__init__(
            collection_name=SQL_QUERIES_COLLECTION,
            max_prompt_skills=max_prompt_queries,
            db_name=db_name,
        )

    def add_saved_query(
        self,
        query_name: str,
        description: str,
        sql_query: str,
    ) -> Tuple[bool, str]:
        return self.add_skill(query_name, description, sql_query)

    def get_saved_query(self, query_name: str) -> Optional[Skill]:
        return self.get_skill(query_name)

    def update_saved_query(
        self,
        query_name: str,
        description: Optional[str] = None,
        sql_query: Optional[str] = None,
    ) -> Tuple[bool, str]:
        return self.update_skill(query_name, description, sql_query)

    def delete_saved_query(self, query_name: str) -> Tuple[bool, str]:
        return self.delete_skill(query_name)

    def list_saved_queries(self, limit: Optional[int] = None) -> List[Skill]:
        return self.list_skills(limit=limit)

    def get_queries_for_prompt(self) -> str:
        queries = self.list_saved_queries()
        if not queries:
            return ""

        lines = ["### Saved SQL Queries"]
        for query in queries:
            lines.append(f"- **{query.name}**: {query.description}")
        return "\n".join(lines)


class CodingSkillManager(SkillManager):
    """Specialized LRU manager for coding-agent reusable skills."""

    def __init__(
        self,
        max_prompt_skills: int = 20,
        max_total_skills: int = 10,
        db_name: str = FILE_DB_NAME,
    ):
        super().__init__(
            collection_name=CODING_SKILLS_COLLECTION,
            max_prompt_skills=max_prompt_skills,
            max_total_skills=max_total_skills,
            db_name=db_name,
        )


_skill_manager: Optional[SkillManager] = None
_schema_manager: Optional[SQLSchemaManager] = None
_query_manager: Optional[SQLQueryManager] = None
_coding_skill_manager: Optional[CodingSkillManager] = None


def get_skill_manager() -> SkillManager:
    """Get or create the singleton skill manager instance."""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager


def get_schema_manager() -> SQLSchemaManager:
    """Get or create the singleton SQL schema manager instance."""
    global _schema_manager
    if _schema_manager is None:
        _schema_manager = SQLSchemaManager()
    return _schema_manager


def get_sql_query_manager() -> SQLQueryManager:
    """Get or create the singleton SQL query manager instance."""
    global _query_manager
    if _query_manager is None:
        _query_manager = SQLQueryManager()
    return _query_manager


def get_coding_skill_manager() -> CodingSkillManager:
    """Get or create the singleton coding skill manager instance."""
    global _coding_skill_manager
    if _coding_skill_manager is None:
        _coding_skill_manager = CodingSkillManager()
    return _coding_skill_manager
