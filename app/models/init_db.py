from __future__ import annotations

from app.models.db import Base, engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
