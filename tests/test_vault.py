"""Unit tests for the Vault facade API."""

from pathlib import Path

from vaultkeeper import Vault


def test_vault_facade_initialization(mock_vault: Path) -> None:
    """Verify Vault instance creation and basic properties."""
    v = Vault(mock_vault)
    assert v.root == mock_vault
    assert v.catalog.total_files > 0
    assert len(v.catalog.notes_by_stem) >= 2


def test_vault_facade_audit(mock_vault: Path) -> None:
    """Verify facade audit method execution."""
    v = Vault(mock_vault)
    report = v.audit()
    assert report.vault_root == mock_vault
    assert len(report.phases) == 5


def test_vault_facade_check_links(mock_vault: Path) -> None:
    """Verify facade check_links method execution."""
    v = Vault(mock_vault)
    broken = v.check_links()
    assert len(broken) >= 1
    assert any(b.clean_target == "Nota_Inesistente" for b in broken)


def test_vault_facade_frontmatter_operations(mock_vault: Path) -> None:
    """Verify frontmatter manipulation via facade."""
    v = Vault(mock_vault)
    note_path = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"

    # Update type
    changed = v.set_frontmatter_type(note_path, "Risorsa")
    assert changed is True
    note = v.get_note(note_path)
    assert note.frontmatter is not None
    assert note.frontmatter.tipo == "Risorsa"

    # Add tags
    changed_tags = v.add_frontmatter_tags(note_path, ["nuovo/tag", "secondo/tag"])
    assert changed_tags is True
    note_updated = v.get_note(note_path)
    assert note_updated.frontmatter is not None
    assert "nuovo/tag" in note_updated.frontmatter.tags


def test_vault_facade_generate_indices(mock_vault: Path) -> None:
    """Verify index generation via facade."""
    v = Vault(mock_vault)
    target_dir = mock_vault / "10-19_Progetti"
    results = v.generate_indices(target=target_dir, recursive=False)
    assert len(results) == 1
    idx_path, changed = results[0]
    assert idx_path.is_file()
    assert changed is True


def test_vault_facade_history_and_undo(mock_vault: Path) -> None:
    """Verify facade history, undo, and get_document methods."""
    v = Vault(mock_vault)
    note_path = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    orig_text = note_path.read_text(encoding="utf-8")

    # Mutate frontmatter
    v.set_frontmatter_type(note_path, "Risorsa")
    assert "tipo: Risorsa" in note_path.read_text(encoding="utf-8")

    # Check history
    hist = v.history()
    assert len(hist) >= 1
    assert hist[0].command == "frontmatter"

    # Revert via facade undo
    res = v.undo()
    assert res.success
    assert note_path.read_text(encoding="utf-8") == orig_text

    # Get document object
    doc = v.get_document(note_path)
    assert doc.tipo == "Progetto"
    assert "tipo/progetto" in doc.tags
