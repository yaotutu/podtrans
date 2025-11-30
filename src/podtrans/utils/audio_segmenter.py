"""Audio segmentation utilities for long podcast episodes.

This module provides functionality to split long audio files into smaller segments
that can be processed more reliably by the TTS pipeline.
"""

from pathlib import Path
from typing import List, Tuple
import tempfile
import shutil
import math

try:
    import torchaudio
    import torch
    TORCHAUDIO_AVAILABLE = True
except ImportError:
    TORCHAUDIO_AVAILABLE = False

from loguru import logger
from rich.console import Console

console = Console()


class AudioSegmenter:
    """Split long audio files into smaller segments for processing."""

    def __init__(self, max_segment_duration: float = 600.0):
        """
        Initialize audio segmenter.

        Args:
            max_segment_duration: Maximum duration per segment in seconds (default: 10 minutes)
        """
        if not TORCHAUDIO_AVAILABLE:
            raise ImportError("torchaudio is required for audio segmentation")

        self.max_segment_duration = max_segment_duration

    def get_audio_info(self, audio_path: Path) -> Tuple[float, int]:
        """
        Get audio file information.

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (duration, sample_rate)
        """
        try:
            info = torchaudio.info(str(audio_path))
            return info.num_frames / info.sample_rate, info.sample_rate
        except Exception as e:
            logger.error(f"Failed to get audio info for {audio_path}: {e}")
            raise

    def needs_segmentation(self, audio_path: Path) -> bool:
        """
        Check if audio file needs to be segmented.

        Args:
            audio_path: Path to audio file

        Returns:
            True if duration exceeds max_segment_duration
        """
        try:
            duration, _ = self.get_audio_info(audio_path)
            return duration > self.max_segment_duration
        except Exception:
            return False

    def split_audio(self, audio_path: Path, output_dir: Path) -> List[Path]:
        """
        Split audio file into smaller segments.

        Args:
            audio_path: Path to input audio file
            output_dir: Directory to save segments

        Returns:
            List of paths to segment files
        """
        try:
            duration, sample_rate = self.get_audio_info(audio_path)

            if duration <= self.max_segment_duration:
                # No need to split
                output_path = output_dir / audio_path.name
                shutil.copy2(audio_path, output_path)
                return [output_path]

            # Calculate number of segments needed
            num_segments = math.ceil(duration / self.max_segment_duration)

            console.print(f"[blue]📊 Splitting {audio_path.name}[/blue]")
            console.print(f"[blue]   Duration: {duration:.1f}s ({duration/60:.1f}min)[/blue]")
            console.print(f"[blue]   Segments: {num_segments} (~{self.max_segment_duration/60:.1f}min each)[/blue]")

            # Load audio
            waveform, sr = torchaudio.load(str(audio_path))

            # Ensure mono
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            # Calculate samples per segment
            samples_per_segment = int(self.max_segment_duration * sr)

            segment_paths = []

            for i in range(num_segments):
                start_sample = i * samples_per_segment
                end_sample = min((i + 1) * samples_per_segment, waveform.shape[1])

                # Extract segment
                segment_waveform = waveform[:, start_sample:end_sample]

                # Generate output filename
                stem = audio_path.stem
                suffix = audio_path.suffix
                segment_filename = f"{stem}_part_{i+1:03d}{suffix}"
                segment_path = output_dir / segment_filename

                # Save segment
                torchaudio.save(str(segment_path), segment_waveform, sr)

                # Calculate actual duration
                actual_duration = (end_sample - start_sample) / sr
                console.print(f"[green]   ✓ Part {i+1}/{num_segments}[/green] ({actual_duration:.1f}s)")

                segment_paths.append(segment_path)

            console.print(f"[green]✓ Audio split complete: {len(segment_paths)} segments[/green]")
            return segment_paths

        except Exception as e:
            logger.error(f"Failed to split audio {audio_path}: {e}")
            raise

    def create_segment_mappings(self, original_path: Path, segment_paths: List[Path]) -> List[dict]:
        """
        Create mapping information for segments.

        Args:
            original_path: Original audio file path
            segment_paths: List of segment file paths

        Returns:
            List of segment mapping dictionaries
        """
        try:
            original_duration, _ = self.get_audio_info(original_path)
            segment_mappings = []

            for i, segment_path in enumerate(segment_paths):
                segment_duration, _ = self.get_audio_info(segment_path)

                mapping = {
                    "segment_index": i + 1,
                    "original_path": str(original_path),
                    "segment_path": str(segment_path),
                    "segment_duration": segment_duration,
                    "start_time": i * self.max_segment_duration,
                    "end_time": min((i + 1) * self.max_segment_duration, original_duration)
                }

                segment_mappings.append(mapping)

            return segment_mappings

        except Exception as e:
            logger.error(f"Failed to create segment mappings: {e}")
            raise


def should_split_audio(audio_path: Path, max_duration: float = 600.0) -> bool:
    """
    Quick check if audio needs splitting without loading the full file.

    Args:
        audio_path: Path to audio file
        max_duration: Maximum duration in seconds

    Returns:
        True if audio should be split
    """
    if not TORCHAUDIO_AVAILABLE:
        return False

    try:
        segmenter = AudioSegmenter(max_duration)
        return segmenter.needs_segmentation(audio_path)
    except Exception:
        return False


def split_long_audio(audio_path: Path, output_dir: Path, max_duration: float = 600.0) -> List[Path]:
    """
    Convenience function to split long audio files.

    Args:
        audio_path: Path to input audio file
        output_dir: Directory to save segments
        max_duration: Maximum duration per segment in seconds

    Returns:
        List of segment file paths
    """
    if not TORCHAUDIO_AVAILABLE:
        console.print("[yellow]⚠️  torchaudio not available, skipping audio segmentation[/yellow]")
        return [audio_path]

    segmenter = AudioSegmenter(max_duration)

    if not segmenter.needs_segmentation(audio_path):
        # No need to split
        output_path = output_dir / audio_path.name
        shutil.copy2(audio_path, output_path)
        return [output_path]

    return segmenter.split_audio(audio_path, output_dir)