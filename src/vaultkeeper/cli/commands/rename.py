"""Implementation of 'vk rename' command."""

import logging
from argparse import Namespace

from ...exceptions import NamingError, VaultKeeperError
from ...vault import Vault
from ..constants import EXIT_ERROR, EXIT_SUCCESS


def handle_rename(args: Namespace, logger: logging.Logger) -> int:
    """Rename a note or asset with global wikilink refactoring and index synchronization."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    file_arg = getattr(args, "file")
    new_name_arg = getattr(args, "new_name")
    skip_links = getattr(args, "skip_links", False)
    dry_run = getattr(args, "dry_run", False)
    prefix = "[DRY-RUN] " if dry_run else ""

    try:
        res = v.rename(
            old_path=file_arg,
            new_name=new_name_arg,
            skip_links=skip_links,
            dry_run=dry_run,
        )
    except (NamingError, VaultKeeperError) as exc:
        logger.error("Rename rejected: %s", exc)
        return EXIT_ERROR
    except Exception as exc:
        logger.error("Unexpected error during rename: %s", exc)
        return EXIT_ERROR

    if res.old_path == res.new_path:
        logger.info("Source and target names are identical. No changes required.")
        return EXIT_SUCCESS

    logger.info("%sRenamed: %s -> %s", prefix, res.old_path.name, res.new_path.name)
    logger.info("  - Updated incoming wikilinks: %d", res.updated_links_count)
    logger.info("  - Folder index synchronized: %s", "Yes" if res.index_updated else "No")
    if res.tx_id:
        logger.info("  - Transaction ID: %s (reversible with 'vk undo')", res.tx_id)

    return EXIT_SUCCESS
