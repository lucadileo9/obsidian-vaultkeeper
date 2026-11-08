"""Main CLI entrypoint and argument parser for the vk command."""

import argparse
import sys
from typing import List, Optional

from .. import __version__
from .commands.archive import handle_archive
from .commands.attachments import handle_attachments
from .commands.audit import handle_audit
from .commands.config import handle_config
from .commands.disambiguate import handle_disambiguate
from .commands.frontmatter import handle_frontmatter
from .commands.graph import handle_graph_health
from .commands.history import handle_history
from .commands.indices import handle_indices
from .commands.init import handle_init
from .commands.links import handle_links
from .commands.map import handle_map
from .commands.move import handle_move
from .commands.naming import handle_naming
from .commands.offload import handle_offload
from .commands.rename import handle_rename
from .commands.search import handle_search
from .commands.tags import handle_tags
from .commands.undo import handle_undo
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

    # 9. vk history
    history_parser = subparsers.add_parser("history", help="List historical vaultkeeper transactions.")
    history_parser.add_argument("--limit", type=int, default=20, help="Maximum number of transactions to list.")
    history_parser.add_argument(
        "--format",
        type=str,
        default="md",
        choices=["md", "json", "yaml", "csv"],
        help="Output format (default: md).",
    )

    # 10. vk undo
    undo_parser = subparsers.add_parser("undo", help="Revert the most recent or specified transaction.")
    undo_parser.add_argument(
        "--tx",
        type=str,
        default=None,
        help="Specific transaction ID to revert (default: latest active transaction).",
    )
    undo_parser.add_argument("--dry-run", action="store_true", help="Preview undo actions without modifying files.")

    # 11. vk rename
    rename_parser = subparsers.add_parser("rename", help="Rename a note or asset with global wikilink refactoring.")
    rename_parser.add_argument("file", type=str, help="Path of the file to rename.")
    rename_parser.add_argument("new_name", type=str, help="New file name or stem.")
    rename_parser.add_argument(
        "--skip-links",
        action="store_true",
        help="Skip refactoring incoming wikilinks across other notes.",
    )
    rename_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate rename and refactoring without modifying files.",
    )

    # 12. vk move
    move_parser = subparsers.add_parser(
        "move", help="Move a note or folder into a different directory and update indices."
    )
    move_parser.add_argument("target", type=str, help="Path of the file or folder to move.")
    move_parser.add_argument("destination", type=str, help="Destination directory path.")
    move_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate move without altering filesystem.",
    )

    # 13. vk archive
    archive_parser = subparsers.add_parser(
        "archive", help="Archive a note or project to mirror cold storage with Tombstone support."
    )
    archive_parser.add_argument("target", type=str, help="Path of the file or directory to archive.")
    archive_parser.add_argument(
        "--no-tombstone",
        action="store_true",
        help="Do not create a tombstone note in the active vault.",
    )
    archive_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate archiving without moving files.",
    )

    # 14. vk offload
    offload_parser = subparsers.add_parser(
        "offload", help="Offload heavy binary assets to cold storage and replace embeds with external links."
    )
    offload_parser.add_argument(
        "target",
        nargs="?",
        default=None,
        type=str,
        help="Specific file or directory to offload (default: all files exceeding threshold).",
    )
    offload_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate offloading without moving files.",
    )

    # 15. vk tags
    tags_parser = subparsers.add_parser("tags", help="Inspect and manipulate controlled tag taxonomy.")
    tags_subparsers = tags_parser.add_subparsers(dest="tag_action", help="Tag action")

    tags_show_parser = tags_subparsers.add_parser("show", help="List registered taxonomy tags.")
    tags_show_parser.add_argument("--query", type=str, default=None, help="Filter tags matching search query.")
    tags_show_parser.add_argument(
        "--format", type=str, default="md", choices=["md", "json", "yaml", "csv"], help="Output format."
    )

    tags_add_parser = tags_subparsers.add_parser("add", help="Add a tag into 00_Tassonomia_Tag.md.")
    tags_add_parser.add_argument("tag", type=str, help="Tag name to add (e.g. area/ricerca).")
    tags_add_parser.add_argument("--section", type=str, default=None, help="Section heading to insert under.")
    tags_add_parser.add_argument("--dry-run", action="store_true", help="Simulate tag insertion without saving.")

    tags_rm_parser = tags_subparsers.add_parser("remove", help="Remove a tag from 00_Tassonomia_Tag.md.")
    tags_rm_parser.add_argument("tag", type=str, help="Tag name to remove.")
    tags_rm_parser.add_argument("--force", action="store_true", help="Force removal even if referenced in notes.")
    tags_rm_parser.add_argument("--dry-run", action="store_true", help="Simulate tag removal without saving.")

    # 16. vk config
    config_parser = subparsers.add_parser("config", help="Inspect and update vault configuration directives.")
    config_subparsers = config_parser.add_subparsers(dest="config_action", help="Config action")

    config_show_parser = config_subparsers.add_parser("show", help="Display active configuration settings.")
    config_show_parser.add_argument(
        "--format", type=str, default="yaml", choices=["yaml", "json", "md"], help="Output format."
    )

    config_set_parser = config_subparsers.add_parser("set", help="Update a directive in vault.toml.")
    config_set_parser.add_argument("key", type=str, help="Configuration key path (e.g. naming.style).")
    config_set_parser.add_argument("value", type=str, help="New value to set.")
    config_set_parser.add_argument("--dry-run", action="store_true", help="Simulate configuration update.")

    # 17. vk search
    search_parser = subparsers.add_parser("search", help="Execute semantic query and filter search across notes.")
    search_parser.add_argument("query", nargs="?", default=None, type=str, help="Optional text search query.")
    search_parser.add_argument("--tag", type=str, default=None, help="Filter by tag (frontmatter or inline).")
    search_parser.add_argument("--type", type=str, default=None, help="Filter by note frontmatter tipo.")
    search_parser.add_argument("--links-to", type=str, default=None, help="Filter notes linking to target stem.")
    search_parser.add_argument("--folder", type=str, default=None, help="Restrict search to a folder path.")
    search_parser.add_argument(
        "--format", type=str, default="md", choices=["md", "json", "yaml", "csv"], help="Output format."
    )

    # 18. vk graph-health
    graph_parser = subparsers.add_parser(
        "graph-health", help="Execute non-punitive topological graph diagnostics."
    )
    graph_parser.add_argument(
        "--format", type=str, default="md", choices=["md", "json", "yaml"], help="Output format."
    )

    # 19. vk map
    map_parser = subparsers.add_parser(
        "map", help="Generate Johnny.Decimal area telemetry and master vault map."
    )
    map_parser.add_argument("--output", type=str, default=None, help="Output path for master MOC markdown note.")
    map_parser.add_argument(
        "--format", type=str, default="md", choices=["md", "json"], help="Output format."
    )

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
            "history": handle_history,
            "undo": handle_undo,
            "rename": handle_rename,
            "move": handle_move,
            "archive": handle_archive,
            "offload": handle_offload,
            "tags": handle_tags,
            "config": handle_config,
            "search": handle_search,
            "graph-health": handle_graph_health,
            "map": handle_map,
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
