from __future__ import annotations

from datetime import datetime
from typing import Optional

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
    createdAt: datetime
    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None
    downloadUrl: Optional[str] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None


class DeletedTaskData(BaseModel):
    taskId: str
