"""Command-line interface for PodTrans.

This module provides the CLI commands using Typer.
"""

from pathlib import Path
import asyncio
from datetime import datetime

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
from podtrans.tts.factory import create_tts_service, create_simple_tts_service
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
def rss(
    rss_url: str = typer.Argument(
        None,
        help="RSS feed URL (optional if using config file)",
    ),
    data_dir: Path = typer.Option(
        Path("./data"),
        "--data-dir",
        "-d",
        help="Data directory path",
    ),
    config: Path = typer.Option(
        Path("./rss_config.toml"),
        "--config",
        "-c",
        help="RSS config file path",
    ),
    mode: str = typer.Option(
        "latest",
        "--mode",
        "-m",
        help="Download mode: 'latest' or 'all'",
    ),
    count: int = typer.Option(
        1,
        "--count",
        "-n",
        help="Number of episodes to download (for 'latest' mode)",
    ),
) -> None:
    """Download podcast episodes from RSS feeds.

    This command downloads audio files from RSS feeds and saves them to the data directory.
    It only performs download, no ASR/translation processing.

    Use 'podtrans asr' after this to process downloaded episodes.
    Use 'podtrans status' to check progress.

    Examples:
        # Download from command line URL
        podtrans rss https://feeds.simplecast.com/your-podcast

        # Download from config file
        podtrans rss

        # Download latest 3 episodes
        podtrans rss https://example.com/feed.xml --count 3

        # Download all episodes
        podtrans rss https://example.com/feed.xml --mode all
    """
    from podtrans.rss import start_rss_processing

    console.print("\n[bold blue]📡 PodTrans - RSS Download[/bold blue]\n")

    if rss_url:
        console.print(f"[dim]RSS URL:[/dim] {rss_url}")
    else:
        console.print(f"[dim]Config:[/dim] {config}")

    console.print(f"[dim]Mode:[/dim] {mode}")
    console.print(f"[dim]Count:[/dim] {count if mode == 'latest' else 'all'}")
    console.print(f"[dim]Data dir:[/dim] {data_dir}\n")

    try:
        # Run RSS processing
        success = asyncio.run(
            start_rss_processing(
                rss_url=rss_url,
                data_dir=str(data_dir),
                config_path=str(config),
                download_mode=mode,
                download_count=count,
            )
        )

        if success:
            console.print("\n[bold green]✅ RSS download completed![/bold green]")
            console.print("[dim]Run 'podtrans asr' to process downloaded episodes[/dim]")
            console.print("[dim]Run 'podtrans status' to check progress[/dim]\n")
        else:
            console.print("\n[bold red]❌ RSS download failed[/bold red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]❌ RSS download error: {e}[/bold red]")
        logger.exception("RSS download error")
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


def _create_episode_summary(
    episode_dir: Path,
    episode,
    segment_files: list[Path],
    pipeline_results: list
) -> None:
    """Create episode summary JSON with all segments information.

    Args:
        episode_dir: Episode directory path
        episode: Episode metadata object
        segment_files: List of segment audio file paths
        pipeline_results: List of pipeline metadata for each segment
    """
    import json
    from datetime import datetime

    # Calculate total duration from segment files
    total_duration = 0
    segment_info = []

    for i, (segment_file, pipeline_meta) in enumerate(zip(segment_files, pipeline_results)):
        # Get segment info from pipeline metadata
        segment_id = f"{episode_dir.name}_part_{i+1:03d}"
        segment_dir = episode_dir / segment_id

        # Count speakers and segments from ASR result
        asr_stage = pipeline_meta.get_stage("asr")
        speaker_count = asr_stage.speakers if asr_stage else 0
        segment_count = asr_stage.segments if asr_stage else 0

        # Get file size
        segment_size = segment_file.stat().st_size if segment_file.exists() else 0
        total_duration += pipeline_meta.audio_duration or 0

        segment_info.append({
            "segment_id": segment_id,
            "segment_index": i + 1,
            "audio_file": segment_file.name,
            "file_size": segment_size,
            "duration": pipeline_meta.audio_duration,
            "speakers": speaker_count,
            "segments": segment_count,
            "status": "completed"
        })

    # Create episode summary
    episode_summary = {
        "episode_id": episode_dir.name,
        "title": episode.title,
        "description": episode.description,
        "audio_url": episode.audio_url,
        "processing_time": datetime.now().isoformat(),
        "total_segments": len(segment_files),
        "total_duration": total_duration,
        "total_size": sum(seg["file_size"] for seg in segment_info),
        "segments": segment_info,
        "processing_status": "completed" if len(segment_files) == len(pipeline_results) else "partial"
    }

    # Save to episode directory
    summary_file = episode_dir / "episode_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(episode_summary, f, ensure_ascii=False, indent=2)

    logger.info(f"Episode summary saved to {summary_file}")


@app.command()
def asr(
    data_dir: Path = typer.Option(
        Path("./data"),
        "--data-dir",
        "-d",
        help="Data directory path",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        help="Maximum retry count for failed episodes",
    ),
) -> None:
    """Batch process ASR for all downloaded episodes.

    This command:
    - Queries database for episodes with download_completed=True and asr_completed=False
    - Processes each episode with WhisperX ASR
    - Saves results to episode directory
    - Updates database with completion status

    Example:
        podtrans asr
        podtrans asr --data-dir ./data --max-retries 5
    """
    from podtrans.services.database import DatabaseManager

    console.print("\n[bold blue]🎙️  PodTrans - Batch ASR Processing[/bold blue]\n")

    # Initialize database
    db_path = data_dir / "episodes.db"
    if not db_path.exists():
        console.print(f"[bold red]❌ Database not found: {db_path}[/bold red]")
        raise typer.Exit(1)

    db = DatabaseManager(db_path, init_db=False)

    # Query pending episodes
    episodes = db.get_pending_episodes(stage='asr')

    # Filter by retry count
    episodes = [ep for ep in episodes if ep.get('retry_count', 0) < max_retries]

    if not episodes:
        console.print("[green]✅ No episodes pending for ASR processing[/green]")
        return

    console.print(f"[cyan]Found {len(episodes)} episodes to process[/cyan]\n")

    # Initialize ASR handler
    settings = get_settings()
    handler = WhisperXHandler(
        model_name=settings.whisper_model,
        device=settings.device,
        compute_type=settings.compute_type,
        hf_token=settings.hf_token,
    )

    success_count = 0
    failed_count = 0

    # Process each episode
    for idx, episode in enumerate(episodes, 1):
        episode_id = episode['id']
        episode_title = episode['episode_title']
        audio_path = Path(episode['audio_path'])
        episode_dir = Path(episode['episode_dir'])

        console.print(f"[bold]Processing [{idx}/{len(episodes)}][/bold]: {episode_title}")
        console.print(f"[dim]Audio: {audio_path}[/dim]")

        try:
            # Check if audio file exists
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Process ASR
            logger.info(f"开始ASR处理: {episode_title}")
            asr_result = handler.process_full_pipeline(
                audio_path=audio_path,
                language=None,  # Auto-detect
                enable_diarization=True,
            )

            # Save result
            result_path = episode_dir / "asr_result.json"
            write_json(asr_result.model_dump(), result_path)

            # Update database
            db.update_episode_status(episode_id, {
                'asr_completed': True,
                'asr_result_path': str(result_path),
                'asr_timestamp': datetime.now(),
                'retry_count': 0,  # Reset retry count on success
            })

            success_count += 1
            console.print(f"[green]✅ Success[/green]: {result_path}\n")
            logger.info(f"ASR处理成功: {episode_title}")

        except Exception as e:
            failed_count += 1
            error_msg = str(e)

            # Update database with error
            current_retry = episode.get('retry_count', 0)
            db.update_episode_status(episode_id, {
                'retry_count': current_retry + 1,
                'error_count': episode.get('error_count', 0) + 1,
                'last_error': error_msg,
            })

            console.print(f"[red]❌ Failed[/red]: {error_msg}\n")
            logger.error(f"ASR处理失败: {episode_title}: {error_msg}")

    # Print summary
    console.print("\n" + "="*50)
    console.print(f"[bold]Processing Summary[/bold]")
    console.print(f"  Total: {len(episodes)}")
    console.print(f"  [green]Success: {success_count}[/green]")
    console.print(f"  [red]Failed: {failed_count}[/red]")
    console.print("="*50 + "\n")


def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def _render_status_display(data_dir: Path, show_episodes: bool = False) -> None:
    """渲染状态显示（用于刷新）"""
    import sqlite3
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.layout import Layout
    from rich.live import Live

    db_path = data_dir / "episodes.db"
    if not db_path.exists():
        console.print(f"[bold red]❌ Database not found: {db_path}[/bold red]")
        console.print(f"[dim]Run 'podtrans rss' first to download episodes[/dim]\n")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 获取所有剧集
    all_episodes = conn.execute("""
        SELECT * FROM episodes
        ORDER BY created_at DESC
    """).fetchall()

    # 统计数据
    total = len(all_episodes)
    download_done = sum(1 for ep in all_episodes if ep['download_completed'])
    asr_done = sum(1 for ep in all_episodes if ep['asr_completed'])
    trans_done = sum(1 for ep in all_episodes if ep['translation_completed'])
    tts_done = sum(1 for ep in all_episodes if ep['tts_completed'])

    # 计算总文件大小
    total_size = sum(ep['file_size'] or 0 for ep in all_episodes)

    # 统计错误
    error_count = sum(1 for ep in all_episodes if ep['last_error'])

    conn.close()

    # 清屏效果
    console.clear()

    # 标题
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"\n[bold blue]📊 PodTrans Status[/bold blue]  [dim]{now}[/dim]\n")

    # 总览表格
    overview_table = Table(show_header=False, box=None, padding=(0, 2))
    overview_table.add_column("Label", style="dim")
    overview_table.add_column("Value", style="bold")

    overview_table.add_row("Total Episodes", str(total))
    overview_table.add_row("Total Size", _format_file_size(total_size))
    overview_table.add_row("Errors", f"[red]{error_count}[/red]" if error_count else "[green]0[/green]")

    console.print(overview_table)
    console.print()

    # 进度条显示
    if total > 0:
        console.print("[bold]Pipeline Progress[/bold]\n")

        # 手动绘制进度条
        stages = [
            ("Download", download_done, "green"),
            ("ASR", asr_done, "cyan"),
            ("Translation", trans_done, "yellow"),
            ("TTS", tts_done, "magenta"),
        ]

        for stage_name, completed, color in stages:
            pct = (completed / total) * 100 if total > 0 else 0
            bar_width = 30
            filled = int(bar_width * completed / total) if total > 0 else 0
            bar = "█" * filled + "░" * (bar_width - filled)
            console.print(f"  {stage_name:12} [{color}]{bar}[/{color}] {completed}/{total} ({pct:.0f}%)")

        console.print()

    # 剧集列表
    if show_episodes and all_episodes:
        console.print("[bold]Episodes[/bold]\n")

        ep_table = Table(show_header=True, header_style="bold", box=None)
        ep_table.add_column("#", style="dim", width=3)
        ep_table.add_column("Title", style="white", max_width=40, overflow="ellipsis")
        ep_table.add_column("Size", style="cyan", justify="right", width=10)
        ep_table.add_column("Status", width=20)
        ep_table.add_column("Updated", style="dim", width=16)

        for idx, ep in enumerate(all_episodes[:10], 1):  # 只显示最近10个
            # 状态图标
            d = "✅" if ep['download_completed'] else "⏳"
            a = "✅" if ep['asr_completed'] else ("⏳" if ep['download_completed'] else "⬜")
            t = "✅" if ep['translation_completed'] else ("⏳" if ep['asr_completed'] else "⬜")
            s = "✅" if ep['tts_completed'] else ("⏳" if ep['translation_completed'] else "⬜")

            status_str = f"{d}→{a}→{t}→{s}"

            # 如果有错误，添加红色标记
            if ep['last_error']:
                status_str += " [red]⚠[/red]"

            # 文件大小
            size_str = _format_file_size(ep['file_size']) if ep['file_size'] else "-"

            # 更新时间
            updated = ep['updated_at'][:16] if ep['updated_at'] else "-"

            # 标题截断
            title = ep['episode_title']
            if len(title) > 40:
                title = title[:37] + "..."

            ep_table.add_row(str(idx), title, size_str, status_str, updated)

        console.print(ep_table)

        if len(all_episodes) > 10:
            console.print(f"\n[dim]... and {len(all_episodes) - 10} more episodes[/dim]")

    console.print()

    # 错误详情
    errors = [ep for ep in all_episodes if ep['last_error']]
    if errors:
        console.print(f"[bold red]Errors ({len(errors)})[/bold red]\n")
        for ep in errors[:3]:  # 只显示最近3个错误
            console.print(f"  [red]•[/red] {ep['episode_title'][:50]}")
            console.print(f"    [dim]{ep['last_error'][:80]}[/dim]")
        if len(errors) > 3:
            console.print(f"\n[dim]  ... and {len(errors) - 3} more errors[/dim]")
        console.print()


@app.command()
def status(
    data_dir: Path = typer.Option(
        Path("./data"),
        "--data-dir",
        "-d",
        help="Data directory path",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        "-w",
        help="Auto-refresh every 2 seconds",
    ),
    interval: float = typer.Option(
        2.0,
        "--interval",
        "-i",
        help="Refresh interval in seconds (default: 2)",
    ),
    episodes: bool = typer.Option(
        True,
        "--episodes/--no-episodes",
        "-e/-E",
        help="Show episode list (default: yes)",
    ),
) -> None:
    """Show pipeline processing status.

    Displays real-time progress of podcast processing pipeline.

    Example:
        podtrans status              # 显示状态
        podtrans status -w           # 自动刷新模式
        podtrans status -w -i 5      # 每5秒刷新
        podtrans status --no-episodes # 不显示剧集列表
    """
    import time

    if watch:
        console.print("[dim]Press Ctrl+C to exit watch mode[/dim]\n")
        try:
            while True:
                _render_status_display(data_dir, show_episodes=episodes)
                console.print(f"[dim]Refreshing every {interval}s... (Ctrl+C to exit)[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped watching[/dim]")
    else:
        _render_status_display(data_dir, show_episodes=episodes)


@app.callback()
def main() -> None:
    """PodTrans - AI-powered podcast translation pipeline.

    Translate English podcasts to Chinese while preserving speaker information.
    """
    pass


if __name__ == "__main__":
    app()
