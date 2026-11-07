"""Main CLI entrypoint and argument parser for the vk command."""

import argparse
import sys
from typing import List, Optional

from .. import __version__
from .commands.attachments import handle_attachments
from .commands.audit import handle_audit
from .commands.disambiguate import handle_disambiguate
from .commands.frontmatter import handle_frontmatter
from .commands.indices import handle_indices
from .commands.init import handle_init
from .commands.links import handle_links
from .commands.naming import handle_naming
from .logging import close_cli_logger, setup_cli_logger


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for vk."""
    parser = argparse.ArgumentParser(
        prog="vk",
        description="Universal Second Brain governance engine and maintenance CLI for Obsidian vaults.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging output.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational output, displaying errors only.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to an optional plain-text logfile to record operational history.",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Override vault root directory path.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Explicit path to vault.toml or config.toml.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. vk init
    init_parser = subparsers.add_parser("init", help="Initialize a default vault.toml configuration file.")
    init_parser.add_argument("--target", type=str, default=None, help="Directory to initialize vault.toml in.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing configuration file.")

    # 2. vk audit
    audit_parser = subparsers.add_parser("audit", help="Run 5-phase vault diagnostics and compute Health Score.")
    audit_parser.add_argument(
        "--step", type=int, choices=[1, 2, 3, 4, 5], default=None, help="Execute only a specific phase."
    )
    audit_parser.add_argument("--json", type=str, default=None, help="Export diagnostic results to a JSON file.")
    audit_parser.add_argument(
        "--report-md", type=str, default=None, help="Export diagnostic results to a Markdown report."
    )

    # 3. vk check-links
    links_parser = subparsers.add_parser(
        "check-links", help="Scan notes for broken wikilinks and unresolved media embeds."
    )
    links_parser.add_argument("--target", type=str, default=None, help="Restrict scan to a specific note or subfolder.")

    # 4. vk clean-attachments
    att_parser = subparsers.add_parser("clean-attachments", help="Find and clean orphan media attachments.")
    att_parser.add_argument("--target", type=str, default=None, help="Restrict search to a specific directory.")
    att_parser.add_argument("--dry-run", action="store_true", help="Simulate deletion without touching disk files.")
    att_parser.add_argument(
        "--hard-delete", action="store_true", help="Permanently delete files instead of moving to .trash."
    )

    # 5. vk normalize-names
    naming_parser = subparsers.add_parser(
        "normalize-names", help="Normalize note and file names according to naming style."
    )
    naming_parser.add_argument(
        "--target", type=str, default=None, help="Restrict normalization to a specific directory."
    )
    naming_parser.add_argument("--dry-run", action="store_true", help="Simulate normalization without renaming files.")

    # 6. vk generate-indices
    indices_parser = subparsers.add_parser("generate-indices", help="Generate or update folder MOC index notes.")
    indices_parser.add_argument("--target", type=str, default=None, help="Specific folder to generate index for.")
    indices_parser.add_argument(
        "--all", action="store_true", help="Recursively generate indices for all subdirectories."
    )
    indices_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate index generation without writing to disk."
    )

    # 7. vk frontmatter
    fm_parser = subparsers.add_parser("frontmatter", help="Inspect and manipulate YAML frontmatter.")
    fm_subparsers = fm_parser.add_subparsers(dest="fm_action", help="Frontmatter actions")

    set_type_parser = fm_subparsers.add_parser("set-type", help="Set or update the tipo frontmatter field.")
    set_type_parser.add_argument("--target", type=str, required=True, help="Path to target markdown note.")
    set_type_parser.add_argument(
        "--type", type=str, required=True, help="Type value (e.g. Appunto, Progetto, Risorsa)."
    )
    set_type_parser.add_argument("--dry-run", action="store_true", help="Simulate change without writing to disk.")

    add_tags_parser = fm_subparsers.add_parser("add-tags", help="Add tags to frontmatter.")
    add_tags_parser.add_argument("--target", type=str, required=True, help="Path to target markdown note.")
    add_tags_parser.add_argument("--tags", nargs="+", required=True, help="One or more tags to inject.")
    add_tags_parser.add_argument("--overwrite", action="store_true", help="Replace existing tags instead of appending.")
    add_tags_parser.add_argument("--dry-run", action="store_true", help="Simulate change without writing to disk.")

    sanitize_tags_parser = fm_subparsers.add_parser("sanitize-tags", help="Sanitize tags based on taxonomy mapping.")
    sanitize_tags_parser.add_argument("--target", type=str, default=None, help="Restrict scan to a specific folder.")
    sanitize_tags_parser.add_argument("--dry-run", action="store_true", help="Simulate sanitization without saving.")

    # 8. vk disambiguate
    disambiguate_parser = subparsers.add_parser("disambiguate", help="Scan and report stem collisions across folders.")
    disambiguate_parser.add_argument("--target", type=str, default=None, help="Target folder to scan.")
    disambiguate_parser.add_argument("--dry-run", action="store_true", help="Simulate without action.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint execution function."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = setup_cli_logger(
        name="vk",
        verbose=args.verbose,
        quiet=args.quiet,
        log_file=args.log_file,
    )

    try:
        if not args.command:
            parser.print_help()
            return 0

        command_handlers = {
            "init": handle_init,
            "audit": handle_audit,
            "check-links": handle_links,
            "clean-attachments": handle_attachments,
            "normalize-names": handle_naming,
            "generate-indices": handle_indices,
            "frontmatter": handle_frontmatter,
            "disambiguate": handle_disambiguate,
        }

        handler = command_handlers.get(args.command)
        if handler:
            try:
                return handler(args, logger)
            except Exception as exc:
                logger.error("Command execution failed: %s", exc)
                return 1

        parser.print_help()
        return 0
    finally:
        close_cli_logger(logger)


if __name__ == "__main__":
    sys.exit(main())
