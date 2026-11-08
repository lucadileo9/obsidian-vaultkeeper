"""Core computational modules for VaultKeeper."""

from .attachments import (
    find_heavy_files,
    find_orphan_attachments,
    hard_delete_attachment,
    soft_delete_attachment,
)
from .audit import run_audit
from .document import MarkdownDocument
from .frontmatter import (
    extract_inline_tags,
    parse_note_content,
    parse_taxonomy_file,
    read_note,
    update_frontmatter,
)
from .graph import GraphTelemetry
from .indices import (
    IndexManager,
    generate_folder_index_content,
    get_index_filename_for_folder,
    write_folder_index,
)
from .journal import (
    TransactionContext,
    TransactionJournal,
)
from .links import (
    WikilinkEngine,
    find_all_links_in_content,
    find_stem_collisions,
    resolve_link_target,
    scan_broken_links,
)
from .map import VaultMapEngine
from .naming import (
    batch_normalize,
    normalize_name,
    normalize_stem,
    rename_vault_item,
    update_wikilinks_in_content,
)
from .search import SearchEngine
from .taxonomy import TaxonomyEngine
from .templates import TemplateEngine, resolve_target_folder
from .traversal import (
    build_vault_catalog,
    walk_vault_directories,
    walk_vault_files,
)

__all__ = [
    "walk_vault_files",
    "walk_vault_directories",
    "build_vault_catalog",
    "parse_note_content",
    "read_note",
    "update_frontmatter",
    "extract_inline_tags",
    "parse_taxonomy_file",
    "resolve_link_target",
    "find_all_links_in_content",
    "scan_broken_links",
    "find_stem_collisions",
    "WikilinkEngine",
    "find_orphan_attachments",
    "find_heavy_files",
    "soft_delete_attachment",
    "hard_delete_attachment",
    "normalize_name",
    "normalize_stem",
    "rename_vault_item",
    "update_wikilinks_in_content",
    "batch_normalize",
    "get_index_filename_for_folder",
    "generate_folder_index_content",
    "write_folder_index",
    "IndexManager",
    "run_audit",
    "TransactionJournal",
    "TransactionContext",
    "MarkdownDocument",
    "TaxonomyEngine",
    "SearchEngine",
    "GraphTelemetry",
    "VaultMapEngine",
    "TemplateEngine",
    "resolve_target_folder",
]
