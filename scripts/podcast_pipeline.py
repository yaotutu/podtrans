#!/usr/bin/env python3
"""
PodTrans 全流程脚本
一键完成：英文音频 → ASR → 翻译 → TTS → 中文播客

使用方法:
    python scripts/podcast_pipeline.py data/input/demo.mp3
    python scripts/podcast_pipeline.py /path/to/your/podcast.mp3
"""

import sys
import os
import time
import argparse
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from podtrans.config import get_settings
from podtrans.cli import transcribe, translate, synthesize
from podtrans.utils.file import read_json, write_json

console = Console()


def get_file_info(input_file: Path) -> dict:
    """获取文件信息"""
    return {
        "name": input_file.stem,
        "size_mb": input_file.stat().st_size / (1024 * 1024),
        "suffix": input_file.suffix.lower()
    }


def setup_output_directories(base_name: str) -> dict:
    """创建输出目录结构"""
    base_dir = Path("data/output") / base_name

    dirs = {
        "base": base_dir,
        "asr": base_dir / "asr",
        "translation": base_dir / "translation",
        "tts": base_dir / "tts"
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    return dirs


def run_step_with_timing(step_name: str, func, *args, **kwargs):
    """运行步骤并计时"""
    console.print(f"\n🔄 [bold blue]{step_name}[/bold blue]...")
    start_time = time.time()

    try:
        result = func(*args, **kwargs)
        duration = time.time() - start_time

        console.print(f"✅ [bold green]{step_name} 完成[/bold green] - 用时: {duration:.1f}秒")
        return result, duration

    except Exception as e:
        duration = time.time() - start_time
        console.print(f"❌ [bold red]{step_name} 失败[/bold red] - 用时: {duration:.1f}秒")
        console.print(f"   错误: {e}")
        raise


def save_metadata(output_dir: Path, metadata: dict):
    """保存流程元数据"""
    metadata_file = output_dir / "pipeline_metadata.json"
    write_json(metadata_file, metadata)
    console.print(f"📋 元数据已保存: {metadata_file}")


def create_summary_table(results: dict) -> Table:
    """创建结果汇总表"""
    table = Table(title="🎯 流程执行结果", show_header=True, header_style="bold magenta")

    table.add_column("步骤", style="cyan", no_wrap=True)
    table.add_column("状态", style="green")
    table.add_column("用时", style="yellow")
    table.add_column("输出文件", style="blue")

    step_names = ["ASR (语音识别)", "Translation (翻译)", "TTS (语音合成)"]
    step_keys = ["asr", "translation", "tts"]

    for step_name, step_key in zip(step_names, step_keys):
        if step_key in results:
            result = results[step_key]
            status = "✅ 成功" if result["success"] else f"❌ 失败: {result.get('error', 'Unknown')}"
            duration = f"{result['duration']:.1f}s" if result["success"] else "N/A"
            output_file = str(result.get("output_file", "")) if result["success"] else "N/A"

            table.add_row(step_name, status, duration, output_file)

    return table


def main():
    parser = argparse.ArgumentParser(
        description="PodTrans 全流程：英文音频 → 中文播客",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s data/input/demo.mp3
  %(prog)s /path/to/podcast.mp3 --device cuda
  %(prog)s data/input/episode.mp3 --whisper-model large-v3
        """
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="输入音频文件路径 (支持 mp3, wav, m4a 等格式)"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output"),
        help="输出根目录 (默认: data/output)"
    )

    parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        help="计算设备 (默认: 从配置读取)"
    )

    parser.add_argument(
        "--whisper-model",
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        help="Whisper 模型大小 (默认: 从配置读取)"
    )

    parser.add_argument(
        "--translation-model",
        help="翻译模型 (默认: 从配置读取)"
    )

    parser.add_argument(
        "--tts-timeout",
        type=int,
        default=1800,
        help="TTS 超时时间，秒 (默认: 1800 = 30分钟)"
    )

    parser.add_argument(
        "--skip-steps",
        nargs="+",
        choices=["asr", "translation", "tts"],
        help="跳过指定步骤 (用于调试)"
    )

    args = parser.parse_args()

    # 验证输入文件
    if not args.input_file.exists():
        console.print(f"❌ 输入文件不存在: {args.input_file}")
        sys.exit(1)

    if not args.input_file.is_file():
        console.print(f"❌ 输入路径不是文件: {args.input_file}")
        sys.exit(1)

    # 获取文件信息
    file_info = get_file_info(args.input_file)
    base_name = file_info["name"]

    # 显示开始信息
    rprint(Panel.fit(
        f"[bold green]🎙️  PodTrans 全流程[/bold green]\n"
        f"输入文件: {args.input_file}\n"
        f"文件大小: {file_info['size_mb']:.1f} MB\n"
        f"输出目录: {args.output_dir / base_name}",
        title="流程开始"
    ))

    # 设置输出目录
    dirs = setup_output_directories(base_name)

    # 初始化结果和元数据
    results = {}
    metadata = {
        "input_file": str(args.input_file),
        "file_info": file_info,
        "start_time": datetime.now().isoformat(),
        "output_directory": str(dirs["base"]),
        "steps": {}
    }

    total_start_time = time.time()

    try:
        # Step 1: ASR (语音识别 + 说话人分离)
        if "asr" not in (args.skip_steps or []):
            asr_file = dirs["asr"] / "asr_result.json"

            # 构建transcribe命令的参数
            transcribe_args = [
                str(args.input_file),
                "--output", str(dirs["asr"])
            ]

            if args.device:
                transcribe_args.extend(["--device", args.device])
            if args.whisper_model:
                transcribe_args.extend(["--model", args.whisper_model])

            # 模拟 transcribe 函数调用
            from typer.testing import CliRunner
            from podtrans.cli import app

            runner = CliRunner()
            with Progress() as progress:
                task = progress.add_task("ASR 处理中...", total=None)

                # 调用 transcribe 命令
                result = runner.invoke(app, ["transcribe"] + transcribe_args)

                if result.exit_code == 0:
                    asr_result = read_json(asr_file)
                    asr_duration = 0  # 实际应该解析输出获取时长

                    results["asr"] = {
                        "success": True,
                        "duration": asr_duration,
                        "output_file": asr_file,
                        "segments": len(asr_result.get("segments", [])),
                        "speakers": asr_result.get("speaker_count", 0),
                        "language": asr_result.get("language", "unknown")
                    }

                    metadata["steps"]["asr"] = {
                        "status": "success",
                        "output_file": str(asr_file),
                        "segments": results["asr"]["segments"],
                        "speakers": results["asr"]["speakers"]
                    }
                else:
                    results["asr"] = {
                        "success": False,
                        "duration": 0,
                        "error": result.stderr or "ASR 处理失败"
                    }
                    metadata["steps"]["asr"] = {
                        "status": "failed",
                        "error": results["asr"]["error"]
                    }
                    raise Exception(f"ASR 失败: {results['asr']['error']}")

        # Step 2: Translation (翻译)
        if "translation" not in (args.skip_steps or []):
            translation_file = dirs["translation"] / "translation_result.json"

            # 构建translate命令的参数
            translate_args = [
                str(asr_file),
                "--output", str(dirs["translation"])
            ]

            if args.translation_model:
                translate_args.extend(["--model", args.translation_model])

            with Progress() as progress:
                task = progress.add_task("翻译处理中...", total=None)

                # 调用 translate 命令
                result = runner.invoke(app, ["translate"] + translate_args)

                if result.exit_code == 0:
                    translation_result = read_json(translation_file)

                    results["translation"] = {
                        "success": True,
                        "duration": 0,  # 实际应该解析输出获取时长
                        "output_file": translation_file,
                        "segments": len(translation_result.get("segments", [])),
                        "speakers": translation_result.get("speaker_count", 0)
                    }

                    metadata["steps"]["translation"] = {
                        "status": "success",
                        "output_file": str(translation_file),
                        "segments": results["translation"]["segments"]
                    }
                else:
                    results["translation"] = {
                        "success": False,
                        "duration": 0,
                        "error": result.stderr or "翻译处理失败"
                    }
                    metadata["steps"]["translation"] = {
                        "status": "failed",
                        "error": results["translation"]["error"]
                    }
                    raise Exception(f"翻译失败: {results['translation']['error']}")

        # Step 3: TTS (语音合成)
        if "tts" not in (args.skip_steps or []):
            tts_file = dirs["tts"] / f"{base_name}_chinese.wav"

            # 构建synthesize命令的参数
            synthesize_args = [
                str(translation_file),
                "--output", str(tts_file),
                "--timeout", str(args.tts_timeout)
            ]

            with Progress() as progress:
                task = progress.add_task("语音合成中...", total=None)

                # 调用 synthesize 命令
                result = runner.invoke(app, ["synthesize"] + synthesize_args)

                if result.exit_code == 0 and tts_file.exists():
                    results["tts"] = {
                        "success": True,
                        "duration": 0,  # 实际应该解析输出获取时长
                        "output_file": tts_file,
                        "file_size_mb": tts_file.stat().st_size / (1024 * 1024)
                    }

                    metadata["steps"]["tts"] = {
                        "status": "success",
                        "output_file": str(tts_file),
                        "file_size_mb": results["tts"]["file_size_mb"]
                    }
                else:
                    results["tts"] = {
                        "success": False,
                        "duration": 0,
                        "error": result.stderr or "语音合成失败"
                    }
                    metadata["steps"]["tts"] = {
                        "status": "failed",
                        "error": results["tts"]["error"]
                    }
                    raise Exception(f"TTS 失败: {results['tts']['error']}")

        # 计算总时长
        total_duration = time.time() - total_start_time
        metadata["total_duration"] = total_duration
        metadata["end_time"] = datetime.now().isoformat()
        metadata["success"] = True

        # 保存元数据
        save_metadata(dirs["base"], metadata)

        # 显示结果汇总
        console.print("\n" + "="*60)
        console.print(create_summary_table(results))

        # 成功完成
        final_output = results["tts"]["output_file"] if "tts" in results and results["tts"]["success"] else None
        if final_output:
            rprint(Panel.fit(
                f"[bold green]🎉 全流程完成！[/bold green]\n"
                f"最终输出: {final_output}\n"
                f"总用时: {total_duration:.1f} 秒\n"
                f"输出目录: {dirs['base']}\n"
                f"[dim]现在你可以播放生成的中文播客了！[/dim]",
                title="处理完成"
            ))
        else:
            console.print("⚠️  流程完成但没有生成最终音频文件")

    except KeyboardInterrupt:
        console.print("\n❌ [bold red]用户中断处理[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ [bold red]流程失败: {e}[/bold red]")
        metadata["success"] = False
        metadata["error"] = str(e)
        save_metadata(dirs["base"], metadata)
        sys.exit(1)


if __name__ == "__main__":
    main()