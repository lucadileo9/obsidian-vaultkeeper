"""Tests for configuration loading, proteus integration and domain models."""

from pathlib import Path

import pytest

from vaultkeeper.config import (
    load_vault_config,
)
from vaultkeeper.exceptions import ConfigurationError, VaultNotFoundError
from vaultkeeper.models import (
    AuditReport,
    BrokenLink,
    Frontmatter,
    PhaseResult,
)


def test_load_default_config_for_existing_dir(mock_vault: Path) -> None:
    """Verify that default configuration loads properly without vault.toml."""
    config = load_vault_config(root_path=mock_vault)
    assert config.root_path == mock_vault
    assert config.naming_style == "Title_Case"
    assert "AI" in config.acronyms
    assert "Appunto" in config.allowed_types
    assert ".md" in config.allowed_extensions
    assert config.index_naming_pattern == "contextual"


def test_load_config_with_vault_toml(mock_vault_with_config: Path) -> None:
    """Verify that configuration loads correctly from vault.toml via proteus."""
    config = load_vault_config(root_path=mock_vault_with_config)
    assert config.root_path == mock_vault_with_config
    assert config.heavy_file_threshold_mb == 50
    assert config.strict_taxonomy is True
    assert config.type_field == "tipo"


def test_load_config_with_custom_overrides(empty_temp_dir: Path) -> None:
    """Verify custom TOML configurations are properly loaded."""
    vault = empty_temp_dir / "CustomVault"
    vault.mkdir()
    toml_path = vault / "vault.toml"
    custom_toml = f"""[vault]
root_path = "{vault}"
max_path_length = 180

[naming]
style = "kebab-case"
acronyms = ["NASA", "ESA"]

[indices]
naming_pattern = "readme"
"""
    toml_path.write_text(custom_toml, encoding="utf-8")
    config = load_vault_config(root_path=vault)
    assert config.max_path_length == 180
    assert config.naming_style == "kebab-case"
    assert config.acronyms == {"NASA", "ESA"}
    assert config.index_naming_pattern == "readme"


def test_nonexistent_vault_raises_error(empty_temp_dir: Path) -> None:
    """Verify VaultNotFoundError when target root does not exist."""
    fake_path = empty_temp_dir / "DoesNotExist"
    with pytest.raises(VaultNotFoundError):
        load_vault_config(root_path=fake_path)


def test_nonexistent_explicit_config_raises_error(mock_vault: Path) -> None:
    """Verify ConfigurationError when an explicit config file does not exist."""
    fake_cfg = mock_vault / "nonexistent.toml"
    with pytest.raises(ConfigurationError):
        load_vault_config(root_path=mock_vault, config_file=fake_cfg)


def test_broken_link_model() -> None:
    """Verify BrokenLink methods."""
    link_md = BrokenLink(
        source_file=Path("/v/note.md"),
        line_number=10,
        raw_target="[[Other_Note]]",
        clean_target="Other_Note",
    )
    assert link_md.is_media_embed() is False

    link_img = BrokenLink(
        source_file=Path("/v/note.md"),
        line_number=12,
        raw_target="![[diagram.png]]",
        clean_target="diagram.png",
    )
    assert link_img.is_media_embed() is True


def test_frontmatter_model() -> None:
    """Verify Frontmatter methods."""
    fm = Frontmatter(
        raw_content="tipo: Appunto\ntags: [tag1, tag2]",
        metadata={"tipo": "Appunto", "tags": ["tag1", "tag2"]},
        tipo="Appunto",
        tags=["tag1", "tag2"],
    )
    assert fm.has_tag("tag1") is True
    assert fm.has_tag("tag3") is False
    assert fm.is_valid_type(["Appunto", "Progetto"]) is True
    assert fm.is_valid_type(["Risorsa"]) is False


def test_audit_report_model() -> None:
    """Verify AuditReport methods."""
    phase1 = PhaseResult(
        phase_id=1,
        title="Test Phase",
        issues=["Issue 1"],
        warnings=[],
        metrics={"count": 1},
    )
    report = AuditReport(
        vault_root=Path("/v"),
        timestamp="2026-11-07T12:00:00Z",
        phases=[phase1],
        total_issues=1,
        health_score=85.0,
    )
    assert report.is_clean() is False
    d = report.to_dict()
    assert d["total_issues"] == 1
    assert d["health_score"] == 85.0
    assert len(d["phases"]) == 1
