"""File I/O utilities for JSON and audio files."""

from pathlib import Path
from typing import Any

import orjson
from loguru import logger


def read_json(file_path: Path | str) -> dict[str, Any]:
    """Read JSON file using orjson (faster than standard json).

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        orjson.JSONDecodeError: If JSON is invalid
    """
    file_path = Path(file_path)
    logger.debug(f"Reading JSON from {file_path}")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        data = orjson.loads(f.read())

    logger.debug(f"Successfully read {len(str(data))} bytes from {file_path}")
    return data


def write_json(
    data: dict[str, Any], file_path: Path | str, indent: bool = True
) -> None:
    """Write dictionary to JSON file using orjson.

    Args:
        data: Dictionary to write
        file_path: Output file path
        indent: Whether to indent JSON (default: True)

    Raises:
        TypeError: If data is not JSON serializable
    """
    file_path = Path(file_path)
    logger.debug(f"Writing JSON to {file_path}")

    # Create parent directory if it doesn't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # orjson options
    options = orjson.OPT_INDENT_2 if indent else 0

    with open(file_path, "wb") as f:
        f.write(orjson.dumps(data, option=options))

    logger.debug(f"Successfully wrote {len(str(data))} bytes to {file_path}")


def ensure_dir(directory: Path | str) -> Path:
    """Ensure directory exists, create if it doesn't.

    Args:
        directory: Directory path

    Returns:
        Path object of the directory
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_file_size_mb(file_path: Path | str) -> float:
    """Get file size in megabytes.

    Args:
        file_path: File path

    Returns:
        File size in MB

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return round(size_mb, 2)
