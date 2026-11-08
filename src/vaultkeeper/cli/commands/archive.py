"""Implementation of 'vk archive' command."""

import logging
from argparse import Namespace

from ...exceptions import ArchiveError, VaultKeeperError
from ...vault import Vault
from ..constants import EXIT_ERROR, EXIT_SUCCESS


def handle_archive(args: Namespace, logger: logging.Logger) -> int:
    """Archive a note or project folder to mirror cold storage with Tombstone support."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    target_arg = getattr(args, "target")
    no_tombstone = getattr(args, "no_tombstone", False)
    dry_run = getattr(args, "dry_run", False)
    prefix = "[DRY-RUN] " if dry_run else ""

    try:
        res = v.archive(
            item_path=target_arg,
            no_tombstone=no_tombstone,
            dry_run=dry_run,
        )
    except (ArchiveError, VaultKeeperError) as exc:
        logger.error("Archive rejected: %s", exc)
        return EXIT_ERROR
    except Exception as exc:
        logger.error("Unexpected error during archive: %s", exc)
        return EXIT_ERROR

    logger.info("%sArchived: %s", prefix, res.source_path.name)
    logger.info("  - Cold storage destination: %s", res.archive_path.as_posix())
    logger.info("  - Tombstone note created: %s", "Yes" if res.tombstone_created else "No")
    if res.summary:
        logger.info("  - Preserved summary: %s", res.summary)
    if res.tx_id:
        logger.info("  - Transaction ID: %s (reversible with 'vk undo')", res.tx_id)

    return EXIT_SUCCESS
