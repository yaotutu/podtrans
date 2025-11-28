# 🚀 PodTrans 模型下载完全指南

> **为什么需要这份指南?** 模型下载是新用户最容易遇到问题的环节。本指南将帮助你顺利完成所有模型的下载和配置。

**版本**: v0.1.0 | **最后更新**: 2025-11-28

---

## 📊 模型下载清单

### 必需模型 (首次运行自动下载)

| 模块 | 模型名称 | 大小 | 用途 | 下载触发时机 |
|------|---------|------|------|------------|
| **ASR** | Whisper (medium) | **1.4 GB** | 语音识别 | 首次运行 `transcribe` |
| **ASR** | wav2vec2 对齐模型 | **360 MB** | 词级时间戳对齐 | 首次进行对齐 |
| **ASR** | speechbrain 说话人嵌入 | **85 MB** | 说话人分离 | 首次进行说话人分离 (需要 HF_TOKEN) |
| **ASR** | silero-vad | **31 MB** | 语音活动检测 | 说话人分离辅助 |

**总计**: **~1.9 GB** (使用默认 medium 模型)

### 可选更大模型

| 模型 | 大小 | 精度 | 速度 | 推荐场景 |
|------|------|------|------|---------|
| `tiny` | 75 MB | ⭐⭐ | ⭐⭐⭐⭐⭐ | 快速测试 |
| `base` | 150 MB | ⭐⭐⭐ | ⭐⭐⭐⭐ | 开发调试 |
| `small` | 500 MB | ⭐⭐⭐⭐ | ⭐⭐⭐ | 平衡选择 |
| `medium` | 1.4 GB | ⭐⭐⭐⭐ | ⭐⭐⭐ | **推荐** (默认) |
| `large-v2` | 2.8 GB | ⭐⭐⭐⭐⭐ | ⭐⭐ | 高精度需求 |
| `large-v3` | 3 GB | ⭐⭐⭐⭐⭐ | ⭐⭐ | 最高精度 |

### 无需本地下载的服务

- ✅ **Translation**: 阿里云 DashScope API (Qwen 模型 - 云端服务)
- ✅ **TTS**: SoulX-Podcast (外部部署服务)

---

## 🎯 快速开始: 一键预下载所有模型

### 方法 1: 运行测试音频 (推荐)

这是最简单的方法,会自动下载所有需要的模型:

```bash
# 准备一个短音频文件 (建议 30-60 秒)
# 可以从网上下载测试音频,或自己录制一段

# 运行一次完整的 ASR 流程 (会自动下载所有模型)
uv run podtrans transcribe data/input/test.mp3

# 预期输出:
# 📥 Downloading whisper model 'medium'... (第一次会显示)
# 📥 Downloading alignment model... (第一次会显示)
# 📥 Downloading diarization models... (第一次会显示,需要 HF_TOKEN)
# ✅ ASR completed successfully!
```

**预计耗时**:
- 首次运行: 5-15 分钟 (取决于网速)
- 后续运行: 1-2 分钟 (模型已缓存)

### 方法 2: Python 脚本预下载

如果你想单独下载模型而不处理音频:

```bash
# 创建预下载脚本
cat > scripts/preload_models.py << 'EOF'
"""预下载所有 ASR 模型"""
from pathlib import Path
from podtrans.asr import WhisperXHandler
from podtrans.config import get_settings

def main():
    settings = get_settings()
    print(f"🎯 开始预下载模型...")
    print(f"📦 Whisper 模型: {settings.whisper_model}")
    print(f"💾 设备: {settings.device}")
    print(f"🔧 计算类型: {settings.compute_type}")
    print()

    # 初始化 WhisperXHandler (会触发模型下载)
    print("1️⃣ 下载 Whisper 模型...")
    handler = WhisperXHandler(
        model_name=settings.whisper_model,
        device=settings.device,
        compute_type=settings.compute_type,
    )
    handler.load_model()
    print("✅ Whisper 模型下载完成!\n")

    print("2️⃣ wav2vec2 对齐模型会在首次运行 align() 时自动下载")
    print("3️⃣ 说话人分离模型会在首次运行 diarize() 时自动下载 (需要 HF_TOKEN)")
    print()
    print("🎉 主要模型预下载完成!")
    print("💡 提示: 运行一次 transcribe 命令会自动下载所有剩余模型")

if __name__ == "__main__":
    main()
EOF

# 运行预下载脚本
uv run python scripts/preload_models.py
```

---

## 📍 模型存储位置

所有模型都会自动缓存到以下目录:

### 1. HuggingFace 模型缓存

**位置**: `~/.cache/huggingface/hub/`

**包含模型**:
```
~/.cache/huggingface/hub/
├── models--Systran--faster-whisper-medium/     # 1.4 GB
├── models--Systran--faster-whisper-large-v2/   # 2.8 GB (如果使用)
├── models--pyannote--speaker-diarization-3.1/  # ~50 MB
├── models--pyannote--segmentation-3.0/         # ~20 MB
└── models--speechbrain--spkrec-ecapa-voxceleb/ # 85 MB
```

**查看缓存大小**:
```bash
du -sh ~/.cache/huggingface/hub/
```

### 2. PyTorch 模型缓存

**位置**: `~/.cache/torch/hub/`

**包含模型**:
```
~/.cache/torch/hub/
├── checkpoints/
│   └── wav2vec2_fairseq_base_ls960_asr_ls960.pth  # 360 MB
└── snakers4_silero-vad_master/                    # 31 MB (VAD 模型)
```

**查看缓存大小**:
```bash
du -sh ~/.cache/torch/hub/
```

### 3. 项目本地缓存

**位置**: `data/cache/`

**包含内容**:
```
data/cache/
├── translations/      # 翻译缓存 (JSON 文件)
└── .gitkeep
```

**说明**: 这不是模型缓存,而是翻译结果的缓存,用于避免重复翻译

---

## 🔧 模型下载配置

### 切换 Whisper 模型

在 `.env` 文件中修改:

```bash
# 使用更小的模型 (节省空间和时间)
WHISPER_MODEL=base      # 150 MB

# 使用默认模型
WHISPER_MODEL=medium    # 1.4 GB (推荐)

# 使用更大的模型 (更高精度)
WHISPER_MODEL=large-v2  # 2.8 GB
```

或在命令行中指定:

```bash
uv run podtrans transcribe demo.mp3 -m large-v2
```

### 设备选择

```bash
# macOS (Apple Silicon)
DEVICE=cpu
COMPUTE_TYPE=int8

# NVIDIA GPU
DEVICE=cuda
COMPUTE_TYPE=float16

# 纯 CPU
DEVICE=cpu
COMPUTE_TYPE=int8
```

---

## ⚠️ 常见问题和解决方案

### 问题 1: 模型下载速度慢或失败

**症状**:
```
Downloading: 0%|          | 0/1.4G [00:30<?, ?B/s]
HTTPError: Connection timeout
```

**解决方案**:

#### 方案 A: 使用 HuggingFace 镜像 (中国用户推荐)

```bash
# 设置镜像环境变量
export HF_ENDPOINT=https://hf-mirror.com

# 重新运行
uv run podtrans transcribe demo.mp3
```

**永久设置** (添加到 `~/.bashrc` 或 `~/.zshrc`):
```bash
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.zshrc
source ~/.zshrc
```

#### 方案 B: 手动下载模型

```bash
# 1. 安装 huggingface-cli
pip install huggingface-hub

# 2. 手动下载 Whisper 模型
huggingface-cli download Systran/faster-whisper-medium \
  --local-dir ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium

# 3. 下载说话人分离模型 (需要 HF_TOKEN)
export HF_TOKEN=your_token_here
huggingface-cli download pyannote/speaker-diarization-3.1 \
  --local-dir ~/.cache/huggingface/hub/models--pyannote--speaker-diarization-3.1
```

#### 方案 C: 使用代理

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

uv run podtrans transcribe demo.mp3
```

---

### 问题 2: 说话人分离模型下载失败

**症状**:
```
HTTPError: 401 Client Error: Unauthorized for url:
https://huggingface.co/pyannote/speaker-diarization-3.1/resolve/main/...
```

**原因**: 未设置 `HF_TOKEN` 或未接受模型使用协议

**解决方案**:

#### 步骤 1: 创建 HuggingFace Token

1. 访问 https://huggingface.co/settings/tokens
2. 点击 "New token"
3. 选择 "Read" 权限
4. 复制生成的 token (格式: `hf_xxxxxxxxxxxx`)

#### 步骤 2: 接受模型使用协议 (重要!)

**必须访问以下页面并点击 "Agree and access repository"**:

1. https://huggingface.co/pyannote/speaker-diarization-3.1
2. https://huggingface.co/pyannote/segmentation-3.0

如果不接受协议,即使设置了 token 也会报 401 错误!

#### 步骤 3: 配置 Token

在 `.env` 文件中添加:
```bash
HF_TOKEN=hf_your_actual_token_here
```

#### 步骤 4: 验证

```bash
# 测试 token 是否有效
uv run python -c "
from huggingface_hub import HfApi
api = HfApi()
user = api.whoami()
print(f'✅ Token 有效! 用户: {user[\"name\"]}')"

# 重新运行
uv run podtrans transcribe demo.mp3
```

---

### 问题 3: 磁盘空间不足

**症状**:
```
OSError: [Errno 28] No space left on device
```

**检查空间**:
```bash
# 检查可用空间
df -h ~/.cache

# 查看模型缓存大小
du -sh ~/.cache/huggingface/hub/
du -sh ~/.cache/torch/hub/
```

**解决方案**:

#### 方案 A: 清理不用的模型

```bash
# 删除不用的 Whisper 模型
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-base
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-small

# 只保留你需要的模型 (例如 medium)
```

#### 方案 B: 使用更小的模型

在 `.env` 中修改:
```bash
WHISPER_MODEL=base  # 只需 150 MB
```

#### 方案 C: 移动缓存目录到其他磁盘

```bash
# 移动缓存到其他磁盘
mv ~/.cache/huggingface /Volumes/ExternalDrive/huggingface_cache

# 创建软链接
ln -s /Volumes/ExternalDrive/huggingface_cache ~/.cache/huggingface
```

---

### 问题 4: 模型加载失败

**症状**:
```
RuntimeError: Error loading model weights
OSError: Unable to load weights from checkpoint
```

**原因**: 模型文件损坏或下载不完整

**解决方案**:

```bash
# 1. 删除损坏的模型缓存
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium

# 2. 重新下载
uv run podtrans transcribe demo.mp3
```

---

### 问题 5: 网络连接超时

**症状**:
```
requests.exceptions.ReadTimeout: HTTPSConnectionPool
```

**解决方案**:

```bash
# 增加超时时间
export HF_HUB_DOWNLOAD_TIMEOUT=300

# 或使用镜像
export HF_ENDPOINT=https://hf-mirror.com

uv run podtrans transcribe demo.mp3
```

---

## 📦 完整模型下载检查清单

使用以下脚本检查所有模型是否已下载:

```bash
# 创建检查脚本
cat > scripts/check_models.py << 'EOF'
"""检查所有模型是否已下载"""
from pathlib import Path
import os

def check_file_size(path: Path) -> str:
    """返回人类可读的文件大小"""
    if not path.exists():
        return "❌ 未找到"

    size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"✅ {size:.1f} {unit}"
        size /= 1024
    return f"✅ {size:.1f} TB"

def main():
    cache_dir = Path.home() / ".cache"

    print("🔍 PodTrans 模型下载检查\n")
    print("=" * 60)

    # Whisper 模型
    print("\n📦 Whisper 模型:")
    for model in ["tiny", "base", "small", "medium", "large-v2", "large-v3"]:
        path = cache_dir / "huggingface" / "hub" / f"models--Systran--faster-whisper-{model}"
        status = check_file_size(path)
        print(f"  {model:12} {status}")

    # wav2vec2 对齐模型
    print("\n📦 wav2vec2 对齐模型:")
    path = cache_dir / "torch" / "hub" / "checkpoints" / "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
    status = "✅ 已下载" if path.exists() else "❌ 未下载"
    print(f"  wav2vec2:    {status}")

    # 说话人分离模型
    print("\n📦 说话人分离模型:")
    models = [
        ("speechbrain", "models--speechbrain--spkrec-ecapa-voxceleb"),
        ("pyannote-diarization", "models--pyannote--speaker-diarization-3.1"),
        ("pyannote-segmentation", "models--pyannote--segmentation-3.0"),
        ("silero-vad", "snakers4_silero-vad_master"),
    ]

    for name, folder in models:
        if folder.startswith("snakers4"):
            path = cache_dir / "torch" / "hub" / folder
        else:
            path = cache_dir / "huggingface" / "hub" / folder
        status = check_file_size(path)
        print(f"  {name:25} {status}")

    # 总计
    print("\n" + "=" * 60)
    hf_size = check_file_size(cache_dir / "huggingface" / "hub")
    torch_size = check_file_size(cache_dir / "torch" / "hub")
    print(f"📊 HuggingFace 缓存总计: {hf_size}")
    print(f"📊 PyTorch 缓存总计:     {torch_size}")
    print("=" * 60)

if __name__ == "__main__":
    main()
EOF

# 运行检查
uv run python scripts/check_models.py
```

**预期输出示例**:
```
🔍 PodTrans 模型下载检查

============================================================

📦 Whisper 模型:
  tiny         ❌ 未找到
  base         ✅ 141 MB
  small        ❌ 未找到
  medium       ✅ 1.4 GB
  large-v2     ✅ 2.8 GB
  large-v3     ❌ 未找到

📦 wav2vec2 对齐模型:
  wav2vec2:    ✅ 已下载

📦 说话人分离模型:
  speechbrain              ✅ 85 MB
  pyannote-diarization     ✅ 50 MB
  pyannote-segmentation    ✅ 20 MB
  silero-vad               ✅ 31 MB

============================================================
📊 HuggingFace 缓存总计: ✅ 4.5 GB
📊 PyTorch 缓存总计:     ✅ 422 MB
============================================================
```

---

## 🎯 推荐的模型下载策略

### 新用户 (首次使用)

1. **使用 base 模型快速测试**:
   ```bash
   # .env
   WHISPER_MODEL=base

   # 运行测试 (只需下载 150 MB)
   uv run podtrans transcribe demo.mp3
   ```

2. **确认一切正常后,切换到 medium**:
   ```bash
   # .env
   WHISPER_MODEL=medium

   # 重新运行 (下载 1.4 GB)
   uv run podtrans transcribe demo.mp3
   ```

### 生产环境

直接使用 `medium` 或 `large-v2`:

```bash
WHISPER_MODEL=medium    # 推荐 (1.4 GB, 平衡精度和速度)
# 或
WHISPER_MODEL=large-v2  # 高精度 (2.8 GB, 速度较慢)
```

### 离线部署

提前下载所有模型到本地,然后打包:

```bash
# 1. 下载所有模型
uv run podtrans transcribe demo.mp3

# 2. 打包缓存目录
tar -czf podtrans_models.tar.gz \
  ~/.cache/huggingface/hub/ \
  ~/.cache/torch/hub/

# 3. 在目标机器解压
tar -xzf podtrans_models.tar.gz -C ~/
```

---

## 💡 优化建议

### 1. 使用 SSD 存储模型

模型加载速度会显著提升:
- HDD: 5-10 秒
- SSD: 2-3 秒

### 2. 预热模型

首次加载后,模型会被操作系统缓存到内存:
- 首次加载: 2-5 秒
- 后续加载: <1 秒

### 3. 定期清理缓存

```bash
# 清理 HuggingFace 缓存
huggingface-cli delete-cache

# 只删除不用的模型
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny
```

---

## 📞 获取帮助

如果遇到模型下载问题:

1. 查看本文档的"常见问题和解决方案"章节
2. 运行 `scripts/check_models.py` 检查模型状态
3. 查看 PodTrans 日志: `cat logs/*.log`
4. 提交 GitHub Issue: https://github.com/YOUR_REPO/issues

---

**最后更新**: 2025-11-28
**文档版本**: v1.0
**适用项目版本**: PodTrans v0.1.0
