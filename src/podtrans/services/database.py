"""
全局数据库管理器

使用SQLite管理所有播客剧集的状态，替代散落的JSON文件。
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from loguru import logger


class DatabaseManager:
    """播客剧集数据库管理器"""

    def __init__(self, db_path: Path):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    podcast_name TEXT NOT NULL,
                    episode_title TEXT NOT NULL,
                    episode_number INTEGER,
                    episode_dir TEXT NOT NULL,
                    audio_url TEXT NOT NULL,
                    audio_path TEXT NOT NULL,
                    publication_date TEXT,
                    description TEXT,
                    duration INTEGER,
                    file_size INTEGER DEFAULT 0,

                    -- 处理状态
                    download_completed BOOLEAN DEFAULT FALSE,
                    download_timestamp TIMESTAMP,
                    asr_completed BOOLEAN DEFAULT FALSE,
                    asr_timestamp TIMESTAMP,
                    asr_result_path TEXT,
                    translation_completed BOOLEAN DEFAULT FALSE,
                    translation_timestamp TIMESTAMP,
                    translation_result_path TEXT,
                    tts_completed BOOLEAN DEFAULT FALSE,
                    tts_timestamp TIMESTAMP,
                    tts_result_path TEXT,
                    current_stage TEXT DEFAULT 'download',

                    -- 错误处理
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    processing BOOLEAN DEFAULT TRUE,

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(podcast_name, episode_title)
                )
            """)

            # 创建索引提高查询性能
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_podcast ON episodes(podcast_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_number ON episodes(episode_number)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_download_completed ON episodes(download_completed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_current_stage ON episodes(current_stage)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_processing ON episodes(processing)")

            logger.info(f"数据库初始化完成: {self.db_path}")

    def create_episode(self,
                      podcast_name: str,
                      episode_title: str,
                      episode_number: Optional[int],
                      episode_dir: str,
                      audio_url: str,
                      audio_path: str,
                      publication_date: Optional[str] = None,
                      description: Optional[str] = None,
                      duration: Optional[int] = None) -> int:
        """
        创建新剧集记录

        Args:
            podcast_name: 播客名称
            episode_title: 剧集标题
            episode_number: 剧集编号
            episode_dir: 剧集目录
            audio_url: 音频URL
            audio_path: 音频文件路径
            publication_date: 发布日期
            description: 描述
            duration: 时长

        Returns:
            剧集ID，如果已存在返回现有ID
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO episodes
                    (podcast_name, episode_title, episode_number, episode_dir,
                     audio_url, audio_path, publication_date, description, duration,
                     current_stage, download_completed, asr_completed, translation_completed, tts_completed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'download', FALSE, FALSE, FALSE, FALSE)
                """, (
                    podcast_name, episode_title, episode_number, episode_dir,
                    audio_url, audio_path, publication_date, description, duration
                ))

                if cursor.rowcount == 0:
                    # 记录已存在，获取现有ID
                    result = conn.execute("""
                        SELECT id FROM episodes
                        WHERE podcast_name = ? AND episode_title = ?
                    """, (podcast_name, episode_title))
                    episode_id = result.fetchone()[0]
                    logger.info(f"剧集已存在，返回现有ID: {episode_id}")
                else:
                    episode_id = cursor.lastrowid
                    logger.info(f"创建新剧集记录: {episode_id}")

                return episode_id

        except sqlite3.Error as e:
            logger.error(f"创建剧集记录失败: {e}")
            return -1

    def get_episode_by_dir(self, episode_dir: str) -> Optional[Dict[str, Any]]:
        """
        根据剧集目录获取剧集信息

        Args:
            episode_dir: 剧集目录

        Returns:
            剧集信息字典，如果不存在返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                result = conn.execute("""
                    SELECT * FROM episodes
                    WHERE episode_dir = ?
                """, (episode_dir,))

                row = result.fetchone()
                if row:
                    return dict(row)
                return None

        except sqlite3.Error as e:
            logger.error(f"获取剧集信息失败: {e}")
            return None

    def update_episode_status(self, episode_id: int, status_updates: Dict[str, Any]) -> bool:
        """
        更新剧集状态

        Args:
            episode_id: 剧集ID
            status_updates: 状态更新内容

        Returns:
            是否更新成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 更新基础状态
                status_fields = [
                    'file_size',
                    'download_completed', 'download_timestamp', 'download_file_size',
                    'asr_completed', 'asr_timestamp', 'asr_result_path',
                    'translation_completed', 'translation_timestamp', 'translation_result_path',
                    'tts_completed', 'tts_timestamp', 'tts_result_path',
                    'current_stage', 'error_count', 'last_error', 'retry_count', 'processing'
                ]

                # 构建SET子句
                set_clauses = []
                values = []

                for field, value in status_updates.items():
                    if field in status_fields:
                        set_clauses.append(f"{field} = ?")
                        values.append(value)

                if set_clauses:
                    # 添加更新时间戳
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(episode_id)

                    sql = f"UPDATE episodes SET {', '.join(set_clauses)} WHERE id = ?"
                    conn.execute(sql, values)

                    logger.debug(f"更新剧集状态 {episode_id}: {status_updates}")
                    return True

                return False

        except sqlite3.Error as e:
            logger.error(f"更新剧集状态失败: {e}")
            return False

    def get_episodes_by_status(self, status_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据状态条件查询剧集

        Args:
            status_filter: 状态过滤条件

        Returns:
            剧集列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # 构建WHERE子句
                where_clauses = []
                values = []

                for field, value in status_filter.items():
                    if field in ['download_completed', 'asr_completed', 'translation_completed',
                               'tts_completed', 'current_stage', 'processing']:
                        where_clauses.append(f"{field} = ?")
                        values.append(value)

                where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

                sql = f"""
                    SELECT * FROM episodes
                    {where_sql}
                    ORDER BY created_at DESC
                """

                result = conn.execute(sql, values)
                return [dict(row) for row in result.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"查询剧集列表失败: {e}")
            return []

    def get_pending_episodes(self, stage: str = 'download') -> List[Dict[str, Any]]:
        """
        获取待处理的剧集

        Args:
            stage: 处理阶段 ('download', 'asr', 'translation', 'tts')

        Returns:
            待处理剧集列表
        """
        stage_mapping = {
            'download': ('download_completed', False),
            'asr': ('download_completed', True),
            'translation': ('asr_completed', True),
            'tts': ('translation_completed', True)
        }

        if stage not in stage_mapping:
            return []

        field, value = stage_mapping[stage]

        status_filter = {
            field: value,
            f'{stage}_completed': False
        }

        return self.get_episodes_by_status(status_filter)

    def get_statistics(self) -> Dict[str, int]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                stats = {}

                # 总剧集数
                result = conn.execute("SELECT COUNT(*) FROM episodes")
                stats['total_episodes'] = result.fetchone()[0]

                # 各阶段完成数量
                stages = ['download_completed', 'asr_completed', 'translation_completed', 'tts_completed']
                for stage in stages:
                    result = conn.execute(f"SELECT COUNT(*) FROM episodes WHERE {stage} = 1")
                    stats[stage] = result.fetchone()[0]

                # 处理中的数量
                result = conn.execute("SELECT COUNT(*) FROM episodes WHERE processing = 1")
                stats['processing'] = result.fetchone()[0]

                return stats

        except sqlite3.Error as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def cleanup_old_episodes(self, days: int = 30) -> int:
        """
        清理旧剧集记录

        Args:
            days: 保留天数

        Returns:
            清理的记录数
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute("""
                    DELETE FROM episodes
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))

                deleted_count = result.rowcount
                logger.info(f"清理了 {deleted_count} 条旧剧集记录")
                return deleted_count

        except sqlite3.Error as e:
            logger.error(f"清理旧记录失败: {e}")
            return 0

    def get_episode_by_title(self, episode_title: str, podcast_name: str) -> Optional[Dict[str, Any]]:
        """
        根据剧集标题获取剧集信息

        Args:
            episode_title: 剧集标题
            podcast_name: 播客名称

        Returns:
            剧集信息字典，如果不存在返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                result = conn.execute("""
                    SELECT * FROM episodes
                    WHERE episode_title = ? AND podcast_name = ?
                """, (episode_title, podcast_name))

                row = result.fetchone()
                if row:
                    return dict(row)
                return None

        except sqlite3.Error as e:
            logger.error(f"获取剧集信息失败: {e}")
            return None