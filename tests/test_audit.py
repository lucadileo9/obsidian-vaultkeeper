"""Unit tests for the 5-phase audit diagnostics engine."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.audit import compute_health_score, run_audit
from vaultkeeper.models import PhaseResult


def test_run_full_audit(mock_vault: Path) -> None:
    """Verify running full 5-phase audit on mock vault."""
    cfg = load_vault_config(root_path=mock_vault)
    report = run_audit(cfg)

    assert report.vault_root == mock_vault
    assert len(report.phases) == 5
    assert report.total_issues > 0  # Broken link [[Nota_Inesistente]] should be an issue
    assert report.health_score < 100.0

    # Phase 5 should contain broken link
    phase5 = report.phases[4]
    assert phase5.phase_id == 5
    assert len(phase5.issues) >= 1
    assert any("Nota_Inesistente" in is_msg for is_msg in phase5.issues)

    # Convert to dict
    d = report.to_dict()
    assert "health_score" in d
    assert len(d["phases"]) == 5


def test_compute_health_score_clean() -> None:
    """Verify health score is 100.0 for clean vault."""
    phases = [PhaseResult(phase_id=i, title=f"Phase {i}", issues=[], warnings=[], metrics={}) for i in range(1, 6)]
    score = compute_health_score(phases)
    assert score == 100.0


def test_compute_health_score_deductions() -> None:
    """Verify health score deductions."""
    phases = [PhaseResult(phase_id=5, title="Links", issues=["Broken 1", "Broken 2"], warnings=[], metrics={})]
    score = compute_health_score(phases)
    # 100 - (2 * 3.0) = 94.0
    assert score == 94.0


def test_audit_edge_cases(mock_vault: Path) -> None:
    """Verify audit detecting long path, invalid types, and unregistered tags."""
    cfg = load_vault_config(root_path=mock_vault)
    cfg.max_path_length = 20  # Force long path issue

    # Note with invalid tipo and unregistered tag
    bad_note = mock_vault / "10-19_Progetti" / "Bad_Metadata_Note.md"
    bad_note.write_text(
        "---\ntipo: InvalidType\ntags:\n  - tag/non_censito\n---\n# Bad Note\n",
        encoding="utf-8",
    )

    report = run_audit(cfg)
    assert any("Path length" in iss for iss in report.phases[0].issues)
    assert any("Invalid tipo" in iss for iss in report.phases[2].issues)
    assert any("Unregistered tag" in iss for iss in report.phases[3].issues)
