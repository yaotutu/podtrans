#!/usr/bin/env python3
"""
RSS模块CLI入口

提供简单的命令行接口来调用RSS模块。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.podtrans.rss import start_rss_processing, get_rss_status
from typer import Typer, Option

app = Typer()


@app.command()
def process(
    rss_url: str = Option(None, "--rss", "-r", help="RSS feed URL (可选，未指定则使用配置文件)"),
    config_path: str = Option("./rss_config.toml", "--config", "-c", help="配置文件路径"),
    data_dir: str = Option("./data", "--data-dir", "-d", help="数据目录路径"),
    download_mode: str = Option("latest", "--mode", "-m", help="下载模式: latest 或 all"),
    download_count: int = Option(1, "--count", "-n", help="下载数量（仅在mode=latest时有效）")
):
    """处理RSS feed，下载剧集

    两种使用方式：
    1. 命令行指定RSS URL：下载指定的RSS feed
    2. 不指定URL：从配置文件读取并处理所有启用的feeds
    """
    if rss_url:
        print(f"RSS处理开始: {rss_url}")
        print(f"下载模式: {download_mode}")
        print(f"下载数量: {download_count if download_mode == 'latest' else '全部'}")
    else:
        print(f"从配置文件读取RSS feeds: {config_path}")

    print(f"数据目录: {data_dir}")
    print("-" * 50)

    result = asyncio.run(start_rss_processing(
        rss_url=rss_url,
        data_dir=data_dir,
        config_path=config_path,
        download_mode=download_mode,
        download_count=download_count
    ))

    if result:
        print("\n✅ RSS处理成功!")
    else:
        print("\n❌ RSS处理失败!")
        sys.exit(1)


@app.command()
def status(data_dir: str = Option("./data", "--data-dir", "-d", help="数据目录路径")):
    """查看RSS状态"""
    status_info = get_rss_status(data_dir)

    print("\n=== RSS模块状态 ===")
    print(f"数据目录: {status_info['data_dir']}")
    print(f"数据库: {status_info['database_path']}")
    print(f"总剧集数: {status_info['total_episodes']}")
    print(f"已下载: {status_info['download_completed']}")
    print(f"处理中: {status_info['processing']}")


@app.command()
def init_config(
    output_path: str = Option("./rss_config.toml", "--output", "-o", help="配置文件输出路径")
):
    """生成配置文件示例（TOML格式）"""
    from src.podtrans.rss_config import RSSConfigManager
    from pathlib import Path

    manager = RSSConfigManager()
    if manager.create_example_config(Path(output_path)):
        print(f"✅ 配置文件示例已生成: {output_path}")
        print("\n请编辑配置文件，填入你的RSS源信息")
        print("TOML格式支持注释，方便理解和修改")
    else:
        print(f"❌ 配置文件生成失败")
        sys.exit(1)


if __name__ == "__main__":
    app()