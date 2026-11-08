"""Integration tests for 'vk history' and 'vk undo' CLI subcommands."""

from pathlib import Path

from vaultkeeper.cli.main import main


def test_cli_history_empty(mock_vault: Path, capsys) -> None:
    """Verify vk history when no transactions have occurred."""
    code = main(["--root", str(mock_vault), "history"])
    assert code == 0


def test_cli_normalize_names_and_undo(mock_vault: Path) -> None:
    """Verify normalizing names records transaction and vk undo restores previous filenames."""
    # Create non-conformant note
    bad_note = mock_vault / "10-19_Progetti" / "mio progetto disordinato.md"
    bad_note.write_text("# Test disordinato", encoding="utf-8")

    # Run live normalization
    code_norm = main(["--root", str(mock_vault), "normalize-names"])
    assert code_norm == 0
    assert not bad_note.exists()

    normalized = mock_vault / "10-19_Progetti" / "Mio_Progetto_Disordinato.md"
    assert normalized.is_file()

    # Check history
    code_hist = main(["--root", str(mock_vault), "history", "--format", "json"])
    assert code_hist == 0

    # Undo dry-run preview
    code_undo_dry = main(["--root", str(mock_vault), "undo", "--dry-run"])
    assert code_undo_dry == 0
    assert normalized.is_file()

    # Real undo
    code_undo = main(["--root", str(mock_vault), "undo"])
    assert code_undo == 0
    assert bad_note.is_file()
    assert not normalized.exists()


def test_cli_clean_attachments_and_undo(mock_vault: Path) -> None:
    """Verify soft-cleaning orphan attachments and restoring via vk undo."""
    orphan = mock_vault / "90-99_Allegati" / "Orphan_Image.png"
    assert orphan.is_file()

    # Soft delete orphan
    code_clean = main(["--root", str(mock_vault), "clean-attachments"])
    assert code_clean == 0
    assert not orphan.is_file()

    # Undo
    code_undo = main(["--root", str(mock_vault), "undo"])
    assert code_undo == 0
    assert orphan.is_file()


def test_cli_frontmatter_and_undo(mock_vault: Path) -> None:
    """Verify frontmatter change and reverting with vk undo."""
    note = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    orig_text = note.read_text(encoding="utf-8")

    # Set new tipo
    code_fm = main(
        [
            "--root",
            str(mock_vault),
            "frontmatter",
            "set-type",
            "--target",
            str(note),
            "--type",
            "Risorsa",
        ]
    )
    assert code_fm == 0
    assert "tipo: Risorsa" in note.read_text(encoding="utf-8")

    # Undo
    code_undo = main(["--root", str(mock_vault), "undo"])
    assert code_undo == 0
    assert note.read_text(encoding="utf-8") == orig_text


def test_cli_undo_when_empty_history(mock_vault: Path) -> None:
    """Verify vk undo fails gracefully when no transactions exist."""
    code = main(["--root", str(mock_vault), "undo"])
    assert code == 1


def test_cli_history_formats_and_limits(mock_vault: Path) -> None:
    """Verify vk history renders cleanly with yaml, csv, and md limits."""
    note = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    main(["--root", str(mock_vault), "frontmatter", "set-type", "--target", str(note), "--type", "Risorsa"])

    for fmt in ["yaml", "csv", "md"]:
        code = main(["--root", str(mock_vault), "history", "--format", fmt, "--limit", "5"])
        assert code == 0


def test_cli_undo_conflict_returns_error(mock_vault: Path) -> None:
    """Verify vk undo returns error code 1 when conflict is detected."""
    note = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    main(["--root", str(mock_vault), "frontmatter", "set-type", "--target", str(note), "--type", "Risorsa"])

    # Modify file externally to trigger hash conflict
    note.write_text("external edit conflict", encoding="utf-8")

    code_undo = main(["--root", str(mock_vault), "undo"])
    assert code_undo == 1
