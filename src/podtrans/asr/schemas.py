"""ASR (Automatic Speech Recognition) data models."""

from pydantic import BaseModel, Field


class Word(BaseModel):
    """Word-level timestamp and speaker information."""

    word: str = Field(description="The word text")
    start: float = Field(ge=0, description="Start time in seconds")
    end: float = Field(ge=0, description="End time in seconds")
    score: float | None = Field(None, ge=0, le=1, description="Confidence score")
    speaker: str | None = Field(None, description="Speaker ID (e.g., 'SPEAKER_00')")

    model_config = {
        "json_schema_extra": {
            "example": {
                "word": "Hello",
                "start": 0.5,
                "end": 0.8,
                "score": 0.95,
                "speaker": "SPEAKER_00",
            }
        }
    }


class Segment(BaseModel):
    """Sentence-level segment with speaker information."""

    start: float = Field(ge=0, description="Start time in seconds")
    end: float = Field(ge=0, description="End time in seconds")
    text: str = Field(description="Transcribed text")
    speaker: str | None = Field(None, description="Speaker ID (e.g., 'SPEAKER_00')")
    words: list[Word] = Field(default_factory=list, description="Word-level timestamps")

    model_config = {
        "json_schema_extra": {
            "example": {
                "start": 0.5,
                "end": 3.2,
                "text": "Hello, welcome to the podcast.",
                "speaker": "SPEAKER_00",
                "words": [
                    {
                        "word": "Hello",
                        "start": 0.5,
                        "end": 0.8,
                        "speaker": "SPEAKER_00",
                    }
                ],
            }
        }
    }

    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end - self.start

    @property
    def word_count(self) -> int:
        """Get number of words in segment."""
        return len(self.text.split())


class ASRResult(BaseModel):
    """Complete ASR result with all segments."""

    segments: list[Segment] = Field(description="List of transcribed segments")
    language: str = Field(description="Detected language code (e.g., 'en', 'zh')")
    audio_duration: float = Field(ge=0, description="Total audio duration in seconds")
    model_name: str = Field(description="ASR model name used (e.g., 'large-v2')")

    model_config = {
        "json_schema_extra": {
            "example": {
                "segments": [
                    {
                        "start": 0.5,
                        "end": 3.2,
                        "text": "Hello, welcome to the podcast.",
                        "speaker": "SPEAKER_00",
                        "words": [],
                    }
                ],
                "language": "en",
                "audio_duration": 3600.5,
                "model_name": "large-v2",
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

    def get_segments_by_speaker(self, speaker_id: str) -> list[Segment]:
        """Get all segments for a specific speaker."""
        return [seg for seg in self.segments if seg.speaker == speaker_id]

    def to_text(self, include_speakers: bool = True) -> str:
        """Convert result to plain text.

        Args:
            include_speakers: Whether to include speaker labels

        Returns:
            Plain text transcription
        """
        lines = []
        for seg in self.segments:
            if include_speakers and seg.speaker:
                lines.append(f"[{seg.speaker}] {seg.text}")
            else:
                lines.append(seg.text)
        return "\n".join(lines)
