import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import Settings, get_settings
from app.dependencies import DatabaseSession

router = APIRouter(prefix="/health", tags=["health"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


class LivenessResponse(BaseModel):
    status: Literal["UP"] = "UP"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["UP", "DOWN"]
    database: Literal["UP", "DOWN"]
    artifact_storage: Literal["UP", "DOWN"] = Field(alias="artifactStorage")
    workspace: Literal["UP", "DOWN"]
    git: Literal["UP", "DOWN"]
    workflow_engine: Literal["UP", "DOWN"] = Field(alias="workflowEngine")


def _directory_ready(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path.is_dir() and os.access(path, os.W_OK)
    except OSError:
        return False


def _workflow_engine_ready(database_url: str) -> bool:
    if not database_url:
        return False
    try:
        url = make_url(database_url)
        if not url.drivername.startswith("sqlite") or not url.database:
            return False
        database_path = Path(url.database).expanduser()
        parent = database_path.parent.resolve()
        return parent.is_dir() and os.access(parent, os.W_OK)
    except (TypeError, ValueError, OSError):
        return False


def _git_ready(timeout: int) -> bool:
    executable = shutil.which("git")
    if executable is None:
        return False
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@router.get("/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    response_model_by_alias=True,
    responses={503: {"model": ReadinessResponse}},
)
def readiness(
    response: Response,
    db: DatabaseSession,
    settings: SettingsDependency,
) -> ReadinessResponse:
    checks: dict[str, bool] = {}
    try:
        db.execute(text("SELECT 1")).scalar_one()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    checks["artifact_storage"] = _directory_ready(settings.ARTIFACT_ROOT)
    checks["workspace"] = _directory_ready(settings.WORKSPACE_ROOT)
    checks["git"] = _git_ready(settings.MAX_COMMAND_SECONDS)
    checks["workflow_engine"] = _workflow_engine_ready(settings.LANGGRAPH_DATABASE_URL)

    is_ready = all(checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="UP" if is_ready else "DOWN",
        database="UP" if checks["database"] else "DOWN",
        artifactStorage="UP" if checks["artifact_storage"] else "DOWN",
        workspace="UP" if checks["workspace"] else "DOWN",
        git="UP" if checks["git"] else "DOWN",
        workflowEngine="UP" if checks["workflow_engine"] else "DOWN",
    )


