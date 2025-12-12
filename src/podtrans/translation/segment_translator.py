"""片段翻译器

处理单个 ASR 片段的翻译工作。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from .translator import Translator
from ..asr.schemas import ASRResult
from ..translation.schemas import TranslationResult
from ..utils.file import read_json, write_json


class SegmentTranslator:
    """ASR 片段翻译器

    专门处理已分片的 ASR 结果的翻译。
    每个片段独立处理，支持并行翻译和错误恢复。
    """

    def __init__(self, translator: Translator):
        """
        初始化片段翻译器

        Args:
            translator: Translator 实例
        """
        self.translator = translator

    def discover_segments(self, episode_dir: Path) -> List[Dict[str, any]]:
        """
        发现剧集目录中的所有 ASR 片段

        Args:
            episode_dir: 剧集目录路径

        Returns:
            片段信息列表
        """
        segments = []
        segments_dir = episode_dir / "segments"

        if not segments_dir.exists():
            logger.warning(f"片段目录不存在: {segments_dir}")
            return segments

        # 读取片段元数据
        metadata_file = episode_dir / "segment_metadata.json"
        if metadata_file.exists():
            try:
                metadata = read_json(metadata_file)
                logger.debug(f"找到元数据: {len(metadata.get('segments', []))} 个片段")
            except Exception as e:
                logger.error(f"读取片段元数据失败: {e}")
                metadata = {}
        else:
            # 没有元数据，扫描目录
            metadata = {"segments": []}
            for segment_dir in sorted(segments_dir.glob("segment_*")):
                if segment_dir.is_dir():
                    asr_file = segment_dir / "asr_result.json"
                    if asr_file.exists():
                        # 尝试从文件名提取信息
                        segment_name = segment_dir.name
                        parts = segment_name.split("_")
                        if len(parts) >= 2:
                            segment_index = int(parts[1])
                        else:
                            segment_index = 0

                        metadata["segments"].append({
                            "segment_index": segment_index,
                            "directory": segment_name,
                            "start_time": 0,  # 未知
                            "end_time": 0,    # 未知
                        })

        # 收集片段信息
        for i, seg_info in enumerate(metadata.get("segments", []), 1):
            segment_index = i
            segment_dir_name = f"segment_{segment_index:03d}"
            segment_dir = segments_dir / segment_dir_name

            asr_file = segment_dir / "asr_result.json"
            if asr_file.exists():
                segments.append({
                    "segment_id": f"episode_{Path(episode_dir).name}_seg_{segment_index:03d}",
                    "segment_index": segment_index,
                    "segment_dir": segment_dir,
                    "asr_result_path": asr_file,
                    "start_time": seg_info.get("start_time", 0),
                    "end_time": seg_info.get("end_time", 0),
                })

        logger.info(f"发现 {len(segments)} 个 ASR 片段")
        return segments

    def load_segment_asr(self, asr_path: Path) -> ASRResult:
        """
        加载片段的 ASR 结果

        Args:
            asr_path: ASR 结果文件路径

        Returns:
            ASRResult 对象
        """
        try:
            asr_data = read_json(asr_path)

            # Convert segment file format to ASRResult format
            # Segment files have 'duration' instead of 'audio_duration'
            if 'duration' in asr_data and 'audio_duration' not in asr_data:
                asr_data['audio_duration'] = asr_data['duration']
                del asr_data['duration']

            # Remove segment-specific fields
            for field in ['segment_id', 'episode_id', 'segment_index', 'start_time', 'end_time']:
                asr_data.pop(field, None)

            return ASRResult(**asr_data)
        except Exception as e:
            logger.error(f"加载 ASR 结果失败 {asr_path}: {e}")
            raise

    def translate_segment(
        self,
        segment_info: Dict[str, any],
        source_lang: str = "en",
        target_lang: str = "zh",
        **kwargs
    ) -> TranslationResult:
        """
        翻译单个片段

        Args:
            segment_info: 片段信息
            source_lang: 源语言
            target_lang: 目标语言
            **kwargs: 传递给 translate_asr_result 的额外参数

        Returns:
            翻译结果
        """
        logger.info(f"翻译片段 {segment_info['segment_index']}: {segment_info['segment_id']}")

        # 加载 ASR 结果
        asr_result = self.load_segment_asr(segment_info["asr_result_path"])

        # 翻译
        translation_result = self.translator.translate_asr_result(
            asr_result=asr_result,
            source_lang=source_lang,
            target_lang=target_lang,
            **kwargs
        )

        return translation_result

    def save_translation_result(
        self,
        segment_dir: Path,
        translation_result: TranslationResult,
        format: str = "json"
    ) -> None:
        """
        保存片段翻译结果

        Args:
            segment_dir: 片段目录
            translation_result: 翻译结果
            format: 输出格式（json/txt/bilingual）
        """
        # 保存 JSON 格式
        json_file = segment_dir / "translation_result.json"
        write_json(translation_result.model_dump(), json_file)

        # 保存纯中文文本
        zh_file = segment_dir / "translation_result.zh.txt"
        with open(zh_file, 'w', encoding='utf-8') as f:
            f.write(translation_result.to_chinese_text(include_speakers=False))

        # 保存双语对照
        bilingual_file = segment_dir / "translation_result.bilingual.txt"
        with open(bilingual_file, 'w', encoding='utf-8') as f:
            f.write(translation_result.to_bilingual_text(include_speakers=True))

        logger.debug(f"翻译结果已保存到: {segment_dir}")

    def get_translation_progress(self, segments: List[Dict[str, any]]) -> Dict[str, any]:
        """
        获取翻译进度

        Args:
            segments: 片段列表

        Returns:
            进度信息
        """
        total = len(segments)
        completed = 0
        pending = 0
        failed = 0

        for seg in segments:
            translation_file = seg["segment_dir"] / "translation_result.json"
            if translation_file.exists():
                completed += 1
            else:
                pending += 1

        return {
            "total_segments": total,
            "completed_segments": completed,
            "pending_segments": pending,
            "failed_segments": failed,
            "progress_percentage": (completed / total * 100) if total > 0 else 0
        }

    def translate_segments(
        self,
        segments: List[Dict[str, any]],
        source_lang: str = "en",
        target_lang: str = "zh",
        max_retries: int = 3,
        **kwargs
    ) -> List[Dict[str, any]]:
        """
        批量翻译片段

        Args:
            segments: 片段列表
            source_lang: 源语言
            target_lang: 目标语言
            max_retries: 最大重试次数
            **kwargs: 传递给翻译器的额外参数

        Returns:
            翻译结果列表
        """
        results = []

        for segment in segments:
            retry_count = 0
            last_error = None

            while retry_count <= max_retries:
                try:
                    # 翻译片段
                    translation_result = self.translate_segment(
                        segment,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        **kwargs
                    )

                    # 保存结果
                    self.save_translation_result(
                        segment["segment_dir"],
                        translation_result
                    )

                    results.append({
                        "segment_id": segment["segment_id"],
                        "segment_index": segment["segment_index"],
                        "success": True,
                        "translation_result_path": segment["segment_dir"] / "translation_result.json"
                    })

                    logger.info(f"片段 {segment['segment_index']} 翻译成功")
                    break

                except Exception as e:
                    last_error = str(e)
                    retry_count += 1

                    if retry_count <= max_retries:
                        logger.warning(f"片段 {segment['segment_index']} 翻译失败，重试 {retry_count}/{max_retries}: {e}")
                    else:
                        logger.error(f"片段 {segment['segment_index']} 翻译最终失败: {e}")
                        results.append({
                            "segment_id": segment["segment_id"],
                            "segment_index": segment["segment_index"],
                            "success": False,
                            "error": last_error,
                            "retry_count": retry_count
                        })

        return results

    def merge_translation_results(
        self,
        episode_dir: Path,
        segments: List[Dict[str, any]],
        output_format: str = "json"
    ) -> Optional[Path]:
        """
        合并所有片段的翻译结果

        Args:
            episode_dir: 剧集目录
            segments: 片段列表
            output_format: 输出格式

        Returns:
            合并后的文件路径
        """
        if not segments:
            return None

        try:
            # 按索引排序片段
            sorted_segments = sorted(segments, key=lambda x: x["segment_index"])

            # 合并所有翻译段
            all_segments = []
            source_language = None
            target_language = None

            for segment in sorted_segments:
                translation_file = segment["segment_dir"] / "translation_result.json"
                if translation_file.exists():
                    translation_data = read_json(translation_file)
                    all_segments.extend(translation_data.get("segments", []))

                    # 使用第一个片段的语言设置
                    if source_language is None:
                        source_language = translation_data.get("source_language")
                        target_language = translation_data.get("target_language")

            # 创建合并后的 TranslationResult
            merged_result = {
                "segments": all_segments,
                "source_language": source_language,
                "target_language": target_language,
                "model_name": "merged_segments",
                "metadata": {
                    "segment_count": len(segments),
                    "total_segments": len(all_segments),
                    "merged_at": datetime.now().isoformat()
                }
            }

            # 保存合并结果
            output_file = episode_dir / f"translation_result.{output_format}"
            if output_format == "json":
                write_json(merged_result, output_file)
            else:
                # 其他格式的处理可以在这里添加
                logger.warning(f"暂不支持 {output_format} 格式的合并输出")

            logger.info(f"翻译结果已合并到: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"合并翻译结果失败: {e}")
            return None