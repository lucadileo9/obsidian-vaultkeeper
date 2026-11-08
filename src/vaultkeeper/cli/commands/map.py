"""Implementation of 'vk map' command."""

import logging
from argparse import Namespace

from ...exceptions import VaultKeeperError
from ...utils.formatters import format_output
from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_map(args: Namespace, logger: logging.Logger) -> int:
    """Generate high-level Johnny.Decimal area telemetry and master vault map."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    output_arg = getattr(args, "output", None)
    fmt = getattr(args, "format", "md")

    try:
        report, written_path = v.vault_map(output_file=output_arg)
    except VaultKeeperError as exc:
        logger.error("Failed to generate vault map: %s", exc)
        return EXIT_ERROR

    if written_path:
        logger.info("Master MOC map written to: %s", written_path.as_posix())

    if fmt == "md":
        from ...core.map import VaultMapEngine

        rendered = VaultMapEngine(v.config).render_markdown_map(report)
        print(rendered)
    else:
        rendered = format_output(report.to_dict(), format=fmt)
        print(rendered)

    return EXIT_SUCCESS
