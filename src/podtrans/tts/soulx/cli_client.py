"""
SoulX-Podcast CLI client for local TTS generation
Handles calling SoulX CLI as a subprocess with proper environment management
"""

import subprocess
import json
import tempfile
import shutil
import os
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import torch
except ImportError:
    torch = None
from ..base import TTSService
from ..schemas import TTSResult
from ...config import get_settings
from rich.console import Console

console = Console()


class SoulXCLIClient(TTSService):
    """SoulX-Podcast CLI client for local TTS generation"""

    def __init__(
        self,
        cli_path: Optional[str] = None,
        conda_env: Optional[str] = None,
        use_conda_env: bool = True,
    ):
        """
        Initialize SoulX CLI client

        Args:
            cli_path: Path to SoulX CLI executable
            conda_env: Name of conda environment for SoulX
            use_conda_env: Whether to activate conda environment when calling CLI
        """
        settings = get_settings()
        self.cli_path = cli_path or settings.soulx_cli_path
        self.conda_env = conda_env or settings.soulx_conda_env
        self.use_conda_env = use_conda_env
        self.temp_dir = None

    def convert_format(
        self, translation_result, speaker_configs=None, **kwargs
    ) -> Dict[str, Any]:
        """Convert TranslationResult to SoulX CLI format using provided voice samples"""
        from podtrans.tts.soulx.converter import SoulXConverter

        # Always use our converter now
        converter = SoulXConverter()
        return converter.convert(translation_result, speaker_configs)

    def synthesize(self, script: dict, output_path: Path, **kwargs) -> TTSResult:
        """Synthesize speech using SoulX CLI"""
        try:
            # Create temporary directory for intermediate files
            self.temp_dir = tempfile.mkdtemp(prefix="soulx_cli_")

            # script is already converted to SoulX format
            soulx_data = script

            # Write input JSON file
            input_file = Path(self.temp_dir) / "input.json"
            with open(input_file, "w", encoding="utf-8") as f:
                json.dump(soulx_data, f, ensure_ascii=False, indent=2)

            # Prepare CLI command
            if self.use_conda_env:
                # Use conda environment
                cmd = self._build_conda_command(input_file, output_path, **kwargs)
            else:
                # Direct CLI call
                cmd = self._build_direct_command(input_file, output_path, **kwargs)

            # Execute CLI command
            console.print(
                f"[blue]Running SoulX CLI command:[/blue] {' '.join(cmd[:3])}..."
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=kwargs.get(
                    "timeout", 1800
                ),  # Increased to 30 minutes for long podcasts
                env=self._get_env_vars(),
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise RuntimeError(
                    f"SoulX CLI failed with code {result.returncode}: {error_msg}"
                )

            # Parse CLI output for metadata
            metadata = self._parse_cli_output(result.stdout)

            console.print(
                f"[green]✓[/green] SoulX CLI synthesis completed successfully"
            )

            return TTSResult(
                audio_path=output_path,
                duration=metadata.get("duration"),
                service="soulx-cli",
                segments_count=len(script.get("text", [])),
            )

        finally:
            # Cleanup temporary directory
            if self.temp_dir and Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir)

    def _build_conda_command(
        self, input_file: Path, output_path: Path, **kwargs
    ) -> list[str]:
        """Build command with conda environment activation for SoulX-Podcast"""
        settings = get_settings()

        # Find the model path (look for pretrained_models directory)
        model_path = kwargs.get("model", settings.soulx_cli_model)
        if not model_path.startswith("/"):
            # Use relative path to SoulX project
            model_path = (
                f"/home/yaotutu/SoulX-Podcast-main/pretrained_models/{model_path}"
            )

        cmd = [
            "bash",
            "-c",
            f"source ~/miniconda3/etc/profile.d/conda.sh && "
            f"conda activate {self.conda_env} && "
            f"cd /home/yaotutu/SoulX-Podcast-main && "
            f"export PYTHONPATH=/home/yaotutu/SoulX-Podcast-main:$PYTHONPATH && "
            f"python cli/podcast.py "
            f"--json_path {input_file} "
            f"--model_path {model_path} "
            f"--output_path {output_path} "
            f"--llm_engine hf "
            f"--seed 1988",
        ]

        # Add FP16 for GPU acceleration if available
        if torch and torch.cuda.is_available():
            cmd[-1] += " --fp16_flow"

        return cmd

    def _build_direct_command(
        self, input_file: Path, output_path: Path, **kwargs
    ) -> list[str]:
        """Build direct CLI command (no conda activation)"""
        settings = get_settings()

        cmd = [
            self.cli_path,
            "generate",
            "--input",
            str(input_file),
            "--output",
            str(output_path),
            "--model",
            kwargs.get("model", settings.soulx_cli_model),
        ]

        # Add optional parameters
        if "temperature" in kwargs:
            cmd.extend(["--temperature", str(kwargs["temperature"])])
        if "top_p" in kwargs:
            cmd.extend(["--top-p", str(kwargs["top_p"])])

        return cmd

    def _get_env_vars(self) -> Dict[str, str]:
        """Get environment variables for CLI execution"""
        env = os.environ.copy()

        # Preserve CUDA environment if using GPU
        if os.environ.get("CUDA_VISIBLE_DEVICES"):
            env["CUDA_VISIBLE_DEVICES"] = os.environ["CUDA_VISIBLE_DEVICES"]

        return env

    def _parse_cli_output(self, cli_output: str) -> Dict[str, Any]:
        """Parse CLI output for metadata"""
        metadata = {}
        try:
            # Try to parse JSON output if available
            if cli_output.strip().startswith("{"):
                return json.loads(cli_output)

            # Parse duration from CLI output
            for line in cli_output.strip().split("\n"):
                line = line.lower()
                if "duration" in line or "time" in line:
                    # Extract numeric value from lines like "Duration: 5.23s"
                    import re

                    match = re.search(r"(\d+\.?\d*)", line)
                    if match:
                        metadata["duration"] = float(match.group(1))
                        break

        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not parse CLI output: {e}")

        return metadata
