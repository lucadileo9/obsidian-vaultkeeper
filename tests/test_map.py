"""Unit and integration tests for VaultMapEngine and Johnny.Decimal map generation."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.map import VaultMapEngine
from vaultkeeper.vault import Vault


def test_vault_map_report_generation(mock_vault_with_config: Path) -> None:
    """Verify VaultMapEngine scanning areas, counting notes, attachments, and checking indices."""
    cfg = load_vault_config(mock_vault_with_config)
    engine = VaultMapEngine(cfg)

    report = engine.generate_report()
    assert report.total_notes >= 2
    assert report.total_attachments >= 2
    assert report.total_bytes > 0
    assert len(report.areas) >= 3

    area_names = [a.area_name for a in report.areas]
    assert "10-19_Progetti" in area_names
    assert "20-29_Aree" in area_names
    assert "90-99_Allegati" in area_names

    # Check to_dict serialization
    d = report.to_dict()
    assert d["total_notes"] == report.total_notes
    assert len(d["areas"]) == len(report.areas)


def test_vault_map_render_and_write_file(mock_vault_with_config: Path) -> None:
    """Verify markdown map rendering and file persistence."""
    v = Vault(mock_vault_with_config)

    # Render without saving file
    report, written_none = v.vault_map()
    assert written_none is None
    assert report.total_notes >= 2

    # Write file to custom path
    out_map = mock_vault_with_config / "00_Vault_Map.md"
    report2, written_path = v.vault_map(output_file=out_map)
    assert written_path == out_map
    assert out_map.is_file()

    content = out_map.read_text(encoding="utf-8")
    assert "# Mappa Strutturale del Vault" in content
    assert "| `10-19_Progetti/` |" in content
    assert "tipo/indice" in content
