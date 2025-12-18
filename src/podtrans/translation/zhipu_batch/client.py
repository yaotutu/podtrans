"""智谱 Batch API 客户端。

封装智谱 AI Batch API 的 HTTP 调用，提供文件上传、任务创建、状态查询等功能。

API 文档: https://open.bigmodel.cn/dev/api/normal-model/batch
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from podtrans.config import get_settings
from podtrans.translation.zhipu_batch.schemas import (
    BatchJobStatus,
    BatchStatus,
)


class ZhipuBatchClientError(Exception):
    """智谱 Batch API 客户端错误基类。"""

    pass


class ZhipuAuthError(ZhipuBatchClientError):
    """认证错误（API Key 无效或缺失）。"""

    pass


class ZhipuUploadError(ZhipuBatchClientError):
    """文件上传错误。"""

    pass


class ZhipuBatchError(ZhipuBatchClientError):
    """批量任务操作错误。"""

    pass


class ZhipuBatchClient:
    """智谱 Batch API 客户端。

    提供以下功能:
    - 上传批量请求文件
    - 创建批量任务
    - 查询任务状态
    - 下载结果文件
    - 取消任务

    使用示例:
        client = ZhipuBatchClient()
        file_id = client.upload_file(Path("requests.jsonl"))
        batch_id = client.create_batch(file_id)
        status = client.get_status(batch_id)
        if status.is_success:
            client.download_result(status.output_file_id, Path("results.jsonl"))
    """

    # API 基础地址
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(self, api_key: str | None = None, timeout: int = 300):
        """初始化客户端。

        Args:
            api_key: 智谱 API 密钥，为空时从配置读取
            timeout: HTTP 请求超时时间（秒）
        """
        settings = get_settings()
        self.api_key = api_key or settings.zhipu_api_key
        if not self.api_key:
            raise ZhipuAuthError(
                "智谱 API 密钥未配置。"
                "请设置 ZHIPU_API_KEY 环境变量或在 .env 文件中配置。"
            )

        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """关闭 HTTP 客户端。"""
        self._client.close()

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """处理 API 响应。

        Args:
            response: HTTP 响应对象

        Returns:
            解析后的 JSON 响应

        Raises:
            ZhipuAuthError: 认证失败
            ZhipuBatchClientError: 其他 API 错误
        """
        if response.status_code == 401:
            # 尝试获取详细错误信息
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "")
            except Exception:
                error_msg = ""
            if error_msg:
                raise ZhipuAuthError(error_msg)
            raise ZhipuAuthError("API 密钥无效或已过期")

        if response.status_code == 429:
            raise ZhipuBatchClientError("请求频率过高，请稍后重试")

        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                error_msg = response.text
            raise ZhipuBatchClientError(
                f"API 错误 (HTTP {response.status_code}): {error_msg}"
            )

        return response.json()

    def upload_file(self, file_path: Path) -> str:
        """上传批量请求文件。

        Args:
            file_path: JSONL 文件路径

        Returns:
            上传后的文件 ID

        Raises:
            ZhipuUploadError: 上传失败
            FileNotFoundError: 文件不存在
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        logger.info(f"上传批量请求文件: {file_path}")

        try:
            with open(file_path, "rb") as f:
                # 文件上传需要特殊处理，使用 multipart/form-data
                response = httpx.post(
                    f"{self.BASE_URL}/files",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (file_path.name, f, "application/jsonl")},
                    data={"purpose": "batch"},
                    timeout=self.timeout,
                )

            data = self._handle_response(response)
            file_id = data.get("id")

            if not file_id:
                raise ZhipuUploadError(f"上传响应中缺少文件 ID: {data}")

            logger.info(f"文件上传成功: {file_id}")
            return file_id

        except httpx.HTTPError as e:
            raise ZhipuUploadError(f"文件上传失败: {e}")

    def create_batch(
        self,
        input_file_id: str,
        auto_delete_input: bool = True,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """创建批量任务。

        Args:
            input_file_id: 上传的输入文件 ID
            auto_delete_input: 是否自动删除输入文件
            metadata: 自定义元数据（最多 16 个键值对）

        Returns:
            批量任务 ID

        Raises:
            ZhipuBatchError: 创建失败
        """
        logger.info(f"创建批量任务: input_file_id={input_file_id}")

        payload = {
            "input_file_id": input_file_id,
            "endpoint": "/v4/chat/completions",
            "auto_delete_input_file": auto_delete_input,
        }

        if metadata:
            # 限制 metadata 键值对数量和长度
            cleaned_metadata = {}
            for k, v in list(metadata.items())[:16]:
                key = str(k)[:64]
                value = str(v)[:512]
                cleaned_metadata[key] = value
            payload["metadata"] = cleaned_metadata

        try:
            response = self._client.post("/batches", json=payload)
            data = self._handle_response(response)

            batch_id = data.get("id")
            if not batch_id:
                raise ZhipuBatchError(f"创建响应中缺少批量任务 ID: {data}")

            logger.info(f"批量任务创建成功: {batch_id}")
            return batch_id

        except httpx.HTTPError as e:
            raise ZhipuBatchError(f"创建批量任务失败: {e}")

    def get_status(self, batch_id: str) -> BatchStatus:
        """获取批量任务状态。

        Args:
            batch_id: 批量任务 ID

        Returns:
            BatchStatus 对象

        Raises:
            ZhipuBatchError: 查询失败
        """
        try:
            response = self._client.get(f"/batches/{batch_id}")
            data = self._handle_response(response)

            # 解析请求计数
            request_counts = data.get("request_counts", {})

            return BatchStatus(
                id=data["id"],
                status=BatchJobStatus(data["status"]),
                input_file_id=data.get("input_file_id", ""),
                output_file_id=data.get("output_file_id"),
                error_file_id=data.get("error_file_id"),
                created_at=data.get("created_at", 0),
                completed_at=data.get("completed_at"),
                total_requests=request_counts.get("total", 0),
                completed_requests=request_counts.get("completed", 0),
                failed_requests=request_counts.get("failed", 0),
            )

        except httpx.HTTPError as e:
            raise ZhipuBatchError(f"获取任务状态失败: {e}")

    def download_result(
        self,
        file_id: str,
        output_path: Path,
    ) -> Path:
        """下载结果文件。

        Args:
            file_id: 结果文件 ID（output_file_id 或 error_file_id）
            output_path: 本地保存路径

        Returns:
            保存的文件路径

        Raises:
            ZhipuBatchError: 下载失败
        """
        logger.info(f"下载结果文件: {file_id} -> {output_path}")

        try:
            response = self._client.get(
                f"/files/{file_id}/content",
                timeout=self.timeout,
            )

            if response.status_code >= 400:
                raise ZhipuBatchError(
                    f"下载失败 (HTTP {response.status_code}): {response.text}"
                )

            # 确保目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.info(f"结果文件下载成功: {output_path}")
            return output_path

        except httpx.HTTPError as e:
            raise ZhipuBatchError(f"下载结果文件失败: {e}")

    def cancel_batch(self, batch_id: str) -> BatchStatus:
        """取消批量任务。

        Args:
            batch_id: 批量任务 ID

        Returns:
            更新后的 BatchStatus

        Raises:
            ZhipuBatchError: 取消失败
        """
        logger.info(f"取消批量任务: {batch_id}")

        try:
            response = self._client.post(f"/batches/{batch_id}/cancel")
            data = self._handle_response(response)

            return BatchStatus(
                id=data["id"],
                status=BatchJobStatus(data["status"]),
                input_file_id=data.get("input_file_id", ""),
                output_file_id=data.get("output_file_id"),
                error_file_id=data.get("error_file_id"),
                created_at=data.get("created_at", 0),
                completed_at=data.get("completed_at"),
            )

        except httpx.HTTPError as e:
            raise ZhipuBatchError(f"取消批量任务失败: {e}")

    def delete_file(self, file_id: str) -> bool:
        """删除文件。

        Args:
            file_id: 文件 ID

        Returns:
            是否删除成功

        Raises:
            ZhipuBatchError: 删除失败
        """
        logger.info(f"删除文件: {file_id}")

        try:
            response = self._client.delete(f"/files/{file_id}")
            self._handle_response(response)
            logger.info(f"文件删除成功: {file_id}")
            return True

        except httpx.HTTPError as e:
            raise ZhipuBatchError(f"删除文件失败: {e}")

    def list_batches(
        self,
        limit: int = 20,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出批量任务。

        Args:
            limit: 返回数量限制（1-100）
            after: 分页游标

        Returns:
            批量任务列表

        Raises:
            ZhipuBatchError: 查询失败
        """
        params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
        if after:
            params["after"] = after

        try:
            response = self._client.get("/batches", params=params)
            data = self._handle_response(response)
            return data.get("data", [])

        except httpx.HTTPError as e:
            raise ZhipuBatchError(f"列出批量任务失败: {e}")

    def poll_until_complete(
        self,
        batch_id: str,
        poll_interval: int | None = None,
        timeout: int | None = None,
        callback: Callable | None = None,
    ) -> BatchStatus:
        """轮询直到任务完成。

        Args:
            batch_id: 批量任务 ID
            poll_interval: 轮询间隔（秒），默认从配置读取
            timeout: 超时时间（秒），默认从配置读取
            callback: 状态更新回调函数，签名: callback(status: BatchStatus)

        Returns:
            最终的 BatchStatus

        Raises:
            ZhipuBatchError: 轮询失败或超时
        """
        settings = get_settings()
        poll_interval = poll_interval or settings.zhipu_batch_poll_interval
        timeout = timeout or settings.zhipu_batch_timeout

        start_time = time.time()
        logger.info(
            f"开始轮询批量任务: {batch_id} (间隔: {poll_interval}s, 超时: {timeout}s)"
        )

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise ZhipuBatchError(
                    f"批量任务超时: {batch_id} (已等待 {elapsed:.0f}s)"
                )

            status = self.get_status(batch_id)

            if callback:
                try:
                    callback(status)
                except Exception as e:
                    logger.warning(f"状态回调出错: {e}")

            logger.info(
                f"任务状态: {status.status.value} "
                f"({status.completed_requests}/{status.total_requests}) "
                f"[{elapsed:.0f}s]"
            )

            if status.is_terminal:
                return status

            time.sleep(poll_interval)
