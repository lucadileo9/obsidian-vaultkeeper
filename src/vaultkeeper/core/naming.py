"""Naming normalization strategy pattern and global wikilink synchronization."""

import re
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from ..exceptions import NamingError
from ..models import VaultCatalog, VaultConfig
from .traversal import walk_vault_files


def clean_disallowed_characters(text: str, disallowed_regex: str) -> str:
    """Remove disallowed punctuation and symbols from filename string."""
    pattern = re.compile(disallowed_regex)
    return pattern.sub("", text)


def normalize_words_title_case(stem: str, acronyms: Set[str]) -> str:
    """Convert words to Title_Case with underscores while preserving uppercase acronyms."""
    # Split by spaces, underscores, or hyphens
    tokens = [t for t in re.split(r"[\s_\-]+", stem) if t]
    norm_tokens = []

    for token in tokens:
        upper = token.upper()
        if upper in acronyms:
            norm_tokens.append(upper)
        else:
            # Capitalize first letter, keep lowercase remainder
            norm_tokens.append(token[:1].upper() + token[1:].lower())

    return "_".join(norm_tokens)


def normalize_words_kebab_case(stem: str) -> str:
    """Convert stem to kebab-case with hyphens."""
    tokens = [t.lower() for t in re.split(r"[\s_\-]+", stem) if t]
    return "-".join(tokens)


def normalize_words_snake_case(stem: str) -> str:
    """Convert stem to snake_case with underscores."""
    tokens = [t.lower() for t in re.split(r"[\s_\-]+", stem) if t]
    return "_".join(tokens)


def normalize_stem(stem: str, config: VaultConfig) -> str:
    """Normalize a filename stem according to the configured naming strategy."""
    if config.naming_style == "none":
        return stem

    # Strip disallowed characters
    cleaned = clean_disallowed_characters(stem, config.disallowed_chars_regex)

    # Check for prefix preservation (e.g. "00_", "10-19_")
    prefix = ""
    prefix_match = re.match(config.preserve_prefix_pattern, cleaned)
    if prefix_match:
        prefix = prefix_match.group(0)
        remainder = cleaned[len(prefix) :]
    else:
        remainder = cleaned

    if config.naming_style == "Title_Case":
        norm_body = normalize_words_title_case(remainder, config.acronyms)
        res = f"{prefix}{norm_body}" if prefix else norm_body
    elif config.naming_style == "kebab-case":
        norm_body = normalize_words_kebab_case(remainder)
        res = f"{prefix.lower()}{norm_body}" if prefix else norm_body
    elif config.naming_style == "snake_case":
        norm_body = normalize_words_snake_case(remainder)
        res = f"{prefix.lower()}{norm_body}" if prefix else norm_body
    else:
        res = cleaned

    # Collapse multiple consecutive underscores or hyphens
    res = re.sub(r"_+", "_", res)
    res = re.sub(r"-+", "-", res)
    return res.strip(" _-")


def normalize_name(filename_or_folder: str, config: VaultConfig, is_directory: bool = False) -> str:
    """Normalize a file or directory name."""
    if is_directory or "." not in filename_or_folder:
        return normalize_stem(filename_or_folder, config)

    # For files with extension
    p = Path(filename_or_folder)
    stem = p.stem
    ext = p.suffix
    norm_stem = normalize_stem(stem, config)
    return f"{norm_stem}{ext}"


def update_wikilinks_in_content(
    content: str,
    old_target: str,
    new_target: str,
) -> Tuple[str, int]:
    """Replace all wikilinks referencing old_target with new_target.

    Handles [[OldTarget]], [[OldTarget|Alias]], [[OldTarget#Anchor]], and ![[OldTarget]].
    Returns (new_content, count_of_replacements).
    """
    count = 0
    # Escape old target for regex
    escaped_old = re.escape(old_target)

    # Match [[old_target(#anchor)?(|alias)?]] or ![[...]]
    pattern = re.compile(r"(!?\[\[)" + escaped_old + r"((?:#[^\]|]*)?)((?:\|[^\]]*)?)(\]\])")

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        prefix = m.group(1)
        anchor = m.group(2)
        alias = m.group(3)
        suffix = m.group(4)
        return f"{prefix}{new_target}{anchor}{alias}{suffix}"

    new_content = pattern.sub(repl, content)
    return new_content, count


def rename_vault_item(
    catalog: VaultCatalog,
    config: VaultConfig,
    old_path: Path,
    new_name: str,
    dry_run: bool = False,
    transaction: Optional[Any] = None,
) -> Tuple[Path, int]:
    """Rename a file or folder and synchronize all incoming wikilinks.

    Returns:
        (new_path, total_updated_links)
    """
    resolved_old = old_path.resolve()
    if not resolved_old.exists():
        raise NamingError(f"Target path does not exist: {resolved_old}")

    dest_path = resolved_old.parent / new_name
    if dest_path == resolved_old:
        return resolved_old, 0

    if dest_path.exists():
        raise NamingError(f"Destination already exists: {dest_path}")

    old_stem = resolved_old.stem
    new_stem = dest_path.stem
    is_dir = resolved_old.is_dir()

    total_links_updated = 0

    # Scan and update links in all vault markdown notes
    for note_path in walk_vault_files(config, target_dir=config.root_path, extensions={".md"}):
        if not is_dir and note_path.resolve() == resolved_old:
            continue

        try:
            content = note_path.read_text(encoding="utf-8")
        except Exception:
            continue

        new_content, count = update_wikilinks_in_content(content, old_stem, new_stem)
        if count > 0:
            total_links_updated += count
            if not dry_run:
                if transaction:
                    transaction.write_content(note_path, new_content)
                else:
                    note_path.write_text(new_content, encoding="utf-8")

    if not dry_run:
        if transaction:
            transaction.move_file(resolved_old, dest_path)
        else:
            resolved_old.rename(dest_path)

    return dest_path, total_links_updated


def batch_normalize(
    catalog: VaultCatalog,
    config: VaultConfig,
    target_dir: Optional[Path] = None,
    dry_run: bool = False,
    transaction: Optional[Any] = None,
) -> List[Tuple[Path, Path, int]]:
    """Scan and normalize all file and directory names in target directory.

    Returns list of:
        (old_path, new_path, updated_links_count)
    """
    results: List[Tuple[Path, Path, int]] = []
    root = target_dir or config.root_path

    # First normalize files
    for file_path in list(walk_vault_files(config, target_dir=root, extensions=None)):
        norm_fname = normalize_name(file_path.name, config, is_directory=False)
        if norm_fname != file_path.name:
            dest, links_cnt = rename_vault_item(
                catalog,
                config,
                file_path,
                norm_fname,
                dry_run=dry_run,
                transaction=transaction,
            )
            results.append((file_path, dest, links_cnt))

    return results
