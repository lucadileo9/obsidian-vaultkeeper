"""Implementation of 'vk generate-indices' command."""

import logging
from argparse import Namespace

from ...vault import Vault
from ..constants import EXIT_ERROR, EXIT_SUCCESS


def handle_indices(args: Namespace, logger: logging.Logger) -> int:
    """Generate or update MOC index files for vault directories."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    dry_run = getattr(args, "dry_run", False)
    target = getattr(args, "target", None)
    recursive = getattr(args, "all", False)
    prefix = "[DRY-RUN] " if dry_run else ""

    logger.info("%sGenerating folder indices (Pattern: %s)", prefix, v.config.index_naming_pattern)
    results = v.generate_indices(target=target, recursive=recursive, dry_run=dry_run)

    created_count = sum(1 for _, changed in results if changed)
    for idx_path, changed in results:
        status_str = "CREATED/UPDATED" if changed else "UNCHANGED"
        logger.info("  - %s: %s", idx_path.name, status_str)

    logger.info("%sFinished index generation. %d files modified.", prefix, created_count)
    return EXIT_SUCCESS
