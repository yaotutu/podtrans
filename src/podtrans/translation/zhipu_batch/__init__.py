"""智谱 Batch API 批量翻译模块。

该模块提供智谱 AI Batch API 的集成，用于大批量翻译任务。
Batch API 价格为标准 API 的 50%，适合非实时的大规模翻译需求。

主要组件:
- ZhipuBatchClient: 智谱 Batch API 客户端
- ZhipuBatchTranslator: 批量翻译器
- BatchJobManager: 批量任务管理器

使用示例:
    from podtrans.translation.zhipu_batch import ZhipuBatchTranslator

    translator = ZhipuBatchTranslator()
    batch_id = translator.submit(segments)
    status = translator.poll_status(batch_id)
    result = translator.fetch_results(batch_id)
"""

from podtrans.translation.zhipu_batch.client import ZhipuBatchClient
from podtrans.translation.zhipu_batch.schemas import (
    BatchJob,
    BatchRequest,
    BatchStatus,
)
from podtrans.translation.zhipu_batch.translator import ZhipuBatchTranslator

__all__ = [
    "ZhipuBatchClient",
    "ZhipuBatchTranslator",
    "BatchJob",
    "BatchStatus",
    "BatchRequest",
]
