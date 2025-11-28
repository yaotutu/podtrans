# 🚀 PodTrans 新电脑快速启动指南

> **版本**: v0.1.0 | **平台**: macOS / Linux / Windows | **更新日期**: 2025-11-28

---

## 📋 前置准备清单

### 1. 系统要求

- **Conda**: 环境和包管理器 (必需)
- **Python**: 3.11+ (通过 conda 安装)
- **FFmpeg**: 用于音频处理 (可选但推荐)
- **CUDA**: 12.1+ (推荐, 用于 GPU 加速)
- **Git**: 版本控制 (必需)

### 2. API Keys 准备

| API Key | 用途 | 必需性 | 获取地址 |
|---------|------|--------|---------|
| **HF_TOKEN** | 说话人分离 (pyannote.audio) | **必需** | https://huggingface.co/settings/tokens |
| **DASHSCOPE_API_KEY** | 翻译 (Qwen 模型) | **必需** | https://dashscope.console.aliyun.com/ |
| **SOULX_API_URL** | TTS 语音合成 | 可选 | 需要外部部署 SoulX-Podcast 服务 |

---

## 🔧 安装步骤 (10 分钟)

### Step 1: 安装 Conda

#### 方法一: Miniconda (推荐)

**macOS / Linux**:
```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

**macOS (Apple Silicon)**:
```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
bash Miniconda3-latest-MacOSX-arm64.sh
```

**Windows**:
```bash
# 下载并运行 Miniconda3-latest-Windows-x86_64.exe
# 或者使用 PowerShell:
winget install Anaconda.Miniconda3
```

#### 验证安装:
```bash
conda --version
# 预期输出: conda 25.9.1 或更高版本
```

---

### Step 2: 克隆项目

```bash
# 使用 HTTPS (推荐)
git clone https://github.com/YOUR_USERNAME/podtrans.git
cd podtrans

# 或使用 SSH (如果配置了 SSH key)
git clone git@github.com:YOUR_USERNAME/podtrans.git
cd podtrans
```

---

### Step 3: 创建 Conda 环境

```bash
# 创建 conda 环境 (使用 environment.yml)
conda env create -f environment.yml

# 等待 2-5 分钟 (取决于网速)
# conda 会自动:
# 1. 创建 Python 3.11 环境
# 2. 安装 PyTorch 2.8.0 + CUDA 12.1
# 3. 安装所有必需依赖 (whisperx, pyannote.audio, 等)
# 4. 安装开发工具 (pytest, ruff, mypy, 等)

# 激活环境
conda activate podtrans
```

**预期输出示例**:
```
Preparing transaction: done
Verifying transaction: done
Executing transaction: done
Installing pip dependencies:
 - podtrans==0.1.0
 - torch==2.8.0
 - whisperx==3.7.4
 - pyannote-audio==3.3.2
 - ...
Successfully installed podtrans-0.1.0 torch-2.8.0+cu128 ...

To activate this environment, use
    $ conda activate podtrans
```

---

### Step 4: 配置环境变量

#### 4.1 复制模板文件
```bash
cp .env.example .env
```

#### 4.2 获取 HuggingFace Token

1. 访问 https://huggingface.co/settings/tokens
2. 点击 "New token" → 选择 "Read" 权限 → 创建
3. 复制生成的 token (格式: `hf_xxxxxxxxxxxx`)
4. **重要**: 访问以下模型页面并点击 "Agree and access repository":
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0

#### 4.3 获取 DashScope API Key

1. 访问 https://dashscope.console.aliyun.com/
2. 登录阿里云账号
3. 创建 API Key
4. 复制 API Key (格式: `sk-xxxxxxxxxxxx`)

#### 4.4 编辑 .env 文件

使用文本编辑器打开 `.env` 文件:

```bash
# macOS
open .env

# Linux
nano .env

# Windows
notepad .env
```

**填入你的 API keys**:
```bash
# ============= 必需配置 =============
HF_TOKEN=hf_your_actual_token_here
DASHSCOPE_API_KEY=sk_your_actual_key_here

# ============= 可选配置 =============
# 默认值已经优化,通常不需要修改
WHISPER_MODEL=medium
DEVICE=cpu
COMPUTE_TYPE=int8
TRANSLATION_MODEL=qwen-coder-plus
TRANSLATION_MAX_TOKENS=120000
```

**macOS 用户注意**:
- ✅ 使用 `DEVICE=cpu` 和 `COMPUTE_TYPE=int8`
- ❌ **不要**使用 `DEVICE=mps` (WhisperX 不支持,会报错)

**NVIDIA GPU 用户**:
- ✅ 使用 `DEVICE=cuda` 和 `COMPUTE_TYPE=float16`
- 需要 CUDA 12.8+

---

### Step 5: 验证安装

```bash
# 测试 Python 环境
conda activate podtrans && python --version
# 预期输出: Python 3.12.x

# 测试包导入
conda activate podtrans && python -c "from podtrans.asr import WhisperXHandler; print('✅ ASR 模块正常')"
conda activate podtrans && python -c "from podtrans.translation import Translator; print('✅ Translation 模块正常')"
conda activate podtrans && python -c "from podtrans.tts import SoulXClient; print('✅ TTS 模块正常')"

# 测试配置加载
conda activate podtrans && python -c "from podtrans.config import get_settings; s=get_settings(); print(f'✅ HF_TOKEN: {s.hf_token[:8]}...' if s.hf_token else '❌ 缺少 HF_TOKEN')"
```

**预期输出**:
```
✅ ASR 模块正常
✅ Translation 模块正常
✅ TTS 模块正常
✅ HF_TOKEN: hf_xxxxxx...
```

---

### Step 6: 预下载模型 (可选但推荐)

首次运行会自动下载约 1.9 GB 的模型,建议提前下载以避免使用时等待。

**详细模型下载指南**: 参见 [MODEL_DOWNLOAD_GUIDE.md](MODEL_DOWNLOAD_GUIDE.md)

**快速预下载**:

```bash
# 方法 1: 使用预下载脚本 (只下载 Whisper 模型)
conda activate podtrans && python scripts/preload_models.py

# 方法 2: 运行一次完整流程 (下载所有模型,推荐)
# 准备一个 30-60 秒的测试音频文件
conda activate podtrans && podtrans transcribe data/input/test.mp3
```

**检查模型下载状态**:

```bash
# 检查所有模型是否已下载
conda activate podtrans && python scripts/check_models.py
```

**预期输出**:
```
🔍 PodTrans 模型下载检查

============================================================

📦 Whisper 模型:
  medium       ✅ 1.4 GB

📦 wav2vec2 对齐模型:
  wav2vec2:    ✅ 已下载 (360 MB)

📦 说话人分离模型:
  speechbrain              ✅ 85 MB
  pyannote-diarization     ✅ 50 MB
  pyannote-segmentation    ✅ 20 MB
  silero-vad               ✅ 31 MB

============================================================
📊 HuggingFace 缓存总计: ✅ 1.5 GB
📊 PyTorch 缓存总计:     ✅ 422 MB
============================================================
```

---

## 🎯 快速测试 (验证一切正常)

### 准备测试音频

```bash
# 方法1: 使用项目自带的测试音频 (如果有)
ls data/input/
# 如果有 demo.mp3 或其他音频文件,跳到下一步

# 方法2: 下载一段测试音频 (30-60 秒即可)
# 例如从 YouTube 下载播客片段:
# brew install yt-dlp  # macOS
# yt-dlp -x --audio-format mp3 -o "data/input/test.mp3" "https://youtube.com/watch?v=xxxxx"

# 方法3: 自己录制一段英文语音
# 放到 data/input/test.mp3
```

### 测试 ASR (语音识别 + 说话人分离)

```bash
# 运行 ASR 模块 (预计耗时: 30 秒音频 ~10-15 秒)
conda activate podtrans && podtrans transcribe data/input/test.mp3

# 成功后会看到:
# ✅ ASR completed successfully!
# 📄 Results saved to: data/output/test/asr_result.json
```

**检查输出**:
```bash
cat data/output/test/asr_result.json | head -30

# 应该看到:
# {
#   "segments": [
#     {
#       "start": 0.0,
#       "end": 2.5,
#       "text": "Hello, welcome to our podcast.",
#       "speaker": "SPEAKER_00",
#       "words": [...]
#     }
#   ],
#   "language": "en",
#   "audio_duration": 30.5,
#   "model_name": "medium"
# }
```

### 测试 Translation (翻译)

```bash
# 运行翻译模块 (预计耗时: ~5-10 秒)
conda activate podtrans && podtrans translate data/output/test/asr_result.json

# 成功后会看到:
# ✅ Translation completed successfully!
# 📄 Results saved to: data/output/test/translation_result.json
```

**检查输出**:
```bash
cat data/output/test/translation_result.json | head -30

# 应该看到:
# {
#   "segments": [
#     {
#       "start": 0.0,
#       "end": 2.5,
#       "original_text": "Hello, welcome to our podcast.",
#       "translated_text": "你好,欢迎收听我们的播客。",
#       "speaker": "SPEAKER_00"
#     }
#   ],
#   "source_language": "en",
#   "target_language": "zh",
#   "model_name": "qwen-coder-plus"
# }
```

---

## ✅ 安装成功标志

如果以上步骤全部通过,说明安装成功! 你现在可以:

- ✅ 运行 ASR 语音识别 + 说话人分离
- ✅ 运行智能批处理翻译
- ✅ 使用完整的 CLI 工具
- ✅ 开始开发和测试

---

## 📚 下一步

### 常用命令速查

```bash
# 1. ASR - 语音识别 + 说话人分离
conda activate podtrans && podtrans transcribe data/input/demo.mp3

# ASR 选项:
conda activate podtrans && podtrans transcribe demo.mp3 -o ./my_output      # 指定输出目录
conda activate podtrans && podtrans transcribe demo.mp3 -l en              # 指定语言
conda activate podtrans && podtrans transcribe demo.mp3 --no-diarization   # 禁用说话人分离
conda activate podtrans && podtrans transcribe demo.mp3 -m large-v3        # 指定 Whisper 模型

# 2. Translation - 翻译
conda activate podtrans && podtrans translate data/output/demo/asr_result.json

# Translation 选项:
conda activate podtrans && podtrans translate asr_result.json -s en -t zh  # 指定源/目标语言
conda activate podtrans && podtrans translate asr_result.json -o ./trans   # 指定输出目录

# 3. TTS - 音频生成 (需要外部 SoulX 服务)
conda activate podtrans && podtrans synthesize data/output/demo/translation_result.json

# TTS 选项:
conda activate podtrans && podtrans synthesize trans.json -o output.wav    # 指定输出文件
conda activate podtrans && podtrans synthesize trans.json \
  --speaker-audio SPEAKER_00=voices/male.wav \
  --speaker-audio SPEAKER_01=voices/female.wav         # 提供语音样本
```

### 辅助脚本

```bash
# 对比当前输出与 baseline
conda activate podtrans && python scripts/compare_with_baseline.py

# 更新 baseline (会先显示对比结果)
conda activate podtrans && python scripts/update_baseline.py

# 转换为 SoulX 格式
conda activate podtrans && python scripts/convert_to_soulx.py
```

### 开发和测试

```bash
# 运行所有测试
conda activate podtrans && pytest

# 运行特定测试
conda activate podtrans && pytest tests/unit/          # 单元测试
conda activate podtrans && pytest tests/integration/   # 集成测试
conda activate podtrans && pytest -m "not slow"        # 跳过慢速测试

# 代码检查
conda activate podtrans && ruff check .                # Linting
conda activate podtrans && ruff format .               # 格式化
conda activate podtrans && mypy src/                   # 类型检查
```

---

## ⚠️ 常见问题

### 1. ASR 在 Mac 上很慢

**问题**: 处理 30 秒音频花了 5 分钟

**解决**:
```bash
# 检查 .env 配置
cat .env | grep DEVICE
cat .env | grep COMPUTE_TYPE

# 确保是:
DEVICE=cpu
COMPUTE_TYPE=int8

# 不要使用 mps (不支持)
```

### 2. 说话人分离不工作

**问题**: 所有段落的 speaker 字段都是 null

**解决**:
1. 检查是否设置了 `HF_TOKEN`
2. 检查是否接受了 pyannote 模型授权:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0

### 3. 翻译丢失部分段落

**问题**: 翻译结果少了几个段落

**解决**:
- 这是已知问题,丢失率 ~2-3%
- 详见 `src/podtrans/translation/KNOWN_ISSUES.md`
- 项目会自动重试,通常能恢复大部分丢失

### 4. TTS 报错连接失败

**问题**: `ConnectionError: Cannot connect to SoulX API`

**解决**:
- SoulX-Podcast 需要外部部署
- 默认地址: `http://localhost:8000`
- 如果没有 TTS 服务,跳过这一步即可

### 5. uv sync 下载很慢

**问题**: 卡在 "Downloading packages..."

**解决**:
```bash
# 使用国内镜像 (可选)
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
uv sync

# 或者使用代理
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
uv sync
```

---

## 📖 完整文档

- **CLAUDE.md** - 项目开发指引 (最详细)
- **README.md** - 项目简介
- **BASELINE_SYSTEM.md** - 基准版本管理
- **scripts/README.md** - 辅助脚本说明

---

## 🆘 获取帮助

如果遇到问题:

1. 查看 `CLAUDE.md` 中的"常见问题"章节
2. 检查 `src/podtrans/translation/KNOWN_ISSUES.md`
3. 提交 GitHub Issue

---

**祝你使用愉快! 🎉**

**版本**: v0.1.0 | **最后更新**: 2025-11-28
