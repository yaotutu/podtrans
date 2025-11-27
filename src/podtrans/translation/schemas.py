"""Translation data models."""

from pydantic import BaseModel, Field


class TranslatedSegment(BaseModel):
    """Single translated segment with timing and speaker information."""

    start: float = Field(ge=0, description="Start time in seconds")
    end: float = Field(ge=0, description="End time in seconds")
    original_text: str = Field(description="Original English text")
    translated_text: str = Field(description="Translated Chinese text")
    speaker: str | None = Field(None, description="Speaker ID (e.g., 'SPEAKER_00')")

    model_config = {
        "json_schema_extra": {
            "example": {
                "start": 0.5,
                "end": 3.2,
                "original_text": "Hello, welcome to the podcast.",
                "translated_text": "Chinese translation here",
                "speaker": "SPEAKER_00",
            }
        }
    }

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end - self.start


class TranslationResult(BaseModel):
    """Complete translation result with all segments."""

    segments: list[TranslatedSegment] = Field(description="List of translated segments")
    source_language: str = Field(
        default="en", description="Source language code (e.g., 'en')"
    )
    target_language: str = Field(
        default="zh", description="Target language code (e.g., 'zh')"
    )
    model_name: str = Field(description="Translation model name used")
    total_duration: float = Field(ge=0, description="Total audio duration in seconds")

    model_config = {
        "json_schema_extra": {
            "example": {
                "segments": [
                    {
                        "start": 0.5,
                        "end": 3.2,
                        "original_text": "Hello, welcome to the podcast.",
                        "translated_text": "Chinese translation here",
                        "speaker": "SPEAKER_00",
                    }
                ],
                "source_language": "en",
                "target_language": "zh",
                "model_name": "qwen-coder-plus",
                "total_duration": 3600.5,
            }
        }
    }

    @property
    def total_segments(self) -> int:
        """Get total number of segments."""
        return len(self.segments)

    @property
    def unique_speakers(self) -> set[str]:
        """Get unique speaker IDs."""
        speakers = {seg.speaker for seg in self.segments if seg.speaker is not None}
        return speakers

    @property
    def speaker_count(self) -> int:
        """Get number of unique speakers."""
        return len(self.unique_speakers)

    def get_segments_by_speaker(self, speaker_id: str) -> list[TranslatedSegment]:
        """Get all segments for a specific speaker."""
        return [seg for seg in self.segments if seg.speaker == speaker_id]

    def to_bilingual_text(self, include_speakers: bool = True) -> str:
        """Convert result to bilingual plain text.

        Args:
            include_speakers: Whether to include speaker labels

        Returns:
            Bilingual plain text (original + translation)
        """
        lines = []
        for seg in self.segments:
            speaker_label = (
                f"[{seg.speaker}] " if include_speakers and seg.speaker else ""
            )
            lines.append(f"{speaker_label}{seg.original_text}")
            lines.append(f"{speaker_label}{seg.translated_text}")
            lines.append("")  # Empty line between segments
        return "\n".join(lines)

    def to_chinese_text(self, include_speakers: bool = True) -> str:
        """Convert result to Chinese-only plain text.

        Args:
            include_speakers: Whether to include speaker labels

        Returns:
            Chinese translation text
        """
        lines = []
        for seg in self.segments:
            if include_speakers and seg.speaker:
                lines.append(f"[{seg.speaker}] {seg.translated_text}")
            else:
                lines.append(seg.translated_text)
        return "\n".join(lines)
