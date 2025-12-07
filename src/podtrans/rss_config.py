"""
RSS配置管理模块

负责读取和管理RSS配置文件（TOML格式）。
"""

import tomli
import tomli_w
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from loguru import logger


class RSSFeedConfig(BaseModel):
    """单个RSS feed的配置"""
    name: str = Field(..., description="播客名称")
    url: str = Field(..., description="RSS feed URL")
    enabled: bool = Field(True, description="是否启用此feed")
    download_mode: str = Field("latest", description="下载模式: latest(最新N集) 或 all(全部)")
    download_count: Optional[int] = Field(1, description="下载数量，仅在download_mode=latest时有效")

    @field_validator('download_mode')
    @classmethod
    def validate_download_mode(cls, v):
        if v not in ['latest', 'all']:
            raise ValueError('download_mode必须是 "latest" 或 "all"')
        return v

    @field_validator('download_count')
    @classmethod
    def validate_download_count(cls, v, info):
        # 注意: Pydantic v2 中使用 info.data 访问其他字段
        if info.data.get('download_mode') == 'latest' and (v is None or v < 1):
            raise ValueError('download_mode=latest时，download_count必须≥1')
        return v


class GlobalSettings(BaseModel):
    """全局设置"""
    data_dir: str = Field("./data", description="数据目录")
    min_file_size_mb: float = Field(1.0, description="最小文件大小(MB)")
    download_timeout: int = Field(300, description="下载超时时间(秒)")
    max_retries: int = Field(3, description="最大重试次数")


class RSSConfig(BaseModel):
    """RSS配置"""
    rss_feeds: List[RSSFeedConfig] = Field(default_factory=list, description="RSS feed列表")
    global_settings: GlobalSettings = Field(default_factory=GlobalSettings, description="全局设置")

    def get_enabled_feeds(self) -> List[RSSFeedConfig]:
        """获取所有启用的feeds"""
        return [feed for feed in self.rss_feeds if feed.enabled]

    def get_feed_by_name(self, name: str) -> Optional[RSSFeedConfig]:
        """根据名称获取feed"""
        for feed in self.rss_feeds:
            if feed.name == name:
                return feed
        return None

    def get_feed_by_url(self, url: str) -> Optional[RSSFeedConfig]:
        """根据URL获取feed"""
        for feed in self.rss_feeds:
            if feed.url == url:
                return feed
        return None


class RSSConfigManager:
    """RSS配置管理器"""

    def __init__(self, config_path: Path = Path("./rss_config.toml")):
        self.config_path = Path(config_path)
        self.config: Optional[RSSConfig] = None

    def load_config(self) -> RSSConfig:
        """
        加载配置文件（TOML格式）

        Returns:
            RSSConfig: 配置对象
        """
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            logger.info("使用默认配置")
            self.config = RSSConfig()
            return self.config

        try:
            with open(self.config_path, 'rb') as f:
                config_data = tomli.load(f)

            self.config = RSSConfig(**config_data)
            logger.info(f"配置加载成功: {self.config_path}")
            logger.info(f"已启用的feeds: {len(self.config.get_enabled_feeds())}/{len(self.config.rss_feeds)}")

            return self.config

        except tomli.TOMLDecodeError as e:
            logger.error(f"配置文件TOML格式错误: {e}")
            raise
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            raise

    def save_config(self, config: RSSConfig) -> bool:
        """
        保存配置文件（TOML格式）

        Args:
            config: 配置对象

        Returns:
            bool: 保存成功返回True
        """
        try:
            with open(self.config_path, 'wb') as f:
                tomli_w.dump(config.model_dump(), f)

            logger.info(f"配置保存成功: {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"配置保存失败: {e}")
            return False

    def create_example_config(self, output_path: Optional[Path] = None) -> bool:
        """
        创建示例配置文件（TOML格式）

        Args:
            output_path: 输出路径，默认为 rss_config.example.toml

        Returns:
            bool: 创建成功返回True
        """
        if output_path is None:
            output_path = self.config_path.parent / "rss_config.example.toml"

        # 直接写入带注释的TOML内容
        toml_content = """# RSS模块配置文件
# 支持配置多个RSS源，设置下载模式和全局参数

# ============================================
# 全局设置
# ============================================
[global_settings]
# 数据存储目录
data_dir = "./data"

# 最小文件大小（MB），小于此值视为下载失败
min_file_size_mb = 1.0

# 下载超时时间（秒）
download_timeout = 300

# 最大重试次数
max_retries = 3


# ============================================
# RSS Feeds 配置
# ============================================

# 示例1：下载最新的3集
[[rss_feeds]]
name = "All-In Podcast"
url = "https://feeds.simplecast.com/54nAGcIl"
enabled = true
download_mode = "latest"  # 可选值: "latest" 或 "all"
download_count = 3        # 仅在 download_mode = "latest" 时有效

# 示例2：下载全部剧集（已禁用）
[[rss_feeds]]
name = "Example Podcast"
url = "https://example.com/feed.xml"
enabled = false
download_mode = "all"
# download_count 在 mode="all" 时无效，可以省略

# 你可以继续添加更多RSS源
# [[rss_feeds]]
# name = "Another Podcast"
# url = "https://another.example.com/rss"
# enabled = true
# download_mode = "latest"
# download_count = 5
"""

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(toml_content)

            logger.info(f"示例配置创建成功: {output_path}")
            return True

        except Exception as e:
            logger.error(f"示例配置创建失败: {e}")
            return False


# 单例模式获取配置
_config_manager: Optional[RSSConfigManager] = None


def get_rss_config_manager(config_path: Path = Path("./rss_config.toml")) -> RSSConfigManager:
    """获取RSS配置管理器（单例）"""
    global _config_manager
    if _config_manager is None:
        _config_manager = RSSConfigManager(config_path)
    return _config_manager


def load_rss_config(config_path: Path = Path("./rss_config.toml")) -> RSSConfig:
    """快捷方法：加载RSS配置"""
    manager = get_rss_config_manager(config_path)
    return manager.load_config()
