"""WhisperX ASR 处理器 - 语音识别与说话人分离

本模块提供了基于 WhisperX 的高级接口，用于：
- 自动语音识别 (Automatic Speech Recognition, ASR)
- 词级时间戳对齐 (Word-level Alignment)
- 说话人分离 (Speaker Diarization)

主要优化:
- 避免重复加载音频文件（性能提升 30-60 秒）
- 支持音频数据复用
- 详细的中文注释

使用示例:
    handler = WhisperXHandler()
    result = handler.process_full_pipeline("podcast.mp3")
    print(f"检测到 {result.speaker_count} 个说话人")
"""

from pathlib import Path
from typing import Any

import torch
import whisperx
from whisperx.diarize import DiarizationPipeline  # whisperx 3.7+ API
from loguru import logger
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from podtrans.asr.schemas import ASRResult, Segment, Word
from podtrans.config import get_settings


class WhisperXHandler:
    """WhisperX ASR 处理器 - 支持说话人分离的语音识别

    本类封装了 WhisperX 的完整 ASR 流程，包括：
    1. 语音转文字 (transcribe)
    2. 词级对齐 (align)
    3. 说话人分离 (diarize)
    4. 说话人标签分配 (assign_speakers)

    设计特点:
    - 懒加载模型（首次使用时才加载）
    - 模型复用（避免重复加载）
    - 音频数据复用（避免重复读取文件）
    - 详细的进度显示和日志记录
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        hf_token: str | None = None,
    ):
        """初始化 WhisperX 处理器

        Args:
            model_name: Whisper 模型名称，可选值：
                - tiny: 最快但精度最低
                - base: 平衡速度和精度
                - small: 较好精度
                - medium: 推荐使用，精度较高
                - large-v2: 高精度
                - large-v3: 最高精度（最慢）
            device: 计算设备，可选值：
                - cuda: NVIDIA GPU (推荐，最快)
                - mps: Apple Silicon GPU (不推荐，兼容性差)
                - cpu: CPU (慢但兼容性好)
            compute_type: 计算精度，可选值：
                - int8: 8位整数（CPU推荐）
                - float16: 16位浮点（GPU推荐）
                - float32: 32位浮点（精度最高但最慢）
            hf_token: HuggingFace API Token
                - 用于下载 pyannote.audio 说话人分离模型
                - 需要在 HuggingFace 接受模型使用协议
                - 如果不提供，将跳过说话人分离

        注意:
            - Apple Silicon (M1/M2/M3/M4) 建议使用 device='cpu', compute_type='int8'
            - MPS 设备不稳定，会自动回退到 CPU
        """
        # 从配置文件加载默认设置
        settings = get_settings()

        # 设置模型参数（优先使用传入参数，否则使用配置文件）
        self.model_name = model_name or settings.whisper_model
        self.device = device or settings.device
        self.compute_type = compute_type or settings.compute_type
        self.hf_token = hf_token or settings.hf_token

        # === Apple Silicon MPS 兼容性处理 ===
        # MPS 不支持 int8 精度，需要降级到 float16
        if self.device == "mps" and self.compute_type == "int8":
            logger.warning(
                "MPS 设备不支持 int8 精度，自动切换到 float16。"
                "建议使用 device='cpu' 以获得更好的兼容性。"
            )
            self.compute_type = "float16"

        # 检查 MPS 是否可用，不可用则回退到 CPU
        if self.device == "mps" and not torch.backends.mps.is_available():
            logger.warning(
                "MPS 设备不可用（可能是 PyTorch 版本不支持），"
                "自动切换到 CPU。"
            )
            self.device = "cpu"

        # === 模型实例（懒加载，首次使用时才加载）===
        self.model: Any = None  # Whisper ASR 模型
        self.align_model: Any = None  # 词级对齐模型
        self.align_metadata: Any = None  # 对齐模型元数据
        self.diarize_model: Any = None  # 说话人分离模型

        # 记录初始化信息
        logger.info(
            f"WhisperX 处理器已初始化: "
            f"model={self.model_name}, "
            f"device={self.device}, "
            f"compute_type={self.compute_type}"
        )

    def load_model(self) -> None:
        """加载 Whisper ASR 模型

        说明:
            - 采用懒加载策略，仅在需要时加载
            - 模型会缓存在内存中，避免重复加载
            - 首次加载较慢（需要下载模型文件）
            - 后续使用会直接从本地缓存加载

        模型大小参考（磁盘空间）:
            - tiny: ~75 MB
            - base: ~150 MB
            - small: ~500 MB
            - medium: ~1.5 GB (推荐)
            - large-v2: ~3 GB
            - large-v3: ~3 GB

        Raises:
            Exception: 模型加载失败（网络问题、磁盘空间不足等）
        """
        logger.info(f"正在加载 Whisper 模型: {self.model_name}")

        try:
            # 调用 WhisperX 的模型加载函数
            self.model = whisperx.load_model(
                self.model_name,
                self.device,
                compute_type=self.compute_type,
            )
            logger.info("Whisper 模型加载成功")
        except Exception as e:
            logger.error(f"Whisper 模型加载失败: {e}")
            logger.error(
                "可能的原因:\n"
                "1. 网络连接问题（首次需要下载模型）\n"
                "2. 磁盘空间不足\n"
                "3. PyTorch 或 WhisperX 版本不兼容\n"
                "4. 设备不支持指定的 compute_type"
            )
            raise

    def transcribe(
        self,
        audio_path: Path | str | None = None,
        audio: Any | None = None,
        language: str | None = None,
        batch_size: int | None = None,
    ) -> tuple[dict[str, Any], Any]:
        """转录音频文件为文字

        这是 ASR 流程的第一步，将音频转换为文字段落。

        Args:
            audio_path: 音频文件路径（与 audio 二选一）
            audio: 已加载的音频数组（与 audio_path 二选一）
                - 如果提供，将避免重复加载音频文件
                - 来自 whisperx.load_audio()
            language: 语言代码（可选）
                - 'en': 英语
                - 'zh': 中文
                - None: 自动检测（推荐）
            batch_size: 批处理大小
                - 更大的值：处理更快，但占用更多内存
                - 推荐值：16 (默认)

        Returns:
            tuple: (转录结果字典, 音频数组)
                - 转录结果包含 segments (段落) 和 language (检测到的语言)
                - 音频数组可供后续步骤复用，避免重复加载

        转录结果格式:
            {
                "segments": [
                    {
                        "start": 0.5,
                        "end": 3.2,
                        "text": "Welcome to the podcast."
                    },
                    ...
                ],
                "language": "en"
            }

        性能优化:
            - 如果后续还需要使用音频数据（如对齐、说话人分离），
              建议传入 audio 参数而非 audio_path，避免重复加载

        Raises:
            FileNotFoundError: 音频文件不存在
            Exception: 转录失败（音频格式不支持、模型错误等）
        """
        # 获取配置
        settings = get_settings()
        batch_size = batch_size or settings.asr_batch_size

        # === 音频加载逻辑 ===
        # 优先使用已加载的音频数组，避免重复加载文件
        if audio is None:
            if audio_path is None:
                raise ValueError("必须提供 audio_path 或 audio 参数之一")

            audio_path = Path(audio_path)
            logger.info(f"正在转录音频: {audio_path}")

            # 检查文件是否存在
            if not audio_path.exists():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")

            # 加载音频文件（16kHz 采样率）
            audio = whisperx.load_audio(str(audio_path))
            logger.debug(f"音频已加载，时长: {len(audio) / 16000:.2f} 秒")
        else:
            logger.info("使用已加载的音频数组进行转录（避免重复加载）")

        # === 模型加载检查 ===
        # 如果模型未加载，先加载模型（懒加载）
        if self.model is None:
            self.load_model()

        try:
            # === 执行转录 ===
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("正在转录...", total=None)

                # 调用 Whisper 模型进行转录
                result = self.model.transcribe(
                    audio,
                    batch_size=batch_size,
                    language=language,
                )

                progress.update(task, completed=True)

            # 获取检测到的语言
            detected_lang = result.get("language", "unknown")
            logger.info(f"转录完成，检测到的语言: {detected_lang}")

            # 返回转录结果和音频数据（供后续步骤复用）
            return result, audio

        except Exception as e:
            logger.error(f"转录失败: {e}")
            logger.error(
                "可能的原因:\n"
                "1. 音频格式不支持（尝试转换为 mp3/wav）\n"
                "2. 音频文件损坏\n"
                "3. 内存不足（尝试减小 batch_size）\n"
                "4. 模型问题"
            )
            raise

    def align(
        self,
        segments: list[dict[str, Any]],
        audio: Any,
        language: str,
    ) -> dict[str, Any]:
        """对齐转录结果以获取词级时间戳

        这是 ASR 流程的第二步。Whisper 初始转录只提供句子级时间戳，
        此步骤将时间戳细化到每个单词，为说话人分离提供更精确的信息。

        为什么需要词级对齐?
            1. 说话人分离需要精确的时间戳来匹配说话人
            2. 字幕制作需要逐词显示
            3. 提高时间戳的准确性

        Args:
            segments: 转录得到的段落列表（来自 transcribe() 的结果）
            audio: 音频数组（来自 whisperx.load_audio()）
                - 必须与转录使用的音频相同
            language: 语言代码（例如 'en', 'zh'）
                - 不同语言需要不同的对齐模型

        Returns:
            对齐后的结果，包含词级时间戳:
            {
                "segments": [
                    {
                        "start": 0.5,
                        "end": 3.2,
                        "text": "Welcome to the podcast.",
                        "words": [
                            {"word": "Welcome", "start": 0.5, "end": 0.8},
                            {"word": "to", "start": 0.9, "end": 1.0},
                            {"word": "the", "start": 1.1, "end": 1.2},
                            {"word": "podcast", "start": 1.3, "end": 1.8}
                        ]
                    }
                ]
            }

        性能说明:
            - 首次对齐特定语言需要下载对齐模型（~100MB）
            - 后续对齐会复用已加载的模型
            - 对齐速度通常比转录快

        Raises:
            Exception: 对齐失败（语言不支持、模型加载失败等）
        """
        logger.info("正在进行词级对齐以获取精确时间戳")

        try:
            # === 加载对齐模型 ===
            # 不同语言需要不同的对齐模型，采用懒加载策略
            if self.align_model is None:
                logger.debug(f"正在加载对齐模型，语言: {language}")
                self.align_model, self.align_metadata = whisperx.load_align_model(
                    language_code=language,
                    device=self.device,
                )

            # === 执行对齐 ===
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("正在对齐词级时间戳...", total=None)

                # 调用 WhisperX 的对齐函数
                result = whisperx.align(
                    segments,
                    self.align_model,
                    self.align_metadata,
                    audio,
                    self.device,
                    return_char_alignments=False,  # 不返回字符级对齐（太细粒度）
                )

                progress.update(task, completed=True)

            logger.info("词级对齐完成")
            return result

        except Exception as e:
            logger.error(f"对齐失败: {e}")
            logger.error(
                "可能的原因:\n"
                "1. 该语言不支持词级对齐\n"
                "2. 对齐模型下载失败\n"
                "3. 音频与转录结果不匹配"
            )
            raise

    def diarize(
        self,
        audio_path: Path | str | None = None,
        audio: Any | None = None,
    ) -> Any:
        """执行说话人分离（识别音频中的不同说话人）

        这是 ASR 流程的第三步。通过分析音频的声纹特征，
        识别音频中有多少个不同的说话人，并为每个时间段标记说话人。

        说话人分离原理:
            1. 提取声纹特征（每个人的声音有独特的特征）
            2. 聚类分析（将相似的声音归为同一个说话人）
            3. 输出时间段 -> 说话人的映射

        Args:
            audio_path: 音频文件路径（与 audio 二选一）
            audio: 已加载的音频数组（与 audio_path 二选一）
                - 如果提供，将避免重复加载音频文件

        Returns:
            说话人分离结果（时间段列表）:
                [
                    (0.5, 3.2, "SPEAKER_00"),   # 0.5-3.2秒是说话人0
                    (3.5, 8.1, "SPEAKER_01"),   # 3.5-8.1秒是说话人1
                    (8.2, 12.5, "SPEAKER_00"),  # 8.2-12.5秒又是说话人0
                    ...
                ]

            如果失败或跳过，返回 None

        依赖条件:
            - 需要提供 HF_TOKEN（HuggingFace token）
            - 需要接受 pyannote.audio 模型的使用协议
            - 访问 https://huggingface.co/pyannote/speaker-diarization-3.1

        性能说明:
            - 首次使用需要下载 pyannote.audio 模型（~200MB）
            - 说话人分离是最耗时的步骤（通常占总时间的 30-40%）
            - 音频越长，处理时间越长

        注意:
            - 如果没有 HF_TOKEN，将跳过说话人分离
            - 说话人分离失败不会影响转录，只是无法区分说话人
        """
        logger.info("正在执行说话人分离")

        # === 检查 HuggingFace Token ===
        if not self.hf_token:
            logger.warning(
                "未提供 HuggingFace token，跳过说话人分离。\n"
                "如需启用说话人分离，请:\n"
                "1. 访问 https://huggingface.co/settings/tokens 创建 token\n"
                "2. 访问 https://huggingface.co/pyannote/speaker-diarization-3.1 接受使用协议\n"
                "3. 在 .env 文件中设置 HF_TOKEN=your_token"
            )
            return None

        try:
            # === 加载说话人分离模型 ===
            if self.diarize_model is None:
                logger.debug("正在加载说话人分离模型（首次加载较慢）")
                self.diarize_model = DiarizationPipeline(
                    use_auth_token=self.hf_token,
                    device=self.device,
                )

            # === 音频加载逻辑 ===
            # 优先使用已加载的音频数组，避免重复加载文件
            if audio is None:
                if audio_path is None:
                    raise ValueError("必须提供 audio_path 或 audio 参数之一")

                audio_path = Path(audio_path)
                logger.debug(f"加载音频用于说话人分离: {audio_path}")
                audio = whisperx.load_audio(str(audio_path))
            else:
                logger.debug("使用已加载的音频数组进行说话人分离（避免重复加载）")

            # === 执行说话人分离 ===
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("正在识别说话人...", total=None)

                # 调用 pyannote.audio 进行说话人分离
                diarize_segments = self.diarize_model(audio)

                progress.update(task, completed=True)

            logger.info("说话人分离完成")
            return diarize_segments

        except Exception as e:
            logger.error(f"说话人分离失败: {e}")
            logger.warning(
                "可能的原因:\n"
                "1. HF_TOKEN 无效或已过期\n"
                "2. 未接受 pyannote 模型使用协议\n"
                "3. 网络连接问题\n"
                "4. 内存不足\n"
                "\n继续处理，但结果将不包含说话人标签"
            )
            return None

    def assign_speakers(
        self,
        diarize_segments: Any,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """将说话人标签分配到转录结果

        这是 ASR 流程的第四步。将说话人分离结果（时间段 -> 说话人）
        与转录结果（时间段 -> 文字）结合，为每个词和句子添加说话人标签。

        分配逻辑:
            1. 根据时间戳将每个词匹配到对应的说话人时间段
            2. 一个句子的说话人 = 该句子中多数词的说话人
            3. 处理时间重叠和边界情况

        Args:
            diarize_segments: 说话人分离结果（来自 diarize()）
            result: 对齐后的转录结果（来自 align()）

        Returns:
            添加了说话人标签的结果:
            {
                "segments": [
                    {
                        "start": 0.5,
                        "end": 3.2,
                        "text": "Welcome to the podcast.",
                        "speaker": "SPEAKER_00",  # ← 添加了说话人
                        "words": [
                            {
                                "word": "Welcome",
                                "start": 0.5,
                                "end": 0.8,
                                "speaker": "SPEAKER_00"  # ← 每个词也有说话人
                            },
                            ...
                        ]
                    }
                ]
            }

        注意:
            - 如果 diarize_segments 为 None，将跳过标签分配
            - 标签分配失败不会抛出异常，而是返回无标签的结果
        """
        # 检查是否有说话人分离数据
        if diarize_segments is None:
            logger.info("无说话人分离数据，跳过标签分配")
            return result

        logger.info("正在为转录结果分配说话人标签")

        try:
            # 调用 WhisperX 的标签分配函数
            # 该函数会根据时间戳自动匹配说话人和词
            result = whisperx.assign_word_speakers(
                diarize_segments,
                result,
            )
            logger.info("说话人标签分配完成")
            return result

        except Exception as e:
            logger.error(f"说话人标签分配失败: {e}")
            logger.warning(
                "可能的原因:\n"
                "1. 时间戳格式不匹配\n"
                "2. 数据结构异常\n"
                "\n返回无说话人标签的结果"
            )
            return result

    def process_full_pipeline(
        self,
        audio_path: Path | str,
        language: str | None = None,
        enable_diarization: bool = True,
    ) -> ASRResult:
        """执行完整的 ASR 流程（推荐使用）

        这是最常用的接口，自动执行所有 ASR 步骤:
        1. 转录 (transcribe) - 音频 -> 文字
        2. 对齐 (align) - 获取词级时间戳
        3. 说话人分离 (diarize) - 识别说话人
        4. 标签分配 (assign_speakers) - 添加说话人标签
        5. 数据转换 - 转为标准化的 ASRResult 模型

        性能优化:
            - ✅ 音频文件只加载一次（相比之前节省 30-60 秒）
            - ✅ 音频数组在各步骤间复用
            - ✅ 模型懒加载和缓存

        Args:
            audio_path: 音频文件路径（支持 mp3, wav, flac, m4a 等格式）
            language: 语言代码（可选）
                - None: 自动检测（推荐）
                - 'en': 英语
                - 'zh': 中文
            enable_diarization: 是否启用说话人分离
                - True: 启用（默认，需要 HF_TOKEN）
                - False: 禁用（更快，但无说话人标签）

        Returns:
            ASRResult: 标准化的 ASR 结果对象，包含:
                - segments: 所有句子段落（带说话人标签和词级时间戳）
                - language: 检测到的语言
                - audio_duration: 音频时长（秒）
                - model_name: 使用的模型名称
                - total_segments: 段落总数
                - speaker_count: 说话人数量
                - unique_speakers: 唯一说话人集合

        使用示例:
            # 基础用法
            handler = WhisperXHandler()
            result = handler.process_full_pipeline("podcast.mp3")
            print(f"段落数: {result.total_segments}")
            print(f"说话人数: {result.speaker_count}")

            # 指定语言（跳过自动检测，更快）
            result = handler.process_full_pipeline("podcast.mp3", language="en")

            # 禁用说话人分离（更快）
            result = handler.process_full_pipeline("podcast.mp3", enable_diarization=False)

        处理时间参考（13分钟音频，M4 CPU）:
            - tiny 模型: ~5 分钟
            - medium 模型: ~12 分钟（推荐）
            - large-v3 模型: ~20 分钟

        Raises:
            FileNotFoundError: 音频文件不存在
            Exception: 处理过程中的各种错误
        """
        audio_path = Path(audio_path)
        logger.info(f"开始完整 ASR 流程: {audio_path}")

        # === Step 1: 转录（音频 -> 文字）===
        # 返回转录结果和音频数组（注意：音频数组会被复用）
        result, audio = self.transcribe(audio_path=audio_path, language=language)
        detected_language = result["language"]
        segments_raw = result["segments"]

        logger.info(
            f"Step 1 完成 - 转录: {len(segments_raw)} 个段落, "
            f"语言: {detected_language}"
        )

        # === Step 2: 对齐（获取词级时间戳）===
        # 复用上一步加载的 audio 数组，避免重复加载文件
        result = self.align(segments_raw, audio, detected_language)

        logger.info("Step 2 完成 - 词级对齐")

        # === Step 3: 说话人分离 + 标签分配 ===
        if enable_diarization and self.hf_token:
            # 复用同一个 audio 数组进行说话人分离
            diarize_segments = self.diarize(audio=audio)
            result = self.assign_speakers(diarize_segments, result)
            logger.info("Step 3 完成 - 说话人分离和标签分配")
        else:
            logger.info("跳过说话人分离（enable_diarization=False 或无 HF_TOKEN）")

        # === Step 4: 数据转换（转为标准化的 Pydantic 模型）===
        asr_result = self._convert_to_asr_result(
            result,
            detected_language,
            len(audio) / 16000,  # 音频时长（秒），16kHz 采样率
        )

        # 输出完成信息
        logger.info(
            f"ASR 流程完成! "
            f"段落数: {asr_result.total_segments}, "
            f"说话人数: {asr_result.speaker_count}"
        )

        return asr_result

    def _convert_to_asr_result(
        self,
        whisperx_result: dict[str, Any],
        language: str,
        duration: float,
    ) -> ASRResult:
        """将 WhisperX 原始结果转换为标准化的 ASRResult 模型

        内部方法，用于数据格式转换和验证。

        转换流程:
            1. 提取每个段落的原始数据
            2. 提取每个词的原始数据
            3. 使用 Pydantic 模型进行验证
            4. 返回类型安全的 ASRResult 对象

        Args:
            whisperx_result: WhisperX 原始输出（字典格式）
            language: 检测到的语言代码
            duration: 音频时长（秒）

        Returns:
            ASRResult: 经过验证的标准化结果对象

        优势:
            - 类型安全（TypeScript 般的类型检查）
            - 数据验证（自动校验时间戳、文本等）
            - 提供便捷方法（total_segments, speaker_count 等）
            - 易于序列化（可直接转 JSON）
        """
        segments = []

        # 遍历每个原始段落
        for seg_raw in whisperx_result.get("segments", []):
            # === 提取词级数据 ===
            words = []
            for word_raw in seg_raw.get("words", []):
                # 使用 Pydantic 模型创建 Word 对象（自动验证数据）
                word = Word(
                    word=word_raw.get("word", ""),
                    start=word_raw.get("start", 0.0),
                    end=word_raw.get("end", 0.0),
                    score=word_raw.get("score"),  # 置信度（可选）
                    speaker=word_raw.get("speaker"),  # 说话人标签（可选）
                )
                words.append(word)

            # === 创建段落对象 ===
            segment = Segment(
                start=seg_raw.get("start", 0.0),
                end=seg_raw.get("end", 0.0),
                text=seg_raw.get("text", ""),
                speaker=seg_raw.get("speaker"),  # 段落级别的说话人标签
                words=words,
            )
            segments.append(segment)

        # === 创建完整的 ASRResult 对象 ===
        asr_result = ASRResult(
            segments=segments,
            language=language,
            audio_duration=duration,
            model_name=self.model_name,
        )

        return asr_result
