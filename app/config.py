from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "pdf-to-word-api")
    app_env: str = os.getenv("APP_ENV", "dev")
    api_prefix: str = "/api/v1"

    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    max_page_count: int = int(os.getenv("MAX_PAGE_COUNT", "300"))
    precheck_pages: int = int(os.getenv("PRECHECK_PAGES", "3"))

    storage_root: Path = Path(os.getenv("STORAGE_ROOT", str(ROOT_DIR / "storage")))
    source_dir: str = "source"
    result_dir: str = "result"
    tmp_dir: str = "tmp"

    db_url: str = os.getenv("DB_URL", f"sqlite:///{ROOT_DIR / 'storage' / 'tasks.db'}")

    worker_max_seconds: int = int(os.getenv("WORKER_MAX_SECONDS", "600"))
    worker_complexity_limit: int = int(os.getenv("WORKER_COMPLEXITY_LIMIT", "120000"))
    visual_exact_dpi: int = int(os.getenv("VISUAL_EXACT_DPI", "220"))

    progress_write_interval_seconds: float = float(os.getenv("PROGRESS_WRITE_INTERVAL_SECONDS", "0.4"))


settings = Settings()


def ensure_storage_dirs() -> None:
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    (settings.storage_root / settings.source_dir).mkdir(parents=True, exist_ok=True)
    (settings.storage_root / settings.result_dir).mkdir(parents=True, exist_ok=True)
    (settings.storage_root / settings.tmp_dir).mkdir(parents=True, exist_ok=True)
