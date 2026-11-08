"""Integration tests for CLI command 'vk create'."""

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from vaultkeeper.cli.main import main


@pytest.fixture
def cli_vault() -> Iterator[Path]:
    """Create a temporary sandbox vault for CLI create testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # 01-09 Meta / System
        meta_dir = root / "01-09_Risorse_Di_Sistema" / "01_Templates"
        meta_dir.mkdir(parents=True, exist_ok=True)

        taxonomy_content = """# Tassonomia dei Tag
- #tipo/appunto
- #tipo/progetto
- #carriera/networking
- #tech/python
"""
        (meta_dir / "00_Tassonomia_Tag.md").write_text(taxonomy_content, encoding="utf-8")

        # 10-19 Progetti
        (root / "10-19_Progetti").mkdir(parents=True, exist_ok=True)
        # 30-39 Carriera / 32_CRM
        (root / "30-39_Carriera" / "32_CRM").mkdir(parents=True, exist_ok=True)
        # 20-29 Istruzione
        (root / "20-29_Istruzione").mkdir(parents=True, exist_ok=True)

        # Template
        tmpl_text = """---
tipo: Sistema
tags:
  - sistema
---
# {{title}}

## Sezione
"""
        (meta_dir / "Template_Contatto.md").write_text(tmpl_text, encoding="utf-8")

        cfg_text = f"""[vault]
root_path = "{root.as_posix()}"
allowed_extensions = [".md"]
ignored_folders = [".obsidian", ".trash", ".git"]
templates_folder = "01-09_Risorse_Di_Sistema/01_Templates"

[frontmatter]
type_field = "tipo"
allowed_types = ["Appunto", "Contatto", "Progetto", "Risorsa", "Indice", "Sistema"]

[tags]
taxonomy_file = "01-09_Risorse_Di_Sistema/01_Templates/00_Tassonomia_Tag.md"
strict_taxonomy = true
"""
        (root / "vault.toml").write_text(cfg_text, encoding="utf-8")

        yield root


def test_cli_create_basic(cli_vault: Path, capsys: pytest.CaptureFixture) -> None:
    """Test creating a note via CLI with auto-routing."""
    ret = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Nuovo Progetto Backend",
            "--type",
            "Progetto",
            "--tags",
            "tech/python",
        ]
    )
    assert ret == 0

    out = capsys.readouterr().out
    assert "Nuova Nota: Nuovo Progetto Backend" in out
    assert "[[Nuovo_Progetto_Backend]]" in out

    dest_file = cli_vault / "10-19_Progetti" / "Nuovo_Progetto_Backend.md"
    assert dest_file.is_file()
    content = dest_file.read_text(encoding="utf-8")
    assert "tipo: Progetto" in content
    assert "tech/python" in content


def test_cli_create_with_template_and_undo(cli_vault: Path, capsys: pytest.CaptureFixture) -> None:
    """Test creating a note with template and reverting via vk undo."""
    ret = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Marco Rossi",
            "--type",
            "Contatto",
            "--template",
            "Template_Contatto",
            "--tags",
            "carriera/networking",
        ]
    )
    assert ret == 0

    crm_file = cli_vault / "30-39_Carriera" / "32_CRM" / "Marco_Rossi.md"
    assert crm_file.is_file()
    assert "tipo: Contatto" in crm_file.read_text(encoding="utf-8")

    # Undo via CLI
    ret_undo = main(["--root", str(cli_vault), "undo"])
    assert ret_undo == 0
    assert not crm_file.exists()


def test_cli_create_dry_run(cli_vault: Path, capsys: pytest.CaptureFixture) -> None:
    """Test vk create with --dry-run does not write file."""
    ret = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Nota di Test Dry Run",
            "--type",
            "Appunto",
            "--dry-run",
        ]
    )
    assert ret == 0
    out = capsys.readouterr().out
    assert "[DRY-RUN]" in out

    target_file = cli_vault / "20-29_Istruzione" / "Nota_Di_Test_Dry_Run.md"
    assert not target_file.exists()


def test_cli_create_formats(cli_vault: Path, capsys: pytest.CaptureFixture) -> None:
    """Test output formatting in JSON, YAML, and CSV."""
    # JSON
    ret_json = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Nota Formato JSON",
            "--type",
            "Appunto",
            "--format",
            "json",
        ]
    )
    assert ret_json == 0
    out_json = capsys.readouterr().out
    data_json = json.loads(out_json)
    assert data_json["stem"] == "Nota_Formato_Json"
    assert data_json["tipo"] == "Appunto"

    # YAML
    ret_yaml = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Nota Formato YAML",
            "--type",
            "Appunto",
            "--format",
            "yaml",
        ]
    )
    assert ret_yaml == 0
    out_yaml = capsys.readouterr().out
    data_yaml = yaml.safe_load(out_yaml)
    assert data_yaml["stem"] == "Nota_Formato_Yaml"

    # CSV
    ret_csv = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Nota Formato CSV",
            "--type",
            "Appunto",
            "--format",
            "csv",
        ]
    )
    assert ret_csv == 0
    out_csv = capsys.readouterr().out
    assert "property,value" in out_csv or "stem" in out_csv


def test_cli_create_errors(cli_vault: Path, capsys: pytest.CaptureFixture) -> None:
    """Test CLI error handling on invalid input or validation failures."""
    # Invalid tipo
    ret_err_tipo = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Nota Errata",
            "--type",
            "NonEsistente",
        ]
    )
    assert ret_err_tipo == 1

    # Invalid taxonomy tag
    ret_err_tag = main(
        [
            "--root",
            str(cli_vault),
            "create",
            "Nota Tag Errato",
            "--type",
            "Appunto",
            "--tags",
            "tag/inventato",
        ]
    )
    assert ret_err_tag == 1
