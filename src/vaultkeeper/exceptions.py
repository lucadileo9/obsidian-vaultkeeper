"""VaultKeeper typed exception hierarchy.

All exceptions raised by the vaultkeeper core engine inherit from VaultKeeperError.
"""

from typing import Optional


class VaultKeeperError(Exception):
    """Base exception for all VaultKeeper operations."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ConfigurationError(VaultKeeperError):
    """Raised when configuration validation or loading fails."""


class VaultNotFoundError(VaultKeeperError):
    """Raised when the specified vault root directory does not exist or is inaccessible."""


class FrontmatterError(VaultKeeperError):
    """Raised when frontmatter parsing, validation, or updating fails."""


class TaxonomyError(VaultKeeperError):
    """Raised when tag taxonomy validation encounters errors."""


class NamingError(VaultKeeperError):
    """Raised when naming normalization or collision detection fails."""


class LinkResolutionError(VaultKeeperError):
    """Raised when wikilink parsing, disambiguation, or rewriting fails."""


class AttachmentError(VaultKeeperError):
    """Raised when attachment scanning, soft-deletion, or file moving fails."""


class JournalError(VaultKeeperError):
    """Raised when transaction journaling fails or transaction state is corrupted."""


class UndoError(VaultKeeperError):
    """Raised when an undo operation fails to revert a transaction."""


class UndoConflictError(UndoError):
    """Raised when undo fails because a file was modified externally after the transaction."""


class DocumentError(VaultKeeperError):
    """Raised when parsing or manipulating a MarkdownDocument fails."""


class LifecycleError(VaultKeeperError):
    """Raised when vault item renaming, moving, or refactoring fails."""


class ArchiveError(LifecycleError):
    """Raised when archiving a note or project fails."""


class OffloadError(LifecycleError):
    """Raised when offloading heavy media to cold storage fails."""


class SearchError(VaultKeeperError):
    """Raised when vault search parameters or execution fails."""


class ConfigUpdateError(VaultKeeperError):
    """Raised when updating vault configuration files fails."""


class TemplateError(VaultKeeperError):
    """Raised when template resolution, parsing, or variable interpolation fails."""


class CreationError(VaultKeeperError):
    """Raised when note creation fails due to collisions or validation errors."""
