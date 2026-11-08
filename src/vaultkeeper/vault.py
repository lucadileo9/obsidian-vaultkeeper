"""High-level Vault facade providing pure Python API for all vault operations."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

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
from .core.indices import write_folder_index
from .core.journal import TransactionJournal
from .core.links import find_stem_collisions, scan_broken_links
from .core.naming import batch_normalize
from .core.traversal import build_vault_catalog, walk_vault_directories
from .exceptions import FrontmatterError, VaultNotFoundError
from .models import (
    AuditReport,
    BrokenLink,
    Note,
    OrphanAttachment,
    TransactionRecord,
    UndoResult,
    VaultCatalog,
    VaultConfig,
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
