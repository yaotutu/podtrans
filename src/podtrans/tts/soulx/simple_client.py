"""
简化的 SoulX CLI 调用服务

这个模块提供一个极简的 SoulX CLI 调用接口，不做任何数据格式转换，
只负责直接调用外部的 SoulX CLI 脚本。
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from podtrans.config import get_settings


class SimpleSoulXService:
    """简化的 SoulX CLI 调用服务

    这个类只做一件事：直接调用 SoulX CLI 脚本。
    不做任何数据格式转换，不做环境管理，不做复杂的错误处理。
    """

    def __init__(
        self,
        cli_script_path: Optional[str] = None,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        conda_env: Optional[str] = None
    ):
        """初始化简化服务

        Args:
            cli_script_path: SoulX CLI 脚本路径，默认从配置读取
            timeout: 调用超时时间（秒），默认从配置读取
            working_dir: 工作目录，默认从配置读取
            conda_env: conda 环境名称，默认从配置读取
        """
        settings = get_settings()

        self.cli_script_path = cli_script_path or getattr(settings, 'soulx_cli_script', 'soulx_cli.py')
        self.timeout = timeout or getattr(settings, 'soulx_cli_timeout', 10800)
        self.working_dir = working_dir or getattr(settings, 'soulx_cli_working_dir', '.')
        self.conda_env = conda_env or getattr(settings, 'soulx_cli_conda_env', 'soulxpodcast')
        self.model_path = getattr(settings, 'soulx_cli_model_path', '/home/yaotutu/SoulX-Podcast-main/pretrained_models/SoulX-Podcast-1.7B')

        logger.info(f"SimpleSoulXService initialized: script={self.cli_script_path}, timeout={self.timeout}s, conda_env={self.conda_env}, model={self.model_path}")

    def call_cli(
        self,
        input_json: str,
        output_wav: str,
        **cli_kwargs: Any
    ) -> Dict[str, Any]:
        """直接调用 SoulX CLI

        Args:
            input_json: 用户提供的 SoulX 格式 JSON 文件路径
            output_wav: 输出 WAV 文件路径
            **cli_kwargs: 传递给 CLI 的其他参数

        Returns:
            dict: {
                "success": bool,  # 是否成功
                "output_path": str,  # 输出文件路径（成功时）
                "error": str,  # 错误信息（失败时）
                "return_code": int,  # CLI 返回码
                "stdout": str,  # 标准输出
                "stderr": str   # 标准错误
            }
        """
        input_path = Path(input_json)
        output_path = Path(output_wav)

        # 基本验证
        if not input_path.exists():
            error_msg = f"Input JSON file does not exist: {input_path}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "return_code": -1,
                "stdout": "",
                "stderr": ""
            }

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 构建 CLI 命令
        cmd = self._build_command(input_path.absolute(), output_path.absolute(), **cli_kwargs)

        logger.info(f"Calling SoulX CLI with conda environment: {self.conda_env}")
        logger.debug(f"Full command:\n{cmd}")

        try:
            # 执行命令（使用 bash -c 来执行复杂的 conda 包装命令）
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            success = result.returncode == 0
            output_file = str(output_path) if success and output_path.exists() else ""

            if success:
                logger.info(f"SoulX CLI succeeded: {output_file}")
            else:
                logger.error(f"SoulX CLI failed with code {result.returncode}: {result.stderr}")

            return {
                "success": success,
                "output_path": output_file,
                "error": result.stderr if not success else "",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

        except subprocess.TimeoutExpired:
            error_msg = f"SoulX CLI timed out after {self.timeout} seconds"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "return_code": -1,
                "stdout": "",
                "stderr": error_msg
            }

        except Exception as e:
            error_msg = f"Unexpected error calling SoulX CLI: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "return_code": -1,
                "stdout": "",
                "stderr": error_msg
            }

    def _build_command(
        self,
        input_path: Path,
        output_path: Path,
        **cli_kwargs: Any
    ) -> str:
        """构建完整的 CLI 命令（带 conda 环境包装）

        Args:
            input_path: 输入 JSON 文件路径
            output_path: 输出 WAV 文件路径
            **cli_kwargs: 其他 CLI 参数

        Returns:
            str: 完整的 shell 命令（包含 conda 环境设置）
        """
        # 构建基础 Python 命令
        python_cmd = ["python", self.cli_script_path]

        # 添加基本参数（适配 SoulX CLI 的参数格式）
        python_cmd.extend(["--json_path", str(input_path)])
        python_cmd.extend(["--model_path", str(self.model_path)])
        python_cmd.extend(["--output_path", str(output_path)])

        # 添加其他参数
        for key, value in cli_kwargs.items():
            if isinstance(value, bool) and value:
                # 布尔参数，只有为 True 时才添加
                python_cmd.append(f"--{key.replace('_', '-')}")
            elif value is not None:
                # 有值的参数
                python_cmd.extend([f"--{key.replace('_', '-')}", str(value)])

        # 构建 conda 环境包装命令
        # 注意：cli_script_path 可能是绝对路径，需要相对到 working_dir
        script_full_path = Path(self.cli_script_path)
        working_dir_full = Path(self.working_dir)

        # 如果脚本在 working_dir 下，使用相对路径；否则使用绝对路径
        try:
            script_rel_path = script_full_path.relative_to(working_dir_full)
            script_path_for_cmd = str(script_rel_path)
        except ValueError:
            # 脚本不在 working_dir 下，使用绝对路径
            script_path_for_cmd = str(script_full_path)

        conda_cmd = f'''
source ~/miniconda3/etc/profile.d/conda.sh && \\
conda activate {self.conda_env} && \\
cd {self.working_dir} && \\
export PYTHONPATH={self.working_dir}:$PYTHONPATH && \\
python {script_path_for_cmd} {" ".join(python_cmd[2:])}
'''.strip()

        return conda_cmd

    def validate_cli_script(self) -> bool:
        """验证 CLI 脚本是否存在并可执行

        Returns:
            bool: CLI 脚本是否可用
        """
        script_path = Path(self.cli_script_path)

        if not script_path.exists():
            logger.error(f"SoulX CLI script not found: {script_path}")
            return False

        if not script_path.is_file():
            logger.error(f"SoulX CLI script is not a file: {script_path}")
            return False

        # 检查是否可读
        try:
            with open(script_path, 'r') as f:
                content = f.read(100)  # 读前100个字符
                if not content.strip():
                    logger.error(f"SoulX CLI script is empty: {script_path}")
                    return False
                # 简单检查是否是 Python 脚本
                if not content.strip().startswith('#!') and 'python' not in content.lower():
                    logger.warning(f"SoulX CLI script might not be a Python script: {script_path}")
        except Exception as e:
            logger.error(f"Cannot read SoulX CLI script {script_path}: {e}")
            return False

        logger.info(f"SoulX CLI script validation passed: {script_path}")
        return True

    def __str__(self) -> str:
        return f"SimpleSoulXService(script={self.cli_script_path}, timeout={self.timeout}s)"

    def __repr__(self) -> str:
        return self.__str__()