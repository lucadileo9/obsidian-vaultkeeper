"""VaultKeeper: Universal Second Brain governance, link validator and maintenance toolkit."""

from .config import generate_default_config_content, load_vault_config
from .exceptions import (
    AttachmentError,
    ConfigurationError,
    CreationError,
    FrontmatterError,
    LinkResolutionError,
    NamingError,
    TaxonomyError,
    TemplateError,
    VaultKeeperError,
    VaultNotFoundError,
)
from .models import (
    AuditReport,
    BrokenLink,
    CreateResult,
    Frontmatter,
    Note,
    OrphanAttachment,
    PhaseResult,
    VaultCatalog,
    VaultConfig,
)
from .vault import Vault

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Vault",
    "VaultConfig",
    "load_vault_config",
    "generate_default_config_content",
    "BrokenLink",
    "CreateResult",
    "Frontmatter",
    "Note",
    "OrphanAttachment",
    "PhaseResult",
    "AuditReport",
    "VaultCatalog",
    "VaultKeeperError",
    "ConfigurationError",
    "VaultNotFoundError",
    "CreationError",
    "TemplateError",
    "FrontmatterError",
    "TaxonomyError",
    "NamingError",
    "LinkResolutionError",
    "AttachmentError",
]
