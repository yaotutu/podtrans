"""Translation cache system for cost optimization and speed improvement.

This module provides a disk-based cache for translations to avoid redundant API calls.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from loguru import logger


class TranslationCache:
    """Disk-based translation cache.

    Cache keys are generated from:
    - Source text
    - Source language
    - Target language
    - Model name

    Cache is stored as JSON files in the cache directory.
    """

    def __init__(self, cache_dir: Path | str | None = None):
        """Initialize translation cache.

        Args:
            cache_dir: Directory to store cache files.
                      Defaults to ./data/cache/translations
        """
        if cache_dir is None:
            from ..config import get_settings
            settings = get_settings()
            cache_dir = settings.get_cache_dir() / "translations"
        else:
            cache_dir = Path(cache_dir)

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Stats
        self._hits = 0
        self._misses = 0

        logger.debug(f"Translation cache initialized at {self.cache_dir}")

    def _generate_key(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        model: str,
    ) -> str:
        """Generate cache key from parameters.

        Args:
            text: Source text
            source_lang: Source language code
            target_lang: Target language code
            model: Model name

        Returns:
            SHA256 hash as hex string
        """
        key_string = f"{text}:{source_lang}:{target_lang}:{model}"
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache entry.

        Args:
            key: Cache key (hash)

        Returns:
            Path to cache file
        """
        # Use first 2 chars as subdirectory for better file system performance
        subdir = key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)

        return cache_subdir / f"{key}.json"

    def get(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        model: str,
    ) -> str | None:
        """Get translation from cache.

        Args:
            text: Source text
            source_lang: Source language code
            target_lang: Target language code
            model: Model name

        Returns:
            Cached translation if exists, None otherwise
        """
        key = self._generate_key(text, source_lang, target_lang, model)
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            self._misses += 1
            logger.debug(f"Cache miss for text: {text[:30]}...")
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                cache_data = json.load(f)

            # Validate cache data
            if "translation" not in cache_data:
                logger.warning(f"Invalid cache entry: {cache_path}")
                self._misses += 1
                return None

            self._hits += 1
            logger.debug(f"Cache hit for text: {text[:30]}...")
            return cache_data["translation"]

        except Exception as e:
            logger.warning(f"Failed to read cache {cache_path}: {e}")
            self._misses += 1
            return None

    def set(
        self,
        text: str,
        translation: str,
        source_lang: str,
        target_lang: str,
        model: str,
    ) -> None:
        """Save translation to cache.

        Args:
            text: Source text
            translation: Translated text
            source_lang: Source language code
            target_lang: Target language code
            model: Model name
        """
        key = self._generate_key(text, source_lang, target_lang, model)
        cache_path = self._get_cache_path(key)

        cache_data = {
            "text": text,
            "translation": translation,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0",
        }

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Cached translation for text: {text[:30]}...")

        except Exception as e:
            logger.warning(f"Failed to write cache {cache_path}: {e}")

    def get_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        model: str,
    ) -> tuple[list[str | None], list[str]]:
        """Get multiple translations from cache.

        Args:
            texts: List of source texts
            source_lang: Source language code
            target_lang: Target language code
            model: Model name

        Returns:
            Tuple of (cached_translations, uncached_texts)
            - cached_translations: List with cached values or None
            - uncached_texts: List of texts that need translation
        """
        cached_translations: list[str | None] = []
        uncached_texts: list[str] = []

        for text in texts:
            cached = self.get(text, source_lang, target_lang, model)
            cached_translations.append(cached)

            if cached is None:
                uncached_texts.append(text)

        return cached_translations, uncached_texts

    def set_batch(
        self,
        text_translation_pairs: list[tuple[str, str]],
        source_lang: str,
        target_lang: str,
        model: str,
    ) -> None:
        """Save multiple translations to cache.

        Args:
            text_translation_pairs: List of (text, translation) tuples
            source_lang: Source language code
            target_lang: Target language code
            model: Model name
        """
        for text, translation in text_translation_pairs:
            self.set(text, translation, source_lang, target_lang, model)

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of cache files deleted
        """
        count = 0
        for cache_file in self.cache_dir.rglob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete cache file {cache_file}: {e}")

        logger.info(f"Cleared {count} cache entries")
        return count

    def get_stats(self) -> dict[str, int | float]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_accesses = self._hits + self._misses
        hit_rate = self._hits / total_accesses if total_accesses > 0 else 0.0

        # Count cache files
        cache_files = list(self.cache_dir.rglob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_accesses": total_accesses,
            "hit_rate": hit_rate,
            "cache_entries": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
        logger.debug("Cache statistics reset")
