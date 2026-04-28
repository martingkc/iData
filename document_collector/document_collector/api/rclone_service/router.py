from logging import getLogger
from typing import Annotated
from fastapi import APIRouter, Body, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from .schemas import (
    RcloneRemoteCreateRequest,
    RcloneListRemoteContentsRequest,
    RcloneSyncPathsRequest,
    MultipleRcloneSyncPathsRequest,
)
from .methods import (
    create_rclone_remote,
    check_rclone_remote,
    list_rclone_remotes,
    list_rclone_remote_contents,
    rclone_sync_to_nas,
    RcloneSyncLogger,
    run_rclone_authorize_command,
    configure_rclone_headless_remote,
    rclone_configure_headless_routine,
)

logger = getLogger(__name__)
router = APIRouter()

## CRUD operations for rclone remotes


@router.post("/create_remote")
async def create_remote(request: RcloneRemoteCreateRequest):
    # Implementation for creating a new rclone remote
    create_rclone_remote(request.name, request.type)
    return {
        "message": f"Rclone remote '{request.name}' of type '{request.type}' created successfully."
    }


@router.get("/check_remote")
async def check_remote(name: str):
    # Implementation for checking an rclone remote
    is_configured = check_rclone_remote(name)
    return {
        "name": name,
        "is_configured": is_configured,
    }


## Operations for remotes
@router.get("/list_remotes")
async def list_remotes() -> list[str]:
    # Implementation for listing all rclone remotes
    return list_rclone_remotes()


@router.post("/list_remote_contents")
async def list_remote_contents(
    request: Annotated[RcloneListRemoteContentsRequest, Body()],
):
    # Implementation for listing the contents of a specific rclone remote
    return list_rclone_remote_contents(
        request.remote_name,
        request.path,
        request.max_depth,
        request.dirs_only,
        request.files_only,
    )


# Sync operations
@router.post("/sync_paths")
async def sync_paths(
    request: Annotated[MultipleRcloneSyncPathsRequest, Body()],
    background_tasks: BackgroundTasks,
):
    """Sync files from source to destination.
    TODO in production this shouldn't be available, the destionation should always be the server side storage.
    """
    # Implementation for syncing files from source to destination
    # Use background tasks to avoid blocking the request
    # rclone_sync_logger = RcloneSyncLogger(
    #     _logger=logger,
    #     remote_name=request.remote_name,
    #     source_path=request.source_path,
    # )
    for sync_request in request.requests:
        background_tasks.add_task(
            rclone_sync_to_nas,
            remote_name=sync_request.remote_name,
            source_path=sync_request.source_path,
            listener=print,
            schedule_periodical_sync=sync_request.schedule_periodical_sync,
        )
    return {"message": "Sync operation request sent."}


@router.post("/authorize_rclone_remote")
async def authorize_rclone_remote(remote_type: str) -> JSONResponse:
    # Implementation for authorizing an rclone remote
    result = run_rclone_authorize_command(remote_type)
    if result:
        return JSONResponse(content={"token": result})
    return JSONResponse(status_code=404, content={"message": "Authorization failed"})


@router.post("/configure_headless_remote")
async def configure_headless_remote(
    config: Annotated[RcloneRemoteCreateRequest, Body()],
):
    # Implementation for configuring a headless rclone remote
    rclone_configure_headless_routine(
        config_token=config.config_token, name=config.name, remote_type=config.type
    )
    return


@router.get("/debug-ip")
async def debug_ip(request: Request):
    return {
        "client": request.client.host if request.client else None,
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "x_real_ip": request.headers.get("x-real-ip"),
        "headers": request.headers,
    }
