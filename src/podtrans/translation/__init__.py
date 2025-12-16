"""Translation module for podcast translation.

This module provides:
- Translator: Main translation class with parallel processing support
- RateLimiter: Thread-safe rate limiting for API calls
- TranslationResult/TranslatedSegment: Data schemas
- Quality metrics and validation utilities
"""

from podtrans.translation.quality import (
    QualityMetrics,
    calculate_quality_metrics,
    generate_quality_report,
    validate_translation_result,
)
from podtrans.translation.rate_limiter import RateLimiter
from podtrans.translation.schemas import TranslatedSegment, TranslationResult
from podtrans.translation.translator import Translator

__all__ = [
    "TranslatedSegment",
    "TranslationResult",
    "Translator",
    "RateLimiter",
    "QualityMetrics",
    "calculate_quality_metrics",
    "validate_translation_result",
    "generate_quality_report",
]
