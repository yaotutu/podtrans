"""Audio processing utilities."""

from pathlib import Path

from loguru import logger
from pydub import AudioSegment


def get_audio_duration(audio_path: Path | str) -> float:
    """Get audio duration in seconds.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    audio_path = Path(audio_path)
    logger.debug(f"Getting duration of {audio_path}")

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    audio = AudioSegment.from_file(audio_path)
    duration = len(audio) / 1000.0  # Convert milliseconds to seconds

    logger.debug(f"Audio duration: {duration:.2f} seconds")
    return duration


def convert_to_wav(
    input_path: Path | str,
    output_path: Path | str | None = None,
    sample_rate: int = 16000,
) -> Path:
    """Convert audio file to WAV format.

    Args:
        input_path: Input audio file
        output_path: Output WAV file (default: same name with .wav extension)
        sample_rate: Target sample rate in Hz (default: 16000 for Whisper)

    Returns:
        Path to output WAV file

    Raises:
        FileNotFoundError: If input file doesn't exist
    """
    input_path = Path(input_path)
    logger.info(f"Converting {input_path} to WAV")

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        output_path = input_path.with_suffix(".wav")
    else:
        output_path = Path(output_path)

    # Load audio and convert
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(sample_rate)
    audio = audio.set_channels(1)  # Mono

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(output_path, format="wav")

    logger.info(f"Converted to WAV: {output_path}")
    return output_path


def validate_audio_file(audio_path: Path | str) -> bool:
    """Validate if file is a valid audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        True if valid, False otherwise
    """
    audio_path = Path(audio_path)

    if not audio_path.exists():
        logger.error(f"File does not exist: {audio_path}")
        return False

    try:
        audio = AudioSegment.from_file(audio_path)
        duration = len(audio) / 1000.0

        if duration <= 0:
            logger.error(f"Audio has zero duration: {audio_path}")
            return False

        logger.debug(f"Valid audio file: {audio_path} ({duration:.2f}s)")
        return True

    except Exception as e:
        logger.error(f"Invalid audio file {audio_path}: {e}")
        return False
