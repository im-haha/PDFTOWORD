from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None
