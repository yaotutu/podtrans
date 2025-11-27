# ASR 模块文档

自动语音识别 (Automatic Speech Recognition) 模块，负责将音频转换为带说话人标签的文字转录。

## 📋 概述

ASR 模块基于 WhisperX 和 pyannote.audio 实现，提供高质量的语音识别和说话人分离功能。

**主要功能**:
- 🎙️ 语音转文字 (WhisperX)
- ⏱️ 词级时间戳对齐
- 👥 说话人分离 (pyannote.audio)
- 🏷️ 说话人标签分配

**技术栈**:
- WhisperX: 快速、准确的语音识别
- pyannote.audio: 先进的说话人分离
- Pydantic v2: 数据验证和类型安全

## 🚀 快速开始

### 基础用法

```python
from podtrans.asr import WhisperXHandler

# 初始化处理器
handler = WhisperXHandler()

# 运行完整 ASR 流程
result = handler.process_full_pipeline("podcast.mp3")

# 查看结果
print(f"段落数: {result.total_segments}")
print(f"说话人数: {result.speaker_count}")
print(f"语言: {result.language}")

# 保存为文本
with open("transcript.txt", "w") as f:
    f.write(result.to_text(include_speakers=True))
```

### 配置选项

```python
# 指定模型和设备
handler = WhisperXHandler(
    model_name="medium",  # tiny/base/small/medium/large-v2/large-v3
    device="cpu",         # cuda/cpu (不推荐 mps)
    compute_type="int8",  # int8/float16/float32
)

# 指定语言（跳过自动检测，更快）
result = handler.process_full_pipeline(
    "podcast.mp3",
    language="en"
)

# 禁用说话人分离（更快，但无说话人标签）
result = handler.process_full_pipeline(
    "podcast.mp3",
    enable_diarization=False
)
```

## 📁 模块结构

```
src/podtrans/asr/
├── __init__.py              # 模块导出
├── whisperx_handler.py      # 核心处理器 (729行)
├── schemas.py               # 数据模型 (395行)
└── README.md                # 本文档
```

### 核心文件说明

#### `whisperx_handler.py`

核心 ASR 处理器，封装完整的语音识别流程。

**主要类**: `WhisperXHandler`

**关键方法**:
- `process_full_pipeline()`: 完整 ASR 流程 (推荐使用)
- `transcribe()`: 语音转文字
- `align()`: 词级时间戳对齐
- `diarize()`: 说话人分离
- `assign_speakers()`: 说话人标签分配

**优化特性** (v0.2.0):
- ✅ 音频数据复用（避免重复加载）
- ✅ 懒加载模型（按需加载）
- ✅ 详细的中文注释（355行+）

#### `schemas.py`

数据模型定义，使用 Pydantic 进行验证。

**核心模型**:
- `Word`: 词级数据（文本、时间戳、说话人）
- `Segment`: 句子级数据（包含多个词）
- `ASRResult`: 完整结果（包含所有段落）

**便捷方法**:
- `total_segments`: 段落总数
- `speaker_count`: 说话人数量
- `get_segments_by_speaker()`: 按说话人筛选
- `to_text()`: 转换为纯文本

## 🔧 配置参数

### 环境变量

在 `.env` 文件中配置：

```bash
# Whisper 模型配置
WHISPER_MODEL=medium          # 模型大小
DEVICE=cpu                    # 计算设备
COMPUTE_TYPE=int8             # 计算精度
ASR_BATCH_SIZE=16             # 批处理大小

# 说话人分离配置
HF_TOKEN=your_token_here      # HuggingFace token (必需)
```

### 模型选择指南

| 模型 | 磁盘空间 | 精度 | 速度 | 推荐场景 |
|------|---------|------|------|---------|
| tiny | ~75MB | ⭐⭐ | ⭐⭐⭐⭐⭐ | 快速测试 |
| base | ~150MB | ⭐⭐⭐ | ⭐⭐⭐⭐ | 快速处理 |
| small | ~500MB | ⭐⭐⭐⭐ | ⭐⭐⭐ | 平衡选择 |
| **medium** | ~1.5GB | ⭐⭐⭐⭐ | ⭐⭐⭐ | **推荐** |
| large-v2 | ~3GB | ⭐⭐⭐⭐⭐ | ⭐⭐ | 高精度需求 |
| large-v3 | ~3GB | ⭐⭐⭐⭐⭐ | ⭐⭐ | 最高精度 |

### 设备选择指南

| 设备 | 性能 | 兼容性 | 推荐配置 |
|------|------|--------|---------|
| **cuda** | ⭐⭐⭐⭐⭐ | NVIDIA GPU | `device=cuda, compute_type=float16` |
| **cpu** | ⭐⭐⭐ | 全平台 | `device=cpu, compute_type=int8` |
| mps | ⭐⭐ | Apple Silicon | ❌ 不推荐（兼容性差） |

**Apple Silicon 用户注意**:
- 推荐使用 `device=cpu, compute_type=int8`
- MPS 虽然更快但不稳定，会自动回退到 CPU

## 📊 性能数据

### 基准测试结果 (2025-11-27)

**测试环境**:
- 设备: Apple Silicon M4
- 模型: medium
- 配置: cpu + int8
- 音频: 13.7分钟播客

**处理时间**:
| 阶段 | 耗时 | 占比 |
|------|------|------|
| 转录 (Transcribe) | 3分31秒 | 30.4% |
| 对齐 (Align) | 17秒 | 2.4% |
| **说话人分离 (Diarize)** | **7分36秒** | **65.7%** ← 瓶颈 |
| 标签分配 (Assign) | 1秒 | 0.1% |
| 其他 (加载/保存) | 6秒 | 1.4% |
| **总计** | **11.5分钟** | **100%** |

**输出质量**:
- ✅ 段落数: 248
- ✅ 说话人数: 2
- ✅ 说话人保留率: 100%

**处理速度**: 0.84x 实时 (稍慢于实时)

### 性能优化历史

#### v0.2.0 (2025-11-27) - 音频复用优化

**问题**: 音频文件被重复加载3次
- `transcribe()` 加载一次
- `diarize()` 又加载一次
- `process_full_pipeline()` 再加载一次

**解决方案**:
- 修改 `transcribe()` 返回 `(result, audio)` 元组
- 修改 `diarize()` 接受可选的 `audio` 参数
- 在 `process_full_pipeline()` 中复用同一音频数组

**性能提升**:
- 小文件 (13分钟): 节省 ~1-2秒
- 中等文件 (30分钟): 节省 ~30-45秒
- 大文件 (60分钟): 节省 ~60-90秒

**日志证明**:
```
2025-11-27 15:20:11.233 | DEBUG | podtrans.asr.whisperx_handler:diarize:454 -
使用已加载的音频数组进行说话人分离（避免重复加载）
```

## 💡 优化建议

### 1️⃣ 说话人分离速度优化 (高优先级)

**现状**: 说话人分离占总时间的 65.7%，是最大瓶颈

**优化方案**:

**方案 A: 使用 GPU 加速**
```python
# 如果有 NVIDIA GPU
handler = WhisperXHandler(
    device="cuda",
    compute_type="float16"
)
```
预期提升: 3-5x 速度提升

**方案 B: 使用更快的说话人分离模型**
- 研究 pyannote.audio 的轻量级模型
- 或探索其他说话人分离方案（如 resemblyzer）

**方案 C: 可选说话人分离**
```python
# 对于单人音频，跳过说话人分离
result = handler.process_full_pipeline(
    audio_path,
    enable_diarization=False  # 节省 65% 时间
)
```

### 2️⃣ 批处理大小优化 (中优先级)

**现状**: 默认 batch_size=16

**优化方案**:
```python
# 如果内存充足，增加批处理大小
handler = WhisperXHandler()
result = handler.process_full_pipeline(
    audio_path,
    batch_size=32  # 或 64，根据可用内存调整
)
```
预期提升: 10-20% 转录速度提升（需要更多内存）

### 3️⃣ 模型缓存优化 (中优先级)

**现状**: 每次创建 `WhisperXHandler` 都会加载模型

**优化方案**: 实现全局模型管理器

```python
# 计划实现
class ModelManager:
    """全局模型管理器"""
    _models = {}

    @classmethod
    def get_whisper_model(cls, model_name, device, compute_type):
        key = f"whisper_{model_name}_{device}_{compute_type}"
        if key not in cls._models:
            cls._models[key] = whisperx.load_model(...)
        return cls._models[key]
```

预期提升:
- 首次加载: 无变化
- 后续使用: 节省 2-3秒模型加载时间

### 4️⃣ 流式处理 (低优先级)

**现状**: 一次性加载整个音频到内存

**优化方案**: 分块处理超长音频

```python
# 计划实现
def process_large_audio_streaming(audio_path, chunk_minutes=10):
    """分块处理超大音频文件"""
    # 1. 将音频分成10分钟的块
    # 2. 逐块处理
    # 3. 合并结果
    pass
```

适用场景: 超长音频 (>2小时) 或内存受限环境

### 5️⃣ 语言自动检测优化 (低优先级)

**现状**: 不指定语言时会自动检测，增加推理时间

**优化方案**:
```python
# 如果已知语言，显式指定
result = handler.process_full_pipeline(
    audio_path,
    language="en"  # 跳过自动检测
)
```

预期提升: 节省 5-10秒（首次检测时间）

## ⚠️ 已知问题

### 1. MPS 设备兼容性差

**问题**: Apple Silicon 的 MPS 设备不稳定

**症状**:
```
RuntimeError: torch.compile not supported on MPS
```

**解决方案**:
- 代码已自动回退到 CPU
- 用户无需手动干预

```python
# 自动处理逻辑 (whisperx_handler.py:106-111)
if self.device == "mps" and not torch.backends.mps.is_available():
    logger.warning("MPS 设备不可用，自动切换到 CPU。")
    self.device = "cpu"
```

### 2. pyannote.audio 版本警告

**警告信息**:
```
Model was trained with pyannote.audio 0.0.1, yours is 3.3.2.
Bad things might happen unless you revert pyannote.audio to 0.x.
```

**影响**:
- 功能正常，可以忽略
- 说话人分离质量未受影响

**解决方案**:
- 保持当前版本（3.3.2）
- 等待模型更新或降级（不推荐）

### 3. 说话人分离需要 HF_TOKEN

**问题**: 无 HF_TOKEN 时无法进行说话人分离

**解决方案**:
1. 访问 https://huggingface.co/settings/tokens 创建 token
2. 访问 https://huggingface.co/pyannote/speaker-diarization-3.1 接受使用协议
3. 在 `.env` 中设置 `HF_TOKEN=your_token_here`

**降级方案**:
- 禁用说话人分离: `enable_diarization=False`
- 所有 speaker 字段为 None

## 📝 开发指南

### 添加新功能

1. **修改 `whisperx_handler.py`**:
   - 添加新方法
   - 更新 `process_full_pipeline()` 集成新功能

2. **更新 `schemas.py`** (如需新字段):
   - 添加新字段到 Pydantic 模型
   - 更新示例和文档

3. **编写测试**:
   - 添加单元测试到 `tests/unit/test_asr.py`
   - 运行完整测试: `uv run pytest tests/unit/test_asr.py`

4. **更新文档**:
   - 更新本 README.md
   - 更新根目录 CLAUDE.md

### 代码风格

- 遵循 PEP 8
- 使用类型提示
- 添加详细的中文注释
- Docstring 格式: Google Style

### 测试

```bash
# 运行单元测试
uv run pytest tests/unit/test_asr.py -v

# 运行完整流程测试
uv run python scripts/test_pipeline.py --asr-only

# 查看测试报告
cat data/output/demo/test_report.md
```

## 🔗 相关文档

- **项目文档**: `/CLAUDE.md`
- **Baseline 系统**: `/BASELINE_SYSTEM.md`
- **测试脚本**: `/scripts/README.md`
- **翻译模块**: `/src/podtrans/translation/README.md`
- **TTS 模块**: `/src/podtrans/tts/README.md`

## 📚 参考资料

- [WhisperX GitHub](https://github.com/m-bain/whisperX)
- [pyannote.audio GitHub](https://github.com/pyannote/pyannote-audio)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Pydantic 文档](https://docs.pydantic.dev/)

## 🎯 路线图

### 已完成
- ✅ 基础 ASR 功能
- ✅ 说话人分离集成
- ✅ 音频复用优化
- ✅ 详细中文注释
- ✅ 性能基准测试

### 计划中
- [ ] 全局模型管理器
- [ ] GPU 性能优化
- [ ] 流式处理支持
- [ ] 更快的说话人分离方案
- [ ] 质量评估指标

### 未来可能
- [ ] 实时转录支持
- [ ] 多语言混合识别
- [ ] 自定义模型微调
- [ ] 字幕文件导出 (SRT/VTT)

---

**文档版本**: v0.2.0
**最后更新**: 2025-11-27
**维护者**: PodTrans Team
