# 基准版本管理系统

## 📁 目录结构

```
data/
├── baseline/
│   ├── demo_v1_baseline/      # 当前最佳版本
│   │   ├── asr_result.json
│   │   ├── transcript.txt
│   │   ├── translation_result.json
│   │   ├── translation_result.zh.txt
│   │   ├── translation_result.bilingual.txt
│   │   ├── soulx_script.json
│   │   └── pipeline_metadata.json
│   ├── archive/               # 历史版本存档（不提交到 git）
│   └── README.md              # 版本说明文档
├── input/                     # 输入音频文件
├── output/                    # 当前输出结果
└── cache/                     # 模型缓存
```

## 🔧 工具脚本

所有脚本位于 `scripts/` 目录，详见 `scripts/README.md`。

### 1. `scripts/compare_with_baseline.py` - 版本对比

对比当前输出与 baseline 版本的质量指标：

```bash
uv run python scripts/compare_with_baseline.py
```

**输出信息**：
- ASR 段落数对比
- 说话人检测数对比
- 翻译段落数对比
- 段落丢失率对比
- 说话人分布对比
- 翻译文本样本对比

### 2. `scripts/update_baseline.py` - 更新基准

当优化后的版本质量更好时，更新 baseline：

```bash
uv run python scripts/update_baseline.py
```

**工作流程**：
1. 自动运行 `compare_with_baseline.py` 显示对比
2. 询问是否确认更新
3. 将旧 baseline 归档到 `data/baseline/archive/`
4. 复制当前输出到 baseline
5. 提醒更新 README.md

### 3. `scripts/convert_to_soulx.py` - 格式转换

将翻译结果转换为 SoulX-Podcast 可用的 JSON 格式：

```bash
uv run python scripts/convert_to_soulx.py
```

**输出**：`data/output/demo/soulx_script.json`

## 📊 质量评估标准

### 必须指标（Must Have）

| 指标 | 目标 | 说明 |
|-----|------|-----|
| 说话人检测数 | ≥ 2 | 至少能区分 2 个说话人 |
| 段落完整性 | ≥ 98% | 丢失率 ≤ 2% |
| 说话人保留率 | 100% | 翻译后说话人信息完整 |

### 优化指标（Nice to Have）

| 指标 | 期望方向 | 说明 |
|-----|---------|-----|
| 处理速度 | ↓ 更快 | 总处理时间减少 |
| API 成本 | ↓ 更低 | 翻译 API 调用成本 |
| 翻译质量 | ↑ 更好 | 流畅度、准确性 |
| 说话人准确率 | ↑ 更准 | 说话人分离准确性 |

## 🔄 优化工作流

### 标准流程

1. **运行优化版本**
   ```bash
   # 修改配置或代码
   uv run podtrans transcribe data/input/demo.mp3
   uv run podtrans translate data/output/demo/asr_result.json
   ```

2. **对比结果**
   ```bash
   uv run python scripts/compare_with_baseline.py
   ```

3. **评估改进**
   - 检查必须指标是否满足
   - 评估优化指标的变化
   - 主观评价翻译质量

4. **决定是否更新**
   - 如果整体质量提升 → 更新 baseline
   - 如果有退步 → 保留旧 baseline，继续优化

5. **更新 baseline**（如果决定更新）
   ```bash
   uv run python scripts/update_baseline.py
   # 然后编辑 data/baseline/README.md 记录改进点
   ```

### 示例场景

**场景 1：优化翻译批次大小**

```bash
# 修改 .env
TRANSLATION_MAX_SEGMENTS_PER_BATCH=50  # 从 100 改为 50

# 重新翻译
uv run podtrans translate data/output/demo/asr_result.json

# 对比
uv run python scripts/compare_with_baseline.py

# 如果丢失率降低了，考虑更新 baseline
```

**场景 2：更换翻译模型**

```bash
# 修改 .env
TRANSLATION_MODEL=qwen-turbo  # 从 qwen-max 改为 qwen-turbo

# 重新翻译
uv run podtrans translate data/output/demo/asr_result.json

# 对比质量和成本
uv run python scripts/compare_with_baseline.py
```

## 📝 版本记录规范

每次更新 baseline 后，在 `data/baseline/README.md` 中记录：

```markdown
### demo_vN_baseline

**创建时间**: YYYY-MM-DD

**相比上一版本的改进**:
- 说话人检测准确率提升 5%
- 翻译丢失率从 2% 降至 0.8%
- 处理速度提升 20%

**配置变更**:
- 翻译批次大小: 100 → 50
- 翻译模型: qwen-max (不变)

**质量指标**:
- ASR 段落数: 248
- 说话人数: 2
- 翻译段落数: 246
- 丢失率: 0.8%
```

## 🎯 最佳实践

1. **频繁对比**: 每次优化后都对比，不要累积多次修改
2. **记录配置**: 在 README 中详细记录配置参数
3. **保留证据**: 关键改进可以保留截图或对比结果
4. **谨慎更新**: baseline 应该是稳定的高质量版本，不要轻易替换
5. **版本归档**: 重要的历史版本可以保留在 archive 中
