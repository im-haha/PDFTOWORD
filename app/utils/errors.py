from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppError(Exception):
    code: int
    message: str
    http_status: int = 400


ERROR_CODES = {
    "INVALID_FILE_TYPE": 4001001,
    "FILE_TOO_LARGE": 4001002,
    "PDF_CORRUPTED": 4001003,
    "NON_TEXT_PDF": 4001004,
    "PAGE_COUNT_EXCEEDED": 4001005,
    "TASK_NOT_FOUND": 4041001,
    "RESULT_NOT_READY": 4091001,
    "RESULT_EXPIRED": 4101001,
    "PDF_PARSE_FAILED": 5001001,
    "LAYOUT_REBUILD_FAILED": 5001002,
    "DOCX_GENERATION_FAILED": 5001003,
    "STORAGE_FAILED": 5001004,
    "TASK_TIMEOUT": 5001005,
    "TASK_MEMORY_EXCEEDED": 5001006,
    "PAGE_COMPLEXITY_EXCEEDED": 5001007,
}


def build_error(key: str, message: str, http_status: int = 400) -> AppError:
    return AppError(code=ERROR_CODES[key], message=message, http_status=http_status)
