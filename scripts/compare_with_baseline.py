"""Compare current output with baseline version."""

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def load_json(file_path: Path) -> dict:
    """Load JSON file."""
    with open(file_path) as f:
        return json.load(f)


def count_speakers(asr_data: dict) -> int:
    """Count unique speakers in ASR result."""
    speakers = set()
    for seg in asr_data.get("segments", []):
        if seg.get("speaker"):
            speakers.add(seg["speaker"])
    return len(speakers)


def compare_versions(baseline_dir: Path, current_dir: Path):
    """Compare baseline and current version."""

    console.print("\n[bold cyan]📊 Baseline vs Current Comparison[/bold cyan]\n")

    # Load files
    baseline_asr = load_json(baseline_dir / "asr_result.json")
    current_asr = load_json(current_dir / "asr_result.json")

    baseline_trans = load_json(baseline_dir / "translation_result.json")
    current_trans = load_json(current_dir / "translation_result.json")

    # Create comparison table
    table = Table(title="Quality Metrics Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column("Baseline", style="green")
    table.add_column("Current", style="yellow")
    table.add_column("Delta", style="magenta")

    # ASR metrics
    baseline_seg = len(baseline_asr.get("segments", []))
    current_seg = len(current_asr.get("segments", []))
    table.add_row(
        "ASR Segments",
        str(baseline_seg),
        str(current_seg),
        f"{current_seg - baseline_seg:+d}",
    )

    baseline_spk = count_speakers(baseline_asr)
    current_spk = count_speakers(current_asr)
    table.add_row(
        "Speakers Detected",
        str(baseline_spk),
        str(current_spk),
        f"{current_spk - baseline_spk:+d}",
    )

    # Translation metrics
    baseline_trans_seg = baseline_trans.get(
        "total_segments", len(baseline_trans.get("segments", []))
    )
    current_trans_seg = current_trans.get(
        "total_segments", len(current_trans.get("segments", []))
    )
    table.add_row(
        "Translation Segments",
        str(baseline_trans_seg),
        str(current_trans_seg),
        f"{current_trans_seg - baseline_trans_seg:+d}",
    )

    # Loss rate
    if baseline_seg > 0:
        baseline_loss = (baseline_seg - baseline_trans_seg) / baseline_seg * 100
    else:
        baseline_loss = 0.0

    if current_seg > 0:
        current_loss = (current_seg - current_trans_seg) / current_seg * 100
    else:
        current_loss = 0.0

    table.add_row(
        "Segment Loss Rate",
        f"{baseline_loss:.1f}%",
        f"{current_loss:.1f}%",
        f"{current_loss - baseline_loss:+.1f}%",
    )

    console.print(table)

    # Speaker distribution comparison
    console.print("\n[bold cyan]🎤 Speaker Distribution[/bold cyan]\n")

    # Count speakers in translation
    baseline_speakers = {}
    for seg in baseline_trans.get("segments", []):
        spk = seg.get("speaker", "Unknown")
        baseline_speakers[spk] = baseline_speakers.get(spk, 0) + 1

    current_speakers = {}
    for seg in current_trans.get("segments", []):
        spk = seg.get("speaker", "Unknown")
        current_speakers[spk] = current_speakers.get(spk, 0) + 1

    spk_table = Table()
    spk_table.add_column("Speaker", style="cyan")
    spk_table.add_column("Baseline Count", style="green")
    spk_table.add_column("Current Count", style="yellow")

    all_speakers = sorted(set(baseline_speakers.keys()) | set(current_speakers.keys()))
    for spk in all_speakers:
        spk_table.add_row(
            spk or "Unknown",
            str(baseline_speakers.get(spk, 0)),
            str(current_speakers.get(spk, 0)),
        )

    console.print(spk_table)

    # Text comparison sample
    console.print(
        "\n[bold cyan]📝 Translation Sample Comparison (First 3 segments)[/bold cyan]\n"
    )

    baseline_segs = baseline_trans.get("segments", [])
    current_segs = current_trans.get("segments", [])

    for i in range(min(3, len(baseline_segs), len(current_segs))):
        baseline_text = baseline_segs[i].get("translated_text", "")
        current_text = current_segs[i].get("translated_text", "")

        console.print(f"[bold]Segment {i + 1}:[/bold]")
        console.print(f"  [green]Baseline:[/green] {baseline_text}")
        console.print(f"  [yellow]Current:[/yellow]  {current_text}")

        if baseline_text == current_text:
            console.print("  [dim]✓ Identical[/dim]")
        else:
            console.print("  [dim]⚠ Different[/dim]")
        console.print()


def main():
    baseline_dir = Path("data/baseline/demo_v1_baseline")
    current_dir = Path("output/demo")

    if not baseline_dir.exists():
        console.print("[red]❌ Baseline not found![/red]")
        return

    if not current_dir.exists():
        console.print("[red]❌ Current output not found![/red]")
        return

    compare_versions(baseline_dir, current_dir)

    console.print("\n[bold green]✅ Comparison complete![/bold green]\n")


if __name__ == "__main__":
    main()
