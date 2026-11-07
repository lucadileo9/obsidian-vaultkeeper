"""Unit tests for frontmatter parsing, updating and tag taxonomy inspection."""

from pathlib import Path

from vaultkeeper.core.frontmatter import (
    extract_inline_tags,
    parse_note_content,
    parse_taxonomy_file,
    update_frontmatter,
)


def test_parse_valid_frontmatter() -> None:
    """Verify parsing of valid YAML frontmatter."""
    content = """---
tipo: Appunto
tags:
  - area/studio
  - tipo/appunto
descrizione: Una nota di prova
---

# Corpo della Nota

Contenuto principale.
"""
    fm, body = parse_note_content(content)
    assert fm is not None
    assert fm.tipo == "Appunto"
    assert "area/studio" in fm.tags
    assert "tipo/appunto" in fm.tags
    assert fm.metadata.get("descrizione") == "Una nota di prova"
    assert "# Corpo della Nota" in body


def test_parse_content_without_frontmatter() -> None:
    """Verify parsing of pure markdown without frontmatter."""
    content = "# Solo Titolo\n\nTesto senza YAML."
    fm, body = parse_note_content(content)
    assert fm is None
    assert body == content


def test_update_frontmatter_existing() -> None:
    """Verify updating existing frontmatter fields preserves other fields."""
    content = """---
tipo: Appunto
tags:
  - tag1
autore: Luca
---

Testo.
"""
    updated = update_frontmatter(content, {"tipo": "Progetto", "stato": "attivo"})
    fm, body = parse_note_content(updated)
    assert fm is not None
    assert fm.tipo == "Progetto"
    assert fm.metadata.get("stato") == "attivo"
    assert fm.metadata.get("autore") == "Luca"
    assert "Testo." in body


def test_update_frontmatter_new() -> None:
    """Verify prepending new frontmatter block when note had none."""
    content = "# Titolo\n\nTesto semplice."
    updated = update_frontmatter(content, {"tipo": "Risorsa", "tags": ["tagA"]})
    fm, body = parse_note_content(updated)
    assert fm is not None
    assert fm.tipo == "Risorsa"
    assert "tagA" in fm.tags
    assert "# Titolo" in body


def test_extract_inline_tags_with_protections() -> None:
    """Verify inline tag extraction protects C directives and hex colors."""
    text = """
Questo e' un paragrafo con un tag valido #argomento/python e un altro #test.

Ecco una direttiva C che non deve essere considerata tag:
#include <stdio.h>
#define BUFFER_SIZE 1024

Ecco dei colori HEX:
Il colore di sfondo e' #FFFFFF oppure #000 oppure #2a3b4c.

Nel codice `print('#non_un_tag')` non deve essere estratto.

Anche nei blocchi di codice:
```c
#include <stdlib.h>
int x = 10;
```
"""
    tags = extract_inline_tags(text, protect_c=True, protect_hex=True)
    assert "argomento/python" in tags
    assert "test" in tags
    assert "include" not in tags
    assert "define" not in tags
    assert "FFFFFF" not in tags
    assert "000" not in tags
    assert "non_un_tag" not in tags


def test_parse_taxonomy_file(mock_vault: Path) -> None:
    """Verify parsing registered tags from taxonomy file."""
    tax_path = mock_vault / "00-09_Meta" / "00_Tassonomia_Tag.md"
    tags = parse_taxonomy_file(tax_path)
    assert "area/lavoro" in tags
    assert "area/studio" in tags


def test_parse_frontmatter_edge_cases() -> None:
    """Verify parsing frontmatter with comma-separated tags or invalid YAML."""
    # Comma-separated tags string
    content_comma = "---\ntags: tag1, tag2, tag3\ntipo: Appunto\n---\nCorpo"
    fm, _ = parse_note_content(content_comma)
    assert fm is not None
    assert "tag1" in fm.tags
    assert "tag2" in fm.tags

    # Invalid YAML
    content_bad_yaml = "---\n: bad yaml [\n---\nCorpo"
    fm_bad, body_bad = parse_note_content(content_bad_yaml)
    assert fm_bad is None
    assert "Corpo" in body_bad

    # YAML that is a scalar instead of a dict
    content_scalar = "---\nJust a string\n---\nCorpo"
    fm_scalar, body_scalar = parse_note_content(content_scalar)
    assert fm_scalar is None
    assert "Corpo" in body_scalar
