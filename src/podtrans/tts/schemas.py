"""TTS data models and schemas."""

from pathlib import Path

from pydantic import BaseModel, Field


class SpeakerConfig(BaseModel):
    """Speaker voice configuration for TTS."""

    speaker_id: str = Field(description="Original speaker ID (e.g., 'SPEAKER_00')")
    voice_sample: Path | None = Field(
        None, description="Path to voice sample audio (3-10 seconds)"
    )
    voice_description: str | None = Field(None, description="Voice description")


class TTSResult(BaseModel):
    """TTS synthesis result metadata."""

    audio_path: Path = Field(description="Generated audio file path")
    format: str = Field(default="wav", description="Audio format")
    duration: float | None = Field(None, ge=0, description="Audio duration in seconds")
    sample_rate: int = Field(default=24000, description="Audio sample rate in Hz")
    service: str = Field(description="TTS service name (e.g., 'soulx')")
    model_name: str | None = Field(None, description="TTS model name")
    segments_count: int = Field(ge=0, description="Number of synthesized segments")
