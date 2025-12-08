"""
SoulX-Podcast 格式转换器

将翻译结果（TranslationResult）转换为 SoulX-Podcast TTS 服务所需的 JSON 格式。

SoulX-Podcast 期望的输入格式：
{
    "speakers": {
        "S1": {
            "prompt_audio": "说话人1的音频样本路径",
            "prompt_text": "说话人1的语音特征描述"
        },
        "S2": {
            "prompt_audio": "说话人2的音频样本路径",
            "prompt_text": "说话人2的语音特征描述"
        }
    },
    "text": [
        ["S1", "第一段文本"],
        ["S2", "第二段文本"],
        ["S1", "第三段文本"]
    ]
}

使用说明：
    converter = SoulXConverter()
    soulx_data = converter.convert_from_file(translation_result_path)

    # soulx_data 就是可以直接给 SoulX 使用的 JSON 数据
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from podtrans.utils.file import read_json


class SoulXConverter:
    """
    SoulX-Podcast 格式转换器

    自动将翻译结果转换为 SoulX 所需的 JSON 格式，处理所有逻辑：
    1. 自动检测剧集目录和文件
    2. 自动加载语音样本
    3. 自动处理说话人映射
    4. 自动提供默认音频
    """

    def __init__(self):
        """初始化转换器"""
        # 默认语音样本路径（当某个说话人没有样本时使用）
        self.default_samples = {
            "male": {
                "audio": "data/default_speaker/male_mandarin.wav",
                "text": "还有一个就是要跟大家纠正一点就是我们在看电影的时候尤其是游戏玩家看电影的时候在看到那个到西北那边的这个陕北民谣这个可能在想哎是不是他是受到了黑神话的启发"
            },
            "female": {
                "audio": "data/default_speaker/female_mandarin.wav",
                "text": "喜欢攀岩徒步滑雪的语言爱好者,以及过两天要带着全部家当去景德镇做陶瓷的白日梦想家。"
            }
        }

    def convert_from_file(self, translation_result_path: str) -> Dict:
        """
        从翻译结果文件转换为 SoulX 格式

        Args:
            translation_result_path: translation_result.json 文件路径

        Returns:
            Dict: SoulX 格式的 JSON 数据

        Example:
            >>> converter = SoulXConverter()
            >>> soulx_data = converter.convert_from_file("/path/to/translation_result.json")
            >>> with open("soulx_input.json", "w", encoding="utf-8") as f:
            ...     json.dump(soulx_data, f, ensure_ascii=False, indent=2)
        """
        translation_path = Path(translation_result_path)
        if not translation_path.exists():
            raise FileNotFoundError(f"翻译结果文件不存在: {translation_path}")

        # 自动推断剧集目录
        episode_dir = translation_path.parent

        # 加载翻译数据
        translation_data = read_json(translation_path)

        # 自动查找语音样本文件
        voice_samples_path = episode_dir / "voice_samples.json"
        voice_samples_data = None
        if voice_samples_path.exists():
            voice_samples_data = read_json(voice_samples_path)
            logger.info(f"找到语音样本文件: {voice_samples_path}")
        else:
            logger.warning(f"未找到语音样本文件: {voice_samples_path}，将使用默认语音")

        # 执行转换
        result = self._convert(
            translation_data=translation_data,
            voice_samples_data=voice_samples_data,
            episode_dir=episode_dir
        )

        logger.info(f"转换完成: {len(result['text'])} 个文本段, {len(result['speakers'])} 个说话人")
        return result

    def _convert(
        self,
        translation_data: Dict,
        voice_samples_data: Optional[Dict] = None,
        episode_dir: Optional[Path] = None
    ) -> Dict:
        """
        内部转换方法

        Args:
            translation_data: 翻译结果字典
            voice_samples_data: 语音样本数据
            episode_dir: 剧集目录

        Returns:
            Dict: SoulX 格式的数据
        """
        # 1. 提取文本段并收集说话人信息
        segments = translation_data.get("segments", [])
        if not segments:
            logger.warning("翻译结果中没有文本段")
            return {"speakers": {}, "text": []}

        # 2. 创建说话人映射 (原始ID -> S1, S2...)
        speaker_mapping = self._create_speaker_mapping(segments)
        logger.debug(f"说话人映射: {speaker_mapping}")

        # 3. 构建说话人配置
        speakers_dict = self._build_speakers(
            speaker_mapping,
            voice_samples_data,
            episode_dir
        )

        # 4. 构建文本数组
        text_array = self._build_text_array(segments, speaker_mapping)

        return {
            "speakers": speakers_dict,
            "text": text_array
        }

    def _create_speaker_mapping(self, segments: List[Dict]) -> Dict[str, str]:
        """
        创建说话人ID映射

        将 WhisperX 的 SPEAKER_XX 格式映射为 SoulX 的 S1, S2... 格式

        Args:
            segments: 文本段列表

        Returns:
            Dict[str, str]: 映射关系，如 {"SPEAKER_00": "S1", "SPEAKER_01": "S2"}
        """
        # 收集所有说话人
        speakers = set()
        for seg in segments:
            speaker = seg.get("speaker")
            if speaker:
                speakers.add(speaker)

        if not speakers:
            # 没有说话人信息，创建默认说话人
            logger.info("未检测到说话人分离，创建默认说话人 S1")
            return {"DEFAULT": "S1"}

        # 排序以确保一致性
        sorted_speakers = sorted(speakers)

        # 创建映射: SPEAKER_00 -> S1, SPEAKER_01 -> S2...
        mapping = {
            speaker_id: f"S{i + 1}"
            for i, speaker_id in enumerate(sorted_speakers)
        }

        return mapping

    def _build_speakers(
        self,
        speaker_mapping: Dict[str, str],
        voice_samples_data: Optional[Dict],
        episode_dir: Optional[Path]
    ) -> Dict[str, Dict]:
        """
        构建说话人配置

        Args:
            speaker_mapping: 说话人ID映射
            voice_samples_data: 语音样本数据
            episode_dir: 剧集目录

        Returns:
            Dict[str, Dict]: SoulX 格式的说话人配置
        """
        # 提取语音样本信息
        speaker_samples = {}
        if voice_samples_data:
            speaker_samples = voice_samples_data.get("speaker_samples", {})

        speakers_dict = {}

        for original_id, soulx_id in speaker_mapping.items():
            # 获取该说话人的语音样本
            sample_info = speaker_samples.get(original_id, {})
            audio_path = sample_info.get("audio_path")
            text_content = sample_info.get("text_content", "")

            # 确定使用哪个音频文件
            if audio_path and episode_dir:
                # 使用实际语音样本
                full_audio_path = episode_dir / audio_path
                if full_audio_path.exists():
                    prompt_audio = str(full_audio_path)
                    prompt_text = text_content
                    logger.debug(f"说话人 {soulx_id} 使用实际语音样本: {prompt_audio}")
                else:
                    # 文件不存在，使用默认音频
                    prompt_audio, prompt_text = self._get_default_audio(soulx_id)
                    logger.warning(f"语音样本文件不存在，使用默认音频: {soulx_id}")
            else:
                # 没有语音样本，使用默认音频
                prompt_audio, prompt_text = self._get_default_audio(soulx_id)
                logger.warning(f"无语音样本，使用默认音频: {soulx_id}")

            # 构建说话人配置
            speakers_dict[soulx_id] = {
                "prompt_audio": prompt_audio,
                "prompt_text": prompt_text
            }

        return speakers_dict

    def _get_default_audio(self, speaker_id: str) -> tuple[str, str]:
        """
        获取默认音频配置

        根据说话人ID交替使用男声/女声默认音频

        Args:
            speaker_id: SoulX 说话人ID，如 "S1", "S2"

        Returns:
            tuple[str, str]: (音频路径, 描述文本)
        """
        # 从 ID 中提取数字
        try:
            speaker_num = int(speaker_id[1:])  # "S1" -> 1
        except (IndexError, ValueError):
            speaker_num = 1

        # 奇数使用男声，偶数使用女声
        if speaker_num % 2 == 1:
            # 男声
            return self.default_samples["male"]["audio"], self.default_samples["male"]["text"]
        else:
            # 女声
            return self.default_samples["female"]["audio"], self.default_samples["female"]["text"]

    def _build_text_array(
        self,
        segments: List[Dict],
        speaker_mapping: Dict[str, str]
    ) -> List[List[str]]:
        """
        构建文本数组

        Args:
            segments: 文本段列表
            speaker_mapping: 说话人ID映射

        Returns:
            List[List[str]]: SoulX 格式的文本数组
        """
        text_array = []

        for seg in segments:
            # 获取翻译文本
            translated_text = seg.get("translated_text", "")
            if not translated_text:
                continue

            # 确定说话人
            original_speaker = seg.get("speaker")
            if original_speaker and original_speaker in speaker_mapping:
                soulx_speaker = speaker_mapping[original_speaker]
            else:
                # 使用默认说话人
                soulx_speaker = next(iter(speaker_mapping.values()))

            # 添加到文本数组
            text_array.append([soulx_speaker, translated_text])

        return text_array


# 便捷函数：直接从文件路径转换
def convert_translation_to_soulx(translation_result_path: str) -> Dict:
    """
    便捷函数：将翻译结果文件转换为 SoulX 格式

    Args:
        translation_result_path: translation_result.json 文件路径

    Returns:
        Dict: SoulX 格式的数据

    Example:
        >>> from podtrans.tts.soulx.converter import convert_translation_to_soulx
        >>> soulx_data = convert_translation_to_soulx("/path/to/translation_result.json")
    """
    converter = SoulXConverter()
    return converter.convert_from_file(translation_result_path)