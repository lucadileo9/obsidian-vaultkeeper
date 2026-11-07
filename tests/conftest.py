"""Pytest fixtures for VaultKeeper test suite."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from vaultkeeper.config import generate_default_config_content


@pytest.fixture
def empty_temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory and automatically cleanup after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir).resolve()


@pytest.fixture
def mock_vault(empty_temp_dir: Path) -> Path:
    """Create a realistic mock Obsidian vault structure for testing."""
    vault = empty_temp_dir / "TestVault"
    vault.mkdir()

    # Create standard folder structure
    (vault / "00-09_Meta").mkdir()
    (vault / "10-19_Progetti").mkdir()
    (vault / "20-29_Aree").mkdir()
    (vault / "90-99_Allegati").mkdir()
    (vault / ".obsidian").mkdir()
    (vault / ".trash").mkdir()

    # Create taxonomy file
    taxonomy_file = vault / "00-09_Meta" / "00_Tassonomia_Tag.md"
    taxonomy_content = """# Tassonomia Tag del Vault

- #area/lavoro
- #area/studio
- #tipo/appunto
- #tipo/progetto
- #tipo/risorsa
- #stato/attivo
- #stato/completato
"""
    taxonomy_file.write_text(taxonomy_content, encoding="utf-8")

    # Create sample note 1
    note1 = vault / "10-19_Progetti" / "Progetto_Alpha.md"
    note1_content = """---
tipo: Progetto
tags:
  - tipo/progetto
  - stato/attivo
---

# Progetto Alpha

Questo e' un progetto di test che collega [[Nota_Beta]] e [[Allegato_Test.pdf]].
"""
    note1.write_text(note1_content, encoding="utf-8")

    # Create sample note 2
    note2 = vault / "20-29_Aree" / "Nota_Beta.md"
    note2_content = """---
tipo: Appunto
tags:
  - tipo/appunto
  - area/studio
---

# Nota Beta

Nota collegata a [[Progetto_Alpha]] con un link rotto a [[Nota_Inesistente]].
"""
    note2.write_text(note2_content, encoding="utf-8")

    # Create attachment
    attachment = vault / "90-99_Allegati" / "Allegato_Test.pdf"
    attachment.write_bytes(b"%PDF-1.4 test dummy content")

    # Create orphan attachment
    orphan = vault / "90-99_Allegati" / "Orphan_Image.png"
    orphan.write_bytes(b"\x89PNG\r\n\x1a\n test dummy png")

    return vault


@pytest.fixture
def mock_vault_with_config(mock_vault: Path) -> Path:
    """Provide a mock vault with an initialized vault.toml file."""
    config_file = mock_vault / "vault.toml"
    config_content = generate_default_config_content(mock_vault)
    config_file.write_text(config_content, encoding="utf-8")
    return mock_vault
