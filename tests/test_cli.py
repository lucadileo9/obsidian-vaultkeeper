"""Unit and integration tests for the vk CLI entrypoint."""

from pathlib import Path

from vaultkeeper.cli.main import main


def test_cli_version(capsys) -> None:
    """Verify vk --version exits cleanly."""
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert "vk 0.1.0" in captured.out or "vk 0.1.0" in captured.err


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


def test_cli_audit(mock_vault: Path) -> None:
    """Verify vk audit runs and returns issues exit code."""
    json_out = mock_vault / "audit_out.json"
    code = main(["--root", str(mock_vault), "audit", "--json", str(json_out)])
    # 2 because of mock broken link
    assert code == 2
    assert json_out.is_file()


def test_cli_check_links(mock_vault: Path) -> None:
    """Verify vk check-links identifies broken links."""
    code = main(["--root", str(mock_vault), "check-links"])
    assert code == 2


def test_cli_clean_attachments_dry_run(mock_vault: Path) -> None:
    """Verify vk clean-attachments with --dry-run leaves files intact."""
    orphan = mock_vault / "90-99_Allegati" / "Orphan_Image.png"
    code = main(["--root", str(mock_vault), "clean-attachments", "--dry-run"])
    assert code == 0
    assert orphan.is_file()


def test_cli_normalize_names_dry_run(mock_vault: Path) -> None:
    """Verify vk normalize-names --dry-run."""
    code = main(["--root", str(mock_vault), "normalize-names", "--dry-run"])
    assert code == 0


def test_cli_generate_indices(mock_vault: Path) -> None:
    """Verify vk generate-indices creates MOC index files."""
    code = main(["--root", str(mock_vault), "generate-indices", "--all"])
    assert code == 0
    # Check that index note was generated
    idx = mock_vault / "10-19_Progetti" / "00_Indice_Progetti.md"
    assert idx.is_file()


def test_cli_frontmatter_commands(mock_vault: Path) -> None:
    """Verify vk frontmatter subcommands."""
    note = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"

    # set-type
    code1 = main(["--root", str(mock_vault), "frontmatter", "set-type", "--target", str(note), "--type", "Risorsa"])
    assert code1 == 0

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

    # sanitize-tags
    code3 = main(["--root", str(mock_vault), "frontmatter", "sanitize-tags"])
    assert code3 == 0


def test_cli_disambiguate(mock_vault: Path) -> None:
    """Verify vk disambiguate detects no collisions in default mock vault."""
    code = main(["--root", str(mock_vault), "disambiguate"])
    assert code == 0
