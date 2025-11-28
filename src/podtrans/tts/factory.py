"""Factory for creating TTS service instances.

This module provides a factory function to create SoulX CLI TTS service.
"""

import subprocess
from pathlib import Path

from .base import TTSService
from .soulx.cli_client import SoulXCLIClient
from ..config import get_settings
from rich.console import Console

console = Console()


def create_tts_service() -> TTSService:
    """Create SoulX CLI TTS service instance.

    Returns:
        TTSService: The configured SoulX CLI service instance

    Raises:
        RuntimeError: If CLI service cannot be initialized
    """
    return _create_cli_service()


def _create_cli_service() -> TTSService:
    """Create CLI-based TTS service with simple availability check."""
    settings = get_settings()

    try:
        # Simple check: verify CLI file exists
        console.print(f"[blue]Checking SoulX CLI at:[/blue] {settings.soulx_cli_path}")

        cli_file = Path(settings.soulx_cli_path)
        if not cli_file.exists():
            console.print(f"[red]✗[/red] SoulX CLI file not found: {settings.soulx_cli_path}")
            raise RuntimeError("SoulX CLI file not found")

        console.print(f"[green]✓[/green] SoulX CLI file exists: {cli_file.name}")
        console.print(f"[green]✓[/green] Environment: {settings.soulx_conda_env}")
        console.print(f"[yellow]Note:[/yellow] Assuming SoulX environment is properly configured (user verified)")

        return SoulXCLIClient(
            cli_path=settings.soulx_cli_path,
            conda_env=settings.soulx_conda_env,
            use_conda_env=True
        )

    except FileNotFoundError:
        console.print(f"[red]✗[/red] SoulX CLI not found at: {settings.soulx_cli_path}")
        console.print("[yellow]Please check your SOULX_CLI_PATH configuration[/yellow]")
        raise RuntimeError("SoulX CLI not found")
    except Exception as e:
        console.print(f"[red]✗[/red] Error initializing SoulX CLI: {e}")
        raise RuntimeError(f"Failed to initialize SoulX CLI: {e}")


