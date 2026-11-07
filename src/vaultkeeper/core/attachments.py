"""Attachment tracking, orphan detection, and soft-delete engine."""

import shutil
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple

from ..exceptions import AttachmentError
from ..models import OrphanAttachment, VaultCatalog, VaultConfig
from .links import find_all_links_in_content
from .traversal import walk_vault_files

MEDIA_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".svg",
    ".webp",
    ".pdf",
    ".mp4",
    ".mov",
    ".mp3",
    ".wav",
    ".zip",
    ".tar",
    ".gz",
}


def find_all_referenced_attachment_names(
    catalog: VaultCatalog,
    config: VaultConfig,
) -> Set[str]:
    """Scan all markdown notes and extract all referenced attachment filenames."""
    referenced: Set[str] = set()

    for note_path in walk_vault_files(config, target_dir=config.root_path, extensions={".md"}):
        try:
            content = note_path.read_text(encoding="utf-8")
        except Exception:
            continue

        links = find_all_links_in_content(content, note_path)
        for _, _, target, _, _, _ in links:
            if not target:
                continue

            target_path = Path(target)
            referenced.add(target_path.name.lower())
            referenced.add(target.lower())

    return referenced


def find_orphan_attachments(
    catalog: VaultCatalog,
    config: VaultConfig,
    target_dir: Optional[Path] = None,
) -> List[OrphanAttachment]:
    """Find all media or attachment files not referenced by any markdown note."""
    referenced = find_all_referenced_attachment_names(catalog, config)
    orphans: List[OrphanAttachment] = []

    # Target directory or entire vault
    scan_root = target_dir or config.root_path

    # Walk non-md files
    for file_path in walk_vault_files(config, target_dir=scan_root, filter_extensions=False):
        if file_path.suffix.lower() == ".md" or file_path.suffix.lower() == ".toml":
            continue

        filename_lower = file_path.name.lower()
        try:
            rel_path = file_path.relative_to(config.root_path)
            rel_str = rel_path.as_posix().lower()
            size = file_path.stat().st_size
        except (ValueError, OSError):
            continue

        # Check if either full relative path or filename is referenced
        if filename_lower not in referenced and rel_str not in referenced:
            folder_type = file_path.parent.name
            orphans.append(
                OrphanAttachment(
                    file_path=file_path,
                    rel_path=rel_path,
                    size_bytes=size,
                    folder_type=folder_type,
                )
            )

    return orphans


def find_heavy_files(
    catalog: VaultCatalog,
    config: VaultConfig,
) -> List[Tuple[Path, int]]:
    """Return all files whose size exceeds heavy_file_threshold_mb."""
    threshold_bytes = config.heavy_file_threshold_mb * 1024 * 1024
    heavy_files: List[Tuple[Path, int]] = []

    for file_path in walk_vault_files(config, target_dir=config.root_path, filter_extensions=False):
        try:
            size = file_path.stat().st_size
            if size >= threshold_bytes:
                heavy_files.append((file_path, size))
        except OSError:
            continue

    return sorted(heavy_files, key=lambda x: x[1], reverse=True)


def soft_delete_attachment(
    attachment_path: Path,
    vault_root: Path,
    trash_folder_name: str = ".trash",
) -> Path:
    """Move an attachment into the vault .trash directory preserving relative path structure."""
    if not attachment_path.is_file():
        raise AttachmentError(f"Attachment file not found: {attachment_path}")

    try:
        rel = attachment_path.relative_to(vault_root)
    except ValueError:
        rel = Path(attachment_path.name)

    trash_root = vault_root / trash_folder_name
    dest = trash_root / rel

    # Avoid collision in trash
    if dest.exists():
        timestamp = int(time.time())
        dest = dest.with_stem(f"{dest.stem}_{timestamp}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(attachment_path), str(dest))
    except Exception as exc:
        raise AttachmentError(f"Failed to move file to trash: {attachment_path}", str(exc)) from exc

    return dest


def hard_delete_attachment(attachment_path: Path) -> None:
    """Permanently delete an attachment file from disk."""
    if not attachment_path.is_file():
        raise AttachmentError(f"Attachment file not found: {attachment_path}")
    try:
        attachment_path.unlink()
    except Exception as exc:
        raise AttachmentError(f"Failed to delete attachment: {attachment_path}", str(exc)) from exc
