"""ANSI colored console logging and plain text logfile formatters for the CLI."""

import logging
import re
import sys
from pathlib import Path
from typing import Optional

# ANSI Color escape sequences
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"

ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class StripAnsiFormatter(logging.Formatter):
    """Logging formatter that strips ANSI color codes for clean plain-text log files."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        return ANSI_ESCAPE_PATTERN.sub("", text)


class ColoredConsoleFormatter(logging.Formatter):
    """Console formatter adding ANSI color tags based on log severity level."""

    LEVEL_COLORS = {
        logging.DEBUG: COLOR_DIM,
        logging.INFO: "",
        logging.WARNING: COLOR_YELLOW,
        logging.ERROR: COLOR_RED,
        logging.CRITICAL: COLOR_RED + COLOR_BOLD,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        message = super().format(record)
        if color:
            return f"{color}{message}{COLOR_RESET}"
        return message


def setup_cli_logger(
    name: str = "vaultkeeper",
    verbose: bool = False,
    quiet: bool = False,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """Configure and return a standardized CLI logger with colored console output."""
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
    logger.handlers.clear()
    logger.propagate = False

    if quiet:
        console_level = logging.ERROR
    elif verbose:
        console_level = logging.DEBUG
    else:
        console_level = logging.INFO

    logger.setLevel(logging.DEBUG)

    # 1. Console Handler (Colored, writes to sys.stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_formatter = ColoredConsoleFormatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Optional, Strips ANSI, timestamped)
    if log_file:
        file_path = Path(log_file).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = StripAnsiFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def close_cli_logger(logger: Optional[logging.Logger] = None) -> None:
    """Close and flush all handlers attached to the logger."""
    target = logger or logging.getLogger("vaultkeeper")
    for handler in list(target.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        target.removeHandler(handler)
