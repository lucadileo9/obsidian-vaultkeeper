"""Unit tests for folder index (MOC) generation with contextual naming."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.indices import (
    get_index_filename_for_folder,
    write_folder_index,
)
from vaultkeeper.core.traversal import build_vault_catalog


def test_get_index_filename_patterns(mock_vault: Path) -> None:
    """Verify index filename patterns based on configuration."""
    cfg = load_vault_config(root_path=mock_vault)
    target = mock_vault / "10-19_Progetti"

    # Contextual pattern
    cfg.index_naming_pattern = "contextual"
    assert get_index_filename_for_folder(target, cfg) == "00_Indice_Progetti.md"

    # Static pattern
    cfg.index_naming_pattern = "static"
    assert get_index_filename_for_folder(target, cfg) == "00_Indice.md"

    # Readme pattern
    cfg.index_naming_pattern = "readme"
    assert get_index_filename_for_folder(target, cfg) == "README.md"


def test_write_folder_index(mock_vault: Path) -> None:
    """Verify generating and writing an index note with notes and documents."""
    cfg = load_vault_config(root_path=mock_vault)
    catalog = build_vault_catalog(cfg)
    target = mock_vault / "10-19_Progetti"

    idx_path, created = write_folder_index(target, cfg, catalog, dry_run=False)
    assert created is True
    assert idx_path.is_file()
    assert idx_path.name == "00_Indice_Progetti.md"

    content = idx_path.read_text(encoding="utf-8")
    assert "tipo: Indice" in content
    assert "# Indice - 10-19_Progetti" in content
    assert "[[Progetto_Alpha]]" in content

    # Second write with no changes returns False
    _, created_again = write_folder_index(target, cfg, catalog, dry_run=False)
    assert created_again is False


def test_folder_index_with_subfolders_and_summary(mock_vault: Path) -> None:
    """Verify index generation includes subfolders and frontmatter description summary."""
    cfg = load_vault_config(root_path=mock_vault)
    sub = mock_vault / "10-19_Progetti" / "Sub_Progetto"
    sub.mkdir()
    note_sub = sub / "Dettaglio.md"
    note_sub.write_text(
        "---\ntipo: Appunto\ndescrizione: Sintesi del sotto progetto di prova.\n---\n# Dettaglio\n",
        encoding="utf-8",
    )

    catalog = build_vault_catalog(cfg)
    idx_sub, _ = write_folder_index(sub, cfg, catalog)
    assert idx_sub.is_file()
    content_sub = idx_sub.read_text(encoding="utf-8")
    assert "Sintesi del sotto progetto di prova" in content_sub
