"""Comprehensive tests for lifecycle operations: IndexManager, WikilinkEngine, rename, move, archive, and offload."""

from pathlib import Path

import pytest

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.document import MarkdownDocument
from vaultkeeper.core.indices import IndexManager
from vaultkeeper.core.lifecycle import (
    extract_summary_for_tombstone,
    move_item,
    rename_item,
)
from vaultkeeper.core.links import WikilinkEngine
from vaultkeeper.exceptions import ArchiveError, LifecycleError, NamingError, OffloadError
from vaultkeeper.vault import Vault


def test_index_manager_basic(mock_vault_with_config: Path) -> None:
    """Test IndexManager path computation, rebuild, renaming, and archiving markings."""
    cfg = load_vault_config(mock_vault_with_config)
    mgr = IndexManager(cfg)

    progetti = mock_vault_with_config / "10-19_Progetti"
    idx_path = mgr.get_index_path(progetti)
    assert idx_path.name == "00_Indice_Progetti.md"

    # Rebuild index
    path, changed = mgr.rebuild_index(progetti)
    assert changed is True
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "[[Progetto_Alpha]]" in content

    # Rebuilding again without changes should return changed=False
    _, changed2 = mgr.rebuild_index(progetti)
    assert changed2 is False

    # Rename entry in index
    mgr.rename_entry(progetti, "Progetto_Alpha", "Progetto_Nuovo")
    updated_content = path.read_text(encoding="utf-8")
    assert "[[Progetto_Nuovo]]" in updated_content
    assert "[[Progetto_Alpha]]" not in updated_content

    # Mark archived in index
    mgr.mark_archived(progetti, "Progetto_Nuovo")
    archived_content = path.read_text(encoding="utf-8")
    assert "[[Progetto_Nuovo]]" in archived_content
    assert "*(Archiviato)*" in archived_content


def test_wikilink_engine_extraction_and_replacement(mock_vault_with_config: Path) -> None:
    """Test WikilinkEngine extraction and replacement preserving anchors and aliases."""
    cfg = load_vault_config(mock_vault_with_config)
    engine = WikilinkEngine(cfg)

    text = """
Link semplice: [[Nota_Uno]]
Link con ancora: [[Nota_Uno#Sezione_Due]]
Link con alias: [[Nota_Uno|Mio Alias]]
Link ancora e alias: [[Nota_Uno#Sezione|Alias Complesso]]
Embed immagine: ![[Foto.png]]
Embed con alias: ![[Foto.png|500]]
Markdown link: [Descrizione](10-19_Progetti/Nota_Uno.md)
Markdown embed: ![Foto](90-99_Allegati/Foto.png)
"""
    # Test extraction
    links = engine.extract_links(text, Path("test.md"))
    assert len(links) == 8

    # Test replacing target
    replaced, count = engine.replace_wikilink_target(text, "Nota_Uno", "Nota_Rinominata")
    assert count == 5  # 4 wikilinks + 1 markdown link
    assert "[[Nota_Rinominata]]" in replaced
    assert "[[Nota_Rinominata#Sezione_Due]]" in replaced
    assert "[[Nota_Rinominata|Mio Alias]]" in replaced
    assert "[[Nota_Rinominata#Sezione|Alias Complesso]]" in replaced
    assert "[Descrizione](10-19_Progetti/Nota_Rinominata.md)" in replaced

    # Test replacing embed with callout link
    replaced_embed, embed_count = engine.replace_embed_with_link(
        replaced,
        "Foto.png",
        "file:///srv/storage/Archive/Foto.png",
    )
    assert embed_count == 3  # 2 wikilink embeds + 1 markdown embed
    assert "> [!INFO] Allegato archiviato su storage freddo:" in replaced_embed
    assert "[Foto.png](file:///srv/storage/Archive/Foto.png)" in replaced_embed


def test_extract_summary_for_tombstone(mock_vault_with_config: Path) -> None:
    """Test summary extraction from frontmatter, callouts, or body paragraphs."""
    # From frontmatter
    doc1 = MarkdownDocument.from_content("---\ndescrizione: Descrizione sintetica del progetto\n---\n# Titolo\nCorpo")
    assert extract_summary_for_tombstone(doc1) == "Descrizione sintetica del progetto"

    # From callout / blockquote
    doc2 = MarkdownDocument.from_content(
        "---\ntipo: Appunto\n---\n# Titolo\n> [!NOTE] Nota di sintesi strategica.\nAltro testo"
    )
    assert extract_summary_for_tombstone(doc2) == "Nota di sintesi strategica."

    # From first non-heading paragraph
    doc3 = MarkdownDocument.from_content(
        "---\ntipo: Appunto\n---\n# Titolo\n\nQuesto e' il primo paragrafo illustrativo.\nSeconda riga."
    )
    assert extract_summary_for_tombstone(doc3) == "Questo e' il primo paragrafo illustrativo."


def test_rename_item_and_undo(mock_vault_with_config: Path) -> None:
    """Test safe note renaming, incoming wikilink refactoring, H1 update, and undo."""
    v = Vault(mock_vault_with_config)
    old_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    referencing_note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    # Initial assertion
    assert "[[Nota_Beta]]" in referencing_note.read_text(encoding="utf-8")

    # Rename Nota_Beta -> Nota_Beta_Aggiornata
    res = v.rename(old_note, "Nota_Beta_Aggiornata")
    assert res.old_path.name == "Nota_Beta.md"
    assert res.new_path.name == "Nota_Beta_Aggiornata.md"
    assert res.updated_links_count >= 1
    assert res.new_path.exists()
    assert not old_note.exists()

    # Check incoming link was refactored
    ref_content = referencing_note.read_text(encoding="utf-8")
    assert "[[Nota_Beta_Aggiornata]]" in ref_content
    assert "[[Nota_Beta]]" not in ref_content

    # Check H1 inside the renamed note was updated
    new_content = res.new_path.read_text(encoding="utf-8")
    assert "# Nota Beta Aggiornata" in new_content

    # Revert via undo
    undo_res = v.undo()
    assert undo_res.success is True
    assert old_note.exists()
    assert not res.new_path.exists()
    assert "[[Nota_Beta]]" in referencing_note.read_text(encoding="utf-8")


def test_rename_item_dry_run_and_same_name(mock_vault_with_config: Path) -> None:
    """Test dry-run rename and renaming to the same name."""
    v = Vault(mock_vault_with_config)
    note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    # Same name
    res_same = v.rename(note, "Nota_Beta.md")
    assert res_same.old_path == res_same.new_path

    # Dry run
    res_dry = v.rename(note, "Nota_Beta_Nuova", dry_run=True)
    assert res_dry.new_path.name == "Nota_Beta_Nuova.md"
    assert note.exists()
    assert not (note.parent / "Nota_Beta_Nuova.md").exists()


def test_rename_preflight_collisions_and_ambiguity(mock_vault_with_config: Path) -> None:
    """Test pre-flight collision checks during rename."""
    v = Vault(mock_vault_with_config)
    note_beta = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    # Collision 1: Target exists in other folder (Progetto_Alpha exists in 10-19_Progetti)
    with pytest.raises(NamingError, match="Stem collision"):
        v.rename(note_beta, "Progetto_Alpha")

    # Collision 2: Destination file exists in same folder
    second_note = mock_vault_with_config / "20-29_Aree" / "Seconda_Nota.md"
    second_note.write_text("# Seconda\n", encoding="utf-8")
    v.refresh()
    with pytest.raises(NamingError, match="Destination already exists"):
        v.rename(note_beta, "Seconda_Nota")

    # Ambiguity: Multiple notes with same stem in different folders
    dup_note = mock_vault_with_config / "10-19_Progetti" / "Nota_Beta.md"
    dup_note.write_text("# Dup\n", encoding="utf-8")
    v.refresh()

    # Should raise error without skip_links
    with pytest.raises(NamingError, match="Ambiguous source stem"):
        v.rename(note_beta, "Nota_Beta_Disambiguata")

    # With skip_links=True, renaming physical file succeeds
    res = v.rename(note_beta, "Nota_Beta_Disambiguata", skip_links=True)
    assert res.new_path.exists()


def test_move_item_and_undo(mock_vault_with_config: Path) -> None:
    """Test moving a note between folders, updating indices, and undoing."""
    v = Vault(mock_vault_with_config)
    src_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    dest_dir = mock_vault_with_config / "10-19_Progetti"

    # Move Nota_Beta into 10-19_Progetti
    res = v.move(src_note, dest_dir)
    assert res.source_path.name == "Nota_Beta.md"
    assert res.dest_path == dest_dir / "Nota_Beta.md"
    assert res.dest_path.exists()
    assert not src_note.exists()
    assert res.old_index_updated is True
    assert res.new_index_updated is True

    # Check new index contains Nota_Beta
    new_idx = dest_dir / "00_Indice_Progetti.md"
    assert "[[Nota_Beta]]" in new_idx.read_text(encoding="utf-8")

    # Undo move
    undo_res = v.undo()
    assert undo_res.success is True
    assert src_note.exists()
    assert not (dest_dir / "Nota_Beta.md").exists()


def test_move_errors_and_dry_run(mock_vault_with_config: Path) -> None:
    """Test move error handling and dry-run."""
    v = Vault(mock_vault_with_config)
    src_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    dest_dir = mock_vault_with_config / "10-19_Progetti"

    # Dry-run
    res_dry = v.move(src_note, dest_dir, dry_run=True)
    assert res_dry.dest_path == dest_dir / "Nota_Beta.md"
    assert src_note.exists()
    assert not (dest_dir / "Nota_Beta.md").exists()

    # Non-existent source
    with pytest.raises(LifecycleError, match="Source path does not exist"):
        v.move(mock_vault_with_config / "Inesistente.md", dest_dir)

    # Destination already exists
    with pytest.raises(LifecycleError, match="Destination already exists"):
        v.move(src_note, src_note.parent)


def test_archive_item_with_tombstone_and_undo(mock_vault_with_config: Path) -> None:
    """Test archiving a note with tombstone generation, cold storage mirror, and undo."""
    v = Vault(mock_vault_with_config)
    note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    res = v.archive(note)
    assert res.tombstone_created is True
    assert res.archive_path.exists()
    assert note.exists()  # Tombstone exists at original path

    # Check tombstone contents
    tombstone_content = note.read_text(encoding="utf-8")
    assert "stato: archiviato" in tombstone_content
    assert "# Progetto Alpha (Archiviato)" in tombstone_content
    assert res.archive_path.name in tombstone_content

    # Check archived file frontmatter in cold storage
    archived_content = res.archive_path.read_text(encoding="utf-8")
    assert "stato: archiviato" in archived_content
    assert "data_archiviazione" in archived_content

    # Check index marking
    idx_content = (note.parent / "00_Indice_Progetti.md").read_text(encoding="utf-8")
    assert "[[Progetto_Alpha]]" in idx_content
    assert "*(Archiviato)*" in idx_content

    # Undo archive
    undo_res = v.undo()
    assert undo_res.success is True
    assert not res.archive_path.exists()
    orig_content = note.read_text(encoding="utf-8")
    assert "# Progetto Alpha\n" in orig_content
    assert "(Archiviato)" not in orig_content


def test_archive_without_tombstone(mock_vault_with_config: Path) -> None:
    """Test archiving with --no-tombstone mode."""
    v = Vault(mock_vault_with_config)
    note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    res = v.archive(note, no_tombstone=True)
    assert res.tombstone_created is False
    assert res.archive_path.exists()
    assert not note.exists()

    # Revert via undo
    v.undo()
    assert note.exists()


def test_archive_errors_and_dry_run(mock_vault_with_config: Path) -> None:
    """Test archive error cases and dry-run."""
    v = Vault(mock_vault_with_config)
    note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    # Dry-run
    res_dry = v.archive(note, dry_run=True)
    assert note.exists()
    assert not res_dry.archive_path.exists()

    # Nonexistent item
    with pytest.raises(ArchiveError, match="Item to archive does not exist"):
        v.archive(mock_vault_with_config / "Ghost.md")


def test_offload_media_and_undo(mock_vault_with_config: Path) -> None:
    """Test offloading heavy media to cold storage, updating note embeds, and undoing."""
    v = Vault(mock_vault_with_config)

    # Create a dummy large media file in attachments folder
    large_media = mock_vault_with_config / "90-99_Allegati" / "Heavy_Presentation.mp4"
    large_media.write_bytes(b"A" * 1024)

    # Embed it in a note
    target_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    note_content = target_note.read_text(encoding="utf-8")
    target_note.write_text(note_content + "\n\nGuarda questo video:\n![[Heavy_Presentation.mp4]]\n", encoding="utf-8")
    v.refresh()

    # Offload specific target
    res = v.offload(target=large_media)
    assert len(res.offloaded_files) == 1
    src, dst, size = res.offloaded_files[0]
    assert src.name == "Heavy_Presentation.mp4"
    assert dst.exists()
    assert not large_media.exists()
    assert res.updated_notes_count >= 1

    # Check note content now has callout instead of direct embed
    updated_note = target_note.read_text(encoding="utf-8")
    assert "![[Heavy_Presentation.mp4]]" not in updated_note
    assert "> [!INFO] Allegato archiviato su storage freddo" in updated_note
    assert f"[{src.name}]({dst.as_posix()})" in updated_note or f"[{src.name}](file://{dst.as_posix()})" in updated_note

    # Undo offload
    undo_res = v.undo()
    assert undo_res.success is True
    assert large_media.exists()
    assert not dst.exists()
    reverted_note = target_note.read_text(encoding="utf-8")
    assert "![[Heavy_Presentation.mp4]]" in reverted_note


def test_offload_errors_and_dry_run(mock_vault_with_config: Path) -> None:
    """Test offload errors and dry-run."""
    v = Vault(mock_vault_with_config)

    # Non-existent target
    with pytest.raises(OffloadError, match="Offload target not found"):
        v.offload(target="Nonexistent_File.mp4")

    # Dry-run with existing file
    existing_att = mock_vault_with_config / "90-99_Allegati" / "Allegato_Test.pdf"
    res_dry = v.offload(target=existing_att, dry_run=True)
    assert len(res_dry.offloaded_files) == 1


def test_lifecycle_edge_cases_and_folder_operations(mock_vault_with_config: Path) -> None:
    """Test directory rename, stem normalization during rename, archive destination conflict, and directory offload."""
    v = Vault(mock_vault_with_config)

    # 1. Rename directory
    subfolder = mock_vault_with_config / "10-19_Progetti" / "Sub_Folder"
    subfolder.mkdir()
    res_dir = v.rename(subfolder, "Nuova_Sub_Folder")
    assert res_dir.new_path.is_dir()
    assert res_dir.new_path.name == "Nuova_Sub_Folder"
    v.undo()
    assert subfolder.is_dir()

    # 2. Rename note with un-normalized input (e.g. spaces/lowercase)
    note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    res_norm = v.rename(note, "nuova nota beta")
    assert res_norm.new_path.name == "Nuova_Nota_Beta.md"
    v.undo()

    # 3. Rename note without H1 heading
    note_no_h1 = mock_vault_with_config / "20-29_Aree" / "Senza_H1.md"
    note_no_h1.write_text("---\ntipo: Appunto\n---\nTesto senza H1\n", encoding="utf-8")
    v.refresh()
    res_no_h1 = v.rename(note_no_h1, "Con_H1_Nuovo")
    assert res_no_h1.new_path.exists()
    v.undo()

    # 4. Archive destination already exists error
    note_alpha = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"
    archive_dest = mock_vault_with_config.parent / "Archive" / "10-19_Progetti" / "Progetto_Alpha.md"
    archive_dest.parent.mkdir(parents=True, exist_ok=True)
    archive_dest.write_text("Already in archive", encoding="utf-8")
    with pytest.raises(ArchiveError, match="Archive destination path already exists"):
        v.archive(note_alpha)
    archive_dest.unlink()

    # 5. Offload directory scan with heavy file threshold
    heavy_file = mock_vault_with_config / "90-99_Allegati" / "Heavy_Scan.mp4"
    heavy_file.write_bytes(b"Z" * (60 * 1024 * 1024))  # 60MB > 50MB threshold
    v.refresh()
    res_dir_offload = v.offload(target=mock_vault_with_config / "90-99_Allegati")
    assert len(res_dir_offload.offloaded_files) >= 1
    v.undo()

    # 6. Offload collision in cold storage (destination already exists)
    heavy_file2 = mock_vault_with_config / "90-99_Allegati" / "Colliding.mp4"
    heavy_file2.write_bytes(b"X" * 100)
    cold_dest = mock_vault_with_config.parent / "Archive" / "90-99_Allegati_Pesanti" / "Colliding.mp4"
    cold_dest.parent.mkdir(parents=True, exist_ok=True)
    cold_dest.write_bytes(b"Pre-existing")

    res_coll = v.offload(target=heavy_file2)
    assert len(res_coll.offloaded_files) == 1
    src, dst, _ = res_coll.offloaded_files[0]
    assert dst.name != "Colliding.mp4"  # Got timestamp appended
    assert "Colliding_" in dst.name
    v.undo()


def test_lifecycle_direct_without_transaction(mock_vault_with_config: Path) -> None:
    """Test rename_item and move_item invoked without a transaction context."""
    cfg = load_vault_config(mock_vault_with_config)
    mgr = IndexManager(cfg)
    link_engine = WikilinkEngine(cfg)
    v = Vault(mock_vault_with_config)

    note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    # Direct rename
    res = rename_item(
        v.catalog,
        cfg,
        mgr,
        link_engine,
        note,
        "Nota_Beta_Direct",
        transaction=None,
    )
    assert res.new_path.exists()

    # Direct move
    dest_dir = mock_vault_with_config / "10-19_Progetti"
    res_move = move_item(
        cfg,
        mgr,
        res.new_path,
        dest_dir,
        transaction=None,
    )
    assert res_move.dest_path.exists()
