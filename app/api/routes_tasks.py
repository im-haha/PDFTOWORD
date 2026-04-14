from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas.task import DeletedTaskData, TaskAcceptedData, TaskStatusData
from app.services.storage_service import remove_task_files, save_source_pdf
from app.services.task_service import compute_progress, create_task, delete_task, get_task
from app.utils.errors import build_error
from app.utils.file_guard import (
    validate_content_type,
    validate_file_size,
    validate_filename,
    validate_pdf_header,
)
from app.utils.pdf_precheck import precheck_text_pdf
from app.workers.convert_worker import convert_worker


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _normalize_output_name(output_name: str | None) -> str | None:
    if not output_name:
        return None
    name = output_name.strip()
    if not name:
        return None
    if not name.lower().endswith(".docx"):
        name += ".docx"
    if "/" in name or "\\" in name:
        raise build_error("INVALID_FILE_TYPE", "invalid output name", 400)
    return name


def _normalize_conversion_mode(conversion_mode: str | None) -> str:
    if conversion_mode:
        mode = conversion_mode.strip().lower()
        if mode in {"visual_exact", "editable", "resume"}:
            return mode
        raise build_error("INVALID_FILE_TYPE", "invalid conversion mode", 400)
    return "resume"


@router.post("", status_code=202)
async def create_conversion_task(
    request: Request,
    file: UploadFile = File(...),
    retainLayout: bool = Form(True),
    detectTables: bool = Form(False),
    outputName: str | None = Form(None),
    conversionMode: str | None = Form(None),
) -> JSONResponse:
    validate_filename(file.filename or "")
    validate_content_type(file.content_type)

    file_bytes = await file.read()
    validate_file_size(len(file_bytes))
    validate_pdf_header(file_bytes)

    task_id = str(uuid4())
    trace_id = request.headers.get("x-trace-id", str(uuid4()))
    normalized_output_name = _normalize_output_name(outputName)
    normalized_mode = _normalize_conversion_mode(conversionMode)

    source_path = save_source_pdf(task_id=task_id, file_bytes=file_bytes, original_name=file.filename or "input.pdf")

    try:
        precheck = precheck_text_pdf(source_path, sample_pages=settings.precheck_pages)
    except Exception as exc:  # pragma: no cover
        remove_task_files(source_path, None)
        raise build_error("PDF_CORRUPTED", f"pdf open failed: {exc}", 400)

    if precheck.page_count > settings.max_page_count:
        remove_task_files(source_path, None)
        raise build_error("PAGE_COUNT_EXCEEDED", "page count exceeded", 400)

    if not precheck.is_text_pdf:
        remove_task_files(source_path, None)
        raise build_error("NON_TEXT_PDF", "non-text pdf detected", 400)

    task = create_task(
        task_id=task_id,
        source_filename=file.filename or "input.pdf",
        output_filename=normalized_output_name,
        source_path=source_path,
        file_size=len(file_bytes),
        page_count=precheck.page_count,
        trace_id=trace_id,
        retain_layout=retainLayout,
        detect_tables=detectTables,
        conversion_mode=normalized_mode,
    )

    await convert_worker.enqueue(task.id)

    payload = TaskAcceptedData(taskId=task.id, status=task.status, createdAt=task.created_at)
    return JSONResponse(status_code=202, content={"code": 0, "message": "accepted", "data": payload.model_dump(mode="json")})


@router.get("/{task_id}")
def get_task_status(task_id: str) -> dict:
    task = get_task(task_id)
    if not task:
        raise build_error("TASK_NOT_FOUND", "task not found", 404)

    progress = compute_progress(task)
    download_url = None
    if task.status == "succeeded":
        download_url = f"{settings.api_prefix}/tasks/{task.id}/result"

    report_payload = None
    if task.report_json:
        try:
            report_payload = json.loads(task.report_json)
        except json.JSONDecodeError:
            report_payload = None

    layout_warnings = []
    font_substitutions = {}
    fallback_summary = {
        "fallbackBlockCount": task.fallback_block_count or 0,
        "degradedTableCount": 0,
    }
    quality_grade = None
    if report_payload:
        layout_warnings = list(report_payload.get("warnings", []))
        font_substitutions = dict(report_payload.get("fontSubstitutions", {}))
        fallback_summary["fallbackBlockCount"] = int(report_payload.get("fallbackBlockCount", fallback_summary["fallbackBlockCount"]))
        fallback_summary["degradedTableCount"] = int(report_payload.get("degradedTables", 0))
        quality_grade = report_payload.get("qualityGrade")

    data = TaskStatusData(
        taskId=task.id,
        status=task.status,
        progress=progress,
        sourceFilename=task.source_filename,
        conversionMode=task.conversion_mode,
        retainLayout=task.retain_layout,
        detectTables=task.detect_tables,
        createdAt=task.created_at,
        startedAt=task.started_at,
        finishedAt=task.finished_at,
        downloadUrl=download_url,
        errorCode=task.error_code,
        errorMessage=task.error_message,
        report=report_payload,
        layoutWarnings=layout_warnings,
        fontSubstitutions=font_substitutions,
        fallbackSummary=fallback_summary,
        qualityGrade=quality_grade,
    )
    return {"code": 0, "message": "ok", "data": data.model_dump(mode="json")}


@router.delete("/{task_id}")
def delete_conversion_task(task_id: str) -> dict:
    task = delete_task(task_id)
    if not task:
        raise build_error("TASK_NOT_FOUND", "task not found", 404)

    remove_task_files(task.source_path, task.result_path)
    data = DeletedTaskData(taskId=task.id)
    return {"code": 0, "message": "deleted", "data": data.model_dump(mode="json")}
