"""Pipeline orchestrator for coordinating ASR, Translation, and TTS stages.

This module provides the PipelineOrchestrator class that manages
the complete podcast translation pipeline without using subprocess calls.
"""

from pathlib import Path
from typing import Optional
import asyncio

from loguru import logger

from podtrans.models import PipelineMetadata, StageStatus
from podtrans.config import get_settings
from podtrans.asr.whisperx_handler import WhisperXHandler
from podtrans.translation.translator import Translator
from podtrans.tts.factory import create_tts_service
from podtrans.tts.schemas import SpeakerConfig
from podtrans.utils.file import write_json


class PipelineOrchestrator:
    """Complete pipeline orchestrator that coordinates ASR, Translation, and TTS stages.

    This class manages the end-to-end podcast translation process without
    using subprocess calls, providing better integration and error handling.
    """

    def __init__(self, output_dir: Path):
        """Initialize the pipeline orchestrator.

        Args:
            output_dir: Directory where all output files will be saved
        """
        settings = get_settings()
        self.settings = settings
        self.output_dir = output_dir

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize stage processors
        self._asr_handler = None
        self._translator = None
        self._tts_service = None

        # Store intermediate results
        self._asr_result = None
        self._translation_result = None
        self._tts_result = None
        self._voice_samples_result = None

    @property
    def asr_handler(self) -> WhisperXHandler:
        """Lazy initialization of ASR handler."""
        if self._asr_handler is None:
            self._asr_handler = WhisperXHandler()
        return self._asr_handler

    @property
    def translator(self) -> Translator:
        """Lazy initialization of translator."""
        if self._translator is None:
            self._translator = Translator(self.settings)
        return self._translator

    @property
    def tts_service(self):
        """Lazy initialization of TTS service."""
        if self._tts_service is None:
            self._tts_service = create_tts_service()
        return self._tts_service

    async def run_pipeline(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        enable_diarization: bool = True,
        source_lang: str = "en",
        target_lang: str = "zh",
        extract_voice_samples: Optional[bool] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        min_quality: Optional[float] = None,
    ) -> PipelineMetadata:
        """Run the complete pipeline (ASR → Translation → TTS → Voice Samples).

        Args:
            audio_path: Path to input audio file
            language: Language code for ASR (auto-detect if None)
            enable_diarization: Whether to perform speaker diarization
            source_lang: Source language for translation
            target_lang: Target language for translation
            extract_voice_samples: Whether to extract voice cloning samples
            min_duration: Minimum sample duration for voice samples (seconds)
            max_duration: Maximum sample duration for voice samples (seconds)
            min_quality: Minimum quality score for voice samples (0-100)

        Returns:
            PipelineMetadata with complete execution information
        """
        pipeline_meta = PipelineMetadata(
            audio_file=str(audio_path),
            output_dir=self.output_dir,
        )

        # Apply default values from settings if not provided
        if extract_voice_samples is None:
            extract_voice_samples = self.settings.voice_sample_extract_enabled
        if min_duration is None:
            min_duration = self.settings.voice_sample_min_duration
        if max_duration is None:
            max_duration = self.settings.voice_sample_max_duration
        if min_quality is None:
            min_quality = self.settings.voice_sample_min_quality

        try:
            # Stage 1: ASR
            await self._run_asr_stage(
                audio_path, language, enable_diarization, pipeline_meta
            )

            # Stage 2: Voice Samples (extracted from ASR result)
            if extract_voice_samples:
                asr_stage = pipeline_meta.get_stage("asr")
                if asr_stage is not None and asr_stage.status == StageStatus.SUCCESS:
                    await self._run_voice_samples_stage(
                        audio_path,
                        min_duration,
                        max_duration,
                        min_quality,
                        self.settings.voice_sample_max_gap,
                        pipeline_meta,
                    )

            # Stage 3: Translation
            asr_stage = pipeline_meta.get_stage("asr")
            if asr_stage is not None and asr_stage.status == StageStatus.SUCCESS:
                await self._run_translation_stage(
                    source_lang, target_lang, pipeline_meta
                )

            # Stage 4: TTS
            translation_stage = pipeline_meta.get_stage("translation")
            if (
                translation_stage is not None
                and translation_stage.status == StageStatus.SUCCESS
            ):
                await self._run_tts_stage(pipeline_meta)

        except Exception as e:
            pipeline_meta.update_stage("pipeline", StageStatus.FAILED, error=str(e))
            logger.exception("Pipeline failed")
            raise

        finally:
            # Save pipeline metadata
            self._save_pipeline_metadata(pipeline_meta)

        return pipeline_meta

    async def _run_asr_stage(
        self,
        audio_path: Path,
        language: Optional[str],
        enable_diarization: bool,
        pipeline_meta: PipelineMetadata,
    ) -> None:
        """Run the ASR stage."""
        logger.info(f"Starting ASR stage for {audio_path}")
        pipeline_meta.update_stage("asr", StageStatus.RUNNING)

        try:
            # Run ASR processing
            asr_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.asr_handler.process_full_pipeline(
                    audio_path=audio_path,
                    language=language,
                    enable_diarization=enable_diarization,
                ),
            )

            # Store result and update metadata
            self._asr_result = asr_result
            pipeline_meta.update_stage(
                "asr",
                StageStatus.SUCCESS,
                segments=asr_result.total_segments,
                speakers=asr_result.speaker_count,
                language=asr_result.language,
            )

            # Save ASR result to file
            asr_file = self.output_dir / "asr_result.json"
            asr_file.write_text(asr_result.model_dump_json(indent=2))

            logger.info(
                f"ASR stage completed: {asr_result.total_segments} segments, "
                f"{asr_result.speaker_count} speakers"
            )

        except Exception as e:
            pipeline_meta.update_stage("asr", StageStatus.FAILED, error=str(e))
            logger.error(f"ASR stage failed: {e}")
            raise

    async def _run_translation_stage(
        self, source_lang: str, target_lang: str, pipeline_meta: PipelineMetadata
    ) -> None:
        """Run the Translation stage."""
        logger.info(f"Starting Translation stage: {source_lang} → {target_lang}")
        pipeline_meta.update_stage("translation", StageStatus.RUNNING)

        try:
            # Run translation processing
            translation_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.translator.translate_asr_result(
                    self._asr_result, source_lang, target_lang
                ),
            )

            # Store result and update metadata
            self._translation_result = translation_result
            pipeline_meta.update_stage(
                "translation",
                StageStatus.SUCCESS,
                segments=translation_result.total_segments,
                speakers=translation_result.speaker_count,
            )

            # Save translation result to file
            trans_file = self.output_dir / "translation_result.json"
            trans_file.write_text(translation_result.model_dump_json(indent=2))

            logger.info(
                f"Translation stage completed: {translation_result.total_segments} segments"
            )

        except Exception as e:
            pipeline_meta.update_stage("translation", StageStatus.FAILED, error=str(e))
            logger.error(f"Translation stage failed: {e}")
            raise

    async def _run_tts_stage(self, pipeline_meta: PipelineMetadata) -> None:
        """Run the TTS stage."""
        logger.info("Starting TTS stage")
        pipeline_meta.update_stage("tts", StageStatus.RUNNING)

        try:
            # Determine output file path
            audio_name = Path(pipeline_meta.audio_file).stem
            output_path = self.output_dir / f"{audio_name}_chinese.wav"

            # Create speaker configs from voice samples if available
            speaker_configs = None
            if self._voice_samples_result:
                speaker_configs = self._create_speaker_configs()

            # Run TTS processing with voice samples if available
            tts_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.tts_service.synthesize_from_translation(
                    self._translation_result, output_path, speaker_configs
                ),
            )

            # Store result and update metadata
            self._tts_result = tts_result
            pipeline_meta.update_stage(
                "tts",
                StageStatus.SUCCESS,
                audio_file=str(output_path),
                duration=tts_result.duration,
            )

            logger.info(f"TTS stage completed: {output_path}")

        except Exception as e:
            pipeline_meta.update_stage("tts", StageStatus.FAILED, error=str(e))
            logger.error(f"TTS stage failed: {e}")
            raise

    async def _run_voice_samples_stage(
        self,
        audio_path: Path,
        min_duration: float,
        max_duration: float,
        min_quality: float,
        max_gap: float,
        pipeline_meta: PipelineMetadata,
    ) -> None:
        """Run the voice samples extraction stage."""
        logger.info("Starting voice samples extraction stage")
        pipeline_meta.update_stage("voice_samples", StageStatus.RUNNING)

        try:
            # Create voice samples directory with audio filename
            audio_name = Path(pipeline_meta.audio_file).stem
            voice_samples_dir = self.output_dir / f"{audio_name}_voice_samples"
            voice_samples_dir.mkdir(exist_ok=True)

            # Extract voice samples using the ASR handler
            voice_samples_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.asr_handler.extract_voice_samples(
                    audio_path=audio_path,
                    asr_result=self._asr_result,
                    min_duration=min_duration,
                    max_duration=max_duration,
                    min_quality=min_quality,
                    max_gap=max_gap,
                    output_dir=voice_samples_dir,
                ),
            )

            # Update the output paths to be relative to the output directory
            for speaker_id, sample in voice_samples_result.speaker_samples.items():
                # Update audio path to be relative to output directory
                sample.audio_path = (
                    voice_samples_dir / speaker_id / sample.audio_path.name
                )

            # Save voice samples result
            self._voice_samples_result = voice_samples_result

            # Save detailed summary
            summary_file = voice_samples_dir / "extraction_summary.json"
            extraction_summary = {
                "extraction_time": voice_samples_result.extraction_time.isoformat(),
                "source_audio": str(audio_path),
                "parameters": {
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                    "min_quality": min_quality,
                    "max_gap": max_gap,
                },
                "summary": voice_samples_result.extraction_summary,
                "samples": {
                    speaker_id: {
                        "quality_score": sample.quality_score,
                        "duration": sample.duration,
                        "words_count": sample.words_count,
                        "recommended_use": sample.recommended_use,
                        "audio_path": str(
                            sample.audio_path.relative_to(self.output_dir)
                        ),
                    }
                    for speaker_id, sample in voice_samples_result.speaker_samples.items()
                },
            }

            write_json(extraction_summary, summary_file, indent=2)

            # Update pipeline metadata
            pipeline_meta.update_stage(
                "voice_samples",
                StageStatus.SUCCESS,
                output_files={
                    "voice_samples_dir": str(
                        voice_samples_dir.relative_to(self.output_dir)
                    ),
                    "extraction_summary": str(
                        summary_file.relative_to(self.output_dir)
                    ),
                    "samples_count": voice_samples_result.total_samples,
                    "speakers_count": voice_samples_result.total_speakers,
                },
            )

            logger.info(
                f"Voice samples extraction completed: "
                f"{voice_samples_result.total_samples} samples from {voice_samples_result.total_speakers} speakers"
            )

        except Exception as e:
            pipeline_meta.update_stage(
                "voice_samples", StageStatus.FAILED, error=str(e)
            )
            logger.error(f"Voice samples extraction stage failed: {e}")
            raise

    def _create_speaker_configs(self) -> list[SpeakerConfig]:
        """Create speaker configs from voice samples for TTS.

        Returns:
            List of SpeakerConfig objects with voice sample paths
        """
        speaker_configs = []

        if not self._voice_samples_result:
            return speaker_configs

        for (
            speaker_id,
            voice_sample,
        ) in self._voice_samples_result.speaker_samples.items():
            config = SpeakerConfig(
                speaker_id=speaker_id,
                voice_sample=voice_sample.audio_path,
                voice_description=voice_sample.recommended_use,
            )
            speaker_configs.append(config)

        logger.info(
            f"Created {len(speaker_configs)} speaker configs from voice samples"
        )
        return speaker_configs

    def _save_pipeline_metadata(self, pipeline_meta: PipelineMetadata) -> None:
        """Save pipeline metadata to file."""
        try:
            metadata_file = self.output_dir / "pipeline_metadata.json"
            metadata_file.write_text(pipeline_meta.model_dump_json(indent=2))
            logger.info(f"Pipeline metadata saved to {metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save pipeline metadata: {e}")

    def get_time_analysis(self) -> dict:
        """Get detailed time analysis of all completed stages.

        Returns:
            Dictionary with timing information for each stage
        """
        analysis = {}

        if hasattr(self, "_asr_result") and self._asr_result:
            # Note: ASR timing would need to be tracked during processing
            # This is a placeholder for future enhancement
            analysis["asr"] = {"duration": 0.0, "status": "completed"}

        if hasattr(self, "_translation_result") and self._translation_result:
            # Note: Translation timing would need to be tracked during processing
            # This is a placeholder for future enhancement
            analysis["translation"] = {"duration": 0.0, "status": "completed"}

        if hasattr(self, "_tts_result") and self._tts_result:
            analysis["tts"] = {
                "duration": self._tts_result.duration or 0.0,
                "status": "completed",
            }

        return analysis
