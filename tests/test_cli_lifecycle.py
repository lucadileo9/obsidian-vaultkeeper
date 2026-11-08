"""Integration tests for lifecycle CLI subcommands: vk rename, vk move, vk archive, and vk offload."""

from pathlib import Path

from vaultkeeper.cli.main import main


def test_cli_rename_and_undo(mock_vault_with_config: Path) -> None:
    """Verify vk rename updates file, incoming links, and undo reverts."""
    target_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    referencing_note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    assert target_note.exists()
    assert "[[Nota_Beta]]" in referencing_note.read_text(encoding="utf-8")

    # Rename via CLI
    code = main(
        [
            "--root",
            str(mock_vault_with_config),
            "rename",
            str(target_note),
            "Nota_Beta_Nuova",
        ]
    )
    assert code == 0

    new_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta_Nuova.md"
    assert new_note.exists()
    assert not target_note.exists()
    assert "[[Nota_Beta_Nuova]]" in referencing_note.read_text(encoding="utf-8")

    # Undo rename
    code_undo = main(["--root", str(mock_vault_with_config), "undo"])
    assert code_undo == 0
    assert target_note.exists()
    assert not new_note.exists()
    assert "[[Nota_Beta]]" in referencing_note.read_text(encoding="utf-8")


def test_cli_rename_dry_run_and_errors(mock_vault_with_config: Path) -> None:
    """Verify vk rename dry-run and error handling."""
    target_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"

    # Dry-run
    code_dry = main(
        [
            "--root",
            str(mock_vault_with_config),
            "rename",
            "--dry-run",
            str(target_note),
            "Nota_Beta_Simulata",
        ]
    )
    assert code_dry == 0
    assert target_note.exists()
    assert not (mock_vault_with_config / "20-29_Aree" / "Nota_Beta_Simulata.md").exists()

    # Collision error: rename to stem that already exists in 10-19_Progetti
    code_err = main(
        [
            "--root",
            str(mock_vault_with_config),
            "rename",
            str(target_note),
            "Progetto_Alpha",
        ]
    )
    assert code_err != 0

    # Non-existent file
    code_ghost = main(
        [
            "--root",
            str(mock_vault_with_config),
            "rename",
            str(mock_vault_with_config / "Ghost.md"),
            "Nuovo_Nome",
        ]
    )
    assert code_ghost != 0


def test_cli_move_and_undo(mock_vault_with_config: Path) -> None:
    """Verify vk move relocates file, updates indices, and undo reverts."""
    target_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    dest_dir = mock_vault_with_config / "10-19_Progetti"

    # Move via CLI
    code = main(
        [
            "--root",
            str(mock_vault_with_config),
            "move",
            str(target_note),
            str(dest_dir),
        ]
    )
    assert code == 0

    moved_file = dest_dir / "Nota_Beta.md"
    assert moved_file.exists()
    assert not target_note.exists()

    # Check index in dest_dir
    idx = dest_dir / "00_Indice_Progetti.md"
    assert "[[Nota_Beta]]" in idx.read_text(encoding="utf-8")

    # Undo move
    code_undo = main(["--root", str(mock_vault_with_config), "undo"])
    assert code_undo == 0
    assert target_note.exists()
    assert not moved_file.exists()


def test_cli_move_dry_run_and_errors(mock_vault_with_config: Path) -> None:
    """Verify vk move dry-run and error conditions."""
    target_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    dest_dir = mock_vault_with_config / "10-19_Progetti"

    # Dry-run
    code_dry = main(
        [
            "--root",
            str(mock_vault_with_config),
            "move",
            "--dry-run",
            str(target_note),
            str(dest_dir),
        ]
    )
    assert code_dry == 0
    assert target_note.exists()
    assert not (dest_dir / "Nota_Beta.md").exists()

    # Non-existent target
    code_err = main(
        [
            "--root",
            str(mock_vault_with_config),
            "move",
            str(mock_vault_with_config / "Ghost.md"),
            str(dest_dir),
        ]
    )
    assert code_err != 0


def test_cli_archive_and_undo(mock_vault_with_config: Path) -> None:
    """Verify vk archive moves to cold storage, leaves tombstone, and undo restores."""
    note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    # Archive via CLI
    code = main(
        [
            "--root",
            str(mock_vault_with_config),
            "archive",
            str(note),
        ]
    )
    assert code == 0
    assert note.exists()  # Tombstone left in place
    assert "stato: archiviato" in note.read_text(encoding="utf-8")

    # Undo archive
    code_undo = main(["--root", str(mock_vault_with_config), "undo"])
    assert code_undo == 0
    orig_content = note.read_text(encoding="utf-8")
    assert "# Progetto Alpha\n" in orig_content
    assert "(Archiviato)" not in orig_content


def test_cli_archive_no_tombstone_and_dry_run(mock_vault_with_config: Path) -> None:
    """Verify vk archive --no-tombstone and --dry-run flags."""
    note = mock_vault_with_config / "10-19_Progetti" / "Progetto_Alpha.md"

    # Dry-run
    code_dry = main(
        [
            "--root",
            str(mock_vault_with_config),
            "archive",
            "--dry-run",
            str(note),
        ]
    )
    assert code_dry == 0
    assert note.exists()
    assert "stato: archiviato" not in note.read_text(encoding="utf-8")

    # Archive without tombstone
    code_no_ts = main(
        [
            "--root",
            str(mock_vault_with_config),
            "archive",
            "--no-tombstone",
            str(note),
        ]
    )
    assert code_no_ts == 0
    assert not note.exists()

    # Revert via undo
    code_undo = main(["--root", str(mock_vault_with_config), "undo"])
    assert code_undo == 0
    assert note.exists()

    # Non-existent target
    code_ghost = main(
        [
            "--root",
            str(mock_vault_with_config),
            "archive",
            str(mock_vault_with_config / "Ghost.md"),
        ]
    )
    assert code_ghost != 0


def test_cli_offload_and_undo(mock_vault_with_config: Path) -> None:
    """Verify vk offload migrates media, updates notes, and undo restores."""
    heavy_file = mock_vault_with_config / "90-99_Allegati" / "Heavy_Video.mp4"
    heavy_file.write_bytes(b"B" * 2048)

    referencing_note = mock_vault_with_config / "20-29_Aree" / "Nota_Beta.md"
    orig_text = referencing_note.read_text(encoding="utf-8")
    referencing_note.write_text(orig_text + "\n\n![[Heavy_Video.mp4]]\n", encoding="utf-8")

    # Dry-run
    code_dry = main(
        [
            "--root",
            str(mock_vault_with_config),
            "offload",
            "--dry-run",
            str(heavy_file),
        ]
    )
    assert code_dry == 0
    assert heavy_file.exists()

    # Real offload
    code_off = main(
        [
            "--root",
            str(mock_vault_with_config),
            "offload",
            str(heavy_file),
        ]
    )
    assert code_off == 0
    assert not heavy_file.exists()
    assert "> [!INFO] Allegato archiviato" in referencing_note.read_text(encoding="utf-8")

    # Undo offload
    code_undo = main(["--root", str(mock_vault_with_config), "undo"])
    assert code_undo == 0
    assert heavy_file.exists()
    assert "![[Heavy_Video.mp4]]" in referencing_note.read_text(encoding="utf-8")


def test_cli_offload_empty_and_error(mock_vault_with_config: Path) -> None:
    """Verify vk offload when no files match or target is invalid."""
    # When no heavy files exist
    code_empty = main(["--root", str(mock_vault_with_config), "offload"])
    assert code_empty == 0

    # Non-existent target
    code_err = main(
        [
            "--root",
            str(mock_vault_with_config),
            "offload",
            str(mock_vault_with_config / "Nonexistent.mp4"),
        ]
    )
    assert code_err != 0
