from __future__ import annotations

from app.config import settings
from app.utils.errors import build_error


PDF_MAGIC = b"%PDF"


def validate_filename(filename: str) -> None:
    normalized = filename.lower()
    if not normalized.endswith(".pdf") or normalized.endswith(".pdf.exe"):
        raise build_error("INVALID_FILE_TYPE", "invalid file type", 400)


def validate_content_type(content_type: str | None) -> None:
    if content_type and content_type != "application/pdf":
        raise build_error("INVALID_FILE_TYPE", "invalid file type", 400)


def validate_file_size(file_size: int) -> None:
    if file_size > settings.max_file_size_mb * 1024 * 1024:
        raise build_error("FILE_TOO_LARGE", "file size exceeded", 400)


def validate_pdf_header(file_bytes: bytes) -> None:
    if not file_bytes.startswith(PDF_MAGIC):
        raise build_error("PDF_CORRUPTED", "pdf header invalid", 400)
