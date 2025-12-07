#!/usr/bin/env python3
"""
清理脚本 - 清空data目录和数据库

用于测试阶段快速重置环境。

使用方法:
    python scripts/clean_data.py          # 交互式确认
    python scripts/clean_data.py --force  # 强制清理，不确认
"""

import argparse
import shutil
from pathlib import Path


def clean_data(data_dir: Path, force: bool = False) -> None:
    """
    清理data目录

    Args:
        data_dir: data目录路径
        force: 是否跳过确认
    """
    if not data_dir.exists():
        print(f"目录不存在: {data_dir}")
        return

    # 统计要删除的内容
    files = list(data_dir.rglob("*"))
    file_count = len([f for f in files if f.is_file()])
    dir_count = len([f for f in files if f.is_dir()])

    print(f"\n即将删除: {data_dir}")
    print(f"  - 文件数: {file_count}")
    print(f"  - 目录数: {dir_count}")

    if not force:
        confirm = input("\n确认删除? (y/N): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

    # 删除目录内容
    for item in data_dir.iterdir():
        if item.is_file():
            item.unlink()
            print(f"  删除文件: {item.name}")
        elif item.is_dir():
            shutil.rmtree(item)
            print(f"  删除目录: {item.name}/")

    print("\n清理完成!")


def main():
    parser = argparse.ArgumentParser(description="清理data目录和数据库")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
        help="data目录路径 (默认: ./data)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制清理，不需要确认"
    )

    args = parser.parse_args()

    clean_data(args.data_dir, args.force)


if __name__ == "__main__":
    main()
