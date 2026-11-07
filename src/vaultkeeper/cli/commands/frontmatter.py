"""Implementation of 'vk frontmatter' subcommands."""

import logging
from argparse import Namespace
from pathlib import Path

from ...core.frontmatter import (
    extract_inline_tags,
    parse_note_content,
    parse_taxonomy_file,
    read_note,
    update_frontmatter,
)
from ...core.traversal import walk_vault_files
from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_frontmatter(args: Namespace, logger: logging.Logger) -> int:
    """Dispatch frontmatter subcommands."""
    subaction = getattr(args, "fm_action", None)
    if subaction == "set-type":
        return handle_set_type(args, logger)
    elif subaction == "add-tags":
        return handle_add_tags(args, logger)
    elif subaction == "sanitize-tags":
        return handle_sanitize_tags(args, logger)
    else:
        logger.error("Unknown frontmatter action. Choose: set-type, add-tags, sanitize-tags.")
        return EXIT_ERROR


def handle_set_type(args: Namespace, logger: logging.Logger) -> int:
    """Set or update the tipo YAML frontmatter field."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    target = getattr(args, "target", None)
    new_type = getattr(args, "type", None)
    dry_run = getattr(args, "dry_run", False)

    if not target or not new_type:
        logger.error("Both --target and --type arguments are required.")
        return EXIT_ERROR

    target_path = Path(target).resolve()
    prefix = "[DRY-RUN] " if dry_run else ""
    changed = v.set_frontmatter_type(target_path, new_type, dry_run=dry_run)

    if changed:
        logger.info("%sUpdated %s: %s -> %s", prefix, target_path.name, v.config.type_field, new_type)
    else:
        logger.info("Frontmatter already has %s: %s", v.config.type_field, new_type)

    return EXIT_SUCCESS


def handle_add_tags(args: Namespace, logger: logging.Logger) -> int:
    """Inject or overwrite tags in a note's frontmatter."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    target = getattr(args, "target", None)
    tags = getattr(args, "tags", [])
    overwrite = getattr(args, "overwrite", False)
    dry_run = getattr(args, "dry_run", False)

    if not target or not tags:
        logger.error("Both --target and --tags arguments are required.")
        return EXIT_ERROR

    target_path = Path(target).resolve()
    prefix = "[DRY-RUN] " if dry_run else ""
    changed = v.add_frontmatter_tags(target_path, tags, overwrite=overwrite, dry_run=dry_run)

    if changed:
        logger.info("%sInjected %d tags into: %s", prefix, len(tags), target_path.name)
    else:
        logger.info("Tags already present in: %s", target_path.name)

    return EXIT_SUCCESS


def handle_sanitize_tags(args: Namespace, logger: logging.Logger) -> int:
    """Sanitize and apply tag replacements based on taxonomy and config mapping."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    dry_run = getattr(args, "dry_run", False)
    target = getattr(args, "target", None)
    prefix = "[DRY-RUN] " if dry_run else ""

    target_dir = Path(target).resolve() if target else v.root
    replacements = v.config.tag_replacements
    logger.info("%sSanitizing tags across notes in: %s", prefix, target_dir)

    modified_count = 0
    for note_path in walk_vault_files(v.config, target_dir=target_dir, extensions={".md"}):
        try:
            content = note_path.read_text(encoding="utf-8")
        except Exception:
            continue

        fm, body = parse_note_content(content, type_field=v.config.type_field)
        if not fm or not fm.tags:
            continue

        updated_tags = []
        changed = False
        for tag in fm.tags:
            if tag in replacements:
                updated_tags.append(replacements[tag])
                changed = True
            else:
                updated_tags.append(tag)

        if changed:
            updated_content = update_frontmatter(content, {"tags": updated_tags}, type_field=v.config.type_field)
            if not dry_run:
                note_path.write_text(updated_content, encoding="utf-8")
            modified_count += 1
            logger.info("  - %s: updated tags to %s", note_path.name, updated_tags)

    logger.info("%sCompleted tag sanitization. %d notes modified.", prefix, modified_count)
    return EXIT_SUCCESS
