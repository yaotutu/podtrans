"""Audio merging utilities for combining segmented TTS outputs.

This module provides functionality to merge multiple audio files back into a single
audio file, maintaining proper order and handling different audio formats.
"""

from pathlib import Path
from typing import List, Tuple
import tempfile
import shutil

try:
    import torchaudio
    import torch
    TORCHAUDIO_AVAILABLE = True
except ImportError:
    TORCHAUDIO_AVAILABLE = False

from loguru import logger
from rich.console import Console

console = Console()


class AudioMerger:
    """Merge multiple audio files into a single audio file."""

    def __init__(self):
        """Initialize audio merger."""
        if not TORCHAUDIO_AVAILABLE:
            raise ImportError("torchaudio is required for audio merging")

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

    def load_audio(self, audio_path: Path) -> Tuple[torch.Tensor, int]:
        """
        Load audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Tuple of (waveform, sample_rate)
        """
        try:
            waveform, sample_rate = torchaudio.load(str(audio_path))

            # Ensure mono
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            return waveform, sample_rate
        except Exception as e:
            logger.error(f"Failed to load audio {audio_path}: {e}")
            raise

    def merge_audio_files(
        self,
        audio_paths: List[Path],
        output_path: Path,
        target_sample_rate: int = None
    ) -> Tuple[Path, float]:
        """
        Merge multiple audio files into a single file.

        Args:
            audio_paths: List of audio file paths to merge (in order)
            output_path: Output path for the merged audio file
            target_sample_rate: Target sample rate (resamples if needed)

        Returns:
            Tuple of (output_path, total_duration)
        """
        if not audio_paths:
            raise ValueError("No audio files to merge")

        try:
            console.print(f"[blue]🔄 Merging {len(audio_paths)} audio files[/blue]")

            # Load first audio to get target sample rate
            first_waveform, first_sample_rate = self.load_audio(audio_paths[0])
            target_sr = target_sample_rate or first_sample_rate

            # Initialize concatenated waveform
            concatenated_waveform = first_waveform

            # Resample first audio if needed
            if first_sample_rate != target_sr:
                from torchaudio.transforms import Resample
                resampler = Resample(first_sample_rate, target_sr)
                concatenated_waveform = resampler(concatenated_waveform)

            total_duration = self.get_audio_info(audio_paths[0])[0]
            console.print(f"[blue]   ✓ Part 1/{len(audio_paths)}[/blue] ({total_duration:.1f}s)")

            # Process remaining audio files
            for i, audio_path in enumerate(audio_paths[1:], 2):
                waveform, sample_rate = self.load_audio(audio_path)

                # Resample if needed
                if sample_rate != target_sr:
                    from torchaudio.transforms import Resample
                    resampler = Resample(sample_rate, target_sr)
                    waveform = resampler(waveform)

                # Concatenate
                concatenated_waveform = torch.cat([concatenated_waveform, waveform], dim=1)

                # Add duration
                duration = self.get_audio_info(audio_path)[0]
                total_duration += duration

                console.print(f"[blue]   ✓ Part {i}/{len(audio_paths)}[/blue] ({duration:.1f}s)")

            # Save merged audio
            output_path.parent.mkdir(parents=True, exist_ok=True)
            torchaudio.save(str(output_path), concatenated_waveform, target_sr)

            console.print(f"[green]✓ Audio merge complete[/green]")
            console.print(f"[green]   Output: {output_path}[/green]")
            console.print(f"[green]   Total duration: {total_duration:.1f}s ({total_duration/60:.1f}min)[green]")

            return output_path, total_duration

        except Exception as e:
            logger.error(f"Failed to merge audio files: {e}")
            raise

    def find_segment_files(self, output_dir: Path) -> List[List[Path]]:
        """
        Find TTS output files for each episode's segments.

        Args:
            output_dir: Directory containing the pipeline output

        Returns:
            List of episodes, each containing a list of segment TTS files
        """
        try:
            # Look for TTS files that follow the pattern: segment_XXX_tts_output.wav
            segment_files = {}

            # Find all TTS files
            tts_pattern = output_dir.glob("**/segment_*_tts_output.wav")

            for tts_file in tts_pattern:
                # Extract episode and segment numbers from the file path
                # Path should be like: episode_001/episode_001_part_001/segment_001_tts_output.wav
                path_parts = tts_file.relative_to(output_dir).parts

                # Extract episode number from the first path part
                episode_num = None
                segment_num = None

                # Try to extract episode number from path like "episode_001"
                for part in path_parts:
                    if part.startswith('episode_') and part != 'episode':
                        try:
                            episode_num = int(part.split('_')[1])
                            break
                        except (ValueError, IndexError):
                            continue

                # Extract segment number from filename like "segment_001_tts_output.wav"
                if 'segment_' in tts_file.name:
                    try:
                        segment_part = tts_file.name.split('segment_')[1].split('_')[0]
                        segment_num = int(segment_part)
                    except (ValueError, IndexError):
                        continue

                if episode_num is not None and segment_num is not None:
                    if episode_num not in segment_files:
                        segment_files[episode_num] = {}

                    segment_files[episode_num][segment_num] = tts_file

            # Sort segments within each episode and return as lists
            result = []
            for episode_num in sorted(segment_files.keys()):
                segments = []
                for segment_num in sorted(segment_files[episode_num].keys()):
                    segments.append(segment_files[episode_num][segment_num])

                if segments:  # Only add episodes that have TTS files
                    result.append(segments)
                    console.print(f"[blue]📁 Found Episode {episode_num:03d}[/blue]: {len(segments)} segments")

            return result

        except Exception as e:
            logger.error(f"Failed to find segment files: {e}")
            return []

    def merge_episode_segments(self, output_dir: Path) -> List[Path]:
        """
        Merge TTS output segments for all episodes in a directory.

        Args:
            output_dir: Directory containing segmented TTS outputs

        Returns:
            List of paths to merged episode files
        """
        try:
            # Find segment files for each episode
            episodes_segments = self.find_segment_files(output_dir)

            if not episodes_segments:
                console.print("[yellow]⚠️  No TTS segment files found for merging[/yellow]")
                return []

            merged_files = []

            for episode_idx, segments in enumerate(episodes_segments, 1):
                if len(segments) <= 1:
                    # No need to merge single segments
                    console.print(f"[blue]Episode {episode_idx:03d}[/blue]: Single segment, copying as-is")
                    output_file = output_dir / f"episode_{episode_idx:03d}_merged_output.wav"
                    shutil.copy2(segments[0], output_file)
                    merged_files.append(output_file)
                    continue

                console.print(f"[blue]🔄 Merging Episode {episode_idx:03d}[/blue]: {len(segments)} segments")

                # Generate output filename
                output_file = output_dir / f"episode_{episode_idx:03d}_merged_output.wav"

                # Merge segments
                merged_path, duration = self.merge_audio_files(segments, output_file)
                merged_files.append(merged_path)

                console.print(f"[green]✓ Episode {episode_idx:03d} merged[/green]: {duration:.1f}s")

            console.print(f"[green]🎉 All episodes merged successfully![/green]")
            console.print(f"[green]   Total episodes: {len(merged_files)}[/green]")

            return merged_files

        except Exception as e:
            logger.error(f"Failed to merge episode segments: {e}")
            raise


def merge_segments_in_directory(output_dir: Path) -> List[Path]:
    """
    Convenience function to merge all TTS segments in a directory.

    Args:
        output_dir: Directory containing segmented TTS outputs

    Returns:
        List of paths to merged episode files
    """
    if not TORCHAUDIO_AVAILABLE:
        console.print("[yellow]⚠️  torchaudio not available, skipping audio merging[/yellow]")
        return []

    merger = AudioMerger()
    return merger.merge_episode_segments(output_dir)


def create_episode_playlist(merged_files: List[Path], output_path: Path):
    """
    Create a playlist file for the merged episodes.

    Args:
        merged_files: List of merged episode files
        output_path: Output path for the playlist file
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n\n")

            for i, merged_file in enumerate(merged_files, 1):
                # Get duration
                if TORCHAUDIO_AVAILABLE:
                    merger = AudioMerger()
                    duration, _ = merger.get_audio_info(merged_file)
                else:
                    duration = 0

                f.write(f"#EXTINF:{duration:.1f},Episode {i}\n")
                f.write(f"{merged_file.name}\n\n")

        console.print(f"[green]✓ Playlist created[/green]: {output_path}")

    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        raise