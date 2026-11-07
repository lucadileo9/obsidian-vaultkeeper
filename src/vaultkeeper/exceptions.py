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
