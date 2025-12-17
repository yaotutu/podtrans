"""
RSS模块 - 播客RSS feed处理

负责RSS feed解析、音频下载和状态管理。
"""

import sys
import re
import json
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger
import httpx
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from .services.database import DatabaseManager
from .rss_config import RSSFeedConfig, GlobalSettings
from .config import get_settings


def clean_title_for_folder(title: str, max_length: int = 50) -> str:
    """
    清理标题用于文件夹命名

    Args:
        title: 原始标题
        max_length: 最大长度（默认50字符）

    Returns:
        清理后的标题
    """
    # 1. 转小写
    cleaned = title.lower()

    # 2. 移除所有特殊字符，只保留字母、数字、空格和连字符
    cleaned = re.sub(r"[^\w\s\-]", "", cleaned)

    # 3. 空格替换为 -
    cleaned = re.sub(r"\s+", "-", cleaned)

    # 4. 多个连续 - 合并为单个
    cleaned = re.sub(r"-+", "-", cleaned)

    # 5. 去除首尾 -
    cleaned = cleaned.strip("-")

    # 6. 截断到最大长度（在单词边界）
    if len(cleaned) > max_length:
        # 找到最大长度内最后一个 - 的位置
        truncated = cleaned[:max_length]
        last_dash = truncated.rfind("-")
        if last_dash > max_length // 2:  # 至少保留一半长度
            cleaned = truncated[:last_dash]
        else:
            cleaned = truncated.rstrip("-")

    return cleaned


def parse_publication_date(pub_date_str: str) -> str:
    """
    解析RSS发布日期为YYYY-MM-DD格式

    Args:
        pub_date_str: RSS的published字段（如 "Sat, 6 Dec 2025 11:00:00 +0000"）

    Returns:
        日期字符串，格式为 YYYY-MM-DD
    """
    if not pub_date_str:
        return datetime.now().strftime("%Y-%m-%d")

    try:
        # RSS标准日期格式 (RFC 2822)
        dt = parsedate_to_datetime(pub_date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # 解析失败，使用当前日期
        return datetime.now().strftime("%Y-%m-%d")


def generate_episode_folder_name(title: str, pub_date_str: str) -> str:
    """
    生成剧集文件夹名

    Args:
        title: 剧集标题
        pub_date_str: 发布日期字符串

    Returns:
        文件夹名，格式为 {cleaned_title}_{date}
    """
    cleaned_title = clean_title_for_folder(title)
    date_str = parse_publication_date(pub_date_str)
    return f"{cleaned_title}_{date_str}"


class RSSProcessor:
    """RSS处理器 - 负责RSS feed的解析和音频下载"""

    def __init__(self, data_dir: Path = Path("./data"), global_settings: Optional[GlobalSettings] = None, settings=None):
        self.data_dir = Path(data_dir)
        self.global_settings = global_settings or GlobalSettings()
        # Use settings parameter if provided, otherwise get from global config
        if settings is None:
            settings = get_settings()
        self.db_path = settings.get_database_dir() / "episodes.db"
        self.db = DatabaseManager(self.db_path)

    async def process_rss(
        self,
        rss_url: str,
        download_mode: str = "latest",
        download_count: Optional[int] = 1
    ) -> bool:
        """
        处理RSS feed，下载剧集

        Args:
            rss_url: RSS feed URL
            download_mode: 下载模式 - "latest"(最新N集) 或 "all"(全部)
            download_count: 下载数量，仅在download_mode="latest"时有效

        Returns:
            bool: 处理成功返回True
        """
        logger.info(f"开始处理RSS feed: {rss_url}")
        logger.info(f"下载模式: {download_mode}, 数量: {download_count if download_mode == 'latest' else '全部'}")

        try:
            # 1. 获取RSS信息并解析
            timeout_value = self.global_settings.download_timeout
            async with httpx.AsyncClient(timeout=timeout_value, follow_redirects=True) as client:
                response = await client.get(rss_url)
                response.raise_for_status()

            # 使用feedparser解析RSS
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"RSS解析警告: {feed.bozo_exception}")

            if not feed.entries:
                logger.error("RSS feed中没有找到剧集")
                return False

            # 根据下载模式确定要处理的剧集
            if download_mode == "all":
                episodes_to_process = feed.entries
                logger.info(f"下载模式: 全部 - 找到 {len(episodes_to_process)} 集")
            else:  # latest
                count = download_count or 1
                episodes_to_process = feed.entries[:count]
                logger.info(f"下载模式: 最新 {count} 集 - 找到 {len(episodes_to_process)} 集")

            # 获取播客名称
            podcast_name = feed.feed.get('title', 'Unknown Feed')

            # 处理每一集
            success_count = 0
            failed_count = 0

            for idx, episode in enumerate(episodes_to_process, 1):
                logger.info(f"处理剧集 {idx}/{len(episodes_to_process)}")
                if await self._process_single_episode(episode, podcast_name):
                    success_count += 1
                else:
                    failed_count += 1

            logger.info(f"处理完成: 成功 {success_count}, 失败 {failed_count}")
            return success_count > 0

        except Exception as e:
            logger.error(f"RSS处理异常: {e}")
            return False

    async def _process_single_episode(self, episode, podcast_name: str) -> bool:
        """
        处理单个剧集

        Args:
            episode: feedparser的episode对象
            podcast_name: 播客名称

        Returns:
            bool: 处理成功返回True
        """
        try:
            episode_title = episode.get('title', 'Unknown Episode')
            episode_guid = episode.get('id', '')  # RSS GUID - 唯一标识符
            pub_date_str = episode.get('published', '')
            logger.info(f"处理剧集: {episode_title}")
            logger.debug(f"GUID: {episode_guid}")

            if not episode_guid:
                logger.error(f"剧集 {episode_title} 没有GUID，跳过")
                return False

            # 1. 检查是否已经处理过（用GUID查询）
            existing_episode = self.db.get_episode_by_guid(episode_guid)
            if existing_episode and existing_episode.get('download_completed'):
                logger.info(f"剧集已存在且下载完成: {episode_title}")
                return True

            # 2. 创建播客目录和剧集子目录
            podcast_name_clean = podcast_name.replace(' ', '_').replace('/', '_')
            podcast_dir = self.data_dir / podcast_name_clean
            podcast_dir.mkdir(parents=True, exist_ok=True)

            # 使用 标题+日期 作为文件夹名，提高可读性
            episode_folder_name = generate_episode_folder_name(episode_title, pub_date_str)
            episode_dir = podcast_dir / episode_folder_name
            episode_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"文件夹: {episode_folder_name}")

            # 音频文件统一命名为 episode.mp3
            audio_path = episode_dir / "episode.mp3"

            # 3. 提取音频URL
            audio_url = ""
            if episode.get('enclosures'):
                audio_url = episode.enclosures[0].get('href', '')

            if not audio_url:
                logger.error(f"剧集 {episode_title} 没有找到音频URL")
                return False

            # 4. 在数据库中创建记录
            episode_id = self.db.create_episode(
                podcast_name=podcast_name,
                episode_title=episode_title,
                episode_guid=episode_guid,
                episode_dir=str(episode_dir),
                audio_url=audio_url,
                audio_path=str(audio_path),
                publication_date=episode.get('published', ''),
                description=episode.get('description', ''),
                duration=0
            )

            if episode_id == -1:
                logger.error("创建数据库记录失败")
                return False

            # 5. 下载音频文件
            logger.info(f"开始下载音频: {audio_url}")

            # 检查文件是否已经存在
            min_file_size = int(self.global_settings.min_file_size_mb * 1024 * 1024)
            if audio_path.exists():
                file_size = audio_path.stat().st_size
                logger.info(f"音频文件已存在: {audio_path} ({file_size} bytes)")

                # 验证文件完整性
                if file_size >= min_file_size:
                    # 更新数据库状态
                    self.db.update_episode_status(episode_id, {
                        'file_size': file_size,
                        'download_completed': True
                    })
                    logger.info(f"使用已存在的音频文件: {episode_title}")
                    return True
                else:
                    logger.warning(f"已存在的文件太小，重新下载: {file_size} bytes")
                    audio_path.unlink()

            try:
                timeout_value = self.global_settings.download_timeout
                async with httpx.AsyncClient(timeout=timeout_value, follow_redirects=True) as client:
                    response = await client.get(audio_url)
                    response.raise_for_status()

                    # 写入文件
                    with open(audio_path, 'wb') as f:
                        f.write(response.content)

                    file_size = len(response.content)
                    logger.info(f"音频下载完成，文件大小: {file_size} bytes")

                    # 验证文件完整性
                    if file_size < min_file_size:
                        logger.error(f"音频文件太小，可能下载失败: {file_size} bytes")
                        audio_path.unlink()  # 删除损坏的文件
                        self.db.update_episode_status(episode_id, {
                            'last_error': f'音频文件太小: {file_size} bytes',
                            'error_count': 1
                        })
                        return False

                    # 7. 更新数据库状态
                    self.db.update_episode_status(episode_id, {
                        'file_size': file_size,
                        'download_completed': True
                    })

                    logger.info(f"剧集处理完成: {episode_title}")
                    return True

            except Exception as e:
                logger.error(f"音频下载失败: {e}")
                # 清理部分下载的文件
                if audio_path.exists():
                    audio_path.unlink()

                self.db.update_episode_status(episode_id, {
                    'last_error': str(e),
                    'error_count': 1
                })
                return False

        except Exception as e:
            logger.error(f"剧集处理异常: {e}")
            return False

    def get_status(self) -> dict:
        """获取服务状态"""
        stats = self.db.get_statistics()
        return {
            'total_episodes': stats.get('total_episodes', 0),
            'download_completed': stats.get('download_completed', 0),
            'processing': stats.get('processing', 0),
            'data_dir': str(self.data_dir),
            'database_path': str(self.db_path)
        }


# RSS模块接口 - 提供给外层的简单接口
def create_rss_processor(data_dir: str = "./data", global_settings: Optional[GlobalSettings] = None) -> RSSProcessor:
    """创建RSS处理器"""
    settings = get_settings()
    return RSSProcessor(Path(data_dir), global_settings, settings)


async def start_rss_processing(
    rss_url: str = None,
    data_dir: str = "./data",
    config_path: str = "./rss_config.toml",
    download_mode: str = "latest",
    download_count: int = 1
) -> bool:
    """
    启动RSS处理 - 主要接口函数

    Args:
        rss_url: RSS feed URL (如果提供，则忽略配置文件中的feeds)
        data_dir: 数据目录路径
        config_path: 配置文件路径
        download_mode: 下载模式 - "latest" 或 "all"
        download_count: 下载数量

    Returns:
        bool: 处理成功返回True
    """
    from .rss_config import load_rss_config

    # 加载配置
    try:
        config = load_rss_config(Path(config_path))
        logger.info(f"配置文件加载成功: {config_path}")
    except Exception as e:
        logger.warning(f"配置文件加载失败，使用默认配置: {e}")
        from .rss_config import RSSConfig
        config = RSSConfig()

    # 使用配置中的全局设置
    global_settings = config.global_settings
    actual_data_dir = data_dir if data_dir != "./data" else global_settings.data_dir

    # 创建处理器
    processor = create_rss_processor(actual_data_dir, global_settings)

    # 显示服务状态
    status = processor.get_status()
    logger.info(f"RSS处理器启动")
    logger.info(f"数据目录: {status['data_dir']}")
    logger.info(f"数据库: {status['database_path']}")
    logger.info(f"当前状态: {status}")

    # 确定要处理的feeds
    feeds_to_process = []

    if rss_url:
        # 命令行指定了URL，使用命令行参数
        logger.info(f"使用命令行参数: {rss_url}")
        feeds_to_process.append({
            'url': rss_url,
            'download_mode': download_mode,
            'download_count': download_count
        })
    else:
        # 使用配置文件中的feeds
        enabled_feeds = config.get_enabled_feeds()
        if not enabled_feeds:
            logger.error("配置文件中没有启用的RSS feeds")
            return False

        logger.info(f"从配置文件读取到 {len(enabled_feeds)} 个启用的feeds")
        for feed_config in enabled_feeds:
            feeds_to_process.append({
                'url': feed_config.url,
                'download_mode': feed_config.download_mode,
                'download_count': feed_config.download_count,
                'name': feed_config.name
            })

    # 处理所有feeds
    all_success = True
    for feed_info in feeds_to_process:
        feed_url = feed_info['url']
        feed_name = feed_info.get('name', feed_url)
        mode = feed_info['download_mode']
        count = feed_info['download_count']

        logger.info(f"\n处理 feed: {feed_name}")
        logger.info(f"URL: {feed_url}")
        logger.info(f"模式: {mode}, 数量: {count if mode == 'latest' else '全部'}")

        result = await processor.process_rss(feed_url, mode, count)

        if not result:
            all_success = False
            logger.error(f"Feed 处理失败: {feed_name}")
        else:
            logger.info(f"Feed 处理成功: {feed_name}")

    # 显示最终状态
    final_status = processor.get_status()
    logger.info(f"\n最终状态: {final_status}")

    return all_success


def get_rss_status(data_dir: str = "./data") -> dict:
    """获取RSS状态"""
    processor = create_rss_processor(data_dir)
    return processor.get_status()