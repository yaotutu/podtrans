# 🚀 PodTrans 完全上手指南

> **手把手教你从零开始运行 PodTrans**
> 特别关注模型下载等容易出问题的环节

**适用对象**: 完全没用过的新用户
**预计耗时**: 20-30 分钟 (含模型下载)
**最后更新**: 2025-11-28

---

## 📋 开始之前

### 你需要准备

| 项目 | 说明 | 是否必需 |
|------|------|---------|
| **电脑** | macOS / Linux / Windows | ✅ 必需 |
| **网络** | 稳定网络连接 (需下载 ~2 GB 模型) | ✅ 必需 |
| **磁盘空间** | 至少 5 GB 可用空间 | ✅ 必需 |
| **Python** | 3.12 或更高版本 | ✅ 必需 |
| **HuggingFace 账号** | 免费注册 | ✅ 必需 |
| **阿里云账号** | 用于翻译 API | ✅ 必需 |

### 预计成本

- ✅ **PodTrans 软件**: 免费开源
- ✅ **模型下载**: 免费
- ✅ **HuggingFace Token**: 免费
- 💰 **翻译 API**: 按使用量付费 (~¥0.1-0.5 / 60分钟播客)
- 💰 **TTS 服务**: 需自行部署 (可选)

---

## 📍 Step 1: 安装 Python 3.12+

### 检查是否已安装

打开终端 (Terminal),输入:

```bash
python3 --version
```

**如果显示 `Python 3.12.x` 或更高版本**:
```
✅ 太棒了!跳到 Step 2
```

**如果显示版本低于 3.12 或报错**:

#### macOS 安装 Python

```bash
# 使用 Homebrew 安装
brew install python@3.12

# 验证安装
python3 --version
# 应该显示: Python 3.12.x
```

#### Linux (Ubuntu/Debian) 安装 Python

```bash
# 添加 deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# 安装 Python 3.12
sudo apt install python3.12 python3.12-venv python3.12-dev

# 验证安装
python3.12 --version
```

#### Windows 安装 Python

1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.12.x 安装包
3. 运行安装程序,**勾选 "Add Python to PATH"**
4. 完成安装后,打开 PowerShell 验证:

```powershell
python --version
# 应该显示: Python 3.12.x
```

---

## 📍 Step 2: 安装 uv 包管理器

**uv** 是一个超快的 Python 包管理器,比 pip 快 10-100 倍。

### macOS / Linux 安装

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**执行后会看到**:
```
Downloading uv...
Installing uv...
✓ Successfully installed uv
```

### Windows 安装

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 验证安装

```bash
uv --version
```

**应该显示**:
```
uv 0.5.x (或更高版本)
```

**如果报错 "command not found"**:

```bash
# 关闭终端,重新打开
# 或手动添加到 PATH (macOS/Linux):
export PATH="$HOME/.local/bin:$PATH"

# 重新验证
uv --version
```

---

## 📍 Step 3: 克隆项目

### 方法 1: 使用 HTTPS (推荐)

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/podtrans.git

# 进入项目目录
cd podtrans

# 确认在正确目录
pwd
# 应该显示: /path/to/podtrans
```

### 方法 2: 使用 SSH (如果配置了 SSH key)

```bash
git clone git@github.com:YOUR_USERNAME/podtrans.git
cd podtrans
```

### 验证克隆成功

```bash
ls -la
```

**应该看到**:
```
drwxr-xr-x   README.md
drwxr-xr-x   CLAUDE.md
drwxr-xr-x   src/
drwxr-xr-x   data/
drwxr-xr-x   docs/
...
```

---

## 📍 Step 4: 安装项目依赖

这一步会自动创建虚拟环境并安装所有 Python 包。

```bash
# 在 podtrans 目录下运行
uv sync
```

**执行过程**:
```
Using Python 3.12.x interpreter at: /usr/bin/python3
Creating virtualenv at: .venv
Resolved 95 packages in 1.23s
Downloading packages... ━━━━━━━━━━━━━━━━━━━━ 100%
Installing packages... ━━━━━━━━━━━━━━━━━━━━ 100%
Installed 95 packages in 45.67s
 + podtrans==0.1.0 (from file:///path/to/podtrans)
 + torch==2.8.0
 + whisperx==3.7.4
 + pyannote-audio==3.3.2
 + pydantic==2.10.0
 + typer==0.15.0
 ... (更多包)
```

**预计耗时**: 30 秒 - 2 分钟 (取决于网速)

**如果遇到问题**:

#### 问题 1: 下载速度很慢

```bash
# 使用国内镜像 (中国用户)
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
uv sync
```

#### 问题 2: 权限错误

```bash
# 确保有写权限
chmod -R 755 .
uv sync
```

### 验证安装成功

```bash
# 测试 Python 环境
uv run python --version
# 应该显示: Python 3.12.x

# 测试包导入
uv run python -c "from podtrans.asr import WhisperXHandler; print('✅ ASR 模块正常')"
uv run python -c "from podtrans.translation import Translator; print('✅ Translation 模块正常')"
uv run python -c "from podtrans.tts import SoulXClient; print('✅ TTS 模块正常')"
```

**应该看到**:
```
✅ ASR 模块正常
✅ Translation 模块正常
✅ TTS 模块正常
```

---

## 📍 Step 5: 获取 API Keys (重要!)

PodTrans 需要两个 API keys 才能正常工作。

### 5.1 获取 HuggingFace Token

**用途**: 下载说话人分离模型

#### 步骤 1: 注册 HuggingFace 账号

1. 访问 https://huggingface.co/join
2. 填写邮箱、用户名、密码
3. 验证邮箱
4. 登录成功

#### 步骤 2: 创建 Access Token

1. 访问 https://huggingface.co/settings/tokens
2. 点击 **"New token"** 按钮
3. 填写信息:
   - **Name**: `podtrans` (随便起名)
   - **Type**: 选择 **"Read"** (只读权限即可)
4. 点击 **"Generate token"**
5. **复制生成的 token** (格式: `hf_xxxxxxxxxxxx`)

   ⚠️ **重要**: Token 只显示一次,请立即复制保存!

#### 步骤 3: 接受模型使用协议 (非常重要!)

**必须完成这一步,否则会报 401 错误!**

访问以下两个页面,点击 **"Agree and access repository"**:

1. https://huggingface.co/pyannote/speaker-diarization-3.1
   - 点击页面顶部的 **"Agree and access repository"** 按钮
   - 阅读协议并勾选 **"I agree"**
   - 点击 **"Access repository"**

2. https://huggingface.co/pyannote/segmentation-3.0
   - 重复上述步骤

**完成后你会看到**:
```
✅ You have been granted access to this model
```

---

### 5.2 获取 DashScope API Key

**用途**: 调用 Qwen 大模型进行翻译

#### 步骤 1: 注册阿里云账号

1. 访问 https://www.aliyun.com/
2. 点击 **"免费注册"**
3. 填写手机号、验证码
4. 完成实名认证 (需要身份证)

#### 步骤 2: 开通 DashScope 服务

1. 访问 https://dashscope.console.aliyun.com/
2. 首次访问会提示开通服务,点击 **"立即开通"**
3. 阅读协议并同意
4. 开通成功

#### 步骤 3: 创建 API Key

1. 在 DashScope 控制台,点击 **"API Key 管理"**
2. 点击 **"创建新的 API Key"**
3. **复制生成的 API Key** (格式: `sk-xxxxxxxxxxxx`)

   ⚠️ **重要**: 请妥善保管,不要泄露!

#### 步骤 4: 充值 (可选)

- DashScope 提供免费额度
- 如果需要处理大量播客,可以充值 (推荐充值 ¥10-20 即可)

---

### 5.3 配置环境变量

#### 创建 .env 文件

```bash
# 在 podtrans 目录下
cp .env.example .env
```

#### 编辑 .env 文件

```bash
# macOS / Linux
nano .env

# 或使用你喜欢的编辑器
open .env      # macOS
vim .env       # Linux
notepad .env   # Windows
```

#### 填入你的 API keys

在 .env 文件中找到以下行,替换为你的真实 API keys:

```bash
# ============= 必需配置 =============
# 替换为你在 HuggingFace 创建的 token
HF_TOKEN=hf_your_actual_token_here

# 替换为你在 DashScope 创建的 API key
DASHSCOPE_API_KEY=sk_your_actual_key_here

# ============= 可选配置 (通常不需要修改) =============
# Whisper 模型大小 (medium 是推荐的平衡选择)
WHISPER_MODEL=medium

# 设备 (macOS 用户必须使用 cpu)
DEVICE=cpu

# 计算精度 (CPU 使用 int8)
COMPUTE_TYPE=int8

# 翻译模型
TRANSLATION_MODEL=qwen-coder-plus
```

**保存文件** (nano 编辑器按 `Ctrl + X`,然后按 `Y`,再按 `Enter`)

#### 验证配置

```bash
uv run python -c "
from podtrans.config import get_settings
s = get_settings()
print(f'✅ HF_TOKEN: {s.hf_token[:8]}...' if s.hf_token else '❌ 缺少 HF_TOKEN')
print(f'✅ DASHSCOPE_API_KEY: {s.dashscope_api_key[:8]}...' if s.dashscope_api_key else '❌ 缺少 DASHSCOPE_API_KEY')
"
```

**应该看到**:
```
✅ HF_TOKEN: hf_xxxxxx...
✅ DASHSCOPE_API_KEY: sk-xxxxxx...
```

**如果看到 ❌**:
- 检查 .env 文件中的 API keys 是否正确粘贴
- 确保 .env 文件在项目根目录下
- 确保没有多余的空格或引号

---

## 📍 Step 6: 下载模型 (重点!)

这是最容易出问题的环节,请仔细跟随步骤。

### 6.1 了解需要下载的模型

PodTrans 需要下载以下模型 (全部自动下载):

| 模型 | 大小 | 用途 | 下载时机 |
|------|------|------|---------|
| Whisper (medium) | 1.4 GB | 语音识别 | 首次运行 transcribe |
| wav2vec2 | 360 MB | 词级对齐 | 首次运行 transcribe |
| pyannote/speechbrain | 85 MB | 说话人分离 | 首次运行 transcribe (需要 HF_TOKEN) |
| silero-vad | 31 MB | 语音活动检测 | 首次运行 transcribe |

**总计**: 约 **1.9 GB**

**下载位置**:
- `~/.cache/huggingface/hub/` (HuggingFace 模型)
- `~/.cache/torch/hub/` (PyTorch 模型)

---

### 6.2 方法 1: 自动下载 (推荐)

**准备一个测试音频文件**:

```bash
# 方法 A: 使用项目自带的测试音频 (如果有)
ls data/input/

# 方法 B: 下载一个短音频 (30-60 秒即可)
# 例如从 YouTube 下载 (需要先安装 yt-dlp):
# brew install yt-dlp  # macOS
# yt-dlp -x --audio-format mp3 -o "data/input/test.mp3" "https://youtube.com/watch?v=xxxxx"

# 方法 C: 自己录制一段英文语音
# 放到 data/input/test.mp3
```

**运行一次完整流程 (会自动下载所有模型)**:

```bash
uv run podtrans transcribe data/input/test.mp3
```

**首次运行会看到**:

```
🎙️ Starting ASR transcription...
📥 Downloading faster-whisper-medium...
Downloading: 100%|██████████| 1.4G/1.4G [05:30<00:00, 4.2MB/s]
✅ Model loaded successfully

📥 Downloading wav2vec2 alignment model...
Downloading: 100%|██████████| 360M/360M [01:20<00:00, 4.5MB/s]
✅ Alignment model loaded

📥 Downloading speaker diarization models...
Downloading pyannote/speaker-diarization-3.1...
Downloading speechbrain/spkrec-ecapa-voxceleb...
✅ Diarization models loaded

🎯 Transcribing audio...
[████████████████████████████] 100%
✅ ASR completed successfully!

📄 Results saved to: data/output/test/asr_result.json
```

**预计耗时**: 5-15 分钟 (取决于网速)

**后续运行**:
- 模型已缓存,只需 1-2 分钟即可完成

---

### 6.3 方法 2: 预下载模型 (可选)

如果你想在不处理音频的情况下先下载模型:

```bash
# 预下载 Whisper 模型
uv run python scripts/preload_models.py
```

**会看到**:
```
🎯 开始预下载 ASR 模型...
📦 Whisper 模型: medium
💾 设备: cpu
🔧 计算类型: int8

1️⃣ 下载 Whisper 模型...
Downloading: 100%|██████████| 1.4G/1.4G [05:30<00:00, 4.2MB/s]
✅ Whisper 模型下载完成!

2️⃣ wav2vec2 对齐模型会在首次运行 align() 时自动下载
3️⃣ 说话人分离模型会在首次运行 diarize() 时自动下载 (需要 HF_TOKEN)

🎉 主要模型预下载完成!
💡 提示: 运行一次 `podtrans transcribe` 命令会自动下载所有剩余模型
```

---

### 6.4 检查模型下载状态

```bash
uv run python scripts/check_models.py
```

**完整下载后会看到**:
```
🔍 PodTrans 模型下载检查

============================================================

📦 Whisper 模型:
  tiny         ❌ 未找到
  base         ❌ 未找到
  small        ❌ 未找到
  medium       ✅ 1.4 GB
  large-v2     ❌ 未找到
  large-v3     ❌ 未找到

📦 wav2vec2 对齐模型:
  wav2vec2:    ✅ 已下载 (360 MB)

📦 说话人分离模型:
  speechbrain              ✅ 85.0 MB
  pyannote-diarization     ✅ 50.0 MB
  pyannote-segmentation    ✅ 20.0 MB
  silero-vad               ✅ 31.0 MB

============================================================
📊 HuggingFace 缓存总计: ✅ 1.5 GB
📊 PyTorch 缓存总计:     ✅ 422.0 MB
============================================================
```

---

### 6.5 常见模型下载问题和解决方案

#### 问题 1: 下载速度非常慢 (< 100 KB/s)

**原因**: HuggingFace 服务器在国外

**解决方案**: 使用国内镜像

```bash
# 临时使用镜像
export HF_ENDPOINT=https://hf-mirror.com
uv run podtrans transcribe data/input/test.mp3

# 永久设置 (添加到 ~/.bashrc 或 ~/.zshrc)
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.zshrc
source ~/.zshrc
```

**重新运行后速度应该提升到 1-5 MB/s**

---

#### 问题 2: 401 Unauthorized 错误

**完整错误信息**:
```
HTTPError: 401 Client Error: Unauthorized for url:
https://huggingface.co/pyannote/speaker-diarization-3.1/resolve/main/...
```

**原因**:
1. 未设置 HF_TOKEN
2. 未接受模型使用协议

**解决步骤**:

**步骤 1**: 检查 HF_TOKEN 是否设置

```bash
uv run python -c "
from podtrans.config import get_settings
s = get_settings()
print(f'HF_TOKEN: {s.hf_token[:8] if s.hf_token else \"未设置\"}')
"
```

如果显示 "未设置",回到 **Step 5.1** 重新配置。

**步骤 2**: 确认已接受模型协议

访问以下页面,确保显示 **"You have been granted access to this model"**:

1. https://huggingface.co/pyannote/speaker-diarization-3.1
2. https://huggingface.co/pyannote/segmentation-3.0

如果看到 **"You need to agree to share your contact information to access this model"**,点击 **"Agree and access repository"**。

**步骤 3**: 测试 HF_TOKEN 是否有效

```bash
uv run python -c "
from huggingface_hub import HfApi
api = HfApi()
try:
    user = api.whoami()
    print(f'✅ Token 有效! 用户: {user[\"name\"]}')
except Exception as e:
    print(f'❌ Token 无效: {e}')
"
```

**步骤 4**: 重新运行

```bash
uv run podtrans transcribe data/input/test.mp3
```

---

#### 问题 3: 磁盘空间不足

**错误信息**:
```
OSError: [Errno 28] No space left on device
```

**检查可用空间**:

```bash
# 检查整体空间
df -h

# 检查缓存目录
df -h ~/.cache
```

**解决方案 A**: 清理不用的模型

```bash
# 查看模型占用空间
du -sh ~/.cache/huggingface/hub/models--*
du -sh ~/.cache/torch/hub/*

# 删除不用的模型 (例如 large-v2 如果你用的是 medium)
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-large-v2
```

**解决方案 B**: 使用更小的模型

```bash
# 编辑 .env 文件
nano .env

# 修改为:
WHISPER_MODEL=base  # 只需 150 MB (精度略低)

# 保存后重新运行
uv run podtrans transcribe data/input/test.mp3
```

**解决方案 C**: 移动缓存到其他磁盘

```bash
# 移动缓存到外部磁盘
mv ~/.cache/huggingface /Volumes/ExternalDrive/huggingface_cache

# 创建软链接
ln -s /Volumes/ExternalDrive/huggingface_cache ~/.cache/huggingface
```

---

#### 问题 4: 下载中断或模型损坏

**错误信息**:
```
RuntimeError: Error loading model weights
OSError: Unable to load weights from checkpoint
```

**解决方案**: 删除损坏的缓存,重新下载

```bash
# 删除所有 HuggingFace 缓存
rm -rf ~/.cache/huggingface/hub/

# 重新下载
uv run podtrans transcribe data/input/test.mp3
```

---

#### 问题 5: 网络连接超时

**错误信息**:
```
requests.exceptions.ReadTimeout: HTTPSConnectionPool
requests.exceptions.ConnectionError
```

**解决方案**:

```bash
# 方法 1: 增加超时时间
export HF_HUB_DOWNLOAD_TIMEOUT=600

# 方法 2: 使用镜像
export HF_ENDPOINT=https://hf-mirror.com

# 方法 3: 使用代理 (如果有)
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# 重新运行
uv run podtrans transcribe data/input/test.mp3
```

---

## 📍 Step 7: 运行完整流程

模型下载完成后,就可以正常使用了!

### 7.1 准备输入音频

```bash
# 将你的英文播客音频放到 data/input/ 目录
cp /path/to/your/podcast.mp3 data/input/

# 查看文件
ls -lh data/input/
```

**推荐的测试音频**:
- 时长: 30-60 秒 (首次测试)
- 格式: MP3, WAV, M4A 等常见格式
- 内容: 清晰的英文对话,最好有 2 个说话人

---

### 7.2 步骤 1: 语音识别 + 说话人分离

```bash
uv run podtrans transcribe data/input/podcast.mp3
```

**输出**:
```
🎙️ Starting ASR transcription...
📂 Input: data/input/podcast.mp3
📂 Output: data/output/podcast/

🎯 Loading Whisper model 'medium'...
✅ Model loaded in 2.3s

🎯 Transcribing audio...
[████████████████████████████] 100%
✅ Transcription completed in 13.2s

🎯 Aligning words...
✅ Alignment completed in 5.4s

🎯 Diarizing speakers...
✅ Detected 2 speakers:
   SPEAKER_00: 9 segments (75%)
   SPEAKER_01: 3 segments (25%)
✅ Diarization completed in 35.6s

📊 Results:
   Total segments: 12
   Total speakers: 2
   Audio duration: 60.0s
   Processing time: 56.5s

📄 Results saved to: data/output/podcast/asr_result.json

✅ ASR completed successfully!
```

**查看结果**:

```bash
# 查看 ASR 结果 (前 30 行)
head -30 data/output/podcast/asr_result.json
```

**JSON 格式示例**:
```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, welcome to our podcast.",
      "speaker": "SPEAKER_00",
      "words": [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "welcome", "start": 0.6, "end": 1.0}
      ]
    }
  ],
  "language": "en",
  "audio_duration": 60.0,
  "model_name": "medium"
}
```

---

### 7.3 步骤 2: 翻译

```bash
uv run podtrans translate data/output/podcast/asr_result.json
```

**输出**:
```
🌐 Starting translation...
📂 Input: data/output/podcast/asr_result.json
📂 Output: data/output/podcast/

📊 Translation config:
   Source language: en
   Target language: zh
   Model: qwen-coder-plus
   Max tokens per batch: 120000
   Max segments per batch: 100

🎯 Creating smart batches...
✅ Created 1 batch(es):
   Batch 1: 12 segments, ~3500 tokens

🎯 Translating batch 1/1...
[████████████████████████████] 100%
✅ Batch 1 translated successfully (12/12 segments)

📊 Translation results:
   Input segments: 12
   Output segments: 12
   Loss rate: 0.0%
   Processing time: 8.3s
   Speed: 1.45 seg/s

📄 Results saved to:
   - data/output/podcast/translation_result.json
   - data/output/podcast/translation_result.txt

✅ Translation completed successfully!
```

**查看翻译结果**:

```bash
# 查看纯文本结果
cat data/output/podcast/translation_result.txt
```

**输出示例**:
```
SPEAKER_00: 你好,欢迎收听我们的播客。
SPEAKER_01: 嗨,很高兴见到你。
SPEAKER_00: 今天我们要讨论一个非常有趣的话题...
```

---

### 7.4 步骤 3: TTS 语音合成 (可选)

**注意**: TTS 需要外部部署 SoulX-Podcast 服务

如果你已经部署了 SoulX 服务:

```bash
uv run podtrans synthesize data/output/podcast/translation_result.json
```

如果没有 TTS 服务,可以跳过这一步,直接使用翻译文本结果。

---

## 📍 Step 8: 验证结果质量

### 8.1 检查 ASR 质量

```bash
# 查看 ASR 结果
cat data/output/podcast/asr_result.json | head -50

# 关键指标:
# ✅ 检测到的说话人数量 (至少 2 个)
# ✅ 文本识别准确度
# ✅ 时间戳对齐精度
```

### 8.2 检查翻译质量

```bash
# 查看翻译文本
cat data/output/podcast/translation_result.txt

# 关键指标:
# ✅ 翻译是否流畅自然
# ✅ 段落是否完整 (丢失率 < 2%)
# ✅ 说话人标签是否保留
```

### 8.3 与 baseline 对比 (可选)

```bash
# 对比当前结果与 baseline
uv run python scripts/compare_with_baseline.py
```

**输出示例**:
```
📊 Baseline vs Current Comparison

┌────────────────────┬──────────┬─────────┬───────┐
│ Metric             │ Baseline │ Current │ Delta │
├────────────────────┼──────────┼─────────┼───────┤
│ ASR Segments       │ 248      │ 248     │ +0    │
│ Speakers Detected  │ 2        │ 2       │ +0    │
│ Translation Segs   │ 246      │ 246     │ +0    │
│ Segment Loss Rate  │ 0.8%     │ 0.8%    │ +0.0% │
└────────────────────┴──────────┴─────────┴───────┘

✅ Quality metrics meet baseline standards
```

---

## 🎉 恭喜!你已经成功运行 PodTrans!

### 📊 完成清单

- ✅ Python 3.12+ 安装
- ✅ uv 包管理器安装
- ✅ 项目依赖安装
- ✅ API keys 配置
- ✅ 模型下载 (~1.9 GB)
- ✅ ASR 转录成功
- ✅ 翻译成功
- ✅ 结果质量验证

### 🚀 下一步

#### 1. 处理更长的播客

```bash
# 处理 60 分钟的播客
uv run podtrans transcribe data/input/long_podcast.mp3
uv run podtrans translate data/output/long_podcast/asr_result.json
```

#### 2. 调整配置优化性能

```bash
# 编辑 .env 使用更大的模型 (更高精度)
WHISPER_MODEL=large-v2  # 需要额外下载 2.8 GB

# 或使用更小的模型 (更快速度)
WHISPER_MODEL=base      # 只需 150 MB
```

#### 3. 批量处理多个文件

```bash
# 批量测试所有输入文件
uv run python scripts/test_pipeline.py --batch data/input/*.mp3
```

#### 4. 查看模型对比

```bash
# 对比不同翻译模型的性能
uv run python scripts/compare_models.py data/output/podcast/asr_result.json \
  --models qwen-max,qwen-plus,qwen-turbo
```

---

## 📚 进阶学习

### 完整文档

| 文档 | 内容 |
|------|------|
| [README.md](../README.md) | 项目概览和快速开始 |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | 详细安装指南 |
| [MODEL_DOWNLOAD_GUIDE.md](MODEL_DOWNLOAD_GUIDE.md) | 模型下载完全指南 |
| [CLAUDE.md](../CLAUDE.md) | 完整开发指引 |
| [BASELINE_SYSTEM.md](BASELINE_SYSTEM.md) | 基准版本管理 |

### 常用命令速查

```bash
# ASR 相关
uv run podtrans transcribe <audio> -m large-v2  # 使用更大模型
uv run podtrans transcribe <audio> -l en        # 指定语言
uv run podtrans transcribe <audio> --no-diarization  # 禁用说话人分离

# Translation 相关
uv run podtrans translate <input> -s en -t zh   # 指定源/目标语言
uv run podtrans translate <input> -o ./output   # 指定输出目录

# 辅助脚本
uv run python scripts/check_models.py           # 检查模型状态
uv run python scripts/compare_with_baseline.py  # 对比 baseline
uv run python scripts/test_pipeline.py          # 完整流程测试
```

---

## ❓ 常见问题 FAQ

### Q1: 首次运行为什么这么慢?

**A**: 首次运行需要下载约 1.9 GB 的模型。模型下载完成后,后续运行会快很多 (60秒音频约 1-2 分钟)。

### Q2: 我可以离线使用吗?

**A**:
- ✅ ASR 模块: 可以离线 (模型下载后)
- ❌ Translation 模块: 需要网络 (调用云端 API)
- ❌ TTS 模块: 需要外部服务

### Q3: macOS 用户可以用 GPU 加速吗?

**A**: 不可以。WhisperX 的底层 faster-whisper 不支持 MPS (Apple Silicon GPU)。必须使用 `DEVICE=cpu`。

### Q4: 翻译丢失了几个段落怎么办?

**A**: 这是已知问题,丢失率约 2-3%。项目有自动重试机制。如果仍然丢失,可以:
1. 减小 `TRANSLATION_MAX_SEGMENTS_PER_BATCH` (从 100 降到 50)
2. 重新运行翻译

### Q5: 翻译费用大概多少?

**A**:
- 60 分钟播客: 约 ¥0.1-0.5
- 使用 qwen-turbo 更便宜 (~¥0.1)
- 使用 qwen-max 更贵 (~¥0.5),但质量更好

### Q6: 可以翻译中文到英文吗?

**A**: 可以。修改翻译命令:

```bash
uv run podtrans translate <input> -s zh -t en
```

### Q7: 如何清理缓存释放空间?

**A**:

```bash
# 查看缓存大小
du -sh ~/.cache/huggingface/hub
du -sh ~/.cache/torch/hub

# 删除所有缓存
rm -rf ~/.cache/huggingface/hub/
rm -rf ~/.cache/torch/hub/

# 下次运行会重新下载
```

---

## 🆘 获取帮助

如果遇到问题:

1. **查看文档**:
   - [MODEL_DOWNLOAD_GUIDE.md](MODEL_DOWNLOAD_GUIDE.md) - 模型下载问题
   - [src/podtrans/translation/KNOWN_ISSUES.md](../src/podtrans/translation/KNOWN_ISSUES.md) - 已知问题

2. **运行诊断脚本**:
   ```bash
   uv run python scripts/check_models.py
   ```

3. **查看日志**:
   ```bash
   cat logs/*.log
   ```

4. **提交 Issue**:
   - GitHub Issues: https://github.com/YOUR_REPO/issues
   - 附上错误信息和日志

---

**祝你使用愉快! 🎉**

如果 PodTrans 对你有帮助,请给项目一个 ⭐ Star!

**最后更新**: 2025-11-28
**文档版本**: v1.0
