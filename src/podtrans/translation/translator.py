"""Translation handler using OpenAI-compatible API (DashScope)."""

import json
from pathlib import Path

import tiktoken
from loguru import logger
from openai import OpenAI

from podtrans.asr.schemas import ASRResult, Segment
from podtrans.config import Settings
from podtrans.translation.schemas import TranslatedSegment, TranslationResult


class Translator:
    """Translator using OpenAI-compatible API to translate ASR results."""

    def __init__(self, settings: Settings) -> None:
        """Initialize translator with settings.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.translation_api_base,
        )
        self.model = settings.translation_model
        self.max_retries = settings.max_retries
        self.max_tokens = settings.translation_max_tokens
        self.max_segments_per_batch = settings.translation_max_segments_per_batch

        # Initialize tokenizer (use cl100k_base for general purpose)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to a simpler estimation if tiktoken fails
            self.tokenizer = None
            logger.warning("Failed to load tiktoken, using character-based estimation")

        logger.info(
            f"Initialized Translator with model={self.model}, "
            f"base_url={settings.translation_api_base}, "
            f"max_tokens={self.max_tokens}"
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback: rough estimation (1 char ≈ 0.5 tokens for mixed EN/CN)
            return len(text) // 2

    def _create_smart_batches(self, segments: list[Segment]) -> list[list[Segment]]:
        """Create batches based on token count instead of fixed segment count.

        Args:
            segments: All segments to batch

        Returns:
            List of batches, where each batch is under max_tokens limit
        """
        batches: list[list[Segment]] = []
        current_batch: list[Segment] = []
        current_tokens = 0

        # Reserve tokens for system prompt and response (estimated)
        system_overhead = 500  # System prompt
        response_overhead_per_segment = 100  # Chinese output per segment

        for seg in segments:
            seg_tokens = self._estimate_tokens(seg.text)
            seg_total = seg_tokens + response_overhead_per_segment

            # Check if adding this segment would exceed limits
            estimated_total = current_tokens + seg_total + system_overhead
            exceeds_tokens = estimated_total > self.max_tokens
            exceeds_segments = len(current_batch) >= self.max_segments_per_batch

            if (exceeds_tokens or exceeds_segments) and current_batch:
                # Start new batch
                batches.append(current_batch)
                current_batch = [seg]
                current_tokens = seg_total
            else:
                # Add to current batch
                current_batch.append(seg)
                current_tokens += seg_total

        # Add remaining segments
        if current_batch:
            batches.append(current_batch)

        return batches

    def translate_segments(
        self,
        segments: list[Segment],
        source_lang: str = "en",
        target_lang: str = "zh",
    ) -> list[TranslatedSegment]:
        """Translate a list of segments using smart batching.

        Args:
            segments: List of ASR segments to translate
            source_lang: Source language code (default: "en")
            target_lang: Target language code (default: "zh")

        Returns:
            List of translated segments with timing and speaker info

        Raises:
            Exception: If translation fails after max retries
        """
        # Create smart batches based on token count
        batches = self._create_smart_batches(segments)

        logger.info(
            f"Smart batching: {len(segments)} segments -> {len(batches)} batches "
            f"(max {self.max_tokens} tokens/batch)"
        )

        translated_segments: list[TranslatedSegment] = []

        # Process each batch
        for batch_idx, batch in enumerate(batches, 1):
            batch_tokens = sum(self._estimate_tokens(seg.text) for seg in batch)
            logger.info(
                f"Translating batch {batch_idx}/{len(batches)}: "
                f"{len(batch)} segments, ~{batch_tokens} tokens"
            )

            batch_results = self._translate_batch(batch, source_lang, target_lang)
            translated_segments.extend(batch_results)

        return translated_segments

    def _translate_batch(
        self,
        segments: list[Segment],
        source_lang: str,
        target_lang: str,
    ) -> list[TranslatedSegment]:
        """Translate a batch of segments.

        Args:
            segments: Batch of segments to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translated segments

        Raises:
            Exception: If translation fails after max retries
        """
        # Prepare batch prompt
        prompt = self._build_batch_prompt(segments, source_lang, target_lang)

        # Call API with retries
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"API call attempt {attempt + 1}/{self.max_retries}")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a professional podcast translator. "
                                "Translate the provided English podcast segments "
                                "to Chinese. "
                                "Keep the translation natural, fluent, and "
                                "suitable for podcast listening. "
                                "IMPORTANT: You MUST return EXACTLY the same "
                                "number of translations as input segments. "
                                "Return ONLY a JSON object with a 'translations' "
                                "array in the exact order as input."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )

                # Parse response
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from API")

                translations_data = json.loads(content)
                translations = translations_data.get("translations", [])

                # Handle count mismatch - accept partial results
                if len(translations) != len(segments):
                    missing_count = len(segments) - len(translations)
                    logger.warning(
                        f"Translation count mismatch: expected {len(segments)}, "
                        f"got {len(translations)}. "
                        f"{missing_count} segments will be skipped."
                    )

                # Build translated segments (only for available translations)
                translated_segments = []
                for i, trans in enumerate(translations):
                    if i < len(segments):
                        translated_segments.append(
                            TranslatedSegment(
                                start=segments[i].start,
                                end=segments[i].end,
                                original_text=segments[i].text,
                                translated_text=trans,
                                speaker=segments[i].speaker,
                            )
                        )

                logger.info(f"Successfully translated {len(segments)} segments")
                return translated_segments

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Translation attempt {attempt + 1}/{self.max_retries} failed: "
                    f"Invalid JSON response - {e}"
                )
                if attempt == self.max_retries - 1:
                    logger.error("Max retries reached, translation failed")
                    raise
            except Exception as e:
                logger.warning(
                    f"Translation attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )
                if attempt == self.max_retries - 1:
                    logger.error("Max retries reached, translation failed")
                    raise

        # This should never be reached due to the raise in the except block
        raise RuntimeError("Unexpected error in translation")

    def _build_batch_prompt(
        self,
        segments: list[Segment],
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Build prompt for batch translation.

        Args:
            segments: Segments to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Formatted prompt string
        """
        texts = [seg.text for seg in segments]
        prompt = f"""Translate the following {len(segments)} {source_lang} podcast \
segments to {target_lang}.

IMPORTANT: You MUST return EXACTLY {len(segments)} translations in the same order.

Input segments:
{json.dumps(texts, ensure_ascii=False, indent=2)}

Expected output format (MUST contain exactly {len(segments)} items):
{{
  "translations": [
    "Translation 1",
    "Translation 2",
    ...
  ]
}}
"""
        return prompt

    def translate_asr_result(
        self,
        asr_result: ASRResult,
        source_lang: str = "en",
        target_lang: str = "zh",
    ) -> TranslationResult:
        """Translate complete ASR result.

        Args:
            asr_result: ASR result to translate
            source_lang: Source language code (default: "en")
            target_lang: Target language code (default: "zh")

        Returns:
            Complete translation result
        """
        logger.info(
            f"Starting translation of {asr_result.total_segments} segments "
            f"from {source_lang} to {target_lang}"
        )

        translated_segments = self.translate_segments(
            asr_result.segments, source_lang, target_lang
        )

        result = TranslationResult(
            segments=translated_segments,
            source_language=source_lang,
            target_language=target_lang,
            model_name=self.model,
            total_duration=asr_result.audio_duration,
        )

        logger.info(
            f"Translation completed: {result.total_segments} segments, "
            f"{result.speaker_count} speakers"
        )
        return result

    def save_result(
        self,
        result: TranslationResult,
        output_path: Path,
        save_bilingual: bool = True,
    ) -> None:
        """Save translation result to files.

        Args:
            result: Translation result to save
            output_path: Output file path (without extension)
            save_bilingual: Whether to save bilingual text file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = output_path.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                result.model_dump(),
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"Saved translation JSON to {json_path}")

        # Save Chinese-only text
        zh_path = output_path.with_suffix(".zh.txt")
        with open(zh_path, "w", encoding="utf-8") as f:
            f.write(result.to_chinese_text(include_speakers=True))
        logger.info(f"Saved Chinese text to {zh_path}")

        # Save bilingual text
        if save_bilingual:
            bilingual_path = output_path.with_suffix(".bilingual.txt")
            with open(bilingual_path, "w", encoding="utf-8") as f:
                f.write(result.to_bilingual_text(include_speakers=True))
            logger.info(f"Saved bilingual text to {bilingual_path}")

    def load_asr_result(self, asr_json_path: Path) -> ASRResult:
        """Load ASR result from JSON file.

        Args:
            asr_json_path: Path to ASR JSON file

        Returns:
            Loaded ASR result
        """
        with open(asr_json_path, encoding="utf-8") as f:
            data = json.load(f)
        return ASRResult(**data)
