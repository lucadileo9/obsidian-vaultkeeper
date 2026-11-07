"""Safe round-trip YAML frontmatter parser, updater and tag taxonomy validator."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from ..exceptions import FrontmatterError, TaxonomyError
from ..models import Frontmatter, Note

FRONTMATTER_PATTERN = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)
CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```|`[^`\n]+`")
MATH_BLOCK_PATTERN = re.compile(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$")
C_DIRECTIVE_PATTERN = re.compile(r"^\s*#(?:include|define|undef|ifdef|ifndef|if|elif|else|endif|pragma)\b", re.MULTILINE)
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
