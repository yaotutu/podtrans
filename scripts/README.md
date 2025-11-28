# Scripts 目录

本目录包含项目相关的辅助脚本和工具。

## 📁 脚本分类

### 基准版本管理

#### `compare_with_baseline.py`
对比当前输出与 baseline 版本的质量指标。

**用法**:
```bash
uv run python scripts/compare_with_baseline.py
```

**功能**:
- 对比 ASR/翻译段落数
- 对比说话人检测数量
- 对比段落丢失率
- 显示说话人分布差异
- 显示翻译文本样本对比

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
```

---

#### `update_baseline.py`
更新 baseline 版本（当优化后质量更好时）。

**用法**:
```bash
uv run python scripts/update_baseline.py
```

**工作流程**:
1. 自动运行 `compare_with_baseline.py` 显示对比
2. 询问用户确认是否更新
3. 将旧 baseline 归档到 `data/baseline/archive/`
4. 用当前输出替换 baseline
5. 提醒更新 `data/baseline/README.md`

**注意**: 更新后务必编辑 `data/baseline/README.md` 记录改进点！

---

#### `convert_to_soulx.py`
将翻译结果转换为 SoulX-Podcast 可用的 JSON 格式。

**用法**:
```bash
uv run python scripts/convert_to_soulx.py
```

**输入**: `data/output/demo/translation_result.json`  
**输出**: `data/output/demo/soulx_script.json`

**用途**:
- 用于外部 SoulX-Podcast CLI 测试
- 验证格式转换是否正确
- 独立于 HTTP API 的格式验证

**输出格式**:
```json
{
  "speakers": {
    "S1": {},
    "S2": {}
  },
  "text": [
    ["S2", "欢迎来到全新一期的深度探索。"],
    ["S1", "是的，我觉得真正有趣的是..."]
  ]
}
```

---

### 模型管理 🆕

#### `check_models.py`
检查所有 ASR 模型是否已下载到本地缓存。

**用法**:
```bash
uv run python scripts/check_models.py
```

**功能**:
- ✅ 检查 Whisper 模型 (所有尺寸)
- ✅ 检查 wav2vec2 对齐模型
- ✅ 检查说话人分离模型 (pyannote, speechbrain, silero-vad)
- ✅ 显示缓存大小
- ✅ 统计总缓存占用

**输出示例**:
```
🔍 PodTrans 模型下载检查

============================================================

📦 Whisper 模型:
  tiny         ❌ 未找到
  base         ✅ 141.0 MB
  small        ❌ 未找到
  medium       ✅ 1.4 GB
  large-v2     ✅ 2.8 GB
  large-v3     ❌ 未找到

📦 wav2vec2 对齐模型:
  wav2vec2:    ✅ 已下载 (360 MB)

📦 说话人分离模型:
  speechbrain              ✅ 85.0 MB
  pyannote-diarization     ✅ 50.0 MB
  pyannote-segmentation    ✅ 20.0 MB
  silero-vad               ✅ 31.0 MB

============================================================
📊 HuggingFace 缓存总计: ✅ 4.5 GB
📊 PyTorch 缓存总计:     ✅ 422.0 MB
============================================================
```

**使用场景**:
1. **首次安装后检查**: 确认所有模型是否已下载
2. **故障排查**: 检查模型缺失或损坏
3. **清理缓存前**: 查看哪些模型可以删除
4. **磁盘空间管理**: 了解模型占用空间

---

#### `preload_models.py`
预下载 Whisper 模型到本地缓存。

**用法**:
```bash
uv run python scripts/preload_models.py
```

**功能**:
- ✅ 根据 .env 配置下载 Whisper 模型
- ✅ 显示下载进度
- ✅ 提示其他模型的下载方式

**输出示例**:
```
🎯 开始预下载 ASR 模型...
📦 Whisper 模型: medium
💾 设备: cpu
🔧 计算类型: int8

1️⃣ 下载 Whisper 模型...
Downloading: 100%|██████████| 1.4G/1.4G [03:45<00:00, 6.2MB/s]
✅ Whisper 模型下载完成!

2️⃣ wav2vec2 对齐模型会在首次运行 align() 时自动下载
3️⃣ 说话人分离模型会在首次运行 diarize() 时自动下载 (需要 HF_TOKEN)

🎉 主要模型预下载完成!
💡 提示: 运行一次 `podtrans transcribe` 命令会自动下载所有剩余模型
```

**使用场景**:
1. **新环境初始化**: 提前下载模型避免首次运行等待
2. **离线部署准备**: 在有网络时预下载所有模型
3. **模型缓存预热**: 加速首次使用体验

**相关文档**: 参见 [docs/MODEL_DOWNLOAD_GUIDE.md](../docs/MODEL_DOWNLOAD_GUIDE.md)

---

### 🚀 全流程脚本 (新增)

#### `podcast_pipeline_simple.py` ⭐
一键完成从英文音频到中文播客的完整流程！

**用法**:
```bash
# 处理单个文件
python scripts/podcast_pipeline_simple.py data/input/your_audio.mp3

# 处理完整路径下的文件
python scripts/podcast_pipeline_simple.py /path/to/podcast.mp3

# 批量处理多个文件
for file in data/input/*.mp3; do
    python scripts/podcast_pipeline_simple.py "$file"
done
```

**功能**:
- ✅ **ASR (语音识别)**: WhisperX + 说话人分离
- ✅ **Translation (翻译)**: 智能翻译，保留说话人信息
- ✅ **TTS (语音合成)**: SoulX-Podcast 多说话人合成
- ✅ **文件管理**: 自动按输入文件名创建输出目录
- ✅ **进度显示**: 实时显示处理进度和用时
- ✅ **结果汇总**: 生成详细的处理结果表格

**输入要求**:
- 文件格式: mp3, wav, m4a 等音频格式
- 语言: 英文语音
- 位置: `data/input/` 目录下或提供完整路径

**输出结构**:
```
data/output/your_audio/
├── asr_result.json           # ASR 识别结果
├── translation_result.json   # 翻译结果
└── your_audio_chinese.wav    # 最终中文播客
```

**性能预估**:
| 音频时长 | 总处理时间 (GPU) |
|---------|----------------|
| 5分钟   | 5-9分钟        |
| 15分钟  | 13-20分钟      |
| 30分钟  | 25-39分钟      |

**示例输出**:
```
╭────────── 流程开始 ───────────╮
│ 🎙️  PodTrans 全流程            │
│ 输入文件: data/input/test.mp3 │
│ 文件大小: 12.6 MB             │
│ 输出目录: data/output/test    │
╰───────────────────────────────╯

🔄 ASR (语音识别 + 说话人分离)... ✅ 完成 - 45.2秒
🔄 Translation (翻译)... ✅ 完成 - 28.7秒
🔄 TTS (语音合成)... ✅ 完成 - 156.3秒

============================================================
🎯 流程执行结果
┌─────────────────────┬──────┬────────┬──────────────────────┐
│ 步骤                │ 状态 │ 用时   │ 输出文件              │
├─────────────────────┼──────┼────────┼──────────────────────┤
│ ASR (语音识别)      │ ✅ 成功 │ 45.2s │ data/output/test/asr_result.json │
│ Translation (翻译)  │ ✅ 成功 │ 28.7s │ data/output/test/translation_result.json │
│ TTS (语音合成)      │ ✅ 成功 │ 156.3s│ data/output/test/test_chinese.wav │
└─────────────────────┴──────┴────────┴──────────────────────┘

╭────────── 处理完成 ───────────╮
│ 🎉 全流程完成！                  │
│ 最终输出: data/output/test/test_chinese.wav │
│ 文件大小: 15.2 MB               │
│ 总用时: 230.2 秒 (3.8 分钟)     │
│ 输出目录: data/output/test      │
│ 现在你可以播放生成的中文播客了！  │
╰────────────────────────────────╯
```

**使用场景**:
1. **日常使用**: 快速将英文播客翻译为中文播客
2. **批量处理**: 一次处理多个音频文件
3. **测试验证**: 验证完整流水线功能
4. **演示展示**: 向他人展示完整功能

---

### 测试和验证

#### `compare_models.py` 🆕⭐
对比不同翻译模型的性能和成本。

**用法**:
```bash
# 对比多个模型
uv run python scripts/compare_models.py data/output/demo/asr_result.json \\
  --models qwen-max,qwen-plus,qwen-turbo

# 自定义批次大小
uv run python scripts/compare_models.py data/output/demo/asr_result.json \\
  --models qwen-max,qwen-plus \\
  --batch-size 50

# 禁用缓存进行纯净对比
uv run python scripts/compare_models.py data/output/demo/asr_result.json \\
  --models qwen-max,qwen-plus \\
  --no-cache
```

**对比维度**:
- ✅ 翻译质量评分 (0-100 + A-F 等级)
- ✅ 段落丢失率
- ✅ 处理速度 (seg/s)
- ✅ API 成本估算 (¥)
- ✅ 缓存命中率

**输出示例**:
```
Model Comparison
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Model         ┃ Status ┃ Loss Rate ┃ Quality  ┃ Time (s) ┃ Speed  ┃ Cost (¥) ┃ Cache Hit ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ qwen-max      │   ✓    │     0.00% │ 95.0 (A+)│   138.88 │  1.79  │   ¥1.340 │     0.0%  │
│ qwen-plus     │   ✓    │     0.00% │ 92.5 (A) │   115.23 │  2.15  │   ¥0.402 │     0.0%  │
│ qwen-turbo    │   ✓    │     0.40% │ 88.0 (A) │    98.45 │  2.52  │   ¥0.128 │     0.0%  │
└───────────────┴────────┴───────────┴──────────┴──────────┴────────┴──────────┴───────────┘

Recommended Model:
  Model: qwen-max
  Quality: 95.0/100 (A+)
  Loss Rate: 0.00%
  Cost: ¥1.340
  Speed: 1.79 seg/s
```

**使用场景**:
1. **模型选型**: 找到最佳性价比模型
2. **成本优化**: 对比不同模型的成本差异
3. **质量评估**: 多模型质量对比
4. **性能测试**: 速度和稳定性对比

---

#### `test_translation_modes.py` 🆕
测试和对比不同翻译模式和配置的效果。

**用法**:
```bash
# 测试 JSON 模式 (默认)
uv run python scripts/test_translation_modes.py data/output/demo/asr_result.json

# 测试纯文本模式
uv run python scripts/test_translation_modes.py data/output/demo/asr_result.json --mode text

# 对比 JSON vs 文本模式
uv run python scripts/test_translation_modes.py data/output/demo/asr_result.json --compare

# 测试不同批次大小
uv run python scripts/test_translation_modes.py data/output/demo/asr_result.json --batch-size 30,50,100

# 完整对比测试 (两种模式 × 三种批次大小)
uv run python scripts/test_translation_modes.py data/output/demo/asr_result.json --compare --batch-size 30,50,100
```

**功能**:
- ✅ 测试 JSON 模式 vs 纯文本模式
- ✅ 测试不同批次大小 (30/50/100)
- ✅ 计算段落丢失率
- ✅ 测量处理时间
- ✅ 生成对比表格
- ✅ 推荐最佳配置

**输出示例**:
```
Translation Mode Comparison
┌──────┬────────────┬───────┬────────┬──────┬───────────┬──────────┬────────┐
│ Mode │ Batch Size │ Input │ Output │ Lost │ Loss Rate │ Time (s) │ Status │
├──────┼────────────┼───────┼────────┼──────┼───────────┼──────────┼────────┤
│ JSON │ 30         │ 248   │ 248    │ 0    │ 0.00%     │ 145.32   │ ✓      │
│ JSON │ 50         │ 248   │ 246    │ 2    │ 0.81%     │ 98.45    │ ✓      │
│ Text │ 30         │ 248   │ 248    │ 0    │ 0.00%     │ 142.18   │ ✓      │
│ Text │ 50         │ 248   │ 247    │ 1    │ 0.40%     │ 95.67    │ ✓      │
└──────┴────────────┴───────┴────────┴──────┴───────────┴──────────┴────────┘

Recommended Configuration:
  Mode: Text
  Batch Size: 30
  Loss Rate: 0.00%
  Time: 142.18s
```

**使用场景**:
1. **验证 JSON 模式兼容性**: 测试您的模型是否支持 response_format
2. **优化批次大小**: 找到速度和稳定性的最佳平衡点
3. **对比模式性能**: 比较 JSON 和文本模式的丢失率差异
4. **配置决策**: 基于实际数据选择最佳配置

---

#### `test_pipeline.py` ⭐
完整流程测试脚本 - 快速验证 ASR + Translation 优化效果。

**用法**:
```bash
# 测试默认文件 (data/input/demo.mp3)
uv run python scripts/test_pipeline.py

# 测试指定音频
uv run python scripts/test_pipeline.py --audio data/input/another.mp3

# 批量测试多个文件
uv run python scripts/test_pipeline.py --batch data/input/*.mp3

# 跳过 baseline 对比
uv run python scripts/test_pipeline.py --no-compare

# 仅运行 ASR 阶段
uv run python scripts/test_pipeline.py --asr-only

# 仅运行 Translation 阶段 (需要已有 ASR 结果)
uv run python scripts/test_pipeline.py --translation-only
```

**功能**:
- ✅ 自动运行 ASR → Translation 完整流程
- ✅ 自动与 baseline 对比质量指标
- ✅ 生成详细测试报告 (Markdown + JSON)
- ✅ 支持批量测试多个音频文件
- ✅ 性能监控 (耗时、速度)
- ✅ 质量评估 (说话人检测、段落完整性、说话人保留率)

**输出文件**:
- `data/output/{audio_name}/test_report.md` - Markdown 格式报告
- `data/output/{audio_name}/test_results.json` - JSON 格式结果
- `data/output/batch_test_results.json` - 批量测试汇总 (批量模式)

**使用场景**:
1. **优化后快速验证**: 修改配置后一键测试完整流程
2. **性能对比**: 对比不同配置下的处理速度
3. **质量保证**: 确保优化不降低质量
4. **批量验证**: 测试多个场景确保稳定性

---

#### `test_soulx_format.py`
快速测试 SoulX 格式转换功能。

**用法**:
```bash
uv run python scripts/test_soulx_format.py
```

**功能**:
- 加载翻译结果
- 测试格式转换
- 显示说话人映射
- 显示前几个文本段落样本

---

## 🔄 典型工作流

### 快速测试流程 (推荐) ⭐

使用 `test_pipeline.py` 一键完成所有步骤:

```bash
# 1. 修改配置或代码
vim .env

# 2. 运行完整测试 (自动运行 ASR + Translation + 对比 + 生成报告)
uv run python scripts/test_pipeline.py

# 3. 查看测试报告
cat data/output/demo/test_report.md

# 4. 如果质量提升，更新 baseline
uv run python scripts/update_baseline.py

# 5. 记录改进点
vim data/baseline/README.md
```

### 手动分步执行流程

如果需要更精细的控制:

```bash
# 1. 修改配置或代码
vim .env

# 2. 重新运行流程
uv run podtrans transcribe data/input/demo.mp3
uv run podtrans translate data/output/demo/asr_result.json

# 3. 对比结果
uv run python scripts/compare_with_baseline.py

# 4. 如果质量提升，更新 baseline
uv run python scripts/update_baseline.py

# 5. 记录改进点
vim data/baseline/README.md
```

### 批量测试多个音频

```bash
# 批量测试所有输入文件
uv run python scripts/test_pipeline.py --batch data/input/*.mp3

# 查看批量测试汇总
cat data/output/batch_test_results.json
```

### SoulX TTS 测试

```bash
# 1. 转换格式
uv run python scripts/convert_to_soulx.py

# 2. 用 SoulX CLI 测试
cd /path/to/SoulX-Podcast
python -m soulx_podcast.cli \
  --script /path/to/podtrans/data/output/demo/soulx_script.json \
  --output podcast_output.wav
```

---

## 📝 添加新脚本

在此目录添加新脚本时，请：

1. 使用描述性文件名 (如 `analyze_speaker_accuracy.py`)
2. 在文件顶部添加 docstring 说明用途
3. 更新此 README.md 添加脚本说明
4. 更新项目根目录的 CLAUDE.md

### 脚本模板

```python
"""Brief description of what this script does.

Usage:
    uv run python scripts/your_script.py

Example:
    uv run python scripts/your_script.py --option value
"""

def main():
    # Your code here
    pass

if __name__ == "__main__":
    main()
```

---

## 🎯 最佳实践

1. **保持独立性**: 脚本应该能独立运行，不依赖复杂的上下文
2. **清晰输出**: 使用 rich 库提供美观的终端输出
3. **错误处理**: 提供清晰的错误信息和使用提示
4. **文档完整**: 在 docstring 和 README 中都记录用法
5. **路径灵活**: 支持相对路径和绝对路径
