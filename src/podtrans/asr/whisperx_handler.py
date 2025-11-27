"""WhisperX handler for ASR with speaker diarization.

This module provides a high-level interface to WhisperX for:
- Automatic Speech Recognition (ASR)
- Word-level alignment
- Speaker diarization
"""

from pathlib import Path
from typing import Any

import torch
import whisperx
from loguru import logger
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from podtrans.asr.schemas import ASRResult, Segment, Word
from podtrans.config import get_settings


class WhisperXHandler:
    """Handler for WhisperX ASR with speaker diarization."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        hf_token: str | None = None,
    ):
        """Initialize WhisperX handler.

        Args:
            model_name: Whisper model name (e.g., "large-v2")
            device: Device to use (cuda/mps/cpu)
            compute_type: Compute precision (int8/float16/float32)
            hf_token: HuggingFace token for speaker diarization
        """
        settings = get_settings()

        self.model_name = model_name or settings.whisper_model
        self.device = device or settings.device
        self.compute_type = compute_type or settings.compute_type
        self.hf_token = hf_token or settings.hf_token

        # Adjust compute type for MPS (Apple Silicon doesn't support int8)
        if self.device == "mps" and self.compute_type == "int8":
            logger.warning("MPS doesn't support int8, falling back to float16")
            self.compute_type = "float16"

        # Check MPS availability
        if self.device == "mps" and not torch.backends.mps.is_available():
            logger.warning("MPS not available, falling back to CPU")
            self.device = "cpu"

        self.model: Any = None
        self.align_model: Any = None
        self.align_metadata: Any = None
        self.diarize_model: Any = None

        logger.info(
            f"WhisperX initialized: model={self.model_name}, "
            f"device={self.device}, compute_type={self.compute_type}"
        )

    def load_model(self) -> None:
        """Load WhisperX ASR model."""
        logger.info(f"Loading Whisper model: {self.model_name}")

        try:
            self.model = whisperx.load_model(
                self.model_name,
                self.device,
                compute_type=self.compute_type,
            )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(
        self,
        audio_path: Path | str,
        language: str | None = None,
        batch_size: int | None = None,
    ) -> dict[str, Any]:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "en", "zh"). If None, auto-detect
            batch_size: Batch size for processing

        Returns:
            Raw transcription result from WhisperX
        """
        audio_path = Path(audio_path)
        settings = get_settings()
        batch_size = batch_size or settings.asr_batch_size

        logger.info(f"Transcribing audio: {audio_path}")

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if self.model is None:
            self.load_model()

        try:
            # Load audio
            audio = whisperx.load_audio(str(audio_path))
            logger.debug(f"Audio loaded, duration: {len(audio) / 16000:.2f}s")

            # Transcribe
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Transcribing...", total=None)
                result = self.model.transcribe(
                    audio,
                    batch_size=batch_size,
                    language=language,
                )
                progress.update(task, completed=True)

            detected_lang = result.get("language", "unknown")
            logger.info(f"Transcription complete, detected language: {detected_lang}")

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def align(
        self,
        segments: list[dict[str, Any]],
        audio: Any,
        language: str,
    ) -> dict[str, Any]:
        """Align transcription to get word-level timestamps.

        Args:
            segments: Transcription segments from transcribe()
            audio: Audio array from whisperx.load_audio()
            language: Language code

        Returns:
            Aligned result with word-level timestamps
        """
        logger.info("Aligning transcription for word-level timestamps")

        try:
            # Load alignment model if not loaded
            if self.align_model is None:
                logger.debug(f"Loading alignment model for language: {language}")
                self.align_model, self.align_metadata = whisperx.load_align_model(
                    language_code=language,
                    device=self.device,
                )

            # Perform alignment
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Aligning words...", total=None)
                result = whisperx.align(
                    segments,
                    self.align_model,
                    self.align_metadata,
                    audio,
                    self.device,
                    return_char_alignments=False,
                )
                progress.update(task, completed=True)

            logger.info("Alignment complete")
            return result

        except Exception as e:
            logger.error(f"Alignment failed: {e}")
            raise

    def diarize(self, audio_path: Path | str) -> Any:
        """Perform speaker diarization.

        Args:
            audio_path: Path to audio file

        Returns:
            Diarization segments
        """
        audio_path = Path(audio_path)
        logger.info("Performing speaker diarization")

        if not self.hf_token:
            logger.warning(
                "No HuggingFace token provided, skipping diarization. "
                "Set HF_TOKEN environment variable to enable speaker diarization."
            )
            return None

        try:
            # Load diarization model if not loaded
            if self.diarize_model is None:
                logger.debug("Loading diarization model")
                self.diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=self.hf_token,
                    device=self.device,
                )

            # Perform diarization
            audio = whisperx.load_audio(str(audio_path))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Identifying speakers...", total=None)
                diarize_segments = self.diarize_model(audio)
                progress.update(task, completed=True)

            logger.info("Diarization complete")
            return diarize_segments

        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            logger.warning("Continuing without speaker labels")
            return None

    def assign_speakers(
        self,
        diarize_segments: Any,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Assign speakers to transcription segments.

        Args:
            diarize_segments: Diarization result
            result: Aligned transcription result

        Returns:
            Result with speaker labels added
        """
        if diarize_segments is None:
            logger.info("No diarization data, skipping speaker assignment")
            return result

        logger.info("Assigning speakers to segments")

        try:
            result = whisperx.assign_word_speakers(
                diarize_segments,
                result,
            )
            logger.info("Speaker assignment complete")
            return result

        except Exception as e:
            logger.error(f"Speaker assignment failed: {e}")
            logger.warning("Returning result without speaker labels")
            return result

    def process_full_pipeline(
        self,
        audio_path: Path | str,
        language: str | None = None,
        enable_diarization: bool = True,
    ) -> ASRResult:
        """Run complete ASR pipeline with alignment and diarization.

        Args:
            audio_path: Path to audio file
            language: Language code. If None, auto-detect
            enable_diarization: Whether to perform speaker diarization

        Returns:
            ASRResult with segments, speakers, and metadata
        """
        audio_path = Path(audio_path)
        logger.info(f"Starting full ASR pipeline for: {audio_path}")

        # Step 1: Transcribe
        result = self.transcribe(audio_path, language=language)
        detected_language = result["language"]
        segments_raw = result["segments"]

        # Step 2: Align for word-level timestamps
        audio = whisperx.load_audio(str(audio_path))
        result = self.align(segments_raw, audio, detected_language)

        # Step 3: Diarize and assign speakers
        if enable_diarization and self.hf_token:
            diarize_segments = self.diarize(audio_path)
            result = self.assign_speakers(diarize_segments, result)
        else:
            logger.info("Skipping diarization")

        # Step 4: Convert to ASRResult
        asr_result = self._convert_to_asr_result(
            result,
            detected_language,
            len(audio) / 16000,  # Duration in seconds (16kHz sample rate)
        )

        logger.info(
            f"ASR pipeline complete: {asr_result.total_segments} segments, "
            f"{asr_result.speaker_count} speakers"
        )

        return asr_result

    def _convert_to_asr_result(
        self,
        whisperx_result: dict[str, Any],
        language: str,
        duration: float,
    ) -> ASRResult:
        """Convert WhisperX result to ASRResult model.

        Args:
            whisperx_result: Raw WhisperX result
            language: Detected language
            duration: Audio duration in seconds

        Returns:
            Validated ASRResult
        """
        segments = []

        for seg_raw in whisperx_result.get("segments", []):
            # Extract words
            words = []
            for word_raw in seg_raw.get("words", []):
                word = Word(
                    word=word_raw.get("word", ""),
                    start=word_raw.get("start", 0.0),
                    end=word_raw.get("end", 0.0),
                    score=word_raw.get("score"),
                    speaker=word_raw.get("speaker"),
                )
                words.append(word)

            # Create segment
            segment = Segment(
                start=seg_raw.get("start", 0.0),
                end=seg_raw.get("end", 0.0),
                text=seg_raw.get("text", ""),
                speaker=seg_raw.get("speaker"),
                words=words,
            )
            segments.append(segment)

        # Create ASRResult
        asr_result = ASRResult(
            segments=segments,
            language=language,
            audio_duration=duration,
            model_name=self.model_name,
        )

        return asr_result
