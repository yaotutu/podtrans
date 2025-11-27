"""SoulX-Podcast HTTP API client."""

from pathlib import Path

import httpx
from loguru import logger

from podtrans.config import Settings
from podtrans.translation.schemas import TranslationResult
from podtrans.tts.base import TTSService
from podtrans.tts.schemas import SpeakerConfig, TTSResult
from podtrans.tts.soulx.converter import SoulXConverter


class SoulXClient(TTSService):
    """SoulX-Podcast TTS service client."""

    def __init__(self, settings: Settings) -> None:
        """Initialize SoulX client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.api_url = settings.soulx_api_url
        self.timeout = settings.soulx_timeout
        self.converter = SoulXConverter()

        logger.info(f"Initialized SoulXClient with API URL: {self.api_url}")

    def convert_format(
        self,
        translation_result: TranslationResult,
        speaker_configs: list[SpeakerConfig] | None = None,
    ) -> dict:
        """Convert TranslationResult to SoulX format.

        Args:
            translation_result: Translation result to convert
            speaker_configs: Optional speaker voice configurations

        Returns:
            SoulX-Podcast compatible JSON dict
        """
        return self.converter.convert(translation_result, speaker_configs)

    def synthesize(
        self,
        script: dict,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize audio from SoulX script via HTTP API.

        Args:
            script: SoulX-format script
            output_path: Where to save the generated audio

        Returns:
            TTS result metadata

        Raises:
            httpx.HTTPError: If API request fails
            Exception: If synthesis fails
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Calling SoulX API: {self.api_url}")
        logger.debug(f"Script: {len(script.get('text', []))} segments")

        try:
            # Call SoulX API
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_url}/synthesize",
                    json=script,
                )
                response.raise_for_status()

                # Save audio file
                with open(output_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"Audio saved to {output_path}")

                # Return result metadata
                return TTSResult(
                    audio_path=output_path,
                    format="wav",
                    service="soulx",
                    segments_count=len(script.get("text", [])),
                )

        except httpx.HTTPError as e:
            logger.error(f"SoulX API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            raise
