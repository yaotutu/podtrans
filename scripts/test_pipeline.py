"""完整流程测试脚本 - 快速验证 ASR + Translation 优化效果

功能:
- 自动运行 ASR → Translation 完整流程
- 与 baseline 自动对比
- 生成详细测试报告
- 支持批量测试

用法:
    # 测试默认文件 (data/input/demo.mp3)
    uv run python scripts/test_pipeline.py

    # 测试指定音频
    uv run python scripts/test_pipeline.py --audio data/input/another.mp3

    # 批量测试多个文件
    uv run python scripts/test_pipeline.py --batch data/input/*.mp3

    # 跳过 baseline 对比
    uv run python scripts/test_pipeline.py --no-compare

    # 仅运行 ASR 阶段
    uv run python scripts/test_pipeline.py --asr-only

    # 仅运行 Translation 阶段 (需要已有 ASR 结果)
    uv run python scripts/test_pipeline.py --translation-only
"""

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# 添加项目根目录到 Python 路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.podtrans.asr import WhisperXHandler
from src.podtrans.config import get_settings
from src.podtrans.translation import Translator
from src.podtrans.utils.file import read_json, write_json

console = Console()


class PipelineTest:
    """完整流程测试器"""

    def __init__(self, audio_path: Path, skip_compare: bool = False):
        """初始化测试器

        Args:
            audio_path: 音频文件路径
            skip_compare: 是否跳过 baseline 对比
        """
        self.audio_path = audio_path
        self.audio_name = audio_path.stem
        self.skip_compare = skip_compare
        self.settings = get_settings()

        # 输出目录
        self.output_dir = self.settings.output_dir / self.audio_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 测试结果
        self.results = {
            "audio_file": str(audio_path),
            "audio_name": self.audio_name,
            "test_time": datetime.now().isoformat(),
            "stages": {},
            "total_duration": 0,
            "baseline_comparison": None,
            "quality_evaluation": {},
        }

    def run_asr(self) -> bool:
        """运行 ASR 阶段

        Returns:
            是否成功
        """
        console.print("\n[bold cyan]🎙️  Stage 1: ASR (Speech Recognition + Diarization)[/bold cyan]\n")

        start_time = time.time()

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Initializing WhisperX...", total=None)

                # 初始化 WhisperX
                handler = WhisperXHandler()

                console.print(f"[green]✓[/green] Model: {handler.model_name}")
                console.print(f"[green]✓[/green] Device: {handler.device}")
                console.print(f"[green]✓[/green] Compute type: {handler.compute_type}\n")

                # 运行 ASR 流程
                task = progress.add_task("Running ASR pipeline...", total=None)
                asr_result = handler.process_full_pipeline(
                    audio_path=self.audio_path,
                    language=None,  # Auto-detect
                    enable_diarization=True,
                )
                progress.remove_task(task)

            # 保存结果
            asr_output = self.output_dir / "asr_result.json"
            write_json(asr_result.model_dump(), asr_output)

            transcript_file = self.output_dir / "transcript.txt"
            transcript_file.write_text(asr_result.to_text(include_speakers=True))

            # 记录结果
            duration = time.time() - start_time
            self.results["stages"]["asr"] = {
                "status": "success",
                "duration_seconds": duration,
                "segments": asr_result.total_segments,
                "speakers": asr_result.speaker_count,
                "language": asr_result.language,
                "output_file": str(asr_output),
            }

            console.print(f"[green]✅ ASR completed in {duration:.2f}s[/green]")
            console.print(f"[dim]Segments: {asr_result.total_segments}, Speakers: {asr_result.speaker_count}[/dim]\n")

            return True

        except Exception as e:
            duration = time.time() - start_time
            self.results["stages"]["asr"] = {
                "status": "failed",
                "duration_seconds": duration,
                "error": str(e),
            }
            console.print(f"[red]❌ ASR failed: {e}[/red]\n")
            return False

    def run_translation(self) -> bool:
        """运行 Translation 阶段

        Returns:
            是否成功
        """
        console.print("[bold cyan]🌐 Stage 2: Translation[/bold cyan]\n")

        # 检查 ASR 结果是否存在
        asr_output = self.output_dir / "asr_result.json"
        if not asr_output.exists():
            console.print("[red]❌ ASR result not found. Please run ASR first.[/red]\n")
            return False

        start_time = time.time()

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Initializing Translator...", total=None)

                # 初始化 Translator
                translator = Translator(self.settings)

                console.print(f"[green]✓[/green] Model: {translator.model}")
                console.print(f"[green]✓[/green] Max segments/batch: {self.settings.translation_max_segments_per_batch}\n")

                # 加载 ASR 结果
                task = progress.add_task("Loading ASR result...", total=None)
                asr_result = translator.load_asr_result(asr_output)
                progress.remove_task(task)

                console.print(f"[green]✓[/green] Loaded {asr_result.total_segments} segments\n")

                # 运行翻译
                task = progress.add_task("Translating...", total=None)
                translation_result = translator.translate_asr_result(
                    asr_result,
                    source_lang="en",
                    target_lang="zh",
                )
                progress.remove_task(task)

            # 保存结果
            output_base = self.output_dir / "translation_result"
            translator.save_result(
                translation_result,
                output_base,
                save_bilingual=True,
            )

            # 计算丢失率
            loss_rate = (
                (asr_result.total_segments - translation_result.total_segments)
                / asr_result.total_segments
                * 100
            )

            # 记录结果
            duration = time.time() - start_time
            self.results["stages"]["translation"] = {
                "status": "success",
                "duration_seconds": duration,
                "segments": translation_result.total_segments,
                "speakers": translation_result.speaker_count,
                "loss_rate_percent": round(loss_rate, 2),
                "model": translation_result.model_name,
                "output_file": str(output_base) + ".json",
            }

            console.print(f"[green]✅ Translation completed in {duration:.2f}s[/green]")
            console.print(f"[dim]Segments: {translation_result.total_segments}, Loss rate: {loss_rate:.2f}%[/dim]\n")

            return True

        except Exception as e:
            duration = time.time() - start_time
            self.results["stages"]["translation"] = {
                "status": "failed",
                "duration_seconds": duration,
                "error": str(e),
            }
            console.print(f"[red]❌ Translation failed: {e}[/red]\n")
            return False

    def compare_baseline(self) -> None:
        """与 baseline 对比"""
        if self.skip_compare:
            console.print("[dim]Skipping baseline comparison[/dim]\n")
            return

        console.print("[bold cyan]📊 Stage 3: Baseline Comparison[/bold cyan]\n")

        baseline_dir = Path("data/baseline/demo_v1_baseline")
        if not baseline_dir.exists():
            console.print("[yellow]⚠️  Baseline not found. Skipping comparison.[/yellow]\n")
            return

        try:
            # 调用对比脚本
            result = subprocess.run(
                ["uv", "run", "python", "scripts/compare_with_baseline.py"],
                capture_output=True,
                text=True,
            )

            self.results["baseline_comparison"] = {
                "status": "completed",
                "output": result.stdout,
            }

            console.print(result.stdout)

        except Exception as e:
            console.print(f"[yellow]⚠️  Comparison failed: {e}[/yellow]\n")
            self.results["baseline_comparison"] = {
                "status": "failed",
                "error": str(e),
            }

    def evaluate_quality(self) -> None:
        """评估质量指标"""
        console.print("[bold cyan]✅ Quality Evaluation[/bold cyan]\n")

        asr_stage = self.results["stages"].get("asr", {})
        translation_stage = self.results["stages"].get("translation", {})

        if asr_stage.get("status") != "success" or translation_stage.get("status") != "success":
            console.print("[yellow]⚠️  Cannot evaluate quality: some stages failed[/yellow]\n")
            return

        # 评估标准
        standards = {
            "speaker_detection": {"target": 2, "actual": asr_stage.get("speakers", 0)},
            "segment_completeness": {
                "target": 98.0,
                "actual": 100 - translation_stage.get("loss_rate_percent", 0),
            },
            "speaker_retention": {
                "target": 100.0,
                "actual": 100.0 if translation_stage.get("speakers", 0) == asr_stage.get("speakers", 0) else 0.0,
            },
        }

        # 显示评估结果
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Metric")
        table.add_column("Target")
        table.add_column("Actual")
        table.add_column("Status")

        all_passed = True

        for metric, values in standards.items():
            target = values["target"]
            actual = values["actual"]

            if metric == "speaker_detection":
                passed = actual >= target
                status = "✅" if passed else "❌"
                table.add_row(
                    "Speaker Detection",
                    f"≥ {target}",
                    str(actual),
                    status,
                )
            elif metric == "segment_completeness":
                passed = actual >= target
                status = "✅" if passed else "❌"
                table.add_row(
                    "Segment Completeness",
                    f"≥ {target}%",
                    f"{actual:.2f}%",
                    status,
                )
            elif metric == "speaker_retention":
                passed = actual >= target
                status = "✅" if passed else "❌"
                table.add_row(
                    "Speaker Retention",
                    f"{target}%",
                    f"{actual:.2f}%",
                    status,
                )

            all_passed = all_passed and passed

        console.print(table)
        console.print()

        # 记录评估结果
        self.results["quality_evaluation"] = {
            "standards": standards,
            "all_passed": all_passed,
        }

        if all_passed:
            console.print("[bold green]🎉 All quality standards met![/bold green]\n")
        else:
            console.print("[bold yellow]⚠️  Some quality standards not met[/bold yellow]\n")

    def generate_report(self) -> None:
        """生成测试报告"""
        console.print("[bold cyan]📝 Generating Test Report[/bold cyan]\n")

        # 计算总耗时
        total_duration = sum(
            stage.get("duration_seconds", 0)
            for stage in self.results["stages"].values()
        )
        self.results["total_duration"] = total_duration

        # 生成 Markdown 报告
        report_lines = [
            f"# Pipeline Test Report",
            f"",
            f"## 测试信息",
            f"",
            f"- **音频文件**: `{self.results['audio_file']}`",
            f"- **测试时间**: {self.results['test_time']}",
            f"- **总耗时**: {total_duration / 60:.2f} 分钟 ({total_duration:.2f} 秒)",
            f"",
        ]

        # ASR 阶段
        asr_stage = self.results["stages"].get("asr", {})
        report_lines.extend([
            f"## ASR 阶段",
            f"",
            f"- **耗时**: {asr_stage.get('duration_seconds', 0) / 60:.2f} 分钟",
            f"- **段落数**: {asr_stage.get('segments', 'N/A')}",
            f"- **说话人数**: {asr_stage.get('speakers', 'N/A')}",
            f"- **语言**: {asr_stage.get('language', 'N/A').upper()}",
            f"- **状态**: {'✅ 成功' if asr_stage.get('status') == 'success' else '❌ 失败'}",
            f"",
        ])

        if asr_stage.get("status") == "failed":
            report_lines.append(f"- **错误**: {asr_stage.get('error', 'Unknown')}")
            report_lines.append("")

        # Translation 阶段
        translation_stage = self.results["stages"].get("translation", {})
        report_lines.extend([
            f"## Translation 阶段",
            f"",
            f"- **耗时**: {translation_stage.get('duration_seconds', 0) / 60:.2f} 分钟",
            f"- **翻译段落**: {translation_stage.get('segments', 'N/A')}",
            f"- **丢失率**: {translation_stage.get('loss_rate_percent', 'N/A')}%",
            f"- **说话人数**: {translation_stage.get('speakers', 'N/A')}",
            f"- **模型**: {translation_stage.get('model', 'N/A')}",
            f"- **状态**: {'✅ 成功' if translation_stage.get('status') == 'success' else '❌ 失败'}",
            f"",
        ])

        if translation_stage.get("status") == "failed":
            report_lines.append(f"- **错误**: {translation_stage.get('error', 'Unknown')}")
            report_lines.append("")

        # Baseline 对比
        if self.results.get("baseline_comparison"):
            comparison = self.results["baseline_comparison"]
            report_lines.extend([
                f"## Baseline 对比",
                f"",
            ])

            if comparison.get("status") == "completed":
                report_lines.append("```")
                report_lines.append(comparison.get("output", "No output"))
                report_lines.append("```")
            else:
                report_lines.append(f"**错误**: {comparison.get('error', 'Unknown')}")

            report_lines.append("")

        # 质量评估
        if self.results.get("quality_evaluation"):
            evaluation = self.results["quality_evaluation"]
            standards = evaluation.get("standards", {})

            report_lines.extend([
                f"## 质量评估",
                f"",
            ])

            for metric, values in standards.items():
                target = values["target"]
                actual = values["actual"]

                if metric == "speaker_detection":
                    passed = actual >= target
                    status = "✅" if passed else "❌"
                    report_lines.append(f"- {status} **说话人检测**: {actual} (目标 ≥ {target})")
                elif metric == "segment_completeness":
                    passed = actual >= target
                    status = "✅" if passed else "❌"
                    report_lines.append(f"- {status} **段落完整性**: {actual:.2f}% (目标 ≥ {target}%)")
                elif metric == "speaker_retention":
                    passed = actual >= target
                    status = "✅" if passed else "❌"
                    report_lines.append(f"- {status} **说话人保留**: {actual:.2f}% (目标 {target}%)")

            report_lines.append("")

            if evaluation.get("all_passed"):
                report_lines.append("## 结论")
                report_lines.append("")
                report_lines.append("✅ **当前版本质量符合要求，可以考虑更新 baseline**")
            else:
                report_lines.append("## 结论")
                report_lines.append("")
                report_lines.append("⚠️  **部分质量指标未达标，建议继续优化**")

        # 保存报告
        report_path = self.output_dir / "test_report.md"
        report_path.write_text("\n".join(report_lines))

        # 保存 JSON 结果
        json_path = self.output_dir / "test_results.json"
        write_json(self.results, json_path)

        console.print(f"[green]✓[/green] Report saved to: {report_path}")
        console.print(f"[green]✓[/green] JSON results saved to: {json_path}\n")

    def run_full_test(self, asr_only: bool = False, translation_only: bool = False) -> None:
        """运行完整测试

        Args:
            asr_only: 仅运行 ASR 阶段
            translation_only: 仅运行 Translation 阶段
        """
        console.print(
            Panel.fit(
                f"[bold cyan]🧪 Pipeline Test[/bold cyan]\n"
                f"[dim]Audio:[/dim] {self.audio_path}\n"
                f"[dim]Output:[/dim] {self.output_dir}",
                border_style="cyan",
            )
        )

        start_time = time.time()

        # 运行 ASR
        if not translation_only:
            asr_success = self.run_asr()
            if asr_only:
                console.print("[dim]ASR-only mode: skipping translation[/dim]\n")
                self.generate_report()
                return
            if not asr_success:
                console.print("[red]ASR failed. Stopping test.[/red]\n")
                self.generate_report()
                return

        # 运行 Translation
        translation_success = self.run_translation()
        if not translation_success:
            console.print("[yellow]Translation failed. Generating partial report.[/yellow]\n")
            self.generate_report()
            return

        # 对比 baseline
        self.compare_baseline()

        # 评估质量
        self.evaluate_quality()

        # 生成报告
        self.generate_report()

        # 显示总结
        total_time = time.time() - start_time
        console.print("=" * 60)
        console.print(f"[bold green]✨ Test Completed in {total_time / 60:.2f} minutes[/bold green]")
        console.print("=" * 60)
        console.print()


def batch_test(audio_files: list[Path], skip_compare: bool = False) -> None:
    """批量测试多个音频文件

    Args:
        audio_files: 音频文件路径列表
        skip_compare: 是否跳过 baseline 对比
    """
    console.print(
        Panel.fit(
            f"[bold cyan]🔄 Batch Test[/bold cyan]\n"
            f"[dim]Files:[/dim] {len(audio_files)}",
            border_style="cyan",
        )
    )

    results = []

    for i, audio_path in enumerate(audio_files, 1):
        console.print(f"\n[bold]Testing {i}/{len(audio_files)}: {audio_path.name}[/bold]\n")

        tester = PipelineTest(audio_path, skip_compare=skip_compare)
        tester.run_full_test()

        results.append({
            "audio": str(audio_path),
            "results": tester.results,
        })

    # 保存批量测试结果
    batch_results_path = Path("data/output/batch_test_results.json")
    write_json({"test_time": datetime.now().isoformat(), "tests": results}, batch_results_path)

    console.print(f"\n[green]✓[/green] Batch results saved to: {batch_results_path}\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="完整流程测试脚本 - 快速验证 ASR + Translation 优化效果"
    )
    parser.add_argument(
        "--audio",
        type=Path,
        default=Path("data/input/demo.mp3"),
        help="音频文件路径 (默认: data/input/demo.mp3)",
    )
    parser.add_argument(
        "--batch",
        nargs="+",
        type=Path,
        help="批量测试多个音频文件",
    )
    parser.add_argument(
        "--no-compare",
        action="store_true",
        help="跳过 baseline 对比",
    )
    parser.add_argument(
        "--asr-only",
        action="store_true",
        help="仅运行 ASR 阶段",
    )
    parser.add_argument(
        "--translation-only",
        action="store_true",
        help="仅运行 Translation 阶段 (需要已有 ASR 结果)",
    )

    args = parser.parse_args()

    # 批量测试
    if args.batch:
        batch_test(args.batch, skip_compare=args.no_compare)
        return

    # 单个测试
    if not args.audio.exists():
        console.print(f"[red]❌ Audio file not found: {args.audio}[/red]")
        return

    tester = PipelineTest(args.audio, skip_compare=args.no_compare)
    tester.run_full_test(asr_only=args.asr_only, translation_only=args.translation_only)


if __name__ == "__main__":
    main()
