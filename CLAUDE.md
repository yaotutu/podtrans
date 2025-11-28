# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供项目开发指引。

## 📋 项目概述

**PodTrans** - AI 驱动的播客翻译流水线

将英文播客自动翻译为中文播客，完整保留说话人信息和语音风格。采用模块化架构设计：

```
English Audio → ASR (WhisperX) → Translation (Qwen) → TTS (SoulX) → Chinese Audio
```

**当前状态**:
- ✅ Milestone 1: ASR 模块（语音识别 + 说话人分离）
- ✅ Milestone 2: Translation 模块（智能批处理翻译）
- ✅ Milestone 3: TTS 模块（SoulX-Podcast 集成）
- 🚧 Milestone 4: 流程编排 + 端到端测试

**目标平台**: macOS (Apple Silicon M4), Linux, Windows

---

## 🔧 核心技术栈

### 基础框架
- **Python 3.12+** - 现代 Python 特性
- **uv** - 快速包管理器
- **Pydantic v2** - 数据验证和配置管理
- **Typer** - CLI 框架
- **Rich** - 终端美化输出
- **loguru** - 结构化日志

### 核心模块
- **ASR**: WhisperX + pyannote.audio (语音识别 + 说话人分离)
- **Translation**: DashScope/Qwen (OpenAI-compatible API)
- **TTS**: SoulX-Podcast (多说话人语音合成)

### 工具库
- **tiktoken** - Token 计数（智能批处理）
- **httpx** - 异步 HTTP 客户端
- **orjson** - 高性能 JSON 序列化

---

## 🚀 快速开始

### 环境设置

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境变量
cp .env.example .env

# 3. 编辑 .env 文件，填入必需的 API keys:
#    - HF_TOKEN: HuggingFace token (用于说话人分离)
#    - DASHSCOPE_API_KEY: 阿里云 DashScope API key (用于翻译)
#    - SOULX_API_URL: SoulX-Podcast 服务地址 (可选)
```

### API Keys 获取

1. **HF_TOKEN** (HuggingFace):
   - 访问 https://huggingface.co/settings/tokens
   - 创建 Access Token
   - 访问以下模型并点击 "Agree and access repository":
     - https://huggingface.co/pyannote/speaker-diarization-3.1
     - https://huggingface.co/pyannote/segmentation-3.0

2. **DASHSCOPE_API_KEY** (阿里云):
   - 访问 https://dashscope.console.aliyun.com/
   - 创建 API Key

---

## 💻 常用命令

### 主要流程

```bash
# 1. ASR - 语音识别 + 说话人分离
uv run podtrans transcribe data/input/demo.mp3

# 2. 翻译
uv run podtrans translate data/output/demo/asr_result.json

# 3. TTS - 音频生成 (需要外部 SoulX 服务)
uv run podtrans synthesize data/output/demo/translation_result.json
```

### ASR 选项

```bash
# 指定输出目录
uv run podtrans transcribe podcast.mp3 -o ./my_output

# 指定语言（跳过自动检测）
uv run podtrans transcribe podcast.mp3 -l en

# 禁用说话人分离
uv run podtrans transcribe podcast.mp3 --no-diarization

# 指定 Whisper 模型
uv run podtrans transcribe podcast.mp3 -m large-v3
```

### 翻译选项

```bash
# 指定源语言和目标语言
uv run podtrans translate asr_result.json -s en -t zh

# 指定输出目录
uv run podtrans translate asr_result.json -o ./translations
```

### TTS 选项

```bash
# 基础用法
uv run podtrans synthesize translation_result.json

# 指定输出文件
uv run podtrans synthesize translation_result.json -o output.wav

# 提供说话人语音样本
uv run podtrans synthesize translation_result.json \
  --speaker-audio SPEAKER_00=voices/male.wav \
  --speaker-audio SPEAKER_01=voices/female.wav

# 提供说话人描述
uv run podtrans synthesize translation_result.json \
  --speaker-desc SPEAKER_00=中年男性，声音低沉 \
  --speaker-desc SPEAKER_01=年轻女性，声音清脆
```

### 基准版本管理

```bash
# 对比当前输出与 baseline
uv run python scripts/compare_with_baseline.py

# 更新 baseline（会先显示对比结果并询问确认）
uv run python scripts/update_baseline.py

# 手动转换为 SoulX 格式（用于外部测试）
uv run python scripts/convert_to_soulx.py
```

### 开发和测试

```bash
# 运行所有测试
uv run pytest

# 运行特定类型测试
uv run pytest tests/unit/          # 单元测试
uv run pytest tests/integration/   # 集成测试
uv run pytest -m "not slow"        # 跳过慢速测试

# 生成覆盖率报告
uv run pytest --cov=src/podtrans --cov-report=html

# 代码检查
uv run ruff check .                # Linting
uv run ruff format .               # 格式化
uv run mypy src/                   # 类型检查
uv run ruff check --fix .          # 自动修复问题
```

---

## 🏗️ 项目架构

### 目录结构

```
podtrans/
├── src/podtrans/           # 源代码
│   ├── asr/                # ASR 模块
│   │   ├── __init__.py
│   │   ├── schemas.py      # ASRResult, Segment, Word
│   │   └── whisperx_handler.py
│   ├── translation/        # 翻译模块
│   │   ├── __init__.py
│   │   ├── schemas.py      # TranslationResult, TranslatedSegment
│   │   ├── translator.py
│   │   ├── KNOWN_ISSUES.md
│   │   └── README.md
│   ├── tts/                # TTS 模块
│   │   ├── __init__.py
│   │   ├── schemas.py      # TTSResult, SpeakerConfig
│   │   ├── base.py         # TTSService 抽象基类
│   │   └── soulx/
│   │       ├── converter.py  # SoulX 格式转换器
│   │       └── client.py     # SoulX HTTP 客户端
│   ├── utils/              # 工具函数
│   ├── config.py           # 配置管理
│   ├── models.py           # 通用数据模型
│   └── cli.py              # CLI 入口
├── scripts/                # 辅助脚本
│   ├── README.md
│   ├── compare_with_baseline.py
│   ├── update_baseline.py
│   ├── convert_to_soulx.py
│   └── test_soulx_format.py
├── data/
│   ├── input/              # 输入音频
│   ├── output/             # 处理结果
│   ├── baseline/           # 基准版本
│   │   ├── demo_v1_baseline/
│   │   ├── archive/
│   │   └── README.md
│   └── cache/              # 模型缓存
├── tests/                  # 测试文件
├── docs/                   # 文档目录
│   ├── SETUP_GUIDE.md      # 新电脑快速启动指南 ⭐
│   ├── BASELINE_SYSTEM.md  # 基准系统文档
│   └── CHANGELOG.md        # 变更日志
├── CLAUDE.md               # 本文件 (开发指引)
├── README.md               # 项目说明
├── pyproject.toml          # 项目配置
└── .env.example            # 环境变量模板
```

### 模块设计

#### 1. ASR 模块 (`src/podtrans/asr/`)

**功能**: 语音识别 + 说话人分离

**核心类**: `WhisperXHandler`

**流程**:
```python
1. transcribe()      # Whisper 转录
2. align()           # 词级时间戳对齐
3. diarize()         # pyannote.audio 说话人分离
4. assign_speakers() # 分配说话人标签
5. 输出 ASRResult    # {segments, language, speakers, duration}
```

**关键配置**:
- `WHISPER_MODEL`: tiny/base/small/medium/large-v2/large-v3 (默认: medium)
- `DEVICE`: cuda/cpu (注意: MPS 不支持，会自动回退到 CPU)
- `COMPUTE_TYPE`: float16(GPU)/int8(CPU)
- `ASR_BATCH_SIZE`: 批处理大小（默认: 16）

**注意事项**:
- 需要 `HF_TOKEN` 才能进行说话人分离
- 无 token 时仍可转录，但所有 speaker 字段为 null
- Apple Silicon 使用 `device=cpu`, `compute_type=int8`

#### 2. Translation 模块 (`src/podtrans/translation/`)

**功能**: 智能批处理翻译，保留说话人信息

**核心类**: `Translator`

**流程**:
```python
1. _create_smart_batches()  # 基于 token 数智能分批
2. _translate_batch()       # 调用 DashScope API
3. 重试机制 (max 3 次)
4. 输出 TranslationResult   # {segments, language, model, metadata}
```

**智能批处理**:
- Token 计数: tiktoken (cl100k_base encoding)
- 最大 tokens/批: 120k (适配 128k 上下文模型)
- 最大 segments/批: 100 (稳定性考虑)
- 开销估算: 系统 prompt 500 + 每段输出 100 tokens

**关键配置**:
- `TRANSLATION_MODEL`: qwen-max/qwen-plus/qwen-turbo (默认: qwen-max)
- `TRANSLATION_MAX_TOKENS`: 120000
- `TRANSLATION_MAX_SEGMENTS_PER_BATCH`: 100
- `TRANSLATION_MAX_RETRIES`: 3

**已知问题**:
- API 偶尔返回数量不匹配（2-3% 丢失率）
- 详见 `src/podtrans/translation/KNOWN_ISSUES.md`

#### 3. TTS 模块 (`src/podtrans/tts/`)

**功能**: 文本转语音，保留说话人区分

**核心类**:
- `TTSService` (抽象基类)
- `SoulXClient` (SoulX-Podcast 实现)
- `SoulXConverter` (格式转换器)

**流程**:
```python
1. convert_format()  # TranslationResult → SoulX JSON
   - 说话人映射: SPEAKER_00 → S1, SPEAKER_01 → S2
   - 构建 speakers: {S1: {audio, desc}, S2: {...}}
   - 构建 text: [[S1, "文本1"], [S2, "文本2"]]
2. synthesize()      # HTTP POST 到 SoulX 服务
3. 输出 TTSResult    # {audio_path, duration, format}
```

**SoulX 格式**:
```json
{
  "speakers": {
    "S1": {
      "prompt_audio": "path/to/voice_sample.wav",
      "prompt_text": "声音特征描述"
    }
  },
  "text": [
    ["S1", "你好，欢迎收听。"],
    ["S2", "很高兴见到你。"]
  ]
}
```

**关键配置**:
- `SOULX_API_URL`: http://localhost:8000 (需外部部署)
- `SOULX_TIMEOUT`: 300 秒

**设计原则**:
- 格式转换在 TTS 层完成，保持 Translation 模块通用性
- 易于扩展其他 TTS 服务（继承 TTSService）

### 配置管理

**文件**: `src/podtrans/config.py`

**实现**: Pydantic Settings + 单例模式

**优先级**: 环境变量 > .env 文件 > 默认值

**使用**:
```python
from podtrans.config import get_settings

settings = get_settings()  # 单例
settings.hf_token          # 访问配置
settings.whisper_model
```

**重要配置项**:

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| HF Token | `HF_TOKEN` | None | HuggingFace token |
| DashScope Key | `DASHSCOPE_API_KEY` | None | 翻译 API key |
| Whisper 模型 | `WHISPER_MODEL` | medium | ASR 模型大小 |
| 设备 | `DEVICE` | cpu | cuda/cpu |
| 翻译模型 | `TRANSLATION_MODEL` | qwen-max | Qwen 模型 |
| 批次大小 | `TRANSLATION_MAX_SEGMENTS_PER_BATCH` | 100 | 每批段落数 |
| Token 限制 | `TRANSLATION_MAX_TOKENS` | 120000 | 每批 tokens |

### 数据模型

所有模型基于 Pydantic v2，使用 `model_dump()` 序列化。

#### ASR 模型 (`asr/schemas.py`)

```python
class Word(BaseModel):
    word: str
    start: float
    end: float
    score: float | None
    speaker: str | None

class Segment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None
    words: list[Word]

class ASRResult(BaseModel):
    segments: list[Segment]
    language: str
    audio_duration: float
    model_name: str

    @property
    def total_segments(self) -> int
    @property
    def speaker_count(self) -> int
```

#### Translation 模型 (`translation/schemas.py`)

```python
class TranslatedSegment(BaseModel):
    start: float
    end: float
    original_text: str
    translated_text: str
    speaker: str | None

class TranslationResult(BaseModel):
    segments: list[TranslatedSegment]
    source_language: str
    target_language: str
    model_name: str

    @property
    def total_segments(self) -> int
    @property
    def speaker_count(self) -> int
```

#### TTS 模型 (`tts/schemas.py`)

```python
class SpeakerConfig(BaseModel):
    speaker_id: str
    voice_sample: Path | None
    voice_description: str | None

class TTSResult(BaseModel):
    audio_path: Path
    format: str = "wav"
    duration: float | None
    sample_rate: int = 24000
    service: str
    segments_count: int
```

### CLI 架构

**文件**: `src/podtrans/cli.py`

**框架**: Typer + Rich

**命令**:
- `podtrans transcribe` - ASR 语音识别
- `podtrans translate` - 翻译
- `podtrans synthesize` - TTS 音频生成
- `podtrans version` - 版本信息

**每个命令包含**:
1. 参数验证和类型检查
2. 配置加载和验证
3. Rich 进度显示
4. 错误处理和日志记录
5. 结果保存和预览
6. PipelineMetadata 跟踪

---

## 📊 基准版本管理系统

### 概述

项目使用 baseline 系统持续跟踪优化效果。当前最佳版本存储在 `data/baseline/demo_v1_baseline/`。

### 核心脚本 (`scripts/`)

详细文档见 `scripts/README.md` 和 `docs/BASELINE_SYSTEM.md`。

| 脚本 | 功能 | 用法 |
|------|------|------|
| `compare_with_baseline.py` | 对比质量指标 | `uv run python scripts/compare_with_baseline.py` |
| `update_baseline.py` | 更新基准版本 | `uv run python scripts/update_baseline.py` |
| `convert_to_soulx.py` | SoulX 格式转换 | `uv run python scripts/convert_to_soulx.py` |
| `test_soulx_format.py` | 格式验证测试 | `uv run python scripts/test_soulx_format.py` |

### 质量评估标准

**必须指标** (Must Have):
- ✅ 说话人检测数 ≥ 2
- ✅ 段落完整性 ≥ 98% (丢失率 ≤ 2%)
- ✅ 说话人保留率 = 100%

**优化指标** (Nice to Have):
- ⏱️ 处理速度 (↓ 更快)
- 💰 API 成本 (↓ 更低)
- 📝 翻译质量 (↑ 更好)
- 🎤 说话人准确率 (↑ 更准)

### 优化工作流

```bash
# 1. 修改配置或代码
vim .env
vim src/podtrans/translation/translator.py

# 2. 重新运行流程
uv run podtrans transcribe data/input/demo.mp3
uv run podtrans translate data/output/demo/asr_result.json

# 3. 对比结果
uv run python scripts/compare_with_baseline.py

# 4. 评估改进
#    - 检查必须指标
#    - 比较优化指标
#    - 主观评价翻译质量

# 5. 如果质量提升，更新 baseline
uv run python scripts/update_baseline.py

# 6. 记录改进点
vim data/baseline/README.md
```

### Baseline 版本规范

每次更新 `data/baseline/README.md` 需记录:
- 创建时间和版本号
- 配置参数变更
- 质量指标对比
- 改进点说明
- 已知问题

---

## ⚠️ 重要注意事项

### 1. 设备兼容性

**Apple Silicon (M1/M2/M3/M4)**:
- ✅ 使用 `device=cpu`, `compute_type=int8`
- ❌ **不要**使用 `device=mps`（WhisperX 不支持，会报错）
- 📝 代码会自动检测并回退到 CPU

**NVIDIA GPU**:
- ✅ 使用 `device=cuda`, `compute_type=float16`
- 需要 CUDA 12.8+

**CPU Only**:
- ✅ 使用 `device=cpu`, `compute_type=int8`
- 处理速度较慢但稳定

### 2. API Keys 说明

**HF_TOKEN** (HuggingFace):
- 用途: 下载 pyannote.audio 模型，启用说话人分离
- 可选性: 无 token 时 ASR 仍可运行，但无说话人标签
- 获取: https://huggingface.co/settings/tokens
- 授权: 需接受 pyannote 模型使用协议

**DASHSCOPE_API_KEY** (阿里云):
- 用途: 调用 Qwen 模型进行翻译
- 必需性: 翻译模块必需
- 获取: https://dashscope.console.aliyun.com/

### 3. 数据目录

```
data/
├── input/              # 手动放置输入音频
├── output/             # 自动生成，每次运行可覆盖
├── baseline/           # 版本管理，提交到 git
│   ├── demo_v1_baseline/  # 当前最佳版本
│   ├── archive/        # 历史版本（不提交）
│   └── README.md       # 版本说明
└── cache/              # 模型缓存（不提交）
```

**Git 管理**:
- ✅ 提交: `data/baseline/demo_v1_baseline/`, `data/baseline/README.md`
- ❌ 忽略: `data/input/*`, `data/output/*`, `data/cache/*`, `data/baseline/archive/*`

### 4. 错误处理

- CLI 失败时保存 `pipeline_metadata.json` 记录错误
- 翻译 API 有重试机制（默认 3 次，可配置）
- 说话人分离失败会警告但继续执行
- 所有异常通过 loguru 记录到控制台

### 5. Pydantic 最佳实践

```python
# ✅ 正确 - Pydantic v2
result.model_dump()
result.model_dump_json()

# ❌ 错误 - Pydantic v1 (已弃用)
result.dict()
result.json()
```

Path 对象自动序列化为字符串。

---

## 🧪 测试

### Pytest Markers

```bash
-m "unit"         # 单元测试（快速）
-m "integration"  # 集成测试（较慢）
-m "e2e"          # 端到端测试（很慢）
-m "not slow"     # 跳过所有慢速测试
```

### 测试结构

```
tests/
├── unit/           # 单元测试（不依赖外部服务）
├── integration/    # 集成测试（可能需要 API keys）
├── e2e/            # 端到端测试（需要完整环境）
└── fixtures/       # 测试数据
```

### 覆盖率

```bash
# HTML 报告
uv run pytest --cov=src/podtrans --cov-report=html
open htmlcov/index.html

# 终端报告
uv run pytest --cov=src/podtrans --cov-report=term
```

---

## 📝 代码风格

### 通用规范

- **Line length**: 88 字符 (ruff 默认)
- **Imports**: 自动排序 (isort 集成在 ruff)
- **Type hints**: 必需（mypy strict mode）
- **Quotes**: 双引号优先
- **Docstrings**: Google style

### Ruff 配置

**忽略规则**:
- `B008` - 允许在参数默认值中调用函数（Typer 需要）
- `B904` - 允许异常处理不使用 `from`

**执行**:
```bash
uv run ruff check .        # 检查
uv run ruff check --fix .  # 自动修复
uv run ruff format .       # 格式化
```

### Mypy 配置

- Strict mode
- 测试文件除外 (`exclude = ["tests/"]`)
- 忽略第三方库: whisperx, pyannote, pydub

---

## 🗺️ 开发路线图

### 已完成

- [x] **Milestone 1**: 项目骨架 + ASR 模块
  - WhisperX 集成
  - pyannote.audio 说话人分离
  - CLI 基础架构

- [x] **Milestone 2**: 翻译模块
  - DashScope API 集成
  - 智能批处理（基于 token 计数）
  - 错误重试机制

- [x] **Milestone 3**: TTS 模块
  - SoulX-Podcast HTTP 客户端
  - 格式转换器（适配器模式）
  - 说话人配置支持

### 进行中

- [ ] **Milestone 4**: 流程编排 + E2E 测试
  - 端到端流水线
  - 完整的集成测试
  - 性能基准测试

### 未来计划

- [ ] RSS 订阅自动化
- [ ] Web UI（Gradio/Streamlit）
- [ ] 批量处理
- [ ] 多语言支持（不仅限于英→中）
- [ ] 云部署方案
- [ ] Docker 容器化

---

## 🔗 相关文档

- **README.md** - 项目介绍和快速开始
- **docs/SETUP_GUIDE.md** - 新电脑快速启动指南 (10 分钟上手)
- **docs/BASELINE_SYSTEM.md** - 基准系统完整文档
- **docs/CHANGELOG.md** - 变更日志
- **scripts/README.md** - 脚本工具使用指南
- **src/podtrans/translation/README.md** - 翻译模块详细说明
- **src/podtrans/translation/KNOWN_ISSUES.md** - 已知问题和解决方案
- **data/baseline/README.md** - Baseline 版本历史

---

## 💡 开发提示

### 添加新功能

1. 确定所属模块（asr/translation/tts）
2. 更新对应的 schemas.py（如需新数据模型）
3. 实现核心逻辑
4. 添加 CLI 命令（如需用户交互）
5. 编写测试
6. 更新相关文档

### 添加新脚本

1. 在 `scripts/` 目录创建文件
2. 添加 docstring 说明用途
3. 更新 `scripts/README.md`
4. 更新本文件 (CLAUDE.md)

### 调试技巧

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
uv run podtrans transcribe ...

# 查看配置加载
uv run python -c "from podtrans.config import get_settings; print(get_settings())"

# 测试单个模块
uv run python -m podtrans.asr.whisperx_handler
```

### 常见问题

**Q: ASR 在 Mac 上很慢**
A: 确认使用 `device=cpu` 和 `compute_type=int8`，不要用 mps

**Q: 翻译丢失部分段落**
A: 已知问题，丢失率 ~2%，详见 `translation/KNOWN_ISSUES.md`

**Q: SoulX TTS 报错连接失败**
A: 需要外部部署 SoulX-Podcast 服务，默认地址 http://localhost:8000

**Q: 说话人分离不工作**
A: 检查是否设置了 `HF_TOKEN` 并接受了 pyannote 模型授权

---

**文档版本**: 2025-11-27
**项目版本**: 0.1.0
**最后更新**: Milestone 3 完成后
