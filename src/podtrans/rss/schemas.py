"""RSS data models for podcast feed and episode information.

This module defines Pydantic models for RSS feeds and podcast episodes,
providing type safety and data validation for the RSS processing pipeline.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List

from pydantic import BaseModel, Field, validator


class PodcastEpisode(BaseModel):
    """Represents a single podcast episode from an RSS feed.

    This model contains essential information about a podcast episode
    including metadata required for downloading and processing.
    """

    title: str = Field(description="Episode title")
    description: Optional[str] = Field(None, description="Episode description or summary")
    audio_url: str = Field(description="Direct URL to the audio file")
    pub_date: datetime = Field(description="Publication date of the episode")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    size: Optional[int] = Field(None, description="File size in bytes")
    guid: str = Field(description="Unique identifier for the episode")
    author: Optional[str] = Field(None, description="Episode author or host")
    image_url: Optional[str] = Field(None, description="URL to episode cover art")

    @validator('audio_url')
    def validate_audio_url(cls, v):
        """Validate that the audio URL is properly formatted."""
        if not v or not v.strip():
            raise ValueError("Audio URL is required and cannot be empty")
        return v.strip()

    @validator('guid')
    def validate_guid(cls, v):
        """Validate that GUID is not empty."""
        if not v or not v.strip():
            raise ValueError("Episode GUID is required and cannot be empty")
        return v.strip()

    @property
    def duration_formatted(self) -> str:
        """Return duration in human-readable format (MM:SS or HH:MM:SS)."""
        if not self.duration:
            return "Unknown"

        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        seconds = int(self.duration % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    @property
    def size_mb(self) -> float:
        """Return file size in megabytes."""
        if not self.size:
            return 0.0
        return round(self.size / (1024 * 1024), 2)


class RSSFeed(BaseModel):
    """Represents an RSS feed containing podcast episodes.

    This model contains feed-level metadata and a list of episodes.
    Episodes are automatically sorted by publication date (newest first).
    """

    title: str = Field(description="Feed title")
    description: Optional[str] = Field(None, description="Feed description")
    link: str = Field(description="Feed URL")
    language: Optional[str] = Field(None, description="Feed language code")
    last_updated: datetime = Field(default_factory=datetime.now, description="When feed was last fetched")
    episodes: List[PodcastEpisode] = Field(default_factory=list, description="List of episodes")

    @validator('link')
    def validate_link(cls, v):
        """Validate that feed link is not empty."""
        if not v or not v.strip():
            raise ValueError("Feed link is required and cannot be empty")
        return v.strip()

    @property
    def total_episodes(self) -> int:
        """Return the total number of episodes in the feed."""
        return len(self.episodes)

    @property
    def latest_episode(self) -> Optional[PodcastEpisode]:
        """Return the most recent episode, or None if no episodes."""
        return self.episodes[0] if self.episodes else None

    def sort_episodes_by_date(self):
        """Sort episodes by publication date (newest first)."""
        self.episodes.sort(key=lambda ep: ep.pub_date, reverse=True)


class RSSProcessingResult(BaseModel):
    """Represents the result of processing an RSS feed through the pipeline.

    This model contains comprehensive information about the processing
    including successful episodes, failures, timing, and output locations.
    """

    feed_url: str = Field(description="Original RSS feed URL")
    feed_title: Optional[str] = Field(None, description="Feed title from processing")
    processed_episodes: List[dict] = Field(default_factory=list, description="Successfully processed episodes")
    failed_episodes: List[dict] = Field(default_factory=list, description="Episodes that failed to process")
    total_episodes: int = Field(description="Total episodes attempted to process")
    success_rate: float = Field(description="Success rate as percentage (0-100)")
    processing_time: float = Field(description="Total processing time in seconds")
    output_dir: Path = Field(description="Base output directory where results were saved")
    files_downloaded: int = Field(default=0, description="Number of audio files successfully downloaded")
    total_size_mb: float = Field(default=0.0, description="Total size of downloaded files in MB")

    @validator('success_rate')
    def validate_success_rate(cls, v):
        """Ensure success rate is within valid range."""
        if not 0 <= v <= 100:
            raise ValueError("Success rate must be between 0 and 100")
        return v

    @validator('processing_time')
    def validate_processing_time(cls, v):
        """Ensure processing time is non-negative."""
        if v < 0:
            raise ValueError("Processing time cannot be negative")
        return v

    @property
    def successful_count(self) -> int:
        """Return number of successfully processed episodes."""
        return len(self.processed_episodes)

    @property
    def failed_count(self) -> int:
        """Return number of failed episodes."""
        return len(self.failed_episodes)

    @property
    def processing_time_formatted(self) -> str:
        """Return processing time in human-readable format."""
        if self.processing_time < 60:
            return f"{self.processing_time:.1f}s"
        elif self.processing_time < 3600:
            minutes = int(self.processing_time // 60)
            seconds = int(self.processing_time % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(self.processing_time // 3600)
            minutes = int((self.processing_time % 3600) // 60)
            return f"{hours}h {minutes}m"

    def get_summary(self) -> str:
        """Return a human-readable summary of the processing result."""
        summary = [
            f"Feed: {self.feed_title or 'Unknown'}",
            f"URL: {self.feed_url}",
            f"Episodes: {self.successful_count}/{self.total_episodes} processed successfully",
            f"Success rate: {self.success_rate:.1f}%",
            f"Processing time: {self.processing_time_formatted}",
            f"Files downloaded: {self.files_downloaded} ({self.total_size_mb:.1f} MB)",
            f"Output directory: {self.output_dir}",
        ]

        if self.failed_episodes:
            summary.append(f"Failed episodes: {self.failed_count}")

        return "\n".join(summary)