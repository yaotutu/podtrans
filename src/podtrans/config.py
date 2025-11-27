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

    # ===================================
    # TTS Configuration
    # ===================================
    soulx_api_url: str = Field(
        default="http://localhost:8000",
        description="SoulX-Podcast API URL",
    )
    soulx_timeout: float = Field(
        default=300.0,
        ge=10.0,
        le=3600.0,
        description="SoulX API request timeout in seconds (default: 5 minutes)",
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
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retries for API calls",
    )

    @field_validator("output_dir", "log_dir")
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
