"""
Common utilities for voice-rtc-bench packages.

This module provides shared utility functions like logging setup using loguru.
"""

import sys

from loguru import logger


def setup_logging(
    level: str = "INFO",
    format_string: str | None = None,
    use_rich: bool = False,
) -> None:
    """
    Configure logging using loguru.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string (default: loguru's default with timestamp)
        use_rich: Whether to use rich handler for better terminal output (requires rich package)
    """
    # Remove default logger
    logger.remove()

    # Set default format if not provided
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

    # Configure loguru
    if use_rich:
        try:
            from rich.console import Console
            from rich.logging import RichHandler

            # Create console with force_terminal to ensure proper width detection
            console = Console(force_terminal=True, width=120)
            # Use rich handler for enhanced output
            logger.add(
                RichHandler(
                    console=console,
                    rich_tracebacks=True,
                    markup=False,  # Disable markup to prevent formatting issues
                    show_time=False,  # Time already in loguru format
                    show_path=False,  # Path already in loguru format
                ),
                format="{message}",
                level=level.upper(),
            )
        except ImportError:
            # Fall back to standard handler if rich is not available
            logger.add(
                sys.stdout,
                format=format_string,
                level=level.upper(),
                colorize=True,
            )
    else:
        logger.add(
            sys.stdout,
            format=format_string,
            level=level.upper(),
            colorize=True,
        )
