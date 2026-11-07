"""Tests for utility helpers."""

from pathlib import Path

from vaultkeeper.utils.helpers import compute_file_hash, format_bytes, truncate_text


def test_format_bytes() -> None:
    """Verify human readable byte formatting."""
    assert format_bytes(100) == "100 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1048576) == "1.00 MB"
    assert format_bytes(1073741824) == "1.00 GB"


def test_truncate_text() -> None:
    """Verify text truncation at word boundaries."""
    text = "Questo e' un testo sufficientemente lungo per testare il troncamento."
    assert truncate_text(text, 20) == "Questo e' un testo..."
    assert truncate_text("Breve", 20) == "Breve"


def test_compute_file_hash(empty_temp_dir: Path) -> None:
    """Verify SHA256 hash calculation."""
    f = empty_temp_dir / "sample.txt"
    f.write_text("Hello World", encoding="utf-8")
    h = compute_file_hash(f)
    assert len(h) == 64
    assert isinstance(h, str)


def test_is_ignored_path() -> None:
    """Verify ignored path filter."""
    from vaultkeeper.core.traversal import is_ignored_path

    ignored = {".obsidian", ".trash", "node_modules"}
    assert is_ignored_path(Path("/vault/.obsidian/plugins"), ignored) is True
    assert is_ignored_path(Path("/vault/10-19_Progetti/Note.md"), ignored) is False
    assert is_ignored_path(Path("/vault/.hidden_folder"), ignored) is True
