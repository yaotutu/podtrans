"""智谱 Batch API 数据模型。

定义了批量翻译相关的 Pydantic 模型，用于请求构建、状态追踪和结果解析。
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class BatchJobStatus(str, Enum):
    """批量任务状态枚举。"""

    VALIDATING = "validating"  # 文件正在验证中
    FAILED = "failed"  # 文件未通过验证
    IN_PROGRESS = "in_progress"  # 任务正在进行中
    FINALIZING = "finalizing"  # 任务已完成，结果正在准备中
    COMPLETED = "completed"  # 任务已完成，结果已准备好
    EXPIRED = "expired"  # 任务未能完成（超时）
    CANCELLING = "cancelling"  # 任务正在取消中
    CANCELLED = "cancelled"  # 任务已取消


class BatchRequest(BaseModel):
    """单个批量请求的格式（JSONL 中的一行）。

    符合智谱 Batch API 要求的请求格式。
    """

    custom_id: str = Field(..., description="请求的唯一标识符，用于匹配结果")
    method: Literal["POST"] = Field(default="POST", description="HTTP 方法")
    url: Literal["/v4/chat/completions"] = Field(
        default="/v4/chat/completions", description="API 端点"
    )
    body: dict[str, Any] = Field(..., description="请求体，包含模型、消息等")


class BatchResponse(BaseModel):
    """单个批量响应的格式（结果 JSONL 中的一行）。"""

    id: str = Field(..., description="批量任务 ID")
    custom_id: str = Field(..., description="请求的唯一标识符")
    response: dict[str, Any] = Field(..., description="响应内容")


class BatchStatus(BaseModel):
    """批量任务状态。"""

    id: str = Field(..., description="批量任务 ID")
    status: BatchJobStatus = Field(..., description="当前状态")
    input_file_id: str = Field(..., description="输入文件 ID")
    output_file_id: str | None = Field(None, description="输出文件 ID（完成后）")
    error_file_id: str | None = Field(None, description="错误文件 ID（有错误时）")
    created_at: int = Field(..., description="创建时间（Unix 时间戳）")
    completed_at: int | None = Field(None, description="完成时间（Unix 时间戳）")

    # 请求计数
    total_requests: int = Field(0, description="总请求数")
    completed_requests: int = Field(0, description="已完成请求数")
    failed_requests: int = Field(0, description="失败请求数")

    @property
    def is_terminal(self) -> bool:
        """判断任务是否已结束（无论成功或失败）。"""
        return self.status in (
            BatchJobStatus.COMPLETED,
            BatchJobStatus.FAILED,
            BatchJobStatus.EXPIRED,
            BatchJobStatus.CANCELLED,
        )

    @property
    def is_success(self) -> bool:
        """判断任务是否成功完成。"""
        return self.status == BatchJobStatus.COMPLETED

    @property
    def progress_percent(self) -> float:
        """计算进度百分比。"""
        if self.total_requests == 0:
            return 0.0
        return (self.completed_requests / self.total_requests) * 100


class BatchJob(BaseModel):
    """批量翻译任务记录。

    用于本地追踪批量任务的完整信息。
    """

    batch_id: str = Field(..., description="智谱批量任务 ID")
    input_file_id: str = Field(..., description="输入文件 ID")
    episode_id: str | None = Field(None, description="关联的剧集 ID")
    segment_index: int | None = Field(None, description="关联的片段索引")

    # 任务信息
    model: str = Field(..., description="使用的模型")
    segments_count: int = Field(..., description="翻译的段落数")
    source_language: str = Field(default="en", description="源语言")
    target_language: str = Field(default="zh", description="目标语言")

    # 状态追踪
    status: BatchJobStatus = Field(
        default=BatchJobStatus.VALIDATING, description="当前状态"
    )
    output_file_id: str | None = Field(None, description="输出文件 ID")
    error_file_id: str | None = Field(None, description="错误文件 ID")

    # 统计
    completed_count: int = Field(0, description="已完成数")
    failed_count: int = Field(0, description="失败数")

    # 本地文件路径
    input_file_path: Path | None = Field(None, description="本地输入文件路径")
    output_file_path: Path | None = Field(None, description="本地输出文件路径")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    completed_at: datetime | None = Field(None, description="完成时间")

    def update_status(self, status: BatchStatus) -> None:
        """从 BatchStatus 更新状态。"""
        self.status = status.status
        self.output_file_id = status.output_file_id
        self.error_file_id = status.error_file_id
        self.completed_count = status.completed_requests
        self.failed_count = status.failed_requests
        self.updated_at = datetime.now()
        if status.is_terminal:
            self.completed_at = datetime.now()


class TranslationSegment(BaseModel):
    """翻译段落（用于构建批量请求）。"""

    index: int = Field(..., description="段落索引")
    start: float = Field(..., description="开始时间（秒）")
    end: float = Field(..., description="结束时间（秒）")
    text: str = Field(..., description="原文文本")
    speaker: str | None = Field(None, description="说话人 ID")


class TranslatedSegment(BaseModel):
    """已翻译的段落（从批量结果解析）。"""

    index: int = Field(..., description="段落索引")
    start: float = Field(..., description="开始时间（秒）")
    end: float = Field(..., description="结束时间（秒）")
    original_text: str = Field(..., description="原文文本")
    translated_text: str = Field(..., description="译文文本")
    speaker: str | None = Field(None, description="说话人 ID")
