from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskAcceptedData(BaseModel):
    taskId: str
    status: str
    createdAt: datetime


class TaskStatusData(BaseModel):
    taskId: str
    status: str
    progress: int = Field(ge=0, le=100)
    sourceFilename: str
    conversionMode: str
    retainLayout: bool
    detectTables: bool
    createdAt: datetime
    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None
    downloadUrl: Optional[str] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    report: Optional[dict[str, Any]] = None
    layoutWarnings: list[str] = Field(default_factory=list)
    fontSubstitutions: dict[str, Any] = Field(default_factory=dict)
    fallbackSummary: dict[str, int] = Field(default_factory=dict)
    qualityGrade: Optional[str] = None


class DeletedTaskData(BaseModel):
    taskId: str
