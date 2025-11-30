"""Command-line interface for PodTrans.

This module provides the CLI commands using Typer.
"""

from pathlib import Path
import asyncio

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from podtrans.asr import WhisperXHandler
from podtrans.asr.schemas import ASRResult
from podtrans.config import get_settings
from podtrans.models import PipelineMetadata, StageStatus
from podtrans.translation import Translator
from podtrans.translation.schemas import TranslationResult
from podtrans.tts.factory import create_tts_service
from podtrans.tts.schemas import SpeakerConfig
from podtrans.utils.audio import get_audio_duration, validate_audio_file
from podtrans.utils.file import read_json, write_json
from podtrans.pipeline.orchestrator import PipelineOrchestrator

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
    # SoulX CLI specific options
    temperature: float = typer.Option(
        None,
        "--temperature",
        "-t",
        help="Generation temperature for CLI backend (0.1-2.0, default: 0.7)",
    ),
    top_p: float = typer.Option(
        None,
        "--top-p",
        help="Top-p sampling for CLI backend (0.1-1.0, default: 0.9)",
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Model name for CLI backend (default: SoulX-Podcast-1.7B)",
    ),
) -> None:
    """Generate podcast audio from translation result using SoulX CLI.

    This command synthesizes audio from the translated text using the SoulX-Podcast
    CLI TTS service, preserving speaker information and generating natural-sounding podcast audio.

    Examples:
        # Basic usage
        podtrans synthesize data/output/demo/translation_result.json

        # Specify output file
        podtrans synthesize translation_result.json -o output.wav

        # CLI with custom parameters
        podtrans synthesize translation_result.json --temperature 0.8

        # With speaker configurations
        podtrans synthesize translation_result.json \\
            --speaker-audio SPEAKER_00=voices/male.wav \\
            --speaker-audio SPEAKER_01=voices/female.wav \\
            --speaker-desc SPEAKER_00=中年男性，声音低沉 \\
            --speaker-desc SPEAKER_01=年轻女性，声音清脆
    """
    settings = get_settings()

    # Display header
    console.print("\n[bold blue]🎙️  PodTrans - TTS Synthesis (SoulX CLI)[/bold blue]\n")
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

    # Initialize SoulX CLI client
    console.print("[bold cyan]🔧 Initializing SoulX CLI client...[/bold cyan]")
    try:
        tts_client = create_tts_service()
        console.print(f"[green]✓[/green] SoulX CLI: {settings.soulx_cli_path}")
        console.print(f"[green]✓[/green] Model: {settings.soulx_cli_model}")
        console.print(f"[green]✓[/green] Environment: {settings.soulx_conda_env}")
        console.print()
    except Exception as e:
        console.print(
            f"[bold red]❌ Failed to initialize SoulX CLI client: {e}[/bold red]"
        )
        logger.exception("TTS client initialization error")
        raise typer.Exit(1)

    # Prepare synthesis parameters
    synthesize_kwargs = {}

    # Add CLI-specific parameters
    if temperature is not None:
        synthesize_kwargs["temperature"] = temperature
    if top_p is not None:
        synthesize_kwargs["top_p"] = top_p
    if model is not None:
        synthesize_kwargs["model"] = model

    # Add speaker configurations to kwargs
    for config in speaker_configs:
        if config.voice_sample:
            synthesize_kwargs[f"speaker_{config.speaker_id.split('_')[1]}_audio"] = (
                config.voice_sample
            )
        if config.voice_description:
            synthesize_kwargs[f"speaker_{config.speaker_id.split('_')[1]}_desc"] = (
                config.voice_description
            )

    # CLI backend - format conversion happens in synthesize method
    console.print("[bold cyan]🔄 Preparing synthesis parameters...[/bold cyan]")
    console.print(
        f"[green]✓[/green] Translation segments: {len(translation_result.segments)}"
    )
    console.print(
        f"[green]✓[/green] Speakers: {len(set(s.speaker for s in translation_result.segments if s.speaker))}\n"
    )

    # Synthesize audio
    console.print("[bold cyan]🚀 Synthesizing audio...[/bold cyan]")
    console.print("[dim]This may take several minutes for long podcasts...[/dim]\n")

    try:
        # CLI backend - pass translation result directly
        tts_result = tts_client.synthesize(
            translation_result, output_path, **synthesize_kwargs
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
def pipeline(
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
        help="Language code for ASR (e.g., 'en', 'zh'). Auto-detect if not specified",
    ),
    source_lang: str = typer.Option(
        "en",
        "--source",
        "-s",
        help="Source language for translation",
    ),
    target_lang: str = typer.Option(
        "zh",
        "--target",
        "-t",
        help="Target language for translation",
    ),
    no_diarization: bool = typer.Option(
        False,
        "--no-diarization",
        help="Disable speaker diarization",
    ),
    no_voice_samples: bool = typer.Option(
        False,
        "--no-voice-samples",
        help="Disable voice sample extraction",
    ),
    min_sample_duration: float | None = typer.Option(
        None,
        "--min-sample-duration",
        help="Minimum voice sample duration in seconds (default: from config)",
    ),
    max_sample_duration: float | None = typer.Option(
        None,
        "--max-sample-duration",
        help="Maximum voice sample duration in seconds (default: from config)",
    ),
    min_sample_quality: float | None = typer.Option(
        None,
        "--min-sample-quality",
        help="Minimum voice sample quality score (0-100, default: from config)",
    ),
) -> None:
    """Run complete podcast translation pipeline (ASR → Voice Samples → Translation → TTS).

    This command orchestrates all stages in sequence:
    1. Transcribe audio with speaker diarization
    2. Extract voice cloning samples for each speaker (NEW!)
    3. Translate transcriptions to target language
    4. Generate synthesized podcast audio

    Voice samples are extracted automatically and saved in voice_samples/ subdirectory.
    Each speaker gets one high-quality sample optimized for voice cloning.

    This is the recommended way to process podcasts end-to-end.

    Example:
        podtrans pipeline data/input/demo.mp3

        podtrans pipeline podcast.mp3 -o ./results -l en -s en -t zh

        podtrans pipeline episode.mp3 --no-diarization --no-voice-samples

        podtrans pipeline podcast.mp3 --min-sample-quality 75 --min-sample-duration 8
    """
    settings = get_settings()

    # Validate audio file
    console.print("\n[bold blue]🎙️  PodTrans - Complete Pipeline[/bold blue]\n")
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

    # Create and run Pipeline orchestrator
    console.print("[bold cyan]🔄 Starting complete pipeline...[/bold cyan]\n")

    try:
        orchestrator = PipelineOrchestrator(output_dir)
        pipeline_meta = asyncio.run(
            orchestrator.run_pipeline(
                audio_path=audio,
                language=language,
                enable_diarization=not no_diarization,
                source_lang=source_lang,
                target_lang=target_lang,
                extract_voice_samples=False
                if no_voice_samples
                else None,  # Use config default if not disabled
                min_duration=min_sample_duration,
                max_duration=max_sample_duration,
                min_quality=min_sample_quality,
            )
        )

        # Display final results
        console.print("\n" + "=" * 60)
        console.print("[bold green]✨ Pipeline Complete![/bold green]\n")

        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Duration", f"{pipeline_meta.total_duration_seconds:.2f}s")
        table.add_row("Final Status", pipeline_meta.final_status.value)

        # Display stage status
        for stage in pipeline_meta.stages:
            status_icon = {
                StageStatus.SUCCESS: "✓",
                StageStatus.FAILED: "✗",
                StageStatus.RUNNING: "⏳",
                StageStatus.PENDING: "⏸️",
            }.get(stage.status, "?")

            table.add_row(f"Stage: {stage.name}", f"{status_icon} {stage.status.value}")
            if stage.duration_seconds:
                table.add_row(f"  Duration", f"{stage.duration_seconds:.2f}s")

        console.print(table)

        # Display voice samples information
        voice_samples_stage = pipeline_meta.get_stage("voice_samples")
        if voice_samples_stage and voice_samples_stage.status == StageStatus.SUCCESS:
            voice_samples_dir = output_dir / "voice_samples"
            if voice_samples_dir.exists():
                console.print("\n[bold]🎤 Voice Samples Extracted:[/bold]")

                # Count samples
                speaker_dirs = [
                    d
                    for d in voice_samples_dir.iterdir()
                    if d.is_dir() and d.name.startswith("SPEAKER_")
                ]

                samples_table = Table(show_header=True, box=None)
                samples_table.add_column("Speaker", style="cyan")
                samples_table.add_column("Audio File", style="green")
                samples_table.add_column("Duration", style="yellow")

                for speaker_dir in sorted(speaker_dirs):
                    audio_file = speaker_dir / "voice_sample.wav"
                    metadata_file = speaker_dir / "voice_sample.txt"

                    if audio_file.exists():
                        # Try to get duration from the file
                        try:
                            size_mb = audio_file.stat().st_size / (1024 * 1024)
                            duration_str = f"{size_mb:.1f} MB"

                            # Try to extract duration from metadata file
                            if metadata_file.exists():
                                with open(metadata_file, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    for line in content.split("\n"):
                                        if "时长:" in line:
                                            duration_str = line.split("时长:")[
                                                1
                                            ].strip()
                                            break

                            samples_table.add_row(
                                speaker_dir.name, "voice_sample.wav", duration_str
                            )
                        except Exception:
                            samples_table.add_row(
                                speaker_dir.name, "voice_sample.wav", "N/A"
                            )

                console.print(samples_table)
                console.print(
                    f"[dim]Location: {voice_samples_dir.relative_to(Path.cwd())}[/dim]"
                )

        # Display output files
        console.print("\n[bold]📁 Generated Files:[/bold]")
        files_table = Table(show_header=True, box=None)
        files_table.add_column("File", style="cyan")
        files_table.add_column("Size", style="yellow")

        for file_path in output_dir.glob("*"):
            if file_path.is_file():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                files_table.add_row(file_path.name, f"{size_mb:.2f} MB")

        console.print(files_table)
        console.print("\n" + "=" * 60 + "\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Pipeline interrupted by user[/yellow]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]❌ Pipeline failed: {e}[/bold red]")
        logger.exception("Pipeline error")
        raise typer.Exit(1)


@app.command()
def extract_samples(
    audio_file: Path = typer.Argument(
        ...,
        exists=True,
        help="Path to input audio file (mp3, wav, flac, m4a)",
    ),
    asr_result: Path = typer.Argument(
        ...,
        exists=True,
        help="Path to ASR result JSON file",
    ),
    output_dir: Path = typer.Option(
        Path("./voice_samples"),
        "--output",
        "-o",
        help="Output directory for voice samples (default: ./voice_samples)",
    ),
    min_duration: float = typer.Option(
        5.0,
        "--min-duration",
        help="Minimum sample duration in seconds (default: 5.0)",
    ),
    max_duration: float = typer.Option(
        20.0,
        "--max-duration",
        help="Maximum sample duration in seconds (default: 20.0)",
    ),
    min_quality: float = typer.Option(
        60.0,
        "--min-quality",
        help="Minimum quality score (0-100, default: 60.0)",
    ),
) -> None:
    """Extract voice cloning samples from ASR results.

    This command extracts the highest quality voice sample for each speaker
    from ASR results, optimized for voice cloning applications.

    For each speaker, it outputs:
    - WAV audio file (5-20 seconds, highest quality sample)
    - Detailed metadata text file with transcription and quality metrics

    Output structure:
        voice_samples/
        ├── SPEAKER_00/
        │   ├── voice_sample.wav    # Best audio sample
        │   └── voice_sample.txt    # Detailed description
        └── SPEAKER_01/
            ├── voice_sample.wav
            └── voice_sample.txt

    Example:
        podtrans extract-samples podcast.mp3 data/output/demo/asr_result.json

        podtrans extract-samples podcast.mp3 asr_result.json -o my_samples --min-quality 75

        podtrans extract-samples podcast.mp3 asr_result.json --min-duration 8 --max-duration 15
    """
    console.print("\n[bold blue]🎙️  PodTrans - Voice Sample Extraction[/bold blue]\n")
    console.print(f"[dim]Audio file:[/dim] {audio_file}")
    console.print(f"[dim]ASR result:[/dim] {asr_result}")
    console.print(f"[dim]Output directory:[/dim] {output_dir}")
    console.print(f"[dim]Duration range:[/dim] {min_duration}s - {max_duration}s")
    console.print(f"[dim]Min quality score:[/dim] {min_quality}\n")

    try:
        # Validate audio file
        if not validate_audio_file(audio_file):
            console.print("[bold red]❌ Invalid audio file[/bold red]")
            raise typer.Exit(1)

        # Load ASR result
        console.print("[dim]Loading ASR result...[/dim]")
        try:
            asr_data = read_json(asr_result)
            asr_result_obj = ASRResult.model_validate(asr_data)
        except Exception as e:
            console.print(f"[bold red]❌ Failed to load ASR result: {e}[/bold red]")
            raise typer.Exit(1)

        console.print(
            f"[green]✓[/green] ASR result loaded: {asr_result_obj.total_segments} segments, {asr_result_obj.speaker_count} speakers"
        )

        # Check if speaker diarization was performed
        if asr_result_obj.speaker_count == 0:
            console.print(
                "[yellow]⚠️  No speaker diarization found in ASR result[/yellow]"
            )
            console.print(
                "[yellow]   Voice samples will not be extracted without speaker labels[/yellow]"
            )
            raise typer.Exit(1)

        # Initialize WhisperX handler
        console.print("[dim]Initializing audio processor...[/dim]")
        handler = WhisperXHandler()

        # Extract voice samples
        console.print("[dim]Extracting voice samples...[/dim]")
        extraction_result = handler.extract_voice_samples(
            audio_path=audio_file,
            asr_result=asr_result_obj,
            min_duration=min_duration,
            max_duration=max_duration,
            min_quality=min_quality,
        )

        # Display results
        console.print("\n" + "=" * 60)
        console.print("[bold green]✨ Voice Sample Extraction Complete![/bold green]\n")

        # Summary table
        table = Table(
            title="Extraction Summary", show_header=True, header_style="bold cyan"
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Speakers", str(extraction_result.total_speakers))
        table.add_row("Samples Extracted", str(extraction_result.total_samples))
        table.add_row(
            "Success Rate",
            f"{extraction_result.extraction_summary['success_rate']:.1%}",
        )
        table.add_row(
            "Average Quality",
            f"{extraction_result.extraction_summary['average_quality']:.1f}/100",
        )
        table.add_row(
            "Average Duration",
            f"{extraction_result.extraction_summary['average_duration']:.1f}s",
        )

        console.print(table)

        if extraction_result.speaker_samples:
            console.print("\n[bold]Extracted Samples:[/bold]\n")

            # Samples table
            samples_table = Table(show_header=True, header_style="bold cyan")
            samples_table.add_column("Speaker", style="cyan")
            samples_table.add_column("Quality", style="green")
            samples_table.add_column("Duration", style="yellow")
            samples_table.add_column("Words", style="white")
            samples_table.add_column("Recommendation", style="magenta")

            for speaker_id, sample in extraction_result.speaker_samples.items():
                quality_color = (
                    "green"
                    if sample.quality_score >= 80
                    else "yellow"
                    if sample.quality_score >= 60
                    else "red"
                )
                samples_table.add_row(
                    speaker_id,
                    f"[{quality_color}]{sample.quality_score:.0f}/100[/{quality_color}]",
                    f"{sample.duration:.1f}s",
                    str(sample.words_count),
                    sample.recommended_use[:30] + "..."
                    if len(sample.recommended_use) > 30
                    else sample.recommended_use,
                )

            console.print(samples_table)

            console.print(f"\n[bold]Output Directory:[/bold] {output_dir.absolute()}")
            console.print("[dim]Each speaker folder contains:[/dim]")
            console.print("[dim]  • voice_sample.wav - Audio file[/dim]")
            console.print("[dim]  • voice_sample.txt - Detailed metadata[/dim]")

        else:
            console.print("[yellow]⚠️  No voice samples extracted[/yellow]")
            console.print(
                "[yellow]   Try adjusting the quality thresholds or duration limits[/yellow]"
            )

        # Save extraction summary
        summary_file = output_dir / "extraction_summary.json"
        extraction_summary = {
            "extraction_time": extraction_result.extraction_time.isoformat(),
            "source_audio": str(audio_file),
            "source_asr_result": str(asr_result),
            "parameters": {
                "min_duration": min_duration,
                "max_duration": max_duration,
                "min_quality": min_quality,
            },
            "summary": extraction_result.extraction_summary,
            "samples": {
                speaker_id: {
                    "quality_score": sample.quality_score,
                    "duration": sample.duration,
                    "words_count": sample.words_count,
                    "recommended_use": sample.recommended_use,
                    "audio_path": str(sample.audio_path),
                }
                for speaker_id, sample in extraction_result.speaker_samples.items()
            },
        }

        try:
            write_json(extraction_summary, summary_file, indent=2)
            console.print(
                f"[green]✓[/green] Extraction summary saved to: {summary_file}"
            )
        except Exception as e:
            console.print(f"[yellow]⚠️  Failed to save summary: {e}[/yellow]")

        console.print("\n" + "=" * 60 + "\n")
        console.print(
            "[bold green]Voice samples are ready for cloning! 🎤[/bold green]"
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Extraction interrupted by user[/yellow]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]❌ Voice sample extraction failed: {e}[/bold red]")
        logger.exception("Voice sample extraction error")
        raise typer.Exit(1)


@app.command()
def rss(
    rss_url: str = typer.Argument(
        ...,
        help="RSS feed URL to fetch podcast episodes from",
    ),
    count: int = typer.Option(
        1,
        "--count",
        "-c",
        help="Number of latest episodes to download (default: 1)",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: data/output/rss_{timestamp})",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="Language code for ASR (e.g., 'en', 'zh'). Auto-detect if not specified",
    ),
    source_lang: str = typer.Option(
        "en",
        "--source",
        "-s",
        help="Source language for translation",
    ),
    target_lang: str = typer.Option(
        "zh",
        "--target",
        "-t",
        help="Target language for translation",
    ),
    no_diarization: bool = typer.Option(
        False,
        "--no-diarization",
        help="Disable speaker diarization",
    ),
    no_voice_samples: bool = typer.Option(
        False,
        "--no-voice-samples",
        help="Disable voice sample extraction",
    ),
    keep_downloads: bool = typer.Option(
        False,
        "--keep-downloads",
        help="Keep downloaded audio files after processing",
    ),
    max_segment_duration: float | None = typer.Option(
        None,
        "--max-segment-duration",
        help="Maximum duration per audio segment in seconds (default: from config)",
    ),
    no_segmentation: bool = typer.Option(
        False,
        "--no-segmentation",
        help="Disable automatic audio segmentation for long episodes",
    ),
    min_sample_duration: float | None = typer.Option(
        None,
        "--min-sample-duration",
        help="Minimum voice sample duration in seconds (default: from config)",
    ),
    max_sample_duration: float | None = typer.Option(
        None,
        "--max-sample-duration",
        help="Maximum voice sample duration in seconds (default: from config)",
    ),
    min_sample_quality: float | None = typer.Option(
        None,
        "--min-sample-quality",
        help="Minimum voice sample quality score (0-100, default: from config)",
    ),
) -> None:
    """Fetch and process podcast episodes from RSS feeds.

    This command automates the complete podcast translation workflow:
    1. Parse RSS feed and fetch episode information
    2. Download audio files for latest episodes
    3. Run complete pipeline (ASR → Voice Samples → Translation → TTS)

    Examples:
        # Process latest episode from RSS feed
        podtrans rss https://feeds.simplecast.com/your-podcast

        # Process 3 latest episodes
        podtrans rss https://example.com/feed.xml --count 3

        # Custom output directory and languages
        podtrans rss https://feeds.example.com/podcast -o ./results -s en -t zh

        # Disable voice samples and keep downloads
        podtrans rss https://feeds.example.com/podcast --no-voice-samples --keep-downloads
    """
    import time
    import shutil
    from pathlib import Path

    from podtrans.rss.fetcher import RSSFetcher
    from podtrans.rss.downloader import AudioDownloader
    from podtrans.utils.file import write_json

    settings = get_settings()
    start_time = time.time()

    # Display header
    console.print("\n[bold blue]🎙️  PodTrans - RSS Processing[/bold blue]\n")
    console.print(f"[dim]RSS Feed:[/dim] {rss_url}")
    console.print(f"[dim]Episodes to process:[/dim] {count}")
    console.print(f"[dim]Translation:[/dim] {source_lang} → {target_lang}")
    console.print(f"[dim]Voice samples:[/dim] {'Disabled' if no_voice_samples else 'Enabled'}")
    console.print(f"[dim]Keep downloads:[/dim] {'Yes' if keep_downloads else 'No'}\n")

    # Validate RSS URL
    console.print("[bold cyan]📡 Validating RSS feed...[/bold cyan]")
    fetcher = RSSFetcher()
    if not fetcher.validate_feed_url(rss_url):
        console.print("[bold red]❌ Invalid RSS feed URL[/bold red]")
        raise typer.Exit(1)
    console.print("[green]✓[/green] RSS feed URL is valid\n")

    # Set up output directory
    if output is None:
        timestamp = int(time.time())
        output_dir = settings.output_dir / f"rss_{timestamp}"
    else:
        output_dir = Path(output)

    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Output directory:[/dim] {output_dir}\n")

    # Fetch RSS feed
    console.print("[bold cyan]📰 Fetching RSS feed...[/bold cyan]")
    try:
        rss_feed = fetcher.fetch_feed(rss_url, max_episodes=count)
        console.print(f"[green]✓[/green] Feed: {rss_feed.title}")
        console.print(f"[green]✓[/green] Episodes found: {rss_feed.total_episodes}")
        console.print(f"[green]✓[/green] Episodes to process: {len(rss_feed.episodes)}\n")
    except Exception as e:
        console.print(f"[bold red]❌ Failed to fetch RSS feed: {e}[/bold red]")
        logger.exception("RSS fetch error")
        raise typer.Exit(1)

    if not rss_feed.episodes:
        console.print("[yellow]⚠️  No episodes found in RSS feed[/yellow]")
        raise typer.Exit(0)

    # Download episodes
    download_dir = settings.rss_download_dir / f"rss_{int(time.time())}"
    downloader = AudioDownloader()
    downloaded_files = []
    failed_episodes = []

    console.print("[bold cyan]⬇️  Downloading episodes...[/bold cyan]")
    try:
        downloaded_files = downloader.download_episodes(rss_feed.episodes, download_dir)
        console.print(f"[green]✓[/green] Downloaded: {len(downloaded_files)} files")

        if failed_episodes := len(rss_feed.episodes) - len(downloaded_files):
            console.print(f"[yellow]⚠️  Failed: {failed_episodes} files[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Download failed: {e}[/bold red]")
        logger.exception("Download error")
        raise typer.Exit(1)

    if not downloaded_files:
        console.print("[bold red]❌ No episodes downloaded successfully[/bold red]")
        raise typer.Exit(1)

    # Create cache directory for simple filenames
    cache_dir = settings.rss_cache_dir / f"rss_{int(time.time())}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Copy downloaded files to cache with simple names
    cached_files = []
    for i, downloaded_file in enumerate(downloaded_files):
        # Create simple filename: episode_001.mp3, episode_002.mp3, etc.
        simple_name = f"episode_{i+1:03d}.mp3"
        cached_file = cache_dir / simple_name

        # Copy file
        import shutil
        shutil.copy2(downloaded_file, cached_file)
        cached_files.append(cached_file)

        logger.info(f"Cached {downloaded_file} -> {cached_file}")

    # Apply audio segmentation if enabled
    final_processing_files = []

    if no_segmentation or not settings.audio_segment_enabled:
        # No segmentation
        final_processing_files = cached_files
        console.print("[dim]Audio segmentation: disabled[/dim]")
    else:
        # Apply audio segmentation
        segment_duration = max_segment_duration or settings.audio_segment_max_duration
        console.print(f"[dim]Audio segmentation: enabled (max {segment_duration}s per segment)[/dim]")

        from podtrans.utils.audio_segmenter import split_long_audio

        for i, cached_file in enumerate(cached_files):
            console.print(f"[blue]🔍 Checking {cached_file.name} for segmentation...[/blue]")

            try:
                # Create segment directory for this episode
                episode_segment_dir = cache_dir / f"episode_{i+1:03d}_segments"
                episode_segment_dir.mkdir(exist_ok=True)

                # Split if needed
                segment_files = split_long_audio(cached_file, episode_segment_dir, segment_duration)
                final_processing_files.extend(segment_files)

                if len(segment_files) > 1:
                    console.print(f"[green]   ✓ Split into {len(segment_files)} segments[/green]")
                else:
                    console.print(f"[dim]   ✓ No segmentation needed[/dim]")

            except Exception as e:
                console.print(f"[yellow]⚠️  Segmentation failed for {cached_file.name}: {e}[/yellow]")
                # Fall back to original file
                final_processing_files.append(cached_file)

    processing_files = final_processing_files
    console.print(f"[dim]Total files to process: {len(processing_files)}[/dim]\n")

    # Process each episode/segment
    processed_episodes = []
    failed_processing = []

    # Create episode -> segments mapping
    episode_segments = {}  # episode_index -> [segment_files]

    for file_index, audio_path in enumerate(processing_files):
        # Determine which episode this file belongs to
        episode_index = 0
        is_segment = False

        # Check if this is a segment file
        if "segments" in str(audio_path) and "_part_" in str(audio_path):
            # Extract episode number from path like "episode_001_segments/episode_001_part_001.mp3"
            import re
            match = re.search(r'episode_(\d+)_segments', str(audio_path))
            if match:
                episode_index = int(match.group(1)) - 1  # Convert to 0-based
                is_segment = True
            else:
                # Fallback: try to get episode from filename prefix
                match = re.search(r'episode_(\d+)_part_(\d+)', audio_path.name)
                if match:
                    episode_index = int(match.group(1)) - 1
                    is_segment = True
        else:
            # This is a non-segmented episode file
            if file_index < len(cached_files):
                episode_index = file_index
            else:
                episode_index = 0  # Default to first episode

        # Ensure episode_index is within bounds
        episode_index = min(episode_index, len(rss_feed.episodes) - 1)

        # Add to episode segments mapping
        if episode_index not in episode_segments:
            episode_segments[episode_index] = []
        episode_segments[episode_index].append(audio_path)

    # Process each episode and all its segments
    for episode_index, segment_files in episode_segments.items():
        episode = rss_feed.episodes[episode_index]

        console.print(f"[bold cyan]🔄 Processing episode {episode_index + 1}/{len(rss_feed.episodes)}:[/bold cyan] {episode.title}")
        if len(segment_files) > 1:
            console.print(f"[dim]   Split into {len(segment_files)} segments[/dim]")

        # Create episode-specific output directory
        simple_name = f"episode_{episode_index + 1:03d}"
        episode_dir = output_dir / simple_name
        episode_dir.mkdir(parents=True, exist_ok=True)

        # Process all segments for this episode
        episode_success = True
        all_pipeline_results = []

        for segment_index, audio_path in enumerate(segment_files):
            if len(segment_files) > 1:
                console.print(f"[blue]   → Segment {segment_index + 1}/{len(segment_files)}[/blue]")

            try:
                # Run pipeline orchestrator with cached file (simple filename!)
                orchestrator = PipelineOrchestrator(episode_dir)
                pipeline_meta = asyncio.run(
                    orchestrator.run_pipeline(
                        audio_path=audio_path,  # Now uses simple cached filename
                        language=language,
                        enable_diarization=not no_diarization,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        extract_voice_samples=False
                        if no_voice_samples
                        else None,  # Use config default if not disabled
                        min_duration=min_sample_duration,
                        max_duration=max_sample_duration,
                        min_quality=min_sample_quality,
                    )
                )
                all_pipeline_results.append(pipeline_meta)

            except Exception as e:
                console.print(f"  [red]✗[/red] Segment {segment_index + 1} failed: {e}")
                episode_success = False
                logger.exception(f"Segment processing failed for {audio_path}: {e}")

        if episode_success and all_pipeline_results:
            processed_episodes.append({
                'episode_title': episode.title,
                'episode_description': episode.description,
                'audio_url': episode.audio_url,
                'duration': episode.duration,
                'output_dir': str(episode_dir),
                'segments_count': len(segment_files),
                'pipeline_metadata': [meta.model_dump() for meta in all_pipeline_results],
            })
            console.print(f"  [green]✓[/green] Processing complete")
        else:
            failed_processing.append({
                'episode_title': episode.title,
                'error': "One or more segments failed",
            })

        console.print()

    # Clean up downloads if requested
    if not keep_downloads and download_dir.exists():
        try:
            shutil.rmtree(download_dir)
            console.print(f"[dim]Cleaned up download directory: {download_dir}[/dim]\n")
        except Exception as e:
            console.print(f"[yellow]⚠️  Failed to clean up downloads: {e}[/yellow]\n")

    # Create processing result summary
    total_time = time.time() - start_time
    success_rate = (len(processed_episodes) / len(rss_feed.episodes)) * 100 if rss_feed.episodes else 0

    processing_result = {
        'feed_url': rss_url,
        'feed_title': rss_feed.title,
        'feed_description': rss_feed.description,
        'episodes_requested': count,
        'episodes_found': rss_feed.total_episodes,
        'episodes_downloaded': len(downloaded_files),
        'episodes_processed': len(processed_episodes),
        'episodes_failed': len(failed_processing),
        'success_rate': success_rate,
        'processing_time_seconds': total_time,
        'output_directory': str(output_dir),
        'settings': {
            'source_lang': source_lang,
            'target_lang': target_lang,
            'voice_samples_enabled': not no_voice_samples,
            'keep_downloads': keep_downloads,
        },
        'processed_episodes': processed_episodes,
        'failed_episodes': failed_processing,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    # Save processing results
    results_file = output_dir / "rss_processing_results.json"
    try:
        write_json(processing_result, results_file, indent=2)
        console.print(f"[green]✓[/green] Results saved to: {results_file}")
    except Exception as e:
        console.print(f"[yellow]⚠️  Failed to save results: {e}[/yellow]")

    # Display final summary
    console.print("\n" + "=" * 60)
    console.print("[bold green]✨ RSS Processing Complete![/bold green]\n")

    # Summary table
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Feed Title", rss_feed.title)
    table.add_row("Episodes Requested", str(count))
    table.add_row("Episodes Found", str(rss_feed.total_episodes))
    table.add_row("Episodes Downloaded", f"{len(downloaded_files)}/{len(rss_feed.episodes)}")
    table.add_row("Episodes Processed", f"{len(processed_episodes)}/{len(downloaded_files)}")
    table.add_row("Success Rate", f"{success_rate:.1f}%")
    table.add_row("Processing Time", f"{total_time:.1f} seconds")
    table.add_row("Output Directory", str(output_dir))

    console.print(table)

    if processed_episodes:
        console.print("\n[bold]📁 Processed Episodes:[/bold]")
        for i, episode in enumerate(processed_episodes, 1):
            console.print(f"  {i}. {episode['episode_title']}")
            console.print(f"     [dim]{episode['output_dir']}[/dim]")

    if failed_processing:
        console.print(f"\n[yellow]⚠️  Failed Episodes: {len(failed_processing)}[/yellow]")
        for episode in failed_processing:
            console.print(f"  • {episode['episode_title']}: {episode['error']}")

    # Audio merging for segmented outputs
    if processed_episodes:
        console.print("\n[bold]🔄 Checking for segmented audio outputs...[/bold]")

        try:
            from .utils.audio_merger import merge_segments_in_directory, create_episode_playlist

            merged_episodes = []

            for episode in processed_episodes:
                episode_output_dir = Path(episode['output_dir'])

                # Check if this episode has segmented TTS outputs
                segment_files = list(episode_output_dir.glob("**/segment_*_tts_output.wav"))

                if segment_files and len(segment_files) > 1:
                    console.print(f"[blue]🎵 Merging segments for: {episode['episode_title']}[/blue]")

                    # Merge segments for this episode
                    merged_files = merge_segments_in_directory(episode_output_dir)

                    if merged_files:
                        merged_episodes.extend(merged_files)
                        console.print(f"[green]✓ Merged {len(merged_files)} audio files[/green]")
                    else:
                        console.print(f"[yellow]⚠️  No segments found for merging[/yellow]")

            # Create playlist if we have merged files
            if merged_episodes:
                playlist_path = output_dir / "merged_episodes_playlist.m3u"
                create_episode_playlist(merged_episodes, playlist_path)
                console.print(f"\n[bold green]🎉 Audio merging complete![/bold green]")
                console.print(f"[green]📁 Playlist: {playlist_path}[/green]")

                # Display merged files info
                console.print("\n[bold]🎵 Merged Episodes:[/bold]")
                for i, merged_file in enumerate(merged_episodes, 1):
                    size_mb = merged_file.stat().st_size / (1024 * 1024)
                    console.print(f"  {i}. {merged_file.name} ({size_mb:.1f} MB)")

        except ImportError:
            console.print("[yellow]⚠️  Audio merging requires torchaudio, skipping...[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Audio merging failed: {e}[/yellow]")
            logger.warning(f"Audio merging failed: {e}")

    # Cleanup cache if not keeping downloads
    if not keep_downloads:
        try:
            # Remove cache directory
            import shutil
            shutil.rmtree(cache_dir)
            logger.info(f"Cleaned up cache directory: {cache_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up cache directory {cache_dir}: {e}")

    console.print("\n" + "=" * 60 + "\n")


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
