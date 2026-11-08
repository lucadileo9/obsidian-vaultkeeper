"""Implementation of 'vk move' command."""

import logging
from argparse import Namespace

from ...exceptions import LifecycleError, VaultKeeperError
from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_move(args: Namespace, logger: logging.Logger) -> int:
    """Move a file or folder into a different Johnny.Decimal directory."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    target_arg = getattr(args, "target")
    dest_arg = getattr(args, "destination")
    dry_run = getattr(args, "dry_run", False)
    prefix = "[DRY-RUN] " if dry_run else ""

    try:
        res = v.move(
            source_path=target_arg,
            dest_folder=dest_arg,
            dry_run=dry_run,
        )
    except (LifecycleError, VaultKeeperError) as exc:
        logger.error("Move rejected: %s", exc)
        return EXIT_ERROR
    except Exception as exc:
        logger.error("Unexpected error during move: %s", exc)
        return EXIT_ERROR

    logger.info("%sMoved: %s -> %s", prefix, res.source_path.name, res.dest_path.parent.name)
    logger.info("  - Source folder index updated: %s", "Yes" if res.old_index_updated else "No")
    logger.info("  - Destination folder index updated: %s", "Yes" if res.new_index_updated else "No")
    if res.tx_id:
        logger.info("  - Transaction ID: %s (reversible with 'vk undo')", res.tx_id)

    return EXIT_SUCCESS
