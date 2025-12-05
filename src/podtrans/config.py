"""Configuration management using Pydantic Settings.

This module provides a type-safe configuration system that loads settings from:
1. Environment variables
2. .env files
3. Default values

All settings are validated using Pydantic models.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Settings are loaded from environment variables and .env files.
    Priority: Environment variables > .env file > defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===================================
    # API Keys
    # ===================================
    hf_token: str = Field(
        default="",
        description="HuggingFace token for accessing pyannote models",
    )
    dashscope_api_key: str = Field(
        default="",
        description="DashScope API key for translation (Alibaba Qwen models)",
    )

    # ===================================
    # Application Configuration
    # ===================================
    output_dir: Path = Field(
        default=Path("./data/output"),
        description="Output directory for processed files",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_dir: Path = Field(
        default=Path("./logs"),
        description="Log directory",
    )

    # ===================================
    # Model Configuration
    # ===================================
    whisper_model: str = Field(
        default="large-v2",
        description=(
            "WhisperX model size (tiny, base, small, medium, large-v2, large-v3)"
        ),
    )
    compute_type: Literal["int8", "float16", "float32"] = Field(
        default="int8",  # int8 for CPU, float16 only works well with CUDA
        description="Compute precision for Whisper",
    )
    device: Literal["cuda", "cpu", "mps"] = Field(
        default="cpu",  # faster-whisper only supports cuda/cpu, not mps
        description=(
            "Device to use "
            "(cuda for NVIDIA GPU, cpu for CPU, mps not supported by faster-whisper)"
        ),
    )
    translation_model: str = Field(
        default="qwen-coder-plus",
        description="Translation model name (DashScope)",
    )
    translation_api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="Translation API base URL (OpenAI-compatible endpoint)",
    )
    translation_max_tokens: int = Field(
        default=120000,
        ge=1000,
        le=200000,
        description="Maximum tokens per translation batch (default: 120k for 128k context models)",
    )
    translation_use_json_mode: bool = Field(
        default=False,
        description="Use JSON mode for translation API (experimental)",
    )

    # ===================================
    # SoulX CLI Configuration
    soulx_cli_path: str = Field(
        default="soulx-podcast",
        description="Path to SoulX-Podcast CLI executable",
    )
    soulx_cli_model: str = Field(
        default="SoulX-Podcast-1.7B",
        description="SoulX CLI model name",
    )
    soulx_cli_timeout: int = Field(
        default=10800,  # 3 hours
        ge=60,
        le=21600,  # 6 hours max
        description="SoulX CLI timeout in seconds (default: 10800 = 3 hours)",
    )
    soulx_cli_temperature: float = Field(
        default=0.7,
        ge=0.1,
        le=2.0,
        description="SoulX CLI generation temperature",
    )
    soulx_cli_top_p: float = Field(
        default=0.9,
        ge=0.1,
        le=1.0,
        description="SoulX CLI top-p sampling",
    )
    soulx_conda_env: str = Field(
        default="soulxpodcast",
        description="Conda environment name for SoulX CLI",
    )

    # ===================================
    # Simple SoulX Configuration (New Simplified Version)
    # ===================================
    soulx_cli_script: str = Field(
        default="soulx_cli.py",
        description="Path to SoulX CLI Python script (simplified version)",
    )
    soulx_cli_working_dir: str = Field(
        default=".",
        description="Working directory for SoulX CLI execution",
    )
    soulx_cli_conda_env: str = Field(
        default="soulxpodcast",
        description="Conda environment name for SoulX CLI execution",
    )
    soulx_cli_model_path: str = Field(
        default="/home/yaotutu/SoulX-Podcast-main/pretrained_models/SoulX-Podcast-1.7B",
        description="Default model path for SoulX CLI execution",
    )

    # ===================================
    # Audio Segmentation Configuration
    audio_segment_max_duration: float = Field(
        default=600.0,
        ge=60.0,
        le=3600.0,
        description="Maximum duration per audio segment in seconds (default: 10 minutes)",
    )
    audio_segment_enabled: bool = Field(
        default=True,
        description="Enable automatic audio segmentation for long episodes",
    )

    # ===================================
    # Processing Configuration
    # ===================================
    asr_batch_size: int = Field(
        default=16,
        ge=1,
        le=64,
        description="Batch size for ASR processing",
    )
    translation_max_segments_per_batch: int = Field(
        default=100,
        ge=1,
        le=500,
        description=(
            "Maximum number of segments per translation batch "
            "(even if tokens allow more). Recommended: 50-100 for stability."
        ),
    )

    # ===================================
    # Voice Sample Extraction Configuration
    # ===================================
    voice_sample_extract_enabled: bool = Field(
        default=True,
        description="Whether to extract voice cloning samples during pipeline",
    )
    voice_sample_min_duration: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Minimum voice sample duration in seconds (default: 5.0)",
    )
    voice_sample_max_duration: float = Field(
        default=20.0,
        ge=1.0,
        le=60.0,
        description="Maximum voice sample duration in seconds (default: 20.0)",
    )
    voice_sample_min_quality: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Minimum voice sample quality score (0-100, default: 60.0)",
    )
    voice_sample_max_gap: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="Maximum gap between merged segments in seconds (default: 2.0)",
    )

    # ===================================
    # RSS Feed Configuration
    # ===================================
    rss_download_dir: Path = Field(
        default=Path("./data/rss_downloads"),
        description="Directory for downloaded RSS episode audio files",
    )
    rss_cache_dir: Path = Field(
        default=Path("./data/rss_cache"),
        description="Directory for RSS feed cache and tracking data",
    )
    rss_max_episode_age_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Maximum age of episodes to download and process (in days)",
    )
    rss_max_episodes_per_feed: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of episodes to download per RSS feed",
    )
    rss_timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="RSS feed fetch timeout in seconds",
    )
    rss_user_agent: str = Field(
        default="PodTrans/0.1.0 (RSS Feed Parser)",
        description="User agent string for RSS feed requests",
    )
    rss_max_file_size_mb: int = Field(
        default=500,
        ge=10,
        le=5000,
        description="Maximum audio file size to download (in megabytes)",
    )
    rss_supported_formats: list[str] = Field(
        default=["mp3", "wav", "m4a", "ogg", "flac", "aac"],
        description="List of supported audio file formats for RSS downloads",
    )
    rss_verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates for RSS feed requests",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retries for API calls and downloads",
    )

    @field_validator("output_dir", "log_dir", "rss_download_dir", "rss_cache_dir")
    @classmethod
    def create_dir_if_not_exists(cls, v: Path) -> Path:
        """Create directory if it doesn't exist."""
        v = v.expanduser().resolve()
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("whisper_model")
    @classmethod
    def validate_whisper_model(cls, v: str) -> str:
        """Validate Whisper model name."""
        valid_models = {
            "tiny",
            "base",
            "small",
            "medium",
            "large",
            "large-v1",
            "large-v2",
            "large-v3",
        }
        if v not in valid_models:
            raise ValueError(
                f"Invalid Whisper model: {v}. Must be one of {valid_models}"
            )
        return v

    def is_gpu_available(self) -> bool:
        """Check if GPU is available based on device setting."""
        return self.device in ("cuda", "mps")

    def get_cache_dir(self) -> Path:
        """Get cache directory path."""
        cache_dir = Path("./data/cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def get_input_dir(self) -> Path:
        """Get input directory path."""
        input_dir = Path("./data/input")
        input_dir.mkdir(parents=True, exist_ok=True)
        return input_dir


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get global settings instance (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)."""
    global _settings
    _settings = Settings()
    return _settings
