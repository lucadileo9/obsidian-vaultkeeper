"""Unit tests for naming normalization and global link synchronization."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.naming import (
    clean_disallowed_characters,
    normalize_name,
    normalize_stem,
    rename_vault_item,
    update_wikilinks_in_content,
)
from vaultkeeper.core.traversal import build_vault_catalog


def test_clean_disallowed_characters() -> None:
    """Verify that disallowed characters are stripped cleanly."""
    raw = "Nota?con:caratteri*speciali!&<>"
    regex = r"['\":?*!&|<>,\\()]"
    cleaned = clean_disallowed_characters(raw, regex)
    assert cleaned == "Notaconcaratterispeciali"


def test_normalize_stem_title_case(mock_vault: Path) -> None:
    """Verify Title_Case normalization preserving acronyms and prefixes."""
    cfg = load_vault_config(root_path=mock_vault)
    # Acronym preservation
    assert normalize_stem("progetto ai per jemore", cfg) == "Progetto_AI_Per_JEMORE"
    # Prefix preservation
    assert normalize_stem("00_introduzione al pkm", cfg) == "00_Introduzione_Al_PKM"
    assert normalize_stem("10-19_progetti speciali", cfg) == "10-19_Progetti_Speciali"
    # Disallowed chars and spacing
    assert normalize_stem("note: with (invalid) chars!", cfg) == "Note_With_Invalid_Chars"


def test_normalize_stem_kebab_case(mock_vault: Path) -> None:
    """Verify kebab-case normalization."""
    cfg = load_vault_config(root_path=mock_vault)
    cfg.naming_style = "kebab-case"
    assert normalize_stem("My Great Project", cfg) == "my-great-project"


def test_normalize_stem_snake_case(mock_vault: Path) -> None:
    """Verify snake_case normalization."""
    cfg = load_vault_config(root_path=mock_vault)
    cfg.naming_style = "snake_case"
    assert normalize_stem("My Great Project", cfg) == "my_great_project"


def test_normalize_name(mock_vault: Path) -> None:
    """Verify full filename normalization preserves extensions."""
    cfg = load_vault_config(root_path=mock_vault)
    assert normalize_name("vecchia nota test.md", cfg) == "Vecchia_Nota_Test.md"
    assert normalize_name("diagramma architettura.png", cfg) == "Diagramma_Architettura.png"


def test_update_wikilinks_in_content() -> None:
    """Verify wikilink replacement in markdown content."""
    text = "Vedi [[Old_Target]], [[Old_Target|Alias]] e [[Old_Target#Heading]]. Anche ![[Old_Target]]."
    updated, count = update_wikilinks_in_content(text, "Old_Target", "New_Target")
    assert count == 4
    assert updated == "Vedi [[New_Target]], [[New_Target|Alias]] e [[New_Target#Heading]]. Anche ![[New_Target]]."


def test_rename_vault_item(mock_vault: Path) -> None:
    """Verify atomic rename of note and updating referencing notes."""
    cfg = load_vault_config(root_path=mock_vault)
    catalog = build_vault_catalog(cfg)

    # Note1 (Progetto_Alpha.md) references Nota_Beta.md
    target_note = mock_vault / "20-29_Aree" / "Nota_Beta.md"
    new_path, updated_links = rename_vault_item(
        catalog,
        cfg,
        target_note,
        "Nota_Beta_Aggiornata.md",
        dry_run=False,
    )

    assert new_path.is_file()
    assert not target_note.exists()
    assert updated_links >= 1

    # Verify Progetto_Alpha was updated
    p1 = (mock_vault / "10-19_Progetti" / "Progetto_Alpha.md").read_text(encoding="utf-8")
    assert "[[Nota_Beta_Aggiornata]]" in p1
