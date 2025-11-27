# PodTrans 架构设计

## 总体架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   RSS Feed  │────▶│     ASR     │────▶│ Translation │────▶│     TTS     │
│   Fetcher   │     │   (Whisper) │     │  (Claude)   │     │  (SoulX)    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │                    │
      │                    │                    │                    │
      ▼                    ▼                    ▼                    ▼
  audio.mp3          asr_result.json    translation.json      audio_zh.mp3
```

## 设计原则

### 1. 模块化设计
每个模块（ASR、Translation、TTS）都是独立的：
- **单一职责**：每个模块只做一件事
- **可测试性**：可以单独测试每个模块
- **可替换性**：可以替换任何模块的实现（如换用其他 TTS 引擎）

### 2. 统一接口
所有模块遵循相同的接口规范：

```python
class PipelineStage(ABC):
    def process(self, input_data) -> output_data:
        """处理数据"""
        pass
```

### 3. 类型安全
使用 Pydantic 模型确保数据在模块间传递时的类型安全：
- 自动验证
- IDE 支持
- 运行时检查

## 当前实现状态

### ✅ ASR 模块（已完成）

**接口：**
```python
# 输入：Path（音频文件路径）
# 输出：ASRResult（Pydantic 模型）

handler = WhisperXHandler()
result = handler.process_full_pipeline(
    audio_path=Path("audio.mp3"),
    language="en",  # 可选
    enable_diarization=True  # 可选
)

# result.segments: List[Segment]
# result.language: str
# result.audio_duration: float
# result.model_name: str
```

**优点：**
- ✅ 清晰的输入输出接口
- ✅ 使用 Pydantic 进行类型验证
- ✅ 完整的错误处理
- ✅ 支持词级时间戳
- ✅ 支持说话人分离

**当前设计是否适合流水线？**
✅ **是的，设计很标准！** 但可以进一步优化以更好地集成到流水线中。

### 改进建议

#### 1. 实现 PipelineStage 接口

让 ASR 模块实现标准的 `PipelineStage` 接口：

```python
# src/podtrans/asr/stage.py
from pathlib import Path
from podtrans.pipeline.base import PipelineStage
from podtrans.asr.schemas import ASRResult
from podtrans.asr.whisperx_handler import WhisperXHandler

class ASRStage(PipelineStage[Path, ASRResult]):
    """ASR pipeline stage using WhisperX."""

    def __init__(self, model_name: str = "medium", device: str = "cpu"):
        self.handler = WhisperXHandler(model_name, device)

    def process(self, input_data: Path) -> ASRResult:
        """Process audio file through ASR."""
        return self.handler.process_full_pipeline(
            audio_path=input_data,
            enable_diarization=True
        )

    def validate_input(self, input_data: Path) -> None:
        """Validate input audio file."""
        if not input_data.exists():
            raise FileNotFoundError(f"Audio file not found: {input_data}")
        if input_data.suffix not in [".mp3", ".wav", ".flac", ".m4a"]:
            raise ValueError(f"Unsupported audio format: {input_data.suffix}")
```

#### 2. 定义数据流接口

各模块之间的数据传递接口：

```python
# RSS Fetcher → ASR
Input:  None (从 RSS feed 自动获取)
Output: Path (下载的音频文件路径)

# ASR → Translation
Input:  Path (音频文件路径)
Output: ASRResult (包含转录文本和时间戳)

# Translation → TTS
Input:  ASRResult (英文转录)
Output: TranslationResult (中文翻译)

# TTS → Final Output
Input:  TranslationResult (中文文本 + 时间戳)
Output: Path (生成的中文音频文件)
```

#### 3. Pipeline 编排器

创建一个编排器来串联所有模块：

```python
# src/podtrans/pipeline/orchestrator.py
class PodcastPipeline:
    """Complete podcast translation pipeline."""

    def __init__(self):
        self.asr_stage = ASRStage(model_name="medium")
        self.translation_stage = TranslationStage()
        self.tts_stage = TTSStage()

    def run(self, audio_path: Path) -> Path:
        """Run complete pipeline."""
        # Step 1: ASR
        asr_result = self.asr_stage.process(audio_path)

        # Step 2: Translation
        translation_result = self.translation_stage.process(asr_result)

        # Step 3: TTS
        output_audio = self.tts_stage.process(translation_result)

        return output_audio
```

## 未来模块设计指南

### Translation 模块（Milestone 2）

```python
class TranslationStage(PipelineStage[ASRResult, TranslationResult]):
    """Translation stage using Claude API."""

    def process(self, input_data: ASRResult) -> TranslationResult:
        """Translate ASR segments to Chinese."""
        # 实现翻译逻辑
        pass
```

**需要考虑：**
- 批量翻译（提高效率）
- 保留时间戳（与原音频对齐）
- 保留说话人信息
- 处理 API 限流和重试

### TTS 模块（Milestone 3）

```python
class TTSStage(PipelineStage[TranslationResult, Path]):
    """TTS stage using SoulX-Podcast."""

    def process(self, input_data: TranslationResult) -> Path:
        """Generate Chinese audio from translated text."""
        # 实现 TTS 逻辑
        pass
```

**需要考虑：**
- 多说话人支持（不同的声音）
- 音频拼接（按时间戳）
- 音质控制
- 语速和音调

### RSS Fetcher（未来）

```python
class RSSFetcher:
    """Fetch podcasts from RSS feeds."""

    def fetch_latest(self, feed_url: str) -> Path:
        """Download latest episode."""
        # 实现 RSS 获取逻辑
        pass
```

## 数据流示例

完整的数据流转：

```python
# 1. RSS Fetcher 下载音频
audio_file = rss_fetcher.fetch_latest("https://podcast.rss")
# audio_file = Path("episode_123.mp3")

# 2. ASR 转录
asr_result = asr_stage.process(audio_file)
# asr_result = ASRResult(
#     segments=[
#         Segment(start=0.0, end=2.5, text="Welcome to our podcast", speaker="SPEAKER_00"),
#         Segment(start=2.5, end=5.0, text="Today we discuss...", speaker="SPEAKER_01"),
#     ],
#     language="en",
#     ...
# )

# 3. Translation 翻译
translation_result = translation_stage.process(asr_result)
# translation_result = TranslationResult(
#     segments=[
#         TranslatedSegment(start=0.0, end=2.5, text="欢迎来到我们的播客", speaker="SPEAKER_00"),
#         TranslatedSegment(start=2.5, end=5.0, text="今天我们讨论...", speaker="SPEAKER_01"),
#     ],
#     ...
# )

# 4. TTS 生成音频
output_audio = tts_stage.process(translation_result)
# output_audio = Path("episode_123_zh.mp3")
```

## 错误处理策略

1. **每个阶段独立的错误处理**
   - ASR 失败 → 保存原音频，标记失败
   - Translation 失败 → 保存 ASR 结果，可以重试翻译
   - TTS 失败 → 保存翻译结果，可以重试 TTS

2. **Pipeline 级别的容错**
   - 记录每个阶段的状态
   - 支持从任何阶段恢复
   - 完整的日志记录

3. **重试机制**
   - API 调用失败自动重试
   - 指数退避策略

## 总结

### 当前 ASR 模块设计评价：✅ 标准且优秀

**优点：**
- ✅ 接口清晰，职责单一
- ✅ 使用 Pydantic 保证类型安全
- ✅ 完整的功能实现
- ✅ **已经适合流水线集成**

**建议改进：**
- 💡 实现 `PipelineStage` 接口（可选，但更标准）
- 💡 添加 Pipeline 编排器
- 💡 统一的错误处理和状态管理

**下一步：**
1. 继续实现 Translation 模块（遵循相同的设计模式）
2. 实现 TTS 模块
3. 实现 Pipeline 编排器
4. 最后添加 RSS Fetcher（如需要）

你的当前设计已经很好了，可以直接基于现有的 ASR 模块继续开发！
