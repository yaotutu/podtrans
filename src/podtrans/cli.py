"""Command-line interface for PodTrans.

This module provides the CLI commands using Typer.
"""

from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from podtrans.asr import WhisperXHandler
from podtrans.config import get_settings
from podtrans.models import PipelineMetadata, StageStatus
from podtrans.translation import Translator
from podtrans.translation.schemas import TranslationResult
from podtrans.tts import SoulXClient
from podtrans.tts.schemas import SpeakerConfig
from podtrans.utils.audio import get_audio_duration, validate_audio_file
from podtrans.utils.file import read_json, write_json

app = typer.Typer(
    name="podtrans",
    help="AI-powered podcast translation pipeline",
    add_completion=False,
)
console = Console()


@app.command()
def transcribe(
    audio: Path = typer.Argument(
        ...,
        exists=True,
        help="Path to audio file (mp3, wav, flac, m4a)",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: data/output/{audio_name})",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="Language code (e.g., 'en', 'zh'). Auto-detect if not specified",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Whisper model name (tiny, base, small, medium, large-v2, large-v3)",
    ),
    device: str | None = typer.Option(
        None,
        "--device",
        "-d",
        help="Device to use (cuda, mps, cpu)",
    ),
    no_diarization: bool = typer.Option(
        False,
        "--no-diarization",
        help="Disable speaker diarization",
    ),
) -> None:
    """Transcribe audio file with speaker diarization.

    This command performs:
    - Automatic Speech Recognition (ASR)
    - Word-level timestamp alignment
    - Speaker diarization (optional)

    Example:
        podtrans transcribe data/input/demo.mp3

        podtrans transcribe podcast.mp3 -o ./results -l en

        podtrans transcribe podcast.mp3 --no-diarization
    """
    settings = get_settings()

    # Validate audio file
    console.print("\n[bold blue]🎙️  PodTrans - Audio Transcription[/bold blue]\n")
    console.print(f"[dim]Audio file:[/dim] {audio}")

    if not validate_audio_file(audio):
        console.print("[bold red]❌ Invalid audio file[/bold red]")
        raise typer.Exit(1)

    # Get audio info
    try:
        duration = get_audio_duration(audio)
        duration_min = duration / 60
        console.print(
            f"[dim]Duration:[/dim] {duration:.2f} seconds ({duration_min:.2f} minutes)"
        )
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not get audio duration: {e}[/yellow]")
        duration = 0

    # Determine output directory
    if output is None:
        audio_name = audio.stem
        output_dir = settings.output_dir / audio_name
    else:
        output_dir = Path(output)

    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Output directory:[/dim] {output_dir}\n")

    # Initialize pipeline metadata
    pipeline_meta = PipelineMetadata(
        audio_file=str(audio),
        output_dir=output_dir,
    )

    # Initialize WhisperX
    console.print("[bold cyan]📝 Initializing WhisperX...[/bold cyan]")
    try:
        handler = WhisperXHandler(
            model_name=model,
            device=device,
        )
        console.print(f"[green]✓[/green] Model: {handler.model_name}")
        console.print(f"[green]✓[/green] Device: {handler.device}")
        console.print(f"[green]✓[/green] Compute type: {handler.compute_type}\n")
    except Exception as e:
        console.print(f"[bold red]❌ Failed to initialize WhisperX: {e}[/bold red]")
        pipeline_meta.update_stage("asr", StageStatus.FAILED, error=str(e))
        write_json(
            pipeline_meta.model_dump(),
            output_dir / "pipeline_metadata.json",
        )
        raise typer.Exit(1)

    # Run ASR pipeline
    console.print("[bold cyan]🚀 Starting ASR pipeline...[/bold cyan]\n")
    pipeline_meta.update_stage("asr", StageStatus.RUNNING)

    try:
        # Run full pipeline
        asr_result = handler.process_full_pipeline(
            audio_path=audio,
            language=language,
            enable_diarization=not no_diarization,
        )

        # Mark as success
        pipeline_meta.update_stage(
            "asr",
            StageStatus.SUCCESS,
            segments=asr_result.total_segments,
            speakers=asr_result.speaker_count,
            language=asr_result.language,
        )

        # Save results
        console.print("\n[bold cyan]💾 Saving results...[/bold cyan]")

        # Save ASR result
        asr_output_file = output_dir / "asr_result.json"
        write_json(asr_result.model_dump(), asr_output_file)
        console.print(f"[green]✓[/green] ASR result: {asr_output_file}")

        # Save transcript as plain text
        transcript_file = output_dir / "transcript.txt"
        transcript_file.write_text(asr_result.to_text(include_speakers=True))
        console.print(f"[green]✓[/green] Transcript: {transcript_file}")

        # Save pipeline metadata
        metadata_file = output_dir / "pipeline_metadata.json"
        write_json(pipeline_meta.model_dump(), metadata_file)
        console.print(f"[green]✓[/green] Metadata: {metadata_file}")

        # Display summary
        console.print("\n" + "=" * 60)
        console.print("[bold green]✨ Transcription Complete![/bold green]\n")

        # Create summary table
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Language", asr_result.language.upper())
        table.add_row("Segments", str(asr_result.total_segments))
        table.add_row("Speakers", str(asr_result.speaker_count))
        table.add_row(
            "Duration",
            f"{pipeline_meta.total_duration_seconds:.2f}s"
            if pipeline_meta.total_duration_seconds
            else "N/A",
        )
        table.add_row("Output", str(output_dir))

        console.print(table)
        console.print("\n" + "=" * 60 + "\n")

        # Show first few segments as preview
        if asr_result.segments:
            console.print("[bold]📄 Preview (first 3 segments):[/bold]\n")
            for seg in asr_result.segments[:3]:
                speaker_label = f"[{seg.speaker}]" if seg.speaker else "[Unknown]"
                console.print(
                    f"[dim]{seg.start:.2f}s - {seg.end:.2f}s[/dim] "
                    f"[cyan]{speaker_label}[/cyan] {seg.text}"
                )
            if len(asr_result.segments) > 3:
                remaining = len(asr_result.segments) - 3
                console.print(f"\n[dim]... and {remaining} more segments[/dim]")

        console.print()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        pipeline_meta.update_stage(
            "asr", StageStatus.FAILED, error="Interrupted by user"
        )
        write_json(
            pipeline_meta.model_dump(),
            output_dir / "pipeline_metadata.json",
        )
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]❌ Transcription failed: {e}[/bold red]")
        logger.exception("Transcription error")
        pipeline_meta.update_stage("asr", StageStatus.FAILED, error=str(e))
        write_json(
            pipeline_meta.model_dump(),
            output_dir / "pipeline_metadata.json",
        )
        raise typer.Exit(1)


@app.command()
def translate(
    asr_json: Path = typer.Argument(
        ...,
        exists=True,
        help="Path to ASR result JSON file",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: same as ASR result directory)",
    ),
    source_lang: str = typer.Option(
        "en",
        "--source",
        "-s",
        help="Source language code (e.g., 'en')",
    ),
    target_lang: str = typer.Option(
        "zh",
        "--target",
        "-t",
        help="Target language code (e.g., 'zh')",
    ),
) -> None:
    """Translate ASR result to target language.

    This command translates the transcription result from ASR to the target language
    using OpenAI-compatible API (DashScope).

    Example:
        podtrans translate data/output/demo/asr_result.json

        podtrans translate asr_result.json -o ./translation -s en -t zh
    """
    settings = get_settings()

    # Display header
    console.print("\n[bold blue]🌐 PodTrans - Translation[/bold blue]\n")
    console.print(f"[dim]ASR result:[/dim] {asr_json}")
    console.print(f"[dim]Translation:[/dim] {source_lang} → {target_lang}\n")

    # Check API key
    if not settings.dashscope_api_key:
        console.print(
            "[bold red]❌ Error: DASHSCOPE_API_KEY not set[/bold red]\n"
            "[dim]Please set your DashScope API key in .env file:[/dim]\n"
            "DASHSCOPE_API_KEY=your_api_key_here\n"
        )
        raise typer.Exit(1)

    # Determine output directory
    if output is None:
        output_dir = asr_json.parent
    else:
        output_dir = Path(output)

    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Output directory:[/dim] {output_dir}\n")

    # Initialize translator
    console.print("[bold cyan]🔧 Initializing translator...[/bold cyan]")
    try:
        translator = Translator(settings)
        console.print(f"[green]✓[/green] Model: {translator.model}")
        console.print(f"[green]✓[/green] API base: {settings.translation_api_base}")
        console.print(
            f"[green]✓[/green] Max segments/batch: {settings.translation_max_segments_per_batch}\n"
        )
    except Exception as e:
        console.print(f"[bold red]❌ Failed to initialize translator: {e}[/bold red]")
        raise typer.Exit(1)

    # Load ASR result
    console.print("[bold cyan]📖 Loading ASR result...[/bold cyan]")
    try:
        asr_result = translator.load_asr_result(asr_json)
        console.print(f"[green]✓[/green] Loaded {asr_result.total_segments} segments")
        console.print(
            f"[green]✓[/green] Detected {asr_result.speaker_count} speakers\n"
        )
    except Exception as e:
        console.print(f"[bold red]❌ Failed to load ASR result: {e}[/bold red]")
        raise typer.Exit(1)

    # Run translation
    console.print("[bold cyan]🚀 Starting translation...[/bold cyan]\n")

    try:
        translation_result = translator.translate_asr_result(
            asr_result, source_lang, target_lang
        )

        # Save results
        console.print("\n[bold cyan]💾 Saving results...[/bold cyan]")

        output_base = output_dir / "translation_result"
        translator.save_result(
            translation_result,
            output_base,
            save_bilingual=True,
        )

        # Display summary
        console.print("\n" + "=" * 60)
        console.print("[bold green]✨ Translation Complete![/bold green]\n")

        # Create summary table
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Model", translation_result.model_name)
        table.add_row(
            "Languages",
            f"{translation_result.source_language} → {translation_result.target_language}",
        )
        table.add_row("Segments", str(translation_result.total_segments))
        table.add_row("Speakers", str(translation_result.speaker_count))
        table.add_row("Output", str(output_dir))

        console.print(table)
        console.print("\n" + "=" * 60 + "\n")

        # Show preview
        if translation_result.segments:
            console.print("[bold]📄 Preview (first 3 segments):[/bold]\n")
            for seg in translation_result.segments[:3]:
                speaker_label = f"[{seg.speaker}]" if seg.speaker else "[Unknown]"
                console.print(
                    f"[dim]{seg.start:.2f}s - {seg.end:.2f}s[/dim] "
                    f"[cyan]{speaker_label}[/cyan]"
                )
                console.print(f"  [dim]EN:[/dim] {seg.original_text}")
                console.print(f"  [dim]ZH:[/dim] {seg.translated_text}\n")

            if len(translation_result.segments) > 3:
                remaining = len(translation_result.segments) - 3
                console.print(f"[dim]... and {remaining} more segments[/dim]")

        console.print()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]❌ Translation failed: {e}[/bold red]")
        logger.exception("Translation error")
        raise typer.Exit(1)


@app.command()
def synthesize(
    translation_json: Path = typer.Argument(
        ...,
        exists=True,
        help="Path to translation result JSON file",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output audio file path (default: same directory as translation result)",
    ),
    speaker_audio: list[str] | None = typer.Option(
        None,
        "--speaker-audio",
        "-s",
        help="Speaker voice samples (format: SPEAKER_ID=path/to/audio.wav)",
    ),
    speaker_desc: list[str] | None = typer.Option(
        None,
        "--speaker-desc",
        "-d",
        help="Speaker voice descriptions (format: SPEAKER_ID=中年男性，声音低沉)",
    ),
) -> None:
    """Generate podcast audio from translation result using TTS.

    This command synthesizes audio from the translated text using the SoulX-Podcast
    TTS service. It preserves speaker information and generates natural-sounding
    podcast audio.

    Example:
        podtrans synthesize data/output/demo/translation_result.json

        podtrans synthesize translation_result.json -o output.wav

        podtrans synthesize translation_result.json \\
            --speaker-audio SPEAKER_00=voices/male.wav \\
            --speaker-audio SPEAKER_01=voices/female.wav

        podtrans synthesize translation_result.json \\
            --speaker-desc SPEAKER_00=中年男性，声音低沉 \\
            --speaker-desc SPEAKER_01=年轻女性，声音清脆
    """
    settings = get_settings()

    # Display header
    console.print("\n[bold blue]🎙️  PodTrans - TTS Synthesis[/bold blue]\n")
    console.print(f"[dim]Translation result:[/dim] {translation_json}\n")

    # Determine output path
    if output is None:
        output_path = translation_json.parent / "podcast_output.wav"
    else:
        output_path = Path(output)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Output audio:[/dim] {output_path}\n")

    # Parse speaker configurations
    speaker_configs: list[SpeakerConfig] = []

    # Parse speaker audio samples
    audio_map: dict[str, Path] = {}
    if speaker_audio:
        for item in speaker_audio:
            try:
                speaker_id, audio_path_str = item.split("=", 1)
                audio_path = Path(audio_path_str)
                if not audio_path.exists():
                    console.print(
                        f"[yellow]⚠️  Speaker audio not found: {audio_path}[/yellow]"
                    )
                    continue
                audio_map[speaker_id] = audio_path
            except ValueError:
                console.print(
                    f"[yellow]⚠️  Invalid speaker-audio format: {item}[/yellow]"
                )
                continue

    # Parse speaker descriptions
    desc_map: dict[str, str] = {}
    if speaker_desc:
        for item in speaker_desc:
            try:
                speaker_id, description = item.split("=", 1)
                desc_map[speaker_id] = description
            except ValueError:
                console.print(
                    f"[yellow]⚠️  Invalid speaker-desc format: {item}[/yellow]"
                )
                continue

    # Load translation result
    console.print("[bold cyan]📖 Loading translation result...[/bold cyan]")
    try:
        translation_data = read_json(translation_json)
        translation_result = TranslationResult(**translation_data)
        console.print(
            f"[green]✓[/green] Loaded {translation_result.total_segments} segments"
        )
        console.print(
            f"[green]✓[/green] Detected {translation_result.speaker_count} speakers\n"
        )

        # Build speaker configs from translation result
        unique_speakers = set()
        for seg in translation_result.segments:
            if seg.speaker:
                unique_speakers.add(seg.speaker)

        for speaker_id in sorted(unique_speakers):
            config = SpeakerConfig(
                speaker_id=speaker_id,
                voice_sample=audio_map.get(speaker_id),
                voice_description=desc_map.get(speaker_id),
            )
            speaker_configs.append(config)

        if speaker_configs:
            console.print("[bold cyan]🎤 Speaker configurations:[/bold cyan]")
            for config in speaker_configs:
                console.print(f"  [cyan]{config.speaker_id}[/cyan]")
                if config.voice_sample:
                    console.print(f"    [dim]Voice sample:[/dim] {config.voice_sample}")
                if config.voice_description:
                    console.print(
                        f"    [dim]Description:[/dim] {config.voice_description}"
                    )
            console.print()

    except Exception as e:
        console.print(f"[bold red]❌ Failed to load translation result: {e}[/bold red]")
        logger.exception("Translation loading error")
        raise typer.Exit(1)

    # Initialize SoulX client
    console.print("[bold cyan]🔧 Initializing TTS client...[/bold cyan]")
    try:
        tts_client = SoulXClient(settings)
        console.print(f"[green]✓[/green] SoulX API: {settings.soulx_api_url}")
        console.print(f"[green]✓[/green] Timeout: {settings.soulx_timeout}s\n")
    except Exception as e:
        console.print(f"[bold red]❌ Failed to initialize TTS client: {e}[/bold red]")
        raise typer.Exit(1)

    # Convert format
    console.print("[bold cyan]🔄 Converting to SoulX format...[/bold cyan]")
    try:
        soulx_script = tts_client.convert_format(
            translation_result,
            speaker_configs if speaker_configs else None,
        )
        console.print(
            f"[green]✓[/green] Script ready: {len(soulx_script['text'])} segments"
        )
        console.print(f"[green]✓[/green] Speakers: {len(soulx_script['speakers'])}\n")
    except Exception as e:
        console.print(f"[bold red]❌ Format conversion failed: {e}[/bold red]")
        logger.exception("Format conversion error")
        raise typer.Exit(1)

    # Synthesize audio
    console.print("[bold cyan]🚀 Synthesizing audio...[/bold cyan]")
    console.print("[dim]This may take several minutes for long podcasts...[/dim]\n")

    try:
        tts_result = tts_client.synthesize(
            script=soulx_script,
            output_path=output_path,
        )

        # Display summary
        console.print("\n" + "=" * 60)
        console.print("[bold green]✨ Synthesis Complete![/bold green]\n")

        # Create summary table
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Service", tts_result.service)
        table.add_row("Format", tts_result.format)
        table.add_row("Segments", str(tts_result.segments_count))
        table.add_row("Output", str(tts_result.audio_path))

        if tts_result.duration:
            duration_min = tts_result.duration / 60
            table.add_row(
                "Duration",
                f"{tts_result.duration:.2f}s ({duration_min:.2f} min)",
            )

        console.print(table)
        console.print("\n" + "=" * 60 + "\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]❌ Synthesis failed: {e}[/bold red]")
        logger.exception("TTS synthesis error")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(
        Panel.fit(
            "[bold cyan]PodTrans[/bold cyan]\n"
            "[dim]Version:[/dim] 0.1.0\n"
            "[dim]AI-powered podcast translation pipeline[/dim]",
            border_style="cyan",
        )
    )


@app.callback()
def main() -> None:
    """PodTrans - AI-powered podcast translation pipeline.

    Translate English podcasts to Chinese while preserving speaker information.
    """
    pass


if __name__ == "__main__":
    app()
