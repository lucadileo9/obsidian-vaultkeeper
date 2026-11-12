"""Safe round-trip YAML frontmatter parser, updater and tag taxonomy validator."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

from ..exceptions import FrontmatterError, TaxonomyError
from ..models import Frontmatter, Note

FRONTMATTER_PATTERN = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)
CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```|`[^`\n]+`")
MATH_BLOCK_PATTERN = re.compile(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$")
C_DIRECTIVE_PATTERN = re.compile(
    r"^\s*#(?:include|define|undef|ifdef|ifndef|if|elif|else|endif|pragma)\b", re.MULTILINE
)
HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b")
TAG_PATTERN = re.compile(r"(?<![a-zA-Z0-9_])#([a-zA-Z_][a-zA-Z0-9_\-/]*)")


def normalize_tag(tag: str) -> str:
    """Normalize a tag string by stripping leading hash and surrounding whitespace."""
    clean = tag.strip()
    if clean.startswith("#"):
        clean = clean[1:].strip()
    return clean


def parse_note_content(
    content: str,
    type_field: str = "tipo",
) -> Tuple[Optional[Frontmatter], str]:
    """Parse raw note content into Frontmatter and markdown body.

    Returns:
        (Frontmatter, body) if YAML frontmatter is present.
        (None, content) if no valid YAML frontmatter is detected.
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return None, content

    raw_yaml, body = match.groups()
    try:
        parsed_data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return None, content

    if not isinstance(parsed_data, dict):
        return None, content

    tipo_val = parsed_data.get(type_field)
    tipo_str = str(tipo_val).strip() if tipo_val is not None else None

    raw_tags = parsed_data.get("tags", [])
    tags_list: List[str] = []

    if isinstance(raw_tags, str):
        # Handle comma or space separated string of tags
        items = re.split(r"[,\s]+", raw_tags)
        tags_list = [normalize_tag(t) for t in items if normalize_tag(t)]
    elif isinstance(raw_tags, (list, tuple, set)):
        for item in raw_tags:
            if item is not None:
                norm = normalize_tag(str(item))
                if norm and norm not in tags_list:
                    tags_list.append(norm)

    frontmatter = Frontmatter(
        raw_content=raw_yaml,
        metadata=parsed_data,
        tipo=tipo_str,
        tags=tags_list,
    )
    return frontmatter, body


def read_note(file_path: Path, vault_root: Path, type_field: str = "tipo") -> Note:
    """Read a Markdown file and return a Note instance."""
    resolved_path = file_path.resolve()
    try:
        content = resolved_path.read_text(encoding="utf-8")
        size_bytes = resolved_path.stat().st_size
    except Exception as exc:
        raise FrontmatterError(f"Cannot read note {resolved_path}", str(exc)) from exc

    try:
        rel_path = resolved_path.relative_to(vault_root.resolve())
    except ValueError:
        rel_path = resolved_path

    frontmatter, body = parse_note_content(content, type_field=type_field)
    return Note(
        file_path=resolved_path,
        rel_path=rel_path,
        frontmatter=frontmatter,
        body=body,
        size_bytes=size_bytes,
    )


def update_frontmatter(
    content: str,
    updates: Dict[str, Any],
    type_field: str = "tipo",
) -> str:
    """Update frontmatter fields preserving existing metadata.

    If frontmatter does not exist, a new YAML frontmatter block is prepended.
    """
    match = FRONTMATTER_PATTERN.match(content)

    if match:
        raw_yaml, body = match.groups()
        try:
            metadata = yaml.safe_load(raw_yaml)
            if not isinstance(metadata, dict):
                metadata = {}
        except yaml.YAMLError:
            metadata = {}
    else:
        metadata = {}
        body = content

    for key, value in updates.items():
        if value is None:
            metadata.pop(key, None)
        else:
            metadata[key] = value

    new_yaml = yaml.dump(
        metadata,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip()

    clean_body = body.lstrip("\r\n")
    return f"---\n{new_yaml}\n---\n\n{clean_body}"


def extract_inline_tags(
    text: str,
    protect_c: bool = True,
    protect_hex: bool = True,
) -> Set[str]:
    """Extract inline tags from markdown text, excluding code, math and false positives."""
    # Strip code blocks and inline code spans
    clean = CODE_BLOCK_PATTERN.sub(" ", text)

    # Strip LaTeX math formulas
    clean = MATH_BLOCK_PATTERN.sub(" ", clean)

    # Strip C/C++ preprocessor directives
    if protect_c:
        lines = []
        for line in clean.splitlines():
            if C_DIRECTIVE_PATTERN.match(line):
                continue
            lines.append(line)
        clean = "\n".join(lines)

    # Strip Hex colors
    if protect_hex:
        clean = HEX_COLOR_PATTERN.sub(" ", clean)

    matches = TAG_PATTERN.findall(clean)
    tags: Set[str] = set()
    for m in matches:
        norm = normalize_tag(m)
        if norm:
            tags.add(norm)
    return tags


def parse_taxonomy_file(taxonomy_path: Path) -> Set[str]:
    """Parse taxonomy file and return all registered canonical tag names without leading hash."""
    if not taxonomy_path.is_file():
        raise TaxonomyError(f"Taxonomy file not found at: {taxonomy_path}")

    try:
        content = taxonomy_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise TaxonomyError(f"Cannot read taxonomy file {taxonomy_path}", str(exc)) from exc

    tags: Set[str] = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("# ") or line.startswith("## ") or line.startswith("### "):
            # Skip markdown headings
            continue

        found = TAG_PATTERN.findall(line)
        for t in found:
            norm = normalize_tag(t)
            if norm:
                tags.add(norm)

    return tags


def batch_set_type(
    vault_root: Path,
    mapping: Dict[Union[str, Path], str],
    allowed_types: Optional[List[str]] = None,
    type_field: str = "tipo",
    transaction: Optional[Any] = None,
    dry_run: bool = False,
) -> List[Tuple[Path, bool]]:
    """Execute batch update of frontmatter tipo with strict All-or-Nothing preflight validation.

    Args:
        vault_root: Vault root directory Path.
        mapping: Dictionary mapping note paths to new type strings.
        allowed_types: Optional list of authorized note types.
        type_field: Frontmatter key for note type (default: 'tipo').
        transaction: Optional active TransactionContext.
        dry_run: If True, simulates changes without writing to disk.

    Returns:
        List of tuples: (note_path, was_modified).

    Raises:
        FrontmatterError: If any preflight validation fails (note missing, invalid type).
    """
    if not mapping:
        raise FrontmatterError("Batch set-type mapping cannot be empty.")

    root_resolved = vault_root.resolve()
    validated_items: List[Tuple[Path, str]] = []

    # Pre-flight Check Phase (Strict All-or-Nothing)
    for target_raw, new_type in mapping.items():
        p = (root_resolved / Path(target_raw) if not Path(target_raw).is_absolute() else Path(target_raw)).resolve()

        if not p.is_file():
            raise FrontmatterError(f"Batch set-type failed pre-flight: Note not found: '{target_raw}'")

        clean_type = str(new_type).strip() if new_type is not None else ""
        if not clean_type:
            raise FrontmatterError(f"Batch set-type failed pre-flight: Empty type provided for note: '{target_raw}'")

        if allowed_types:
            matched = [t for t in allowed_types if t.lower() == clean_type.lower()]
            if not matched:
                raise FrontmatterError(
                    f"Batch set-type failed pre-flight: Invalid note type '{new_type}' for note '{target_raw}'. "
                    f"Allowed types: {', '.join(allowed_types)}"
                )
            clean_type = matched[0]

        validated_items.append((p, clean_type))

    # Execution Phase
    results: List[Tuple[Path, bool]] = []
    for p, clean_type in validated_items:
        content = p.read_text(encoding="utf-8")
        updated = update_frontmatter(content, {type_field: clean_type}, type_field=type_field)
        changed = (updated != content)

        if changed and not dry_run:
            if transaction:
                transaction.write_content(p, updated)
            else:
                p.write_text(updated, encoding="utf-8")

        results.append((p, changed))

    return results


def batch_add_tags(
    vault_root: Path,
    mapping: Dict[Union[str, Path], List[str]],
    allowed_taxonomy_tags: Optional[Set[str]] = None,
    strict_taxonomy: bool = False,
    overwrite: bool = False,
    type_field: str = "tipo",
    transaction: Optional[Any] = None,
    dry_run: bool = False,
) -> List[Tuple[Path, bool]]:
    """Execute batch addition or replacement of frontmatter tags with strict All-or-Nothing preflight.

    Args:
        vault_root: Vault root directory Path.
        mapping: Dictionary mapping note paths to lists of tags.
        allowed_taxonomy_tags: Optional set of canonical taxonomy tags.
        strict_taxonomy: If True, validates tags against taxonomy.
        overwrite: If True, replaces existing tags instead of appending.
        type_field: Frontmatter key for note type (default: 'tipo').
        transaction: Optional active TransactionContext.
        dry_run: If True, simulates changes without writing to disk.

    Returns:
        List of tuples: (note_path, was_modified).

    Raises:
        FrontmatterError: If any note is missing or tags format is invalid.
        TaxonomyError: If strict taxonomy is enabled and an unauthorized tag is encountered.
    """
    if not mapping:
        raise FrontmatterError("Batch add-tags mapping cannot be empty.")

    root_resolved = vault_root.resolve()
    validated_items: List[Tuple[Path, List[str]]] = []

    # Pre-flight Check Phase (Strict All-or-Nothing)
    for target_raw, tags_raw in mapping.items():
        p = (root_resolved / Path(target_raw) if not Path(target_raw).is_absolute() else Path(target_raw)).resolve()

        if not p.is_file():
            raise FrontmatterError(f"Batch add-tags failed pre-flight: Note not found: '{target_raw}'")

        if not isinstance(tags_raw, (list, tuple, set)):
            raise FrontmatterError(
                f"Batch add-tags failed pre-flight: Tags for '{target_raw}' must be a list of strings, "
                f"got {type(tags_raw).__name__}"
            )

        cleaned_tags: List[str] = []
        for t in tags_raw:
            clean_t = normalize_tag(str(t))
            if clean_t and clean_t not in cleaned_tags:
                cleaned_tags.append(clean_t)

        if strict_taxonomy and allowed_taxonomy_tags is not None:
            for tag in cleaned_tags:
                if tag not in allowed_taxonomy_tags:
                    raise TaxonomyError(
                        f"Batch add-tags failed pre-flight: Tag '{tag}' for note '{target_raw}' "
                        "is not registered in taxonomy."
                    )

        validated_items.append((p, cleaned_tags))

    # Execution Phase
    results: List[Tuple[Path, bool]] = []
    for p, cleaned_tags in validated_items:
        content = p.read_text(encoding="utf-8")
        fm, _ = parse_note_content(content, type_field=type_field)

        if overwrite or fm is None:
            final_tags = cleaned_tags
        else:
            final_tags = list(dict.fromkeys(fm.tags + cleaned_tags))

        updated = update_frontmatter(content, {"tags": final_tags}, type_field=type_field)
        changed = (updated != content)

        if changed and not dry_run:
            if transaction:
                transaction.write_content(p, updated)
            else:
                p.write_text(updated, encoding="utf-8")

        results.append((p, changed))

    return results
