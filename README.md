# PodTrans 🎙️

> AI-powered podcast translation pipeline: English podcast → Chinese podcast with speaker diarization

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## 📋 项目简介

PodTrans 是一个全自动的播客翻译工具，可以将英文播客翻译成自然流畅的中文播客，并保留原有的说话人信息和语音风格。

### 核心功能

- **🎯 自动语音识别（ASR）**：使用 WhisperX 进行高精度转录
- **👥 说话人分离（Diarization）**：基于 pyannote.audio，准确识别不同说话人
- **🌐 智能翻译**：使用 Claude 进行播客风格的口语化翻译
- **🔊 中文 TTS**：基于 SoulX-Podcast，生成自然的中文播客音频
- **📊 完整流程**：一键完成从英文音频到中文音频的全流程转换

## 🏗️ 技术架构

```
English Podcast (MP3)
         ↓
    [WhisperX + pyannote.audio]
         ↓
Speaker-labeled Transcript (JSON)
         ↓
    [Claude API Translation]
         ↓
Chinese Podcast Script (JSON)
         ↓
    [SoulX-Podcast TTS]
         ↓
Chinese Podcast (MP3)
```

## 🚀 快速开始

### 前置要求

- Python 3.12+
- FFmpeg（用于音频处理）
- CUDA 12.8+（可选，用于 GPU 加速）
- HuggingFace Token（用于说话人分离）
- Anthropic API Key（用于翻译）

### 安装

```bash
# 1. 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目
git clone <your-repo-url>
cd podtrans

# 3. 安装依赖
uv sync

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API keys
```

### 基本使用

```bash
# 完整流程（一键翻译）
uv run podtrans run --audio data/input/podcast.mp3

# 分步执行
# 1. ASR（语音识别 + 说话人分离）
uv run podtrans transcribe --audio data/input/podcast.mp3

# 2. 翻译
uv run podtrans translate --input data/output/podcast/asr_result.json

# 3. TTS（文本转语音）
uv run podtrans synthesize --input data/output/podcast/translation_result.json
```

## 📁 项目结构

```
podtrans/
├── src/podtrans/          # 源代码
│   ├── asr/              # ASR 模块（WhisperX）
│   ├── translation/      # 翻译模块（Claude）
│   ├── tts/              # TTS 模块（SoulX-Podcast）
│   ├── pipeline/         # 流程编排
│   └── utils/            # 工具函数
├── tests/                # 测试
├── docs/                 # 文档
└── data/                 # 数据目录
    ├── input/           # 输入音频
    ├── output/          # 输出结果
    └── cache/           # 缓存
```

## 🛠️ 开发

### 运行测试

```bash
# 所有测试
uv run pytest

# 单元测试
uv run pytest tests/unit/

# 覆盖率报告
uv run pytest --cov=src/podtrans --cov-report=html
```

### 代码检查

```bash
# Linting
uv run ruff check .

# Formatting
uv run ruff format .

# Type checking
uv run mypy src/
```

### 基准版本管理

项目使用 baseline 版本系统来跟踪和评估优化效果：

```bash
# 对比当前输出与 baseline
uv run python scripts/compare_with_baseline.py

# 更新 baseline（会先显示对比结果）
uv run python scripts/update_baseline.py

# 手动转换为 SoulX 格式
uv run python scripts/convert_to_soulx.py
```

Baseline 版本存储在 `data/baseline/demo_v1_baseline/`，包含：
- ASR 转录结果
- 翻译结果（JSON + 文本）
- SoulX TTS 脚本

详见 `data/baseline/README.md`

## 📊 性能基准

**60 分钟英文播客处理时间（参考）：**

| 阶段 | GPU (NVIDIA) | CPU | 成本 |
|------|-------------|-----|------|
| ASR | 5-10 分钟 | 30-60 分钟 | $0 |
| 翻译 | 2-5 分钟 | 2-5 分钟 | $0.10-0.40 |
| TTS | 10-20 分钟 | 60-120 分钟 | $0 |
| **总计** | **~20-35 分钟** | **~90-180 分钟** | **~$0.15-0.50** |

## 🗺️ 开发路线图

- [x] Milestone 1: 项目骨架 + ASR 模块
- [ ] Milestone 2: 翻译模块
- [ ] Milestone 3: TTS 模块
- [ ] Milestone 4: 流程编排 + 完整测试
- [ ] 未来计划：
  - [ ] RSS 订阅自动化
  - [ ] Web UI
  - [ ] 批量处理
  - [ ] 多语言支持

## 📝 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 📧 联系

如有问题或建议，请提交 [Issue](../../issues)。

## 🙏 致谢

本项目基于以下优秀的开源项目：

- [WhisperX](https://github.com/m-bain/whisperX) - 快速自动语音识别
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) - 说话人分离
- [Claude](https://www.anthropic.com/claude) - 高质量翻译
- [SoulX-Podcast](https://github.com/Soul-AILab/SoulX-Podcast) - 中文播客 TTS

---

**状态**：🚧 开发中 | **版本**：0.1.0 | **最后更新**：2025-11-26



# 重要提示
** 所有代码必须要有详细的注释说明 **
