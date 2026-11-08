"""Domain models and data structures for VaultKeeper.

All models represent immutable or strictly typed structures exchanged across
the core computation engine and the CLI presentation layer.

This package re-exports all domain models from its submodules for full
backward-compatibility:
    - config: Vault configuration schema
    - entities: Markdown notes, frontmatter, and vault in-memory catalog
    - journal: Reversible actions, transaction journal records, undo outcomes
    - results: Results of note mutations, creation, moves, and archiving
    - telemetry: Audit reports, search results, graph topology, and vault mapping
"""

from vaultkeeper.models.config import VaultConfig
from vaultkeeper.models.entities import Frontmatter, Note, VaultCatalog
from vaultkeeper.models.journal import ActionRecord, TransactionRecord, UndoResult
from vaultkeeper.models.results import (
    ArchiveResult,
    CreateResult,
    MoveResult,
    OffloadResult,
    RenameResult,
    TagMutationResult,
)
from vaultkeeper.models.telemetry import (
    AreaSummary,
    AuditReport,
    BrokenLink,
    GraphHealthReport,
    GraphHub,
    OrphanAttachment,
    PhaseResult,
    SearchResult,
    SearchResultItem,
    VaultMapReport,
)

__all__ = [
    # Config
    "VaultConfig",
    # Entities
    "Frontmatter",
    "Note",
    "VaultCatalog",
    # Journal
    "ActionRecord",
    "TransactionRecord",
    "UndoResult",
    # Results
    "ArchiveResult",
    "CreateResult",
    "MoveResult",
    "OffloadResult",
    "RenameResult",
    "TagMutationResult",
    # Telemetry & Reports
    "AreaSummary",
    "AuditReport",
    "BrokenLink",
    "GraphHealthReport",
    "GraphHub",
    "OrphanAttachment",
    "PhaseResult",
    "SearchResult",
    "SearchResultItem",
    "VaultMapReport",
]
