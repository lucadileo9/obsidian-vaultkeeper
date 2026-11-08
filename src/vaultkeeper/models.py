"""Domain models and data structures for VaultKeeper.

All models represent immutable or strictly typed structures exchanged across
the core computation engine and the CLI presentation layer.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class BrokenLink:
    """Represents an unresolved wikilink or media embed discovered in a note."""

    source_file: Path
    line_number: int
    raw_target: str
    clean_target: str
    anchor: Optional[str] = None
    alias: Optional[str] = None

    def is_media_embed(self) -> bool:
        """Return True if the target refers to a media or binary document."""
        return self.clean_target.lower().endswith(
            (
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
            )
        )


@dataclass
class Frontmatter:
    """Represents parsed YAML frontmatter of a Markdown note."""

    raw_content: str
    metadata: Dict[str, Any]
    tipo: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def has_tag(self, tag: str) -> bool:
        """Check if a specific tag is present in the note's tags."""
        return tag in self.tags

    def is_valid_type(self, allowed_types: List[str]) -> bool:
        """Check if the tipo field matches one of the allowed types."""
        return bool(self.tipo and self.tipo in allowed_types)


@dataclass
class Note:
    """Represents an isolated Markdown note with metadata and content."""

    file_path: Path
    rel_path: Path
    frontmatter: Optional[Frontmatter]
    body: str
    size_bytes: int


@dataclass
class OrphanAttachment:
    """Represents a media or document file not referenced by any note in the vault."""

    file_path: Path
    rel_path: Path
    size_bytes: int
    folder_type: str


@dataclass
class PhaseResult:
    """Structured result of a single audit phase."""

    phase_id: int
    title: str
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def is_clean(self) -> bool:
        """Return True if no blocking issues were found in this phase."""
        return len(self.issues) == 0


@dataclass
class AuditReport:
    """Complete 5-phase audit diagnostics report."""

    vault_root: Path
    timestamp: str
    phases: List[PhaseResult]
    total_issues: int
    health_score: float

    def is_clean(self) -> bool:
        """Return True if the vault is completely free of audit issues."""
        return self.total_issues == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to serializable dictionary for JSON or API export."""
        return {
            "vault_root": str(self.vault_root),
            "timestamp": self.timestamp,
            "total_issues": self.total_issues,
            "health_score": round(self.health_score, 2),
            "phases": [
                {
                    "phase_id": p.phase_id,
                    "title": p.title,
                    "issues_count": len(p.issues),
                    "warnings_count": len(p.warnings),
                    "issues": p.issues,
                    "warnings": p.warnings,
                    "metrics": p.metrics,
                }
                for p in self.phases
            ],
        }


@dataclass
class VaultCatalog:
    """In-memory O(1) index for vault paths, stems, and file resolution."""

    vault_root: Path
    notes_by_stem: Dict[str, List[Path]] = field(default_factory=dict)
    files_by_name: Set[str] = field(default_factory=set)
    rel_paths: Set[str] = field(default_factory=set)
    total_files: int = 0
    total_size_bytes: int = 0


@dataclass
class VaultConfig:
    """Configuration schema loaded via proteus."""

    root_path: Path
    allowed_extensions: Set[str] = field(
        default_factory=lambda: {
            ".md",
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".svg",
            ".docx",
            ".xlsx",
            ".pptx",
        }
    )
    ignored_folders: Set[str] = field(
        default_factory=lambda: {
            ".obsidian",
            ".trash",
            ".git",
            ".stversions",
            ".deleted",
            "node_modules",
            ".venv",
        }
    )
    max_path_length: int = 240
    naming_style: str = "Title_Case"
    acronyms: Set[str] = field(
        default_factory=lambda: {
            "AI",
            "API",
            "AWS",
            "BCG",
            "CRM",
            "HPC",
            "IT",
            "JEMORE",
            "MECE",
            "SQL",
            "UX",
            "MOC",
            "PKM",
        }
    )
    disallowed_chars_regex: str = r"['\":?*!&|<>,\\()]"
    preserve_prefix_pattern: str = r"^[0-9]{2}(-[0-9]{2})?_"
    type_field: str = "tipo"
    allowed_types: List[str] = field(
        default_factory=lambda: [
            "Appunto",
            "Contatto",
            "Progetto",
            "Risorsa",
            "Indice",
            "Sistema",
        ]
    )
    required_frontmatter_fields: List[str] = field(default_factory=lambda: ["tipo", "tags"])
    taxonomy_file: Optional[str] = "00_Tassonomia_Tag.md"
    strict_taxonomy: bool = True
    protect_c_directives: bool = True
    protect_hex_colors: bool = True
    tag_replacements: Dict[str, str] = field(
        default_factory=lambda: {
            "appunti": "tipo/appunto",
            "risorse": "tipo/risorsa",
            "progetti": "tipo/progetto",
        }
    )
    attachment_folders: List[str] = field(
        default_factory=lambda: [
            "_attachments",
            "attachments",
            "assets",
            "Slide",
            "media",
        ]
    )
    heavy_file_threshold_mb: int = 50
    trash_folder: str = ".trash"
    index_naming_pattern: str = "contextual"
    index_prefix: str = "00_"
    index_summary_max_chars: int = 250
    include_non_md_in_indices: bool = True
    archive_path: Optional[str] = None
    templates_folder: Optional[str] = "00-09_Meta/02_Template"
    offload_folder: Optional[str] = None
    max_undo_history: int = 100


@dataclass
class ActionRecord:
    """Represents an atomic reversible filesystem or content modification."""

    action_type: str  # "write_content", "move_file", "delete_file", "create_file"
    path: str
    target_path: Optional[str] = None
    content_before: Optional[str] = None
    content_after: Optional[str] = None
    hash_before: Optional[str] = None
    hash_after: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a JSON-serializable dictionary."""
        return {
            "action_type": self.action_type,
            "path": self.path,
            "target_path": self.target_path,
            "content_before": self.content_before,
            "content_after": self.content_after,
            "hash_before": self.hash_before,
            "hash_after": self.hash_after,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRecord":
        """Reconstruct record from a dictionary."""
        return cls(
            action_type=data["action_type"],
            path=data["path"],
            target_path=data.get("target_path"),
            content_before=data.get("content_before"),
            content_after=data.get("content_after"),
            hash_before=data.get("hash_before"),
            hash_after=data.get("hash_after"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TransactionRecord:
    """Represents a logged atomic transaction composed of one or more actions."""

    tx_id: str
    timestamp: str
    command: str
    description: str
    actions: List[ActionRecord] = field(default_factory=list)
    reverted: bool = False
    reverted_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to a JSON-serializable dictionary."""
        return {
            "tx_id": self.tx_id,
            "timestamp": self.timestamp,
            "command": self.command,
            "description": self.description,
            "actions": [a.to_dict() for a in self.actions],
            "reverted": self.reverted,
            "reverted_at": self.reverted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionRecord":
        """Reconstruct transaction from a dictionary."""
        return cls(
            tx_id=data["tx_id"],
            timestamp=data["timestamp"],
            command=data["command"],
            description=data.get("description", ""),
            actions=[ActionRecord.from_dict(a) for a in data.get("actions", [])],
            reverted=data.get("reverted", False),
            reverted_at=data.get("reverted_at"),
        )


@dataclass(frozen=True)
class UndoResult:
    """Outcome of an undo/revert operation on a historical transaction."""

    tx_id: str
    success: bool
    reverted_actions: int
    message: str
    affected_files: List[str] = field(default_factory=list)


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
