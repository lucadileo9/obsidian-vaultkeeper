"""Comprehensive test suite for batch JSON operations across Facade, Core, and CLI."""

import json
from pathlib import Path

import pytest

from vaultkeeper.cli.main import main
from vaultkeeper.exceptions import FrontmatterError, LifecycleError, NamingError, TaxonomyError, VaultKeeperError
from vaultkeeper.vault import Vault


def test_batch_move_nominal_and_undo(mock_vault_with_config: Path) -> None:
    """Verify batch move moves multiple files, updates indices, and undo reverts all."""
    v = Vault(mock_vault_with_config)

    # Create two notes in 20-29_Aree
    n1 = mock_vault_with_config / "20-29_Aree" / "Doc_Uno.md"
    n2 = mock_vault_with_config / "20-29_Aree" / "Doc_Due.md"
    n1.write_text("# Doc Uno\n", encoding="utf-8")
    n2.write_text("# Doc Due\n", encoding="utf-8")

    dest_folder = "10-19_Progetti"
    mapping = {
        str(n1): dest_folder,
        str(n2): dest_folder,
    }

    results = v.batch_move(mapping)
    assert len(results) == 2
    assert (mock_vault_with_config / "10-19_Progetti" / "Doc_Uno.md").exists()
    assert (mock_vault_with_config / "10-19_Progetti" / "Doc_Due.md").exists()
    assert not n1.exists()
    assert not n2.exists()

    # Verify single transaction
    assert results[0].tx_id is not None
    assert results[0].tx_id == results[1].tx_id

    # Undo batch move
    undo_res = v.undo(results[0].tx_id)
    assert undo_res.success
    assert n1.exists()
    assert n2.exists()
    assert not (mock_vault_with_config / "10-19_Progetti" / "Doc_Uno.md").exists()
    assert not (mock_vault_with_config / "10-19_Progetti" / "Doc_Due.md").exists()


def test_batch_move_preflight_failures(mock_vault_with_config: Path) -> None:
    """Verify All-or-Nothing preflight rejects entire batch on any conflict or error."""
    v = Vault(mock_vault_with_config)

    valid_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    missing_note = mock_vault_with_config / "20-29_Aree" / "Inesistente.md"

    # 1. Missing source
    with pytest.raises(LifecycleError, match="Source path does not exist"):
        v.batch_move({
            str(valid_note): "10-19_Progetti",
            str(missing_note): "10-19_Progetti",
        })
    assert valid_note.exists()

    # 2. Destination collision with existing note
    existing_dest = mock_vault_with_config / "10-19_Progetti" / "Nota_Beta.md"
    existing_dest.write_text("# Collision\n", encoding="utf-8")

    with pytest.raises(LifecycleError, match="Destination already exists"):
        v.batch_move({
            str(valid_note): "10-19_Progetti",
        })

    # 3. Duplicate destination in same batch
    n1 = mock_vault_with_config / "00-09_Meta" / "Doc_A.md"
    n2 = mock_vault_with_config / "00-09_Meta" / "Doc_B.md"
    n1.write_text("# A\n", encoding="utf-8")
    n2.write_text("# B\n", encoding="utf-8")

    # Map two different files into destination with same name (if source had same basename in diff dirs)
    sub = mock_vault_with_config / "20-29_Aree" / "Doc_A.md"
    sub.write_text("# Sub A\n", encoding="utf-8")

    with pytest.raises(LifecycleError, match="Multiple sources map to the same destination"):
        v.batch_move({
            str(n1): "10-19_Progetti",
            str(sub): "10-19_Progetti",
        })
    assert n1.exists()
    assert sub.exists()


def test_batch_move_dry_run(mock_vault_with_config: Path) -> None:
    """Verify batch move dry-run returns planned results without modifying disk."""
    v = Vault(mock_vault_with_config)
    target = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    res = v.batch_move({str(target): "10-19_Progetti"}, dry_run=True)
    assert len(res) == 1
    assert target.exists()
    assert not (mock_vault_with_config / "10-19_Progetti" / "Nota_Beta.md").exists()


def test_batch_rename_nominal_and_undo(mock_vault_with_config: Path) -> None:
    """Verify batch rename updates notes, refactors cross-referencing wikilinks, and reverts cleanly."""
    v = Vault(mock_vault_with_config)
    note1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"
    note2 = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    mapping = {
        str(note1): "Progetto_Alpha_Prime",
        str(note2): "Nota_Beta_Prime",
    }

    results = v.batch_rename(mapping)
    assert len(results) == 2

    new1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha_Prime.md"
    new2 = mock_vault_with_config / "20-29_Aree" / "Nota_Beta_Prime.md"
    assert new1.exists()
    assert new2.exists()
    assert not note1.exists()
    assert not note2.exists()

    # Check cross-links refactored
    assert "[[Nota_Beta_Prime]]" in new1.read_text(encoding="utf-8")
    assert "[[Progetto_Alpha_Prime]]" in new2.read_text(encoding="utf-8")

    # Undo
    undo_res = v.undo(results[0].tx_id)
    assert undo_res.success
    assert note1.exists()
    assert note2.exists()
    assert not new1.exists()
    assert not new2.exists()
    assert "[[Nota_Beta]]" in note1.read_text(encoding="utf-8")
    assert "[[Progetto_Alpha]]" in note2.read_text(encoding="utf-8")


def test_batch_rename_preflight_failures(mock_vault_with_config: Path) -> None:
    """Verify batch rename preflight rejects if any collision or missing source."""
    v = Vault(mock_vault_with_config)
    note1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    # 1. Collision with existing note
    with pytest.raises(NamingError, match="Stem collision for target stem"):
        v.batch_rename({str(note1): "Nota_Beta"})
    assert note1.exists()

    # 2. Missing source
    with pytest.raises(NamingError, match="Source file does not exist"):
        v.batch_rename({"Inesistente.md": "Nuova_Nota"})

    # 3. Intra-batch collision (two notes renamed to same target stem)
    note2 = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    with pytest.raises(NamingError, match="Duplicate target stem"):
        v.batch_rename({
            str(note1): "Nuova_Destinazione",
            str(note2): "Nuova_Destinazione",
        })


def test_batch_rename_dry_run(mock_vault_with_config: Path) -> None:
    """Verify batch rename dry-run does not alter files or links."""
    v = Vault(mock_vault_with_config)
    note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    results = v.batch_rename({str(note): "Nota_Beta_Simulata"}, dry_run=True)
    assert len(results) == 1
    assert note.exists()
    assert not (mock_vault_with_config / "20-29_Aree" / "Nota_Beta_Simulata.md").exists()


def test_batch_set_type_nominal_and_undo(mock_vault_with_config: Path) -> None:
    """Verify batch set-type sets frontmatter type in a single transaction and undo reverts."""
    v = Vault(mock_vault_with_config)
    note1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"
    note2 = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    mapping = {
        str(note1): "Risorsa",
        str(note2): "Progetto",
    }

    results = v.batch_set_frontmatter_type(mapping)
    assert len(results) == 2
    assert "tipo: Risorsa" in note1.read_text(encoding="utf-8")
    assert "tipo: Progetto" in note2.read_text(encoding="utf-8")

    # Undo
    undo_res = v.undo()
    assert undo_res.success
    assert "tipo: Progetto" in note1.read_text(encoding="utf-8")
    assert "tipo: Appunto" in note2.read_text(encoding="utf-8")


def test_batch_set_type_preflight_failures(mock_vault_with_config: Path) -> None:
    """Verify batch set-type preflight blocks invalid types without touching files."""
    v = Vault(mock_vault_with_config)
    note1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    # Invalid type
    with pytest.raises(FrontmatterError, match="Invalid note type 'TipoInvalido'"):
        v.batch_set_frontmatter_type({str(note1): "TipoInvalido"})
    assert "tipo: Progetto" in note1.read_text(encoding="utf-8")

    # Missing file
    with pytest.raises(FrontmatterError, match="Note not found"):
        v.batch_set_frontmatter_type({"Nota_Inesistente.md": "Risorsa"})


def test_batch_set_type_dry_run(mock_vault_with_config: Path) -> None:
    """Verify batch set-type dry-run does not write to disk."""
    v = Vault(mock_vault_with_config)
    note1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    results = v.batch_set_frontmatter_type({str(note1): "Risorsa"}, dry_run=True)
    assert len(results) == 1
    assert "tipo: Progetto" in note1.read_text(encoding="utf-8")


def test_batch_add_tags_nominal_and_overwrite_and_undo(mock_vault_with_config: Path) -> None:
    """Verify batch add-tags appends or overwrites tags, and undo reverts cleanly."""
    v = Vault(mock_vault_with_config)
    note1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"
    note2 = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    # Add tags
    results = v.batch_add_frontmatter_tags({
        str(note1): ["area/lavoro"],
        str(note2): ["stato/attivo"],
    })
    assert len(results) == 2
    assert "area/lavoro" in note1.read_text(encoding="utf-8")
    assert "stato/attivo" in note2.read_text(encoding="utf-8")

    # Undo
    undo_res = v.undo()
    assert undo_res.success
    assert "area/lavoro" not in note1.read_text(encoding="utf-8")

    # Overwrite tags
    results_ov = v.batch_add_frontmatter_tags(
        {str(note1): ["area/studio"]},
        overwrite=True,
    )
    assert len(results_ov) == 1
    content1 = note1.read_text(encoding="utf-8")
    assert "area/studio" in content1
    assert "stato/attivo" not in content1


def test_batch_add_tags_preflight_strict_taxonomy(mock_vault_with_config: Path) -> None:
    """Verify batch add-tags preflight fails if tag not in taxonomy when strict."""
    # Enable strict taxonomy in config
    cfg_file = mock_vault_with_config / "vault.toml"
    cfg_file.write_text(
        cfg_file.read_text(encoding="utf-8").replace("strict_taxonomy = false", "strict_taxonomy = true"),
        encoding="utf-8",
    )

    v = Vault(mock_vault_with_config)
    note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    with pytest.raises(TaxonomyError, match="is not registered in taxonomy"):
        v.batch_add_frontmatter_tags({str(note): ["tag_illegale"]})


def test_batch_json_source_loading_and_errors(mock_vault_with_config: Path) -> None:
    """Verify loading from JSON file on disk and handling malformed files."""
    v = Vault(mock_vault_with_config)

    # 1. Non-existent JSON file
    with pytest.raises(VaultKeeperError, match="Batch mapping file not found"):
        v.batch_move("inesistente.json")

    # 2. Malformed JSON file
    bad_json = mock_vault_with_config / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(VaultKeeperError, match="Invalid JSON"):
        v.batch_move(bad_json)

    # 3. Valid JSON but not a dictionary (e.g. array)
    list_json = mock_vault_with_config / "list.json"
    list_json.write_text('["item1", "item2"]', encoding="utf-8")
    with pytest.raises(VaultKeeperError, match="must contain a JSON dictionary"):
        v.batch_move(list_json)


def test_batch_cli_commands(mock_vault_with_config: Path) -> None:
    """Verify CLI commands for all batch operations."""
    note1 = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"
    note2 = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    # 1. CLI vk frontmatter set-type --batch
    batch_type = mock_vault_with_config / "batch_type.json"
    batch_type.write_text(json.dumps({str(note1): "Risorsa"}), encoding="utf-8")
    code = main(["--root", str(mock_vault_with_config), "frontmatter", "set-type", "--batch", str(batch_type)])
    assert code == 0
    assert "tipo: Risorsa" in note1.read_text(encoding="utf-8")

    # 2. CLI vk frontmatter add-tags --batch
    batch_tags = mock_vault_with_config / "batch_tags.json"
    batch_tags.write_text(json.dumps({str(note1): ["area/lavoro"]}), encoding="utf-8")
    code = main(["--root", str(mock_vault_with_config), "frontmatter", "add-tags", "--batch", str(batch_tags)])
    assert code == 0
    assert "area/lavoro" in note1.read_text(encoding="utf-8")

    # 3. CLI vk rename --batch
    batch_rename = mock_vault_with_config / "batch_rename.json"
    batch_rename.write_text(json.dumps({str(note2): "Nota_Beta_Cli"}), encoding="utf-8")
    code = main(["--root", str(mock_vault_with_config), "rename", "--batch", str(batch_rename)])
    assert code == 0
    new_note2 = mock_vault_with_config / "20-29_Aree" / "Nota_Beta_Cli.md"
    assert new_note2.exists()

    # 4. CLI vk move --batch
    batch_move = mock_vault_with_config / "batch_move.json"
    batch_move.write_text(json.dumps({str(new_note2): "10-19_Progetti"}), encoding="utf-8")
    code = main(["--root", str(mock_vault_with_config), "move", "--batch", str(batch_move)])
    assert code == 0
    moved_note = mock_vault_with_config / "10-19_Progetti" / "Nota_Beta_Cli.md"
    assert moved_note.exists()
