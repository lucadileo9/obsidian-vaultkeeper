"""Implementation of 'vk clean-attachments' command."""

import logging
from argparse import Namespace

from ...utils.helpers import format_bytes
from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_attachments(args: Namespace, logger: logging.Logger) -> int:
    """Clean orphan attachments by moving them to .trash or hard-deleting."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    dry_run = getattr(args, "dry_run", False)
    hard_delete = getattr(args, "hard_delete", False)
    target = getattr(args, "target", None)

    prefix = "[DRY-RUN] " if dry_run else ""
    action_name = "Hard delete" if hard_delete else "Soft delete to .trash"

    logger.info("%sExecuting attachment cleanup in: %s", prefix, v.root)
    orphans = v.find_orphans(target=target)

    if not orphans:
        logger.info("No orphan attachments found.")
        return EXIT_SUCCESS

    logger.info("Found %d orphan attachments:", len(orphans))
    total_bytes = sum(o.size_bytes for o in orphans)
    for o in orphans:
        logger.info("  - %s (%s)", o.rel_path.as_posix(), format_bytes(o.size_bytes))

    results = v.clean_attachments(target=target, hard_delete=hard_delete, dry_run=dry_run)
    logger.info("%sCompleted %s for %d files (Total space: %s).", prefix, action_name, len(results), format_bytes(total_bytes))
    return EXIT_SUCCESS
