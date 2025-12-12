"""ASR (自动语音识别) 数据模型

本模块定义了 ASR 流程中使用的所有数据结构，使用 Pydantic v2 进行数据验证。

数据层次结构:
    ASRResult (完整结果)
    └── Segment[] (句子段落列表)
        └── Word[] (词级详细信息列表)

设计优势:
- 类型安全：自动进行类型检查和验证
- 数据验证：自动校验时间戳、文本等字段
- 易于序列化：可直接转换为 JSON
- 便捷方法：提供 total_segments, speaker_count 等计算属性

使用示例:
    # 创建词级数据
    word = Word(word="Hello", start=0.5, end=0.8, speaker="SPEAKER_00")

    # 创建段落
    segment = Segment(
        start=0.5,
        end=3.2,
        text="Hello, welcome to the podcast.",
        speaker="SPEAKER_00",
        words=[word, ...]
    )

    # 创建完整结果
    result = ASRResult(
        segments=[segment, ...],
        language="en",
        audio_duration=780.5,
        model_name="medium"
    )

    # 访问计算属性
    print(f"总段落数: {result.total_segments}")
    print(f"说话人数: {result.speaker_count}")

    # 序列化为 JSON
    json_str = result.model_dump_json(indent=2)
"""

from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field


class Word(BaseModel):
    """词级时间戳和说话人信息

    表示转录结果中的单个词及其详细信息。

    字段说明:
        word: 词的文本内容（例如 "Hello", "world"）
        start: 词的开始时间（秒），相对于音频开始位置
        end: 词的结束时间（秒），相对于音频开始位置
        score: 置信度分数（0.0-1.0），可选
            - 1.0 表示模型非常确信
            - 接近 0 表示模型不确定
            - None 表示未提供置信度
        speaker: 说话人标签（例如 "SPEAKER_00", "SPEAKER_01"），可选
            - 如果启用了说话人分离，会自动填充
            - 如果未启用说话人分离，为 None

    用途:
        - 精确的字幕制作（逐词显示）
        - 说话人分离的基础（基于时间戳匹配）
        - 语音分析和统计

    注意:
        - start 必须 >= 0
        - end 必须 >= start（由使用方保证）
        - score 必须在 0-1 范围内
    """

    word: str = Field(description="词的文本内容")
    start: float = Field(ge=0, description="开始时间（秒）")
    end: float = Field(ge=0, description="结束时间（秒）")
    score: float | None = Field(
        None, ge=0, le=1, description="置信度分数 (0.0-1.0)，None 表示未提供"
    )
    speaker: str | None = Field(
        None, description="说话人标签 (例如 'SPEAKER_00')，None 表示未识别"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "word": "Hello",
                "start": 0.5,
                "end": 0.8,
                "score": 0.95,
                "speaker": "SPEAKER_00",
            }
        }
    }


class Segment(BaseModel):
    """句子级段落，包含说话人信息

    表示转录结果中的一个完整句子或语义段落。

    字段说明:
        start: 段落开始时间（秒）
        end: 段落结束时间（秒）
        text: 完整的转录文本
        speaker: 该段落的说话人标签（可选）
            - 通过词级说话人投票确定（多数词的说话人）
            - 如果未启用说话人分离，为 None
        words: 该段落包含的所有词（词级详细信息）
            - 空列表表示没有词级信息
            - 通常由对齐步骤填充

    用途:
        - 翻译的基本单位（按段落翻译）
        - 对话展示（区分说话人）
        - 字幕文件生成

    计算属性:
        duration: 段落时长（秒）= end - start
        word_count: 词数（简单按空格分割）
    """

    start: float = Field(ge=0, description="开始时间（秒）")
    end: float = Field(ge=0, description="结束时间（秒）")
    text: str = Field(description="转录的完整文本")
    speaker: str | None = Field(
        None, description="说话人标签 (例如 'SPEAKER_00')，None 表示未识别"
    )
    words: list[Word] = Field(
        default_factory=list, description="词级时间戳列表，空列表表示无词级信息"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "start": 0.5,
                "end": 3.2,
                "text": "Hello, welcome to the podcast.",
                "speaker": "SPEAKER_00",
                "words": [
                    {
                        "word": "Hello",
                        "start": 0.5,
                        "end": 0.8,
                        "speaker": "SPEAKER_00",
                    }
                ],
            }
        }
    }

    @property
    def duration(self) -> float:
        """获取段落时长（秒）

        Returns:
            float: 段落持续时间（end - start）

        示例:
            segment = Segment(start=0.5, end=3.2, text="Hello")
            print(segment.duration)  # 输出: 2.7
        """
        return self.end - self.start

    @property
    def word_count(self) -> int:
        """获取段落中的词数（简单统计）

        使用空格分割文本进行统计，适用于大多数语言。
        注意：中文等语言可能需要更复杂的分词方法。

        Returns:
            int: 词的数量

        示例:
            segment = Segment(start=0, end=1, text="Hello world")
            print(segment.word_count)  # 输出: 2
        """
        return len(self.text.split())


class ASRResult(BaseModel):
    """完整的 ASR 结果，包含所有段落和元数据

    这是 ASR 流程的最终输出，包含了完整的转录、说话人、时间戳等信息。

    字段说明:
        segments: 所有转录段落的列表
            - 按时间顺序排列
            - 每个段落包含文本、时间戳、说话人等信息
        language: 检测到的语言代码
            - 'en': 英语
            - 'zh': 中文
            - 等等（遵循 ISO 639-1 标准）
        audio_duration: 音频总时长（秒）
            - 用于验证处理完整性
            - 计算处理速度
        model_name: 使用的 Whisper 模型名称
            - 例如 "medium", "large-v2"
            - 用于追溯和质量评估

    计算属性:
        total_segments: 段落总数
        unique_speakers: 唯一说话人集合
        speaker_count: 说话人数量

    便捷方法:
        get_segments_by_speaker(speaker_id): 获取特定说话人的所有段落
        to_text(include_speakers): 转换为纯文本格式

    用途:
        - 保存到文件（JSON 格式）
        - 传递给翻译模块
        - 生成字幕文件
        - 质量分析和统计
    """

    segments: list[Segment] = Field(description="所有转录段落的列表，按时间排序")
    language: str = Field(
        description="检测到的语言代码 (例如 'en', 'zh'，遵循 ISO 639-1)"
    )
    audio_duration: float = Field(ge=0, description="音频总时长（秒）")
    model_name: str = Field(
        description="使用的 ASR 模型名称 (例如 'medium', 'large-v2')"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "segments": [
                    {
                        "start": 0.5,
                        "end": 3.2,
                        "text": "Hello, welcome to the podcast.",
                        "speaker": "SPEAKER_00",
                        "words": [],
                    }
                ],
                "language": "en",
                "audio_duration": 3600.5,
                "model_name": "medium",
            }
        }
    }

    @property
    def total_segments(self) -> int:
        """获取段落总数

        Returns:
            int: 转录段落的数量

        用途:
            - 快速了解转录规模
            - 质量评估（段落数异常可能表示问题）
            - 翻译进度追踪

        示例:
            result = ASRResult(...)
            print(f"共有 {result.total_segments} 个段落")
        """
        return len(self.segments)

    @property
    def unique_speakers(self) -> set[str]:
        """获取唯一说话人集合

        从所有段落中提取不重复的说话人标签。
        注意：不包含 None（未识别说话人的段落）。

        Returns:
            set[str]: 说话人标签集合（例如 {"SPEAKER_00", "SPEAKER_01"}）

        用途:
            - 确定对话中的参与者数量
            - 按说话人统计发言
            - TTS 音色配置

        示例:
            result = ASRResult(...)
            speakers = result.unique_speakers
            print(f"检测到 {len(speakers)} 个说话人: {speakers}")
            # 输出: 检测到 2 个说话人: {'SPEAKER_00', 'SPEAKER_01'}
        """
        speakers = {seg.speaker for seg in self.segments if seg.speaker is not None}
        return speakers

    @property
    def speaker_count(self) -> int:
        """获取说话人数量

        这是 unique_speakers 的便捷属性，直接返回数量。

        Returns:
            int: 不同说话人的数量

        用途:
            - 快速判断是单人还是多人对话
            - 质量评估指标（播客通常应有 >= 2 个说话人）
            - Baseline 对比

        示例:
            result = ASRResult(...)
            if result.speaker_count >= 2:
                print("这是一个多人对话")
            else:
                print("这是单人讲话或说话人分离失败")
        """
        return len(self.unique_speakers)

    def get_segments_by_speaker(self, speaker_id: str) -> list[Segment]:
        """获取特定说话人的所有段落

        按说话人筛选段落，用于分析单个说话人的发言。

        Args:
            speaker_id: 说话人标签（例如 "SPEAKER_00"）

        Returns:
            list[Segment]: 该说话人的所有段落列表

        用途:
            - 统计某个说话人的发言时长
            - 单独导出某个说话人的文本
            - 分析说话人特征

        示例:
            result = ASRResult(...)
            speaker_0_segments = result.get_segments_by_speaker("SPEAKER_00")
            total_words = sum(seg.word_count for seg in speaker_0_segments)
            print(f"SPEAKER_00 共说了 {total_words} 个词")
        """
        return [seg for seg in self.segments if seg.speaker == speaker_id]

    def to_text(self, include_speakers: bool = True) -> str:
        """将 ASR 结果转换为纯文本格式

        生成可读的文本转录，可选择是否包含说话人标签。

        Args:
            include_speakers: 是否包含说话人标签
                - True: 每行前面加 [SPEAKER_XX] 标签
                - False: 只输出纯文本

        Returns:
            str: 格式化的文本转录，每个段落一行

        输出格式:
            包含说话人（include_speakers=True）:
                [SPEAKER_00] Hello, welcome to the podcast.
                [SPEAKER_01] Thank you for having me.
                [SPEAKER_00] Let's get started.

            纯文本（include_speakers=False）:
                Hello, welcome to the podcast.
                Thank you for having me.
                Let's get started.

        用途:
            - 保存为 TXT 文件
            - 快速浏览转录内容
            - 生成简单的字幕

        示例:
            result = ASRResult(...)

            # 保存为带说话人标签的文本
            with open("transcript.txt", "w") as f:
                f.write(result.to_text(include_speakers=True))

            # 保存为纯文本
            with open("transcript_plain.txt", "w") as f:
                f.write(result.to_text(include_speakers=False))
        """
        lines = []
        for seg in self.segments:
            if include_speakers and seg.speaker:
                # 格式: [SPEAKER_00] 文本内容
                lines.append(f"[{seg.speaker}] {seg.text}")
            else:
                # 格式: 文本内容
                lines.append(seg.text)
        return "\n".join(lines)


class ASRResultSegment(BaseModel):
    """ASR 结果片段

    用于表示从完整 ASR 结果中切分出来的片段。

    字段说明:
        segment_id: 片段唯一标识符（例如 "episode_001_seg_001"）
        episode_id: 所属剧集 ID
        segment_index: 片段在完整结果中的索引（从 1 开始）
        start_time: 片段在原始音频中的开始时间（秒）
        end_time: 片段在原始音频中的结束时间（秒）
        original_start_offset: 片段在原始音频中的起始偏移（秒）
        segments: 片段内的转录段落列表
        words: 片段内的词汇列表（可选）
        speakers: 片段内的说话人集合
        language: 检测到的语言
        model_name: 使用的 ASR 模型名称
        created_at: 创建时间
        file_path: 保存路径（可选）
    """

    segment_id: str = Field(description="片段唯一标识符")
    episode_id: str = Field(description="所属剧集 ID")
    segment_index: int = Field(ge=1, description="片段索引（从1开始）")
    start_time: float = Field(ge=0, description="在原始音频中的开始时间（秒）")
    end_time: float = Field(ge=0, description="在原始音频中的结束时间（秒）")
    original_start_offset: float = Field(ge=0, description="在原始音频中的起始偏移（秒）")

    # 片段内的 ASR 结果
    segments: list[Segment] = Field(description="转录段落列表")
    words: list[Word] = Field(default_factory=list, description="词汇列表（可选）")
    speakers: set[str] = Field(default_factory=set, description="片段内的说话人集合")
    language: str = Field(description="检测到的语言")
    model_name: str = Field(description="使用的 ASR 模型名称")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    file_path: Path | None = Field(None, description="保存路径（可选）")

    @property
    def duration(self) -> float:
        """获取片段时长（秒）"""
        return self.end_time - self.start_time

    @property
    def total_segments(self) -> int:
        """获取片段内的段落数"""
        return len(self.segments)

    @property
    def speaker_count(self) -> int:
        """获取片段内的说话人数量"""
        return len(self.speakers)


class ASRSplitMetadata(BaseModel):
    """ASR 结果切分元数据

    记录切分操作的整体信息。
    """

    episode_id: str = Field(description="剧集 ID")
    total_duration: float = Field(ge=0, description="音频总时长（秒）")
    segment_count: int = Field(ge=1, description="片段总数")
    target_duration: float = Field(gt=0, description="目标片段时长（秒）")
    segments: list[dict] = Field(description="片段信息列表")
    created_at: datetime = Field(default_factory=datetime.now, description="切分时间")
    model_name: str = Field(description="ASR 模型名称")

    model_config = {
        "json_schema_extra": {
            "example": {
                "episode_id": "episode_001",
                "total_duration": 3600.0,
                "segment_count": 6,
                "target_duration": 600.0,
                "segments": [
                    {
                        "segment_id": "segment_001",
                        "start_time": 0.0,
                        "end_time": 602.5,
                        "file_name": "segment_001.json",
                        "duration": 602.5
                    }
                ],
                "created_at": "2025-12-09T12:00:00",
                "model_name": "medium"
            }
        }
    }
