"""Unit and integration tests for the vk CLI entrypoint."""

from pathlib import Path

from vaultkeeper import __version__
from vaultkeeper.cli.logging import close_cli_logger, setup_cli_logger
from vaultkeeper.cli.main import main


def test_cli_version(capsys) -> None:
    """Verify vk --version exits cleanly."""
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    expected = f"vk {__version__}"
    assert expected in captured.out or expected in captured.err


def test_cli_help(capsys) -> None:
    """Verify vk --help displays all subcommands."""
    code = main([])
    assert code == 0
    captured = capsys.readouterr()
    assert "audit" in captured.out
    assert "check-links" in captured.out
    assert "clean-attachments" in captured.out
    assert "normalize-names" in captured.out
    assert "generate-indices" in captured.out
    assert "frontmatter" in captured.out
    assert "disambiguate" in captured.out
    assert "init" in captured.out


def test_cli_init(empty_temp_dir: Path) -> None:
    """Verify vk init generates vault.toml."""
    code = main(["init", "--target", str(empty_temp_dir)])
    assert code == 0
    assert (empty_temp_dir / "vault.toml").is_file()

    # Re-init without --force should fail
    code_fail = main(["init", "--target", str(empty_temp_dir)])
    assert code_fail == 1


def test_cli_audit(mock_vault: Path) -> None:
    """Verify vk audit runs and returns issues exit code."""
    json_out = mock_vault / "audit_out.json"
    report_md = mock_vault / "audit_report.md"
    log_file = mock_vault / "cli_audit.log"

    code = main(
        [
            "--root",
            str(mock_vault),
            "--log-file",
            str(log_file),
            "audit",
            "--json",
            str(json_out),
            "--report-md",
            str(report_md),
        ]
    )
    # 2 because of mock broken link
    assert code == 2
    assert json_out.is_file()
    assert report_md.is_file()
    assert log_file.is_file()


def test_cli_check_links(mock_vault: Path) -> None:
    """Verify vk check-links identifies broken links."""
    code = main(["--root", str(mock_vault), "check-links"])
    assert code == 2


def test_cli_clean_attachments(mock_vault: Path) -> None:
    """Verify vk clean-attachments dry-run and live execution."""
    orphan = mock_vault / "90-99_Allegati" / "Orphan_Image.png"
    assert orphan.is_file()

    # Dry-run
    code_dry = main(["--root", str(mock_vault), "clean-attachments", "--dry-run"])
    assert code_dry == 0
    assert orphan.is_file()

    # Live soft-delete
    code_live = main(["--root", str(mock_vault), "clean-attachments"])
    assert code_live == 0
    assert not orphan.is_file()


def test_cli_normalize_names(mock_vault: Path) -> None:
    """Verify vk normalize-names dry-run and live execution."""
    bad_file = mock_vault / "20-29_Aree" / "bad name test.md"
    bad_file.write_text("# Bad Name Note\n", encoding="utf-8")

    # Dry run
    code_dry = main(["--root", str(mock_vault), "normalize-names", "--dry-run"])
    assert code_dry == 0
    assert bad_file.is_file()

    # Live
    code_live = main(["--root", str(mock_vault), "normalize-names"])
    assert code_live == 0
    assert not bad_file.exists()
    assert (mock_vault / "20-29_Aree" / "Bad_Name_Test.md").is_file()


def test_cli_generate_indices(mock_vault: Path) -> None:
    """Verify vk generate-indices creates MOC index files."""
    code = main(["--root", str(mock_vault), "generate-indices", "--all"])
    assert code == 0
    idx = mock_vault / "10-19_Progetti" / "00_Indice_Progetti.md"
    assert idx.is_file()


def test_cli_frontmatter_commands(mock_vault: Path) -> None:
    """Verify vk frontmatter subcommands."""
    note = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"

    # set-type
    code1 = main(["--root", str(mock_vault), "frontmatter", "set-type", "--target", str(note), "--type", "Risorsa"])
    assert code1 == 0

    # set-type again (no change)
    code1_same = main(
        ["--root", str(mock_vault), "frontmatter", "set-type", "--target", str(note), "--type", "Risorsa"]
    )
    assert code1_same == 0

    # add-tags
    code2 = main(
        [
            "--root",
            str(mock_vault),
            "frontmatter",
            "add-tags",
            "--target",
            str(note),
            "--tags",
            "test/tag1",
            "test/tag2",
        ]
    )
    assert code2 == 0

    # add-tags with overwrite
    code2_overwrite = main(
        [
            "--root",
            str(mock_vault),
            "frontmatter",
            "add-tags",
            "--target",
            str(note),
            "--tags",
            "area/studio",
            "--overwrite",
        ]
    )
    assert code2_overwrite == 0

    # sanitize-tags on note with deprecated tag
    note_rep = mock_vault / "10-19_Progetti" / "Nota_Da_Sostituire.md"
    note_rep.write_text("---\ntipo: Appunto\ntags:\n  - appunti\n---\n# Test\n", encoding="utf-8")

    code3 = main(["--root", str(mock_vault), "frontmatter", "sanitize-tags"])
    assert code3 == 0
    assert "tipo/appunto" in note_rep.read_text(encoding="utf-8")

    # Missing arguments raises SystemExit 2 in argparse
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--root", str(mock_vault), "frontmatter", "set-type"])
    assert exc.value.code == 2


def test_cli_disambiguate(mock_vault: Path) -> None:
    """Verify vk disambiguate detects no collisions, and reports when collisions exist."""
    code_clean = main(["--root", str(mock_vault), "disambiguate"])
    assert code_clean == 0

    # Create collision
    dup = mock_vault / "20-29_Aree" / "Progetto_Alpha.md"
    dup.write_text("# Duplicate Progetto Alpha", encoding="utf-8")

    code_collision = main(["--root", str(mock_vault), "disambiguate"])
    assert code_collision == 2


def test_cli_logging_file(empty_temp_dir: Path) -> None:
    """Verify setup_cli_logger writes to file cleanly."""
    log_path = empty_temp_dir / "test_run.log"
    logger = setup_cli_logger(name="test_logger", verbose=True, log_file=log_path)
    try:
        logger.info("Message for file logging")
        assert log_path.is_file()
        assert "Message for file logging" in log_path.read_text(encoding="utf-8")
    finally:
        close_cli_logger(logger)
