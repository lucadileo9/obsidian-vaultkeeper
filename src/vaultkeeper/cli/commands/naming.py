"""Implementation of 'vk normalize-names' command."""

import logging
from argparse import Namespace

from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_naming(args: Namespace, logger: logging.Logger) -> int:
    """Normalize file names according to configured naming strategy and sync wikilinks."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    dry_run = getattr(args, "dry_run", False)
    target = getattr(args, "target", None)
    prefix = "[DRY-RUN] " if dry_run else ""

    logger.info("%sExecuting naming normalization (Style: %s)", prefix, v.config.naming_style)
    results = v.normalize_names(target=target, dry_run=dry_run)

    if not results:
        logger.info("All files and directories already comply with naming conventions.")
        return EXIT_SUCCESS

    logger.info("%sNormalized %d files:", prefix, len(results))
    total_links = 0
    for old_p, new_p, links_count in results:
        total_links += links_count
        logger.info("  - %s -> %s (Updated %d incoming links)", old_p.name, new_p.name, links_count)

    logger.info("%sFinished normalization. Total synchronized wikilinks: %d", prefix, total_links)
    return EXIT_SUCCESS
