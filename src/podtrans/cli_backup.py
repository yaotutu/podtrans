"""Command-line interface for PodTrans.

This module provides the CLI commands using Typer.
"""

from datetime import datetime
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from podtrans.asr import WhisperXHandler
from podtrans.config import get_settings
from podtrans.translation import Translator
from podtrans.translation.schemas import TranslationResult
from podtrans.utils.file import read_json, write_json

app = typer.Typer(
    name="podtrans",
    help="AI-powered podcast translation pipeline",
    add_completion=False,
)
console = Console()



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

    This command downloads audio files from RSS feeds and saves them to the
    data directory. It only performs download, no ASR/translation processing.

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
            console.print(
                "[dim]Run 'podtrans asr' to process downloaded episodes[/dim]"
            )
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
    episode_dir: Path, episode, segment_files: list[Path], pipeline_results: list
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

    for i, (segment_file, pipeline_meta) in enumerate(
        zip(segment_files, pipeline_results, strict=True)
    ):
        # Get segment info from pipeline metadata
        segment_id = f"{episode_dir.name}_part_{i + 1:03d}"

        # Count speakers and segments from ASR result
        asr_stage = pipeline_meta.get_stage("asr")
        speaker_count = asr_stage.speakers if asr_stage else 0
        segment_count = asr_stage.segments if asr_stage else 0

        # Get file size
        segment_size = segment_file.stat().st_size if segment_file.exists() else 0
        total_duration += pipeline_meta.audio_duration or 0

        segment_info.append(
            {
                "segment_id": segment_id,
                "segment_index": i + 1,
                "audio_file": segment_file.name,
                "file_size": segment_size,
                "duration": pipeline_meta.audio_duration,
                "speakers": speaker_count,
                "segments": segment_count,
                "status": "completed",
            }
        )

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
        "processing_status": "completed"
        if len(segment_files) == len(pipeline_results)
        else "partial",
    }

    # Save to episode directory
    summary_file = episode_dir / "episode_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
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
    processed_ids: set[int] = set()  # Track processed episodes to avoid duplicates

    # Process episodes with dynamic query
    while True:
        # Query pending episodes each iteration
        episodes = db.get_pending_episodes(stage="asr")
        episodes = [
            ep
            for ep in episodes
            if ep.get("retry_count", 0) < max_retries and ep["id"] not in processed_ids
        ]

        if not episodes:
            if success_count == 0 and failed_count == 0:
                console.print(
                    "[green]✅ No episodes pending for ASR processing[/green]"
                )
            break

        episode = episodes[0]
        processed_ids.add(episode["id"])

        episode_id = episode["id"]
        episode_title = episode["episode_title"]
        audio_path = Path(episode["audio_path"])
        episode_dir = Path(episode["episode_dir"])

        total_pending = len(episodes)
        console.print(
            f"[bold]Processing[/bold] (pending: {total_pending}): {episode_title}"
        )
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

            # Extract voice samples for each speaker
            from podtrans.asr.voice_sample import VoiceSampleExtractor

            console.print("[dim]Extracting voice samples...[/dim]")
            extractor = VoiceSampleExtractor()
            try:
                voice_result = extractor.extract_samples(
                    audio_path=audio_path,
                    asr_result=asr_result,
                    output_dir=episode_dir,
                )

                # Save voice samples metadata
                voice_samples_path = episode_dir / "voice_samples.json"
                write_json(voice_result.model_dump(), voice_samples_path)

                avg_q = voice_result.extraction_summary.get("average_quality", 0)
                console.print(
                    f"[dim]Voice samples: {voice_result.total_samples} samples, "
                    f"avg quality {avg_q:.1f}[/dim]"
                )
            except Exception as voice_err:
                logger.warning(f"声音样本提取失败: {voice_err}")
                console.print(
                    f"[yellow]⚠️  Voice sample extraction failed: {voice_err}[/yellow]"
                )

            # Update database
            db.update_episode_status(
                episode_id,
                {
                    "asr_completed": True,
                    "asr_result_path": str(result_path),
                    "asr_timestamp": datetime.now(),
                    "retry_count": 0,  # Reset retry count on success
                },
            )

            success_count += 1
            console.print(f"[green]✅ Success[/green]: {result_path}\n")
            logger.info(f"ASR处理成功: {episode_title}")

        except Exception as e:
            failed_count += 1
            error_msg = str(e)

            # Update database with error
            current_retry = episode.get("retry_count", 0)
            db.update_episode_status(
                episode_id,
                {
                    "retry_count": current_retry + 1,
                    "error_count": episode.get("error_count", 0) + 1,
                    "last_error": error_msg,
                },
            )

            console.print(f"[red]❌ Failed[/red]: {error_msg}\n")
            logger.error(f"ASR处理失败: {episode_title}: {error_msg}")

    # Print summary
    if success_count > 0 or failed_count > 0:
        console.print("\n" + "=" * 50)
        console.print("[bold]Processing Summary[/bold]")
        console.print(f"  Total: {success_count + failed_count}")
        console.print(f"  [green]Success: {success_count}[/green]")
        console.print(f"  [red]Failed: {failed_count}[/red]")
        console.print("=" * 50 + "\n")


@app.command()
def translation(
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
    """Batch process translation for all ASR-completed episodes.

    This command:
    - Queries database for episodes with asr_completed=True and
      translation_completed=False
    - Processes each episode with Qwen translation
    - Saves results to episode directory
    - Updates database with completion status

    Example:
        podtrans translation
        podtrans translation --data-dir ./data --max-retries 5
        podtrans translation -s en -t zh
    """
    from podtrans.services.database import DatabaseManager

    console.print("\n[bold blue]🌐 PodTrans - Batch Translation[/bold blue]\n")

    # Check API key
    settings = get_settings()
    if not settings.dashscope_api_key:
        console.print(
            "[bold red]❌ Error: DASHSCOPE_API_KEY not set[/bold red]\n"
            "[dim]Please set your DashScope API key in .env file:[/dim]\n"
            "DASHSCOPE_API_KEY=your_api_key_here\n"
        )
        raise typer.Exit(1)

    # Initialize database
    db_path = data_dir / "episodes.db"
    if not db_path.exists():
        console.print(f"[bold red]❌ Database not found: {db_path}[/bold red]")
        raise typer.Exit(1)

    db = DatabaseManager(db_path, init_db=False)

    console.print(f"[dim]Translation: {source_lang} → {target_lang}[/dim]\n")

    # Initialize translator
    console.print("[bold cyan]🔧 Initializing translator...[/bold cyan]")
    try:
        translator = Translator(settings)
        console.print(f"[green]✓[/green] Model: {translator.model}")
        console.print(f"[green]✓[/green] API base: {settings.translation_api_base}")
        console.print(
            f"[green]✓[/green] Max segments/batch: "
            f"{settings.translation_max_segments_per_batch}\n"
        )
    except Exception as e:
        console.print(f"[bold red]❌ Failed to initialize translator: {e}[/bold red]")
        raise typer.Exit(1)

    success_count = 0
    failed_count = 0
    processed_ids: set[int] = set()  # Track processed episodes to avoid duplicates

    # Process episodes with dynamic query
    while True:
        # Query pending episodes each iteration
        episodes = db.get_pending_episodes(stage="translation")
        episodes = [
            ep
            for ep in episodes
            if ep.get("retry_count", 0) < max_retries and ep["id"] not in processed_ids
        ]

        if not episodes:
            if success_count == 0 and failed_count == 0:
                console.print("[green]✅ No episodes pending for translation[/green]")
            break

        episode = episodes[0]
        processed_ids.add(episode["id"])

        episode_id = episode["id"]
        episode_title = episode["episode_title"]
        asr_result_path = Path(episode["asr_result_path"])
        episode_dir = Path(episode["episode_dir"])

        total_pending = len(episodes)
        console.print(
            f"[bold]Translating[/bold] (pending: {total_pending}): {episode_title}"
        )
        console.print(f"[dim]ASR result: {asr_result_path}[/dim]")

        try:
            # Check if ASR result file exists
            if not asr_result_path.exists():
                raise FileNotFoundError(f"ASR result not found: {asr_result_path}")

            # Load ASR result
            logger.info(f"开始翻译: {episode_title}")
            asr_result = translator.load_asr_result(asr_result_path)
            seg_count = asr_result.total_segments
            spk_count = asr_result.speaker_count
            console.print(f"[dim]Segments: {seg_count}, Speakers: {spk_count}[/dim]")

            # Translate
            translation_result = translator.translate_asr_result(
                asr_result, source_lang, target_lang
            )

            # Save result
            result_path = episode_dir / "translation_result"
            translator.save_result(
                translation_result,
                result_path,
                save_bilingual=True,
            )

            # Update database
            db.update_episode_status(
                episode_id,
                {
                    "translation_completed": True,
                    "translation_result_path": str(result_path.with_suffix(".json")),
                    "translation_timestamp": datetime.now(),
                    "retry_count": 0,  # Reset retry count on success
                },
            )

            success_count += 1
            console.print(f"[green]✅ Success[/green]: {result_path}.json\n")
            logger.info(f"翻译成功: {episode_title}")

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
            raise typer.Exit(1)

        except Exception as e:
            from podtrans.translation.translator import ContentBlockedError

            failed_count += 1

            # Check if it's a content blocked error
            if isinstance(e, ContentBlockedError):
                error_msg = f"[内容审核] {str(e)}"
                # Don't increment retry_count for content blocked errors
                # These need manual review, not retry
                db.update_episode_status(
                    episode_id,
                    {
                        "error_count": episode.get("error_count", 0) + 1,
                        "last_error": error_msg,
                    },
                )
                console.print(
                    "[yellow]⚠️  Content Blocked[/yellow]: "
                    "内容审核未通过，已标记等待人工处理\n"
                )
            else:
                error_msg = str(e)
                # Update database with error
                current_retry = episode.get("retry_count", 0)
                db.update_episode_status(
                    episode_id,
                    {
                        "retry_count": current_retry + 1,
                        "error_count": episode.get("error_count", 0) + 1,
                        "last_error": error_msg,
                    },
                )
                console.print(f"[red]❌ Failed[/red]: {error_msg}\n")

            logger.error(f"翻译失败: {episode_title}: {error_msg}")

    # Print summary
    if success_count > 0 or failed_count > 0:
        console.print("\n" + "=" * 50)
        console.print("[bold]Translation Summary[/bold]")
        console.print(f"  Total: {success_count + failed_count}")
        console.print(f"  [green]Success: {success_count}[/green]")
        console.print(f"  [red]Failed: {failed_count}[/red]")
        console.print("=" * 50 + "\n")


@app.command()
def tts(
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
    """Batch process TTS for all translated episodes.

    This command:
    - Queries database for episodes with translation_completed=True and
      tts_completed=False
    - Assembles SoulX input JSON from translation_result.json and voice_samples.json
    - Saves soulx_input.json for debugging
    - Calls SoulX to generate audio
    - Updates database with completion status

    Example:
        podtrans tts
        podtrans tts --data-dir ./data --max-retries 5
    """
    from podtrans.services.database import DatabaseManager
    from podtrans.tts.soulx.converter import SoulXConverter

    console.print("\n[bold blue]🎙️  PodTrans - Batch TTS Processing[/bold blue]\n")

    # Initialize database
    db_path = data_dir / "episodes.db"
    if not db_path.exists():
        console.print(f"[bold red]❌ Database not found: {db_path}[/bold red]")
        raise typer.Exit(1)

    db = DatabaseManager(db_path, init_db=False)

    # Initialize converter
    converter = SoulXConverter()

    console.print("[bold cyan]📋 TTS command will only generate soulx_input.json[/bold cyan]")
    console.print("[yellow]No external TTS service will be called[/yellow]\n")

    success_count = 0
    failed_count = 0
    processed_ids: set[int] = set()

    # Process episodes with dynamic query
    while True:
        # Query pending episodes each iteration
        episodes = db.get_pending_episodes(stage="tts")
        episodes = [
            ep
            for ep in episodes
            if ep.get("retry_count", 0) < max_retries and ep["id"] not in processed_ids
        ]

        if not episodes:
            if success_count == 0 and failed_count == 0:
                console.print("[green]✅ No episodes pending for TTS[/green]")
            break

        episode = episodes[0]
        processed_ids.add(episode["id"])

        episode_id = episode["id"]
        episode_title = episode["episode_title"]
        episode_dir = Path(episode["episode_dir"])

        total_pending = len(episodes)
        console.print(
            f"[bold]Processing TTS[/bold] (pending: {total_pending}): {episode_title}"
        )

        try:
            # Check required files
            translation_path = episode_dir / "translation_result.json"
            voice_samples_path = episode_dir / "voice_samples.json"

            if not translation_path.exists():
                raise FileNotFoundError(f"Translation not found: {translation_path}")

            if not voice_samples_path.exists():
                console.print(
                    "[yellow]⚠️  voice_samples.json not found, "
                    "TTS will use default voices[/yellow]"
                )
                voice_samples_path = None

            # 使用简化的转换器直接从文件转换
            logger.info(f"开始TTS处理: {episode_title}")
            console.print("[dim]Converting to SoulX format...[/dim]")

            # converter 会自动处理所有逻辑
            soulx_input = converter.convert_from_file(translation_path)

            # 获取统计信息
            seg_count = len(soulx_input.get("text", []))
            spk_count = len(soulx_input.get("speakers", {}))
            console.print(f"[dim]Segments: {seg_count}, Speakers: {spk_count}[/dim]")

            # Save soulx_input.json for debugging
            soulx_input_path = episode_dir / "soulx_input.json"
            write_json(soulx_input, soulx_input_path)
            console.print(f"[green]✓[/green] Saved: {soulx_input_path}")

            # TTS command now only generates soulx_input.json
            # No external TTS service is called
            console.print("[yellow]Note: TTS command only generates soulx_input.json[/yellow]")
            console.print("[yellow]To synthesize audio, run: soulx-podcast --json_path soulx_input.json[/yellow]")

            # Update database
            db.update_episode_status(
                episode_id,
                {
                    "tts_completed": True,
                    "tts_soulx_input_path": str(soulx_input_path),
                    "tts_timestamp": datetime.now(),
                    "retry_count": 0,
                },
            )

            success_count += 1
            console.print(f"[green]✅ Success[/green]: {soulx_input_path}\n")
            logger.info(f"TTS处理成功: {episode_title}")

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
            raise typer.Exit(1)

        except Exception as e:
            failed_count += 1
            error_msg = str(e)

            # Update database with error
            current_retry = episode.get("retry_count", 0)
            db.update_episode_status(
                episode_id,
                {
                    "retry_count": current_retry + 1,
                    "error_count": episode.get("error_count", 0) + 1,
                    "last_error": error_msg,
                },
            )

            console.print(f"[red]❌ Failed[/red]: {error_msg}\n")
            logger.error(f"TTS处理失败: {episode_title}: {error_msg}")

    # Print summary
    if success_count > 0 or failed_count > 0:
        console.print("\n" + "=" * 50)
        console.print("[bold]TTS Summary[/bold]")
        console.print(f"  Total: {success_count + failed_count}")
        console.print(f"  [green]Success: {success_count}[/green]")
        console.print(f"  [red]Failed: {failed_count}[/red]")
        console.print("=" * 50 + "\n")


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

    db_path = data_dir / "episodes.db"
    if not db_path.exists():
        console.print(f"[bold red]❌ Database not found: {db_path}[/bold red]")
        console.print("[dim]Run 'podtrans rss' first to download episodes[/dim]\n")
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
    download_done = sum(1 for ep in all_episodes if ep["download_completed"])
    asr_done = sum(1 for ep in all_episodes if ep["asr_completed"])
    trans_done = sum(1 for ep in all_episodes if ep["translation_completed"])
    tts_done = sum(1 for ep in all_episodes if ep["tts_completed"])

    # 计算总文件大小
    total_size = sum(ep["file_size"] or 0 for ep in all_episodes)

    # 统计错误
    error_count = sum(1 for ep in all_episodes if ep["last_error"])

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
    overview_table.add_row(
        "Errors", f"[red]{error_count}[/red]" if error_count else "[green]0[/green]"
    )

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
            stats = f"{completed}/{total} ({pct:.0f}%)"
            console.print(f"  {stage_name:12} [{color}]{bar}[/{color}] {stats}")

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
            d = "✅" if ep["download_completed"] else "⏳"
            a = (
                "✅"
                if ep["asr_completed"]
                else ("⏳" if ep["download_completed"] else "⬜")
            )
            t = (
                "✅"
                if ep["translation_completed"]
                else ("⏳" if ep["asr_completed"] else "⬜")
            )
            s = (
                "✅"
                if ep["tts_completed"]
                else ("⏳" if ep["translation_completed"] else "⬜")
            )

            status_str = f"{d}→{a}→{t}→{s}"

            # 如果有错误，添加红色标记
            if ep["last_error"]:
                status_str += " [red]⚠[/red]"

            # 文件大小
            size_str = _format_file_size(ep["file_size"]) if ep["file_size"] else "-"

            # 更新时间
            updated = ep["updated_at"][:16] if ep["updated_at"] else "-"

            # 标题截断
            title = ep["episode_title"]
            if len(title) > 40:
                title = title[:37] + "..."

            ep_table.add_row(str(idx), title, size_str, status_str, updated)

        console.print(ep_table)

        if len(all_episodes) > 10:
            console.print(
                f"\n[dim]... and {len(all_episodes) - 10} more episodes[/dim]"
            )

    console.print()

    # 错误详情
    errors = [ep for ep in all_episodes if ep["last_error"]]
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
                console.print(
                    f"[dim]Refreshing every {interval}s... (Ctrl+C to exit)[/dim]"
                )
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
