"""Audio file downloader for podcast episodes.

This module provides functionality to download audio files from podcast URLs,
with progress tracking, error handling, and file validation.
"""

import time
from pathlib import Path
from typing import Optional, List, Callable

import httpx
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TimeRemainingColumn

from podtrans.config import get_settings
from podtrans.rss.schemas import PodcastEpisode
from podtrans.utils.audio import validate_audio_file

console = Console()


class AudioDownloader:
    """Audio file downloader with progress tracking and error handling."""

    def __init__(self):
        """Initialize the downloader with default settings."""
        self.settings = get_settings()

    def download_episode(
        self,
        episode: PodcastEpisode,
        output_dir: Path,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Path:
        """Download a single podcast episode.

        Args:
            episode: Podcast episode to download
            output_dir: Directory to save the downloaded file
            filename: Custom filename (optional, will generate if not provided)
            progress_callback: Callback function for progress updates (optional)

        Returns:
            Path to the downloaded file

        Raises:
            httpx.HTTPError: If the download fails
            ValueError: If file validation fails or file is too large
        """
        logger.info(f"Downloading episode: {episode.title}")

        # Generate filename if not provided
        if filename:
            output_path = output_dir / filename
        else:
            safe_name = self._sanitize_filename(episode.title)
            ext = self._get_file_extension(episode.audio_url)
            output_path = output_dir / f"{safe_name}{ext}"

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Start download with progress tracking
            with httpx.Client(timeout=self.settings.rss_timeout, follow_redirects=True) as client:
                # Get file info first
                logger.debug(f"Checking file info for: {episode.audio_url}")
                head_response = client.head(episode.audio_url, follow_redirects=True)
                head_response.raise_for_status()

                # Check file size
                content_length = head_response.headers.get('content-length')
                if content_length:
                    file_size_bytes = int(content_length)
                    file_size_mb = file_size_bytes / (1024 * 1024)
                    logger.info(f"File size: {file_size_mb:.2f} MB")

                    # Check size limit
                    if file_size_bytes > self.settings.rss_max_file_size_mb * 1024 * 1024:
                        raise ValueError(
                            f"File too large: {file_size_mb:.2f} MB > {self.settings.rss_max_file_size_mb} MB limit"
                        )

                # Download with progress bar
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TextColumn("•"),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"Downloading {episode.title[:50]}...", total=file_size_bytes)

                    with client.stream('GET', episode.audio_url) as response:
                        response.raise_for_status()

                        downloaded_bytes = 0
                        start_time = time.time()

                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                f.write(chunk)
                                downloaded_bytes += len(chunk)

                                # Update progress
                                progress.update(task, completed=downloaded_bytes)

                                # Custom progress callback
                                if progress_callback and content_length:
                                    progress_percent = (downloaded_bytes / content_length) * 100
                                    progress_callback(progress_percent)

                                # Log progress every 10MB
                                if downloaded_bytes % (10 * 1024 * 1024) == 0:
                                    elapsed = time.time() - start_time
                                    speed = (downloaded_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                                    logger.debug(f"Downloaded {downloaded_bytes / (1024*1024):.1f} MB, speed: {speed:.2f} MB/s")

            logger.info(f"Successfully downloaded: {output_path}")

            # Validate downloaded file
            if not validate_audio_file(output_path):
                # Remove invalid file
                if output_path.exists():
                    output_path.unlink()
                raise ValueError("Downloaded file is not a valid audio file")

            final_size = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Final file size: {final_size:.2f} MB")

            return output_path

        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading {episode.title}: {e}")
            # Clean up partial download
            if output_path.exists():
                output_path.unlink()
            raise
        except Exception as e:
            logger.error(f"Failed to download {episode.title}: {e}")
            # Clean up partial download
            if output_path.exists():
                output_path.unlink()
            raise

    def download_episodes(
        self,
        episodes: List[PodcastEpisode],
        output_dir: Path,
        max_concurrent: int = 1,
    ) -> List[Path]:
        """Download multiple episodes sequentially (MVP implementation).

        Args:
            episodes: List of episodes to download
            output_dir: Output directory
            max_concurrent: Maximum concurrent downloads (ignored in MVP, always sequential)

        Returns:
            List of successfully downloaded file paths
        """
        logger.info(f"Downloading {len(episodes)} episodes (sequential for MVP)")

        downloaded_files = []
        failed_episodes = []

        for i, episode in enumerate(episodes, 1):
            try:
                logger.info(f"Processing episode {i}/{len(episodes)}: {episode.title}")

                # Generate unique filename to avoid conflicts
                safe_name = self._sanitize_filename(f"episode_{i:03d}_{episode.title}")
                ext = self._get_file_extension(episode.audio_url)
                filename = f"{safe_name}{ext}"

                # Download the episode
                downloaded_path = self.download_episode(episode, output_dir, filename)
                downloaded_files.append(downloaded_path)

                logger.info(f"Successfully downloaded {episode.title}")

            except Exception as e:
                logger.error(f"Failed to download {episode.title}: {e}")
                failed_episodes.append((episode, str(e)))
                continue

        # Log summary
        logger.info(f"Download completed: {len(downloaded_files)} successful, {len(failed_episodes)} failed")

        if failed_episodes:
            logger.warning("Failed downloads:")
            for episode, error in failed_episodes:
                logger.warning(f"  - {episode.title}: {error}")

        return downloaded_files

    def _get_file_extension(self, url: str) -> str:
        """Get file extension from URL.

        Args:
            url: Audio file URL

        Returns:
            File extension including dot (e.g., '.mp3')
        """
        from urllib.parse import urlparse, unquote

        try:
            parsed_url = urlparse(url)
            path = unquote(parsed_url.path).lower()

            # Check for common audio extensions
            for ext in self.settings.rss_supported_formats:
                if path.endswith(f'.{ext}'):
                    return f'.{ext}'

            # Try to extract extension from last part of path
            if '.' in path:
                return '.' + path.split('.')[-1]

        except Exception as e:
            logger.debug(f"Failed to extract extension from URL {url}: {e}")

        # Default to .mp3
        return '.mp3'

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        if not filename:
            return "untitled"

        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Remove extra whitespace and normalize
        filename = ' '.join(filename.split())

        # Limit length
        if len(filename) > 100:
            filename = filename[:100].rstrip()

        # Ensure it's not empty
        if not filename:
            filename = "untitled"

        return filename

    def get_download_info(self, episode: PodcastEpisode) -> dict:
        """Get download information for an episode without actually downloading.

        Args:
            episode: Podcast episode to check

        Returns:
            Dictionary with download information
        """
        info = {
            'title': episode.title,
            'url': episode.audio_url,
            'estimated_size': None,
            'duration': episode.duration,
            'size_mb': episode.size_mb,
            'accessible': False,
        }

        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.head(episode.audio_url, follow_redirects=True)
                if response.status_code == 200:
                    info['accessible'] = True
                    content_length = response.headers.get('content-length')
                    if content_length:
                        info['estimated_size'] = int(content_length)
                        info['size_mb'] = round(int(content_length) / (1024 * 1024), 2)
        except Exception as e:
            logger.debug(f"Failed to get download info for {episode.title}: {e}")

        return info

    def validate_audio_format(self, url: str) -> bool:
        """Check if the URL points to a supported audio format.

        Args:
            url: Audio file URL

        Returns:
            True if format is supported, False otherwise
        """
        try:
            ext = self._get_file_extension(url)
            supported_exts = [f'.{fmt}' for fmt in self.settings.rss_supported_formats]
            return ext.lower() in supported_exts
        except Exception:
            return False