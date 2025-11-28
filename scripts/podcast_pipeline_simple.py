#!/usr/bin/env python3
"""
PodTrans 全流程脚本 (简化版)
一键完成：英文音频 → ASR → 翻译 → TTS → 中文播客

使用方法:
    python scripts/podcast_pipeline_simple.py data/input/test.mp3
"""

import sys
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

console = Console()


def run_command(cmd, description, timeout=None):
    """运行命令并显示进度"""
    console.print(f"\n🔄 [bold blue]{description}[/bold blue]...")
    console.print(f"命令: {' '.join(cmd[:4])}{'...' if len(cmd) > 4 else ''}")

    start_time = time.time()

    try:
        # 使用 subprocess 运行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy()
        )

        duration = time.time() - start_time

        if result.returncode == 0:
            console.print(f"✅ [bold green]{description} 完成[/bold green] - 用时: {duration:.1f}秒")
            return True, duration, result.stdout
        else:
            console.print(f"❌ [bold red]{description} 失败[/bold red] - 用时: {duration:.1f}秒")
            console.print(f"错误: {result.stderr}")
            return False, duration, result.stderr

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        console.print(f"⏰ [bold yellow]{description} 超时[/bold yellow] - 用时: {duration:.1f}秒")
        return False, duration, "命令执行超时"
    except Exception as e:
        duration = time.time() - start_time
        console.print(f"❌ [bold red]{description} 异常[/bold red] - 用时: {duration:.1f}秒")
        console.print(f"异常: {e}")
        return False, duration, str(e)


def main():
    if len(sys.argv) != 2:
        console.print("❌ 用法: python scripts/podcast_pipeline_simple.py <audio_file>")
        console.print("示例: python scripts/podcast_pipeline_simple.py data/input/test.mp3")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    # 验证输入文件
    if not input_file.exists():
        console.print(f"❌ 输入文件不存在: {input_file}")
        sys.exit(1)

    # 获取文件信息
    file_info = {
        "name": input_file.stem,
        "size_mb": input_file.stat().st_size / (1024 * 1024),
        "suffix": input_file.suffix.lower()
    }

    base_name = file_info["name"]
    output_dir = Path("data/output") / base_name

    # 显示开始信息
    rprint(Panel.fit(
        f"[bold green]🎙️  PodTrans 全流程[/bold green]\n"
        f"输入文件: {input_file}\n"
        f"文件大小: {file_info['size_mb']:.1f} MB\n"
        f"输出目录: {output_dir}",
        title="流程开始"
    ))

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 结果统计
    results = []
    total_start_time = time.time()

    # 时间记录
    step_times = {}

    # Step 1: ASR
    console.print(f"\n🔄 [bold blue]Step 1: ASR (语音识别 + 说话人分离)[/bold blue]")
    asr_start_time = time.time()
    asr_file = output_dir / "asr_result.json"
    asr_cmd = [
        "python", "-m", "podtrans.cli", "transcribe",
        str(input_file),
        "--output", str(output_dir)
    ]

    success, duration, output = run_command(asr_cmd, "ASR (语音识别 + 说话人分离)")
    asr_duration = time.time() - asr_start_time
    step_times["ASR"] = asr_duration

    results.append({
        "step": "ASR (语音识别)",
        "success": success,
        "duration": asr_duration,
        "output_file": asr_file if success and asr_file.exists() else None,
        "error": None if success else output,
        "timestamp_start": asr_start_time,
        "timestamp_end": time.time()
    })

    if not success:
        console.print("❌ ASR 步骤失败，流程终止")
        sys.exit(1)

    # Step 2: Translation
    console.print(f"\n🔄 [bold blue]Step 2: Translation (翻译)[/bold blue]")
    translation_start_time = time.time()
    translation_file = output_dir / "translation_result.json"
    translation_cmd = [
        "python", "-m", "podtrans.cli", "translate",
        str(asr_file),
        "--output", str(output_dir)
    ]

    success, duration, output = run_command(translation_cmd, "Translation (翻译)")
    translation_duration = time.time() - translation_start_time
    step_times["Translation"] = translation_duration

    results.append({
        "step": "Translation (翻译)",
        "success": success,
        "duration": translation_duration,
        "output_file": translation_file if success and translation_file.exists() else None,
        "error": None if success else output,
        "timestamp_start": translation_start_time,
        "timestamp_end": time.time()
    })

    if not success:
        console.print("❌ 翻译步骤失败，流程终止")
        sys.exit(1)

    # Step 3: TTS
    console.print(f"\n🔄 [bold blue]Step 3: TTS (语音合成)[/bold blue]")
    tts_start_time = time.time()
    tts_file = output_dir / f"{base_name}_chinese.wav"
    tts_cmd = [
        "python", "-m", "podtrans.cli", "synthesize",
        str(translation_file),
        "--output", str(tts_file)
    ]

    success, duration, output = run_command(tts_cmd, "TTS (语音合成)", timeout=3600)  # 60分钟
    tts_duration = time.time() - tts_start_time
    step_times["TTS"] = tts_duration

    results.append({
        "step": "TTS (语音合成)",
        "success": success,
        "duration": tts_duration,
        "output_file": tts_file if success and tts_file.exists() else None,
        "error": None if success else output,
        "timestamp_start": tts_start_time,
        "timestamp_end": time.time()
    })

    # 计算总时间
    total_duration = time.time() - total_start_time
    step_times["Total"] = total_duration

    # 创建结果表格
    table = Table(title="🎯 流程执行结果", show_header=True, header_style="bold magenta")
    table.add_column("步骤", style="cyan", no_wrap=True)
    table.add_column("状态", style="green")
    table.add_column("用时", style="yellow")
    table.add_column("输出文件", style="blue")

    for result in results:
        status = "✅ 成功" if result["success"] else f"❌ 失败"
        duration = f"{result['duration']:.1f}s"
        output_file = str(result.get("output_file", "")) if result["success"] else "N/A"
        table.add_row(result["step"], status, duration, output_file)

    console.print("\n" + "="*60)
    console.print(table)

    # 最终结果
    final_tts_file = output_dir / f"{base_name}_chinese.wav"
    if success and final_tts_file.exists():
        file_size_mb = final_tts_file.stat().st_size / (1024 * 1024)

        # 时间分析
        time_analysis = "\n⏱️ 各步骤用时分析:\n"
        for step, duration in step_times.items():
            percentage = (duration / total_duration) * 100
            time_analysis += f"  • {step}: {duration:.1f}s ({percentage:.1f}%)\n"

        rprint(Panel.fit(
            f"[bold green]🎉 全流程完成！[/bold green]\n"
            f"最终输出: {final_tts_file}\n"
            f"文件大小: {file_size_mb:.1f} MB\n"
            f"总用时: {total_duration:.1f} 秒 ({total_duration/60:.1f} 分钟)\n"
            f"输出目录: {output_dir}\n"
            f"{time_analysis}"
            f"[dim]现在你可以播放生成的中文播客了！[/dim]",
            title="处理完成"
        ))
    else:
        # 即使TTS失败，也显示已完成步骤的时间分析
        time_analysis = "\n⏱️ 已完成步骤用时分析:\n"
        for step, duration in step_times.items():
            if step != "Total":  # 排除总时间
                percentage = (duration / total_duration) * 100 if total_duration > 0 else 0
                time_analysis += f"  • {step}: {duration:.1f}s ({percentage:.1f}%)\n"

        rprint(Panel.fit(
            f"[bold red]❌ 流程未完全成功[/bold red]\n"
            f"请检查上表中的错误信息\n"
            f"{time_analysis}"
            f"已用时: {total_duration:.1f} 秒",
            title="处理失败"
        ))


if __name__ == "__main__":
    main()