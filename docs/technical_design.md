# 播客翻译项目 - 完整技术方案 (2024-2025)

> 文档版本：v1.0
> 创建日期：2025-11-26
> 项目名称：PodTrans

---

## 目录

1. [技术选型建议](#一技术选型建议)
2. [核心技术集成方案](#二核心技术集成方案)
3. [项目结构设计](#三项目结构设计)
4. [核心依赖清单](#四核心依赖清单)
5. [数据格式定义](#五数据格式定义)
6. [分阶段开发计划](#六分阶段开发计划)
7. [开发注意事项](#七开发注意事项)
8. [常见问题](#八常见问题)

---

## 一、技术选型建议

### 1.1 Python 项目管理

**推荐：uv**

**选择理由：**
- **性能卓越**：基于 Rust 实现，依赖解析和安装速度比 Poetry 快 10-100 倍
- **功能完整**：完全替代 pyenv + pip + venv，支持 Python 版本管理
- **2024-2025 趋势**：最新工具，积极迭代，社区增长迅速
- **简化工作流**：一个工具解决所有问题，减少工具链复杂度
- **离线缓存**：智能缓存机制，离线也能秒装依赖

**替代方案对比：**
- Poetry：成熟稳定，但慢；适合发布库到 PyPI
- PDM：符合标准，但生态较小；适合 Node.js 风格开发

### 1.2 Python 版本

**推荐：Python 3.12**

**选择理由：**
- **综合性能提升**：相比 3.11，在异步操作、typing 和生成器方面有显著改进（1.5-3x）
- **更好的错误提示**：改进的错误信息，提升开发体验
- **长期支持**：3.12 将支持到 2028 年 10 月
- **AI/ML 生态兼容**：主流深度学习库已全面支持

### 1.3 代码质量工具

**linter + formatter：Ruff**

**选择理由：**
- **速度惊人**：比 Black + Flake8 快 150-200 倍
- **一体化方案**：替代 Black、isort、Flake8、pyupgrade、autoflake
- **兼容 Black**：>99.9% 格式兼容，平滑迁移
- **800+ 规则**：覆盖所有主流 linter
- **大厂采用**：FastAPI、pandas、pydantic 都在用

**配置示例：**
```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "B", "Q"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

**类型检查：mypy（strict mode）**

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### 1.4 项目结构

**推荐：src layout（PyPA 官方建议）**

**选择理由：**
- **防止意外导入**：确保测试运行的是安装版本，而非开发目录
- **清晰分离**：源码、测试、文档分离
- **2024 标准**：现代 Python 项目的主流选择
- **打包友好**：与 pyproject.toml 配合完美

### 1.5 配置管理

**推荐：Pydantic Settings + TOML**

**选择理由：**
- **类型安全**：基于 Pydantic，自动验证和类型转换
- **多源配置**：支持 .env、TOML、环境变量
- **简洁直观**：与 Pydantic 模型无缝集成
- **文档自动生成**：配置即文档

### 1.6 日志方案

**推荐：Loguru**

**选择理由：**
- **开箱即用**：零配置开始使用
- **JSON 支持**：原生支持结构化日志
- **性能优良**：异步日志，低开销
- **自动轮转**：自动管理日志文件大小
- **彩色输出**：CLI 体验友好

**配置示例：**
```python
from loguru import logger

logger.add(
    "logs/podtrans_{time}.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO",
    format="{time} | {level} | {message}",
    serialize=True  # JSON 格式
)
```

### 1.7 CLI 框架

**推荐：Typer**

**选择理由：**
- **基于类型提示**：现代 Pythonic 风格
- **自动生成帮助**：基于 docstring 和类型
- **底层是 Click**：继承 Click 的所有强大功能
- **自动补全**：原生支持 shell 自动补全
- **简洁代码**：比 argparse 和 Click 都简洁

**示例：**
```python
import typer

app = typer.Typer()

@app.command()
def transcribe(
    audio_file: Path,
    output_dir: Path = Path("./output"),
    language: str = "en"
):
    """转录音频文件"""
    pass
```

### 1.8 测试框架

**推荐：pytest**

**选择理由：**
- **事实标准**：Python 测试的行业标准
- **简洁语法**：assert 即可，无需特殊方法
- **丰富插件**：pytest-cov、pytest-mock 等
- **fixture 机制**：灵活的测试依赖管理

### 1.9 进度条

**推荐：Rich**

**选择理由：**
- **美观现代**：彩色输出，视觉效果好
- **高度可定制**：颜色、宽度、字符可配置
- **多进度条**：支持同时显示多个进度
- **附加功能**：表格、语法高亮、Markdown 渲染

---

## 二、核心技术集成方案

### 2.1 WhisperX 集成

**安装：**
```bash
# GPU 版本（推荐）
pip install whisperx

# CPU 版本
pip install whisperx --extra-index-url https://download.pytorch.org/whl/cpu
```

**依赖：**
- FFmpeg（系统级）
- CUDA Toolkit 12.8（GPU 加速）
- HuggingFace Token（说话人分离）

**API 使用：**
```python
import whisperx

# 1. 加载模型
device = "cuda"  # 或 "cpu"、"mps"（Mac）
model = whisperx.load_model("large-v2", device, compute_type="float16")

# 2. 转录
audio = whisperx.load_audio("podcast.mp3")
result = model.transcribe(audio, batch_size=16)

# 3. 对齐（词级时间戳）
model_a, metadata = whisperx.load_align_model(
    language_code=result["language"],
    device=device
)
result = whisperx.align(result["segments"], model_a, metadata, audio, device)

# 4. 说话人分离
from whisperx.diarize import DiarizationPipeline
diarize_model = DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
diarize_segments = diarize_model(audio)
result = whisperx.assign_word_speakers(diarize_segments, result)
```

**输出格式：**
```json
{
  "segments": [
    {
      "start": 0.5,
      "end": 3.2,
      "text": "Hello, welcome to the podcast.",
      "speaker": "SPEAKER_00",
      "words": [
        {"word": "Hello", "start": 0.5, "end": 0.8, "speaker": "SPEAKER_00"}
      ]
    }
  ],
  "language": "en"
}
```

**HuggingFace 配置：**
1. 注册并生成 token：https://huggingface.co/settings/tokens
2. 接受模型协议：
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)

**GPU 支持：**
- CUDA：需要 <8GB 显存（large-v2 + beam_size=5）
- MPS（Mac）：支持，性能略低于 CUDA
- CPU：可用，但速度慢 5-10 倍

### 2.2 pyannote.audio 集成

**说明：**
WhisperX 内置了 pyannote.audio，无需单独集成。只需：
1. 提供 HuggingFace token
2. 接受模型使用协议

**注意事项：**
- 使用 Speaker-Diarization-3.1（不要用 3.0，有性能问题）
- 说话人 ID 为 `SPEAKER_00`、`SPEAKER_01` 等
- 准确度取决于音频质量和说话人声音差异

### 2.3 SoulX-Podcast 集成

**安装：**
```bash
git clone https://github.com/Soul-AILab/SoulX-Podcast.git
cd SoulX-Podcast
pip install -r requirements.txt

# 下载模型（二选一）
# 1. 基础模型
huggingface-cli download Soul-AILab/SoulX-Podcast-1.7B --local-dir pretrained_models/SoulX-Podcast-1.7B

# 2. 方言模型（支持川话、河南话、粤语）
huggingface-cli download Soul-AILab/SoulX-Podcast-1.7B-dialect --local-dir pretrained_models/SoulX-Podcast-1.7B-dialect
```

**脚本格式：**
```text
[SPEAKER_00] 大家好，欢迎来到我们的播客。<|laughter|>
[SPEAKER_01] 你好！很高兴能来这里。
[SPEAKER_00] 今天我们聊聊人工智能。<|sigh|>
```

**支持的副语言标签：**
- `<|laughter|>`：笑声
- `<|sigh|>`：叹气
- `<|breathing|>`：呼吸声
- `<|coughing|>`：咳嗽
- `<|throat_clearing|>`：清嗓子

**多说话人支持：**
- 零样本声音克隆（zero-shot voice cloning）
- 需要提供参考音频（每个说话人 3-10 秒）
- 支持跨方言克隆

**注意事项：**
- 需要 Linux 环境（Docker 或 WSL）
- 建议使用 GPU（模型 1.7B 参数）
- 官方文档不完整，需要阅读源码理解 API

### 2.4 LLM 翻译方案

**推荐模型：Claude 3.7 Sonnet**

**选择理由：**
- **成本低**：$3/M input + $15/M output（比 GPT-4 便宜 50%）
- **质量高**：多语言能力强，中文自然
- **prompt caching**：重复内容可减少 90% 成本
- **上下文长度**：200K tokens，足够长播客

**Prompt 设计（播客风格翻译）：**
```python
TRANSLATION_PROMPT = """
你是一位专业的播客翻译专家。请将以下英文播客对话翻译成中文，要求：

1. **自然口语化**：使用日常对话的表达方式，避免书面语
2. **保留语气词**：如 "嗯"、"啊"、"哦" 等，增加真实感
3. **保持节奏**：句子长短适中，符合中文播客习惯
4. **文化适配**：将文化特定内容本地化（如单位、习语）
5. **保留停顿标记**：保持 <|laughter|>、<|sigh|> 等标签
6. **保持说话人标记**：[SPEAKER_XX] 格式不变

原文：
{original_text}

翻译：
"""
```

**成本估算（60 分钟播客）：**
- 英文转录：~15,000 词 ≈ 20,000 tokens
- 输入成本：$0.06
- 输出成本（假设 1:1.2 比例）：$0.36
- **总计：约 $0.42/集**

使用 prompt caching 优化后：**约 $0.10-0.20/集**

---

## 三、项目结构设计

```
podtrans/
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions CI
├── .vscode/
│   └── settings.json                 # VSCode 配置
├── docs/
│   ├── technical_design.md           # 技术设计文档（本文档）
│   ├── architecture.md               # 架构设计文档
│   ├── api.md                        # API 文档
│   └── deployment.md                 # 部署指南
├── logs/                             # 日志目录（.gitignore）
├── data/                             # 数据目录（.gitignore）
│   ├── input/                        # 原始音频
│   ├── output/                       # 处理结果
│   └── cache/                        # 缓存
├── src/
│   └── podtrans/
│       ├── __init__.py
│       ├── __main__.py               # CLI 入口
│       ├── cli.py                    # CLI 命令定义
│       ├── config.py                 # 配置管理
│       ├── models.py                 # Pydantic 数据模型
│       ├── exceptions.py             # 自定义异常
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── audio.py              # 音频处理工具
│       │   ├── file.py               # 文件操作工具
│       │   └── logger.py             # 日志配置
│       ├── asr/
│       │   ├── __init__.py
│       │   ├── whisperx.py           # WhisperX 封装
│       │   └── schemas.py            # ASR 数据模型
│       ├── translation/
│       │   ├── __init__.py
│       │   ├── claude.py             # Claude API 封装
│       │   ├── prompt.py             # Prompt 模板
│       │   └── schemas.py            # 翻译数据模型
│       ├── tts/
│       │   ├── __init__.py
│       │   ├── soulx.py              # SoulX-Podcast 封装
│       │   ├── script.py             # 脚本生成
│       │   └── schemas.py            # TTS 数据模型
│       └── pipeline/
│           ├── __init__.py
│           ├── orchestrator.py       # 流程编排
│           └── stages.py             # 各阶段实现
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # pytest 配置和 fixtures
│   ├── fixtures/
│   │   ├── audio/                    # 测试音频文件
│   │   └── data/                     # 测试数据
│   ├── unit/
│   │   ├── test_asr.py
│   │   ├── test_translation.py
│   │   └── test_tts.py
│   ├── integration/
│   │   └── test_pipeline.py
│   └── e2e/
│       └── test_full_workflow.py
├── .env.example                      # 环境变量示例
├── .gitignore
├── .python-version                   # pyenv/uv 版本指定
├── LICENSE
├── README.md
├── pyproject.toml                    # 项目配置（uv + ruff + mypy）
└── uv.lock                           # 锁定依赖版本
```

---

## 四、核心依赖清单

### 4.1 生产依赖

| 包名 | 版本范围 | 作用 |
|------|---------|------|
| typer[all] | >=0.15.0 | CLI 框架，基于类型提示 |
| pydantic | >=2.10.0 | 数据验证和序列化 |
| pydantic-settings | >=2.7.0 | 配置管理（支持 .env、TOML） |
| loguru | >=0.7.3 | 日志（支持 JSON、自动轮转） |
| rich | >=13.9.0 | 进度条、表格、美化输出 |
| whisperx | >=3.1.1 | 语音识别 + 词级对齐 + 说话人分离 |
| pyannote.audio | >=3.1.1 | 说话人分离（WhisperX 依赖） |
| torch | >=2.0.0 | 深度学习框架（WhisperX 依赖） |
| anthropic | >=0.40.0 | Claude API 客户端 |
| pydub | >=0.25.1 | 音频格式转换 |
| librosa | >=0.10.0 | 音频特征提取 |
| orjson | >=3.10.0 | 快速 JSON 解析 |
| python-dotenv | >=1.0.0 | 加载 .env 文件 |

### 4.2 开发依赖

| 包名 | 版本范围 | 作用 |
|------|---------|------|
| pytest | >=8.3.0 | 测试框架 |
| pytest-cov | >=6.0.0 | 测试覆盖率 |
| pytest-mock | >=3.14.0 | Mock 工具 |
| ruff | >=0.8.0 | Linter + Formatter |
| mypy | >=1.13.0 | 类型检查 |

---

## 五、数据格式定义

### 5.1 ASR 输出格式

```python
class Word(BaseModel):
    """单词级时间戳"""
    word: str
    start: float = Field(ge=0, description="开始时间（秒）")
    end: float = Field(ge=0, description="结束时间（秒）")
    score: Optional[float] = Field(None, ge=0, le=1, description="置信度")
    speaker: Optional[str] = Field(None, description="说话人 ID")

class Segment(BaseModel):
    """句子级片段"""
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    speaker: Optional[str] = None
    words: List[Word] = Field(default_factory=list)

class ASRResult(BaseModel):
    """完整 ASR 结果"""
    segments: List[Segment]
    language: str = Field(description="检测到的语言代码，如 'en'")
    audio_duration: float = Field(ge=0, description="音频总时长（秒）")
    model_name: str = Field(description="使用的模型名称")
```

**存储位置：** `data/output/{audio_name}/asr_result.json`

### 5.2 翻译输出格式

```python
class TranslatedSegment(BaseModel):
    """翻译后的片段"""
    original_text: str
    translated_text: str
    start: float
    end: float
    speaker: Optional[str] = None

class TranslationResult(BaseModel):
    """翻译结果"""
    segments: List[TranslatedSegment]
    source_language: str = Field(description="源语言")
    target_language: str = Field(description="目标语言")
    model_name: str = Field(description="使用的翻译模型")
    total_tokens: Optional[int] = Field(None, description="消耗的总 tokens")
    cost_usd: Optional[float] = Field(None, description="成本（美元）")
```

**存储位置：** `data/output/{audio_name}/translation_result.json`

### 5.3 TTS 脚本格式

```python
class TTSLine(BaseModel):
    """TTS 单行脚本"""
    speaker_id: str = Field(description="说话人 ID，如 SPEAKER_00")
    text: str = Field(description="包含副语言标签的文本")
    start: float
    end: float

class TTSScript(BaseModel):
    """TTS 完整脚本"""
    lines: List[TTSLine]
    speakers: dict[str, dict] = Field(
        description="说话人配置，{speaker_id: {voice_params...}}"
    )

    def to_soulx_format(self) -> str:
        """转换为 SoulX-Podcast 格式"""
        script_lines = []
        for line in self.lines:
            script_lines.append(f"[{line.speaker_id}] {line.text}")
        return "\n".join(script_lines)
```

**存储位置：** `data/output/{audio_name}/tts_script.txt`

---

## 六、分阶段开发计划

### Milestone 1: 项目骨架 + ASR 模块（第 1-2 周）

**目标：** 搭建完整的项目结构，实现 ASR 功能并完成单元测试。

#### 任务清单：

**1.1 项目初始化**
- [ ] 创建目录结构（按照 src layout）
- [ ] 初始化 uv 项目：`uv init --name podtrans`
- [ ] 配置 `pyproject.toml`（依赖、工具配置）
- [ ] 创建 `.env.example`
- [ ] 编写 `README.md`（项目介绍、安装指南）
- [ ] 配置 `.gitignore`

**1.2 配置管理**
- [ ] 实现 `src/podtrans/config.py`（Pydantic Settings）
- [ ] 定义配置项：HuggingFace Token、输出目录、日志级别、模型路径
- [ ] 支持 `.env` 和环境变量

**1.3 日志系统**
- [ ] 实现 `src/podtrans/utils/logger.py`
- [ ] 配置 Loguru：控制台输出、文件输出（JSON）、自动轮转

**1.4 数据模型**
- [ ] 实现 `src/podtrans/models.py`（通用模型）
- [ ] 实现 `src/podtrans/asr/schemas.py`（Word、Segment、ASRResult）

**1.5 ASR 模块**
- [ ] 实现 `src/podtrans/asr/whisperx.py`
- [ ] 功能：`load_model()`、`transcribe()`、`align()`、`diarize()`
- [ ] 支持 GPU/CPU 自动检测，添加进度条

**1.6 CLI（ASR 部分）**
- [ ] 实现 `src/podtrans/cli.py`
- [ ] 定义 `transcribe` 命令：`podtrans transcribe --audio podcast.mp3`

**1.7 单元测试**
- [ ] 创建 `tests/conftest.py`
- [ ] 实现 `tests/unit/test_asr.py`
- [ ] 确保覆盖率 >80%

**1.8 文档**
- [ ] 编写 `docs/architecture.md`
- [ ] 编写 `docs/api.md`（ASR API）
- [ ] 更新 `README.md`

**里程碑交付：**
✅ 可以运行：`podtrans transcribe --audio test.mp3`，输出准确的 ASR 结果

---

### Milestone 2: 翻译模块（第 3-4 周）

**目标：** 实现 LLM 翻译功能，支持播客风格的中文翻译。

#### 任务清单：

**2.1 数据模型**
- [ ] 实现 `src/podtrans/translation/schemas.py`

**2.2 Prompt 模板**
- [ ] 实现 `src/podtrans/translation/prompt.py`
- [ ] 定义翻译 prompt 模板，支持批量翻译

**2.3 Claude API 封装**
- [ ] 实现 `src/podtrans/translation/claude.py`
- [ ] 功能：`translate_segment()`、`translate_batch()`、错误重试、成本估算

**2.4 CLI（翻译部分）**
- [ ] 添加 `translate` 命令：`podtrans translate --input asr_result.json`

**2.5 单元测试**
- [ ] 实现 `tests/unit/test_translation.py`
- [ ] Mock Claude API，测试批量翻译和成本估算

**2.6 集成测试**
- [ ] 实现 `tests/integration/test_asr_translation.py`

**2.7 文档**
- [ ] 更新 `docs/api.md`
- [ ] 编写 `docs/translation_guide.md`

**里程碑交付：**
✅ 可以运行：`podtrans translate --input asr_result.json`，输出高质量中文翻译

---

### Milestone 3: TTS 模块（第 5-6 周）

**目标：** 集成 SoulX-Podcast，生成中文播客音频。

#### 任务清单：

**3.1 数据模型**
- [ ] 实现 `src/podtrans/tts/schemas.py`

**3.2 脚本生成**
- [ ] 实现 `src/podtrans/tts/script.py`
- [ ] 功能：智能添加副语言标签、格式化为 SoulX 脚本

**3.3 SoulX-Podcast 集成**
- [ ] 下载并配置 SoulX-Podcast
- [ ] 实现 `src/podtrans/tts/soulx.py`

**3.4 CLI（TTS 部分）**
- [ ] 添加 `synthesize` 命令：`podtrans synthesize --input translation.json`

**3.5 单元测试**
- [ ] 实现 `tests/unit/test_tts.py`

**3.6 集成测试**
- [ ] 实现 `tests/integration/test_translation_tts.py`

**3.7 文档**
- [ ] 更新 `docs/api.md`
- [ ] 编写 `docs/tts_guide.md`

**里程碑交付：**
✅ 可以运行：`podtrans synthesize --input translation.json`，生成中文播客音频

---

### Milestone 4: 流程编排 + 完整测试（第 7-8 周）

**目标：** 实现完整的端到端流程，优化性能，完善测试和文档。

#### 任务清单：

**4.1 Pipeline 编排**
- [ ] 实现 `src/podtrans/pipeline/stages.py`
- [ ] 实现 `src/podtrans/pipeline/orchestrator.py`

**4.2 CLI（完整流程）**
- [ ] 添加 `run` 命令：`podtrans run --audio podcast.mp3`

**4.3 性能优化**
- [ ] 批量翻译、缓存机制、内存优化

**4.4 错误处理**
- [ ] 实现 `src/podtrans/exceptions.py`

**4.5 端到端测试**
- [ ] 实现 `tests/e2e/test_full_workflow.py`

**4.6 CI/CD**
- [ ] 创建 `.github/workflows/ci.yml`

**4.7 文档完善**
- [ ] 编写 `docs/deployment.md`
- [ ] 编写 `CONTRIBUTING.md`
- [ ] 更新 `README.md`

**里程碑交付：**
✅ 可以运行：`podtrans run --audio podcast.mp3`，一键完成完整流程

---

## 七、开发注意事项

### 7.1 环境配置

**初始化项目：**
```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建项目
mkdir podtrans && cd podtrans
uv init

# 3. 设置 Python 版本
uv python install 3.12
uv python pin 3.12

# 4. 添加依赖
uv add typer pydantic pydantic-settings loguru rich whisperx anthropic
uv add --dev pytest pytest-cov ruff mypy
```

**HuggingFace Token：**
```bash
# 1. 注册 HuggingFace：https://huggingface.co/join
# 2. 生成 token：https://huggingface.co/settings/tokens
# 3. 接受模型协议：
#    - https://huggingface.co/pyannote/segmentation-3.0
#    - https://huggingface.co/pyannote/speaker-diarization-3.1
# 4. 设置环境变量
export HF_TOKEN="hf_xxxxxxxxxxxx"
```

**Claude API Key：**
```bash
# 1. 注册 Anthropic：https://console.anthropic.com/
# 2. 生成 API key
# 3. 设置环境变量
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"
```

### 7.2 开发工作流

**代码检查：**
```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

**运行测试：**
```bash
uv run pytest
uv run pytest tests/unit/
uv run pytest --cov=src/podtrans --cov-report=html
```

**运行 CLI：**
```bash
uv run podtrans --help
uv run podtrans transcribe --audio test.mp3
```

### 7.3 Git 工作流

**分支策略：**
- `main`：稳定版本
- `develop`：开发分支
- `feature/xxx`：功能分支

**Commit 规范：**
```
feat: 添加 ASR 模块
fix: 修复翻译批量处理 bug
docs: 更新 README
test: 添加 TTS 单元测试
```

### 7.4 性能基准

**预期性能（60 分钟播客）：**

| 阶段 | 耗时（GPU） | 耗时（CPU） | 成本 |
|------|------------|------------|------|
| ASR | 5-10 分钟 | 30-60 分钟 | $0 |
| 翻译 | 2-5 分钟 | 2-5 分钟 | $0.10-0.40 |
| TTS | 10-20 分钟 | 60-120 分钟 | $0 |
| **总计** | **~20-35 分钟** | **~90-180 分钟** | **~$0.15-0.50** |

---

## 八、常见问题

### Q1: WhisperX 安装失败
**A:** 检查 CUDA 版本，确保与 PyTorch 兼容。

### Q2: pyannote 说话人分离不准确
**A:** 使用 Speaker-Diarization-3.1，确保音频质量高。

### Q3: SoulX-Podcast 集成困难
**A:** 官方文档不完整，建议阅读源码，或考虑其他 TTS 方案。

### Q4: 翻译成本太高
**A:** 使用 Claude 3.7 Sonnet，启用 prompt caching，批量翻译。

### Q5: 类型检查报错
**A:** 添加类型存根：`uv add --dev types-requests`

---

## 附录：快速开始

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 克隆项目
git clone <your-repo>
cd podtrans

# 3. 安装依赖
uv sync

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API keys

# 5. 运行示例
uv run podtrans transcribe --audio data/input/test.mp3

# 6. 运行测试
uv run pytest

# 7. 代码检查
uv run ruff check .
uv run mypy src/
```

---

**文档结束**
