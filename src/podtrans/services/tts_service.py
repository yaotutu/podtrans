"""TTS 服务 - 封装 podcast-tts CLI 调用

该服务封装了对外部 podcast-tts CLI 工具的调用，
提供同步阻塞式的 TTS 任务执行。
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class TTSResult:
    """TTS 执行结果"""

    success: bool
    output_path: str | None = None
    duration: float | None = None
    error: str | None = None
    task_id: str | None = None


class TTSService:
    """TTS 服务 - 同步执行

    封装 podcast-tts CLI 调用，提供：
    - 同步阻塞执行
    - 混合输出解析（从日志中提取最后的 JSON）
    - 超时控制
    """

    def __init__(self, cli_path: str, timeout: int = 3600):
        """
        初始化 TTS 服务

        Args:
            cli_path: podcast-tts CLI 可执行文件路径
            timeout: 执行超时时间（秒），默认 3600（1小时）
        """
        self.cli_path = cli_path
        self.timeout = timeout

    def _extract_last_json(self, text: str) -> dict | None:
        """从混合输出中提取最后一个 JSON 对象

        podcast-tts CLI 输出格式为：
        - 开始时输出一个 JSON
        - 中间输出大量日志
        - 结束时输出一个 JSON

        此方法从后往前查找有效的 JSON 对象。

        Args:
            text: CLI 的完整 stdout 输出

        Returns:
            解析后的 JSON 字典，如果没找到返回 None
        """
        # 匹配所有 JSON 对象（简单的 {...} 匹配）
        json_pattern = r"\{[^{}]*\}"
        matches = re.findall(json_pattern, text)

        # 从后往前找有效的 JSON
        for match in reversed(matches):
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        return None

    def execute(self, episode_dir: Path) -> TTSResult:
        """执行 TTS 任务（同步阻塞）

        调用 podcast-tts CLI 处理指定的剧集目录，
        等待任务完成后返回结果。

        Args:
            episode_dir: 剧集目录路径，需包含：
                - voice_samples.json
                - segments/*/translation_result.json

        Returns:
            TTSResult 包含执行结果
        """
        logger.info(f"开始 TTS 处理: {episode_dir}")

        try:
            result = subprocess.run(
                [self.cli_path, str(episode_dir)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # 从混合输出中提取最后一个 JSON
            output = self._extract_last_json(result.stdout)

            if output is None:
                # 如果没有找到 JSON，尝试从 stderr 获取错误信息
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else "No valid JSON found in output"
                )
                logger.error(f"TTS 输出解析失败: {error_msg}")
                return TTSResult(
                    success=False,
                    error=error_msg,
                )

            if output.get("success"):
                logger.info(f"TTS 处理成功: {output.get('output_path')}")
                return TTSResult(
                    success=True,
                    output_path=output.get("output_path"),
                    duration=output.get("duration"),
                    task_id=output.get("task_id"),
                )
            else:
                error_msg = output.get("error", output.get("message", "Unknown error"))
                logger.error(f"TTS 处理失败: {error_msg}")
                return TTSResult(
                    success=False,
                    error=error_msg,
                    task_id=output.get("task_id"),
                )

        except subprocess.TimeoutExpired:
            error_msg = f"Timeout after {self.timeout}s"
            logger.error(f"TTS 执行超时: {error_msg}")
            return TTSResult(success=False, error=error_msg)
        except FileNotFoundError:
            error_msg = f"CLI not found: {self.cli_path}"
            logger.error(f"TTS CLI 不存在: {error_msg}")
            return TTSResult(success=False, error=error_msg)
        except Exception as e:
            logger.exception(f"TTS 执行异常: {e}")
            return TTSResult(success=False, error=str(e))
