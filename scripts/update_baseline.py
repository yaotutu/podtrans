"""Update baseline version with current output if it's better."""

import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

console = Console()


def main():
    baseline_dir = Path("data/baseline/demo_v1_baseline")
    current_dir = Path("data/output/demo")
    archive_dir = Path("data/baseline/archive")

    if not current_dir.exists():
        console.print("[red]❌ Current output not found![/red]")
        return

    # Show comparison first
    console.print("\n[bold cyan]Running comparison...[/bold cyan]")
    import subprocess

    subprocess.run(["uv", "run", "python", "scripts/compare_with_baseline.py"])

    # Ask for confirmation
    console.print("\n")
    should_update = Confirm.ask(
        "[bold yellow]Do you want to update the baseline with current output?[/bold yellow]"
    )

    if not should_update:
        console.print("[dim]Cancelled.[/dim]")
        return

    # Archive old baseline
    if baseline_dir.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"demo_v1_baseline_{timestamp}"
        archive_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"\n[cyan]📦 Archiving old baseline to:[/cyan] {archive_path}")
        shutil.copytree(baseline_dir, archive_path)
        shutil.rmtree(baseline_dir)

    # Copy current to baseline
    console.print("[cyan]📥 Updating baseline...[/cyan]")
    shutil.copytree(current_dir, baseline_dir)

    console.print("\n[bold green]✅ Baseline updated successfully![/bold green]")
    console.print(f"[dim]Old version archived in: {archive_dir}[/dim]\n")

    # Remind to update README
    console.print(
        "[yellow]⚠️  Don't forget to update data/baseline/README.md with the new version info![/yellow]\n"
    )


if __name__ == "__main__":
    main()
