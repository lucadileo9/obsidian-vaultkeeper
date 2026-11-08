"""Configuration models loaded from vault.toml."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


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
