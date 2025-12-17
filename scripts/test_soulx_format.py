"""Test SoulX format conversion."""

import json
from pathlib import Path

from podtrans.translation.schemas import TranslationResult
from podtrans.tts.soulx.converter import SoulXConverter
from podtrans.utils.file import read_json

# Load translation result
translation_json = Path("output/demo/translation_result.json")
translation_data = read_json(translation_json)
translation_result = TranslationResult(**translation_data)

print(f"Loaded {translation_result.total_segments} segments")
print(f"Speakers: {translation_result.speaker_count}")

# Convert to SoulX format
converter = SoulXConverter()
soulx_script = converter.convert(translation_result, speaker_configs=None)

# Print sample
print("\n" + "=" * 60)
print("SoulX Format Sample:")
print("=" * 60)
print(json.dumps(soulx_script, ensure_ascii=False, indent=2)[:1000])
print("...")

# Print speakers
print("\n" + "=" * 60)
print("Speakers:")
print("=" * 60)
print(json.dumps(soulx_script["speakers"], ensure_ascii=False, indent=2))

# Print first 3 text items
print("\n" + "=" * 60)
print("First 3 text items:")
print("=" * 60)
for item in soulx_script["text"][:3]:
    print(f"{item[0]}: {item[1]}")

print(f"\nTotal segments in text array: {len(soulx_script['text'])}")
