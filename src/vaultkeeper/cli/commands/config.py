"""Implementation of 'vk config' command: show, set."""

import logging
from argparse import Namespace

from ...exceptions import ConfigurationError, VaultKeeperError
from ...utils.formatters import format_output
from ...vault import Vault
from ..constants import EXIT_ERROR, EXIT_SUCCESS


def handle_config(args: Namespace, logger: logging.Logger) -> int:
    """Inspect and update vault configuration directives."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    action = getattr(args, "config_action", None)
    if not action:
        logger.error("No config action specified. Choose from: show, set.")
        return EXIT_ERROR

    if action == "show":
        fmt = getattr(args, "format", "yaml")
        cfg_dict = v.config_show()
        rendered = format_output(cfg_dict, format=fmt, title="Vault Configuration")
        print(rendered)
        return EXIT_SUCCESS

    if action == "set":
        key = getattr(args, "key")
        value = getattr(args, "value")
        dry_run = getattr(args, "dry_run", False)
        prefix = "[DRY-RUN] " if dry_run else ""

        try:
            v.config_set(key=key, value=value, dry_run=dry_run)
        except (ConfigurationError, VaultKeeperError) as exc:
            logger.error("Failed to set configuration: %s", exc)
            return EXIT_ERROR

        logger.info("%sConfiguration updated: %s = %s", prefix, key, value)
        return EXIT_SUCCESS

    logger.error("Unknown config action: %s", action)
    return EXIT_ERROR
