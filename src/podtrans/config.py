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
    llm_api_key: str = Field(
        default="",
        description="LLM API 密钥（用于翻译，支持任意 OpenAI 兼容服务）",
    )

    # ===================================
    # Application Configuration
    # ===================================
    output_dir: Path = Field(
        default=Path("./output"),
        description="Output directory for processed files",
    )
    cache_dir: Path = Field(
        default=Path("./cache"),
        description="Cache directory for models and translations",
    )
    database_dir: Path = Field(
        default=Path("./database"),
        description="Database directory for episode tracking",
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
    llm_model: str = Field(
        default="qwen-coder-plus",
        description="LLM 模型名称（用于翻译）",
    )
    llm_api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="LLM API 地址（OpenAI 兼容格式）",
    )
    llm_max_tokens: int = Field(
        default=120000,
        ge=1000,
        le=200000,
        description="每批翻译的最大 token 数（默认: 120k，适配 128k 上下文模型）",
    )
    translation_use_json_mode: bool = Field(
        default=False,
        description="Use JSON mode for translation API (experimental)",
    )

    # ===================================
    # TTS Configuration (podcast-tts CLI)
    # ===================================
    tts_cli_path: str = Field(
        default="podcast-tts",
        description="Path to podcast-tts CLI executable",
    )
    tts_timeout: int = Field(
        default=3600,  # 1 hour
        ge=60,
        le=14400,  # 4 hours max
        description="TTS CLI timeout in seconds (default: 3600 = 1 hour)",
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
    # ASR Result Splitting Configuration
    # ===================================
    enable_asr_splitting: bool = Field(
        default=True,
        description="Enable ASR result splitting for long episodes",
    )
    asr_split_threshold: int = Field(
        default=600,
        ge=300,
        le=3600,
        description="Audio duration threshold for ASR result splitting in seconds (default: 600 = 10 minutes)",
    )
    asr_target_duration: int = Field(
        default=600,
        ge=300,
        le=1800,
        description="Target duration for each ASR result segment in seconds (default: 600 = 10 minutes)",
    )
    asr_min_duration: int = Field(
        default=300,
        ge=60,
        le=600,
        description="Minimum duration for each ASR result segment in seconds (default: 300 = 5 minutes)",
    )
    asr_max_duration: int = Field(
        default=900,
        ge=600,
        le=3600,
        description="Maximum duration for each ASR result segment in seconds (default: 900 = 15 minutes)",
    )

    # ===================================
    # Segment Translation Configuration
    # ===================================
    enable_segment_translation: bool = Field(
        default=True,
        description="Enable segment-based translation for split episodes",
    )
    translation_merge_segments: bool = Field(
        default=False,
        description="Whether to merge translated segments into a single file",
    )
    translation_segment_parallel: bool = Field(
        default=False,
        description="Enable parallel translation of segments",
    )
    translation_segment_max_workers: int = Field(
        default=4,
        ge=1,
        le=8,
        description="Maximum number of parallel workers for segment translation",
    )
    translation_segment_batch_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of segments to process in each parallel batch",
    )

    # ===================================
    # Parallel Batch Translation Configuration
    # 并行批次翻译配置：用于加速多批次翻译处理
    # ===================================
    translation_parallel_enabled: bool = Field(
        default=True,
        description="Enable parallel batch translation (process multiple batches concurrently)",
    )
    translation_parallel_max_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum number of parallel workers for batch translation",
    )
    translation_rate_limit_per_second: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="Maximum API requests per second (rate limiting to avoid API throttling)",
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
    llm_max_segments_per_batch: int = Field(
        default=100,
        ge=1,
        le=500,
        description="每批翻译的最大段落数（推荐: 50-100）",
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

    # ===================================
    # 智谱 Batch API 配置
    # 用于大批量翻译任务，价格为标准 API 的 50%
    # ===================================
    zhipu_api_key: str = Field(
        default="",
        description="智谱 AI API 密钥（用于 Batch API 批量翻译）",
    )
    zhipu_batch_model: str = Field(
        default="glm-4-plus",
        description="智谱批量翻译使用的模型（推荐: glm-4-plus, glm-4-air-250414）",
    )
    zhipu_batch_poll_interval: int = Field(
        default=60,
        ge=10,
        le=600,
        description="批量任务状态轮询间隔（秒，默认: 60）",
    )
    zhipu_batch_timeout: int = Field(
        default=86400,
        ge=3600,
        le=604800,
        description="批量任务超时时间（秒，默认: 86400 = 24小时）",
    )
    zhipu_batch_auto_delete_input: bool = Field(
        default=True,
        description="批量任务完成后是否自动删除输入文件",
    )

    @field_validator("output_dir", "log_dir", "cache_dir", "database_dir")
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
        """Get cache directory path (already validated and created)."""
        return self.cache_dir

    def get_database_dir(self) -> Path:
        """Get database directory path (already validated and created)."""
        return self.database_dir

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
