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
