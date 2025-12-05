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
    rss_url: str = Option(..., "--rss", "-r", help="RSS feed URL"),
    data_dir: str = Option("./data", "--data-dir", "-d", help="数据目录路径")
):
    """处理RSS feed，下载最新剧集"""
    print(f"RSS处理开始: {rss_url}")
    print(f"数据目录: {data_dir}")
    print("-" * 50)

    result = asyncio.run(start_rss_processing(rss_url, data_dir))

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


if __name__ == "__main__":
    app()