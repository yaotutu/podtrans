"""
RSS模块 - 播客RSS feed处理

负责RSS feed解析、音频下载和状态管理。
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger
import httpx
import feedparser
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from .services.database import DatabaseManager


class RSSProcessor:
    """RSS处理器 - 负责RSS feed的解析和音频下载"""

    def __init__(self, data_dir: Path = Path("./data")):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "episodes.db"
        self.db = DatabaseManager(self.db_path)

    async def process_rss(self, rss_url: str) -> bool:
        """
        处理RSS feed，下载最新剧集

        Args:
            rss_url: RSS feed URL

        Returns:
            bool: 处理成功返回True
        """
        logger.info(f"开始处理RSS feed: {rss_url}")

        try:
            # 1. 获取RSS信息并解析
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(rss_url)
                response.raise_for_status()

            # 使用feedparser解析RSS
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"RSS解析警告: {feed.bozo_exception}")

            if not feed.entries:
                logger.error("RSS feed中没有找到剧集")
                return False

            # 获取最新剧集
            latest_episode = feed.entries[0]
            episode_title = latest_episode.get('title', 'Unknown Episode')

            logger.info(f"找到最新剧集: {episode_title}")

            # 2. 检查是否已经处理过
            podcast_name = feed.feed.get('title', 'Unknown Feed')
            existing_episode = self.db.get_episode_by_title(episode_title, podcast_name)
            if existing_episode and existing_episode.get('download_completed'):
                logger.info(f"剧集已存在且下载完成: {episode_title}")
                return True

            # 3. 创建固定的输出目录（基于播客名称）
            podcast_name_clean = podcast_name.replace(' ', '_').replace('/', '_')
            episode_dir = self.data_dir / podcast_name_clean
            episode_dir.mkdir(parents=True, exist_ok=True)

            # 生成固定的音频文件名（基于剧集标题）
            episode_title_clean = episode_title.replace(' ', '_').replace('/', '_').replace('?', '').replace('!', '').replace(':', '').replace('"', '').replace("'", "")
            audio_path = episode_dir / f"{episode_title_clean}.mp3"

            # 4. 提取音频URL
            audio_url = ""
            if latest_episode.get('enclosures'):
                audio_url = latest_episode.enclosures[0].get('href', '')

            if not audio_url:
                logger.error("没有找到音频URL")
                return False

            # 5. 在数据库中创建记录
            episode_id = self.db.create_episode(
                podcast_name=podcast_name,
                episode_title=episode_title,
                episode_number=None,
                episode_dir=str(episode_dir),
                audio_url=audio_url,
                audio_path=str(audio_path),
                publication_date=latest_episode.get('published', ''),
                description=latest_episode.get('description', ''),
                duration=0
            )

            if episode_id == -1:
                logger.error("创建数据库记录失败")
                return False

            # 6. 下载音频文件
            logger.info(f"开始下载音频: {audio_url}")

            # 检查文件是否已经存在
            if audio_path.exists():
                file_size = audio_path.stat().st_size
                logger.info(f"音频文件已存在: {audio_path} ({file_size} bytes)")

                # 验证文件完整性
                if file_size >= 1024 * 1024:  # 至少1MB
                    # 更新数据库状态
                    self.db.update_episode_status(episode_id, {
                        'file_size': file_size,
                        'download_completed': True,
                        'current_stage': 'asr'
                    })
                    logger.info(f"使用已存在的音频文件: {episode_title}")
                    return True
                else:
                    logger.warning(f"已存在的文件太小，重新下载: {file_size} bytes")
                    audio_path.unlink()

            try:
                async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
                    response = await client.get(audio_url)
                    response.raise_for_status()

                    # 写入文件
                    with open(audio_path, 'wb') as f:
                        f.write(response.content)

                    file_size = len(response.content)
                    logger.info(f"音频下载完成，文件大小: {file_size} bytes")

                    # 验证文件完整性（至少1MB）
                    if file_size < 1024 * 1024:  # 1MB
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
                        'download_completed': True,
                        'current_stage': 'asr'
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
            logger.error(f"RSS处理异常: {e}")
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
def create_rss_processor(data_dir: str = "./data") -> RSSProcessor:
    """创建RSS处理器"""
    return RSSProcessor(Path(data_dir))


async def start_rss_processing(rss_url: str, data_dir: str = "./data") -> bool:
    """
    启动RSS处理 - 主要接口函数

    Args:
        rss_url: RSS feed URL
        data_dir: 数据目录路径

    Returns:
        bool: 处理成功返回True
    """
    processor = create_rss_processor(data_dir)

    # 显示服务状态
    status = processor.get_status()
    logger.info(f"RSS处理器启动")
    logger.info(f"数据目录: {status['data_dir']}")
    logger.info(f"数据库: {status['database_path']}")
    logger.info(f"当前状态: {status}")

    # 处理RSS
    result = await processor.process_rss(rss_url)

    if result:
        logger.info("RSS处理完成")
        # 显示更新后的状态
        final_status = processor.get_status()
        logger.info(f"最终状态: {final_status}")
    else:
        logger.error("RSS处理失败")

    return result


def get_rss_status(data_dir: str = "./data") -> dict:
    """获取RSS状态"""
    processor = create_rss_processor(data_dir)
    return processor.get_status()