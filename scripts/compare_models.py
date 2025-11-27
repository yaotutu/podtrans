#!/usr/bin/env python3
"""Compare different translation models.

This script tests multiple models on the same input and compares:
- Translation quality
- Loss rate (completeness)
- Processing speed
- API cost

Usage:
    # Test multiple models
    uv run python scripts/compare_models.py \\
      data/output/demo/asr_result.json \\
      --models qwen-max,qwen-plus,qwen-turbo

    # Test with custom batch size
    uv run python scripts/compare_models.py \\
      data/output/demo/asr_result.json \\
      --models qwen-max,qwen-plus \\
      --batch-size 50

    # Disable cache for fresh comparison
    uv run python scripts/compare_models.py \\
      data/output/demo/asr_result.json \\
      --models qwen-max,qwen-plus \\
      --no-cache
"""

import argparse
import json
import sys
import time
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.table import Table

from podtrans.asr.schemas import ASRResult
from podtrans.config import Settings
from podtrans.translation import Translator, calculate_quality_metrics


# Model pricing (as of 2025-11, per 1K tokens)
MODEL_PRICING = {
    "qwen-max": {"input": 0.02, "output": 0.06},
    "qwen-plus": {"input": 0.004, "output": 0.012},
    "qwen-turbo": {"input": 0.0008, "output": 0.0024},
    "qwen-coder-plus": {"input": 0.004, "output": 0.012},
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate API cost in CNY.

    Args:
        model: Model name
        input_tokens: Input token count
        output_tokens: Output token count

    Returns:
        Estimated cost in CNY
    """
    if model not in MODEL_PRICING:
        logger.warning(f"Unknown model pricing for {model}, using qwen-max")
        pricing = MODEL_PRICING["qwen-max"]
    else:
        pricing = MODEL_PRICING[model]

    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]

    return input_cost + output_cost


def test_model(
    asr_result: ASRResult,
    model: str,
    batch_size: int,
    use_cache: bool,
    output_dir: Path,
) -> dict:
    """Test a single model.

    Args:
        asr_result: ASR result to translate
        model: Model name to test
        batch_size: Batch size for translation
        use_cache: Whether to use cache
        output_dir: Directory to save results

    Returns:
        Test results dictionary
    """
    console = Console()
    console.print(f"\n[bold cyan]Testing model: {model}[/bold cyan]")

    # Create custom settings
    settings = Settings()
    settings.translation_model = model
    settings.translation_max_segments_per_batch = batch_size

    # Create translator
    translator = Translator(settings, enable_cache=use_cache)

    # Run translation
    input_segments = len(asr_result.segments)
    start_time = time.time()

    try:
        translation_result = translator.translate_asr_result(asr_result, "en", "zh")
        elapsed_time = time.time() - start_time

        # Calculate metrics
        output_segments = translation_result.total_segments
        loss_count = input_segments - output_segments
        loss_rate = (loss_count / input_segments) * 100 if input_segments > 0 else 0

        # Estimate tokens and cost
        avg_input_length = sum(len(seg.text) for seg in asr_result.segments) / len(
            asr_result.segments
        )
        avg_output_length = sum(
            len(seg.translated_text) for seg in translation_result.segments
        ) / len(translation_result.segments)

        # Rough estimation: 1 char ≈ 0.5 tokens for mixed EN/CN
        input_tokens = int(sum(len(seg.text) for seg in asr_result.segments) * 0.5)
        output_tokens = int(
            sum(len(seg.translated_text) for seg in translation_result.segments) * 0.5
        )

        estimated_cost = estimate_cost(model, input_tokens, output_tokens)

        # Get cache stats if enabled
        cache_stats = translator.get_cache_stats() if use_cache else None
        cache_hit_rate = (
            cache_stats["hit_rate"] * 100 if cache_stats else 0.0
        )

        # Calculate quality metrics
        quality_metrics = calculate_quality_metrics(translation_result)

        # Save result
        output_file = output_dir / f"translation_{model.replace('-', '_')}.json"
        translator.save_result(translation_result, output_file.with_suffix(""))

        console.print(f"[green]✓ Translation completed[/green]")
        console.print(f"  Output: {output_segments}/{input_segments} segments")
        console.print(f"  Loss rate: {loss_rate:.2f}%")
        console.print(f"  Time: {elapsed_time:.2f}s")
        console.print(f"  Quality score: {quality_metrics.overall_score:.1f}/100")

        return {
            "model": model,
            "success": True,
            "input_segments": input_segments,
            "output_segments": output_segments,
            "loss_count": loss_count,
            "loss_rate": loss_rate,
            "time": elapsed_time,
            "speed": output_segments / elapsed_time if elapsed_time > 0 else 0,
            "avg_input_length": avg_input_length,
            "avg_output_length": avg_output_length,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": estimated_cost,
            "cache_hit_rate": cache_hit_rate,
            "quality_score": quality_metrics.overall_score,
            "quality_grade": quality_metrics.grade,
            "error": None,
        }

    except Exception as e:
        elapsed_time = time.time() - start_time
        console.print(f"[red]✗ Translation failed: {e}[/red]")
        logger.exception(f"Model {model} failed")

        return {
            "model": model,
            "success": False,
            "input_segments": input_segments,
            "output_segments": 0,
            "loss_count": input_segments,
            "loss_rate": 100.0,
            "time": elapsed_time,
            "speed": 0,
            "avg_input_length": 0,
            "avg_output_length": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": 0,
            "cache_hit_rate": 0,
            "quality_score": 0,
            "quality_grade": "F",
            "error": str(e),
        }


def display_comparison(results: list[dict]) -> None:
    """Display comparison table.

    Args:
        results: List of test results
    """
    console = Console()

    table = Table(title="Model Comparison")
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Loss Rate", justify="right")
    table.add_column("Quality", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("Speed", justify="right")
    table.add_column("Cost (¥)", justify="right")
    table.add_column("Cache Hit", justify="right")

    for result in results:
        status = "✓" if result["success"] else "✗"
        status_style = "green" if result["success"] else "red"

        loss_style = (
            "red"
            if result["loss_rate"] > 5
            else "yellow"
            if result["loss_rate"] > 0
            else "green"
        )

        quality_style = (
            "green"
            if result["quality_score"] >= 85
            else "yellow"
            if result["quality_score"] >= 70
            else "red"
        )

        table.add_row(
            result["model"],
            f"[{status_style}]{status}[/{status_style}]",
            f"[{loss_style}]{result['loss_rate']:.2f}%[/{loss_style}]",
            f"[{quality_style}]{result['quality_score']:.1f} ({result['quality_grade']})[/{quality_style}]",
            f"{result['time']:.2f}",
            f"{result['speed']:.2f} seg/s",
            f"¥{result['estimated_cost']:.3f}",
            f"{result['cache_hit_rate']:.1f}%",
        )

    console.print("\n")
    console.print(table)

    # Find best model
    successful_results = [r for r in results if r["success"]]
    if successful_results:
        # Rank by quality score, then by cost
        best = max(
            successful_results,
            key=lambda x: (x["quality_score"], -x["estimated_cost"]),
        )

        console.print("\n[bold green]Recommended Model:[/bold green]")
        console.print(f"  Model: {best['model']}")
        console.print(f"  Quality: {best['quality_score']:.1f}/100 ({best['quality_grade']})")
        console.print(f"  Loss Rate: {best['loss_rate']:.2f}%")
        console.print(f"  Cost: ¥{best['estimated_cost']:.3f}")
        console.print(f"  Speed: {best['speed']:.2f} seg/s")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare different translation models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1],
    )

    parser.add_argument(
        "asr_file",
        type=Path,
        help="Path to ASR result JSON file",
    )

    parser.add_argument(
        "--models",
        type=str,
        default="qwen-max,qwen-plus,qwen-turbo",
        help="Comma-separated list of models to test (default: qwen-max,qwen-plus,qwen-turbo)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for translation (default: 50)",
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable translation cache",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same as ASR file)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.asr_file.exists():
        logger.error(f"ASR file not found: {args.asr_file}")
        sys.exit(1)

    # Parse models
    models = [m.strip() for m in args.models.split(",")]

    # Determine output directory
    output_dir = args.output_dir or args.asr_file.parent

    # Load ASR result
    with open(args.asr_file, encoding="utf-8") as f:
        asr_data = json.load(f)

    asr_result = ASRResult(**asr_data)

    # Test each model
    results = []
    for model in models:
        result = test_model(
            asr_result,
            model,
            args.batch_size,
            not args.no_cache,
            output_dir,
        )
        results.append(result)

    # Display comparison
    display_comparison(results)

    # Save comparison results
    comparison_file = output_dir / "model_comparison.json"
    with open(comparison_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "asr_file": str(args.asr_file),
                "batch_size": args.batch_size,
                "cache_enabled": not args.no_cache,
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    logger.info(f"Comparison results saved to {comparison_file}")


if __name__ == "__main__":
    main()
