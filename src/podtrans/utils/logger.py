"""Logging configuration using Loguru.

This module provides a centralized logging system with:
- Colored console output for better readability
- JSON file output for structured logging
- Automatic log rotation
- Different log levels for console and file
"""

import sys

from loguru import logger

from podtrans.config import get_settings


def setup_logger() -> None:
    """Setup Loguru logger with console and file handlers.

    Console:
    - Colored output
    - Human-readable format
    - Configurable log level from settings

    File:
    - JSON format for structured logging
    - Automatic rotation (500 MB)
    - 10 days retention
    - Always INFO level or higher
    """
    # Remove default handler
    logger.remove()

    settings = get_settings()

    # Console handler (colored, human-readable)
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
    )

    # File handler (JSON, structured)
    log_file = settings.log_dir / "podtrans_{time:YYYY-MM-DD}.log"
    logger.add(
        log_file,
        format="{time} | {level} | {name}:{function}:{line} | {message}",
        level="INFO",  # Always INFO or higher for file logs
        rotation="500 MB",  # Rotate when file reaches 500 MB
        retention="10 days",  # Keep logs for 10 days
        compression="zip",  # Compress rotated logs
        serialize=False,  # Use plain text format (easier to read than JSON for now)
        enqueue=True,  # Async logging
    )

    logger.info("Logger initialized")
    logger.debug(f"Log level: {settings.log_level}")
    logger.debug(f"Log directory: {settings.log_dir}")


def get_logger(name: str | None = None):
    """Get a logger instance.

    Args:
        name: Logger name (usually __name__). If None, returns root logger.

    Returns:
        Logger instance configured by setup_logger()

    Example:
        >>> from podtrans.utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    if name:
        return logger.bind(name=name)
    return logger


# Initialize logger on module import
setup_logger()
