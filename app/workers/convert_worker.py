from __future__ import annotations

import asyncio

from app.config import settings
from app.services.convert_service import convert_service
from app.services.progress_service import progress_service
from app.services.storage_service import build_result_docx_path, remove_temp_dir
from app.services.task_service import (
    get_task,
    mark_failed,
    mark_processing,
    mark_succeeded,
    update_progress_snapshot,
)
from app.utils.logger import get_logger
from app.utils.pdf_precheck import inspect_complexity


logger = get_logger(__name__)


class ConvertWorker:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._runner: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        self._stopped.clear()
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._run(), name="convert-worker")
            logger.info("convert worker started")

    async def stop(self) -> None:
        self._stopped.set()
        if self._runner:
            self._runner.cancel()
            try:
                await self._runner
            except asyncio.CancelledError:
                pass
            logger.info("convert worker stopped")

    async def enqueue(self, task_id: str) -> None:
        await self._queue.put(task_id)

    async def _run(self) -> None:
        while not self._stopped.is_set():
            task_id = await self._queue.get()
            try:
                await self._handle_task(task_id)
            except Exception:
                logger.exception("worker failed while handling task=%s", task_id)
            finally:
                self._queue.task_done()

    async def _handle_task(self, task_id: str) -> None:
        task = get_task(task_id)
        if not task:
            return

        mark_processing(task_id)
        progress_service.set(task_id, 1, force=True)
        update_progress_snapshot(task_id, 1)

        complexity = inspect_complexity(task.source_path)
        if complexity.too_complex:
            mark_failed(task_id, "PAGE_COMPLEXITY_EXCEEDED", complexity.reason, phase="precheck")
            progress_service.delete(task_id)
            return

        result_path = build_result_docx_path(task_id)

        def update_progress(progress: int) -> None:
            progress_service.set(task_id, progress)
            update_progress_snapshot(task_id, progress)

        temp_dir = None
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    convert_service.run,
                    task_id,
                    task.source_path,
                    result_path,
                    update_progress,
                    task.conversion_mode,
                    task.detect_tables,
                    task.retain_layout,
                ),
                timeout=settings.worker_max_seconds,
            )
            temp_dir = result.temp_dir
            mark_succeeded(task_id, result_path, result.report)
        except TimeoutError:
            mark_failed(task_id, "TASK_TIMEOUT", "task execution timeout", phase="convert")
        except Exception as exc:
            logger.exception("task convert failed task=%s", task_id)
            mark_failed(task_id, "DOCX_GENERATION_FAILED", str(exc), phase="docx_write")
        finally:
            remove_temp_dir(temp_dir)
            progress_service.delete(task_id)


convert_worker = ConvertWorker()
