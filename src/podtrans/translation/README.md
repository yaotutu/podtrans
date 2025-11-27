# Translation Module

## 概述

翻译模块负责将 ASR 转录结果从英文翻译为中文，使用 OpenAI 兼容的 API（阿里云 DashScope）。

## 架构设计

### 智能分批策略（方案 B）

基于 **128k 上下文模型** 设计，采用双重限制策略：

```
输入: 248 个片段
  ↓
Token 估算 + 片段计数
  ↓
智能分批: 
  - 限制 1: 每批 ≤ 120k tokens
  - 限制 2: 每批 ≤ 100 segments
  ↓
输出: 3 个批次
  - 批次 1: 100 segments (~1266 tokens)
  - 批次 2: 100 segments
  - 批次 3: 48 segments
```

### 核心组件

```
translation/
├── __init__.py          # 模块导出
├── schemas.py           # 数据模型
├── translator.py        # 翻译引擎
├── README.md            # 本文档
└── KNOWN_ISSUES.md      # 已知问题记录
```

## 功能特性

### 1. Token 计数（tiktoken）

使用 `cl100k_base` 编码器精确估算 token 数：

```python
# translator.py:48-61
def _estimate_tokens(self, text: str) -> int:
    if self.tokenizer:
        return len(self.tokenizer.encode(text))
    else:
        return len(text) // 2  # Fallback
```

### 2. 智能分批

```python
# translator.py:63-103
def _create_smart_batches(self, segments: list[Segment]) -> list[list[Segment]]:
    # 双重限制：
    # 1. Token 限制: max_tokens (默认 120k)
    # 2. 片段限制: max_segments_per_batch (默认 100)
    
    SYSTEM_OVERHEAD = 500  # System prompt 开销
    RESPONSE_OVERHEAD_PER_SEGMENT = 100  # 每个片段的中文输出开销
```

### 3. 容错机制

接受部分翻译结果，丢失的片段会被跳过：

```python
# translator.py:202-222
if len(translations) != len(segments):
    logger.warning(f"{missing_count} segments will be skipped.")
    # 只使用已返回的翻译
```

### 4. 输出格式

生成 3 种文件：

1. **JSON**：`translation_result.json`
   ```json
   {
     "segments": [...],
     "source_language": "en",
     "target_language": "zh",
     "model_name": "qwen3-max",
     "total_duration": 3600.5
   }
   ```

2. **中文文本**：`translation_result.zh.txt`
   ```
   [SPEAKER_00] 欢迎来到全新一期的深度挖掘。
   [SPEAKER_00] 今天，我们要揭开音频世界中一个非常迷人的层面。
   ```

3. **双语对照**：`translation_result.bilingual.txt`
   ```
   [SPEAKER_00] Welcome to a new Deep Dive.
   [SPEAKER_00] 欢迎来到全新一期的深度挖掘。

   [SPEAKER_00] Today we're peeling back a really fascinating layer of the audio world.
   [SPEAKER_00] 今天，我们要揭开音频世界中一个非常迷人的层面。
   ```

## 配置说明

### 环境变量（.env）

```bash
# API 密钥（必需）
DASHSCOPE_API_KEY=your_api_key_here

# 模型选择
TRANSLATION_MODEL=qwen3-max

# API 端点
TRANSLATION_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# 智能分批参数
TRANSLATION_MAX_TOKENS=120000              # 每批最大 token 数
TRANSLATION_MAX_SEGMENTS_PER_BATCH=100     # 每批最大片段数

# 重试设置
MAX_RETRIES=3
```

### 参数调优

**对于 128k 上下文模型**：
```bash
TRANSLATION_MAX_TOKENS=120000
TRANSLATION_MAX_SEGMENTS_PER_BATCH=100
```

**对于 32k 上下文模型**：
```bash
TRANSLATION_MAX_TOKENS=30000
TRANSLATION_MAX_SEGMENTS_PER_BATCH=50
```

**提高稳定性（减少丢失）**：
```bash
TRANSLATION_MAX_SEGMENTS_PER_BATCH=50   # 更小批次
MAX_RETRIES=5                           # 更多重试
```

## 使用示例

### 基本用法

```bash
# 翻译 ASR 结果
podtrans translate data/output/demo/asr_result.json

# 自定义输出目录
podtrans translate asr_result.json -o ./translations

# 自定义语言对
podtrans translate asr_result.json -s en -t zh
```

### 程序化使用

```python
from podtrans.config import get_settings
from podtrans.translation import Translator

settings = get_settings()
translator = Translator(settings)

# 加载 ASR 结果
asr_result = translator.load_asr_result("asr_result.json")

# 翻译
translation_result = translator.translate_asr_result(asr_result)

# 保存
translator.save_result(translation_result, "output/translation")
```

## 性能指标

### 测试环境
- 播客长度：~24 分钟
- 片段数量：248
- 模型：qwen3-max
- 批次配置：100 segments/batch

### 实测数据

```
智能分批结果:
  - 总批次: 3
  - 批次 1: 100 segments (~1266 tokens) ≈ 60 秒
  - 批次 2: 100 segments (~1266 tokens) ≈ 60 秒
  - 批次 3: 48 segments (~600 tokens) ≈ 30 秒
  - 总耗时: ~150 秒

翻译质量:
  - 成功率: ~97% (约 3% 片段丢失)
  - 翻译准确度: 主观评估良好
  - 术语一致性: 需要人工校对
```

## API 成本估算

```python
# DashScope qwen3-max 价格（2025-11）
# 输入：¥0.02/1k tokens
# 输出：¥0.06/1k tokens

# 单次翻译成本估算（248 片段）
输入 tokens: ~3200 × 3 批 = 9,600 tokens
输出 tokens: ~6400 × 3 批 = 19,200 tokens
总成本: (9.6 × 0.02) + (19.2 × 0.06) = ¥1.34
```

## 日志示例

```
2025-11-26 16:02:07 | INFO  | Initialized Translator with model=qwen3-max, max_tokens=120000
2025-11-26 16:02:07 | INFO  | Starting translation of 248 segments from en to zh
2025-11-26 16:02:07 | INFO  | Smart batching: 248 segments -> 3 batches (max 120000 tokens/batch)
2025-11-26 16:02:07 | INFO  | Translating batch 1/3: 100 segments, ~1266 tokens
2025-11-26 16:03:05 | WARN  | Translation count mismatch: expected 100, got 98. 2 segments will be skipped.
2025-11-26 16:03:05 | INFO  | Successfully translated 100 segments
```

## 故障排查

### 问题 1: API Key 未设置
```
Error: DASHSCOPE_API_KEY not set
```
**解决**：检查 `.env` 文件是否存在并包含正确的 API key

### 问题 2: 翻译数量不匹配
```
Translation count mismatch: expected 100, got 97
```
**解决**：这是已知问题，参见 `KNOWN_ISSUES.md`

### 问题 3: Token 超限
```
Error: maximum context length exceeded
```
**解决**：降低 `TRANSLATION_MAX_TOKENS` 或 `TRANSLATION_MAX_SEGMENTS_PER_BATCH`

## 下一步开发

- [ ] 测试其他模型（qwen-plus, qwen-turbo）
- [ ] 实现单片段重试机制
- [ ] 添加翻译质量评估
- [ ] 支持术语表（glossary）
- [ ] 缓存机制（避免重复翻译）

---

**版本**: v0.1.0  
**最后更新**: 2025-11-26  
**维护者**: PodTrans Team
