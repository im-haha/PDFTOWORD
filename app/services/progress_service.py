from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.config import settings


@dataclass
class ProgressItem:
    progress: int
    updated_at: float


class ProgressService:
    def __init__(self) -> None:
        self._data: dict[str, ProgressItem] = {}
        self._lock = threading.Lock()

    def set(self, task_id: str, progress: int, force: bool = False) -> None:
        now = time.time()
        with self._lock:
            old = self._data.get(task_id)
            if (
                not force
                and old
                and now - old.updated_at < settings.progress_write_interval_seconds
                and progress < 100
            ):
                return

            self._data[task_id] = ProgressItem(progress=max(0, min(100, progress)), updated_at=now)

    def get(self, task_id: str) -> int | None:
        with self._lock:
            item = self._data.get(task_id)
            return item.progress if item else None

    def delete(self, task_id: str) -> None:
        with self._lock:
            self._data.pop(task_id, None)


progress_service = ProgressService()
