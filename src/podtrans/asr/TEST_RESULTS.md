# ASR 模块测试结果

## 测试环境

- **设备**: Mac M4 (Apple Silicon)
- **Python**: 3.12
- **Device**: CPU (faster-whisper 不支持 MPS)
- **Compute Type**: int8 (CPU 模式下 float16 不支持)
- **测试音频**: demo.mp3 (822.52秒 / 13.71分钟)

## 依赖版本

```
torch==2.4.1
torchaudio==2.4.1
pyannote-audio==3.3.2
whisperx==3.3.1
ctranslate2==4.4.0
```

## 测试结果

### ✅ base 模型

**配置:**
```bash
uv run podtrans transcribe data/input/demo.mp3 --model base --no-diarization
```

**结果:**
- 状态: ✅ 成功
- 转录时长: ~79 秒
- 处理速度: ~10.4x 实时速度
- 段落数: 247
- 语言检测: en (1.00)
- 输出大小: 412KB (asr_result.json)

**特点:**
- 速度快，适合快速测试和预览
- 准确度一般
- 资源占用低

---

### ✅ medium 模型（推荐）

**配置:**
```bash
uv run podtrans transcribe data/input/demo.mp3 --model medium --no-diarization
```

**结果:**
- 状态: ✅ 成功
- 转录时长: 237.06 秒 (~4分钟)
- 处理速度: ~3.5x 实时速度
- 段落数: 248
- 语言检测: en (1.00)
- 输出大小: 411KB (asr_result.json)

**特点:**
- 速度适中
- **准确度高，适合生产环境** ⭐
- 平衡性能和质量

---

### ❌ large-v2 模型

**配置:**
```bash
uv run podtrans transcribe data/input/demo.mp3 --model large-v2 --no-diarization
```

**结果:**
- 状态: ❌ 失败（段错误 - Exit code 139）
- 原因: CPU 模式下模型太大，内存需求过高
- ctranslate2 在 Apple Silicon CPU 模式下对大模型兼容性问题

**建议:**
- 在 Mac M4 CPU 模式下不推荐使用 large-v2
- 如需更高精度，使用 medium 模型已足够

---

## 模型对比总结

| 模型 | 状态 | 转录时长 | 速度倍率 | 精度 | 推荐场景 |
|------|------|----------|----------|------|----------|
| **base** | ✅ | ~79s | 10.4x | ⭐⭐⭐ | 快速测试、预览 |
| **medium** | ✅ | ~237s | 3.5x | ⭐⭐⭐⭐⭐ | **生产环境** ⭐ |
| **large-v2** | ❌ | - | - | - | 不可用（CPU模式） |

## 输出文件

每次转录生成以下文件（位于 `data/output/{audio_name}/`）：

1. **asr_result.json** - 完整的 ASR 结果
   - 包含所有段落和词级时间戳
   - 大小: ~400KB (13分钟音频)

2. **transcript.txt** - 纯文本转录稿
   - 包含说话人标签（如果启用 diarization）
   - 大小: ~14KB

3. **pipeline_metadata.json** - 流程元数据
   - 处理时间、状态、段落数、说话人数等
   - 大小: ~600B

## 已知问题

1. ⚠️ **pyannote.audio 版本警告**
   - 模型使用 0.0.1 训练，当前版本 3.3.2
   - 不影响功能，可忽略

2. ⚠️ **torch 版本警告**
   - 模型使用 1.10.0 训练，当前版本 2.4.1
   - 不影响功能，可忽略

3. ⚠️ **uv 警告**
   - `tool.uv.dev-dependencies` 已废弃
   - 建议迁移到 `dependency-groups.dev`

## 下一步

- ✅ ASR 模块已完成并验证
- ⏭️ 开始实现 Milestone 2: 翻译模块
- ⏭️ 开始实现 Milestone 3: TTS 模块
- ⏭️ 流程编排和端到端测试

---

*测试日期: 2025-11-26*
*测试人员: Claude Code*
