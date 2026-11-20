"""Loguru setup for the m3db command."""
import sys

from loguru import logger

LEVELS = ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR")


def setup_logging(level: str) -> None:
    """Print log messages at LEVEL and above to stderr, one line each."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> <level>{level: <7}</level> {message}",
    )
