"""Convert translation result to SoulX-Podcast format for CLI testing."""

import json
from pathlib import Path

from podtrans.translation.schemas import TranslationResult
from podtrans.tts.soulx.converter import SoulXConverter
from podtrans.utils.file import read_json


def main():
    # Input and output paths
    translation_json = Path("data/output/demo/translation_result.json")
    output_json = Path("data/output/demo/soulx_script.json")

    # Load translation result
    print(f"Loading translation result from: {translation_json}")
    translation_data = read_json(translation_json)
    translation_result = TranslationResult(**translation_data)

    print(f"  - Segments: {translation_result.total_segments}")
    print(f"  - Speakers: {translation_result.speaker_count}")

    # Convert to SoulX format
    print("\nConverting to SoulX format...")
    converter = SoulXConverter()
    soulx_script = converter.convert(translation_result, speaker_configs=None)

    print(f"  - Speakers in output: {len(soulx_script['speakers'])}")
    print(f"  - Text segments: {len(soulx_script['text'])}")

    # Save to file
    print(f"\nSaving SoulX script to: {output_json}")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(soulx_script, f, ensure_ascii=False, indent=2)

    print("\n✅ Conversion complete!")
    print("\nYou can now use this file with SoulX CLI:")
    print(
        f"  python -m soulx_podcast.cli --script {output_json} --output podcast_output.wav"
    )

    # Print sample
    print("\n" + "=" * 60)
    print("Sample output (first 5 segments):")
    print("=" * 60)
    for i, item in enumerate(soulx_script["text"][:5]):
        print(f"{item[0]}: {item[1]}")

    print("\n" + "=" * 60)
    print("Speakers configuration:")
    print("=" * 60)
    print(json.dumps(soulx_script["speakers"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
