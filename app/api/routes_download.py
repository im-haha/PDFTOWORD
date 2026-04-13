from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.services.task_service import get_task
from app.utils.errors import build_error


router = APIRouter(prefix="/tasks", tags=["download"])


@router.get("/{task_id}/result")
def download_result(task_id: str) -> FileResponse:
    task = get_task(task_id)
    if not task:
        raise build_error("TASK_NOT_FOUND", "task not found", 404)

    if task.status != "succeeded":
        raise build_error("RESULT_NOT_READY", "task not completed", 409)

    if task.expires_at and datetime.now() > task.expires_at:
        raise build_error("RESULT_EXPIRED", "result expired", 410)

    if not task.result_path:
        raise build_error("RESULT_EXPIRED", "result missing", 410)

    file_path = Path(task.result_path)
    if not file_path.exists():
        raise build_error("RESULT_EXPIRED", "result file missing", 410)

    download_name = task.output_filename or (Path(task.source_filename).stem + ".docx")
    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
    )
