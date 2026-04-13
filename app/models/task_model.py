from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db import Base


class ConversionTask(Base):
    __tablename__ = "conversion_task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)

    source_filename: Mapped[str] = mapped_column(String(255))
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_path: Mapped[str] = mapped_column(String(500))
    result_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    file_size: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[int] = mapped_column(Integer)
    retain_layout: Mapped[bool] = mapped_column(Boolean, default=True)
    detect_tables: Mapped[bool] = mapped_column(Boolean, default=False)
    conversion_mode: Mapped[str] = mapped_column(String(30), default="editable")

    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    latest_progress: Mapped[int] = mapped_column(Integer, default=0)
