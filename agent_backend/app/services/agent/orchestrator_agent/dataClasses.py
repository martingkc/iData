from dataclasses import dataclass, field
from typing import List, Optional
from typing_extensions import TypedDict


@dataclass
class Context:
    user_id: str
    # Optional list of document paths to filter searches (e.g., ["folder/file.pdf", "other/doc.docx"])
    path_filters: Optional[List[str]] = field(default_factory=list)

# TypedDict defines the structure of user information for the LLM
class UserInfo(TypedDict):
    """User information to be stored persistently.
    
    Attributes:
        name: The user's name
        preferences: What the user likes, interests, or preferences
        goals: What the user wants to accomplish
        other_info: Any other relevant information about the user
    """
    name: str
    preferences: str
    goals: str
    other_info: str
