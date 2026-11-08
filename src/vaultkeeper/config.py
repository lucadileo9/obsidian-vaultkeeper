"""Configuration loader and schema validator using the proteus library."""

from pathlib import Path
from typing import Any, Optional, Set

from proteus.core import ConfigurationManager
from proteus.exceptions import ConfigurationNotLoadedError, InvalidKeyError

from .exceptions import ConfigurationError, VaultNotFoundError
from .models import VaultConfig

DEFAULT_VAULT_TOML = """# VaultKeeper Configuration File (vault.toml)
# Defines governance rules, link resolution, and maintenance standards for your vault.

[vault]
root_path = "{root_path}"
allowed_extensions = [".md", ".pdf", ".png", ".jpg", ".jpeg", ".svg", ".docx", ".xlsx", ".pptx"]
ignored_folders = [".obsidian", ".trash", ".git", ".stversions", ".deleted", "node_modules", ".venv"]
max_path_length = 240

[naming]
style = "Title_Case"                         # "Title_Case", "kebab-case", "snake_case", "none"
disallowed_chars = "[\'\\":?*!&|<>,\\\\\\\\()]"
acronyms = ["AI", "API", "AWS", "BCG", "CRM", "HPC", "IT", "JEMORE", "MECE", "SQL", "UX", "MOC", "PKM"]
preserve_prefix_pattern = "^[0-9]{{2}}(-[0-9]{{2}})?_"

[frontmatter]
type_field = "tipo"
allowed_types = ["Appunto", "Contatto", "Progetto", "Risorsa", "Indice", "Sistema"]
required_fields = ["tipo", "tags"]

[tags]
taxonomy_file = "00_Tassonomia_Tag.md"
strict_taxonomy = true
protect_c_directives = true
protect_hex_colors = true
tag_replacements = {{ "appunti" = "tipo/appunto", "risorse" = "tipo/risorsa", "progetti" = "tipo/progetto" }}

[attachments]
folder_names = ["_attachments", "attachments", "assets", "Slide", "media"]
heavy_file_threshold_mb = 50
trash_folder = ".trash"

[indices]
naming_pattern = "contextual"                # "contextual" (00_Indice_<folder>.md), "static" (00_Indice.md), "readme" (README.md)
prefix = "00_"
summary_max_chars = 250
include_non_md = true
"""


def find_config_file(root_path: Path, explicit_path: Optional[Path] = None) -> Optional[Path]:
    """Find the configuration file using hierarchical resolution.

    Order of precedence:
    1. Explicit file path passed by caller.
    2. `vault.toml` located in the vault root directory.
    3. User global config at `~/.config/vaultkeeper/config.toml`.
    """
    if explicit_path is not None:
        if explicit_path.is_file():
            return explicit_path.resolve()
        raise ConfigurationError(f"Specified configuration file not found: {explicit_path}")

    vault_cfg = root_path / "vault.toml"
    if vault_cfg.is_file():
        return vault_cfg.resolve()

    user_cfg = Path.home() / ".config" / "vaultkeeper" / "config.toml"
    if user_cfg.is_file():
        return user_cfg.resolve()

    return None


def load_vault_config(
    root_path: Optional[Path] = None,
    config_file: Optional[Path] = None,
) -> VaultConfig:
    """Load and validate VaultConfig using proteus.

    Args:
        root_path: Root directory of the vault. If None, loaded from configuration.
        config_file: Optional explicit path to vault.toml or config.toml.

    Returns:
        Fully populated VaultConfig instance.

    Raises:
        ConfigurationError: If configuration is invalid or missing required values.
        VaultNotFoundError: If target vault root does not exist.
    """
    cm = ConfigurationManager()
    cfg_path = None

    if root_path is not None:
        target_root = Path(root_path).resolve()
        if not target_root.is_dir():
            raise VaultNotFoundError(f"Vault root directory does not exist: {target_root}")
        cfg_path = find_config_file(target_root, config_file)
    elif config_file is not None:
        cfg_path = Path(config_file).resolve()
        if not cfg_path.is_file():
            raise ConfigurationError(f"Config file not found: {cfg_path}")
    else:
        cfg_path = find_config_file(Path.cwd(), None)

    if cfg_path and cfg_path.is_file():
        try:
            cm.load(str(cfg_path))
        except Exception as exc:
            raise ConfigurationError(f"Failed to load configuration file {cfg_path}", str(exc)) from exc

    def safe_get(key: str, default: Any = None) -> Any:
        try:
            val = cm.get(key, default)
            return val if val is not None else default
        except (ConfigurationNotLoadedError, InvalidKeyError, KeyError):
            return default

    raw_root = safe_get("vault.root_path")
    if root_path is not None:
        effective_root = Path(root_path).resolve()
    elif raw_root:
        effective_root = Path(raw_root).resolve()
    else:
        effective_root = Path.cwd().resolve()

    if not effective_root.is_dir():
        raise VaultNotFoundError(f"Vault root directory does not exist: {effective_root}")

    # Extract vault section
    allowed_ext_raw = safe_get("vault.allowed_extensions")
    allowed_extensions: Set[str] = (
        set(allowed_ext_raw)
        if isinstance(allowed_ext_raw, (list, set, tuple))
        else {
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

    ignored_folders_raw = safe_get("vault.ignored_folders")
    ignored_folders: Set[str] = (
        set(ignored_folders_raw)
        if isinstance(ignored_folders_raw, (list, set, tuple))
        else {
            ".obsidian",
            ".trash",
            ".git",
            ".stversions",
            ".deleted",
            "node_modules",
            ".venv",
        }
    )

    max_path_length = int(safe_get("vault.max_path_length") or 240)

    # Extract naming section
    naming_style = str(safe_get("naming.style") or "Title_Case")
    acronyms_raw = safe_get("naming.acronyms")
    acronyms: Set[str] = (
        set(acronyms_raw)
        if isinstance(acronyms_raw, (list, set, tuple))
        else {
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
    disallowed_chars_regex = str(safe_get("naming.disallowed_chars") or r"['\":?*!&|<>,\\()]")
    preserve_prefix_pattern = str(safe_get("naming.preserve_prefix_pattern") or r"^[0-9]{2}(-[0-9]{2})?_")

    # Extract frontmatter section
    type_field = str(safe_get("frontmatter.type_field") or "tipo")
    allowed_types_raw = safe_get("frontmatter.allowed_types")
    allowed_types = (
        list(allowed_types_raw)
        if isinstance(allowed_types_raw, (list, set, tuple))
        else ["Appunto", "Contatto", "Progetto", "Risorsa", "Indice", "Sistema"]
    )
    required_fields_raw = safe_get("frontmatter.required_fields")
    required_frontmatter_fields = (
        list(required_fields_raw) if isinstance(required_fields_raw, (list, set, tuple)) else ["tipo", "tags"]
    )

    # Extract tags section
    taxonomy_file = safe_get("tags.taxonomy_file", "00_Tassonomia_Tag.md")
    if taxonomy_file is not None:
        taxonomy_file = str(taxonomy_file)
    strict_taxonomy = bool(safe_get("tags.strict_taxonomy", True))
    protect_c_directives = bool(safe_get("tags.protect_c_directives", True))
    protect_hex_colors = bool(safe_get("tags.protect_hex_colors", True))
    tag_replacements_raw = safe_get("tags.tag_replacements")
    tag_replacements = (
        dict(tag_replacements_raw)
        if isinstance(tag_replacements_raw, dict)
        else {
            "appunti": "tipo/appunto",
            "risorse": "tipo/risorsa",
            "progetti": "tipo/progetto",
        }
    )

    # Extract attachments section
    att_folders_raw = safe_get("attachments.folder_names")
    attachment_folders = (
        list(att_folders_raw)
        if isinstance(att_folders_raw, (list, set, tuple))
        else ["_attachments", "attachments", "assets", "Slide", "media"]
    )
    heavy_file_threshold_mb = int(safe_get("attachments.heavy_file_threshold_mb") or 50)
    trash_folder = str(safe_get("attachments.trash_folder") or ".trash")

    # Extract indices section
    index_naming_pattern = str(safe_get("indices.naming_pattern") or "contextual")
    index_prefix = str(safe_get("indices.prefix") or "00_")
    index_summary_max_chars = int(safe_get("indices.summary_max_chars") or 250)
    include_non_md = bool(safe_get("indices.include_non_md", True))

    # Extract extended lifecycle and history sections
    archive_path_raw = safe_get("vault.archive_path")
    archive_path = str(archive_path_raw) if archive_path_raw else None
    templates_folder = str(safe_get("vault.templates_folder") or "00-09_Meta/02_Template")
    offload_folder_raw = safe_get("attachments.offload_folder")
    offload_folder = str(offload_folder_raw) if offload_folder_raw else None
    max_undo_history = int(safe_get("history.max_transactions") or 100)

    return VaultConfig(
        root_path=effective_root,
        allowed_extensions=allowed_extensions,
        ignored_folders=ignored_folders,
        max_path_length=max_path_length,
        naming_style=naming_style,
        acronyms=acronyms,
        disallowed_chars_regex=disallowed_chars_regex,
        preserve_prefix_pattern=preserve_prefix_pattern,
        type_field=type_field,
        allowed_types=allowed_types,
        required_frontmatter_fields=required_frontmatter_fields,
        taxonomy_file=taxonomy_file,
        strict_taxonomy=strict_taxonomy,
        protect_c_directives=protect_c_directives,
        protect_hex_colors=protect_hex_colors,
        tag_replacements=tag_replacements,
        attachment_folders=attachment_folders,
        heavy_file_threshold_mb=heavy_file_threshold_mb,
        trash_folder=trash_folder,
        index_naming_pattern=index_naming_pattern,
        index_prefix=index_prefix,
        index_summary_max_chars=index_summary_max_chars,
        include_non_md_in_indices=include_non_md,
        archive_path=archive_path,
        templates_folder=templates_folder,
        offload_folder=offload_folder,
        max_undo_history=max_undo_history,
    )


def generate_default_config_content(root_path: Path) -> str:
    """Generate default vault.toml content with the specified root path."""
    return DEFAULT_VAULT_TOML.format(root_path=Path(root_path).resolve().as_posix())
