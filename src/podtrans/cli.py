"""Command-line interface for PodTrans.

This module provides the CLI commands using Typer.
"""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from podtrans.asr import WhisperXHandler
from podtrans.asr.result_splitter import ASRResultSplitter
from podtrans.config import get_settings
from podtrans.translation import Translator
from podtrans.translation.segment_translator import SegmentTranslator
from podtrans.utils.file import write_json

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
    settings = get_settings()
    db_path = settings.get_database_dir() / "episodes.db"
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

                # Save voice sample info to each speaker directory
                extractor.save_speaker_info_to_dirs(voice_result, episode_dir)

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

            # Split ASR result if enabled and audio is long enough
            segments = []
            if (
                settings.enable_asr_splitting
                and asr_result.audio_duration >= settings.asr_split_threshold
            ):
                console.print("[cyan]🔄 Splitting ASR result...[/cyan]")

                # Create segments directory
                segments_dir = episode_dir / "segments"
                segments_dir.mkdir(exist_ok=True)

                # Initialize splitter
                splitter = ASRResultSplitter(
                    target_duration=settings.asr_target_duration,
                    min_duration=settings.asr_min_duration,
                    max_duration=settings.asr_max_duration,
                    episode_id=f"episode_{episode_id}",
                )

                # Split the result
                segments, split_metadata = splitter.split_result(
                    asr_result, segments_dir
                )

                # Save segment metadata at the episode level
                metadata_path = episode_dir / "segment_metadata.json"
                write_json(split_metadata.model_dump(), metadata_path)

                # Save individual segments in their own subdirectories
                for segment in segments:
                    # Create subdirectory for this segment
                    segment_dir = segments_dir / f"segment_{segment.segment_index:03d}"
                    segment_dir.mkdir(exist_ok=True)

                    # Save ASR result with asr_ prefix
                    asr_file = segment_dir / "asr_result.json"
                    write_json(
                        {
                            "segment_id": segment.segment_id,
                            "episode_id": segment.episode_id,
                            "segment_index": segment.segment_index,
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "duration": segment.duration,
                            "segments": [s.model_dump() for s in segment.segments],
                            "speakers": list(segment.speakers),
                            "language": segment.language,
                            "model_name": segment.model_name,
                            "created_at": segment.created_at.isoformat(),
                        },
                        asr_file,
                    )

                console.print(
                    f"[green]✓[/green] Split into {len(segments)} segments "
                    f"(avg: {sum(s.duration for s in segments) / len(segments) / 60:.1f} min)"
                )

                # Update database with split information
                split_updates = {
                    "asr_split_completed": True,
                    "asr_split_timestamp": datetime.now(),
                    "asr_segment_count": len(segments),
                    "asr_split_metadata": split_metadata.model_dump_json(),
                }
            else:
                split_updates = {
                    "asr_split_completed": False,
                    "asr_split_timestamp": None,
                    "asr_segment_count": 1,
                    "asr_split_metadata": None,
                }

            # Update database
            db.update_episode_status(
                episode_id,
                {
                    "asr_completed": True,
                    "asr_result_path": str(result_path),
                    "asr_timestamp": datetime.now(),
                    "retry_count": 0,  # Reset retry count on success
                    **split_updates,
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
    episode_dir: Path = typer.Option(
        None,
        "--episode-dir",
        "-e",
        help="Translate specific episode directory (bypasses database)",
    ),
    segment_by_segment: bool = typer.Option(
        False,
        "--segment-by-segment",
        help="Translate segments one by one (with pause between segments)",
    ),
    parallel: bool = typer.Option(
        None,
        "--parallel/--no-parallel",
        "-p/-P",
        help="Enable parallel batch translation (default: from config)",
    ),
    workers: int = typer.Option(
        None,
        "--workers",
        "-w",
        help="Number of parallel workers (default: from config, typically 4)",
    ),
) -> None:
    """Batch process translation for all ASR-completed episodes.

    This command:
    - Queries database for episodes with asr_completed=True and
      translation_completed=False
    - Processes each episode with Qwen translation
    - Saves results to episode directory
    - Updates database with completion status

    Parallel Mode:
    - Use --parallel to enable parallel batch processing (faster)
    - Use --workers to set the number of concurrent workers
    - Rate limiting is automatically applied to avoid API throttling

    Example:
        podtrans translation
        podtrans translation --data-dir ./data --max-retries 5
        podtrans translation -s en -t zh
        podtrans translation --parallel --workers 4
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

    # Determine parallel settings (CLI overrides config)
    # 并行设置：CLI 参数优先于配置文件
    use_parallel = (
        parallel if parallel is not None else settings.translation_parallel_enabled
    )
    num_workers = (
        workers if workers is not None else settings.translation_parallel_max_workers
    )

    # Handle single episode directory mode
    if episode_dir:
        console.print(f"[dim]Translation: {source_lang} → {target_lang}[/dim]")
        if use_parallel:
            console.print(f"[dim]Parallel: enabled ({num_workers} workers)[/dim]\n")
        else:
            console.print("[dim]Parallel: disabled (sequential mode)[/dim]\n")

        # Initialize translator
        console.print("[bold cyan]🔧 Initializing translator...[/bold cyan]")
        try:
            translator = Translator(settings)
            console.print(f"[green]✓[/green] Model: {translator.model}")
            console.print(f"[green]✓[/green] API base: {settings.translation_api_base}")
            console.print(
                f"[green]✓[/green] Max segments/batch: "
                f"{settings.translation_max_segments_per_batch}"
            )
            if use_parallel:
                console.print(
                    f"[green]✓[/green] Parallel workers: {num_workers}, "
                    f"Rate limit: {settings.translation_rate_limit_per_second} req/s"
                )
            console.print()
        except Exception as e:
            console.print(
                f"[bold red]❌ Failed to initialize translator: {e}[/bold red]"
            )
            raise typer.Exit(1)

        # Initialize segment translator
        segment_translator = SegmentTranslator(translator)

        # Check if episode has segments
        segments_dir = episode_dir / "segments"
        segment_metadata_file = episode_dir / "segment_metadata.json"

        if segments_dir.exists() and segment_metadata_file.exists():
            console.print(f"[cyan]🔄 Processing episode: {episode_dir.name}[/cyan]")

            # Discover segments
            segments = segment_translator.discover_segments(episode_dir)

            if not segments:
                console.print("[yellow]⚠️  No segments found[/yellow]")
                raise typer.Exit(1)

            console.print(f"[dim]Found {len(segments)} segments[/dim]")

            if segment_by_segment:
                # Translate one by one
                console.print("[cyan]🔄 Translating segments one by one...[/cyan]\n")

                for i, segment in enumerate(segments, 1):
                    # Check if already translated
                    translation_file = (
                        segment["segment_dir"] / "translation_result.json"
                    )
                    if translation_file.exists():
                        console.print(
                            f"✅ Segment {i}/{len(segments)} [{segment['segment_id']}] - Already translated, skipping..."
                        )
                        continue

                    console.print(f"\n{'=' * 60}")
                    console.print(
                        f"[bold]Translating segment {i}/{len(segments)}[/bold]"
                    )
                    console.print(f"ID: {segment['segment_id']}")
                    console.print(
                        f"Time: {segment['start_time']:.1f}s - {segment['end_time']:.1f}s"
                    )
                    console.print(f"{'=' * 60}")

                    try:
                        # Translate segment
                        result = segment_translator.translate_segment(
                            segment, source_lang=source_lang, target_lang=target_lang
                        )

                        # Save result
                        segment_translator.save_translation_result(
                            segment["segment_dir"], result
                        )

                        console.print("[green]✅ Translation completed![/green]")
                        console.print(f"[dim]Saved to: {segment['segment_dir']}[/dim]")

                        # Show created files
                        for f in segment["segment_dir"].glob("*translation*"):
                            size = f.stat().st_size
                            console.print(f"[dim]  - {f.name} ({size} bytes)[/dim]")

                    except Exception as e:
                        console.print(f"[red]❌ Translation failed: {e}[/red]")
                        if max_retries > 0:
                            console.print(
                                f"[dim]You can retry later with --max-retries {max_retries}[/dim]"
                            )

                # Show final progress
                progress = segment_translator.get_translation_progress(segments)
                console.print("\n[bold]Translation Summary:[/bold]")
                console.print(f"  Total segments: {progress['total_segments']}")
                console.print(f"  Completed: {progress['completed_segments']}")
                console.print(f"  Progress: {progress['progress_percentage']:.1f}%")

            else:
                # Batch translate all segments
                results = segment_translator.translate_segments(
                    segments,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    max_retries=max_retries,
                    use_parallel=use_parallel,
                    max_workers=num_workers,
                )

                success_count = sum(1 for r in results if r["success"])
                console.print(
                    f"\n[green]✅[/green] Translation completed: {success_count}/{len(results)} segments"
                )
        else:
            console.print("[yellow]⚠️  No segments found in episode directory[/yellow]")
            # Fall back to full episode translation
            asr_file = episode_dir / "asr_result.json"
            if asr_file.exists():
                console.print(
                    "[cyan]🔄 Falling back to full episode translation[/cyan]"
                )
                _translate_full_episode_direct(
                    asr_file, translator, source_lang, target_lang, console
                )
            else:
                console.print("[red]❌ No ASR result found[/red]")
                raise typer.Exit(1)

        return

    # Initialize database for batch mode
    settings = get_settings()
    db_path = settings.get_database_dir() / "episodes.db"
    if not db_path.exists():
        console.print(f"[bold red]❌ Database not found: {db_path}[/bold red]")
        raise typer.Exit(1)

    db = DatabaseManager(db_path, init_db=False)

    console.print(f"[dim]Translation: {source_lang} → {target_lang}[/dim]")
    if use_parallel:
        console.print(f"[dim]Parallel: enabled ({num_workers} workers)[/dim]\n")
    else:
        console.print("[dim]Parallel: disabled (sequential mode)[/dim]\n")

    # Initialize translator
    console.print("[bold cyan]🔧 Initializing translator...[/bold cyan]")
    try:
        translator = Translator(settings)
        console.print(f"[green]✓[/green] Model: {translator.model}")
        console.print(f"[green]✓[/green] API base: {settings.translation_api_base}")
        console.print(
            f"[green]✓[/green] Max segments/batch: "
            f"{settings.translation_max_segments_per_batch}"
        )
        if use_parallel:
            console.print(
                f"[green]✓[/green] Parallel workers: {num_workers}, "
                f"Rate limit: {settings.translation_rate_limit_per_second} req/s"
            )
        console.print()
    except Exception as e:
        console.print(f"[bold red]❌ Failed to initialize translator: {e}[/bold red]")
        raise typer.Exit(1)

    success_count = 0
    failed_count = 0
    processed_ids: set[int] = set()  # Track processed episodes to avoid duplicates

    # Initialize segment translator
    segment_translator = SegmentTranslator(translator)

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
        episode_dir = Path(episode["episode_dir"])

        total_pending = len(episodes)
        console.print(
            f"[bold]Translating[/bold] (pending: {total_pending}): {episode_title}"
        )
        console.print(f"[dim]Episode directory: {episode_dir}[/dim]")

        try:
            # Check if this episode has segments
            segments_dir = episode_dir / "segments"
            segment_metadata_file = episode_dir / "segment_metadata.json"

            if segments_dir.exists() and segment_metadata_file.exists():
                # 片段模式
                console.print("[cyan]🔄 Processing in segment mode[/cyan]")

                # Discover segments
                segments = segment_translator.discover_segments(episode_dir)

                if not segments:
                    console.print(
                        "[yellow]⚠️  No segments found, falling back to episode mode[/yellow]"
                    )
                    # Fall back to episode mode
                    _translate_full_episode(
                        episode, translator, source_lang, target_lang, console, db
                    )
                    success_count += 1
                    continue

                # Create segment records in database if needed
                db.create_translation_segments(episode_id, segments)

                console.print(f"[dim]Found {len(segments)} segments[/dim]")

                # Get progress
                progress = segment_translator.get_translation_progress(segments)
                console.print(
                    f"[dim]Progress: {progress['completed_segments']}/{progress['total_segments']} "
                    f"({progress['progress_percentage']:.1f}%)[/dim]"
                )

                # Process segments
                results = segment_translator.translate_segments(
                    segments,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    max_retries=max_retries,
                    use_parallel=use_parallel,
                    max_workers=num_workers,
                )

                # Update database with results
                for result in results:
                    segment = next(
                        s for s in segments if s["segment_id"] == result["segment_id"]
                    )

                    if result["success"]:
                        # Convert Path to string for database
                        result_path = (
                            str(result["translation_result_path"])
                            if result.get("translation_result_path")
                            else None
                        )
                        db.update_translation_segment_status(
                            segment["segment_id"],
                            episode_id,
                            {
                                "translation_completed": True,
                                "translation_result_path": result_path,
                                "error_count": 0,
                                "retry_count": 0,
                            },
                        )
                    else:
                        db.update_translation_segment_status(
                            segment["segment_id"],
                            episode_id,
                            {
                                "translation_completed": False,
                                "error_count": 1,
                                "last_error": result["error"],
                                "retry_count": result.get("retry_count", 0),
                            },
                        )

                # Check if all segments completed
                final_progress = segment_translator.get_translation_progress(segments)
                if (
                    final_progress["completed_segments"]
                    == final_progress["total_segments"]
                ):
                    # Update episode as completed
                    db.update_episode_status(
                        episode_id,
                        {
                            "translation_completed": True,
                            "translation_timestamp": datetime.now(),
                            "retry_count": 0,
                        },
                    )

                    # Optionally merge results
                    if settings.translation_merge_segments:
                        merged_file = segment_translator.merge_translation_results(
                            episode_dir, segments, "json"
                        )
                        console.print(f"[green]✓[/green] Merged results: {merged_file}")

                success_count += 1
                console.print(
                    f"[green]✅ Segments completed: "
                    f"{final_progress['completed_segments']}/{final_progress['total_segments']}\n"
                )

            else:
                # 完整剧集模式
                console.print("[cyan]🔄 Processing in episode mode[/cyan]")
                _translate_full_episode(
                    episode, translator, source_lang, target_lang, console, db
                )
                success_count += 1

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


def _translate_full_episode(episode, translator, source_lang, target_lang, console, db):
    """翻译完整剧集（非片段模式）"""
    episode_id = episode["id"]
    episode_title = episode["episode_title"]
    asr_result_path = Path(episode["asr_result_path"])
    episode_dir = Path(episode["episode_dir"])

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

    console.print(f"[green]✅ Success[/green]: {result_path}.json\n")
    logger.info(f"翻译成功: {episode_title}")


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


@app.command()
def tts(
    data_dir: Path = typer.Option(
        Path("./data"),
        "--data-dir",
        "-d",
        help="Data directory path",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="只显示待处理剧集，不执行",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        help="Maximum retry count for failed episodes",
    ),
) -> None:
    """Execute TTS for translation-completed episodes.

    This command:
    - Queries database for episodes with translation_completed=True
      and tts_completed=False
    - Executes podcast-tts CLI (blocking)
    - Updates database with completion status

    Example:
        podtrans tts              # 处理一个待处理剧集
        podtrans tts --dry-run    # 只显示，不执行
    """
    from podtrans.services.database import DatabaseManager
    from podtrans.services.tts_service import TTSService

    console.print("\n[bold blue]🔊 PodTrans - TTS Processing[/bold blue]\n")

    # Initialize database
    settings = get_settings()
    db_path = settings.get_database_dir() / "episodes.db"
    if not db_path.exists():
        console.print(f"[bold red]❌ Database not found: {db_path}[/bold red]")
        raise typer.Exit(1)

    db = DatabaseManager(db_path, init_db=False)

    # Initialize TTS service
    tts_service = TTSService(
        cli_path=settings.tts_cli_path,
        timeout=settings.tts_timeout,
    )
    console.print(f"[dim]TTS CLI: {settings.tts_cli_path}[/dim]")
    console.print(f"[dim]Timeout: {settings.tts_timeout}s[/dim]\n")

    # Query pending episodes
    episodes = db.get_pending_episodes(stage="tts")
    episodes = [ep for ep in episodes if ep.get("retry_count", 0) < max_retries]

    if not episodes:
        console.print("[green]✅ No episodes pending for TTS processing[/green]")
        return

    # Show pending episodes
    console.print(f"[bold]Found {len(episodes)} pending episode(s)[/bold]\n")
    for i, ep in enumerate(episodes, 1):
        console.print(f"  {i}. {ep['episode_title']}")
        console.print(f"     [dim]{ep['episode_dir']}[/dim]")

    if dry_run:
        console.print("\n[yellow]--dry-run: Not executing[/yellow]")
        return

    # Process only the first episode (single processing mode)
    episode = episodes[0]
    episode_id = episode["id"]
    episode_title = episode["episode_title"]
    episode_dir = Path(episode["episode_dir"])

    console.print(f"\n[bold cyan]Processing:[/bold cyan] {episode_title}")
    console.print(f"[dim]Directory: {episode_dir}[/dim]")

    # Execute TTS
    logger.info(f"开始 TTS 处理: {episode_title}")
    result = tts_service.execute(episode_dir)

    if result.success:
        # Update database
        db.update_episode_status(
            episode_id,
            {
                "tts_completed": True,
                "tts_timestamp": datetime.now(),
                "tts_result_path": result.output_path,
                "retry_count": 0,  # Reset retry count on success
            },
        )

        console.print("\n[green]✅ TTS completed successfully![/green]")
        console.print(f"[dim]Output: {result.output_path}[/dim]")
        if result.duration:
            console.print(f"[dim]Duration: {result.duration:.1f}s[/dim]")
        logger.info(f"TTS 处理成功: {episode_title}")

    else:
        # Update database with error
        current_retry = episode.get("retry_count", 0)
        db.update_episode_status(
            episode_id,
            {
                "retry_count": current_retry + 1,
                "error_count": episode.get("error_count", 0) + 1,
                "last_error": result.error,
            },
        )

        console.print(f"\n[red]❌ TTS failed: {result.error}[/red]")
        logger.error(f"TTS 处理失败: {episode_title}: {result.error}")
        raise typer.Exit(1)


def _translate_full_episode_direct(
    asr_file, translator, source_lang, target_lang, console
):
    """直接翻译完整剧集（不需要数据库）"""
    episode_dir = asr_file.parent

    # Check if already translated
    translation_file = episode_dir / "translation_result.json"
    if translation_file.exists():
        console.print("[yellow]⚠️  Episode already translated, skipping...[/yellow]")
        return

    # Load ASR result
    console.print(f"[dim]Loading ASR result: {asr_file.name}[/dim]")
    asr_result = translator.load_asr_result(asr_file)
    seg_count = asr_result.total_segments
    spk_count = asr_result.speaker_count
    console.print(f"[dim]Segments: {seg_count}, Speakers: {spk_count}[/dim]")

    # Translate
    translation_result = translator.translate_asr_result(
        asr_result=asr_result, source_lang=source_lang, target_lang=target_lang
    )

    # Save results
    output_file = episode_dir / "translation_result.json"
    write_json(translation_result.model_dump(), output_file)
    console.print(f"[green]✓[/green] Translation saved: {output_file}")

    # Save Chinese text
    zh_file = episode_dir / "translation_result.zh.txt"
    with open(zh_file, "w", encoding="utf-8") as f:
        f.write(translation_result.to_chinese_text(include_speakers=False))
    console.print(f"[green]✓[/green] Chinese text saved: {zh_file}")

    # Save bilingual text
    bilingual_file = episode_dir / "translation_result.bilingual.txt"
    with open(bilingual_file, "w", encoding="utf-8") as f:
        f.write(translation_result.to_bilingual_text(include_speakers=True))
    console.print(f"[green]✓[/green] Bilingual text saved: {bilingual_file}")


@app.callback()
def main() -> None:
    """PodTrans - AI-powered podcast translation pipeline.

    Translate English podcasts to Chinese while preserving speaker information.
    """
    pass


if __name__ == "__main__":
    app()
