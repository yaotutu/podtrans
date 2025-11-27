# Translation Module - Known Issues

## Issue #1: API 返回翻译数量不匹配

### 问题描述
使用 DashScope (qwen3-max) 翻译时，API 经常返回的翻译数量少于输入的片段数量。

### 复现条件
- 模型：qwen3-max, qwen-coder-plus
- 批次大小：50-100 个片段
- 现象：API 返回 97-98 个翻译，但发送了 100 个片段

### 测试记录

#### 测试 1: 全文翻译（248 片段 → 1 批次）
```
输入：248 segments
API 返回：
  - 第1次重试：238 translations (丢失 10 个)
  - 第2次重试：239 translations (丢失 9 个)
  - 第3次重试：238 translations (丢失 10 个)
结果：失败
```

#### 测试 2: 智能分批（248 片段 → 3 批次，每批 100/100/48）
```
批次 1：
  输入：100 segments
  API 返回：
    - 第1次重试：98 translations (丢失 2 个)
    - 第2次重试：97 translations (丢失 3 个)
    - 第3次重试：97 translations (丢失 3 个)
  结果：失败
```

### 可能原因

1. **API 输出长度限制**
   - DashScope API 可能有最大输出 token 限制
   - 大量翻译结果接近限制时会被截断

2. **JSON 格式生成不稳定**
   - qwen 系列模型在生成大型 JSON 数组时不够稳定
   - 可能在中途停止生成

3. **Response Format 限制**
   - 使用 `response_format={"type": "json_object"}` 可能有隐藏限制

### 当前解决方案（临时）

**版本 v0.1.0 - 部分接受策略**
```python
# translator.py line 202-208
if len(translations) != len(segments):
    logger.warning(f"{missing_count} segments will be skipped.")
    # 只使用已返回的翻译，丢弃缺失的片段
```

**行为**：
- 接受 API 返回的部分结果
- 丢失的片段不会出现在最终输出中
- 记录警告日志但继续执行

### 影响

- ✅ **优点**：翻译流程不会因少量丢失而完全失败
- ⚠️ **缺点**：最终翻译结果会缺少部分片段（约 2-3% 丢失率）
- 📊 **数据完整性**：对于 248 片段的播客，预计丢失 6-9 个片段

### 后续优化方案

#### 方案 A：减小批次大小（短期）
```python
TRANSLATION_MAX_SEGMENTS_PER_BATCH=50  # 从 100 降到 50
```
- 预期丢失率降低到 1-2%
- 但 API 调用次数翻倍

#### 方案 B：单片段重试（中期）
```python
# 对于丢失的片段，单独重新翻译
for missing_segment in missing_segments:
    retry_translation(missing_segment)
```
- 保证 100% 翻译
- 但增加复杂度和 API 调用

#### 方案 C：更换模型（推荐）
尝试其他模型，测试格式遵守能力：
- ✅ `qwen-plus`：通用模型，可能更稳定
- ✅ `qwen-turbo`：轻量级，可能更快更稳定
- ✅ `qwen2.5-72b-instruct`：更大模型，可能更准确

#### 方案 D：不使用 JSON 模式（激进）
```python
# 改用纯文本输出，自己解析
prompt = "翻译以下句子，每行一个翻译，用 ||| 分隔"
response_format = None  # 不强制 JSON
```

### 监控建议

添加翻译质量监控：
```python
# 记录每批的丢失率
loss_rate = (len(segments) - len(translations)) / len(segments)
if loss_rate > 0.05:  # 超过 5% 丢失
    logger.error(f"High loss rate: {loss_rate:.2%}")
```

---

## 优化优先级

1. **P0 (关键)**：测试其他模型（qwen-plus, qwen-turbo）
2. **P1 (重要)**：减小批次大小到 50
3. **P2 (次要)**：实现单片段重试机制
4. **P3 (低优)**：探索非 JSON 模式

---

**更新时间**: 2025-11-26  
**状态**: 🟡 已知问题，有临时方案  
**下一步**: 测试其他模型并记录结果
