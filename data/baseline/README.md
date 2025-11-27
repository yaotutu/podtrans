# Baseline Versions

本目录存储基准版本，用于对比和评估优化效果。

## 版本说明

### demo_v1_baseline (当前最佳版本)

**创建时间**: 2025-11-27

**配置参数**:
- Whisper 模型: medium
- 设备: cpu (Apple Silicon)
- 说话人分离: pyannote.audio 3.3.2
- 翻译模型: qwen-max (DashScope)
- 翻译批次: 智能批处理 (120k tokens, max 100 segments)

**质量指标**:
- ASR 段落数: 248
- 检测到说话人: 2 (SPEAKER_00, SPEAKER_01)
- 翻译段落数: 246
- 说话人保留率: 100%

**文件清单**:
```
demo_v1_baseline/
├── asr_result.json           # ASR 原始结果
├── transcript.txt            # 英文转录文本
├── translation_result.json   # 翻译结果 (JSON)
├── translation_result.zh.txt # 中文翻译文本
├── translation_result.bilingual.txt  # 双语对照文本
├── soulx_script.json        # SoulX TTS 格式
└── pipeline_metadata.json   # 流水线元数据
```

**已知问题**:
- 翻译 API 偶尔有 2-3% 的段落丢失（已记录在 translation/KNOWN_ISSUES.md）
- ASR 耗时较长（13分钟音频需要约12分钟处理）

## 版本管理规则

1. 每次优化后，与当前 baseline 对比
2. 如果新版本质量更好，替换 baseline 并更新此文档
3. 保留版本号命名: `demo_v{N}_baseline`
4. 旧版本可选择性保留在 `archive/` 子目录

## 对比指标

优化时应关注以下指标：

- ✅ 说话人识别准确率
- ✅ 翻译质量（流畅度、准确性）
- ✅ 段落完整性（是否丢失）
- ⏱️ 处理速度
- 💰 API 成本
- 🎯 说话人标记一致性

## 使用方法

```bash
# 对比新版本和 baseline
diff data/output/demo/translation_result.zh.txt \
     data/baseline/demo_v1_baseline/translation_result.zh.txt

# 统计说话人分布
grep -o '"speaker": "SPEAKER_[0-9]*"' data/baseline/demo_v1_baseline/translation_result.json | sort | uniq -c
```
