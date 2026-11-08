"""Implementation of 'vk init' command."""

import logging
from argparse import Namespace
from pathlib import Path

from ...config import generate_default_config_content
from ..constants import EXIT_ERROR, EXIT_SUCCESS


def handle_init(args: Namespace, logger: logging.Logger) -> int:
    """Generate default vault.toml configuration file in target directory."""
    target_dir = Path(args.target).resolve() if getattr(args, "target", None) else Path.cwd().resolve()

    if not target_dir.is_dir():
        logger.error("Target path is not a directory: %s", target_dir)
        return EXIT_ERROR

    dest = target_dir / "vault.toml"
    if dest.exists() and not getattr(args, "force", False):
        logger.error("Configuration file already exists: %s (use --force to overwrite)", dest)
        return EXIT_ERROR

    content = generate_default_config_content(target_dir)
    dest.write_text(content, encoding="utf-8")
    logger.info("Initialized configuration file at: %s", dest)
    return EXIT_SUCCESS
