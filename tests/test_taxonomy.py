"""Unit and integration tests for TaxonomyEngine and tag lifecycle management."""

from pathlib import Path

import pytest

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.taxonomy import TaxonomyEngine
from vaultkeeper.exceptions import TaxonomyError
from vaultkeeper.vault import Vault


def test_taxonomy_loading_and_search(mock_vault_with_config: Path) -> None:
    """Verify loading registered taxonomy tags, validation, and search filtering."""
    cfg = load_vault_config(mock_vault_with_config)
    engine = TaxonomyEngine(cfg)

    tags = engine.load_taxonomy()
    assert "area/lavoro" in tags
    assert "tipo/progetto" in tags
    assert "stato/attivo" in tags

    assert engine.is_valid_tag("area/lavoro") is True
    assert engine.is_valid_tag("#area/lavoro") is True
    assert engine.is_valid_tag("inesistente/tag") is False

    # Search
    search_all = engine.search_tags()
    assert len(search_all) == len(tags)

    search_tipo = engine.search_tags(query="tipo")
    assert all("tipo" in t for t in search_tipo)
    assert len(search_tipo) >= 3


def test_taxonomy_add_tag_and_undo(mock_vault_with_config: Path) -> None:
    """Verify adding tag in alphabetical order, dry-run, and undo rollback."""
    v = Vault(mock_vault_with_config)

    # Initial state
    assert "area/ricerca" not in v.tags_show()

    # Dry-run
    res_dry = v.tags_add("area/ricerca", dry_run=True)
    assert res_dry.tag == "area/ricerca"
    assert "area/ricerca" not in v.tags_show()

    # Real addition
    res = v.tags_add("area/ricerca")
    assert res.tag == "area/ricerca"
    assert "area/ricerca" in v.tags_show()

    # Adding again should be idempotent (no duplicate)
    res_dup = v.tags_add("area/ricerca")
    assert res_dup.tag == "area/ricerca"

    # Verify content format in 00_Tassonomia_Tag.md
    tax_path = res.taxonomy_file
    content = tax_path.read_text(encoding="utf-8")
    assert "- #area/ricerca" in content

    # Undo
    undo_res = v.undo()
    assert undo_res.success is True
    assert "area/ricerca" not in v.tags_show()


def test_taxonomy_add_invalid_tag(mock_vault_with_config: Path) -> None:
    """Verify that malformed tags raise TaxonomyError."""
    v = Vault(mock_vault_with_config)

    with pytest.raises(TaxonomyError, match="Invalid tag format"):
        v.tags_add("tag con spazi")

    with pytest.raises(TaxonomyError, match="Invalid tag format"):
        v.tags_add("")


def test_taxonomy_remove_tag_and_safety_checks(mock_vault_with_config: Path) -> None:
    """Verify safe removal of unused tag, safety blockage for in-use tags, and force removal."""
    v = Vault(mock_vault_with_config)

    # Add temporary tag that is not used in any notes
    v.tags_add("area/temporanea")
    assert "area/temporanea" in v.tags_show()

    # Dry-run remove
    res_dry = v.tags_remove("area/temporanea", dry_run=True)
    assert res_dry.tag == "area/temporanea"
    assert "area/temporanea" in v.tags_show()

    # Real remove of unused tag
    res = v.tags_remove("area/temporanea")
    assert res.tag == "area/temporanea"
    assert "area/temporanea" not in v.tags_show()

    # Undo remove
    v.undo()
    assert "area/temporanea" in v.tags_show()
    v.tags_remove("area/temporanea")

    # Attempt to remove in-use tag (tipo/progetto is used in Progetto_Alpha.md)
    with pytest.raises(TaxonomyError, match="currently referenced in"):
        v.tags_remove("tipo/progetto", force=False)

    # Force removal succeeds
    res_forced = v.tags_remove("tipo/progetto", force=True)
    assert res_forced.tag == "tipo/progetto"
    assert "tipo/progetto" not in v.tags_show()

    # Undo force removal
    v.undo()
    assert "tipo/progetto" in v.tags_show()

    # Remove non-existent tag
    with pytest.raises(TaxonomyError, match="does not exist in taxonomy"):
        v.tags_remove("tag/inesistente")


def test_taxonomy_structured_sections(mock_vault_with_config: Path) -> None:
    """Verify alphabetical insertion within dedicated section headings."""
    cfg = load_vault_config(mock_vault_with_config)
    engine = TaxonomyEngine(cfg)

    # Set up structured taxonomy note
    tax_path = engine.taxonomy_path
    structured_content = """# Tassonomia Tag del Vault

## Area
- #area/lavoro
- #area/studio

## Tipo
- #tipo/appunto
- #tipo/risorsa

## Altro
"""
    tax_path.write_text(structured_content, encoding="utf-8")

    # 1. Insert into Area before lavoro (alphabetical first)
    engine.add_tag("area/accademia")
    # 2. Insert into Area at end of section
    engine.add_tag("area/tecnologia")
    # 3. Insert into Tipo between appunto and risorsa
    engine.add_tag("tipo/progetto", section="Tipo")
    # 4. Insert into empty section Altro
    engine.add_tag("altro/generico", section="Altro")

    res_content = tax_path.read_text(encoding="utf-8")
    assert "- #area/accademia" in res_content
    assert "- #area/tecnologia" in res_content
    assert "- #tipo/progetto" in res_content
    assert "- #altro/generico" in res_content


def test_taxonomy_create_file_when_missing(mock_vault_with_config: Path) -> None:
    """Verify creating 00_Tassonomia_Tag.md when no taxonomy file exists."""
    cfg = load_vault_config(mock_vault_with_config)
    engine = TaxonomyEngine(cfg)
    tax_path = engine.taxonomy_path

    if tax_path.exists():
        tax_path.unlink()

    assert engine.load_taxonomy() == set()

    res = engine.add_tag("area/nuova")
    assert res.tag == "area/nuova"
    assert res.taxonomy_file.is_file()
    assert "- #area/nuova" in res.taxonomy_file.read_text(encoding="utf-8")
