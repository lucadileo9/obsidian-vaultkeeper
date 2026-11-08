"""Unit tests for MarkdownDocument domain model."""

from pathlib import Path

import pytest

from vaultkeeper.core.document import MarkdownDocument
from vaultkeeper.core.journal import TransactionJournal
from vaultkeeper.exceptions import DocumentError


def test_markdown_document_from_content() -> None:
    """Verify parsing from raw markdown content."""
    raw = """---
tipo: Appunto
tags:
  - area/studio
  - topic/architettura
custom_key: my_value
---

# Architettura del Sistema

Testo introduttivo con collegamento a [[Modulo_Core]] e [[Modulo_Utils|Utility]].
"""
    doc = MarkdownDocument.from_content(raw)
    assert doc.tipo == "Appunto"
    assert "area/studio" in doc.tags
    assert "topic/architettura" in doc.tags
    assert doc.metadata["custom_key"] == "my_value"
    assert "# Architettura del Sistema" in doc.body


def test_markdown_document_from_file_and_save(mock_vault: Path) -> None:
    """Verify loading from file, modifying, and saving back to disk."""
    note_path = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    doc = MarkdownDocument.from_file(note_path)

    assert doc.tipo == "Progetto"
    assert "tipo/progetto" in doc.tags
    assert "Nota_Beta" in doc.get_wikilinks()

    # Modify tags and body
    added = doc.add_tag("stato/revisione")
    assert added
    assert "stato/revisione" in doc.tags

    # Attempt adding same tag again
    assert not doc.add_tag("stato/revisione")

    # Replace wikilink
    count = doc.replace_wikilink("Nota_Beta", "Nota_Beta_Nuova")
    assert count == 1
    assert "[[Nota_Beta_Nuova]]" in doc.body

    # Save to disk
    doc.save()

    # Reload and verify
    reloaded = MarkdownDocument.from_file(note_path)
    assert "stato/revisione" in reloaded.tags
    assert "Nota_Beta_Nuova" in reloaded.get_wikilinks()


def test_markdown_document_save_with_transaction(mock_vault: Path) -> None:
    """Verify saving document under TransactionContext tracks changes."""
    note_path = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    doc = MarkdownDocument.from_file(note_path)
    orig_content = doc.to_content()

    journal = TransactionJournal(mock_vault)
    with journal.begin_transaction("doc_edit", "Edit via MarkdownDocument") as tx:
        doc.tipo = "Risorsa"
        doc.save(transaction=tx)

    # Verify saved
    reloaded = MarkdownDocument.from_file(note_path)
    assert reloaded.tipo == "Risorsa"

    # Revert via journal undo
    res = journal.undo()
    assert res.success

    # Verify original restored
    restored = MarkdownDocument.from_file(note_path)
    assert restored.tipo == "Progetto"
    assert restored.to_content() == orig_content


def test_markdown_document_remove_tag_and_fields() -> None:
    """Verify removing tags and metadata fields."""
    raw = """---
tipo: Appunto
tags:
  - test1
  - test2
---
# Title
"""
    doc = MarkdownDocument.from_content(raw)
    assert doc.remove_tag("test1")
    assert not doc.has_tag("test1")
    assert not doc.remove_tag("nonexistent")

    assert doc.remove_frontmatter_field("tipo")
    assert doc.tipo is None
    assert not doc.remove_frontmatter_field("nonexistent_field")


def test_markdown_document_nonexistent_file_raises() -> None:
    """Verify loading a nonexistent file raises DocumentError."""
    with pytest.raises(DocumentError, match="File not found"):
        MarkdownDocument.from_file("/fake/path/nonexistent.md")


def test_markdown_document_without_frontmatter() -> None:
    """Verify document initialized with pure body without frontmatter."""
    doc = MarkdownDocument.from_content("# Simple Note\nJust body text.")
    assert doc.tipo is None
    assert doc.tags == []
    assert doc.metadata == {}

    # Set tipo creates frontmatter
    doc.tipo = "Appunto"
    assert doc.tipo == "Appunto"
    assert "---" in doc.to_content()

    # Save without path raises DocumentError
    with pytest.raises(DocumentError, match="no path specified"):
        doc.save()
