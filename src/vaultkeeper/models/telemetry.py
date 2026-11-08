"""Telemetry and reporting models for audit diagnostics, search results, graph topology, and vault mapping."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


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
class SearchResultItem:
    """Individual matching note in a search query."""

    file_path: Path
    rel_path: str
    title: str
    tipo: Optional[str]
    tags: List[str]
    matched_terms: List[str]
    snippet: str


@dataclass
class SearchResult:
    """Outcome of a semantic search operation."""

    query: Optional[str]
    filters: Dict[str, Any]
    items: List[SearchResultItem]
    total_matches: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert search results to serializable dictionary."""
        return {
            "query": self.query,
            "filters": self.filters,
            "total_matches": self.total_matches,
            "items": [
                {
                    "file_path": str(it.file_path),
                    "rel_path": it.rel_path,
                    "title": it.title,
                    "tipo": it.tipo,
                    "tags": it.tags,
                    "matched_terms": it.matched_terms,
                    "snippet": it.snippet,
                }
                for it in self.items
            ],
        }


@dataclass(frozen=True)
class GraphHub:
    """High-degree node in the concept graph."""

    stem: str
    file_path: Path
    in_degree: int
    out_degree: int


@dataclass
class GraphHealthReport:
    """Topological non-punitive graph diagnostics."""

    vault_root: Path
    timestamp: str
    total_nodes: int
    total_edges: int
    true_orphans: List[str]
    dead_ends: List[str]
    top_hubs: List[GraphHub]
    disconnected_components: List[List[str]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert graph report to serializable dictionary."""
        return {
            "vault_root": str(self.vault_root),
            "timestamp": self.timestamp,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "true_orphans_count": len(self.true_orphans),
            "true_orphans": self.true_orphans,
            "dead_ends_count": len(self.dead_ends),
            "dead_ends": self.dead_ends,
            "top_hubs": [
                {
                    "stem": h.stem,
                    "file_path": str(h.file_path),
                    "in_degree": h.in_degree,
                    "out_degree": h.out_degree,
                }
                for h in self.top_hubs
            ],
            "disconnected_components_count": len(self.disconnected_components),
            "disconnected_components": self.disconnected_components,
        }


@dataclass
class AreaSummary:
    """Johnny.Decimal area metric summary."""

    area_name: str
    path: Path
    notes_count: int
    attachments_count: int
    total_bytes: int
    has_index: bool
    index_path: Optional[Path] = None


@dataclass
class VaultMapReport:
    """Hierarchical Johnny.Decimal structural map of the vault."""

    vault_root: Path
    timestamp: str
    total_notes: int
    total_attachments: int
    total_bytes: int
    areas: List[AreaSummary]

    def to_dict(self) -> Dict[str, Any]:
        """Convert vault map to serializable dictionary."""
        return {
            "vault_root": str(self.vault_root),
            "timestamp": self.timestamp,
            "total_notes": self.total_notes,
            "total_attachments": self.total_attachments,
            "total_bytes": self.total_bytes,
            "areas": [
                {
                    "area_name": a.area_name,
                    "path": str(a.path),
                    "notes_count": a.notes_count,
                    "attachments_count": a.attachments_count,
                    "total_bytes": a.total_bytes,
                    "has_index": a.has_index,
                    "index_path": str(a.index_path) if a.index_path else None,
                }
                for a in self.areas
            ],
        }
