"""Execution result models for mutations, note creation, renaming, moving, and archiving."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class RenameResult:
    """Outcome of a vk rename operation."""

    old_path: Path
    new_path: Path
    updated_links_count: int
    index_updated: bool
    tx_id: Optional[str] = None


@dataclass(frozen=True)
class MoveResult:
    """Outcome of a vk move operation."""

    source_path: Path
    dest_path: Path
    old_index_updated: bool
    new_index_updated: bool
    tx_id: Optional[str] = None


@dataclass(frozen=True)
class ArchiveResult:
    """Outcome of a vk archive operation."""

    source_path: Path
    archive_path: Path
    tombstone_created: bool
    summary: str
    tx_id: Optional[str] = None


@dataclass(frozen=True)
class OffloadResult:
    """Outcome of a vk offload operation."""

    offloaded_files: List[Tuple[Path, Path, int]]  # (source, dest, size_bytes)
    total_bytes_saved: int
    updated_notes_count: int
    tx_id: Optional[str] = None


@dataclass(frozen=True)
class TagMutationResult:
    """Outcome of adding or removing a taxonomy tag."""

    tag: str
    action: str  # "add", "remove"
    taxonomy_file: Path
    notes_affected_count: int = 0
    tx_id: Optional[str] = None


@dataclass(frozen=True)
class CreateResult:
    """Outcome of creating a standardized note from a template."""

    file_path: Path
    rel_path: Path
    stem: str
    title: str
    tipo: str
    tags: List[str]
    template_used: Optional[str]
    index_updated: bool
    index_path: Optional[Path] = None
    tx_id: Optional[str] = None
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert creation result to serializable dictionary."""
        return {
            "file_path": str(self.file_path),
            "rel_path": str(self.rel_path),
            "stem": self.stem,
            "title": self.title,
            "tipo": self.tipo,
            "tags": list(self.tags),
            "template_used": self.template_used,
            "index_updated": self.index_updated,
            "index_path": str(self.index_path) if self.index_path else None,
            "tx_id": self.tx_id,
            "dry_run": self.dry_run,
        }
