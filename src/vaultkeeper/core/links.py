"""Wikilink and embed resolution engine with O(1) catalog lookup."""

import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models import BrokenLink, VaultCatalog, VaultConfig
from .traversal import walk_vault_files

# Regex for [[Target#Anchor|Alias]] or ![[Target#Anchor|Alias]]
WIKILINK_PATTERN = re.compile(r"(!)?\[\[([^\]]+)\]\]")

# Regex for [Text](Target#Anchor) or ![Text](Target#Anchor)
MDLINK_PATTERN = re.compile(r"(!)?\[([^\]]*)\]\(([^)]+)\)")


def parse_wikilink_target(raw_inner: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Parse inner wikilink content into (clean_target, anchor, alias).

    Examples:
        "Note" -> ("Note", None, None)
        "Note#Section" -> ("Note", "Section", None)
        "Note#Section|Title" -> ("Note", "Section", "Title")
        "Note|Title" -> ("Note", None, "Title")
        "#Section" -> ("", "Section", None)
    """
    clean_inner = raw_inner.strip()
    alias: Optional[str] = None
    anchor: Optional[str] = None

    if "|" in clean_inner:
        target_part, alias_part = clean_inner.split("|", 1)
        alias = alias_part.strip()
    else:
        target_part = clean_inner

    if "#" in target_part:
        note_part, anchor_part = target_part.split("#", 1)
        target = note_part.strip()
        anchor = anchor_part.strip()
    else:
        target = target_part.strip()

    return target, anchor, alias


def resolve_link_target(
    catalog: VaultCatalog,
    link_target: str,
    source_file: Path,
) -> Optional[Path]:
    """Resolve a link target to an absolute file path using Obsidian's resolution logic.

    Returns:
        Path if target exists in vault, None otherwise.
    """
    clean_target = link_target.strip()
    if not clean_target:
        # Internal anchor reference to same file (e.g. [[#Heading]])
        return source_file

    # Unquote URL encoding if present (e.g. %20 -> space)
    clean_target = urllib.parse.unquote(clean_target)

    # 1. Direct path relative to source file's directory
    cand_rel = (source_file.parent / clean_target).resolve()
    if cand_rel.is_file():
        return cand_rel
    if (cand_rel.with_suffix(".md")).is_file():
        return cand_rel.with_suffix(".md")

    # 2. Path relative to vault root
    cand_vault = (catalog.vault_root / clean_target).resolve()
    if cand_vault.is_file():
        return cand_vault
    if (cand_vault.with_suffix(".md")).is_file():
        return cand_vault.with_suffix(".md")

    # 3. Lookup by stem in notes_by_stem
    stem = Path(clean_target).stem
    if stem in catalog.notes_by_stem:
        paths = catalog.notes_by_stem[stem]
        if paths:
            return paths[0]

    # 4. Lookup by filename in files_by_name (for attachments and exact filenames)
    target_name = Path(clean_target).name
    if target_name in catalog.files_by_name:
        for file_path in walk_vault_files(
            VaultConfig(root_path=catalog.vault_root),
            target_dir=catalog.vault_root,
            extensions=None,
        ):
            if file_path.name == target_name:
                return file_path

    # 5. Lookup by adding .md suffix
    target_md = f"{target_name}.md"
    if target_md in catalog.files_by_name:
        for file_path in walk_vault_files(
            VaultConfig(root_path=catalog.vault_root),
            target_dir=catalog.vault_root,
            extensions={".md"},
        ):
            if file_path.name == target_md:
                return file_path

    return None


def find_all_links_in_content(
    content: str,
    source_file: Path,
) -> List[Tuple[int, str, str, Optional[str], Optional[str], bool]]:
    """Extract all wikilinks and markdown links from note text.

    Returns list of:
        (line_number, raw_link, clean_target, anchor, alias, is_embed)
    """
    results = []
    lines = content.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        # 1. Wikilinks
        for match in WIKILINK_PATTERN.finditer(line):
            is_embed = match.group(1) == "!"
            raw_inner = match.group(2)
            raw_link = match.group(0)
            target, anchor, alias = parse_wikilink_target(raw_inner)
            results.append((line_idx, raw_link, target, anchor, alias, is_embed))

        # 2. Markdown Links [Text](Path)
        for match in MDLINK_PATTERN.finditer(line):
            is_embed = match.group(1) == "!"
            raw_link = match.group(0)
            alias = match.group(2)
            url_target = match.group(3).strip()

            # Ignore external URLs
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url_target) or url_target.startswith("mailto:"):
                continue

            target, anchor, _ = parse_wikilink_target(url_target)
            results.append((line_idx, raw_link, target, anchor, alias, is_embed))

    return results


def scan_broken_links(
    catalog: VaultCatalog,
    config: VaultConfig,
    target_file_or_dir: Optional[Path] = None,
) -> List[BrokenLink]:
    """Scan all markdown notes in target directory or vault and return all broken links."""
    broken_links: List[BrokenLink] = []

    if target_file_or_dir and target_file_or_dir.is_file():
        note_files = [target_file_or_dir]
    else:
        note_files = list(walk_vault_files(config, target_file_or_dir, extensions={".md"}))

    for note_path in note_files:
        try:
            content = note_path.read_text(encoding="utf-8")
        except Exception:
            continue

        links = find_all_links_in_content(content, note_path)
        for line_no, raw_link, target, anchor, alias, _ in links:
            if not target:
                continue

            resolved = resolve_link_target(catalog, target, note_path)
            if resolved is None:
                broken_links.append(
                    BrokenLink(
                        source_file=note_path,
                        line_number=line_no,
                        raw_target=raw_link,
                        clean_target=target,
                        anchor=anchor,
                        alias=alias,
                    )
                )

    return broken_links


def find_stem_collisions(catalog: VaultCatalog) -> Dict[str, List[Path]]:
    """Return dictionary of note stems that exist in multiple locations."""
    return {stem: paths for stem, paths in catalog.notes_by_stem.items() if len(paths) > 1}


class WikilinkEngine:
    """Unified engine for parsing, extracting, and refactoring wikilinks across the vault."""

    def __init__(self, config: VaultConfig) -> None:
        self.config = config

    def extract_links(
        self,
        content: str,
        source_file: Path,
    ) -> List[Tuple[int, str, str, Optional[str], Optional[str], bool]]:
        """Extract all links from markdown content."""
        return find_all_links_in_content(content, source_file)

    def replace_wikilink_target(
        self,
        content: str,
        old_target: str,
        new_target: str,
    ) -> Tuple[str, int]:
        """Replace occurrences of a target stem in wikilinks and markdown links."""
        escaped_old = re.escape(old_target)
        count = 0

        # 1. Wikilinks: [[Old_Target#Anchor|Alias]] -> [[New_Target#Anchor|Alias]]
        wiki_pattern = re.compile(r"(!?\[\[)" + escaped_old + r"((?:#[^\]|]*)?)((?:\|[^\]]*)?)(\]\])")

        def repl_wiki(m: re.Match) -> str:
            nonlocal count
            count += 1
            return f"{m.group(1)}{new_target}{m.group(2)}{m.group(3)}{m.group(4)}"

        new_content = wiki_pattern.sub(repl_wiki, content)

        # 2. Markdown Links: [Text](path/Old_Target.md) -> [Text](path/New_Target.md)
        md_pattern = re.compile(
            r"(!?\[[^\]]*\]\()([^\)\n]*?)(?:\b|\b(?<=[/_]))" + escaped_old + r"(\.md|\b)([^\)\n]*\))"
        )

        def repl_md(m: re.Match) -> str:
            nonlocal count
            count += 1
            return f"{m.group(1)}{m.group(2)}{new_target}{m.group(3)}{m.group(4)}"

        new_content = md_pattern.sub(repl_md, new_content)
        return new_content, count

    def replace_embed_with_link(
        self,
        content: str,
        filename: str,
        external_url: str,
        callout_label: str = "Allegato archiviato su storage freddo",
    ) -> Tuple[str, int]:
        """Replace media embed syntax ![[File.ext]] with a callout external link."""
        escaped_name = re.escape(filename)
        count = 0

        # Match ![[Filename]] or ![[Filename|Alias]]
        pattern = re.compile(r"(!\[\[" + escaped_name + r"(?:\|[^\]]*)?\]\])")

        def repl(m: re.Match) -> str:
            nonlocal count
            count += 1
            return f"> [!INFO] {callout_label}:\n> [{filename}]({external_url})"

        new_content = pattern.sub(repl, content)

        # Also match standard markdown embed ![Alias](...Filename)
        pattern_md = re.compile(r"(!\[[^\]]*\]\([^\)\n]*" + escaped_name + r"\))")

        def repl_md(m: re.Match) -> str:
            nonlocal count
            count += 1
            return f"> [!INFO] {callout_label}:\n> [{filename}]({external_url})"

        new_content = pattern_md.sub(repl_md, new_content)
        return new_content, count

    def refactor_in_vault(
        self,
        old_stem: str,
        new_stem: str,
        transaction: Optional[Any] = None,
        dry_run: bool = False,
    ) -> int:
        """Scan and refactor all wikilinks pointing to old_stem across all vault notes."""
        total_links = 0
        for note_path in walk_vault_files(self.config, target_dir=self.config.root_path, extensions={".md"}):
            try:
                content = note_path.read_text(encoding="utf-8")
            except Exception:
                continue

            updated_content, count = self.replace_wikilink_target(content, old_stem, new_stem)
            if count > 0:
                total_links += count
                if not dry_run:
                    if transaction:
                        transaction.write_content(note_path, updated_content)
                    else:
                        note_path.write_text(updated_content, encoding="utf-8")

        return total_links
