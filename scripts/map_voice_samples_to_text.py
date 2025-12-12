#!/usr/bin/env python3
"""将 voice_samples 片段映射到 ASR 结果中的对应文本"""

from pathlib import Path
from typing import Dict, List, Tuple
import json
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()


class VoiceSampleMapper:
    """映射 voice_samples 到 ASR 文本"""

    def __init__(self, asr_result_path: Path, voice_samples_dir: Path):
        self.asr_result_path = asr_result_path
        self.voice_samples_dir = voice_samples_dir
        self.asr_data = None
        self.segments_by_speaker = {}

    def load_asr_result(self):
        """加载 ASR 结果"""
        console.print(f"[blue]正在加载 ASR 结果: {self.asr_result_path}[/blue]")
        with open(self.asr_result_path, 'r', encoding='utf-8') as f:
            self.asr_data = json.load(f)

        # 按说话人分组所有段落
        for segment in self.asr_data.get('segments', []):
            speaker = segment.get('speaker', 'UNKNOWN')
            if speaker not in self.segments_by_speaker:
                self.segments_by_speaker[speaker] = []
            self.segments_by_speaker[speaker].append(segment)

        console.print(f"[blue]加载完成，共 {len(self.segments_by_speaker)} 个说话人[/blue]")

    def find_voice_sample_files(self) -> List[Path]:
        """查找所有 voice_sample 文件"""
        pattern = "voice_sample_SPEAKER_*.wav"
        voice_files = list(self.voice_samples_dir.glob(pattern))
        voice_files.sort(key=lambda x: x.name)
        return voice_files

    def extract_time_from_filename(self, filename: str) -> Tuple[float, float, str]:
        """从文件名提取时间信息和说话人"""
        # 文件名格式: voice_sample_SPEAKER_00_start123.45_end567.89.wav
        parts = filename.replace('.wav', '').split('_')
        speaker = f"_{parts[2]}_{parts[3]}"  # _SPEAKER_00

        # 提取开始和结束时间
        start_time = None
        end_time = None

        for part in parts:
            if part.startswith('start'):
                start_time = float(part.replace('start', ''))
            elif part.startswith('end'):
                end_time = float(part.replace('end', ''))

        return start_time, end_time, speaker

    def map_voice_sample_to_text(self, start_time: float, end_time: float, speaker: str) -> List[Dict]:
        """将时间范围映射到对应的文本段落"""
        if speaker not in self.segments_by_speaker:
            return []

        relevant_segments = []
        for segment in self.segments_by_speaker[speaker]:
            seg_start = segment.get('start', 0)
            seg_end = segment.get('end', 0)

            # 检查是否有时间重叠
            if not (seg_end < start_time or seg_start > end_time):
                relevant_segments.append({
                    'text': segment.get('text', ''),
                    'start': seg_start,
                    'end': seg_end,
                    'overlap_start': max(seg_start, start_time),
                    'overlap_end': min(seg_end, end_time),
                    'duration': seg_end - seg_start
                })

        return relevant_segments

    def process_all_voice_samples(self) -> Dict[str, List[Dict]]:
        """处理所有 voice_sample 文件"""
        voice_files = self.find_voice_sample_files()
        results = {}

        for voice_file in voice_files:
            console.print(f"\n[blue]处理: {voice_file.name}[/blue]")

            # 从文件名提取信息
            start_time, end_time, speaker = self.extract_time_from_filename(voice_file.name)

            if start_time is None or end_time is None:
                console.print(f"[yellow]无法从文件名提取时间信息: {voice_file.name}[/yellow]")
                continue

            # 映射到文本
            text_segments = self.map_voice_sample_to_text(start_time, end_time, speaker)

            results[voice_file.name] = {
                'speaker': speaker,
                'time_range': (start_time, end_time),
                'duration': end_time - start_time,
                'text_segments': text_segments,
                'full_text': ' '.join(seg['text'] for seg in text_segments)
            }

            # 显示映射结果
            console.print(f"  说话人: {speaker}")
            console.print(f"  时间: {start_time:.1f}s - {end_time:.1f}s")
            console.print(f"  对应段落数: {len(text_segments)}")
            if text_segments:
                console.print(f"  文本: {results[voice_file.name]['full_text'][:100]}...")

        return results

    def save_mapping_results(self, results: Dict, output_path: Path):
        """保存映射结果"""
        mapping_data = {
            'asr_result_file': str(self.asr_result_path),
            'voice_samples_dir': str(self.voice_samples_dir),
            'mappings': results
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=2)

        console.print(f"\n[green]映射结果已保存到: {output_path}[/green]")

    def display_summary_table(self, results: Dict):
        """显示汇总表格"""
        table = Table(title="Voice Samples 文本映射汇总")
        table.add_column("文件名", style="cyan", no_wrap=True)
        table.add_column("说话人", style="green")
        table.add_column("时长(秒)", style="yellow")
        table.add_column("段落数", style="magenta")
        table.add_column("文本预览", style="white")

        for filename, data in results.items():
            table.add_row(
                filename,
                data['speaker'],
                f"{data['duration']:.1f}",
                str(len(data['text_segments'])),
                data['full_text'][:50] + "..." if len(data['full_text']) > 50 else data['full_text']
            )

        console.print("\n")
        console.print(table)


def main():
    """主函数 - 查找并处理最近的 voice_samples"""
    # 首先尝试从 data/The_Daily 查找
    the_daily_dir = Path("data/The_Daily")
    latest_episode = None
    voice_samples_dir = None
    asr_result_path = None

    if the_daily_dir.exists():
        # 找到最新的剧集目录
        for item in the_daily_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                vs_dir = item / "voice_samples"
                asr_file = item / "asr_result.json"

                if vs_dir.exists() and asr_file.exists():
                    if (latest_episode is None or
                        item.stat().st_mtime > latest_episode.stat().st_mtime):
                        latest_episode = item
                        voice_samples_dir = vs_dir
                        asr_result_path = asr_file

    # 如果在 The_Daily 找到，使用它
    if latest_episode:
        console.print(f"[bold green]找到剧集目录:[/bold green] {latest_episode.name}")
        console.print(f"[cyan]ASR 结果:[/cyan] {asr_result_path}")
        console.print(f"[cyan]Voice Samples:[/cyan] {voice_samples_dir}")
    else:
        # 否则尝试从 data/output 查找
        data_output = Path("data/output")
        if not data_output.exists():
            console.print("[red]data/output 目录不存在[/red]")
            return

        # 找到最新的处理目录
        latest_dir = None
        for item in data_output.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                if latest_dir is None or item.stat().st_mtime > latest_dir.stat().st_mtime:
                    latest_dir = item

        if not latest_dir:
            console.print("[red]未找到处理结果目录[/red]")
            return

        # 查找 voice_samples 目录
        voice_samples_dir = latest_dir / "voice_samples"
        asr_result_path = latest_dir / "asr_result.json"

        if not voice_samples_dir.exists():
            console.print(f"[red]voice_samples 目录不存在: {voice_samples_dir}[/red]")
            return

        if not asr_result_path.exists():
            console.print(f"[red]ASR 结果文件不存在: {asr_result_path}[/red]")
            return

        console.print(f"[bold green]找到处理目录:[/bold green] {latest_dir.name}")
        console.print(f"[cyan]ASR 结果:[/cyan] {asr_result_path}")
        console.print(f"[cyan]Voice Samples:[/cyan] {voice_samples_dir}")

    # 创建映射器并处理
    mapper = VoiceSampleMapper(asr_result_path, voice_samples_dir)
    mapper.load_asr_result()

    # 处理所有 voice sample
    results = mapper.process_all_voice_samples()

    # 显示汇总
    mapper.display_summary_table(results)

    # 保存结果
    base_dir = latest_episode if latest_episode else voice_samples_dir.parent
    output_path = base_dir / "voice_sample_text_mapping.json"
    mapper.save_mapping_results(results, output_path)

    # 生成文本文件版本
    text_output_path = base_dir / "voice_sample_texts.txt"
    with open(text_output_path, 'w', encoding='utf-8') as f:
        f.write("Voice Samples 文本映射\n")
        f.write("=" * 60 + "\n\n")

        for filename, data in results.items():
            f.write(f"{filename}\n")
            f.write(f"说话人: {data['speaker']}\n")
            f.write(f"时间: {data['time_range'][0]:.1f}s - {data['time_range'][1]:.1f}s\n")
            f.write(f"文本: {data['full_text']}\n")
            f.write("-" * 60 + "\n\n")

    console.print(f"[green]文本版本已保存到: {text_output_path}[/green]")


if __name__ == "__main__":
    main()