from __future__ import annotations

from fastapi import APIRouter

from app.config import settings


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "service": settings.app_name,
            "status": "up",
        },
    }
