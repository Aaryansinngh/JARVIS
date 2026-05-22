"""
utils/logger.py — Centralised logging for Jarvis
Uses loguru for structured, colourful logs.
"""
import sys
from pathlib import Path
from loguru import logger


def setup_logger(debug: bool = False, log_file: str = "./data/jarvis.log") -> None:
    """Configure the global logger. Call once at startup."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger.remove()  # Remove default handler

    # Console: clean, colourful
    level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> — <level>{message}</level>",
    )

    # File: full details with rotation
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
    )

    logger.info("Logger initialised.")


# Export the configured logger
__all__ = ["logger", "setup_logger"]
