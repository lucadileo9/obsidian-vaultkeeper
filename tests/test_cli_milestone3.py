"""Integration tests for Milestone 3 CLI commands: tags, config, search, graph-health, and map."""

from pathlib import Path

from vaultkeeper.cli.main import main


def test_cli_tags_show_add_remove(mock_vault_with_config: Path, capsys) -> None:
    """Verify vk tags show, add, and remove CLI flows."""
    root_str = str(mock_vault_with_config)

    # 1. tags show default (md)
    code_show = main(["--root", root_str, "tags", "show"])
    assert code_show == 0

    # 2. tags show with query
    code_query = main(["--root", root_str, "tags", "show", "--query", "progetto"])
    assert code_query == 0

    # 3. tags show json format
    code_json = main(["--root", root_str, "tags", "show", "--format", "json"])
    assert code_json == 0

    # 4. tags add dry-run
    code_add_dry = main(["--root", root_str, "tags", "add", "area/marketing", "--dry-run"])
    assert code_add_dry == 0

    # 5. tags add real
    code_add = main(["--root", root_str, "tags", "add", "area/marketing"])
    assert code_add == 0

    # Verify presence via show
    capsys.readouterr()  # clear buffer
    main(["--root", root_str, "tags", "show", "--query", "marketing"])
    out = capsys.readouterr().out
    assert "#area/marketing" in out

    # 6. tags remove without force on in-use tag should fail
    code_rm_fail = main(["--root", root_str, "tags", "remove", "tipo/progetto"])
    assert code_rm_fail != 0

    # 7. tags remove on unused tag should succeed
    code_rm = main(["--root", root_str, "tags", "remove", "area/marketing"])
    assert code_rm == 0

    # 8. tags undo restores removed tag
    code_undo = main(["--root", root_str, "undo"])
    assert code_undo == 0


def test_cli_config_show_and_set(mock_vault_with_config: Path) -> None:
    """Verify vk config show and set CLI commands."""
    root_str = str(mock_vault_with_config)

    # config show
    code_show = main(["--root", root_str, "config", "show"])
    assert code_show == 0

    # config show json
    code_show_json = main(["--root", root_str, "config", "show", "--format", "json"])
    assert code_show_json == 0

    # config set dry-run
    code_set_dry = main(["--root", root_str, "config", "set", "naming.style", "kebab-case", "--dry-run"])
    assert code_set_dry == 0

    # config set real
    code_set = main(["--root", root_str, "config", "set", "naming.style", "kebab-case"])
    assert code_set == 0

    cfg_file = mock_vault_with_config / "vault.toml"
    assert 'style = "kebab-case"' in cfg_file.read_text(encoding="utf-8")

    # undo config set
    code_undo = main(["--root", root_str, "undo"])
    assert code_undo == 0
    assert 'style = "kebab-case"' not in cfg_file.read_text(encoding="utf-8")


def test_cli_search(mock_vault_with_config: Path, capsys) -> None:
    """Verify vk search CLI execution with filters and formats."""
    root_str = str(mock_vault_with_config)

    # 1. Search text query
    code_q = main(["--root", root_str, "search", "Alpha"])
    assert code_q == 0
    out = capsys.readouterr().out
    assert "Progetto Alpha" in out

    # 2. Search by tag
    code_tag = main(["--root", root_str, "search", "--tag", "tipo/appunto"])
    assert code_tag == 0

    # 3. Search by type
    code_type = main(["--root", root_str, "search", "--type", "Progetto"])
    assert code_type == 0

    # 4. Search by links-to
    code_link = main(["--root", root_str, "search", "--links-to", "Nota_Beta"])
    assert code_link == 0

    # 5. Search with json format
    code_json = main(["--root", root_str, "search", "--type", "Progetto", "--format", "json"])
    assert code_json == 0


def test_cli_graph_health(mock_vault_with_config: Path, capsys) -> None:
    """Verify vk graph-health execution."""
    root_str = str(mock_vault_with_config)

    # Default md
    code_gh = main(["--root", root_str, "graph-health"])
    assert code_gh == 0
    out = capsys.readouterr().out
    assert "Diagnostica Topologica del Grafo" in out
    assert "Totale Nodi" in out

    # JSON format
    code_json = main(["--root", root_str, "graph-health", "--format", "json"])
    assert code_json == 0


def test_cli_map(mock_vault_with_config: Path, capsys) -> None:
    """Verify vk map execution and master MOC output generation."""
    root_str = str(mock_vault_with_config)

    # Default md output
    code_map = main(["--root", root_str, "map"])
    assert code_map == 0
    out = capsys.readouterr().out
    assert "Mappa Strutturale del Vault" in out
    assert "10-19_Progetti" in out

    # Write to custom output file
    out_file = mock_vault_with_config / "00_Custom_Map.md"
    code_write = main(["--root", root_str, "map", "--output", str(out_file)])
    assert code_write == 0
    assert out_file.is_file()
    assert "Mappa Strutturale del Vault" in out_file.read_text(encoding="utf-8")

    # JSON format
    code_json = main(["--root", root_str, "map", "--format", "json"])
    assert code_json == 0


def test_cli_milestone3_edge_cases_and_formats(mock_vault_with_config: Path, capsys) -> None:
    """Verify edge cases and alternative output formats for Milestone 3 CLI commands."""
    root_str = str(mock_vault_with_config)

    # 1. tags with no action
    assert main(["--root", root_str, "tags"]) != 0

    # 2. config with no action
    assert main(["--root", root_str, "config"]) != 0

    # 3. search empty results in markdown format
    capsys.readouterr()
    code_empty = main(["--root", root_str, "search", "Z99_Nonexistent_Term_XYZ"])
    assert code_empty == 0
    assert "Nessuna nota trovata" in capsys.readouterr().out

    # 4. search in yaml and csv format
    assert main(["--root", root_str, "search", "--format", "yaml"]) == 0
    assert main(["--root", root_str, "search", "--format", "csv"]) == 0

    # 5. graph-health in yaml format
    assert main(["--root", root_str, "graph-health", "--format", "yaml"]) == 0
