from __future__ import annotations

from sqlalchemy import inspect, text

from app.models.db import Base, engine


def _ensure_task_columns() -> None:
    required_columns: dict[str, str] = {
        "report_json": "TEXT",
        "report_summary": "VARCHAR(255)",
        "layout_warning_count": "INTEGER DEFAULT 0",
        "fallback_block_count": "INTEGER DEFAULT 0",
        "font_substitution_count": "INTEGER DEFAULT 0",
    }

    inspector = inspect(engine)
    if "conversion_task" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("conversion_task")}
    missing = {name: ddl for name, ddl in required_columns.items() if name not in existing}
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE conversion_task ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_task_columns()
