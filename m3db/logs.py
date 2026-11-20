"""Loguru setup for the m3db command, and timing of load phases."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

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


@contextmanager
def phase(name: str) -> Iterator[None]:
    """Log at DEBUG level how long the with-block took, as "NAME in 0.12 s"."""
    start = perf_counter()
    yield
    logger.debug(f"{name} in {perf_counter() - start:.2f} s")


def counted(count: int, singular: str, plural: str | None = None) -> str:
    """Return COUNT with the noun that fits it, as "1 tagging" or "1,200 taggings"."""
    noun = singular if count == 1 else (plural or singular + "s")
    return f"{count:,} {noun}"
