from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    created = "created"
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ReconstructionOptions(BaseModel):
    method: str = "vggt-colmap"
    max_num_iterations: int = Field(default=30000, ge=100, le=300000)
    gpu_ids: str | None = Field(default=None, description="Example: 0 or 0,1")
    matching_method: str = Field(default="exhaustive")
    high_quality: bool = Field(default=True)


class ProjectMetadata(BaseModel):
    id: str
    name: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: ProjectStatus = ProjectStatus.created
    image_count: int = 0
    options: ReconstructionOptions = Field(default_factory=ReconstructionOptions)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    semantic_objects: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    status: ProjectStatus
    image_count: int
    artifacts: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
