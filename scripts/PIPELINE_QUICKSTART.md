# PodTrans 全流程脚本快速上手指南

## 🚀 一键使用

### 基本命令
```bash
# 激活环境
conda activate podtrans

# 一键处理英文音频到中文播客
python scripts/podcast_pipeline_simple.py data/input/your_audio.mp3
```

## 📂 文件组织

### 输入文件
- 将你的英文音频文件放入 `data/input/` 目录
- 支持格式: `mp3`, `wav`, `m4a`, `flac` 等

### 输出结构
脚本会自动创建以文件名命名的目录：
```
data/output/your_audio/
├── asr_result.json           # ASR 识别结果
├── translation_result.json   # 中文翻译结果
└── your_audio_chinese.wav    # 最终中文播客 🎵
```

## 💡 使用示例

### 示例 1: 处理单个文件
```bash
python scripts/podcast_pipeline_simple.py data/input/podcast_episode.mp3
```

### 示例 2: 批量处理多个文件
```bash
# 批量处理目录下所有 mp3 文件
for file in data/input/*.mp3; do
    echo "处理 $file..."
    python scripts/podcast_pipeline_simple.py "$file"
done
```

### 示例 3: 处理其他位置的文件
```bash
python scripts/podcast_pipeline_simple.py /home/user/podcasts/episode.mp3
```

## ⏱️ 处理时间预估

使用 GPU 加速时的预估时间：

| 音频时长 | ASR 时间 | 翻译时间 | TTS 时间 | **总时间** |
|---------|---------|---------|---------|-----------|
| 5分钟   | 1-2分钟 | 30秒    | 3-5分钟 | **5-8分钟** |
| 15分钟  | 3-5分钟 | 1-2分钟 | 8-12分钟| **12-19分钟** |
| 30分钟  | 6-8分钟 | 2-3分钟 | 15-25分钟| **23-36分钟** |

## 🎯 输出质量

- **ASR 准确率**: >95% (清晰语音)
- **说话人分离**: 准确识别 2-3 人对话
- **翻译质量**: 保持原意的自然中文表达
- **语音合成**: 接近人声的自然度，清晰的说话人区分

## 🔧 常见配置

### GPU 模式 (推荐，速度快)
```bash
# 检查 .env 配置
cat .env | grep DEVICE
# 应该显示: DEVICE=cuda
```

### CPU 模式 (兼容性好)
```bash
# 修改 .env 文件
sed -i 's/DEVICE=cuda/DEVICE=cpu/' .env
sed -i 's/COMPUTE_TYPE=float16/COMPUTE_TYPE=int8/' .env
```

## 📊 实时监控

脚本运行时会显示：
- 🔄 当前处理步骤
- ⏱️ 已用时间
- 📁 输出文件路径
- ✅ 完成状态

### 示例输出
```
╭────────── 流程开始 ───────────╮
│ 🎙️  PodTrans 全流程            │
│ 输入文件: data/input/test.mp3 │
│ 文件大小: 12.6 MB             │
│ 输出目录: data/output/test    │
╰───────────────────────────────╯

🔄 ASR (语音识别 + 说话人分离)... ✅ 完成 - 44.4秒
🔄 Translation (翻译)... ✅ 完成 - 6.2秒
🔄 TTS (语音合成)... ✅ 完成 - 156.3秒

============================================================
🎯 流程执行结果
┌─────────────────────┬──────┬────────┬──────────────────────┐
│ 步骤                │ 状态 │ 用时   │ 输出文件              │
├─────────────────────┼──────┼────────┼──────────────────────┤
│ ASR (语音识别)      │ ✅ 成功 │ 44.4s │ asr_result.json        │
│ Translation (翻译)  │ ✅ 成功 │ 6.2s  │ translation_result.json│
│ TTS (语音合成)      │ ✅ 成功 │ 156.3s│ test_chinese.wav      │
└─────────────────────┴──────┴────────┴──────────────────────┘

╭────────── 处理完成 ───────────╮
│ 🎉 全流程完成！                  │
│ 最终输出: data/output/test/test_chinese.wav │
│ 文件大小: 15.2 MB               │
│ 总用时: 207.1 秒 (3.5 分钟)     │
│ 现在你可以播放生成的中文播客了！  │
╰────────────────────────────────╯
```

## 🚨 故障排除

### 问题 1: GPU 内存不足
**错误**: `CUDA out of memory`
**解决**: 使用 CPU 模式
```bash
# 修改 .env 文件
echo "DEVICE=cpu" >> .env
echo "COMPUTE_TYPE=int8" >> .env
```

### 问题 2: 翻译 API 失败
**错误**: `LLM API error`
**解决**: 检查 API Key
```bash
# 检查配置
cat .env | grep LLM_API_KEY
# 如果为空，需要设置你的 API Key
```

### 问题 3: TTS 超时
**现象**: 长音频处理时间超过预期
**解决**: 耐心等待，这是正常的
- 30分钟音频可能需要 25-40 分钟处理
- 脚本会自动处理超时，只需耐心等待

## 🔍 检查结果

### 验证输出文件
```bash
# 检查文件是否生成
ls -la data/output/your_audio/

# 检查音频文件
file data/output/your_audio/your_audio_chinese.wav
# 应该显示: RIFF (little-endian) data, WAVE audio...
```

### 播放生成的播客
```bash
# 使用系统默认播放器
# Linux
xdg-open data/output/your_audio/your_audio_chinese.wav

# macOS
open data/output/your_audio/your_audio_chinese.wav

# 或使用任何音频播放器 (VLC, Audacity 等)
```

## 🎉 开始使用

现在你已经掌握了全流程脚本的使用方法！

1. **准备音频**: 将英文音频放入 `data/input/`
2. **运行脚本**: `python scripts/podcast_pipeline_simple.py your_file.mp3`
3. **等待完成**: 观察实时进度显示
4. **享受结果**: 播放生成的中文播客！

---

🎙️ **开始你的播客翻译之旅吧！**