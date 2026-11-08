"""Unit and integration tests for SearchEngine and semantic filtering."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.search import SearchEngine
from vaultkeeper.vault import Vault


def test_search_by_text_query(mock_vault_with_config: Path) -> None:
    """Verify text search matching stem, title, body content, and tags."""
    v = Vault(mock_vault_with_config)

    # Search for "Alpha" (matches Progetto_Alpha in title/body and Nota_Beta in body link)
    res_alpha = v.search(query="Alpha")
    assert res_alpha.total_matches == 2
    titles = [it.title for it in res_alpha.items]
    assert "Progetto Alpha" in titles
    assert "Nota Beta" in titles

    # Search for body term "collegata"
    res_body = v.search(query="collegata")
    assert res_body.total_matches >= 1
    assert any("Nota_Beta" in it.rel_path for it in res_body.items)


def test_search_by_filters(mock_vault_with_config: Path) -> None:
    """Verify semantic filtering by tag, type, links-to, and Johnny.Decimal folder."""
    v = Vault(mock_vault_with_config)

    # 1. Filter by tag
    res_tag = v.search(tag="tipo/progetto")
    assert res_tag.total_matches == 1
    assert res_tag.items[0].title == "Progetto Alpha"

    # 2. Filter by tipo
    res_tipo = v.search(tipo="Appunto")
    assert res_tipo.total_matches == 1
    assert res_tipo.items[0].title == "Nota Beta"

    # 3. Filter by links_to
    res_link = v.search(links_to="Nota_Beta")
    assert res_link.total_matches == 1
    assert "Progetto_Alpha" in res_link.items[0].rel_path

    # 4. Filter by folder
    res_folder = v.search(folder="10-19_Progetti")
    assert all("10-19_Progetti" in it.rel_path for it in res_folder.items)


def test_search_combined_criteria_and_dict_export(mock_vault_with_config: Path) -> None:
    """Verify multi-criteria combination and serialization to dictionary."""
    cfg = load_vault_config(mock_vault_with_config)
    engine = SearchEngine(cfg)

    # Combined: tag + type
    res = engine.search(tag="tipo/progetto", tipo="Progetto")
    assert res.total_matches == 1
    assert res.items[0].tipo == "Progetto"

    # Empty result
    res_empty = engine.search(query="NonexistentTermX999")
    assert res_empty.total_matches == 0
    assert len(res_empty.items) == 0

    # Serialization
    d = res.to_dict()
    assert d["total_matches"] == 1
    assert len(d["items"]) == 1
    assert d["items"][0]["title"] == "Progetto Alpha"
