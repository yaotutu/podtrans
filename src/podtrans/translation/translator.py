"""Translation handler using OpenAI-compatible API (DashScope)."""

import json
from pathlib import Path

import tiktoken
from loguru import logger
from openai import OpenAI

from podtrans.asr.schemas import ASRResult, Segment
from podtrans.config import Settings
from podtrans.translation.cache import TranslationCache
from podtrans.translation.schemas import TranslatedSegment, TranslationResult


class Translator:
    """Translator using OpenAI-compatible API to translate ASR results."""

    def __init__(
        self,
        settings: Settings,
        enable_cache: bool = True,
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize translator with settings.

        Args:
            settings: Application settings
            enable_cache: Whether to enable translation cache (default: True)
            cache_dir: Cache directory (default: ./data/cache/translations)
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
        self.use_json_mode = settings.translation_use_json_mode

        # Initialize cache
        self.enable_cache = enable_cache
        if enable_cache:
            self.cache = TranslationCache(cache_dir)
            logger.info("Translation cache enabled")
        else:
            self.cache = None
            logger.info("Translation cache disabled")

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
            f"max_tokens={self.max_tokens}, "
            f"use_json_mode={self.use_json_mode}"
        )

    def _get_cached_translations(
        self,
        segments: list[Segment],
        source_lang: str,
        target_lang: str,
    ) -> tuple[list[str | None], list[Segment]]:
        """Get cached translations and uncached segments.

        Args:
            segments: All segments to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Tuple of (cached_translations, uncached_segments)
        """
        if not self.cache:
            return [None] * len(segments), segments

        cached_translations: list[str | None] = []
        uncached_segments: list[Segment] = []

        for seg in segments:
            cached = self.cache.get(seg.text, source_lang, target_lang, self.model)
            cached_translations.append(cached)

            if cached is None:
                uncached_segments.append(seg)

        return cached_translations, uncached_segments

    def _build_translated_segments_from_cache(
        self,
        segments: list[Segment],
        cached_translations: list[str | None],
    ) -> list[TranslatedSegment]:
        """Build TranslatedSegment objects from cached translations.

        Args:
            segments: Original segments
            cached_translations: Cached translations (all non-None)

        Returns:
            List of TranslatedSegment objects
        """
        results = []
        for seg, trans in zip(segments, cached_translations):
            if trans is not None:
                results.append(
                    TranslatedSegment(
                        start=seg.start,
                        end=seg.end,
                        original_text=seg.text,
                        translated_text=trans,
                        speaker=seg.speaker,
                    )
                )

        return results

    def _merge_cached_and_new_translations(
        self,
        segments: list[Segment],
        cached_translations: list[str | None],
        uncached_results: list[TranslatedSegment],
    ) -> list[TranslatedSegment]:
        """Merge cached and newly translated results.

        Args:
            segments: Original segments
            cached_translations: Cached translations (with None for uncached)
            uncached_results: Newly translated segments

        Returns:
            Complete list of TranslatedSegment objects
        """
        results = []
        uncached_idx = 0

        for seg, cached in zip(segments, cached_translations):
            if cached is not None:
                # Use cached translation
                results.append(
                    TranslatedSegment(
                        start=seg.start,
                        end=seg.end,
                        original_text=seg.text,
                        translated_text=cached,
                        speaker=seg.speaker,
                    )
                )
            else:
                # Use newly translated result
                if uncached_idx < len(uncached_results):
                    results.append(uncached_results[uncached_idx])
                    uncached_idx += 1

        return results

    def get_cache_stats(self) -> dict | None:
        """Get cache statistics.

        Returns:
            Cache stats dictionary or None if cache disabled
        """
        if self.cache:
            return self.cache.get_stats()
        return None

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
        """Translate a list of segments using smart batching and caching.

        Args:
            segments: List of ASR segments to translate
            source_lang: Source language code (default: "en")
            target_lang: Target language code (default: "zh")

        Returns:
            List of translated segments with timing and speaker info

        Raises:
            Exception: If translation fails after max retries
        """
        # Check cache if enabled
        if self.enable_cache and self.cache:
            cached_translations, uncached_segments = self._get_cached_translations(
                segments, source_lang, target_lang
            )

            cache_hits = sum(1 for t in cached_translations if t is not None)
            logger.info(
                f"Cache: {cache_hits}/{len(segments)} hits "
                f"({cache_hits / len(segments) * 100:.1f}%)"
            )

            # If all cached, return immediately
            if not uncached_segments:
                logger.info("All segments retrieved from cache")
                return self._build_translated_segments_from_cache(
                    segments, cached_translations
                )
        else:
            uncached_segments = segments
            cached_translations = [None] * len(segments)

        # Create smart batches for uncached segments
        batches = self._create_smart_batches(uncached_segments)

        logger.info(
            f"Smart batching: {len(uncached_segments)} segments -> {len(batches)} batches "
            f"(max {self.max_tokens} tokens/batch)"
        )

        # Track newly translated segments for caching
        newly_translated: list[tuple[str, str]] = []

        # Process each batch
        uncached_results: list[TranslatedSegment] = []
        for batch_idx, batch in enumerate(batches, 1):
            batch_tokens = sum(self._estimate_tokens(seg.text) for seg in batch)
            logger.info(
                f"Translating batch {batch_idx}/{len(batches)}: "
                f"{len(batch)} segments, ~{batch_tokens} tokens"
            )

            batch_results = self._translate_batch(batch, source_lang, target_lang)
            uncached_results.extend(batch_results)

            # Collect for caching
            for result in batch_results:
                newly_translated.append((result.original_text, result.translated_text))

        # Cache newly translated segments
        if self.enable_cache and self.cache and newly_translated:
            self.cache.set_batch(
                newly_translated, source_lang, target_lang, self.model
            )
            logger.debug(f"Cached {len(newly_translated)} new translations")

        # Merge cached and newly translated results
        if self.enable_cache and any(t is not None for t in cached_translations):
            return self._merge_cached_and_new_translations(
                segments, cached_translations, uncached_results
            )
        else:
            return uncached_results

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

                # Build API call parameters
                api_params = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": self._get_system_prompt(),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                }

                # Add response_format only if JSON mode is enabled
                if self.use_json_mode:
                    api_params["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**api_params)

                # Parse response
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from API")

                # Parse translations based on mode
                if self.use_json_mode:
                    translations = self._parse_json_response(content)
                else:
                    translations = self._parse_text_response(content, len(segments))

                # Handle count mismatch with single-segment retry
                if len(translations) != len(segments):
                    missing_count = len(segments) - len(translations)
                    missing_indices = list(range(len(translations), len(segments)))

                    logger.warning(
                        f"Translation count mismatch: expected {len(segments)}, "
                        f"got {len(translations)}. Missing {missing_count} segments."
                    )
                    logger.warning(f"Missing segment indices: {missing_indices}")

                    # Log missing segment texts (first 50 chars each)
                    for idx in missing_indices:
                        logger.warning(
                            f"  Missing segment [{idx}]: {segments[idx].text[:50]}..."
                        )

                    # Retry missing segments individually
                    translations = self._retry_missing_segments(
                        segments, translations, source_lang, target_lang
                    )

                # Build translated segments
                translated_segments = []
                for i, (seg, trans) in enumerate(zip(segments, translations)):
                    translated_segments.append(
                        TranslatedSegment(
                            start=seg.start,
                            end=seg.end,
                            original_text=seg.text,
                            translated_text=trans,
                            speaker=seg.speaker,
                        )
                    )

                logger.info(
                    f"Successfully translated {len(translated_segments)} segments"
                )
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

    def _get_system_prompt(self) -> str:
        """Get system prompt based on JSON mode.

        Returns:
            System prompt string with few-shot examples
        """
        if self.use_json_mode:
            return """You are a professional podcast translator specializing in English to Chinese translation.

Translation Guidelines:
- Keep translations natural, fluent, and suitable for podcast listening
- Use colloquial expressions适合口语的表达
- Preserve the speaker's tone and style
- CRITICAL: Return EXACTLY the same number of translations as input segments

Output Format: JSON object with 'translations' array

Few-shot Examples:

Example 1 (Casual conversation):
Input: ["Hello everyone, welcome to the show.", "Today we're discussing AI technology."]
Output: {"translations": ["大家好,欢迎收听本期节目。", "今天我们要讨论人工智能技术。"]}

Example 2 (Technical discussion):
Input: ["The algorithm uses deep learning.", "It processes data in real-time.", "Performance has improved significantly."]
Output: {"translations": ["该算法采用深度学习技术。", "它能实时处理数据。", "性能已经得到显著提升。"]}

Example 3 (Interview style):
Input: ["That's a great question.", "Let me explain my perspective.", "I think the key issue is trust."]
Output: {"translations": ["这是个很好的问题。", "让我来解释一下我的观点。", "我认为关键问题在于信任。"]}

Now translate the following podcast segments:"""
        else:
            return """You are a professional podcast translator specializing in English to Chinese translation.

Translation Guidelines:
- Keep translations natural, fluent, and suitable for podcast listening
- Use colloquial expressions 适合口语的表达
- Preserve the speaker's tone and style
- CRITICAL: Return EXACTLY the same number of translations as input segments

Output Format: One translation per segment, separated by '|||' delimiter

Few-shot Examples:

Example 1:
Input: ["Hello everyone.", "Today we discuss AI."]
Output: 大家好。|||今天我们讨论人工智能。

Example 2:
Input: ["The market is volatile.", "Investors are cautious.", "We'll see what happens."]
Output: 市场波动较大。|||投资者持谨慎态度。|||我们拭目以待。

Now translate the following podcast segments:"""

    def _parse_json_response(self, content: str) -> list[str]:
        """Parse JSON response to extract translations.

        Args:
            content: JSON response content

        Returns:
            List of translations

        Raises:
            json.JSONDecodeError: If content is not valid JSON
        """
        translations_data = json.loads(content)
        translations = translations_data.get("translations", [])
        return translations

    def _parse_text_response(self, content: str, expected_count: int) -> list[str]:
        """Parse text response (non-JSON mode) to extract translations.

        Args:
            content: Text response content
            expected_count: Expected number of translations

        Returns:
            List of translations
        """
        # Try delimiter-based parsing first
        if "|||" in content:
            translations = [t.strip() for t in content.split("|||")]
            return [t for t in translations if t]  # Filter empty strings

        # Fallback: split by newlines
        lines = [line.strip() for line in content.split("\n")]
        translations = [line for line in lines if line]

        return translations

    def _retry_missing_segments(
        self,
        segments: list[Segment],
        translations: list[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        """Retry translating missing segments individually.

        Args:
            segments: All segments
            translations: Already translated segments
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Complete list of translations (with retried segments)
        """
        missing_count = len(segments) - len(translations)

        if missing_count == 0:
            return translations

        logger.info(
            f"Retrying {missing_count} missing segments individually "
            "to ensure 100% coverage..."
        )

        missing_segments = segments[len(translations) :]
        recovered_translations = []

        for i, segment in enumerate(missing_segments, start=1):
            try:
                # Translate single segment
                logger.debug(
                    f"Retrying segment {i}/{missing_count}: {segment.text[:30]}..."
                )

                single_result = self._translate_single_segment(
                    segment, source_lang, target_lang
                )

                if single_result:
                    recovered_translations.append(single_result)
                    logger.info(f"✓ Recovered segment {i}/{missing_count}")
                else:
                    # Fallback: use original text with marker
                    fallback = f"[UNTRANSLATED] {segment.text}"
                    recovered_translations.append(fallback)
                    logger.error(
                        f"✗ Failed to translate segment {i}/{missing_count}, "
                        "using original text"
                    )

            except Exception as e:
                # Ultimate fallback
                fallback = f"[ERROR] {segment.text}"
                recovered_translations.append(fallback)
                logger.error(f"✗ Error retrying segment {i}/{missing_count}: {e}")

        final_translations = translations + recovered_translations
        logger.info(
            f"Recovery complete: {len(final_translations)}/{len(segments)} segments"
        )

        return final_translations

    def _translate_single_segment(
        self,
        segment: Segment,
        source_lang: str,
        target_lang: str,
    ) -> str | None:
        """Translate a single segment.

        Args:
            segment: Segment to translate
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Translation string, or None if failed
        """
        prompt = f"""Translate the following {source_lang} text to {target_lang}:

"{segment.text}"

Return ONLY the translation, no explanations."""

        try:
            api_params = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate naturally and fluently.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }

            response = self.client.chat.completions.create(**api_params)
            content = response.choices[0].message.content

            if content:
                return content.strip()

        except Exception as e:
            logger.debug(f"Single segment translation failed: {e}")

        return None

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

        if self.use_json_mode:
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
        else:
            prompt = f"""Translate the following {len(segments)} {source_lang} podcast \
segments to {target_lang}.

IMPORTANT: You MUST return EXACTLY {len(segments)} translations in the same order.
Separate each translation with '|||' delimiter.

Input segments:
{json.dumps(texts, ensure_ascii=False, indent=2)}

Expected output format (MUST contain exactly {len(segments)} items separated by |||):
Translation 1|||Translation 2|||Translation 3|||...
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
