"""Unit tests for attachment tracking, orphan detection and soft-deletion."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.attachments import (
    find_heavy_files,
    find_orphan_attachments,
    hard_delete_attachment,
    soft_delete_attachment,
)
from vaultkeeper.core.traversal import build_vault_catalog


def test_find_orphan_attachments(mock_vault: Path) -> None:
    """Verify orphan detector isolates unreferenced media files."""
    cfg = load_vault_config(root_path=mock_vault)
    catalog = build_vault_catalog(cfg)

    orphans = find_orphan_attachments(catalog, cfg)
    assert len(orphans) == 1
    assert orphans[0].file_path.name == "Orphan_Image.png"


def test_find_heavy_files(mock_vault: Path) -> None:
    """Verify heavy file detector thresholds."""
    cfg = load_vault_config(root_path=mock_vault)
    cfg.heavy_file_threshold_mb = 1  # 1 MB threshold

    # Create dummy 1.5 MB file
    heavy = mock_vault / "90-99_Allegati" / "Heavy_Data.zip"
    heavy.write_bytes(b"\x00" * (1500 * 1024))

    catalog = build_vault_catalog(cfg)
    found = find_heavy_files(catalog, cfg)
    assert len(found) == 1
    assert found[0][0].name == "Heavy_Data.zip"


def test_soft_delete_attachment(mock_vault: Path) -> None:
    """Verify soft-delete moves file into .trash directory."""
    orphan = mock_vault / "90-99_Allegati" / "Orphan_Image.png"
    assert orphan.exists()

    trash_dest = soft_delete_attachment(orphan, mock_vault, trash_folder_name=".trash")
    assert not orphan.exists()
    assert trash_dest.is_file()
    assert ".trash" in str(trash_dest)


def test_hard_delete_attachment(mock_vault: Path) -> None:
    """Verify hard delete permanently deletes file."""
    orphan = mock_vault / "90-99_Allegati" / "Orphan_Image.png"
    assert orphan.exists()
    hard_delete_attachment(orphan)
    assert not orphan.exists()
