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
from typing import Any

from pydantic import BaseModel, Field


class VoiceSample(BaseModel):
    """声音克隆样本

    表示从ASR结果中提取的单个语音片段，包含音频和文字信息。
    """

    speaker_id: str = Field(description="说话人ID (例如 'SPEAKER_00')")
    audio_path: Path = Field(description="音频文件路径")
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
