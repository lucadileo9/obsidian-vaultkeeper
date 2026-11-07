"""Folder index and MOC (Map of Content) generator supporting contextual naming."""

from pathlib import Path
from typing import List, Optional, Tuple

from ..models import VaultCatalog, VaultConfig
from ..utils.helpers import format_bytes, truncate_text
from .frontmatter import parse_note_content
from .naming import normalize_stem


def get_index_filename_for_folder(folder_path: Path, config: VaultConfig) -> str:
    """Return the index note filename based on the configured pattern.

    Options:
        - "contextual": e.g. "00_Indice_Progetti.md"
        - "static": "00_Indice.md"
        - "readme": "README.md"
    """
    pattern = config.index_naming_pattern.lower()
    folder_name = folder_path.name.strip()

    if pattern == "readme":
        return "README.md"
    elif pattern == "static":
        return f"{config.index_prefix}Indice.md"
    else:
        # Contextual naming (default)
        import re
        clean_folder = re.sub(config.preserve_prefix_pattern, "", folder_name).strip()
        if not clean_folder:
            clean_folder = folder_name.strip()
        norm_folder = normalize_stem(clean_folder, config)
        return f"{config.index_prefix}Indice_{norm_folder}.md"


def is_index_file(file_path: Path, config: VaultConfig) -> bool:
    """Check if a file is an index note."""
    fname = file_path.name
    if fname == "README.md" or fname == f"{config.index_prefix}Indice.md":
        return True
    if fname.startswith(f"{config.index_prefix}Indice_") and fname.endswith(".md"):
        return True
    return False


def extract_note_summary(file_path: Path, max_chars: int = 250) -> str:
    """Extract a concise one-line summary from note frontmatter or body."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return ""

    fm, body = parse_note_content(content)
    if fm and fm.metadata:
        for field in ("descrizione", "description", "sommario", "summary"):
            val = fm.metadata.get(field)
            if val:
                return truncate_text(str(val), max_chars)

    # Fallback to first non-empty markdown paragraph
    lines = body.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---") or stripped.startswith(">"):
            continue
        return truncate_text(stripped, max_chars)

    return ""


def generate_folder_index_content(
    folder_path: Path,
    config: VaultConfig,
    catalog: Optional[VaultCatalog] = None,
) -> str:
    """Generate Markdown content for a folder MOC index."""
    folder_name = folder_path.name
    index_fname = get_index_filename_for_folder(folder_path, config)

    # 1. Frontmatter
    frontmatter_yaml = f"""---
{config.type_field}: Indice
tags:
  - {config.type_field}/indice
---"""

    # 2. Heading
    header = f"# Indice - {folder_name}\n"

    # 3. Direct Subdirectories
    subdirs: List[Path] = sorted(
        [
            d
            for d in folder_path.iterdir()
            if d.is_dir()
            and d.name not in config.ignored_folders
            and not d.name.startswith(".")
        ],
        key=lambda p: p.name,
    )

    subdirs_section = ""
    if subdirs:
        subdirs_section = "## Sottocartelle\n\n"
        for d in subdirs:
            sub_index_name = get_index_filename_for_folder(d, config)
            sub_index_path = d / sub_index_name
            if sub_index_path.is_file():
                subdirs_section += f"- [[{sub_index_path.stem}|{d.name}]]\n"
            else:
                subdirs_section += f"- `{d.name}/`\n"
        subdirs_section += "\n"

    # 4. Markdown Notes
    md_notes: List[Path] = sorted(
        [
            f
            for f in folder_path.iterdir()
            if f.is_file()
            and f.suffix.lower() == ".md"
            and f.name != index_fname
            and not is_index_file(f, config)
            and not f.name.startswith(".")
        ],
        key=lambda p: p.stem,
    )

    notes_section = ""
    if md_notes:
        notes_section = "## Note\n\n"
        for note in md_notes:
            summary = extract_note_summary(note, config.index_summary_max_chars)
            if summary:
                notes_section += f"- [[{note.stem}]]: {summary}\n"
            else:
                notes_section += f"- [[{note.stem}]]\n"
        notes_section += "\n"

    # 5. Non-Markdown Documents / Media (PDF, Word, Excel, Slide)
    docs_section = ""
    if config.include_non_md_in_indices:
        doc_files: List[Path] = sorted(
            [
                f
                for f in folder_path.iterdir()
                if f.is_file()
                and f.suffix.lower() in config.allowed_extensions
                and f.suffix.lower() != ".md"
                and not f.name.startswith(".")
            ],
            key=lambda p: p.name,
        )

        if doc_files:
            docs_section = "## Documenti e Allegati\n\n"
            for doc in doc_files:
                try:
                    size_str = format_bytes(doc.stat().st_size)
                except OSError:
                    size_str = "0 B"
                docs_section += f"- [[{doc.name}]] (`{size_str}`)\n"
            docs_section += "\n"

    content = f"{frontmatter_yaml}\n\n{header}\n{subdirs_section}{notes_section}{docs_section}".strip()
    return f"{content}\n"


def write_folder_index(
    folder_path: Path,
    config: VaultConfig,
    catalog: Optional[VaultCatalog] = None,
    dry_run: bool = False,
) -> Tuple[Path, bool]:
    """Generate and write the index note for folder_path.

    Returns:
        (index_path, was_created_or_modified)
    """
    index_fname = get_index_filename_for_folder(folder_path, config)
    index_path = folder_path / index_fname
    content = generate_folder_index_content(folder_path, config, catalog)

    if index_path.is_file():
        existing = index_path.read_text(encoding="utf-8")
        if existing == content:
            return index_path, False

    if not dry_run:
        index_path.write_text(content, encoding="utf-8")

    return index_path, True
