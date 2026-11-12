"""Vault lifecycle engine: atomic renaming, safe moving, archiving, and heavy media offloading."""

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..exceptions import ArchiveError, LifecycleError, NamingError, OffloadError
from ..models import (
    ArchiveResult,
    MoveResult,
    OffloadResult,
    RenameResult,
    VaultCatalog,
    VaultConfig,
)
from ..utils.helpers import format_bytes, truncate_text
from .attachments import find_heavy_files
from .document import MarkdownDocument
from .indices import IndexManager
from .links import WikilinkEngine
from .naming import normalize_stem
from .traversal import walk_vault_files


def extract_summary_for_tombstone(doc: MarkdownDocument, max_chars: int = 300) -> str:
    """Extract an introductory summary from blockquotes, callouts, or the first paragraph."""
    # 1. Check description in frontmatter
    fm_desc = (
        doc.metadata.get("descrizione")
        or doc.metadata.get("description")
        or doc.metadata.get("sommario")
        or doc.metadata.get("summary")
    )
    if fm_desc:
        return truncate_text(str(fm_desc), max_chars)

    # 2. Check for markdown blockquotes or callouts
    for line in doc.body.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            # Strip callout tag e.g. > [!NOTE]
            clean = re.sub(r"^>\s*(\[![\w\-]+\])?\s*", "", stripped).strip()
            if clean:
                return truncate_text(clean, max_chars)

    # 3. Fallback to first non-empty text paragraph
    for line in doc.body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
            return truncate_text(stripped, max_chars)

    return ""


def rename_item(
    catalog: VaultCatalog,
    config: VaultConfig,
    index_manager: IndexManager,
    wikilink_engine: WikilinkEngine,
    source_path: Path,
    new_name: str,
    skip_links: bool = False,
    transaction: Optional[Any] = None,
    dry_run: bool = False,
) -> RenameResult:
    """Rename a note or asset with global wikilink refactoring and index synchronization."""
    resolved_src = source_path.resolve()
    if not resolved_src.exists():
        raise NamingError(f"Source file does not exist: {resolved_src}")

    # Determine new stem and target filename
    if resolved_src.is_file():
        if Path(new_name).suffix == resolved_src.suffix:
            new_stem = Path(new_name).stem
            target_filename = new_name
        else:
            new_stem = new_name
            target_filename = f"{new_name}{resolved_src.suffix}"
    else:
        new_stem = new_name
        target_filename = new_name

    # Apply naming convention normalization if configured
    norm_stem = normalize_stem(new_stem, config)
    if norm_stem != new_stem:
        new_stem = norm_stem
        target_filename = f"{new_stem}{resolved_src.suffix}" if resolved_src.is_file() else new_stem

    dest_path = resolved_src.parent / target_filename
    if dest_path == resolved_src:
        return RenameResult(
            old_path=resolved_src,
            new_path=dest_path,
            updated_links_count=0,
            index_updated=False,
            tx_id=getattr(transaction, "tx_id", None),
        )

    # Pre-flight Check 1: Destination must not already exist in same directory
    if dest_path.exists():
        raise NamingError(f"Destination already exists: {dest_path}")

    # Pre-flight Check 2: Check target stem collision across the vault
    if new_stem in catalog.notes_by_stem:
        colliding = [p for p in catalog.notes_by_stem[new_stem] if p.resolve() != resolved_src]
        if colliding:
            raise NamingError(
                f"Stem collision: Target stem '{new_stem}' already exists at '{colliding[0].as_posix()}'. "
                "Cannot rename to an ambiguous stem."
            )

    # Pre-flight Check 3: Check if source stem is ambiguous
    old_stem = resolved_src.stem
    if old_stem in catalog.notes_by_stem and len(catalog.notes_by_stem[old_stem]) > 1:
        if not skip_links:
            raise NamingError(
                f"Ambiguous source stem: Multiple notes share stem '{old_stem}'. "
                "Pass skip_links=True to rename the physical file without rewriting global links."
            )

    is_md = resolved_src.is_file() and resolved_src.suffix.lower() == ".md"

    # Physical move/rename
    if not dry_run:
        if transaction:
            transaction.move_file(resolved_src, dest_path)
        else:
            resolved_src.rename(dest_path)

    # Update H1 heading inside the note if it matched the old stem (with underscores or spaces)
    if is_md and not dry_run and dest_path.is_file():
        try:
            content = dest_path.read_text(encoding="utf-8")
            old_title_spaced = old_stem.replace("_", " ")
            old_title_regex = f"(?:{re.escape(old_stem)}|{re.escape(old_title_spaced)})"
            h1_pattern = re.compile(r"^#\s+" + old_title_regex + r"\s*$", re.MULTILINE)
            clean_display_title = new_stem.replace("_", " ")
            updated_h1, h1_count = h1_pattern.subn(f"# {clean_display_title}", content)
            if h1_count > 0:
                if transaction:
                    transaction.write_content(dest_path, updated_h1)
                else:
                    dest_path.write_text(updated_h1, encoding="utf-8")
        except Exception:
            pass

    # Global wikilink refactoring
    updated_links = 0
    if not skip_links:
        updated_links = wikilink_engine.refactor_in_vault(
            old_stem,
            new_stem,
            transaction=transaction,
            dry_run=dry_run,
        )

    # Synchronize folder index
    index_updated = index_manager.rename_entry(
        resolved_src.parent,
        old_stem,
        new_stem,
        transaction=transaction,
        dry_run=dry_run,
    )

    return RenameResult(
        old_path=resolved_src,
        new_path=dest_path,
        updated_links_count=updated_links,
        index_updated=index_updated,
        tx_id=getattr(transaction, "tx_id", None),
    )


def move_item(
    config: VaultConfig,
    index_manager: IndexManager,
    source_path: Path,
    dest_folder: Path,
    transaction: Optional[Any] = None,
    dry_run: bool = False,
) -> MoveResult:
    """Move a file or folder into a different Johnny.Decimal directory."""
    resolved_src = source_path.resolve()
    resolved_dest_dir = dest_folder.resolve()

    if not resolved_src.exists():
        raise LifecycleError(f"Source path does not exist: {resolved_src}")

    dest_file = resolved_dest_dir / resolved_src.name
    if dest_file.exists():
        raise LifecycleError(f"Destination already exists: {dest_file}")

    if not dry_run:
        resolved_dest_dir.mkdir(parents=True, exist_ok=True)
        if transaction:
            transaction.move_file(resolved_src, dest_file)
        else:
            shutil.move(str(resolved_src), str(dest_file))

    # Rebuild indices in both old and new folders
    old_index_updated = False
    new_index_updated = False

    if resolved_src.parent != resolved_dest_dir:
        _, old_index_updated = index_manager.rebuild_index(
            resolved_src.parent,
            transaction=transaction,
            dry_run=dry_run,
        )
        _, new_index_updated = index_manager.rebuild_index(
            resolved_dest_dir,
            transaction=transaction,
            dry_run=dry_run,
        )

    return MoveResult(
        source_path=resolved_src,
        dest_path=dest_file,
        old_index_updated=old_index_updated,
        new_index_updated=new_index_updated,
        tx_id=getattr(transaction, "tx_id", None),
    )


def batch_move_items(
    config: VaultConfig,
    index_manager: IndexManager,
    mapping: Dict[Union[str, Path], Union[str, Path]],
    transaction: Optional[Any] = None,
    dry_run: bool = False,
) -> List[MoveResult]:
    """Execute batch move of multiple items with strict All-or-Nothing preflight validation.

    Args:
        config: Vault configuration schema.
        index_manager: IndexManager instance for folder MOC synchronization.
        mapping: Dictionary mapping source paths to destination folders/paths.
        transaction: Optional active TransactionContext.
        dry_run: If True, simulates moves without altering disk.

    Returns:
        List of MoveResult domain models.

    Raises:
        LifecycleError: If any preflight validation fails (missing source, destination collision,
                        or intra-batch collision).
    """
    if not mapping:
        raise LifecycleError("Batch move mapping cannot be empty.")

    root_resolved = config.root_path.resolve()
    validated_moves: List[Tuple[Path, Path, Path]] = []
    dest_files_set: Set[Path] = set()

    # Pre-flight Check Phase (Strict All-or-Nothing)
    for src_raw, dest_raw in mapping.items():
        src_raw_p = Path(src_raw)
        src_p = (root_resolved / src_raw_p if not src_raw_p.is_absolute() else src_raw_p).resolve()

        if not src_p.exists():
            raise LifecycleError(f"Batch move failed pre-flight: Source path does not exist: '{src_raw}'")

        dest_raw_p = Path(dest_raw)
        dest_target = (root_resolved / dest_raw_p if not dest_raw_p.is_absolute() else dest_raw_p).resolve()

        if src_p.is_file():
            if dest_target.suffix == src_p.suffix and not dest_target.is_dir():
                dest_dir = dest_target.parent
                dest_file = dest_target
            else:
                dest_dir = dest_target
                dest_file = dest_dir / src_p.name
        else:
            dest_dir = dest_target
            dest_file = dest_dir / src_p.name

        # Check intra-batch duplicate destination collisions
        if dest_file in dest_files_set:
            raise LifecycleError(
                f"Batch move failed pre-flight: Multiple sources map to the same destination: '{dest_file.name}'"
            )
        dest_files_set.add(dest_file)

        # Check existing destination collision on disk
        if dest_file.exists() and dest_file != src_p:
            # Allow destination only if it is also a source being moved away in this same batch
            is_src_in_batch = any(
                (root_resolved / Path(s) if not Path(s).is_absolute() else Path(s)).resolve() == dest_file
                for s in mapping.keys()
            )
            if not is_src_in_batch:
                raise LifecycleError(f"Batch move failed pre-flight: Destination already exists: '{dest_file}'")

        validated_moves.append((src_p, dest_dir, dest_file))

    # Execution Phase (All pre-flight checks passed)
    results: List[MoveResult] = []
    affected_folders: Set[Path] = set()

    for src_p, dest_dir, dest_file in validated_moves:
        if src_p == dest_file:
            results.append(
                MoveResult(
                    source_path=src_p,
                    dest_path=dest_file,
                    old_index_updated=False,
                    new_index_updated=False,
                    tx_id=getattr(transaction, "tx_id", None),
                )
            )
            continue

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if transaction:
                transaction.move_file(src_p, dest_file)
            else:
                shutil.move(str(src_p), str(dest_file))

        affected_folders.add(src_p.parent)
        affected_folders.add(dest_dir)

    # Rebuild indices for all unique affected folders
    for folder in affected_folders:
        if folder.exists():
            index_manager.rebuild_index(folder, transaction=transaction, dry_run=dry_run)

    for src_p, dest_dir, dest_file in validated_moves:
        if src_p != dest_file:
            results.append(
                MoveResult(
                    source_path=src_p,
                    dest_path=dest_file,
                    old_index_updated=src_p.parent in affected_folders,
                    new_index_updated=dest_dir in affected_folders,
                    tx_id=getattr(transaction, "tx_id", None),
                )
            )

    return results


def archive_item(
    config: VaultConfig,
    index_manager: IndexManager,
    item_path: Path,
    no_tombstone: bool = False,
    transaction: Optional[Any] = None,
    dry_run: bool = False,
) -> ArchiveResult:
    """Archive a note or project folder to mirror cold storage with Tombstone support."""
    resolved_item = item_path.resolve()
    if not resolved_item.exists():
        raise ArchiveError(f"Item to archive does not exist: {resolved_item}")

    # Determine archive root directory
    if config.archive_path:
        archive_root = Path(config.archive_path).resolve()
    else:
        archive_root = config.root_path.parent / "Archive"

    try:
        rel = resolved_item.relative_to(config.root_path.resolve())
    except ValueError:
        rel = Path(resolved_item.name)

    dest_archive = archive_root / rel
    if dest_archive.exists():
        raise ArchiveError(f"Archive destination path already exists: {dest_archive}")

    # Extract summary and tipo if item is a Markdown note
    summary = ""
    tipo = "Risorsa"
    if resolved_item.is_file() and resolved_item.suffix.lower() == ".md":
        try:
            doc = MarkdownDocument.from_file(resolved_item)
            summary = extract_summary_for_tombstone(doc)
            tipo = doc.tipo or "Risorsa"
        except Exception:
            pass

    # Move to cold storage
    if not dry_run:
        dest_archive.parent.mkdir(parents=True, exist_ok=True)
        if transaction:
            transaction.move_file(resolved_item, dest_archive)
        else:
            shutil.move(str(resolved_item), str(dest_archive))

    # Update archived note frontmatter with archive metadata
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not dry_run and dest_archive.is_file() and dest_archive.suffix.lower() == ".md":
        try:
            archived_doc = MarkdownDocument.from_file(dest_archive)
            archived_doc.set_frontmatter_field("stato", "archiviato")
            archived_doc.set_frontmatter_field("data_archiviazione", today)
            archived_doc.save()
        except Exception:
            pass

    tombstone_created = False
    if not no_tombstone and resolved_item.suffix.lower() == ".md":
        tombstone_created = True
        display_title = resolved_item.stem.replace("_", " ")
        summary_line = f"> **Sintesi:** {summary}\n" if summary else ""
        tombstone_body = f"""---
{config.type_field}: {tipo}
stato: archiviato
data_archiviazione: '{today}'
percorso_archivio: '{dest_archive.as_posix()}'
---

# {display_title} (Archiviato)

> [!NOTE] Risorsa archiviata il {today}.
{summary_line}> **Percorso Freddo:** [{dest_archive.name}](file://{dest_archive.as_posix()})
"""
        if not dry_run:
            if transaction:
                transaction.create_file(resolved_item, tombstone_body)
            else:
                resolved_item.write_text(tombstone_body, encoding="utf-8")

        index_manager.mark_archived(
            resolved_item.parent,
            resolved_item.stem,
            transaction=transaction,
            dry_run=dry_run,
        )
    else:
        # Rebuild index in parent directory without tombstone
        index_manager.rebuild_index(
            resolved_item.parent,
            transaction=transaction,
            dry_run=dry_run,
        )

    return ArchiveResult(
        source_path=resolved_item,
        archive_path=dest_archive,
        tombstone_created=tombstone_created,
        summary=summary,
        tx_id=getattr(transaction, "tx_id", None),
    )


def offload_media(
    catalog: VaultCatalog,
    config: VaultConfig,
    wikilink_engine: WikilinkEngine,
    target: Optional[Union[str, Path]] = None,
    transaction: Optional[Any] = None,
    dry_run: bool = False,
) -> OffloadResult:
    """Offload heavy binary files (>50MB or specific target) to cold storage."""
    # Determine offload destination directory
    if config.offload_folder:
        offload_dir = Path(config.offload_folder).resolve()
    elif config.archive_path:
        offload_dir = Path(config.archive_path).resolve() / "90-99_Allegati_Pesanti"
    else:
        offload_dir = config.root_path.parent / "Archive" / "90-99_Allegati_Pesanti"

    files_to_offload: List[Path] = []
    if target:
        target_p = (config.root_path / target if not Path(target).is_absolute() else Path(target)).resolve()
        if target_p.is_file():
            files_to_offload.append(target_p)
        elif target_p.is_dir():
            files_to_offload.extend([f for f, _ in find_heavy_files(catalog, config) if f.is_relative_to(target_p)])
        else:
            raise OffloadError(f"Offload target not found: {target_p}")
    else:
        files_to_offload.extend([f for f, _ in find_heavy_files(catalog, config)])

    if not files_to_offload:
        return OffloadResult(
            offloaded_files=[],
            total_bytes_saved=0,
            updated_notes_count=0,
            tx_id=getattr(transaction, "tx_id", None),
        )

    offloaded_records: List[Tuple[Path, Path, int]] = []
    total_bytes = 0
    total_updated_notes = 0

    for file_path in files_to_offload:
        try:
            size = file_path.stat().st_size
        except OSError:
            size = 0

        dest_file = offload_dir / file_path.name
        if dest_file.exists():
            import time

            dest_file = dest_file.with_stem(f"{dest_file.stem}_{int(time.time())}")

        if not dry_run:
            offload_dir.mkdir(parents=True, exist_ok=True)
            if transaction:
                transaction.move_file(file_path, dest_file)
            else:
                shutil.move(str(file_path), str(dest_file))

        offloaded_records.append((file_path, dest_file, size))
        total_bytes += size

        # Update embeds across markdown notes
        ext_url = f"file://{dest_file.as_posix()}"
        callout_label = f"Allegato archiviato su storage freddo ({format_bytes(size)})"

        for note_path in walk_vault_files(config, target_dir=config.root_path, extensions={".md"}):
            try:
                content = note_path.read_text(encoding="utf-8")
            except Exception:
                continue

            updated_content, count = wikilink_engine.replace_embed_with_link(
                content,
                file_path.name,
                ext_url,
                callout_label=callout_label,
            )
            if count > 0:
                total_updated_notes += 1
                if not dry_run:
                    if transaction:
                        transaction.write_content(note_path, updated_content)
                    else:
                        note_path.write_text(updated_content, encoding="utf-8")

    return OffloadResult(
        offloaded_files=offloaded_records,
        total_bytes_saved=total_bytes,
        updated_notes_count=total_updated_notes,
        tx_id=getattr(transaction, "tx_id", None),
    )
