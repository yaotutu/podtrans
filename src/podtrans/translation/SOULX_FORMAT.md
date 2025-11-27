# SoulX-Podcast 格式适配分析

## SoulX-Podcast 输入格式

### 标准格式
```json
{
  "speakers": {
    "S1": {
      "prompt_audio": "path/to/audio1.wav",
      "prompt_text": "声音描述或样本文本"
    },
    "S2": {
      "prompt_audio": "path/to/audio2.wav", 
      "prompt_text": "声音描述或样本文本"
    }
  },
  "text": [
    ["S1", "你好，欢迎来到播客。"],
    ["S2", "很高兴见到你。"],
    ["S1", "今天我们聊聊技术话题。<|laughter|>"]
  ]
}
```

### 字段说明
- **speakers**: 说话人配置（可选，用于声音克隆）
  - `prompt_audio`: 参考音频路径（3-10秒样本）
  - `prompt_text`: 音频对应文本
- **text**: 对话数组
  - 格式：`[speaker_id, dialogue_text]`
  - 支持特殊标签：`<|laughter|>`, `<|sigh|>` 等

## 我们的翻译输出格式

### TranslationResult Schema
```json
{
  "segments": [
    {
      "start": 0.5,
      "end": 3.2,
      "original_text": "Hello, welcome to the podcast.",
      "translated_text": "你好，欢迎来到播客。",
      "speaker": "SPEAKER_00"
    },
    {
      "start": 3.5,
      "end": 5.8,
      "original_text": "Nice to meet you.",
      "translated_text": "很高兴见到你。",
      "speaker": "SPEAKER_01"
    }
  ],
  "source_language": "en",
  "target_language": "zh",
  "model_name": "qwen3-max",
  "total_duration": 3600.5
}
```

## 格式对比

| 特性 | SoulX-Podcast | 我们的格式 | 兼容性 |
|------|---------------|------------|--------|
| 说话人标识 | `S1`, `S2` | `SPEAKER_00`, `SPEAKER_01` | ✅ 需要映射 |
| 文本内容 | 纯中文 | `translated_text` 字段 | ✅ 完全兼容 |
| 时间戳 | ❌ 无 | ✅ 有 (start/end) | ⚠️ 我们有但 SoulX 不需要 |
| 说话人音频 | ✅ 需要 | ❌ 无 | ⚠️ 需要额外提供 |
| 对话顺序 | 数组顺序 | segments 顺序 | ✅ 完全兼容 |

## 转换需求

### ✅ 已满足
1. **中文翻译文本** - `translated_text` 字段直接可用
2. **说话人信息** - `speaker` 字段已包含
3. **对话顺序** - segments 数组保持时间顺序

### ⚠️ 需要转换
1. **说话人 ID 映射**
   ```
   SPEAKER_00 → S1
   SPEAKER_01 → S2
   None → S1 (默认)
   ```

2. **数据结构转换**
   ```python
   # 从 segments 转换为 text 数组
   segments → [["S1", "text"], ["S2", "text"], ...]
   ```

### ❌ 需要补充
1. **说话人音频样本** (speakers.prompt_audio)
   - 需要用户提供参考音频
   - 或使用默认音色

2. **说话人描述** (speakers.prompt_text)
   - 可选字段
   - 建议生成默认描述

## 实现方案

### 方案 A: 添加转换方法到 TranslationResult

```python
# translation/schemas.py

def to_soulx_format(
    self,
    speaker_audio_map: dict[str, str] | None = None,
    speaker_desc_map: dict[str, str] | None = None,
) -> dict:
    """Convert to SoulX-Podcast format.
    
    Args:
        speaker_audio_map: {speaker_id: audio_path}
        speaker_desc_map: {speaker_id: description}
        
    Returns:
        SoulX-Podcast compatible JSON dict
    """
    # 1. 映射说话人 ID
    speaker_mapping = self._create_speaker_mapping()
    
    # 2. 构建 speakers 配置
    speakers = {}
    for our_id, soulx_id in speaker_mapping.items():
        speakers[soulx_id] = {
            "prompt_audio": speaker_audio_map.get(our_id, ""),
            "prompt_text": speaker_desc_map.get(our_id, f"Speaker {soulx_id}")
        }
    
    # 3. 构建 text 数组
    text = []
    for seg in self.segments:
        soulx_id = speaker_mapping.get(seg.speaker, "S1")
        text.append([soulx_id, seg.translated_text])
    
    return {
        "speakers": speakers,
        "text": text
    }

def _create_speaker_mapping(self) -> dict[str, str]:
    """Map our speaker IDs to SoulX format (S1, S2, ...)."""
    unique_speakers = sorted(self.unique_speakers)
    return {
        speaker: f"S{i+1}" 
        for i, speaker in enumerate(unique_speakers)
    }
```

### 方案 B: 独立的转换工具类

```python
# translation/soulx_converter.py

class SoulXConverter:
    """Convert TranslationResult to SoulX-Podcast format."""
    
    def convert(
        self,
        translation_result: TranslationResult,
        speaker_config: dict | None = None,
    ) -> dict:
        """Convert translation result to SoulX format."""
        pass
```

## 推荐方案

**方案 A** - 添加 `to_soulx_format()` 方法到 `TranslationResult`

**理由**：
1. ✅ 简单直接，无需额外类
2. ✅ 与现有 `to_chinese_text()`, `to_bilingual_text()` 风格一致
3. ✅ 方便测试和使用
4. ✅ 符合数据模型的职责范围

## 使用示例（预期）

```python
from podtrans.translation import Translator

# 加载翻译结果
translator = Translator(settings)
translation_result = translator.load_result("translation_result.json")

# 转换为 SoulX 格式
soulx_data = translation_result.to_soulx_format(
    speaker_audio_map={
        "SPEAKER_00": "voices/male1.wav",
        "SPEAKER_01": "voices/female1.wav",
    },
    speaker_desc_map={
        "SPEAKER_00": "中年男性，声音低沉",
        "SPEAKER_01": "年轻女性，声音清脆",
    }
)

# 保存为 SoulX 格式
import json
with open("soulx_script.json", "w", encoding="utf-8") as f:
    json.dump(soulx_data, f, ensure_ascii=False, indent=2)
```

## CLI 命令设计（可选）

```bash
# 转换现有翻译结果为 SoulX 格式
podtrans to-soulx translation_result.json -o soulx_script.json

# 带说话人音频配置
podtrans to-soulx translation_result.json \
  --speaker-audio SPEAKER_00=voices/male.wav \
  --speaker-audio SPEAKER_01=voices/female.wav \
  -o soulx_script.json
```

## 已知限制

1. **说话人音频需要外部提供**
   - 我们的 ASR 结果不包含声音样本
   - 需要用户手动准备或使用默认音色

2. **说话人识别准确性**
   - 取决于 pyannote.audio 的识别质量
   - 可能需要人工校对说话人分配

3. **特殊标签处理**
   - SoulX 支持 `<|laughter|>` 等副语言标签
   - 我们的翻译模型不会自动生成这些标签
   - 可能需要后处理添加

## 下一步行动

- [ ] 实现 `to_soulx_format()` 方法
- [ ] 添加单元测试
- [ ] 更新文档和使用示例
- [ ] 考虑是否添加 CLI 命令

---

**创建时间**: 2025-11-26  
**状态**: 📝 设计文档  
**优先级**: P1 - 下一个开发目标
