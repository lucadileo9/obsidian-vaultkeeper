"""Unit and integration tests for GraphTelemetry non-punitive topological analysis."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.graph import GraphTelemetry
from vaultkeeper.vault import Vault


def test_graph_telemetry_metrics(mock_vault_with_config: Path) -> None:
    """Verify nodes, edges, hubs, dead-ends, and true orphans detection."""
    # Note 1: Progetto_Alpha links to Nota_Beta
    # Note 2: Nota_Beta links to Progetto_Alpha
    # Add an isolated note (orphan not in any index)
    isolated_note = mock_vault_with_config / "20-29_Aree" / "Nota_Isolata.md"
    isolated_note.write_text("---\ntipo: Appunto\n---\n# Nota Isolata\nTesto senza link.", encoding="utf-8")

    # Add a dead-end note: links into it, but it links to nothing
    dead_end_note = mock_vault_with_config / "20-29_Aree" / "Vicolo_Cieco.md"
    dead_end_note.write_text("---\ntipo: Appunto\n---\n# Vicolo Cieco\nNessun link.", encoding="utf-8")

    # Link into dead_end_note from Progetto_Alpha
    alpha_note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"
    alpha_text = alpha_note.read_text(encoding="utf-8")
    alpha_note.write_text(alpha_text + "\n[[Vicolo_Cieco]]\n", encoding="utf-8")

    cfg = load_vault_config(mock_vault_with_config)
    telemetry = GraphTelemetry(cfg)
    report = telemetry.analyze()

    assert report.total_nodes >= 4
    assert report.total_edges >= 3

    # Check true orphans
    assert "Nota_Isolata" in report.true_orphans

    # Check dead-ends
    assert "Vicolo_Cieco" in report.dead_ends

    # Check hubs
    hub_stems = [h.stem for h in report.top_hubs]
    assert "Nota_Beta" in hub_stems or "Progetto_Alpha" in hub_stems or "Vicolo_Cieco" in hub_stems

    # Serialization
    d = report.to_dict()
    assert "vault_root" in d
    assert d["true_orphans_count"] >= 1
    assert d["dead_ends_count"] >= 1


def test_graph_telemetry_facade(mock_vault_with_config: Path) -> None:
    """Verify Vault.graph_health facade method."""
    v = Vault(mock_vault_with_config)
    report = v.graph_health()
    assert report.total_nodes >= 2
    assert report.total_edges >= 2
