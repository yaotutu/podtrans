#!/usr/bin/env python3
"""将 voice sample 信息保存到各自的说话人文件夹中"""

import json
from pathlib import Path
from rich.console import Console

console = Console()


def save_voice_sample_info():
    """将 voice sample 信息保存到各自文件夹"""

    # 查找最新的包含 voice_samples.json 的目录
    the_daily_dir = Path("data/The_Daily")
    latest_episode = None
    voice_samples_json_path = None

    if the_daily_dir.exists():
        for item in the_daily_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                json_file = item / "voice_samples.json"
                if json_file.exists():
                    if (latest_episode is None or
                        item.stat().st_mtime > latest_episode.stat().st_mtime):
                        latest_episode = item
                        voice_samples_json_path = json_file

    if not voice_samples_json_path:
        console.print("[red]未找到 voice_samples.json 文件[/red]")
        return

    console.print(f"[bold green]找到文件:[/bold green] {voice_samples_json_path}")

    # 加载 voice samples 数据
    with open(voice_samples_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    speaker_samples = data.get('speaker_samples', {})
    console.print(f"[blue]找到 {len(speaker_samples)} 个说话人的 voice samples[/blue]")

    # 为每个说话人创建单独的信息文件
    for speaker_id, sample_info in speaker_samples.items():
        # 创建说话人特定的数据
        speaker_data = {
            "speaker_id": sample_info["speaker_id"],
            "audio_file": sample_info["audio_path"],
            "time_range": {
                "start": sample_info["start_time"],
                "end": sample_info["end_time"],
                "duration": sample_info["duration"]
            },
            "text_content": sample_info["text_content"],
            "quality_metrics": {
                "score": sample_info["quality_score"],
                "words_count": sample_info["words_count"],
                "speech_rate": sample_info["speech_rate"]
            },
            "metadata": {
                "is_complete_sentence": sample_info.get("is_complete_sentence", False),
                "has_meaningful_content": sample_info.get("has_meaningful_content", False),
                "extraction_time": sample_info.get("extraction_time", ""),
                "recommended_use": sample_info.get("recommended_use", "")
            }
        }

        # 确定说话人文件夹路径
        speaker_dir = voice_samples_json_path.parent / "voice_samples" / speaker_id

        if speaker_dir.exists():
            # 保存 JSON 文件
            info_json_path = speaker_dir / "voice_sample_info.json"
            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump(speaker_data, f, ensure_ascii=False, indent=2)

            # 保存纯文本文件
            info_txt_path = speaker_dir / "voice_sample_info.txt"
            with open(info_txt_path, 'w', encoding='utf-8') as f:
                f.write(f"说话人: {speaker_id}\n")
                f.write(f"=" * 50 + "\n\n")
                f.write(f"音频文件: {sample_info['audio_path']}\n")
                f.write(f"时间范围: {sample_info['start_time']:.3f}s - {sample_info['end_time']:.3f}s\n")
                f.write(f"时长: {sample_info['duration']:.3f}s\n\n")
                f.write(f"文本内容:\n")
                f.write("-" * 20 + "\n")
                f.write(f"{sample_info['text_content']}\n")
                f.write(f"-" * 50 + "\n\n")
                f.write(f"质量指标:\n")
                f.write(f"  - 质量分数: {sample_info['quality_score']:.1f}\n")
                f.write(f"  - 词数: {sample_info['words_count']}\n")
                f.write(f"  - 语速: {sample_info['speech_rate']:.2f} 词/秒\n\n")
                f.write(f"使用建议:\n")
                f.write(f"  {sample_info.get('recommended_use', '无')}\n")

            console.print(f"[green]✓ {speaker_id}[/green]: 信息已保存到 {speaker_dir}")
        else:
            console.print(f"[red]✗ {speaker_id}[/red]: 文件夹不存在 {speaker_dir}")

    # 创建汇总文件
    summary_path = voice_samples_json_path.parent / "voice_samples_summary_by_speaker.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("Voice Samples 按说话人汇总\n")
        f.write("=" * 60 + "\n\n")

        # 按质量分数排序
        sorted_speakers = sorted(
            speaker_samples.items(),
            key=lambda x: x[1].get('quality_score', 0),
            reverse=True
        )

        for i, (speaker_id, info) in enumerate(sorted_speakers, 1):
            f.write(f"{i}. {speaker_id}\n")
            f.write(f"   时间: {info['start_time']:.1f}s - {info['end_time']:.1f}s ({info['duration']:.1f}s)\n")
            f.write(f"   质量: {info['quality_score']:.1f}/100\n")
            f.write(f"   文本: {info['text_content'][:100]}{'...' if len(info['text_content']) > 100 else ''}\n")
            f.write(f"   文件: {info['audio_path']}\n")
            f.write("\n")

    console.print(f"\n[blue]汇总文件已保存到:[/blue] {summary_path}")


if __name__ == "__main__":
    save_voice_sample_info()