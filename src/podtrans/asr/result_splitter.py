"""ASR 结果切分器

将完整的 ASR 结果智能切分为多个片段，每个片段约 10 分钟。
切分时会考虑句子边界、说话人切换等因素，确保每个片段的完整性。
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from loguru import logger

from .schemas import ASRResult, ASRResultSegment, ASRSplitMetadata


class ASRResultSplitter:
    """ASR 结果智能切分器

    将完整的 ASR 结果按照指定时长切分为多个片段，切分时会：
    1. 优先在段落边界切分
    2. 避免在句子中间切分
    3. 考虑说话人切换点
    4. 确保每个片段有合理的大小
    """

    def __init__(
        self,
        target_duration: float = 600.0,  # 10分钟
        min_duration: float = 300.0,      # 5分钟
        max_duration: float = 900.0,      # 15分钟
        episode_id: str = "unknown",
    ):
        """初始化切分器

        Args:
            target_duration: 目标片段时长（秒）
            min_duration: 最小片段时长（秒）
            max_duration: 最大片段时长（秒）
            episode_id: 剧集ID
        """
        self.target_duration = target_duration
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.episode_id = episode_id

    def split_result(self, asr_result: ASRResult, output_dir: Path) -> Tuple[List[ASRResultSegment], ASRSplitMetadata]:
        """切分 ASR 结果

        Args:
            asr_result: 完整的 ASR 结果
            output_dir: 输出目录，用于保存片段

        Returns:
            Tuple[List[ASRResultSegment], ASRSplitMetadata]: 切分后的片段列表和元数据
        """
        logger.info(f"开始切分 ASR 结果，目标时长: {self.target_duration/60:.1f} 分钟")

        # 检查是否需要切分
        if asr_result.audio_duration <= self.target_duration:
            logger.info("音频时长小于目标时长，无需切分")
            return [], ASRSplitMetadata(
                episode_id=self.episode_id,
                total_duration=asr_result.audio_duration,
                segment_count=1,
                target_duration=self.target_duration,
                segments=[],
                model_name=asr_result.model_name,
            )

        # 查找切分点
        split_points = self._find_split_points(asr_result)

        # 创建片段
        segments = self._create_segments(asr_result, split_points, output_dir)

        # 创建元数据
        metadata = ASRSplitMetadata(
            episode_id=self.episode_id,
            total_duration=asr_result.audio_duration,
            segment_count=len(segments),
            target_duration=self.target_duration,
            segments=[
                {
                    "segment_id": seg.segment_id,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "file_name": Path(seg.file_path).name if seg.file_path else None,
                    "duration": seg.duration,
                    "segment_count": seg.total_segments,
                    "speakers": list(seg.speakers),
                }
                for seg in segments
            ],
            model_name=asr_result.model_name,
        )

        logger.info(f"切分完成，共 {len(segments)} 个片段")
        return segments, metadata

    def _find_split_points(self, asr_result: ASRResult) -> List[float]:
        """查找最优的切分点

        策略：
        1. 每隔目标时长查找候选切分点
        2. 优先选择段落边界
        3. 避免在句子中间
        4. 考虑说话人切换

        Args:
            asr_result: ASR 结果

        Returns:
            List[float]: 切分点时间列表（秒）
        """
        split_points = []
        current_time = 0

        while current_time < asr_result.audio_duration:
            # 计算下一个目标切分时间
            target_time = current_time + self.target_duration

            # 如果剩余时间太短，直接结束
            if asr_result.audio_duration - target_time < self.min_duration:
                break

            # 查找最佳切分点
            best_split = self._find_best_split_point(asr_result, target_time)

            # 确保不超出最大时长限制
            if best_split - current_time > self.max_duration:
                logger.warning(f"片段过长 ({best_split - current_time:.1f}s > {self.max_duration}s)")
                # 强制在目标时间切分
                best_split = target_time

            split_points.append(best_split)
            current_time = best_split

        return split_points

    def _find_best_split_point(self, asr_result: ASRResult, target_time: float) -> float:
        """在目标时间附近查找最佳切分点

        优先级：
        1. 段落边界（首选）
        2. 句子结尾（标点符号）
        3. 说话人切换点
        4. 最接近目标时间的位置

        Args:
            asr_result: ASR 结果
            target_time: 目标切分时间（秒）

        Returns:
            float: 最佳切分点时间（秒）
        """
        # 搜索窗口（±30秒）
        window_size = 30
        search_start = max(0, target_time - window_size)
        search_end = min(asr_result.audio_duration, target_time + window_size)

        best_point = target_time
        best_score = -float('inf')

        # 遍历所有段落
        for segment in asr_result.segments:
            # 检查段落结束是否在搜索窗口内
            if search_start <= segment.end <= search_end:
                score = self._score_split_point(segment.end, target_time, segment)
                if score > best_score:
                    best_score = score
                    best_point = segment.end

        # 如果没有找到好的段落边界，尝试句子边界
        if best_score < 0.5:
            for segment in asr_result.segments:
                words = segment.words
                for i, word in enumerate(words):
                    if search_start <= word.end <= search_end:
                        # 检查是否是句子结尾
                        if self._is_sentence_end(word.word, i, words):
                            score = self._score_split_point(word.end, target_time, None)
                            if score > best_score:
                                best_score = score
                                best_point = word.end

        logger.debug(f"切分点: 目标={target_time:.1f}s, 实际={best_point:.1f}s, 评分={best_score:.2f}")
        return best_point

    def _score_split_point(self, point: float, target_time: float, segment=None) -> float:
        """给切分点评分

        Args:
            point: 切分点时间（秒）
            target_time: 目标时间（秒）
            segment: 段落对象（可选）

        Returns:
            float: 评分（越高越好）
        """
        # 基础分：距离目标时间越近分数越高
        distance = abs(point - target_time)
        time_score = max(0, 1 - distance / 60)  # 60秒内得正分

        # 段落边界加分
        boundary_bonus = 0.3 if segment else 0

        # 句子结尾加分
        sentence_bonus = 0.2 if segment and self._ends_with_punctuation(segment.text) else 0

        # 说话人切换加分
        speaker_bonus = 0.1 if self._is_speaker_change(point) else 0

        return time_score + boundary_bonus + sentence_bonus + speaker_bonus

    def _is_sentence_end(self, word: str, index: int, words: List) -> bool:
        """判断是否是句子结尾

        Args:
            word: 当前词
            index: 词的索引
            words: 所有词列表

        Returns:
            bool: 是否是句子结尾
        """
        # 检查标点符号
        if self._ends_with_punctuation(word):
            return True

        # 检查下一个词是否大写（英文）
        if index + 1 < len(words):
            next_word = words[index + 1].word
            if next_word and next_word[0].isupper() and word[0].islower():
                return True

        return False

    def _ends_with_punctuation(self, text: str) -> bool:
        """检查文本是否以标点符号结尾

        Args:
            text: 文本

        Returns:
            bool: 是否以标点符号结尾
        """
        return bool(re.search(r'[.!?。！？]$', text.strip()))

    def _is_speaker_change(self, time_point: float) -> bool:
        """检查指定时间点是否是说话人切换点

        注意：这里简化处理，实际实现可能需要更复杂的时间窗口比较

        Args:
            time_point: 时间点（秒）

        Returns:
            bool: 是否是说话人切换点
        """
        # 简化实现：检查附近是否有说话人变化
        # 实际实现需要访问全局的段落列表
        return False

    def _create_segments(
        self, asr_result: ASRResult, split_points: List[float], output_dir: Path
    ) -> List[ASRResultSegment]:
        """根据切分点创建片段

        Args:
            asr_result: 完整的 ASR 结果
            split_points: 切分点列表
            output_dir: 输出目录

        Returns:
            List[ASRResultSegment]: 片段列表
        """
        segments = []
        start_time = 0

        # 确保切分点按顺序排列
        split_points = sorted(split_points)

        for i, split_point in enumerate(split_points, 1):
            # 获取这个时间范围内的所有段落
            segment_data = [
                seg for seg in asr_result.segments
                if seg.start >= start_time and seg.end <= split_point
            ]

            # 处理跨边界的段落
            for seg in asr_result.segments:
                if seg.start < start_time and seg.end > start_time:
                    # 段落开始于切分点之前，结束于切分点之后
                    # 需要截取或复制到前一个片段
                    pass
                elif seg.start < split_point and seg.end > split_point:
                    # 段落跨越切分点，可能需要分割
                    # 为简化，这里将整个段落包含在内
                    if seg not in segment_data:
                        segment_data.append(seg)

            # 收集所有词
            words = []
            for seg in segment_data:
                words.extend(seg.words)

            # 收集说话人
            speakers = {seg.speaker for seg in segment_data if seg.speaker}

            # 创建片段对象
            segment = ASRResultSegment(
                segment_id=f"{self.episode_id}_seg_{i:03d}",
                episode_id=self.episode_id,
                segment_index=i,
                start_time=start_time,
                end_time=split_point,
                original_start_offset=start_time,
                segments=segment_data,
                words=words,
                speakers=speakers,
                language=asr_result.language,
                model_name=asr_result.model_name,
                file_path=None,  # Path will be set by CLI
            )

            segments.append(segment)
            start_time = split_point

        # 处理最后一段
        if start_time < asr_result.audio_duration:
            segment_data = [
                seg for seg in asr_result.segments
                if seg.start >= start_time
            ]

            words = []
            for seg in segment_data:
                words.extend(seg.words)

            speakers = {seg.speaker for seg in segment_data if seg.speaker}

            segment = ASRResultSegment(
                segment_id=f"{self.episode_id}_seg_{len(segments)+1:03d}",
                episode_id=self.episode_id,
                segment_index=len(segments)+1,
                start_time=start_time,
                end_time=asr_result.audio_duration,
                original_start_offset=start_time,
                segments=segment_data,
                words=words,
                speakers=speakers,
                language=asr_result.language,
                model_name=asr_result.model_name,
                file_path=None,  # Path will be set by CLI
            )

            segments.append(segment)

        return segments