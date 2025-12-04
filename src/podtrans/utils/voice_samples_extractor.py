"""
Voice Samples Extractor - 智能筛选最佳语音样本

从所有segments的voice samples中为每个speaker选择质量最高的样本，
并收集对应的声音描述信息。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from podtrans.asr.voice_sample import VoiceSample


class VoiceSamplesExtractor:
    """Voice Samples智能提取器"""

    def __init__(self, episode_dir: Path):
        """
        初始化提取器

        Args:
            episode_dir: episode的输出目录
        """
        self.episode_dir = episode_dir
        self.voice_samples_dir = episode_dir / "voice_samples_for_cloning"
        self.voice_samples_dir.mkdir(exist_ok=True)

        # 创建cache目录用于存储原始音频文件
        self.cache_dir = self.voice_samples_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)

    def extract_best_samples(self) -> Dict[str, VoiceSample]:
        """
        从所有segments中提取每个speaker的最佳样本

        Returns:
            Dict[str, VoiceSample]: 每个speaker_id对应的最佳样本
        """
        logger.info("开始提取最佳voice samples...")

        best_samples = {}

        # 扫描所有segment的voice_samples文件夹
        # 新结构：voice_samples在每个segment目录内部 (episode_001_part_XXX/voice_samples)
        segment_dirs = []

        # 查找新结构的voice_samples目录
        new_structure_dirs = [d for d in self.episode_dir.iterdir() if d.is_dir() and (d / "voice_samples").exists()]
        for segment_dir in new_structure_dirs:
            voice_samples_dir = segment_dir / "voice_samples"
            if voice_samples_dir.exists():
                segment_dirs.append(voice_samples_dir)

        if not segment_dirs:
            logger.warning("未找到任何voice_samples文件夹")
            return best_samples

        logger.info(f"找到 {len(segment_dirs)} 个voice_samples文件夹")

        # 从每个segment目录加载样本
        for segment_dir in segment_dirs:
            try:
                samples = self._load_samples_from_dir(segment_dir)
                for speaker_id, sample in samples.items():
                    # 选择质量更高的样本
                    if (speaker_id not in best_samples or
                        sample.quality_score > best_samples[speaker_id].quality_score):
                        best_samples[speaker_id] = sample
                        logger.debug(f"发现更好的样本 {speaker_id}: {sample.quality_score} (来自 {segment_dir.name})")
            except Exception as e:
                logger.warning(f"加载 {segment_dir} 的样本失败: {e}")

        logger.info(f"最佳样本提取完成: {len(best_samples)} 个speakers")
        return best_samples

    def collect_speaker_descriptions(self) -> Dict[str, Dict]:
        """
        收集所有speaker的声音描述信息

        Returns:
            Dict[str, Dict]: 每个speaker_id的描述信息
        """
        logger.info("开始收集声音描述信息...")

        descriptions = {}

        # 从各个extraction_summary.json中提取描述
        # 新结构：voice_samples在每个segment目录内部 (episode_001_part_XXX/voice_samples)
        segment_dirs = []

        # 查找新结构的voice_samples目录
        new_structure_dirs = [d for d in self.episode_dir.iterdir() if d.is_dir() and (d / "voice_samples").exists()]
        for segment_dir in new_structure_dirs:
            voice_samples_dir = segment_dir / "voice_samples"
            if voice_samples_dir.exists():
                segment_dirs.append(voice_samples_dir)

        for segment_dir in segment_dirs:
            summary_file = segment_dir / "extraction_summary.json"
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary = json.load(f)

                    if "samples" in summary:
                        for speaker_id, info in summary["samples"].items():
                            quality_score = info.get("quality_score", 0)
                            description = info.get("description", "")

                            if speaker_id not in descriptions:
                                descriptions[speaker_id] = {
                                    "source_segment": segment_dir.name,
                                    "quality_score": quality_score,
                                    "description": description,
                                    "audio_file": f"{speaker_id}.wav"
                                }
                            elif description:
                                # 优先选择非空描述，如果质量分数更高则更新
                                if (quality_score > descriptions[speaker_id]["quality_score"] or
                                    not descriptions[speaker_id]["description"]):
                                    descriptions[speaker_id]["description"] = description
                                    descriptions[speaker_id]["source_segment"] = segment_dir.name
                                    descriptions[speaker_id]["quality_score"] = quality_score

                except Exception as e:
                    logger.warning(f"解析 {summary_file} 失败: {e}")

        logger.info(f"声音描述收集完成: {len(descriptions)} 个speakers")
        return descriptions

    def save_best_samples(self, best_samples: Dict[str, VoiceSample]) -> None:
        """
        保存最佳样本到voice_samples_for_cloning目录

        Args:
            best_samples: 每个speaker的最佳样本
        """
        logger.info("保存最佳voice samples...")

        for speaker_id, sample in best_samples.items():
            try:
                # 目标文件名
                target_file = self.voice_samples_dir / f"{speaker_id}.wav"

                # 复制音频文件
                shutil.copy2(sample.audio_path, target_file)

                logger.info(f"保存最佳样本: {speaker_id} (质量分数: {sample.quality_score})")

            except Exception as e:
                logger.error(f"保存样本 {speaker_id} 失败: {e}")

    def save_descriptions(self, descriptions: Dict[str, Dict]) -> None:
        """
        保存声音描述信息到speaker_descriptions.json

        Args:
            descriptions: 每个speaker的描述信息
        """
        logger.info("保存声音描述信息...")

        descriptions_file = self.voice_samples_dir / "speaker_descriptions.json"

        # 添加保存时间
        descriptions_with_meta = {
            "extraction_time": datetime.now().isoformat(),
            "total_speakers": len(descriptions),
            "speakers": descriptions
        }

        try:
            with open(descriptions_file, 'w', encoding='utf-8') as f:
                json.dump(descriptions_with_meta, f, ensure_ascii=False, indent=2)

            logger.info(f"声音描述信息已保存: {descriptions_file}")

        except Exception as e:
            logger.error(f"保存描述信息失败: {e}")

    def copy_original_audio_files(self) -> None:
        """
        复制原始音频文件到cache目录

        从episode目录中查找所有音频文件并复制到cache目录，便于对比和调试
        """
        logger.info("复制原始音频文件到cache目录...")

        copied_count = 0

        # 查找常见的音频文件格式
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg'}
        audio_files = []

        # 扫描episode目录中的音频文件
        for file_path in self.episode_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                # 跳过已经处理过的文件（voice_samples目录和voice_samples_for_cloning目录中的文件）
                if ('voice_samples' not in file_path.parts and
                    'voice_samples_for_cloning' not in file_path.parts):
                    audio_files.append(file_path)

        # 复制音频文件
        for audio_file in audio_files:
            try:
                # 计算相对路径以保持目录结构
                relative_path = audio_file.relative_to(self.episode_dir)
                target_path = self.cache_dir / relative_path

                # 创建目标目录
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 复制文件
                shutil.copy2(audio_file, target_path)
                copied_count += 1

                logger.debug(f"复制音频文件: {relative_path}")

            except Exception as e:
                logger.warning(f"复制音频文件失败 {audio_file}: {e}")

        logger.info(f"原始音频文件复制完成: {copied_count} 个文件")

    def _load_samples_from_dir(self, voice_samples_dir: Path) -> Dict[str, VoiceSample]:
        """
        从voice_samples目录加载样本

        Args:
            voice_samples_dir: voice_samples目录路径

        Returns:
            Dict[str, VoiceSample]: speaker_id到样本的映射
        """
        samples = {}

        # 查找所有speaker目录
        speaker_dirs = [d for d in voice_samples_dir.iterdir() if d.is_dir() and d.name.startswith("SPEAKER_")]

        for speaker_dir in speaker_dirs:
            # 查找音频文件
            audio_files = list(speaker_dir.glob("*.wav"))

            if audio_files:
                # 选择第一个音频文件（通常每个speaker目录只有一个最佳样本）
                audio_file = audio_files[0]

                # 尝试从extraction_summary.json获取详细信息
                summary_file = voice_samples_dir / "extraction_summary.json"
                quality_score = 0.0
                text_content = ""

                if summary_file.exists():
                    try:
                        with open(summary_file, 'r', encoding='utf-8') as f:
                            summary = json.load(f)

                        if "samples" in summary and speaker_dir.name in summary["samples"]:
                            sample_info = summary["samples"][speaker_dir.name]
                            quality_score = sample_info.get("quality_score", 0)
                            text_content = sample_info.get("text_content", "")

                    except Exception:
                        pass  # 如果解析失败，使用默认值

                # 创建VoiceSample对象
                sample = VoiceSample(
                    speaker_id=speaker_dir.name,
                    audio_path=audio_file,
                    text_content=text_content or f"Voice sample for {speaker_dir.name}",
                    start_time=0.0,
                    end_time=0.0,
                    duration=0.0,
                    quality_score=quality_score,
                    words_count=len(text_content.split()) if text_content else 0,
                    speech_rate=0.0,
                    is_complete_sentence=bool(text_content and '.' in text_content),
                    has_meaningful_content=bool(text_content and len(text_content.strip()) > 0),
                    recommended_use="voice cloning"
                )

                samples[speaker_dir.name] = sample

        return samples

    def process_episode(self) -> Optional[Path]:
        """
        处理整个episode的voice samples

        Returns:
            Optional[Path]: voice_samples_for_cloning目录路径，如果失败返回None
        """
        try:
            logger.info(f"开始处理episode: {self.episode_dir.name}")

            # 1. 提取最佳样本
            best_samples = self.extract_best_samples()

            if not best_samples:
                logger.warning("未找到任何voice samples")
                return None

            # 2. 收集声音描述
            descriptions = self.collect_speaker_descriptions()

            # 3. 保存最佳样本
            self.save_best_samples(best_samples)

            # 4. 保存描述信息
            self.save_descriptions(descriptions)

            # 5. 复制原始音频文件到cache目录
            self.copy_original_audio_files()

            logger.info(f"Episode {self.episode_dir.name} 处理完成")
            return self.voice_samples_dir

        except Exception as e:
            logger.error(f"处理episode {self.episode_dir.name} 失败: {e}")
            return None