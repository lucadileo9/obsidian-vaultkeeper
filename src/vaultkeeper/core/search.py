"""Semantic search engine aware of Obsidian frontmatter, tags, links, and Johnny.Decimal folders."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from ..models import SearchResult, SearchResultItem, VaultCatalog, VaultConfig
from ..utils.helpers import truncate_text
from .frontmatter import extract_inline_tags, parse_note_content
from .links import WikilinkEngine
from .traversal import walk_vault_files


class SearchEngine:
    """Obsidian-aware semantic search engine supporting tag, type, link, and folder filters."""

    def __init__(self, config: VaultConfig, catalog: Optional[VaultCatalog] = None) -> None:
        self.config = config
        self.catalog = catalog
        self.link_engine = WikilinkEngine(config)

    def search(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        tipo: Optional[str] = None,
        links_to: Optional[str] = None,
        folder: Optional[Union[str, Path]] = None,
    ) -> SearchResult:
        """Search notes in the vault matching combined criteria."""
        folder_filter_p: Optional[Path] = None
        if folder:
            p = Path(folder)
            folder_filter_p = (self.config.root_path / p if not p.is_absolute() else p).resolve()

        clean_query = query.strip() if query else None
        clean_tag = tag.lstrip("#").strip().lower() if tag else None
        clean_tipo = tipo.strip().lower() if tipo else None
        clean_links_to = Path(links_to).stem if links_to else None

        active_filters: Dict[str, Any] = {}
        if clean_tag:
            active_filters["tag"] = clean_tag
        if clean_tipo:
            active_filters["type"] = clean_tipo
        if clean_links_to:
            active_filters["links_to"] = clean_links_to
        if folder_filter_p:
            active_filters["folder"] = folder_filter_p.as_posix()

        items: List[SearchResultItem] = []

        scan_dir = folder_filter_p if folder_filter_p and folder_filter_p.is_dir() else self.config.root_path

        for note_path in walk_vault_files(self.config, target_dir=scan_dir, extensions={".md"}):
            if folder_filter_p and not note_path.is_relative_to(folder_filter_p):
                continue

            try:
                content = note_path.read_text(encoding="utf-8")
            except Exception:
                continue

            fm, body = parse_note_content(content, type_field=self.config.type_field)

            # 1. Type filter
            note_tipo = fm.tipo if fm else None
            if clean_tipo:
                if not note_tipo or note_tipo.strip().lower() != clean_tipo:
                    continue

            # 2. Tag filter
            note_tags: Set[str] = set()
            if fm and fm.tags:
                note_tags.update(t.lstrip("#").strip().lower() for t in fm.tags)
            inline_tags = extract_inline_tags(
                body,
                protect_c=self.config.protect_c_directives,
                protect_hex=self.config.protect_hex_colors,
            )
            note_tags.update(t.lstrip("#").strip().lower() for t in inline_tags)

            if clean_tag:
                tag_matched = any(t == clean_tag or t.startswith(f"{clean_tag}/") for t in note_tags)
                if not tag_matched:
                    continue

            # 3. Links-to filter
            if clean_links_to:
                links = self.link_engine.extract_links(content, note_path)
                has_link = any(
                    Path(clean_target).stem.lower() == clean_links_to.lower()
                    for _, _, clean_target, _, _, _ in links
                )
                if not has_link:
                    continue

            # 4. Text query filter
            matched_terms: List[str] = []
            snippet = ""

            title = note_path.stem.replace("_", " ")
            # Try to read H1 title if present
            for line in body.splitlines():
                if line.strip().startswith("# "):
                    title = line.strip().lstrip("# ").strip()
                    break

            if clean_query:
                q_lower = clean_query.lower()
                stem_match = q_lower in note_path.stem.lower()
                title_match = q_lower in title.lower()
                body_match = q_lower in body.lower()
                tag_match = any(q_lower in t for t in note_tags)

                if not (stem_match or title_match or body_match or tag_match):
                    continue

                if stem_match or title_match:
                    matched_terms.append("title")
                if tag_match:
                    matched_terms.append("tag")
                if body_match:
                    matched_terms.append("body")

                # Extract surrounding snippet
                lines = body.splitlines()
                for line in lines:
                    if q_lower in line.lower() and not line.strip().startswith("#"):
                        snippet = truncate_text(line.strip(), 160)
                        break
                if not snippet and lines:
                    for line in lines:
                        if line.strip() and not line.strip().startswith("#"):
                            snippet = truncate_text(line.strip(), 160)
                            break
            else:
                # If no text query, extract first non-heading sentence for snippet
                for line in body.splitlines():
                    if line.strip() and not line.strip().startswith("#") and not line.strip().startswith(">"):
                        snippet = truncate_text(line.strip(), 160)
                        break

            try:
                rel_p = note_path.relative_to(self.config.root_path).as_posix()
            except ValueError:
                rel_p = note_path.as_posix()

            items.append(
                SearchResultItem(
                    file_path=note_path,
                    rel_path=rel_p,
                    title=title,
                    tipo=note_tipo,
                    tags=sorted(list(note_tags)),
                    matched_terms=matched_terms,
                    snippet=snippet,
                )
            )

        # Sort items by rel_path
        items.sort(key=lambda it: it.rel_path)

        return SearchResult(
            query=clean_query,
            filters=active_filters,
            items=items,
            total_matches=len(items),
        )
