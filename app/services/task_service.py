from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from typing import Any

from sqlalchemy import select

from app.models.db import get_db_session
from app.models.task_model import ConversionTask
from app.services.progress_service import progress_service


TASK_EXPIRE_HOURS = 24


@dataclass
class TaskSnapshot:
    id: str
    source_path: str
    result_path: str | None


def create_task(
    *,
    task_id: str,
    source_filename: str,
    output_filename: str | None,
    source_path: str,
    file_size: int,
    page_count: int,
    trace_id: str,
    retain_layout: bool,
    detect_tables: bool,
    conversion_mode: str,
) -> ConversionTask:
    now = datetime.now()
    task = ConversionTask(
        id=task_id,
        status="queued",
        source_filename=source_filename,
        output_filename=output_filename,
        source_path=source_path,
        result_path=None,
        file_size=file_size,
        page_count=page_count,
        retain_layout=retain_layout,
        detect_tables=detect_tables,
        conversion_mode=conversion_mode,
        error_code=None,
        error_message=None,
        created_at=now,
        started_at=None,
        finished_at=None,
        expires_at=now + timedelta(hours=TASK_EXPIRE_HOURS),
        trace_id=trace_id,
        latest_progress=0,
        report_json=None,
        report_summary=None,
        layout_warning_count=0,
        fallback_block_count=0,
        font_substitution_count=0,
    )
    with get_db_session() as db:
        db.add(task)
    return task


def get_task(task_id: str) -> ConversionTask | None:
    with get_db_session() as db:
        stmt = select(ConversionTask).where(ConversionTask.id == task_id)
        return db.execute(stmt).scalar_one_or_none()


def mark_processing(task_id: str) -> None:
    with get_db_session() as db:
        task = db.get(ConversionTask, task_id)
        if not task:
            return
        task.status = "processing"
        task.started_at = datetime.now()
        task.error_code = None
        task.error_message = None
        task.latest_progress = 1


def mark_succeeded(task_id: str, result_path: str, report: Any | None = None) -> None:
    with get_db_session() as db:
        task = db.get(ConversionTask, task_id)
        if not task:
            return
        task.status = "succeeded"
        task.result_path = result_path
        task.finished_at = datetime.now()
        task.latest_progress = 100
        if report is not None:
            report_payload = report.to_dict() if hasattr(report, "to_dict") else report
            task.report_json = json.dumps(report_payload, ensure_ascii=False)
            quality = report_payload.get("qualityGrade", "-")
            warn = int(report_payload.get("layoutWarningCount", 0))
            fallback = int(report_payload.get("fallbackBlockCount", 0))
            task.report_summary = f"grade={quality}, warnings={warn}, fallback={fallback}"
            task.layout_warning_count = warn
            task.fallback_block_count = fallback
            task.font_substitution_count = int(report_payload.get("fontSubstitutionCount", 0))


def mark_failed(task_id: str, error_code: str, error_message: str, phase: str | None = None) -> None:
    with get_db_session() as db:
        task = db.get(ConversionTask, task_id)
        if not task:
            return
        task.status = "failed"
        task.error_code = error_code
        task.error_message = f"[{phase}] {error_message}" if phase else error_message
        task.finished_at = datetime.now()
        task.latest_progress = max(task.latest_progress, 1)


def update_progress_snapshot(task_id: str, progress: int) -> None:
    with get_db_session() as db:
        task = db.get(ConversionTask, task_id)
        if not task:
            return
        task.latest_progress = max(0, min(100, progress))


def delete_task(task_id: str) -> TaskSnapshot | None:
    with get_db_session() as db:
        task = db.get(ConversionTask, task_id)
        if not task:
            return None
        data = TaskSnapshot(
            id=task.id,
            source_path=task.source_path,
            result_path=task.result_path,
        )
        db.delete(task)
        progress_service.delete(task_id)
        return data


def compute_progress(task: ConversionTask) -> int:
    cached = progress_service.get(task.id)
    if cached is not None:
        return cached
    if task.status == "succeeded":
        return 100
    if task.status == "queued":
        return 0
    if task.status == "failed":
        return task.latest_progress
    return max(1, task.latest_progress)
