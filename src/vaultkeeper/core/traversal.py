"""Filesystem traversal engine and in-memory vault catalog indexing."""

import os
from pathlib import Path
from typing import Iterator, Optional, Set

from ..models import VaultCatalog, VaultConfig


def is_ignored_path(path: Path, ignored_folders: Set[str]) -> bool:
    """Return True if any segment of the path matches an ignored folder name."""
    for part in path.parts:
        if part in ignored_folders or part.startswith("."):
            return True
    return False


def walk_vault_files(
    config: VaultConfig,
    target_dir: Optional[Path] = None,
    extensions: Optional[Set[str]] = None,
    filter_extensions: bool = True,
) -> Iterator[Path]:
    """Yield all valid file paths in the vault or target directory.

    Recursively scans directory tree while pruning ignored folders and hidden directories.
    If filter_extensions is False, yields all files regardless of extension.
    """
    root = (target_dir or config.root_path).resolve()
    allowed_exts = extensions or config.allowed_extensions

    for dirpath_str, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath_str)

        # Prune ignored folders in-place to prevent os.walk from descending
        dirnames[:] = [
            d
            for d in dirnames
            if d not in config.ignored_folders and not d.startswith(".")
        ]

        for fname in filenames:
            if fname.startswith("."):
                continue

            file_path = dirpath / fname
            if filter_extensions and allowed_exts:
                if file_path.suffix.lower() not in allowed_exts:
                    continue

            yield file_path


def walk_vault_directories(
    config: VaultConfig,
    target_dir: Optional[Path] = None,
) -> Iterator[Path]:
    """Yield all non-ignored directory paths in the vault or target directory."""
    root = (target_dir or config.root_path).resolve()

    for dirpath_str, dirnames, _ in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [
            d
            for d in dirnames
            if d not in config.ignored_folders and not d.startswith(".")
        ]

        for d in dirnames:
            yield Path(dirpath_str) / d


def build_vault_catalog(config: VaultConfig) -> VaultCatalog:
    """Build an in-memory O(1) catalog for link resolution and vault indexing.

    Indexes all notes by stem, all filenames, and relative paths.
    """
    catalog = VaultCatalog(vault_root=config.root_path)

    for file_path in walk_vault_files(config, config.root_path, filter_extensions=False):
        try:
            rel = file_path.relative_to(config.root_path).as_posix()
            size = file_path.stat().st_size
        except (ValueError, OSError):
            continue

        catalog.total_files += 1
        catalog.total_size_bytes += size
        catalog.files_by_name.add(file_path.name)
        catalog.rel_paths.add(rel)

        if file_path.suffix.lower() == ".md":
            stem = file_path.stem
            if stem not in catalog.notes_by_stem:
                catalog.notes_by_stem[stem] = []
            catalog.notes_by_stem[stem].append(file_path)

    return catalog
