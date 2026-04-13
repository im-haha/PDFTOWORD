from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.config import settings
from app.utils.hash_util import sha256_bytes


def _dated_dir(base_dir: Path) -> Path:
    now = datetime.now()
    target = base_dir / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_source_pdf(task_id: str, file_bytes: bytes, original_name: str) -> str:
    source_root = settings.storage_root / settings.source_dir
    target_dir = _dated_dir(source_root)
    digest = sha256_bytes(file_bytes)[:12]
    safe_name = f"{task_id}_{digest}.pdf"
    output = target_dir / safe_name
    output.write_bytes(file_bytes)
    return str(output)


def build_result_docx_path(task_id: str) -> str:
    result_root = settings.storage_root / settings.result_dir
    target_dir = _dated_dir(result_root)
    output = target_dir / f"{task_id}.docx"
    return str(output)


def build_temp_image_dir(task_id: str) -> Path:
    tmp_root = settings.storage_root / settings.tmp_dir
    image_dir = tmp_root / task_id
    image_dir.mkdir(parents=True, exist_ok=True)
    return image_dir


def remove_file_if_exists(path: str | None) -> None:
    if not path:
        return
    p = Path(path)
    if p.exists():
        p.unlink()


def remove_task_files(source_path: str | None, result_path: str | None, temp_dir: str | None = None) -> None:
    remove_file_if_exists(source_path)
    remove_file_if_exists(result_path)

    if temp_dir:
        td = Path(temp_dir)
        remove_temp_dir(str(td))


def remove_temp_dir(temp_dir: str | None) -> None:
    if not temp_dir:
        return

    td = Path(temp_dir)
    if td.exists() and td.is_dir():
        for child in td.glob("*"):
            if child.is_file():
                child.unlink()
        td.rmdir()
