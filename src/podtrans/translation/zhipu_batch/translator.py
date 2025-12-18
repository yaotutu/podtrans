"""智谱 Batch API 批量翻译器。

提供完整的批量翻译流程:
1. 构建 JSONL 请求文件
2. 上传并创建批量任务
3. 轮询任务状态
4. 下载并解析结果
"""

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from podtrans.config import get_settings
from podtrans.translation.zhipu_batch.client import (
    ZhipuBatchClient,
    ZhipuBatchClientError,
)
from podtrans.translation.zhipu_batch.schemas import (
    BatchJob,
    BatchRequest,
    BatchStatus,
    TranslatedSegment,
    TranslationSegment,
)

# 翻译系统提示词（与现有翻译模块保持一致）
TRANSLATION_SYSTEM_PROMPT = """你是一个专业的翻译助手，专门将英文播客内容翻译成中文。

翻译要求：
1. 保持原文的语气和风格
2. 使用自然流畅的中文表达
3. 专业术语保留英文或使用通用译法
4. 口语化内容保持口语风格
5. 不添加任何解释或注释

输出格式：
- 直接输出翻译结果
- 不要包含原文
- 不要添加引号或其他标记"""


class ZhipuBatchTranslator:
    """智谱 Batch API 批量翻译器。

    使用示例:
        translator = ZhipuBatchTranslator()

        # 方式1: 提交任务后手动轮询
        batch_job = translator.submit(segments, episode_id="ep001")
        status = translator.poll_status(batch_job.batch_id)
        if status.is_success:
            result = translator.fetch_results(batch_job)

        # 方式2: 完整流程（阻塞直到完成）
        result = translator.translate_and_wait(segments)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        work_dir: Path | None = None,
    ):
        """初始化翻译器。

        Args:
            api_key: 智谱 API 密钥，为空时从配置读取
            model: 翻译模型，为空时从配置读取
            work_dir: 工作目录（存放临时文件），默认为 output/zhipu_batch
        """
        settings = get_settings()

        self.api_key = api_key or settings.zhipu_api_key
        self.model = model or settings.zhipu_batch_model
        self.work_dir = work_dir or (settings.output_dir / "zhipu_batch")
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self._client: ZhipuBatchClient | None = None

    @property
    def client(self) -> ZhipuBatchClient:
        """懒加载客户端。"""
        if self._client is None:
            self._client = ZhipuBatchClient(api_key=self.api_key)
        return self._client

    def close(self):
        """关闭客户端连接。"""
        if self._client:
            self._client.close()
            self._client = None

    # ===================================
    # JSONL 文件构建
    # ===================================

    def build_request_file(
        self,
        segments: list[TranslationSegment],
        source_lang: str = "en",
        target_lang: str = "zh",
        episode_id: str | None = None,
    ) -> Path:
        """构建 JSONL 请求文件。

        Args:
            segments: 要翻译的段落列表
            source_lang: 源语言代码
            target_lang: 目标语言代码
            episode_id: 剧集 ID（用于文件命名）

        Returns:
            生成的 JSONL 文件路径
        """
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = episode_id or "batch"
        file_path = self.work_dir / f"{prefix}_{timestamp}_requests.jsonl"

        logger.info(f"构建批量请求文件: {file_path} ({len(segments)} 段)")

        requests = []
        for seg in segments:
            # 构建用户消息
            user_message = f"请将以下英文翻译成中文：\n\n{seg.text}"

            request = BatchRequest(
                custom_id=f"seg_{seg.index:04d}",  # 至少6字符: seg_0000
                body={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,  # 较低温度保证一致性
                },
            )
            requests.append(request)

        # 写入 JSONL 文件
        with open(file_path, "w", encoding="utf-8") as f:
            for req in requests:
                f.write(req.model_dump_json() + "\n")

        logger.info(f"请求文件已生成: {file_path} ({file_path.stat().st_size} bytes)")
        return file_path

    # ===================================
    # 任务提交
    # ===================================

    def submit(
        self,
        segments: list[TranslationSegment],
        source_lang: str = "en",
        target_lang: str = "zh",
        episode_id: str | None = None,
        segment_index: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> BatchJob:
        """提交批量翻译任务。

        Args:
            segments: 要翻译的段落列表
            source_lang: 源语言代码
            target_lang: 目标语言代码
            episode_id: 剧集 ID
            segment_index: 片段索引（如果是分片剧集）
            metadata: 自定义元数据

        Returns:
            BatchJob 对象，包含任务 ID 和状态
        """
        # 1. 构建请求文件
        request_file = self.build_request_file(
            segments=segments,
            source_lang=source_lang,
            target_lang=target_lang,
            episode_id=episode_id,
        )

        # 2. 上传文件
        settings = get_settings()
        file_id = self.client.upload_file(request_file)

        # 3. 创建批量任务
        task_metadata = {
            "source": "podtrans",
            "source_lang": source_lang,
            "target_lang": target_lang,
        }
        if episode_id:
            task_metadata["episode_id"] = episode_id
        if metadata:
            task_metadata.update(metadata)

        batch_id = self.client.create_batch(
            input_file_id=file_id,
            auto_delete_input=settings.zhipu_batch_auto_delete_input,
            metadata=task_metadata,
        )

        # 4. 创建本地任务记录
        job = BatchJob(
            batch_id=batch_id,
            input_file_id=file_id,
            episode_id=episode_id,
            segment_index=segment_index,
            model=self.model,
            segments_count=len(segments),
            source_language=source_lang,
            target_language=target_lang,
            input_file_path=request_file,
        )

        # 保存任务记录
        self._save_job(job)

        logger.info(
            f"批量翻译任务已提交: batch_id={batch_id}, segments={len(segments)}"
        )
        return job

    def _save_job(self, job: BatchJob) -> Path:
        """保存任务记录到本地。"""
        job_file = self.work_dir / f"{job.batch_id}_job.json"
        with open(job_file, "w", encoding="utf-8") as f:
            f.write(job.model_dump_json(indent=2))
        return job_file

    def load_job(self, batch_id: str) -> BatchJob | None:
        """从本地加载任务记录。"""
        job_file = self.work_dir / f"{batch_id}_job.json"
        if not job_file.exists():
            return None
        with open(job_file, encoding="utf-8") as f:
            return BatchJob.model_validate_json(f.read())

    # ===================================
    # 状态查询
    # ===================================

    def poll_status(self, batch_id: str) -> BatchStatus:
        """查询任务状态。

        Args:
            batch_id: 批量任务 ID

        Returns:
            BatchStatus 对象
        """
        return self.client.get_status(batch_id)

    def wait_for_completion(
        self,
        batch_id: str,
        poll_interval: int | None = None,
        timeout: int | None = None,
        callback: Callable | None = None,
    ) -> BatchStatus:
        """等待任务完成。

        Args:
            batch_id: 批量任务 ID
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）
            callback: 状态更新回调

        Returns:
            最终的 BatchStatus
        """
        return self.client.poll_until_complete(
            batch_id=batch_id,
            poll_interval=poll_interval,
            timeout=timeout,
            callback=callback,
        )

    # ===================================
    # 结果获取
    # ===================================

    def fetch_results(
        self,
        job: BatchJob,
        segments: list[TranslationSegment] | None = None,
    ) -> list[TranslatedSegment]:
        """获取并解析翻译结果。

        Args:
            job: BatchJob 对象
            segments: 原始段落列表（用于补充元数据）

        Returns:
            翻译后的段落列表
        """
        # 获取最新状态
        status = self.poll_status(job.batch_id)

        if not status.is_success:
            raise ZhipuBatchClientError(
                f"任务未完成或失败: status={status.status.value}"
            )

        if not status.output_file_id:
            raise ZhipuBatchClientError("结果文件 ID 为空")

        # 下载结果文件
        output_file = self.work_dir / f"{job.batch_id}_results.jsonl"
        self.client.download_result(status.output_file_id, output_file)

        # 更新任务记录
        job.output_file_path = output_file
        job.update_status(status)
        self._save_job(job)

        # 解析结果
        return self._parse_results(output_file, segments)

    def _parse_results(
        self,
        result_file: Path,
        segments: list[TranslationSegment] | None = None,
    ) -> list[TranslatedSegment]:
        """解析结果文件。

        Args:
            result_file: 结果 JSONL 文件路径
            segments: 原始段落列表

        Returns:
            翻译后的段落列表
        """
        # 构建原始段落索引（用于补充元数据）
        segment_map: dict[int, TranslationSegment] = {}
        if segments:
            for seg in segments:
                segment_map[seg.index] = seg

        results: list[TranslatedSegment] = []

        with open(result_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    custom_id = data.get("custom_id", "")
                    response = data.get("response", {})

                    # 解析段落索引
                    match = re.match(r"seg_(\d+)", custom_id)
                    if not match:
                        logger.warning(f"无法解析 custom_id: {custom_id}")
                        continue

                    index = int(match.group(1))

                    # 获取翻译文本
                    body = response.get("body", {})
                    choices = body.get("choices", [])
                    if not choices:
                        logger.warning(f"段落 {index} 响应为空")
                        continue

                    translated_text = (
                        choices[0].get("message", {}).get("content", "").strip()
                    )

                    # 获取原始段落信息
                    orig_seg = segment_map.get(index)

                    result = TranslatedSegment(
                        index=index,
                        start=orig_seg.start if orig_seg else 0.0,
                        end=orig_seg.end if orig_seg else 0.0,
                        original_text=orig_seg.text if orig_seg else "",
                        translated_text=translated_text,
                        speaker=orig_seg.speaker if orig_seg else None,
                    )
                    results.append(result)

                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 解析失败: {e}")
                except Exception as e:
                    logger.warning(f"结果解析失败: {e}")

        # 按索引排序
        results.sort(key=lambda x: x.index)

        logger.info(f"解析完成: {len(results)} 个翻译结果")
        return results

    # ===================================
    # 便捷方法
    # ===================================

    def translate_and_wait(
        self,
        segments: list[TranslationSegment],
        source_lang: str = "en",
        target_lang: str = "zh",
        episode_id: str | None = None,
        poll_interval: int | None = None,
        timeout: int | None = None,
        status_callback: Callable | None = None,
    ) -> list[TranslatedSegment]:
        """提交任务并等待完成（阻塞式）。

        这是一个便捷方法，适合简单场景。对于需要非阻塞处理的场景，
        请使用 submit() + poll_status() + fetch_results() 组合。

        Args:
            segments: 要翻译的段落列表
            source_lang: 源语言代码
            target_lang: 目标语言代码
            episode_id: 剧集 ID
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）
            status_callback: 状态更新回调

        Returns:
            翻译后的段落列表
        """
        # 1. 提交任务
        job = self.submit(
            segments=segments,
            source_lang=source_lang,
            target_lang=target_lang,
            episode_id=episode_id,
        )

        # 2. 等待完成
        status = self.wait_for_completion(
            batch_id=job.batch_id,
            poll_interval=poll_interval,
            timeout=timeout,
            callback=status_callback,
        )

        # 3. 检查结果
        if not status.is_success:
            raise ZhipuBatchClientError(
                f"批量翻译失败: status={status.status.value}, "
                f"failed={status.failed_requests}/{status.total_requests}"
            )

        # 4. 获取结果
        return self.fetch_results(job, segments)

    def list_jobs(self) -> list[BatchJob]:
        """列出本地保存的所有任务。"""
        jobs = []
        for job_file in self.work_dir.glob("*_job.json"):
            try:
                with open(job_file, encoding="utf-8") as f:
                    job = BatchJob.model_validate_json(f.read())
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"加载任务记录失败: {job_file}: {e}")
        return sorted(jobs, key=lambda x: x.created_at, reverse=True)

    def refresh_job_status(self, job: BatchJob) -> BatchJob:
        """刷新任务状态。"""
        status = self.poll_status(job.batch_id)
        job.update_status(status)
        self._save_job(job)
        return job


def segments_from_asr_result(asr_result: dict[str, Any]) -> list[TranslationSegment]:
    """从 ASR 结果构建 TranslationSegment 列表。

    Args:
        asr_result: ASR 结果字典（从 asr_result.json 加载）

    Returns:
        TranslationSegment 列表
    """
    segments = []
    for i, seg in enumerate(asr_result.get("segments", [])):
        segments.append(
            TranslationSegment(
                index=i,
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                text=seg.get("text", "").strip(),
                speaker=seg.get("speaker"),
            )
        )
    return segments


def results_to_translation_result(
    translated_segments: list[TranslatedSegment],
    source_lang: str = "en",
    target_lang: str = "zh",
    model: str = "",
) -> dict[str, Any]:
    """将翻译结果转换为标准 TranslationResult 格式。

    Args:
        translated_segments: 翻译后的段落列表
        source_lang: 源语言
        target_lang: 目标语言
        model: 使用的模型

    Returns:
        TranslationResult 兼容的字典
    """
    segments = []
    for seg in translated_segments:
        segments.append(
            {
                "start": seg.start,
                "end": seg.end,
                "original_text": seg.original_text,
                "translated_text": seg.translated_text,
                "speaker": seg.speaker,
            }
        )

    return {
        "segments": segments,
        "source_language": source_lang,
        "target_language": target_lang,
        "model_name": model,
        "total_duration": segments[-1]["end"] if segments else 0.0,
    }
