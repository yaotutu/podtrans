"""TTS service abstract base class."""

from abc import ABC, abstractmethod
from pathlib import Path

from podtrans.translation.schemas import TranslationResult
from podtrans.tts.schemas import SpeakerConfig, TTSResult


class TTSService(ABC):
    """Abstract base class for TTS services."""

    @abstractmethod
    def convert_format(
        self,
        translation_result: TranslationResult,
        speaker_configs: list[SpeakerConfig] | None = None,
    ) -> dict:
        """Convert TranslationResult to service-specific format.

        Args:
            translation_result: Translation result to convert
            speaker_configs: Optional speaker voice configurations

        Returns:
            Service-specific format (e.g., SoulX JSON)
        """
        pass

    @abstractmethod
    def synthesize(
        self,
        script: dict,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize audio from script.

        Args:
            script: Service-specific script format
            output_path: Where to save the generated audio

        Returns:
            TTS result metadata

        Raises:
            Exception: If synthesis fails
        """
        pass

    def synthesize_from_translation(
        self,
        translation_result: TranslationResult,
        output_path: Path,
        speaker_configs: list[SpeakerConfig] | None = None,
    ) -> TTSResult:
        """Synthesize audio from TranslationResult (convenience method).

        Args:
            translation_result: Translation result
            output_path: Where to save the generated audio
            speaker_configs: Optional speaker voice configurations

        Returns:
            TTS result metadata
        """
        # 1. Convert format
        script = self.convert_format(translation_result, speaker_configs)

        # 2. Synthesize
        return self.synthesize(script, output_path)
