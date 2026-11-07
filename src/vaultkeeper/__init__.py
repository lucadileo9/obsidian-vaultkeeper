"""VaultKeeper: Universal Second Brain governance, link validator and maintenance toolkit."""

from .config import generate_default_config_content, load_vault_config
from .exceptions import (
    AttachmentError,
    ConfigurationError,
    FrontmatterError,
    LinkResolutionError,
    NamingError,
    TaxonomyError,
    VaultKeeperError,
    VaultNotFoundError,
)
from .models import (
    AuditReport,
    BrokenLink,
    Frontmatter,
    Note,
    OrphanAttachment,
    PhaseResult,
    VaultCatalog,
    VaultConfig,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "VaultConfig",
    "load_vault_config",
    "generate_default_config_content",
    "BrokenLink",
    "Frontmatter",
    "Note",
    "OrphanAttachment",
    "PhaseResult",
    "AuditReport",
    "VaultCatalog",
    "VaultKeeperError",
    "ConfigurationError",
    "VaultNotFoundError",
    "FrontmatterError",
    "TaxonomyError",
    "NamingError",
    "LinkResolutionError",
    "AttachmentError",
]
