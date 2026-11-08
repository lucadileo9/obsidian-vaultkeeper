"""Core entity models representing Markdown notes, frontmatter, and vault index."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


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
class VaultCatalog:
    """In-memory O(1) index for vault paths, stems, and file resolution."""

    vault_root: Path
    notes_by_stem: Dict[str, List[Path]] = field(default_factory=dict)
    files_by_name: Set[str] = field(default_factory=set)
    rel_paths: Set[str] = field(default_factory=set)
    total_files: int = 0
    total_size_bytes: int = 0
