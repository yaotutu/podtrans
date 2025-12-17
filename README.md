# PodTrans 🎙️

> AI 驱动的播客翻译流水线：英文播客 → 中文播客 (保留说话人信息和语音风格)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## 📋 项目简介

PodTrans 是一个全自动的播客翻译工具,可以将英文播客翻译成自然流畅的中文播客,并完整保留说话人信息和语音风格。

### ✨ 核心特性

- **🎯 高精度语音识别 (ASR)**: 基于 WhisperX 3.7.4,支持词级时间戳对齐
- **👥 智能说话人分离**: 基于 pyannote.audio 3.3.2,准确识别和标记不同说话人
- **🌐 智能批处理翻译**: 使用阿里云 Qwen 模型,自动优化批次大小,支持长文本翻译
- **🔊 多说话人 TTS**: 集成 SoulX-Podcast,生成自然的中文播客音频
- **📊 质量保障**: 完整的 baseline 系统,持续跟踪优化效果

### 🎬 工作流程

```
English Audio (MP3)
         ↓
    [WhisperX 3.7.4 + pyannote.audio 3.3.2]
    • 语音识别 (Whisper large-v2)
    • 词级时间戳对齐 (wav2vec2)
    • 说话人分离 (pyannote diarization)
         ↓
Speaker-labeled Transcript (JSON)
{
  "segments": [
    {"speaker": "SPEAKER_00", "text": "Hello...", "start": 0.0, "end": 2.5},
    {"speaker": "SPEAKER_01", "text": "Hi there...", "start": 2.5, "end": 5.0}
  ]
}
         ↓
    [DashScope Qwen Translation]
    • 智能批处理 (基于 token 计数)
    • 保留说话人标签
    • 自动重试机制
         ↓
Chinese Podcast Script (JSON)
{
  "segments": [
    {"speaker": "SPEAKER_00", "original": "Hello...", "translated": "你好..."},
    {"speaker": "SPEAKER_01", "original": "Hi there...", "translated": "嗨,你好..."}
  ]
}
         ↓
    [SoulX-Podcast TTS]
    • 多说话人语音合成
    • 保留语音风格
         ↓
Chinese Audio (WAV)
```

---

## 🚀 快速开始

### 前置要求

- **Conda** (必需, 用于环境管理)
- **Python 3.11+** (必需, 通过 conda 安装)
- **FFmpeg** (可选但推荐,用于音频处理)
- **HuggingFace Token** (必需,用于说话人分离)
- **DashScope API Key** (必需,用于翻译)
- **CUDA 12.1+** (推荐,用于GPU加速)

### 10 分钟安装指南

```bash
# 1. 安装 Miniconda (如果尚未安装)
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
# 或者使用系统包管理器: sudo apt install conda

# 2. 克隆项目
git clone https://github.com/YOUR_USERNAME/podtrans.git
cd podtrans

# 3. 创建并激活 conda 环境
conda env create -f environment.yml
conda activate podtrans

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件,填入以下必需的 API keys:
#   - HF_TOKEN: 从 https://huggingface.co/settings/tokens 获取
#   - LLM_API_KEY: 从 https://dashscope.console.aliyun.com/ 或其他 LLM 服务商获取

# 5. 验证安装
python -c "from podtrans.asr import WhisperXHandler; print('✅ 安装成功!')"
```

**详细文档**:
- **[GETTING_STARTED.md](docs/GETTING_STARTED.md)** - 🌟 **完全上手指南** (手把手教程,新用户必读!)
- [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) - 快速安装指南
- [MODEL_DOWNLOAD_GUIDE.md](docs/MODEL_DOWNLOAD_GUIDE.md) - 模型下载详解

---

## 💻 使用方法

### 基本工作流

```bash
# 准备输入音频
cp your_podcast.mp3 data/input/

# Step 1: ASR - 语音识别 + 说话人分离
python -m podtrans.cli transcribe data/input/your_podcast.mp3
# 输出: output/your_podcast/asr_result.json

# Step 2: Translation - 智能批处理翻译
python -m podtrans.cli translate output/your_podcast/asr_result.json
# 输出: output/your_podcast/translation_result.json

# Step 3: TTS - 多说话人语音合成 (需要外部 SoulX 服务)
python -m podtrans.cli synthesize output/your_podcast/translation_result.json
# 输出: output/your_podcast/output.wav
```

### 常用选项

#### ASR 选项

```bash
# 指定输出目录
python -m podtrans.cli transcribe podcast.mp3 -o ./my_output

# 指定语言 (跳过自动检测,加快速度)
python -m podtrans.cli transcribe podcast.mp3 -l en

# 禁用说话人分离 (仅转录文本)
python -m podtrans.cli transcribe podcast.mp3 --no-diarization

# 使用更大的 Whisper 模型 (更准确但更慢)
python -m podtrans.cli transcribe podcast.mp3 -m large-v3
```

#### Translation 选项

```bash
# 指定源语言和目标语言
python -m podtrans.cli translate asr_result.json -s en -t zh

# 指定输出目录
python -m podtrans.cli translate asr_result.json -o ./translations
```

#### TTS 选项

```bash
# 基础用法
python -m podtrans.cli synthesize translation_result.json

# 指定输出文件
python -m podtrans.cli synthesize translation_result.json -o chinese_podcast.wav

# 提供说话人语音样本 (改进声音质量)
python -m podtrans.cli synthesize translation_result.json \
  --speaker-audio SPEAKER_00=voices/male.wav \
  --speaker-audio SPEAKER_01=voices/female.wav

# 提供说话人描述
python -m podtrans.cli synthesize translation_result.json \
  --speaker-desc SPEAKER_00="中年男性,声音低沉有磁性" \
  --speaker-desc SPEAKER_01="年轻女性,声音清脆活泼"
```

---

## 📊 性能基准

基于实际测试 (macOS M4, CPU 模式):

### 处理速度

| 音频时长 | ASR | Translation | TTS | 总计 |
|---------|-----|-------------|-----|------|
| 30 秒 | ~13 秒 | ~5 秒 | N/A | ~18 秒 |
| 60 秒 | ~54 秒 (含说话人分离) | ~10 秒 | N/A | ~64 秒 |

**说明**:
- ASR 速度: 约 1:2 (30 秒音频需 13 秒处理)
- 含说话人分离: 约 1:1 (60 秒音频需 54 秒)
- GPU (CUDA): 预计快 3-5 倍

### 质量指标 (基于 demo_v1_baseline)

| 指标 | 测试结果 | 状态 |
|------|---------|------|
| 说话人检测数 | 2 个 | ✅ ≥ 2 |
| 段落完整性 | 100% | ✅ ≥ 98% |
| 说话人保留率 | 100% | ✅ = 100% |
| 翻译准确率 | ~98% | ✅ 高质量 |

---

## 🏗️ 项目架构

### 目录结构

```
podtrans/
├── src/podtrans/           # 源代码
│   ├── asr/                # ASR 模块 (WhisperX + pyannote)
│   │   ├── schemas.py      # 数据模型: ASRResult, Segment, Word
│   │   └── whisperx_handler.py
│   ├── translation/        # 翻译模块 (DashScope Qwen)
│   │   ├── schemas.py      # 数据模型: TranslationResult, TranslatedSegment
│   │   ├── translator.py   # 智能批处理翻译器
│   │   ├── KNOWN_ISSUES.md # 已知问题和解决方案
│   │   └── README.md       # 模块详细说明
│   ├── tts/                # TTS 模块 (SoulX-Podcast)
│   │   ├── schemas.py      # 数据模型: TTSResult, SpeakerConfig
│   │   ├── base.py         # TTSService 抽象基类
│   │   └── soulx/          # SoulX 客户端实现
│   ├── config.py           # 配置管理 (Pydantic Settings)
│   ├── models.py           # 通用数据模型
│   └── cli.py              # CLI 入口 (Typer)
├── scripts/                # 辅助脚本
│   ├── compare_with_baseline.py  # 对比质量指标
│   ├── update_baseline.py        # 更新基准版本
│   ├── convert_to_soulx.py       # SoulX 格式转换
│   └── README.md
├── data/
│   ├── input/              # 输入音频 (手动放置)
│   ├── output/             # 处理结果 (自动生成)
│   ├── baseline/           # 基准版本 (版本管理)
│   │   ├── demo_v1_baseline/
│   │   └── README.md
│   └── cache/              # 模型缓存
├── tests/                  # 测试文件
│   ├── unit/               # 单元测试
│   └── integration/        # 集成测试
├── SETUP_GUIDE.md          # 新电脑快速启动指南 ⭐
├── CLAUDE.md               # 开发指引 (最详细)
├── BASELINE_SYSTEM.md      # 基准系统文档
├── pyproject.toml          # 项目配置
└── .env.example            # 环境变量模板
```

### 核心依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| **whisperx** | 3.7.4 | 语音识别 + 对齐 |
| **torch** | 2.8.0 | 深度学习框架 |
| **pyannote.audio** | 3.3.2 | 说话人分离 |
| **pydantic** | 2.10+ | 数据验证 |
| **typer** | 0.15+ | CLI 框架 |
| **openai** | 1.58+ | API 客户端 (兼容 DashScope) |
| **tiktoken** | 0.8+ | Token 计数 |

---

## 🛠️ 开发

### 运行测试

```bash
# 所有测试
pytest

# 单元测试 (快速)
pytest tests/unit/

# 集成测试
pytest tests/integration/

# 跳过慢速测试
pytest -m "not slow"

# 生成覆盖率报告
pytest --cov=src/podtrans --cov-report=html
open htmlcov/index.html
```

### 代码质量检查

```bash
# Linting
ruff check .

# 自动修复
ruff check --fix .

# 格式化
ruff format .

# 类型检查
uv run mypy src/
```

### 基准版本管理

项目使用 baseline 系统持续跟踪优化效果:

```bash
# 对比当前输出与 baseline
uv run python scripts/compare_with_baseline.py

# 更新 baseline (会先显示对比结果并询问确认)
uv run python scripts/update_baseline.py
```

**详细文档**: 参见 [BASELINE_SYSTEM.md](docs/BASELINE_SYSTEM.md)

---

## ⚙️ 配置说明

### 环境变量

在 `.env` 文件中配置:

```bash
# ============= 必需配置 =============
# HuggingFace token (用于说话人分离)
HF_TOKEN=hf_your_token_here

# LLM API key (用于翻译，支持任意 OpenAI 兼容服务)
LLM_API_KEY=sk_your_key_here

# ============= ASR 配置 =============
# Whisper 模型大小 (tiny/base/small/medium/large-v2/large-v3)
WHISPER_MODEL=medium

# 设备 (cuda/cpu)
# 注意: macOS 使用 cpu (mps 不支持)
DEVICE=cpu

# 计算精度 (int8 for CPU, float16 for CUDA)
COMPUTE_TYPE=int8

# ============= LLM 配置 =============
# LLM 模型 (qwen-coder-plus/qwen-plus/qwen-turbo)
LLM_MODEL=qwen-coder-plus

# 每批最大 tokens (默认 120k,适配 128k 上下文模型)
LLM_MAX_TOKENS=120000

# 每批最大段落数 (默认 100,提高稳定性)
LLM_MAX_SEGMENTS_PER_BATCH=100

# ============= TTS 配置 (可选) =============
# SoulX-Podcast 服务地址
SOULX_API_URL=http://localhost:8000
```

### 设备兼容性

**macOS (Apple Silicon)**:
```bash
DEVICE=cpu
COMPUTE_TYPE=int8
# ❌ 不要使用 DEVICE=mps (WhisperX 不支持)
```

**NVIDIA GPU**:
```bash
DEVICE=cuda
COMPUTE_TYPE=float16
# 需要 CUDA 12.8+
```

**纯 CPU**:
```bash
DEVICE=cpu
COMPUTE_TYPE=int8
# 速度较慢但稳定
```

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [GETTING_STARTED.md](docs/GETTING_STARTED.md) | **🌟 完全上手指南** (手把手教程,新用户必读!) |
| [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) | 快速安装指南 (10 分钟上手) |
| [MODEL_DOWNLOAD_GUIDE.md](docs/MODEL_DOWNLOAD_GUIDE.md) | 模型下载完全指南 (解决下载问题) |
| [CLAUDE.md](CLAUDE.md) | 完整开发指引 (最详细) |
| [BASELINE_SYSTEM.md](docs/BASELINE_SYSTEM.md) | 基准版本管理系统 |
| [scripts/README.md](scripts/README.md) | 辅助脚本使用说明 |
| [src/podtrans/translation/README.md](src/podtrans/translation/README.md) | 翻译模块详细说明 |
| [src/podtrans/translation/KNOWN_ISSUES.md](src/podtrans/translation/KNOWN_ISSUES.md) | 已知问题和解决方案 |

---

## ⚠️ 重要注意事项

### 1. HuggingFace Token 授权

获取 token 后,**必须**访问以下页面并点击 "Agree and access repository":
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

否则说话人分离功能将无法使用。

### 2. macOS 用户

- ✅ 使用 `DEVICE=cpu` 和 `COMPUTE_TYPE=int8`
- ❌ **不要**使用 `DEVICE=mps` (会报错)
- 代码会自动检测并回退到 CPU

### 3. 翻译质量

- 翻译 API 偶尔会丢失少量段落 (丢失率 ~2-3%)
- 项目有自动重试机制,通常能恢复大部分
- 详见 [translation/KNOWN_ISSUES.md](src/podtrans/translation/KNOWN_ISSUES.md)

### 4. TTS 服务

- SoulX-Podcast 需要**外部部署**
- 默认地址: `http://localhost:8000`
- 如果没有 TTS 服务,可以只运行 ASR + Translation

---

## 🗺️ 开发路线图

### 已完成 ✅

- [x] **Milestone 1**: 项目骨架 + ASR 模块
  - WhisperX 3.7.4 集成
  - pyannote.audio 3.3.2 说话人分离
  - CLI 基础架构
  - 词级时间戳对齐

- [x] **Milestone 2**: 翻译模块
  - DashScope Qwen API 集成
  - 智能批处理 (基于 tiktoken 计数)
  - 自动重试机制
  - 质量评估系统

- [x] **Milestone 3**: TTS 模块
  - SoulX-Podcast HTTP 客户端
  - 格式转换器 (适配器模式)
  - 多说话人配置支持

### 进行中 🚧

- [ ] **Milestone 4**: 流程编排 + E2E 测试
  - 端到端流水线
  - 完整的集成测试
  - 性能基准测试

### 未来计划 💡

- [ ] RSS 订阅自动化
- [ ] Web UI (Gradio/Streamlit)
- [ ] 批量处理
- [ ] 多语言支持 (不仅限于英→中)
- [ ] 云部署方案
- [ ] Docker 容器化

---

## 🤝 贡献

欢迎贡献! 请遵循以下步骤:

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

**代码规范**:
- 使用 `ruff` 进行代码检查和格式化
- 使用 `mypy` 进行类型检查
- 编写单元测试
- 添加详细的中文注释

---

## 📝 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

---

## 🙏 致谢

本项目基于以下优秀的开源项目:

- [WhisperX](https://github.com/m-bain/whisperX) - 快速自动语音识别
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) - 说话人分离
- [DashScope](https://dashscope.aliyun.com/) - 阿里云 Qwen 大模型
- [SoulX-Podcast](https://github.com/Soul-AILab/SoulX-Podcast) - 中文播客 TTS

---

## 📧 联系与支持

- **Issues**: [GitHub Issues](../../issues)
- **Discussions**: [GitHub Discussions](../../discussions)

---

**项目状态**: 🚧 开发中 | **版本**: v0.1.0 | **最后更新**: 2025-11-28
