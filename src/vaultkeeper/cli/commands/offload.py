"""Implementation of 'vk offload' command."""

import logging
from argparse import Namespace

from ...exceptions import OffloadError, VaultKeeperError
from ...utils.helpers import format_bytes
from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_offload(args: Namespace, logger: logging.Logger) -> int:
    """Offload heavy binary files (>50MB or specific target) to cold storage."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    target_arg = getattr(args, "target", None)
    dry_run = getattr(args, "dry_run", False)
    prefix = "[DRY-RUN] " if dry_run else ""

    try:
        res = v.offload(
            target=target_arg,
            dry_run=dry_run,
        )
    except (OffloadError, VaultKeeperError) as exc:
        logger.error("Offload rejected: %s", exc)
        return EXIT_ERROR
    except Exception as exc:
        logger.error("Unexpected error during offload: %s", exc)
        return EXIT_ERROR

    if not res.offloaded_files:
        logger.info("No heavy binary files found matching criteria.")
        return EXIT_SUCCESS

    logger.info(
        "%sOffloaded %d files (Saved: %s):",
        prefix,
        len(res.offloaded_files),
        format_bytes(res.total_bytes_saved),
    )
    for src, dst, size in res.offloaded_files:
        logger.info("  - %s -> %s (%s)", src.name, dst.name, format_bytes(size))

    logger.info("  - Updated notes with external links: %d", res.updated_notes_count)
    if res.tx_id:
        logger.info("  - Transaction ID: %s (reversible with 'vk undo')", res.tx_id)

    return EXIT_SUCCESS
