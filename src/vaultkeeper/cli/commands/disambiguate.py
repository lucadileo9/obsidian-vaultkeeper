"""Implementation of 'vk disambiguate' command."""

import logging
from argparse import Namespace

from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_ISSUES_FOUND = 2


def handle_disambiguate(args: Namespace, logger: logging.Logger) -> int:
    """Scan and report stem collisions between notes located in separate folders."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    collisions = v.stem_collisions()

    if not collisions:
        logger.info("No stem collisions detected across vault.")
        return EXIT_SUCCESS

    logger.warning("Detected %d stem collisions:", len(collisions))
    for stem, paths in collisions.items():
        logger.warning("  - '%s' is duplicated across %d paths:", stem, len(paths))
        for p in paths:
            try:
                rel = p.relative_to(v.root).as_posix()
            except ValueError:
                rel = str(p)
            logger.warning("      * %s", rel)

    logger.info("Recommendation: Rename duplicated notes with contextual prefixes or use 'vk normalize-names'.")
    return EXIT_ISSUES_FOUND
