"""High-level Vault facade providing pure Python API for all vault operations."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from proteus.core import ConfigurationManager

from .config import load_vault_config
from .core.attachments import (
    find_heavy_files,
    find_orphan_attachments,
    hard_delete_attachment,
    soft_delete_attachment,
)
from .core.audit import run_audit
from .core.document import MarkdownDocument
from .core.frontmatter import (
    parse_note_content,
    read_note,
    update_frontmatter,
)
from .core.graph import GraphTelemetry
from .core.indices import IndexManager, write_folder_index
from .core.journal import TransactionJournal
from .core.lifecycle import archive_item, move_item, offload_media, rename_item
from .core.links import WikilinkEngine, find_stem_collisions, scan_broken_links
from .core.map import VaultMapEngine
from .core.naming import batch_normalize, normalize_stem
from .core.search import SearchEngine
from .core.taxonomy import TaxonomyEngine
from .core.templates import TemplateEngine, resolve_target_folder
from .core.traversal import build_vault_catalog, walk_vault_directories
from .exceptions import CreationError, FrontmatterError, TaxonomyError, VaultNotFoundError
from .models import (
    ArchiveResult,
    AuditReport,
    BrokenLink,
    CreateResult,
    GraphHealthReport,
    MoveResult,
    Note,
    OffloadResult,
    OrphanAttachment,
    RenameResult,
    SearchResult,
    TagMutationResult,
    TransactionRecord,
    UndoResult,
    VaultCatalog,
    VaultConfig,
    VaultMapReport,
)


class Vault:
    """Universal facade for interacting with an Obsidian or document vault.

    All methods are purely computational: they return domain models or throw
    typed exceptions. Zero print() statements or sys.exit() calls are executed.
    """

    def __init__(
        self,
        root_path: Optional[Union[str, Path]] = None,
        config_file: Optional[Union[str, Path]] = None,
    ) -> None:
        p_root = Path(root_path).resolve() if root_path else None
        p_cfg = Path(config_file).resolve() if config_file else None
        self.config: VaultConfig = load_vault_config(root_path=p_root, config_file=p_cfg)
        self._catalog: Optional[VaultCatalog] = None
        self.journal: TransactionJournal = TransactionJournal(
            self.root,
            max_transactions=self.config.max_undo_history,
        )

    @property
    def root(self) -> Path:
        """Return the root path of the vault."""
        return self.config.root_path

    @property
    def catalog(self) -> VaultCatalog:
        """Return or lazily construct the in-memory vault catalog."""
        if self._catalog is None:
            self._catalog = build_vault_catalog(self.config)
        return self._catalog

    def refresh(self) -> None:
        """Invalidate the in-memory catalog cache."""
        self._catalog = None

    def audit(self, phases: Optional[List[int]] = None) -> AuditReport:
        """Execute multi-phase diagnostic audit and return structured report."""
        return run_audit(self.config, phases_to_run=phases)

    def check_links(
        self,
        target: Optional[Union[str, Path]] = None,
    ) -> List[BrokenLink]:
        """Scan notes for unresolved wikilinks or media embeds."""
        target_path = Path(target).resolve() if target else None
        return scan_broken_links(self.catalog, self.config, target_file_or_dir=target_path)

    def stem_collisions(self) -> Dict[str, List[Path]]:
        """Identify notes that share identical stems across different folders."""
        return find_stem_collisions(self.catalog)

    def find_orphans(
        self,
        target: Optional[Union[str, Path]] = None,
    ) -> List[OrphanAttachment]:
        """Find media or attachment files not referenced by any markdown note."""
        target_path = Path(target).resolve() if target else None
        return find_orphan_attachments(self.catalog, self.config, target_dir=target_path)

    def find_heavy_files(self) -> List[Tuple[Path, int]]:
        """Find files exceeding configured heavy file threshold."""
        return find_heavy_files(self.catalog, self.config)

    def clean_attachments(
        self,
        target: Optional[Union[str, Path]] = None,
        hard_delete: bool = False,
        dry_run: bool = False,
    ) -> List[Tuple[Path, Optional[Path]]]:
        """Clean orphan attachments by soft-deleting to .trash or permanently removing.

        Returns list of tuples: (original_path, destination_or_none)
        """
        orphans = self.find_orphans(target=target)
        results: List[Tuple[Path, Optional[Path]]] = []

        if dry_run:
            for orphan in orphans:
                orig = orphan.file_path
                dest = (self.root / self.config.trash_folder / orphan.rel_path) if not hard_delete else None
                results.append((orig, dest))
            return results

        if orphans:
            desc = f"Clean {len(orphans)} orphan attachments ({'hard' if hard_delete else 'soft'} delete)"
            with self.journal.begin_transaction("clean-attachments", desc) as tx:
                for orphan in orphans:
                    orig = orphan.file_path
                    if hard_delete:
                        hard_delete_attachment(orig, transaction=tx)
                        results.append((orig, None))
                    else:
                        dest = soft_delete_attachment(orig, self.root, self.config.trash_folder, transaction=tx)
                        results.append((orig, dest))
            self.refresh()

        return results

    def normalize_names(
        self,
        target: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
    ) -> List[Tuple[Path, Path, int]]:
        """Normalize file names according to style and synchronize wikilinks.

        Returns list of tuples: (old_path, new_path, updated_links_count)
        """
        target_path = Path(target).resolve() if target else None
        if dry_run:
            return batch_normalize(self.catalog, self.config, target_dir=target_path, dry_run=True)

        with self.journal.begin_transaction("normalize-names", "Batch normalize vault item names") as tx:
            results = batch_normalize(
                self.catalog,
                self.config,
                target_dir=target_path,
                dry_run=False,
                transaction=tx,
            )

        if results:
            self.refresh()
        return results

    def generate_indices(
        self,
        target: Optional[Union[str, Path]] = None,
        recursive: bool = True,
        dry_run: bool = False,
    ) -> List[Tuple[Path, bool]]:
        """Generate or update MOC index notes for folders.

        Returns list of tuples: (index_path, was_created_or_modified)
        """
        results: List[Tuple[Path, bool]] = []
        base_dir = Path(target).resolve() if target else self.root

        if not base_dir.is_dir():
            raise VaultNotFoundError(f"Target is not a directory: {base_dir}")

        # Index the target directory itself
        idx_path, changed = write_folder_index(base_dir, self.config, self.catalog, dry_run=dry_run)
        results.append((idx_path, changed))

        if recursive:
            for d in walk_vault_directories(self.config, target_dir=base_dir):
                idx_path, changed = write_folder_index(d, self.config, self.catalog, dry_run=dry_run)
                results.append((idx_path, changed))

        if not dry_run:
            self.refresh()

        return results

    def get_note(self, file_path: Union[str, Path]) -> Note:
        """Read and parse a Markdown note from the vault."""
        p = Path(file_path).resolve()
        return read_note(p, self.root, type_field=self.config.type_field)

    def set_frontmatter_type(
        self,
        target: Union[str, Path],
        new_type: str,
        dry_run: bool = False,
    ) -> bool:
        """Update or insert the tipo field in a note's frontmatter."""
        note_path = Path(target).resolve()
        if not note_path.is_file():
            raise FrontmatterError(f"Note not found: {note_path}")

        content = note_path.read_text(encoding="utf-8")
        updated = update_frontmatter(content, {self.config.type_field: new_type})
        if updated == content:
            return False

        if not dry_run:
            with self.journal.begin_transaction("frontmatter", f"Set tipo to '{new_type}' in {note_path.name}") as tx:
                tx.write_content(note_path, updated)
            self.refresh()

        return True

    def add_frontmatter_tags(
        self,
        target: Union[str, Path],
        tags: List[str],
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> bool:
        """Add or overwrite tags in a note's YAML frontmatter."""
        note_path = Path(target).resolve()
        if not note_path.is_file():
            raise FrontmatterError(f"Note not found: {note_path}")

        content = note_path.read_text(encoding="utf-8")
        fm, _ = parse_note_content(content, type_field=self.config.type_field)

        if overwrite or fm is None:
            new_tags = list(dict.fromkeys(tags))
        else:
            existing = fm.tags
            new_tags = list(dict.fromkeys(existing + tags))

        updated = update_frontmatter(content, {"tags": new_tags})
        if updated == content:
            return False

        if not dry_run:
            desc = f"{'Overwrite' if overwrite else 'Add'} tags in {note_path.name}"
            with self.journal.begin_transaction("frontmatter", desc) as tx:
                tx.write_content(note_path, updated)
            self.refresh()

        return True

    def history(self, limit: int = 20) -> List[TransactionRecord]:
        """List historical transactions from newest to oldest."""
        return self.journal.list_transactions(limit=limit)

    def undo(self, tx_id: Optional[str] = None, dry_run: bool = False) -> UndoResult:
        """Revert a transaction and refresh in-memory catalog."""
        result = self.journal.undo(tx_id=tx_id, dry_run=dry_run)
        if result.success and not dry_run:
            self.refresh()
        return result

    def get_document(self, file_path: Union[str, Path]) -> MarkdownDocument:
        """Load and return an object-oriented MarkdownDocument for a note."""
        p = Path(file_path).resolve()
        return MarkdownDocument.from_file(p, type_field=self.config.type_field)

    def rename(
        self,
        old_path: Union[str, Path],
        new_name: str,
        skip_links: bool = False,
        dry_run: bool = False,
    ) -> RenameResult:
        """Rename a note or asset with global wikilink refactoring and index synchronization."""
        source_p = Path(old_path).resolve()
        idx_mgr = IndexManager(self.config)
        link_engine = WikilinkEngine(self.config)

        if dry_run:
            return rename_item(
                self.catalog,
                self.config,
                idx_mgr,
                link_engine,
                source_p,
                new_name,
                skip_links=skip_links,
                dry_run=True,
            )

        with self.journal.begin_transaction("rename", f"Rename {source_p.name} to {new_name}") as tx:
            res = rename_item(
                self.catalog,
                self.config,
                idx_mgr,
                link_engine,
                source_p,
                new_name,
                skip_links=skip_links,
                transaction=tx,
                dry_run=False,
            )

        self.refresh()
        return res

    def move(
        self,
        source_path: Union[str, Path],
        dest_folder: Union[str, Path],
        dry_run: bool = False,
    ) -> MoveResult:
        """Move a file or folder into a different Johnny.Decimal directory."""
        source_p = Path(source_path).resolve()
        dest_p = Path(dest_folder).resolve()
        idx_mgr = IndexManager(self.config)

        if dry_run:
            return move_item(
                self.config,
                idx_mgr,
                source_p,
                dest_p,
                dry_run=True,
            )

        with self.journal.begin_transaction("move", f"Move {source_p.name} to {dest_p.name}") as tx:
            res = move_item(
                self.config,
                idx_mgr,
                source_p,
                dest_p,
                transaction=tx,
                dry_run=False,
            )

        self.refresh()
        return res

    def archive(
        self,
        item_path: Union[str, Path],
        no_tombstone: bool = False,
        dry_run: bool = False,
    ) -> ArchiveResult:
        """Archive a note or project folder to mirror cold storage with Tombstone support."""
        item_p = Path(item_path).resolve()
        idx_mgr = IndexManager(self.config)

        if dry_run:
            return archive_item(
                self.config,
                idx_mgr,
                item_p,
                no_tombstone=no_tombstone,
                dry_run=True,
            )

        with self.journal.begin_transaction("archive", f"Archive {item_p.name}") as tx:
            res = archive_item(
                self.config,
                idx_mgr,
                item_p,
                no_tombstone=no_tombstone,
                transaction=tx,
                dry_run=False,
            )

        self.refresh()
        return res

    def offload(
        self,
        target: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
    ) -> OffloadResult:
        """Offload heavy binary files (>50MB or specific target) to cold storage."""
        link_engine = WikilinkEngine(self.config)

        if dry_run:
            return offload_media(
                self.catalog,
                self.config,
                link_engine,
                target=target,
                dry_run=True,
            )

        desc = f"Offload media target: {target}" if target else "Offload heavy media files"
        with self.journal.begin_transaction("offload", desc) as tx:
            res = offload_media(
                self.catalog,
                self.config,
                link_engine,
                target=target,
                transaction=tx,
                dry_run=False,
            )

        if res.offloaded_files:
            self.refresh()
        return res

    def tags_show(self, query: Optional[str] = None) -> List[str]:
        """Return registered taxonomy tags, optionally filtered by search query."""
        engine = TaxonomyEngine(self.config)
        return engine.search_tags(query=query)

    def tags_add(
        self,
        tag: str,
        section: Optional[str] = None,
        dry_run: bool = False,
    ) -> TagMutationResult:
        """Add a tag to the controlled taxonomy file in alphabetical order."""
        engine = TaxonomyEngine(self.config)
        if dry_run:
            return engine.add_tag(tag, section=section, dry_run=True)

        with self.journal.begin_transaction("tags", f"Add tag '{tag}' to taxonomy") as tx:
            res = engine.add_tag(tag, section=section, transaction=tx, dry_run=False)

        self.refresh()
        return res

    def tags_remove(
        self,
        tag: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> TagMutationResult:
        """Remove a tag from the controlled taxonomy file."""
        engine = TaxonomyEngine(self.config)
        if dry_run:
            return engine.remove_tag(tag, force=force, dry_run=True)

        with self.journal.begin_transaction("tags", f"Remove tag '{tag}' from taxonomy") as tx:
            res = engine.remove_tag(tag, force=force, transaction=tx, dry_run=False)

        self.refresh()
        return res

    def config_show(self) -> Dict[str, Any]:
        """Return the complete active configuration dictionary."""
        cm = ConfigurationManager()
        cfg_file = self.root / "vault.toml"
        if cfg_file.is_file():
            cm.load(str(cfg_file))
        return cm.get_all()

    def config_set(self, key: str, value: Any, dry_run: bool = False) -> bool:
        """Update a configuration directive in vault.toml."""
        cfg_file = self.root / "vault.toml"
        cm = ConfigurationManager()
        if cfg_file.is_file():
            cm.load(str(cfg_file))

        typed_val: Any = value
        if isinstance(value, str):
            if value.lower() in ("true", "yes", "on"):
                typed_val = True
            elif value.lower() in ("false", "no", "off"):
                typed_val = False
            else:
                try:
                    typed_val = int(value)
                except ValueError:
                    try:
                        typed_val = float(value)
                    except ValueError:
                        typed_val = value

        cm.set(key, typed_val)

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp_f:
            tmp_p = Path(tmp_f.name)
        try:
            cm.save(str(tmp_p))
            new_content = tmp_p.read_text(encoding="utf-8")
        finally:
            if tmp_p.exists():
                tmp_p.unlink()

        if dry_run:
            return True

        with self.journal.begin_transaction("config", f"Update {key} = {value}") as tx:
            tx.write_content(cfg_file, new_content)

        self.config = load_vault_config(root_path=self.root, config_file=cfg_file)
        self.refresh()
        return True

    def search(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        tipo: Optional[str] = None,
        links_to: Optional[str] = None,
        folder: Optional[Union[str, Path]] = None,
    ) -> SearchResult:
        """Search notes in the vault matching combined criteria."""
        engine = SearchEngine(self.config, self.catalog)
        return engine.search(query=query, tag=tag, tipo=tipo, links_to=links_to, folder=folder)

    def graph_health(self) -> GraphHealthReport:
        """Execute non-punitive topological graph diagnostics."""
        telemetry = GraphTelemetry(self.config, self.catalog)
        return telemetry.analyze()

    def vault_map(
        self,
        output_file: Optional[Union[str, Path]] = None,
    ) -> Tuple[VaultMapReport, Optional[Path]]:
        """Generate high-level Johnny.Decimal area telemetry and master vault map."""
        engine = VaultMapEngine(self.config)
        report = engine.generate_report()
        out_path: Optional[Path] = None
        if output_file:
            out_p = Path(output_file)
            out_path = engine.write_map_file(output_path=out_p, report=report)
        return report, out_path

    def create(
        self,
        title: str,
        tipo: str,
        folder: Optional[Union[str, Path]] = None,
        tags: Optional[List[str]] = None,
        template: Optional[str] = None,
        extra_vars: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> CreateResult:
        """Create a standardized note using templates, strict validation, and folder auto-routing.

        Args:
            title: Title of the note.
            tipo: Note classification (e.g. 'Appunto', 'Progetto', 'Contatto', 'Risorsa').
            folder: Optional folder path. If None, auto-routes via Johnny.Decimal.
            tags: Optional list of taxonomy tags.
            template: Optional template name or path.
            extra_vars: Optional custom interpolation variables.
            dry_run: If True, simulates creation without modifying filesystem.

        Returns:
            CreateResult domain model.

        Raises:
            CreationError: If title is empty, type is disallowed, or stem collision occurs.
            TaxonomyError: If strict taxonomy is enabled and invalid tags are supplied.
            TemplateError: If a requested template is not found.
        """
        clean_title = title.strip()
        if not clean_title:
            raise CreationError("Note title cannot be empty.")

        clean_tipo = tipo.strip()
        matched_types = [t for t in self.config.allowed_types if t.lower() == clean_tipo.lower()]
        if not matched_types:
            raise CreationError(f"Invalid note type '{tipo}'. Allowed types: {', '.join(self.config.allowed_types)}")
        effective_tipo = matched_types[0]

        cleaned_tags: List[str] = []
        if tags:
            for t in tags:
                for part in t.split(","):
                    stripped = part.strip().lstrip("#")
                    if stripped and stripped not in cleaned_tags:
                        cleaned_tags.append(stripped)

            if self.config.strict_taxonomy:
                tax_engine = TaxonomyEngine(self.config)
                for tag in cleaned_tags:
                    if not tax_engine.is_valid_tag(tag):
                        raise TaxonomyError(f"Tag '{tag}' is not registered in taxonomy '{self.config.taxonomy_file}'.")

        stem = normalize_stem(clean_title, self.config)
        if not stem:
            raise CreationError(f"Normalized stem for title '{title}' is empty.")

        if stem in self.catalog.notes_by_stem and self.catalog.notes_by_stem[stem]:
            existing_paths = self.catalog.notes_by_stem[stem]
            first_path = existing_paths[0]
            try:
                existing_rel = first_path.relative_to(self.root)
            except ValueError:
                existing_rel = first_path
            raise CreationError(f"Stem collision: a note with stem '{stem}' already exists at '{existing_rel}'.")

        target_folder = resolve_target_folder(self.root, effective_tipo, folder)
        dest_file = target_folder / f"{stem}.md"
        if dest_file.exists():
            raise CreationError(f"File already exists at destination: '{dest_file}'.")

        tmpl_engine = TemplateEngine(self.config)
        template_used: Optional[str] = None
        if template:
            template_path = tmpl_engine.resolve_template_path(template)
            if template_path and template_path.is_file():
                raw_tmpl = template_path.read_text(encoding="utf-8")
                template_used = template_path.name
            else:
                raw_tmpl = tmpl_engine.get_default_template(effective_tipo)
        else:
            template_path = tmpl_engine.find_template(effective_tipo)
            if template_path and template_path.is_file():
                raw_tmpl = template_path.read_text(encoding="utf-8")
                template_used = template_path.name
            else:
                raw_tmpl = tmpl_engine.get_default_template(effective_tipo)

        rendered_content = tmpl_engine.render_template(
            raw_content=raw_tmpl,
            title=clean_title,
            stem=stem,
            tipo=effective_tipo,
            tags=cleaned_tags,
            extra_vars=extra_vars,
        )

        index_mgr = IndexManager(self.config)
        expected_idx_path = index_mgr.get_index_path(target_folder)
        try:
            rel_path = dest_file.relative_to(self.root)
        except ValueError:
            rel_path = dest_file

        if dry_run:
            return CreateResult(
                file_path=dest_file,
                rel_path=rel_path,
                stem=stem,
                title=clean_title,
                tipo=effective_tipo,
                tags=cleaned_tags,
                template_used=template_used,
                index_updated=True,
                index_path=expected_idx_path,
                tx_id=None,
                dry_run=True,
            )

        with self.journal.begin_transaction("create", f"Create note '{clean_title}' ({dest_file.name})") as tx:
            target_folder.mkdir(parents=True, exist_ok=True)
            tx.write_content(dest_file, rendered_content)
            idx_path, idx_updated = index_mgr.rebuild_index(target_folder, transaction=tx, dry_run=False)

        self.refresh()
        return CreateResult(
            file_path=dest_file,
            rel_path=rel_path,
            stem=stem,
            title=clean_title,
            tipo=effective_tipo,
            tags=cleaned_tags,
            template_used=template_used,
            index_updated=idx_updated,
            index_path=idx_path,
            tx_id=tx.tx_id,
            dry_run=False,
        )
