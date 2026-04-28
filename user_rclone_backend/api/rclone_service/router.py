from logging import getLogger
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .methods import run_rclone_authorize_command

logger = getLogger(__name__)
router = APIRouter()


@router.post("/authorize_rclone_remote")
async def authorize_rclone_remote(remote_type: str) -> JSONResponse:
    # Implementation for authorizing an rclone remote
    result = run_rclone_authorize_command(remote_type)
    if result:
        return JSONResponse(content={"token": result})
    return JSONResponse(status_code=404, content={"message": "Authorization failed"})
