from typing import List, Literal
from pydantic import BaseModel, Field

# remote types currently supported by the document collector and its api
# currently only google drive is supported even though rclone supports many more remote types
REMOTE_TYPES = ["drive", "local"]


class RcloneRemoteCreateRequest(BaseModel):
    """Request model for creating a new rclone remote"""

    name: str
    type: Literal[*REMOTE_TYPES]
    config_token: str = Field(
        ...,
        description="Configuration token for headless authentication",
    )


class RcloneListRemoteContentsRequest(BaseModel):
    """Request model for listing the contents of a specific rclone remote"""

    remote_name: str
    path: str
    max_depth: int | None = None
    dirs_only: bool = False
    files_only: bool = False


class RcloneSyncPathsRequest(BaseModel):
    """Request model for syncing paths between two locations using rclone"""

    remote_name: str
    source_path: str
    schedule_periodical_sync: bool = False


class MultipleRcloneSyncPathsRequest(BaseModel):
    """Request model for syncing multiple paths between two locations using rclone"""

    requests: List[RcloneSyncPathsRequest]
