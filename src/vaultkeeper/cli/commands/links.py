"""Implementation of 'vk check-links' command."""

import logging
from argparse import Namespace

from ...vault import Vault
from ..constants import EXIT_ERROR, EXIT_ISSUES_FOUND, EXIT_SUCCESS


def handle_links(args: Namespace, logger: logging.Logger) -> int:
    """Scan notes for broken wikilinks, broken media embeds, and stem collisions."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    target = getattr(args, "target", None)
    logger.info("Scanning links in vault: %s", v.root)
    if target:
        logger.info("Restricted target: %s", target)

    broken_links = v.check_links(target=target)
    collisions = v.stem_collisions()

    if broken_links:
        logger.warning("Discovered %d broken links:", len(broken_links))
        for b in broken_links:
            kind = "media embed" if b.is_media_embed() else "wikilink"
            logger.warning("  - %s: [[%s]] at %s:%d", kind, b.clean_target, b.source_file.name, b.line_number)
    else:
        logger.info("No broken wikilinks or media embeds found.")

    if collisions:
        logger.info("Identified %d stem collisions:", len(collisions))
        for stem, paths in collisions.items():
            paths_str = ", ".join(p.name for p in paths)
            logger.info("  - '%s' found in %d locations: %s", stem, len(paths), paths_str)

    return EXIT_ISSUES_FOUND if broken_links else EXIT_SUCCESS
