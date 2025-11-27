"""Translation quality metrics and validation.

This module provides functions to assess translation quality and detect anomalies.
"""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from podtrans.translation.schemas import TranslationResult


@dataclass
class QualityMetrics:
    """Translation quality metrics."""

    # Completeness metrics
    total_segments: int
    translated_segments: int
    completeness_rate: float  # 0.0 - 1.0

    # Retry metrics
    retry_count: int
    retry_rate: float  # 0.0 - 1.0

    # Length metrics
    avg_original_length: float
    avg_translated_length: float
    avg_length_ratio: float  # Chinese / English

    # Speaker metrics
    speaker_count: int
    speaker_consistency: float  # 0.0 - 1.0 (all segments have speakers)

    # Anomaly flags
    has_untranslated: bool  # Contains [UNTRANSLATED] markers
    has_errors: bool  # Contains [ERROR] markers
    length_anomalies: list[int]  # Segment indices with abnormal length ratios

    @property
    def overall_score(self) -> float:
        """Calculate overall quality score (0-100).

        Returns:
            Quality score 0-100
        """
        score = 100.0

        # Deduct for incompleteness
        score -= (1 - self.completeness_rate) * 50

        # Deduct for untranslated segments
        if self.has_untranslated:
            score -= 20

        # Deduct for errors
        if self.has_errors:
            score -= 30

        # Deduct for length anomalies
        if self.length_anomalies:
            anomaly_rate = len(self.length_anomalies) / self.total_segments
            score -= anomaly_rate * 20

        # Deduct for speaker inconsistency
        score -= (1 - self.speaker_consistency) * 10

        return max(0.0, min(100.0, score))

    @property
    def grade(self) -> str:
        """Get quality grade based on score.

        Returns:
            Grade: A+ (95-100), A (85-95), B (70-85), C (60-70), D (50-60), F (<50)
        """
        score = self.overall_score

        if score >= 95:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"


def calculate_quality_metrics(
    result: TranslationResult,
    retry_count: int = 0,
) -> QualityMetrics:
    """Calculate quality metrics for translation result.

    Args:
        result: Translation result to analyze
        retry_count: Number of segments that were retried

    Returns:
        Quality metrics
    """
    total_segments = len(result.segments)

    if total_segments == 0:
        logger.warning("Empty translation result, cannot calculate metrics")
        return QualityMetrics(
            total_segments=0,
            translated_segments=0,
            completeness_rate=0.0,
            retry_count=0,
            retry_rate=0.0,
            avg_original_length=0.0,
            avg_translated_length=0.0,
            avg_length_ratio=0.0,
            speaker_count=0,
            speaker_consistency=0.0,
            has_untranslated=False,
            has_errors=False,
            length_anomalies=[],
        )

    # Completeness
    translated_segments = total_segments
    completeness_rate = 1.0

    # Length metrics
    original_lengths = [len(seg.original_text) for seg in result.segments]
    translated_lengths = [len(seg.translated_text) for seg in result.segments]

    avg_original = sum(original_lengths) / total_segments
    avg_translated = sum(translated_lengths) / total_segments
    avg_ratio = avg_translated / avg_original if avg_original > 0 else 0.0

    # Speaker metrics
    speaker_count = result.speaker_count
    segments_with_speakers = sum(1 for seg in result.segments if seg.speaker is not None)
    speaker_consistency = segments_with_speakers / total_segments

    # Anomaly detection
    has_untranslated = False
    has_errors = False
    length_anomalies = []

    for i, seg in enumerate(result.segments):
        # Check for markers
        if "[UNTRANSLATED]" in seg.translated_text:
            has_untranslated = True

        if "[ERROR]" in seg.translated_text:
            has_errors = True

        # Check length ratio anomalies
        if len(seg.original_text) > 0:
            ratio = len(seg.translated_text) / len(seg.original_text)
            # Abnormal if ratio < 0.3 or > 3.0
            if ratio < 0.3 or ratio > 3.0:
                length_anomalies.append(i)

    # Retry metrics
    retry_rate = retry_count / total_segments if total_segments > 0 else 0.0

    return QualityMetrics(
        total_segments=total_segments,
        translated_segments=translated_segments,
        completeness_rate=completeness_rate,
        retry_count=retry_count,
        retry_rate=retry_rate,
        avg_original_length=avg_original,
        avg_translated_length=avg_translated,
        avg_length_ratio=avg_ratio,
        speaker_count=speaker_count,
        speaker_consistency=speaker_consistency,
        has_untranslated=has_untranslated,
        has_errors=has_errors,
        length_anomalies=length_anomalies,
    )


def validate_translation_result(result: TranslationResult) -> list[str]:
    """Validate translation result and return list of issues.

    Args:
        result: Translation result to validate

    Returns:
        List of issue descriptions (empty if no issues)
    """
    issues = []

    # Check completeness
    if len(result.segments) == 0:
        issues.append("Empty translation result")
        return issues

    # Check for untranslated segments
    untranslated_count = sum(
        1 for seg in result.segments if "[UNTRANSLATED]" in seg.translated_text
    )
    if untranslated_count > 0:
        issues.append(
            f"Contains {untranslated_count} untranslated segments "
            f"({untranslated_count / len(result.segments) * 100:.1f}%)"
        )

    # Check for error markers
    error_count = sum(
        1 for seg in result.segments if "[ERROR]" in seg.translated_text
    )
    if error_count > 0:
        issues.append(
            f"Contains {error_count} error segments "
            f"({error_count / len(result.segments) * 100:.1f}%)"
        )

    # Check for empty translations
    empty_count = sum(1 for seg in result.segments if not seg.translated_text.strip())
    if empty_count > 0:
        issues.append(f"Contains {empty_count} empty translations")

    # Check speaker consistency
    if result.speaker_count > 0:
        segments_without_speaker = sum(
            1 for seg in result.segments if seg.speaker is None
        )
        if segments_without_speaker > 0:
            issues.append(
                f"{segments_without_speaker} segments missing speaker labels "
                f"({segments_without_speaker / len(result.segments) * 100:.1f}%)"
            )

    # Check for length anomalies
    anomaly_count = 0
    for i, seg in enumerate(result.segments):
        if len(seg.original_text) > 0:
            ratio = len(seg.translated_text) / len(seg.original_text)
            if ratio < 0.3:
                anomaly_count += 1
                logger.debug(
                    f"Segment {i}: Translation too short (ratio={ratio:.2f}), "
                    f"original='{seg.original_text[:50]}...'"
                )
            elif ratio > 3.0:
                anomaly_count += 1
                logger.debug(
                    f"Segment {i}: Translation too long (ratio={ratio:.2f}), "
                    f"original='{seg.original_text[:50]}...'"
                )

    if anomaly_count > 0:
        issues.append(
            f"{anomaly_count} segments with abnormal length ratios "
            f"({anomaly_count / len(result.segments) * 100:.1f}%)"
        )

    return issues


def generate_quality_report(
    result: TranslationResult,
    retry_count: int = 0,
    output_path: Path | None = None,
) -> str:
    """Generate quality report for translation result.

    Args:
        result: Translation result to analyze
        retry_count: Number of segments that were retried
        output_path: Optional path to save report (Markdown format)

    Returns:
        Quality report as Markdown string
    """
    metrics = calculate_quality_metrics(result, retry_count)
    issues = validate_translation_result(result)

    report = f"""# Translation Quality Report

## Overall Assessment

- **Quality Score**: {metrics.overall_score:.1f}/100
- **Grade**: {metrics.grade}
- **Status**: {'✅ Pass' if metrics.overall_score >= 70 else '⚠️ Needs Review' if metrics.overall_score >= 50 else '❌ Fail'}

## Metrics Summary

### Completeness
- Total Segments: {metrics.total_segments}
- Translated Segments: {metrics.translated_segments}
- Completeness Rate: {metrics.completeness_rate * 100:.2f}%

### Reliability
- Retry Count: {metrics.retry_count}
- Retry Rate: {metrics.retry_rate * 100:.2f}%

### Length Statistics
- Avg Original Length: {metrics.avg_original_length:.1f} chars
- Avg Translated Length: {metrics.avg_translated_length:.1f} chars
- Avg Length Ratio (CN/EN): {metrics.avg_length_ratio:.2f}

### Speaker Information
- Speaker Count: {metrics.speaker_count}
- Speaker Consistency: {metrics.speaker_consistency * 100:.2f}%

## Anomalies Detected

"""

    if not issues:
        report += "✅ No issues detected\n"
    else:
        report += f"⚠️ Found {len(issues)} issue(s):\n\n"
        for i, issue in enumerate(issues, 1):
            report += f"{i}. {issue}\n"

    if metrics.length_anomalies:
        report += f"\n### Length Anomaly Details\n\n"
        report += f"Segments with abnormal length ratios: {metrics.length_anomalies}\n"

    report += f"""
## Recommendations

"""

    if metrics.overall_score >= 95:
        report += "✅ Excellent quality. No action needed.\n"
    elif metrics.overall_score >= 85:
        report += "✅ Good quality. Minor improvements possible.\n"
    elif metrics.overall_score >= 70:
        report += "⚠️ Acceptable quality. Consider reviewing anomalies.\n"
    elif metrics.overall_score >= 50:
        report += "⚠️ Quality needs improvement. Review and fix issues.\n"
    else:
        report += "❌ Poor quality. Significant issues require attention.\n"

    if metrics.has_untranslated:
        report += "- ⚠️ Review untranslated segments\n"

    if metrics.has_errors:
        report += "- ⚠️ Fix error segments\n"

    if metrics.retry_rate > 0.1:
        report += "- 💡 High retry rate. Consider smaller batch sizes or better prompts.\n"

    if metrics.length_anomalies:
        report += f"- 💡 {len(metrics.length_anomalies)} length anomalies detected. Manual review recommended.\n"

    report += f"""
---

**Model**: {result.model_name}
**Source Language**: {result.source_language}
**Target Language**: {result.target_language}
"""

    # Save if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        logger.info(f"Quality report saved to {output_path}")

    return report
