# Changelog

All notable changes to this project will be documented in this file.

## [v0.3.0] - 2025-11-27

### Added
- **Translation Cache System**: Disk-based caching with SHA256 hashing for significant performance improvement (6000x speedup on repeated translations)
  - New file: `src/podtrans/translation/cache.py`
  - Configurable via `TRANSLATION_ENABLE_CACHE` environment variable
  - Cache stored in `data/cache/translations/` with subdirectory organization
- **Quality Assessment System**: Automatic translation quality scoring and reporting
  - New file: `src/podtrans/translation/quality.py`
  - Quality metrics: completeness, reliability, speaker consistency, length anomalies
  - Quality grading: A+ (95-100), A (85-95), B (70-85), C (60-70), D (50-60), F (<50)
  - Markdown report generation
- **Model Comparison Tool**: Script to benchmark different translation models
  - New file: `scripts/compare_models.py`
  - Compares quality, speed, cost, and cache hit rates
  - Automatic model recommendation based on quality score

### Changed
- **Enhanced Translation Prompts**: Added few-shot learning examples to system prompts
  - Modified: `src/podtrans/translation/translator.py`
  - Improved format compliance with 3 example scenarios
- **Translator Integration**: Integrated caching system into Translator class
  - Cache-first strategy for segment translation
  - Cache hit/miss tracking and logging

### Fixed
- Fixed `generate_quality_report()` accessing non-existent `result.metadata` field

### Performance
- Translation with cache: 0.02s (vs 120s without cache)
- Cache hit rate: 100% on repeated translations
- Quality score: 92.5/100 (A grade) with 100% completeness

### Documentation
- Added test report: `docs/translation_v0.3.0_test_report.md`
- Updated exports in `src/podtrans/translation/__init__.py`

## [v0.2.0] - 2025-11-26

### Added
- Single-segment retry mechanism for failed translations
- Improved error handling and logging

### Fixed
- Resolved segment loss issues (reduced from 2-3% to ~0%)

## [v0.1.0] - 2025-11-25

### Added
- Initial release
- ASR module (WhisperX + pyannote.audio)
- Translation module (DashScope/Qwen)
- TTS module (SoulX-Podcast integration)
- CLI interface
- Basic pipeline orchestration
