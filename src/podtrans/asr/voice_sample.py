"""Voice Sample Extraction Module

本模块提供从ASR结果中提取声音克隆样本的功能。

功能特点:
- 基于ASR精确时间戳提取音频片段
- 智能质量评分系统
- 为每个说话人选择最佳样本
- 生成详细的元数据说明

使用示例:
    from podtrans.asr.voice_sample import VoiceSampleExtractor

    extractor = VoiceSampleExtractor()
    results = extractor.extract_samples(audio_path, asr_result)
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import BaseModel, Field
from pydub import AudioSegment

if TYPE_CHECKING:
    from podtrans.asr.schemas import ASRResult, Segment


class VoiceSample(BaseModel):
    """声音克隆样本

    表示从ASR结果中提取的单个语音片段，包含音频和文字信息。
    """

    speaker_id: str = Field(description="说话人ID (例如 'SPEAKER_00')")
    audio_path: str = Field(description="音频文件路径 (相对于episode目录)")
    text_content: str = Field(description="对应的文字内容")
    start_time: float = Field(ge=0, description="开始时间（秒）")
    end_time: float = Field(ge=0, description="结束时间（秒）")
    duration: float = Field(ge=0, description="持续时间（秒）")

    # 质量指标
    quality_score: float = Field(ge=0, le=100, description="质量评分 (0-100)")
    words_count: int = Field(ge=0, description="词数")
    speech_rate: float = Field(ge=0, description="语速（词/秒）")

    # 文本特征
    is_complete_sentence: bool = Field(description="是否完整句子")
    has_meaningful_content: bool = Field(description="是否有意义的内容")

    # 元数据
    extraction_time: datetime = Field(
        default_factory=datetime.now, description="提取时间"
    )
    recommended_use: str = Field(description="推荐用途")

    @property
    def phoneme_coverage(self) -> float:
        """音素覆盖率估算 (0-1)

        简单估算文本中包含的音素种类数量。
        实际应用中可以使用更精确的音素分析工具。
        """
        text = self.text_content.lower()
        # 元音
        vowels = set("aeiou")
        # 常见辅音
        consonants = set("bcdfghjklmnpqrstvwxyz")

        vowel_count = len(set(c for c in text if c in vowels))
        consonant_count = len(set(c for c in text if c in consonants))

        # 归一化到0-1范围
        return min((vowel_count + consonant_count) / 26.0, 1.0)


class VoiceExtractionResult(BaseModel):
    """声音提取结果

    包含所有提取的样本和摘要信息。
    """

    speaker_samples: dict[str, VoiceSample] = Field(description="按说话人分组的样本")
    total_speakers: int = Field(description="总说话人数")
    total_samples: int = Field(description="总样本数")
    extraction_time: datetime = Field(
        default_factory=datetime.now, description="提取时间"
    )
    extraction_summary: dict[str, Any] = Field(description="提取摘要")

    model_config = {
        "json_schema_extra": {
            "example": {
                "speaker_samples": {
                    "SPEAKER_00": {
                        "speaker_id": "SPEAKER_00",
                        "audio_path": "voice_samples/SPEAKER_00/voice_sample.wav",
                        "text_content": "我觉得这个观点很有意思...",
                        "start_time": 15.2,
                        "end_time": 28.0,
                        "duration": 12.8,
                        "quality_score": 95.0,
                    }
                },
                "total_speakers": 2,
                "total_samples": 2,
                "extraction_summary": {
                    "average_quality": 87.5,
                    "average_duration": 11.2,
                    "success_rate": 1.0,
                },
            }
        }
    }


class QualityScorer:
    """质量评分器

    负责计算语音样本的质量评分。
    """

    @staticmethod
    def calculate_quality_score(
        duration: float,
        speech_rate: float,
        text: str,
        words_count: int,
        min_duration: float = 5.0,
        max_duration: float = 20.0,
    ) -> float:
        """计算语音样本质量评分 (0-100)

        评分维度:
        - 时长评分 (25分): 5-20秒最佳
        - 语速评分 (20分): 2.5-4.0词/秒最佳
        - 完整性评分 (30分): 完整句子加分
        - 音素丰富度 (25分): 包含多种发音

        Args:
            duration: 音频时长（秒）
            speech_rate: 语速（词/秒）
            text: 文本内容
            words_count: 词数
            min_duration: 最小期望时长
            max_duration: 最大期望时长

        Returns:
            float: 质量评分 (0-100)
        """
        score = 0.0

        # 1. 时长评分 (25分)
        if min_duration <= duration <= max_duration:
            score += 25
        elif duration < min_duration:
            # 太短，按比例扣分
            ratio = duration / min_duration
            score += 25 * ratio * 0.5  # 最多得一半分数
        elif duration > max_duration:
            # 太长，按比例扣分
            ratio = max_duration / duration
            score += 25 * ratio * 0.7  # 最多得70%分数

        # 2. 语速评分 (20分)
        if 2.5 <= speech_rate <= 4.0:
            score += 20
        elif 2.0 <= speech_rate <= 5.0:
            score += 15
        elif 1.5 <= speech_rate <= 6.0:
            score += 10
        else:
            score += 5

        # 3. 完整性评分 (30分)
        # 检查是否完整句子
        if text.strip().endswith((".。", "！!", "？?", "；;")):
            score += 15
        elif len(text.strip()) > 20:
            score += 8

        # 检查是否有意义的内容
        meaningful_words = [
            "觉得",
            "认为",
            "因为",
            "所以",
            "但是",
            "如果",
            "这个",
            "那个",
            "可以",
            "可能",
            "应该",
            "需要",
            "想要",
            "希望",
            "喜欢",
        ]
        if any(word in text for word in meaningful_words):
            score += 15
        elif words_count >= 5:
            score += 10
        else:
            score += 5

        # 4. 音素丰富度 (25分)
        # 简化的音素丰富度计算
        text_lower = text.lower()
        vowel_types = len(set(c for c in text_lower if c in "aeiou"))
        consonant_types = len(
            set(c for c in text_lower if c in "bcdfghjklmnpqrstvwxyz")
        )

        phoneme_score = min((vowel_types + consonant_types) * 2, 25)
        score += phoneme_score

        return min(score, 100.0)

    @staticmethod
    def get_recommendation(score: float) -> str:
        """根据评分获取推荐用途"""
        if score >= 90:
            return "强烈推荐：优秀的克隆训练样本，语调自然，内容完整"
        elif score >= 80:
            return "推荐使用：高质量的克隆样本，适合作为主要训练素材"
        elif score >= 70:
            return "可考虑使用：中等质量，需要更多样本辅助"
        elif score >= 60:
            return "勉强可用：质量一般，建议寻找更好的样本"
        else:
            return "不推荐：质量不足，建议舍弃"


class VoiceSampleExtractor:
    """声音样本提取器

    从ASR结果中提取每个说话人的最佳声音片段，用于后续TTS声音克隆。
    """

    def __init__(
        self,
        min_duration: float = 5.0,
        max_duration: float = 20.0,
        top_k: int = 1,
    ):
        """初始化提取器

        Args:
            min_duration: 最小样本时长（秒），默认5秒
            max_duration: 最大样本时长（秒），默认20秒
            top_k: 每个说话人选取的最佳样本数量，默认1个
        """
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.top_k = top_k
        self.scorer = QualityScorer()

    def extract_samples(
        self,
        audio_path: Path,
        asr_result: "ASRResult",
        output_dir: Path,
    ) -> VoiceExtractionResult:
        """从音频中提取每个说话人的最佳样本

        Args:
            audio_path: 原始音频文件路径
            asr_result: ASR处理结果
            output_dir: 输出目录

        Returns:
            VoiceExtractionResult: 提取结果，包含每个说话人的最佳样本
        """
        logger.info(f"开始提取声音样本: {audio_path}")

        # 1. 按说话人分组 segments
        speaker_segments = self._group_segments_by_speaker(asr_result)
        logger.info(f"检测到 {len(speaker_segments)} 个说话人")

        # 2. 创建输出目录
        voice_samples_dir = output_dir / "voice_samples"
        voice_samples_dir.mkdir(parents=True, exist_ok=True)

        # 3. 加载音频文件
        logger.info(f"加载音频文件: {audio_path}")
        audio = AudioSegment.from_file(audio_path)

        # 4. 对每个说话人提取最佳样本
        speaker_samples: dict[str, VoiceSample] = {}
        total_quality = 0.0
        total_duration = 0.0

        for speaker_id, segments in speaker_segments.items():
            logger.info(f"处理说话人 {speaker_id}, 共 {len(segments)} 个片段")

            # 评分并选择最佳片段
            best_segment = self._select_best_segment(segments)
            if best_segment is None:
                logger.warning(f"说话人 {speaker_id} 没有符合条件的片段")
                continue

            # 创建说话人目录
            speaker_dir = voice_samples_dir / speaker_id
            speaker_dir.mkdir(parents=True, exist_ok=True)

            # 提取并保存音频片段
            sample_path = speaker_dir / "sample_001.wav"
            self._extract_audio_segment(
                audio, best_segment.start, best_segment.end, sample_path
            )

            # 计算评分和指标
            duration = best_segment.end - best_segment.start
            words_count = len(best_segment.text.split())
            speech_rate = words_count / duration if duration > 0 else 0
            text = best_segment.text

            quality_score = self.scorer.calculate_quality_score(
                duration=duration,
                speech_rate=speech_rate,
                text=text,
                words_count=words_count,
                min_duration=self.min_duration,
                max_duration=self.max_duration,
            )

            # 判断文本特征
            sentence_endings = (".", "。", "!", "！", "?", "？", ";", "；")
            is_complete = text.strip().endswith(sentence_endings)
            has_meaningful = len(text.strip()) > 20 or words_count >= 5

            # 创建样本对象
            sample = VoiceSample(
                speaker_id=speaker_id,
                audio_path=str(sample_path.relative_to(output_dir)),
                text_content=text,
                start_time=best_segment.start,
                end_time=best_segment.end,
                duration=duration,
                quality_score=quality_score,
                words_count=words_count,
                speech_rate=speech_rate,
                is_complete_sentence=is_complete,
                has_meaningful_content=has_meaningful,
                recommended_use=self.scorer.get_recommendation(quality_score),
            )

            speaker_samples[speaker_id] = sample
            total_quality += quality_score
            total_duration += duration

            logger.info(
                f"  {speaker_id}: 提取样本 {duration:.1f}s, 评分 {quality_score:.1f}"
            )

        # 5. 构建结果
        total_samples = len(speaker_samples)
        avg_quality = total_quality / total_samples if total_samples > 0 else 0
        avg_duration = total_duration / total_samples if total_samples > 0 else 0
        success_rate = total_samples / len(speaker_segments) if speaker_segments else 0

        result = VoiceExtractionResult(
            speaker_samples=speaker_samples,
            total_speakers=len(speaker_segments),
            total_samples=total_samples,
            extraction_summary={
                "average_quality": round(avg_quality, 2),
                "average_duration": round(avg_duration, 2),
                "success_rate": success_rate,
            },
        )

        logger.info(
            f"声音样本提取完成: {total_samples} 个样本, 平均评分 {avg_quality:.1f}"
        )

        return result

    def save_speaker_info_to_dirs(self, voice_result: VoiceExtractionResult, output_dir: Path) -> None:
        """将voice sample信息保存到各个说话人的子目录中

        Args:
            voice_result: VoiceExtractionResult提取结果
            output_dir: 输出目录（voice_samples的父目录）
        """
        import json
        from datetime import datetime

        voice_samples_dir = output_dir / "voice_samples"
        if not voice_samples_dir.exists():
            logger.warning(f"voice_samples目录不存在: {voice_samples_dir}")
            return

        logger.info(f"开始保存voice sample信息到各个说话人目录")

        for speaker_id, sample in voice_result.speaker_samples.items():
            speaker_dir = voice_samples_dir / speaker_id

            if speaker_dir.exists():
                # 创建说话人特定的数据
                speaker_data = {
                    "speaker_id": speaker_id,
                    "audio_file": f"voice_samples/{speaker_id}/sample_001.wav",
                    "time_range": {
                        "start": sample.start_time,
                        "end": sample.end_time,
                        "duration": sample.duration
                    },
                    "text_content": sample.text_content,
                    "quality_metrics": {
                        "score": sample.quality_score,
                        "words_count": sample.words_count,
                        "speech_rate": sample.speech_rate
                    },
                    "metadata": {
                        "is_complete_sentence": True,  # 从提取逻辑可以推断
                        "has_meaningful_content": True,
                        "extraction_time": datetime.now().isoformat(),
                        "recommended_use": "推荐使用：高质量的克隆样本，适合作为主要训练素材" if sample.quality_score >= 80 else "可用样本，建议结合其他样本使用"
                    }
                }

                # 保存 JSON 文件
                info_json_path = speaker_dir / "voice_sample_info.json"
                with open(info_json_path, 'w', encoding='utf-8') as f:
                    json.dump(speaker_data, f, ensure_ascii=False, indent=2)

                # 保存纯文本文件
                info_txt_path = speaker_dir / "voice_sample_info.txt"
                with open(info_txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"说话人: {speaker_id}\n")
                    f.write(f"=" * 50 + "\n\n")
                    f.write(f"音频文件: voice_samples/{speaker_id}/sample_001.wav\n")
                    f.write(f"时间范围: {sample.start_time:.3f}s - {sample.end_time:.3f}s\n")
                    f.write(f"时长: {sample.duration:.3f}s\n\n")
                    f.write(f"文本内容:\n")
                    f.write("-" * 20 + "\n")
                    f.write(f"{sample.text_content}\n")
                    f.write("-" * 50 + "\n\n")
                    f.write(f"质量指标:\n")
                    f.write(f"  - 质量分数: {sample.quality_score:.1f}\n")
                    f.write(f"  - 词数: {sample.words_count}\n")
                    f.write(f"  - 语速: {sample.speech_rate:.2f} 词/秒\n\n")
                    f.write(f"使用建议:\n")
                    f.write(f"  {speaker_data['metadata']['recommended_use']}\n")

                logger.info(f"  ✓ {speaker_id}: 信息已保存到 {speaker_dir}")
            else:
                logger.warning(f"  ✗ {speaker_id}: 目录不存在 {speaker_dir}")

        # 创建汇总文件
        summary_path = output_dir / "voice_samples_summary_by_speaker.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("Voice Samples 按说话人汇总\n")
            f.write("=" * 60 + "\n\n")

            # 按质量分数排序
            sorted_samples = sorted(
                voice_result.speaker_samples.items(),
                key=lambda x: x[1].quality_score,
                reverse=True
            )

            for i, (speaker_id, sample) in enumerate(sorted_samples, 1):
                f.write(f"{i}. {speaker_id}\n")
                f.write(f"   时间: {sample.start_time:.1f}s - {sample.end_time:.1f}s ({sample.duration:.1f}s)\n")
                f.write(f"   质量: {sample.quality_score:.1f}/100\n")
                f.write(f"   文本: {sample.text_content[:100]}{'...' if len(sample.text_content) > 100 else ''}\n")
                f.write(f"   文件: voice_samples/{speaker_id}/sample_001.wav\n")
                f.write("\n")

        logger.info(f"汇总文件已保存到: {summary_path}")

    def _group_segments_by_speaker(
        self, asr_result: "ASRResult"
    ) -> dict[str, list["Segment"]]:
        """按说话人分组segments

        Args:
            asr_result: ASR结果

        Returns:
            按说话人ID分组的segment字典
        """
        from podtrans.asr.schemas import Segment

        speaker_segments: dict[str, list[Segment]] = {}

        for segment in asr_result.segments:
            if segment.speaker is None:
                continue

            if segment.speaker not in speaker_segments:
                speaker_segments[segment.speaker] = []

            speaker_segments[segment.speaker].append(segment)

        return speaker_segments

    def _select_best_segment(self, segments: list["Segment"]) -> "Segment | None":
        """选择最佳片段

        按评分排序，选择评分最高的片段。

        Args:
            segments: 候选片段列表

        Returns:
            评分最高的片段，如果没有符合条件的片段则返回None
        """
        # 过滤时长不符合要求的片段
        valid_segments = [
            seg
            for seg in segments
            if self.min_duration <= (seg.end - seg.start) <= self.max_duration
        ]

        # 如果没有完美时长的片段，放宽条件：选择最长的片段（至少2秒）
        if not valid_segments:
            valid_segments = [seg for seg in segments if (seg.end - seg.start) >= 2.0]

        if not valid_segments:
            return None

        # 计算每个片段的评分
        scored_segments = []
        for seg in valid_segments:
            duration = seg.end - seg.start
            words_count = len(seg.text.split())
            speech_rate = words_count / duration if duration > 0 else 0

            score = self.scorer.calculate_quality_score(
                duration=duration,
                speech_rate=speech_rate,
                text=seg.text,
                words_count=words_count,
                min_duration=self.min_duration,
                max_duration=self.max_duration,
            )
            scored_segments.append((seg, score))

        # 按评分降序排序
        scored_segments.sort(key=lambda x: x[1], reverse=True)

        return scored_segments[0][0] if scored_segments else None

    def _extract_audio_segment(
        self,
        audio: AudioSegment,
        start_time: float,
        end_time: float,
        output_path: Path,
    ) -> None:
        """切割并保存音频片段

        Args:
            audio: 原始音频对象
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出文件路径
        """
        # pydub 使用毫秒
        start_ms = int(start_time * 1000)
        end_ms = int(end_time * 1000)

        segment = audio[start_ms:end_ms]
        segment.export(output_path, format="wav")

        logger.debug(f"音频片段已保存: {output_path} ({end_time - start_time:.1f}s)")
