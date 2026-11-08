"""Object-oriented domain model representing a Markdown note with frontmatter and body."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..exceptions import DocumentError
from ..models import Frontmatter
from .frontmatter import parse_note_content
from .journal import TransactionContext
from .links import find_all_links_in_content
from .naming import update_wikilinks_in_content


class MarkdownDocument:
    """Encapsulates a Markdown file's frontmatter, body, and link operations."""

    def __init__(
        self,
        path: Optional[Path] = None,
        frontmatter: Optional[Frontmatter] = None,
        body: str = "",
        type_field: str = "tipo",
    ) -> None:
        self.path = Path(path).resolve() if path else None
        self.frontmatter = frontmatter
        self.body = body
        self.type_field = type_field

    @classmethod
    def from_content(
        cls,
        content: str,
        path: Optional[Union[str, Path]] = None,
        type_field: str = "tipo",
    ) -> "MarkdownDocument":
        """Parse raw content string into a MarkdownDocument instance."""
        p = Path(path).resolve() if path else None
        fm, body = parse_note_content(content, type_field=type_field)
        return cls(path=p, frontmatter=fm, body=body, type_field=type_field)

    @classmethod
    def from_file(
        cls,
        path: Union[str, Path],
        type_field: str = "tipo",
        encoding: str = "utf-8",
    ) -> "MarkdownDocument":
        """Load and parse a markdown document directly from disk."""
        p = Path(path).resolve()
        if not p.is_file():
            raise DocumentError(f"File not found: {p}")
        try:
            content = p.read_text(encoding=encoding)
        except Exception as exc:
            raise DocumentError(f"Failed to read file '{p}': {exc}") from exc
        return cls.from_content(content, path=p, type_field=type_field)

    @property
    def metadata(self) -> Dict[str, Any]:
        """Return a copy of the frontmatter dictionary or empty dict if none."""
        if self.frontmatter:
            return dict(self.frontmatter.metadata)
        return {}

    @property
    def tipo(self) -> Optional[str]:
        """Return the note type or None."""
        return self.frontmatter.tipo if self.frontmatter else None

    @tipo.setter
    def tipo(self, value: Optional[str]) -> None:
        """Set the note type."""
        self.set_frontmatter_field(self.type_field, value)

    @property
    def tags(self) -> List[str]:
        """Return a copy of the note's frontmatter tags."""
        if self.frontmatter:
            return list(self.frontmatter.tags)
        return []

    def set_frontmatter_field(self, key: str, value: Any) -> None:
        """Set or update a specific field in the frontmatter."""
        if self.frontmatter is None:
            metadata: Dict[str, Any] = {key: value}
            self.frontmatter = Frontmatter(
                raw_content="",
                metadata=metadata,
                tipo=str(value) if key == self.type_field else None,
                tags=list(value) if key == "tags" and isinstance(value, list) else [],
            )
        else:
            self.frontmatter.metadata[key] = value
            if key == self.type_field:
                self.frontmatter.tipo = str(value) if value is not None else None
            elif key == "tags" and isinstance(value, list):
                self.frontmatter.tags = [str(t) for t in value]

    def remove_frontmatter_field(self, key: str) -> bool:
        """Remove a field from frontmatter. Returns True if removed, False otherwise."""
        if not self.frontmatter or key not in self.frontmatter.metadata:
            return False
        del self.frontmatter.metadata[key]
        if key == self.type_field:
            self.frontmatter.tipo = None
        elif key == "tags":
            self.frontmatter.tags = []
        return True

    def add_tag(self, tag: str) -> bool:
        """Add a tag to frontmatter if not already present."""
        clean = tag.strip().lstrip("#")
        current_tags = self.tags
        if clean in current_tags:
            return False
        current_tags.append(clean)
        self.set_frontmatter_field("tags", current_tags)
        return True

    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from frontmatter if present."""
        clean = tag.strip().lstrip("#")
        current_tags = self.tags
        if clean not in current_tags:
            return False
        current_tags.remove(clean)
        self.set_frontmatter_field("tags", current_tags)
        return True

    def has_tag(self, tag: str) -> bool:
        """Check if tag is in frontmatter tags."""
        clean = tag.strip().lstrip("#")
        return clean in self.tags

    def get_wikilinks(self) -> List[str]:
        """Return a list of all unique target stems referenced in the note body."""
        dummy_path = self.path or Path("note.md")
        links = find_all_links_in_content(self.body, dummy_path)
        return sorted({target for _, _, target, _, _, _ in links if target})

    def replace_wikilink(self, old_target: str, new_target: str) -> int:
        """Replace occurrences of a wikilink target stem in the body."""
        new_body, count = update_wikilinks_in_content(self.body, old_target, new_target)
        self.body = new_body
        return count

    def to_content(self) -> str:
        """Serialize frontmatter and body into valid Markdown text."""
        if not self.frontmatter or not self.frontmatter.metadata:
            return self.body

        yaml_text = yaml.safe_dump(
            self.frontmatter.metadata,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).strip()
        body_part = self.body.lstrip("\n")
        return f"---\n{yaml_text}\n---\n\n{body_part}" if body_part else f"---\n{yaml_text}\n---\n"

    def save(
        self,
        path: Optional[Union[str, Path]] = None,
        transaction: Optional[TransactionContext] = None,
        encoding: str = "utf-8",
    ) -> Path:
        """Save document to disk, optionally wrapped in a TransactionContext."""
        target_path = Path(path).resolve() if path else self.path
        if not target_path:
            raise DocumentError("Cannot save MarkdownDocument: no path specified.")

        content = self.to_content()
        if transaction:
            transaction.write_content(target_path, content, encoding=encoding)
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding=encoding)

        self.path = target_path
        return target_path
