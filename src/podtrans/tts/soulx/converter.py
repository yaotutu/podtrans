"""SoulX-Podcast format converter."""

from loguru import logger

from podtrans.translation.schemas import TranslationResult
from podtrans.tts.schemas import SpeakerConfig


class SoulXConverter:
    """Convert TranslationResult to SoulX-Podcast JSON format."""

    def convert(
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
        # 1. Create speaker ID mapping (SPEAKER_00 -> S1, SPEAKER_01 -> S2, etc.)
        speaker_mapping = self._create_speaker_mapping(translation_result)

        # 2. Build speakers config
        speakers_dict = self._build_speakers_dict(
            speaker_mapping, speaker_configs or []
        )

        # 3. Build text array
        text_array = self._build_text_array(translation_result, speaker_mapping)

        result = {"speakers": speakers_dict, "text": text_array}

        logger.info(
            f"Converted {len(text_array)} segments with {len(speakers_dict)} speakers"
        )
        return result

    def _create_speaker_mapping(
        self, translation_result: TranslationResult
    ) -> dict[str, str]:
        """Create mapping from original speaker IDs to SoulX format.

        Args:
            translation_result: Translation result

        Returns:
            Mapping dict (e.g., {"SPEAKER_00": "S1", "SPEAKER_01": "S2"})
        """
        unique_speakers = set()
        for seg in translation_result.segments:
            if seg.speaker:
                unique_speakers.add(seg.speaker)

        # Sort for consistency
        sorted_speakers = sorted(unique_speakers)

        # Create mapping: SPEAKER_00 -> S1, SPEAKER_01 -> S2, etc.
        mapping = {
            speaker_id: f"S{i + 1}" for i, speaker_id in enumerate(sorted_speakers)
        }

        logger.debug(f"Speaker mapping: {mapping}")
        return mapping

    def _build_speakers_dict(
        self, speaker_mapping: dict[str, str], speaker_configs: list[SpeakerConfig]
    ) -> dict[str, dict]:
        """Build speakers configuration dict.

        Args:
            speaker_mapping: Speaker ID mapping
            speaker_configs: Speaker voice configurations

        Returns:
            Speakers dict for SoulX format
        """
        # Create config lookup by original speaker ID
        config_lookup = {
            config.speaker_id: config for config in speaker_configs if config.speaker_id
        }

        speakers_dict = {}
        for original_id, soulx_id in speaker_mapping.items():
            config = config_lookup.get(original_id)
            speaker_entry = {}

            if config and config.voice_sample:
                speaker_entry["prompt_audio"] = str(config.voice_sample)

            if config and config.voice_description:
                speaker_entry["prompt_text"] = config.voice_description

            speakers_dict[soulx_id] = speaker_entry

        return speakers_dict

    def _build_text_array(
        self, translation_result: TranslationResult, speaker_mapping: dict[str, str]
    ) -> list[list[str]]:
        """Build text array.

        Args:
            translation_result: Translation result
            speaker_mapping: Speaker ID mapping

        Returns:
            Text array in SoulX format
        """
        text_array = []
        for seg in translation_result.segments:
            soulx_speaker_id = speaker_mapping.get(seg.speaker, "S1")
            text_array.append([soulx_speaker_id, seg.translated_text])

        return text_array
