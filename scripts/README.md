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

### 优化后评估

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
