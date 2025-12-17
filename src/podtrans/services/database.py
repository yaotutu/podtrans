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

    def __init__(self, db_path: Path, init_db: bool = True, migrate: bool = True):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
            init_db: 是否初始化数据库表结构（默认True）
                     - True: RSS模块首次创建数据库时使用
                     - False: 其他模块只读写时使用
            migrate: 是否运行数据库迁移（默认True）
        """
        self.db_path = Path(db_path)
        if init_db:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_database()
        elif migrate and self.db_path.exists():
            # 运行迁移以添加新字段
            self._migrate_database()
            # 运行翻译片段相关迁移
            self._migrate_translation_segments()

    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    podcast_name TEXT NOT NULL,
                    episode_title TEXT NOT NULL,
                    episode_guid TEXT NOT NULL UNIQUE,
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
                    -- Convert stage (format conversion)
                    convert_completed BOOLEAN DEFAULT FALSE,
                    convert_timestamp TIMESTAMP,
                    convert_result_path TEXT,
                    convert_format TEXT,

                    -- TTS stage (audio generation)
                    tts_completed BOOLEAN DEFAULT FALSE,
                    tts_timestamp TIMESTAMP,
                    tts_result_path TEXT,

                    -- ASR 结果切分相关
                    asr_split_completed BOOLEAN DEFAULT FALSE,
                    asr_split_timestamp TIMESTAMP,
                    asr_segment_count INTEGER DEFAULT 1,
                    asr_split_metadata TEXT,

                    -- 错误处理
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    processing BOOLEAN DEFAULT TRUE,

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引提高查询性能
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_podcast ON episodes(podcast_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_guid ON episodes(episode_guid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_download_completed ON episodes(download_completed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_asr_completed ON episodes(asr_completed)")

            logger.info(f"数据库初始化完成: {self.db_path}")

    def _migrate_database(self):
        """迁移数据库以添加新字段"""
        with sqlite3.connect(self.db_path) as conn:
            # 检查 asr_split_completed 字段是否存在
            cursor = conn.execute("""
                PRAGMA table_info(episodes)
            """)
            columns = {row[1] for row in cursor.fetchall()}

            # 添加缺失的字段
            if 'asr_split_completed' not in columns:
                logger.info("迁移数据库：添加 ASR 切分相关字段")
                conn.execute("""
                    ALTER TABLE episodes
                    ADD COLUMN asr_split_completed BOOLEAN DEFAULT FALSE
                """)
                conn.execute("""
                    ALTER TABLE episodes
                    ADD COLUMN asr_split_timestamp TIMESTAMP
                """)
                conn.execute("""
                    ALTER TABLE episodes
                    ADD COLUMN asr_segment_count INTEGER DEFAULT 1
                """)
                conn.execute("""
                    ALTER TABLE episodes
                    ADD COLUMN asr_split_metadata TEXT
                """)
                logger.info("数据库迁移完成")

    def _migrate_translation_segments(self):
        """迁移数据库以添加翻译片段支持"""
        with sqlite3.connect(self.db_path) as conn:
            # 检查表是否已存在
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='translation_segments'
            """)

            if cursor.fetchone() is None:
                logger.info("迁移数据库：添加 translation_segments 表")

                # 创建 translation_segments 表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS translation_segments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        episode_id INTEGER NOT NULL,
                        segment_id TEXT NOT NULL,
                        segment_index INTEGER NOT NULL,
                        asr_result_path TEXT NOT NULL,
                        translation_completed BOOLEAN DEFAULT FALSE,
                        translation_timestamp TIMESTAMP,
                        translation_result_path TEXT,
                        error_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        retry_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (episode_id) REFERENCES episodes(id),
                        UNIQUE(episode_id, segment_id)
                    )
                """)

                # 创建索引
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_translation_segments_episode
                    ON translation_segments(episode_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_translation_segments_status
                    ON translation_segments(translation_completed)
                """)

                logger.info("translation_segments 表创建完成")

            # 检查并添加 episodes 表的新字段
            cursor = conn.execute("""
                PRAGMA table_info(episodes)
            """)
            columns = {row[1] for row in cursor.fetchall()}

            # 添加缺失的字段
            if 'translation_segment_count' not in columns:
                logger.info("添加翻译片段相关字段到 episodes 表")
                conn.execute("""
                    ALTER TABLE episodes
                    ADD COLUMN translation_segment_count INTEGER DEFAULT 0
                """)
                conn.execute("""
                    ALTER TABLE episodes
                    ADD COLUMN translation_segments_completed INTEGER DEFAULT 0
                """)
                conn.execute("""
                    ALTER TABLE episodes
                    ADD COLUMN translation_segments_mode BOOLEAN DEFAULT FALSE
                """)
                logger.info("episodes 表字段添加完成")

    def create_episode(self,
                      podcast_name: str,
                      episode_title: str,
                      episode_guid: str,
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
            episode_guid: RSS GUID（唯一标识符）
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
                    (podcast_name, episode_title, episode_guid, episode_dir,
                     audio_url, audio_path, publication_date, description, duration,
                     download_completed, asr_completed, translation_completed, tts_completed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE, FALSE, FALSE, FALSE)
                """, (
                    podcast_name, episode_title, episode_guid, episode_dir,
                    audio_url, audio_path, publication_date, description, duration
                ))

                if cursor.rowcount == 0:
                    # 记录已存在，获取现有ID
                    result = conn.execute("""
                        SELECT id FROM episodes
                        WHERE episode_guid = ?
                    """, (episode_guid,))
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
                stages = [
                    'download_completed', 'asr_completed', 'translation_completed',
                    'tts_completed'
                ]
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

    def get_episode_by_guid(self, episode_guid: str) -> Optional[Dict[str, Any]]:
        """
        根据GUID获取剧集信息

        Args:
            episode_guid: RSS GUID

        Returns:
            剧集信息字典，如果不存在返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                result = conn.execute("""
                    SELECT * FROM episodes
                    WHERE episode_guid = ?
                """, (episode_guid,))

                row = result.fetchone()
                if row:
                    return dict(row)
                return None

        except sqlite3.Error as e:
            logger.error(f"获取剧集信息失败: {e}")
            return None

    # ==================== Translation Segments Methods ====================

    def create_translation_segments(self, episode_id: int, segments: List[Dict[str, Any]]) -> bool:
        """
        批量创建翻译片段记录

        Args:
            episode_id: 剧集ID
            segments: 片段信息列表，每个包含 segment_id, segment_index, asr_result_path

        Returns:
            是否创建成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 更新剧集的片段模式标记和计数
                conn.execute("""
                    UPDATE episodes
                    SET
                        translation_segments_mode = TRUE,
                        translation_segment_count = ?,
                        translation_segments_completed = 0
                    WHERE id = ?
                """, (len(segments), episode_id))

                # 插入片段记录
                for segment in segments:
                    conn.execute("""
                        INSERT OR REPLACE INTO translation_segments
                        (episode_id, segment_id, segment_index, asr_result_path, created_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        episode_id,
                        segment["segment_id"],
                        segment["segment_index"],
                        str(segment["asr_result_path"])
                    ))

                logger.info(f"创建了 {len(segments)} 个翻译片段记录")
                return True

        except sqlite3.Error as e:
            logger.error(f"创建翻译片段记录失败: {e}")
            return False

    def get_pending_translation_segments(self, episode_id: int = None) -> List[Dict[str, Any]]:
        """
        获取待翻译的片段列表

        Args:
            episode_id: 剧集ID，如果为None则获取所有待翻译的片段

        Returns:
            待翻译的片段信息列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                if episode_id:
                    result = conn.execute("""
                        SELECT ts.*, e.episode_title, e.episode_dir
                        FROM translation_segments ts
                        JOIN episodes e ON ts.episode_id = e.id
                        WHERE ts.episode_id = ? AND ts.translation_completed = FALSE
                        ORDER BY ts.episode_id, ts.segment_index
                    """, (episode_id,))
                else:
                    result = conn.execute("""
                        SELECT ts.*, e.episode_title, e.episode_dir
                        FROM translation_segments ts
                        JOIN episodes e ON ts.episode_id = e.id
                        WHERE ts.translation_completed = FALSE
                        ORDER BY ts.episode_id, ts.segment_index
                    """)

                return [dict(row) for row in result.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"获取待翻译片段失败: {e}")
            return []

    def update_translation_segment_status(
        self,
        segment_id: str,
        episode_id: int,
        status_data: Dict[str, Any]
    ) -> bool:
        """
        更新片段翻译状态

        Args:
            segment_id: 片段ID
            episode_id: 剧集ID
            status_data: 状态更新数据

        Returns:
            是否更新成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 更新片段状态
                fields = []
                values = []

                if "translation_completed" in status_data:
                    fields.append("translation_completed = ?")
                    values.append(status_data["translation_completed"])

                if "translation_result_path" in status_data:
                    fields.append("translation_result_path = ?")
                    # Convert Path to string if necessary
                    path_value = status_data["translation_result_path"]
                    if isinstance(path_value, Path):
                        path_value = str(path_value)
                    values.append(path_value)

                if "error_count" in status_data:
                    fields.append("error_count = ?")
                    values.append(status_data["error_count"])

                if "last_error" in status_data:
                    fields.append("last_error = ?")
                    values.append(status_data["last_error"])

                if "retry_count" in status_data:
                    fields.append("retry_count = ?")
                    values.append(status_data["retry_count"])

                # 添加时间戳和标识符
                fields.append("updated_at = CURRENT_TIMESTAMP")
                values.extend([segment_id, episode_id])

                query = f"""
                    UPDATE translation_segments
                    SET {', '.join(fields)}
                    WHERE segment_id = ? AND episode_id = ?
                """
                conn.execute(query, values)

                # 更新剧集级别的翻译进度
                conn.execute("""
                    UPDATE episodes
                    SET translation_segments_completed = (
                        SELECT COUNT(*)
                        FROM translation_segments
                        WHERE episode_id = ? AND translation_completed = TRUE
                    )
                    WHERE id = ?
                """, (episode_id, episode_id))

                return True

        except sqlite3.Error as e:
            logger.error(f"更新片段翻译状态失败: {e}")
            return False

    def get_translation_progress(self, episode_id: int) -> Dict[str, Any]:
        """
        获取剧集的翻译进度

        Args:
            episode_id: 剧集ID

        Returns:
            翻译进度信息
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # 获取剧集基本信息
                episode = conn.execute("""
                    SELECT translation_segment_count, translation_segments_completed
                    FROM episodes
                    WHERE id = ?
                """, (episode_id,)).fetchone()

                if not episode:
                    return {"error": "Episode not found"}

                # 获取片段统计
                stats = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN translation_completed = TRUE THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN translation_completed = FALSE THEN 1 ELSE 0 END) as pending,
                        SUM(error_count) as total_errors
                    FROM translation_segments
                    WHERE episode_id = ?
                """, (episode_id,)).fetchone()

                return {
                    "episode_id": episode_id,
                    "segment_count": episode["translation_segment_count"],
                    "segments_completed": episode["translation_segments_completed"],
                    "total_segments": stats["total"] or 0,
                    "completed_segments": stats["completed"] or 0,
                    "pending_segments": stats["pending"] or 0,
                    "total_errors": stats["total_errors"] or 0,
                    "progress_percentage": (
                        (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
                    )
                }

        except sqlite3.Error as e:
            logger.error(f"获取翻译进度失败: {e}")
            return {"error": str(e)}