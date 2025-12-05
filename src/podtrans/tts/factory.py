"""Factory for creating TTS service instances.

This module provides factory functions to create both the original
complex SoulX CLI TTS service and the new simplified version.
"""

from pathlib import Path

from .base import TTSService
from .soulx.cli_client import SoulXCLIClient
from .soulx.simple_client import SimpleSoulXService
from ..config import get_settings
from rich.console import Console

console = Console()


def create_tts_service() -> TTSService:
    """Create SoulX CLI TTS service instance (original complex version).

    Returns:
        TTSService: The configured SoulX CLI service instance

    Raises:
        RuntimeError: If CLI service cannot be initialized
    """
    return _create_cli_service()


def create_simple_tts_service() -> SimpleSoulXService:
    """Create simplified SoulX CLI service instance.

    This is the new simplified version that directly calls the CLI
    without complex logic or environment management.

    Returns:
        SimpleSoulXService: The configured simplified SoulX CLI service

    Raises:
        RuntimeError: If CLI service cannot be initialized
    """
    return _create_simple_cli_service()


def _create_cli_service() -> TTSService:
    """Create CLI-based TTS service with simple availability check."""
    settings = get_settings()

    try:
        # Simple check: verify CLI file exists
        console.print(f"[blue]Checking SoulX CLI at:[/blue] {settings.soulx_cli_path}")

        cli_file = Path(settings.soulx_cli_path)
        if not cli_file.exists():
            console.print(
                f"[red]✗[/red] SoulX CLI file not found: {settings.soulx_cli_path}"
            )
            raise RuntimeError("SoulX CLI file not found")

        console.print(f"[green]✓[/green] SoulX CLI file exists: {cli_file.name}")
        console.print(f"[green]✓[/green] Environment: {settings.soulx_conda_env}")
        console.print(
            f"[yellow]Note:[/yellow] Assuming SoulX environment is properly configured (user verified)"
        )

        return SoulXCLIClient(
            cli_path=settings.soulx_cli_path,
            conda_env=settings.soulx_conda_env,
            use_conda_env=True,
        )

    except FileNotFoundError:
        console.print(f"[red]✗[/red] SoulX CLI not found at: {settings.soulx_cli_path}")
        console.print("[yellow]Please check your SOULX_CLI_PATH configuration[/yellow]")
        raise RuntimeError("SoulX CLI not found")
    except Exception as e:
        console.print(f"[red]✗[/red] Error initializing SoulX CLI: {e}")
        raise RuntimeError(f"Failed to initialize SoulX CLI: {e}")


def _create_simple_cli_service() -> SimpleSoulXService:
    """Create simplified CLI-based TTS service."""
    settings = get_settings()

    try:
        console.print("[blue]Creating Simple SoulX Service...[/blue]")
        console.print(f"[blue]Script path:[/blue] {settings.soulx_cli_script}")
        console.print(f"[blue]Working dir:[/blue] {settings.soulx_cli_working_dir}")
        console.print(f"[blue]Timeout:[/blue] {settings.soulx_cli_timeout}s")
        console.print(f"[blue]Conda env:[/blue] {settings.soulx_cli_conda_env}")
        console.print(f"[blue]Model path:[/blue] {settings.soulx_cli_model_path}")

        service = SimpleSoulXService(
            cli_script_path=settings.soulx_cli_script,
            timeout=settings.soulx_cli_timeout,
            working_dir=settings.soulx_cli_working_dir,
            conda_env=settings.soulx_cli_conda_env
        )

        # Validate CLI script exists and is readable
        if not service.validate_cli_script():
            console.print(f"[red]✗[/red] SoulX CLI script validation failed: {settings.soulx_cli_script}")
            raise RuntimeError("SoulX CLI script validation failed")

        console.print("[green]✓[/green] Simple SoulX Service created successfully")
        console.print("[yellow]Note:[/yellow] User is responsible for providing correct SoulX data format")

        return service

    except Exception as e:
        console.print(f"[red]✗[/red] Error creating Simple SoulX Service: {e}")
        raise RuntimeError(f"Failed to create Simple SoulX Service: {e}")
