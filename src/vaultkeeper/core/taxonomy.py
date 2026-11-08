"""TaxonomyEngine: centralized management and validation of 00_Tassonomia_Tag.md."""

import re
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from ..exceptions import TaxonomyError
from ..models import TagMutationResult, VaultConfig
from .frontmatter import extract_inline_tags, parse_note_content, parse_taxonomy_file
from .traversal import walk_vault_files


class TaxonomyEngine:
    """Centralized manager for controlled tag taxonomy loading, search, and mutation."""

    def __init__(self, config: VaultConfig) -> None:
        self.config = config

    @property
    def taxonomy_path(self) -> Path:
        """Resolve path to 00_Tassonomia_Tag.md."""
        fname = self.config.taxonomy_file or "00_Tassonomia_Tag.md"
        # 1. Check relative to root_path
        p1 = (self.config.root_path / fname).resolve()
        if p1.is_file():
            return p1

        # 2. Check 00-09_Meta / 00_Tassonomia_Tag.md
        p2 = (self.config.root_path / "00-09_Meta" / Path(fname).name).resolve()
        if p2.is_file():
            return p2

        # 3. Check any directory in vault
        for f in walk_vault_files(self.config, target_dir=self.config.root_path, extensions={".md"}):
            if f.name == Path(fname).name:
                return f.resolve()

        return p1

    def load_taxonomy(self) -> Set[str]:
        """Load and return all canonical registered tag names."""
        tax_path = self.taxonomy_path
        if not tax_path.is_file():
            return set()
        return parse_taxonomy_file(tax_path)

    def is_valid_tag(self, tag: str) -> bool:
        """Verify whether a tag is compliant with the controlled taxonomy."""
        clean = tag.lstrip("#").strip()
        return clean in self.load_taxonomy()

    def search_tags(self, query: Optional[str] = None) -> List[str]:
        """Return registered tags, optionally filtered by search substring."""
        tags = sorted(list(self.load_taxonomy()))
        if not query:
            return tags
        q = query.lower().strip()
        return [t for t in tags if q in t.lower()]

    def count_tag_usage(self, tag: str) -> int:
        """Count how many vault notes reference this tag."""
        clean = tag.lstrip("#").strip()
        count = 0
        for note_path in walk_vault_files(self.config, target_dir=self.config.root_path, extensions={".md"}):
            if note_path.name == self.taxonomy_path.name:
                continue
            try:
                content = note_path.read_text(encoding="utf-8")
            except Exception:
                continue

            fm, body = parse_note_content(content, type_field=self.config.type_field)
            note_tags: Set[str] = set()
            if fm and fm.tags:
                note_tags.update(t.lstrip("#").strip() for t in fm.tags)
            inline = extract_inline_tags(
                body,
                protect_c=self.config.protect_c_directives,
                protect_hex=self.config.protect_hex_colors,
            )
            note_tags.update(t.lstrip("#").strip() for t in inline)

            if clean in note_tags:
                count += 1

        return count

    def add_tag(
        self,
        tag: str,
        section: Optional[str] = None,
        transaction: Optional[Any] = None,
        dry_run: bool = False,
    ) -> TagMutationResult:
        """Add a new tag into the controlled taxonomy file in alphabetical order."""
        clean = tag.lstrip("#").strip()
        if not clean or re.search(r"\s", clean):
            raise TaxonomyError(f"Invalid tag format '{tag}': tags must not contain whitespace.")

        tax_path = self.taxonomy_path
        if not tax_path.is_file():
            # Create a default taxonomy file if missing
            tax_path.parent.mkdir(parents=True, exist_ok=True)
            initial_content = f"# Tassonomia Tag del Vault\n\n- #{clean}\n"
            if not dry_run:
                if transaction:
                    transaction.write_content(tax_path, initial_content)
                else:
                    tax_path.write_text(initial_content, encoding="utf-8")
            return TagMutationResult(
                tag=clean,
                action="add",
                taxonomy_file=tax_path,
                notes_affected_count=0,
                tx_id=getattr(transaction, "tx_id", None),
            )

        existing_tags = self.load_taxonomy()
        if clean in existing_tags:
            return TagMutationResult(
                tag=clean,
                action="add",
                taxonomy_file=tax_path,
                notes_affected_count=0,
                tx_id=getattr(transaction, "tx_id", None),
            )

        content = tax_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Determine target section heading
        target_heading = None
        if section:
            target_heading = section.strip()
        elif "/" in clean:
            prefix = clean.split("/")[0]
            target_heading = prefix.capitalize()

        inserted = False

        if target_heading:
            heading_regex = re.compile(r"^#+\s*" + re.escape(target_heading) + r"\s*$", re.IGNORECASE)
            in_section = False
            section_items: List[Tuple[int, str]] = []  # (index, line)

            for idx, line in enumerate(lines):
                if heading_regex.match(line):
                    in_section = True
                    continue
                if in_section and line.startswith("#"):
                    # Exited target section into a new section
                    break
                if in_section and line.strip().startswith("-"):
                    section_items.append((idx, line))

            if in_section:
                # Find alphabetical insertion point within section items
                formatted_tag = f"- #{clean}"
                insert_pos = None
                for idx, item in section_items:
                    item_clean = item.strip().lstrip("-").strip().lstrip("#").strip()
                    if clean < item_clean:
                        insert_pos = idx
                        break

                if insert_pos is not None:
                    lines.insert(insert_pos, formatted_tag)
                elif section_items:
                    # Append after last item of section
                    lines.insert(section_items[-1][0] + 1, formatted_tag)
                else:
                    # Append right below heading
                    for idx, line in enumerate(lines):
                        if heading_regex.match(line):
                            lines.insert(idx + 1, formatted_tag)
                            break
                inserted = True

        if not inserted:
            # Fallback: append in alphabetical order among all top-level list items or at end of file
            formatted_tag = f"- #{clean}"
            item_indices = [idx for idx, line in enumerate(lines) if line.strip().startswith("-")]
            insert_pos = None
            for idx in item_indices:
                item_clean = lines[idx].strip().lstrip("-").strip().lstrip("#").strip()
                if clean < item_clean:
                    insert_pos = idx
                    break

            if insert_pos is not None:
                lines.insert(insert_pos, formatted_tag)
            else:
                lines.append(formatted_tag)

        new_content = "\n".join(lines) + "\n"

        if not dry_run:
            if transaction:
                transaction.write_content(tax_path, new_content)
            else:
                tax_path.write_text(new_content, encoding="utf-8")

        return TagMutationResult(
            tag=clean,
            action="add",
            taxonomy_file=tax_path,
            notes_affected_count=0,
            tx_id=getattr(transaction, "tx_id", None),
        )

    def remove_tag(
        self,
        tag: str,
        force: bool = False,
        transaction: Optional[Any] = None,
        dry_run: bool = False,
    ) -> TagMutationResult:
        """Remove a tag from the controlled taxonomy file with safety checks for active notes."""
        clean = tag.lstrip("#").strip()
        existing_tags = self.load_taxonomy()
        if clean not in existing_tags:
            raise TaxonomyError(f"Tag '{clean}' does not exist in taxonomy.")

        usage_count = self.count_tag_usage(clean)
        if usage_count > 0 and not force:
            raise TaxonomyError(
                f"Tag '{clean}' is currently referenced in {usage_count} note(s). "
                "Cannot remove active taxonomy tag without --force."
            )

        tax_path = self.taxonomy_path
        content = tax_path.read_text(encoding="utf-8")

        # Match `- #tag` or `- tag` or lines ending with `#tag`
        pattern = re.compile(r"^\s*-\s*#?" + re.escape(clean) + r"\s*$\n?", re.MULTILINE)
        new_content, count = pattern.subn("", content)

        if count == 0:
            # Try looser match
            pattern_loose = re.compile(r"#" + re.escape(clean) + r"\b")
            lines = [line_text for line_text in content.splitlines() if not pattern_loose.search(line_text)]
            new_content = "\n".join(lines) + "\n"

        if not dry_run:
            if transaction:
                transaction.write_content(tax_path, new_content)
            else:
                tax_path.write_text(new_content, encoding="utf-8")

        return TagMutationResult(
            tag=clean,
            action="remove",
            taxonomy_file=tax_path,
            notes_affected_count=usage_count,
            tx_id=getattr(transaction, "tx_id", None),
        )
