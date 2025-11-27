"""Common data models and schemas."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_serializer


class StageStatus(str, Enum):
    """Status of a pipeline stage."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class StageMetadata(BaseModel):
    """Metadata for a single pipeline stage."""

    name: str = Field(description="Stage name (e.g., 'asr', 'translation', 'tts')")
    status: StageStatus = Field(default=StageStatus.PENDING)
    start_time: datetime | None = Field(default=None)
    end_time: datetime | None = Field(default=None)
    duration_seconds: float | None = Field(default=None, ge=0)
    error_message: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage-specific metadata (e.g., model name, tokens used)",
    )

    def mark_running(self) -> None:
        """Mark stage as running."""
        self.status = StageStatus.RUNNING
        self.start_time = datetime.now()

    def mark_success(self, **extra_metadata: Any) -> None:
        """Mark stage as successful."""
        self.status = StageStatus.SUCCESS
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        if extra_metadata:
            self.metadata.update(extra_metadata)

    def mark_failed(self, error: str) -> None:
        """Mark stage as failed."""
        self.status = StageStatus.FAILED
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.error_message = error


class PipelineMetadata(BaseModel):
    """Metadata for the entire pipeline."""

    audio_file: str = Field(description="Input audio file name")
    output_dir: Path = Field(description="Output directory")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    stages: list[StageMetadata] = Field(default_factory=list)
    total_duration_seconds: float | None = Field(default=None, ge=0)
    final_status: StageStatus = Field(default=StageStatus.PENDING)

    def get_stage(self, stage_name: str) -> StageMetadata | None:
        """Get stage by name."""
        for stage in self.stages:
            if stage.name == stage_name:
                return stage
        return None

    def update_stage(
        self,
        stage_name: str,
        status: StageStatus,
        error: str | None = None,
        **metadata: Any,
    ) -> None:
        """Update stage status."""
        stage = self.get_stage(stage_name)
        if stage is None:
            # Create new stage if it doesn't exist
            stage = StageMetadata(name=stage_name)
            self.stages.append(stage)

        if status == StageStatus.RUNNING:
            stage.mark_running()
        elif status == StageStatus.SUCCESS:
            stage.mark_success(**metadata)
        elif status == StageStatus.FAILED and error:
            stage.mark_failed(error)

        self.updated_at = datetime.now()
        self._update_final_status()

    def _update_final_status(self) -> None:
        """Update final status based on all stages."""
        if not self.stages:
            self.final_status = StageStatus.PENDING
            return

        # If any stage failed, mark as failed
        if any(s.status == StageStatus.FAILED for s in self.stages):
            self.final_status = StageStatus.FAILED
            return

        # If any stage running, mark as running
        if any(s.status == StageStatus.RUNNING for s in self.stages):
            self.final_status = StageStatus.RUNNING
            return

        # If all stages successful, mark as success
        if all(s.status == StageStatus.SUCCESS for s in self.stages):
            self.final_status = StageStatus.SUCCESS
            # Calculate total duration
            self.total_duration_seconds = sum(
                s.duration_seconds for s in self.stages if s.duration_seconds
            )
            return

        # Otherwise, still pending
        self.final_status = StageStatus.PENDING

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Custom serializer to handle Path objects."""
        return {
            "audio_file": self.audio_file,
            "output_dir": str(self.output_dir),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stages": [stage.model_dump() for stage in self.stages],
            "total_duration_seconds": self.total_duration_seconds,
            "final_status": self.final_status.value,
        }
