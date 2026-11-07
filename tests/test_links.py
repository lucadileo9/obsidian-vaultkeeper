"""Unit tests for wikilink resolution, catalog indexing and collision detection."""

from pathlib import Path

from vaultkeeper.config import load_vault_config
from vaultkeeper.core.links import (
    find_stem_collisions,
    parse_wikilink_target,
    resolve_link_target,
    scan_broken_links,
)
from vaultkeeper.core.traversal import build_vault_catalog


def test_parse_wikilink_target() -> None:
    """Verify parsing targets with anchors and aliases."""
    t1, a1, al1 = parse_wikilink_target("Nota_Alpha")
    assert (t1, a1, al1) == ("Nota_Alpha", None, None)

    t2, a2, al2 = parse_wikilink_target("Nota_Alpha#Sezione")
    assert (t2, a2, al2) == ("Nota_Alpha", "Sezione", None)

    t3, a3, al3 = parse_wikilink_target("Nota_Alpha#Sezione|Titolo Visibile")
    assert (t3, a3, al3) == ("Nota_Alpha", "Sezione", "Titolo Visibile")

    t4, a4, al4 = parse_wikilink_target("Nota_Alpha|Titolo")
    assert (t4, a4, al4) == ("Nota_Alpha", None, "Titolo")


def test_resolve_link_target(mock_vault: Path) -> None:
    """Verify link resolution against vault catalog."""
    cfg = load_vault_config(root_path=mock_vault)
    catalog = build_vault_catalog(cfg)
    source = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"

    # Resolves existing note
    res_note = resolve_link_target(catalog, "Nota_Beta", source)
    assert res_note is not None
    assert res_note.name == "Nota_Beta.md"

    # Resolves existing attachment
    res_att = resolve_link_target(catalog, "Allegato_Test.pdf", source)
    assert res_att is not None
    assert res_att.name == "Allegato_Test.pdf"

    # Fails on non-existent note
    res_none = resolve_link_target(catalog, "Nota_Inesistente", source)
    assert res_none is None


def test_scan_broken_links(mock_vault: Path) -> None:
    """Verify scanning notes for broken links."""
    cfg = load_vault_config(root_path=mock_vault)
    catalog = build_vault_catalog(cfg)

    broken = scan_broken_links(catalog, cfg)
    assert len(broken) >= 1
    # Check that Nota_Inesistente was found as broken
    targets = [b.clean_target for b in broken]
    assert "Nota_Inesistente" in targets


def test_find_stem_collisions(mock_vault: Path) -> None:
    """Verify stem collision detector when duplicate note names exist."""
    # Create duplicate note in different folder
    dup = mock_vault / "10-19_Progetti" / "Nota_Beta.md"
    dup.write_text("# Duplicate Beta", encoding="utf-8")

    cfg = load_vault_config(root_path=mock_vault)
    catalog = build_vault_catalog(cfg)
    collisions = find_stem_collisions(catalog)

    assert "Nota_Beta" in collisions
    assert len(collisions["Nota_Beta"]) == 2
