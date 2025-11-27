"""Translation module for podcast translation."""

from podtrans.translation.quality import (
    QualityMetrics,
    calculate_quality_metrics,
    generate_quality_report,
    validate_translation_result,
)
from podtrans.translation.schemas import TranslatedSegment, TranslationResult
from podtrans.translation.translator import Translator

__all__ = [
    "TranslatedSegment",
    "TranslationResult",
    "Translator",
    "QualityMetrics",
    "calculate_quality_metrics",
    "validate_translation_result",
    "generate_quality_report",
]
