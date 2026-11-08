"""Unit tests for TransactionJournal, TransactionContext, and undo mechanisms."""

from pathlib import Path

import pytest

from vaultkeeper.core.journal import TransactionJournal
from vaultkeeper.exceptions import JournalError, UndoConflictError, UndoError


def test_transaction_write_and_commit(mock_vault: Path) -> None:
    """Verify transaction records changes and writes gzip history."""
    journal = TransactionJournal(mock_vault)
    target = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    orig_content = target.read_text(encoding="utf-8")

    with journal.begin_transaction("edit", "Update alpha note") as tx:
        tx.write_content(target, "# Brand New Content\nUpdated text")

    assert target.read_text(encoding="utf-8") == "# Brand New Content\nUpdated text"

    history = journal.list_transactions()
    assert len(history) == 1
    assert history[0].command == "edit"
    assert history[0].description == "Update alpha note"
    assert len(history[0].actions) == 1
    assert history[0].actions[0].content_before == orig_content
    assert history[0].actions[0].content_after == "# Brand New Content\nUpdated text"


def test_transaction_rollback_on_error(mock_vault: Path) -> None:
    """Verify in-memory rollback restores filesystem when an exception occurs inside context."""
    journal = TransactionJournal(mock_vault)
    target = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    orig_content = target.read_text(encoding="utf-8")
    new_file = mock_vault / "20-29_Aree" / "Temporary_File.md"

    with pytest.raises(RuntimeError, match="Intentional failure"):
        with journal.begin_transaction("failing_cmd", "Will fail") as tx:
            tx.write_content(target, "# Modified before fail")
            tx.create_file(new_file, "# Created before fail")
            assert new_file.is_file()
            raise RuntimeError("Intentional failure")

    # Target should be reverted
    assert target.read_text(encoding="utf-8") == orig_content
    # Created file should be deleted
    assert not new_file.exists()
    # No transaction committed to history
    assert len(journal.list_transactions()) == 0


def test_transaction_move_and_delete(mock_vault: Path) -> None:
    """Verify move_file and delete_file action tracking."""
    journal = TransactionJournal(mock_vault)
    source = mock_vault / "20-29_Aree" / "Nota_Beta.md"
    dest = mock_vault / "20-29_Aree" / "Nota_Beta_Moved.md"

    # Move file
    with journal.begin_transaction("move_test") as tx:
        tx.move_file(source, dest)

    assert not source.exists()
    assert dest.is_file()

    # Delete file
    with journal.begin_transaction("delete_test") as tx:
        tx.delete_file(dest, soft=False)

    assert not dest.exists()

    history = journal.list_transactions()
    assert len(history) == 2


def test_undo_restores_written_content(mock_vault: Path) -> None:
    """Verify undo restores original file content."""
    journal = TransactionJournal(mock_vault)
    target = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    orig_content = target.read_text(encoding="utf-8")

    with journal.begin_transaction("edit_to_undo") as tx:
        tx.write_content(target, "# Completely Changed")

    assert target.read_text(encoding="utf-8") == "# Completely Changed"

    # Preview dry run
    dry_result = journal.undo(dry_run=True)
    assert dry_result.success
    assert target.read_text(encoding="utf-8") == "# Completely Changed"

    # Real undo
    result = journal.undo(dry_run=False)
    assert result.success
    assert result.reverted_actions == 1
    assert target.read_text(encoding="utf-8") == orig_content

    # Re-undo should fail because transaction is already reverted
    with pytest.raises(UndoError, match="already been reverted"):
        journal.undo(tx_id=result.tx_id)


def test_undo_restores_moved_file(mock_vault: Path) -> None:
    """Verify undo restores moved files back to their original paths."""
    journal = TransactionJournal(mock_vault)
    source = mock_vault / "20-29_Aree" / "Nota_Beta.md"
    dest = mock_vault / "10-19_Progetti" / "Nota_Beta_Relocated.md"

    with journal.begin_transaction("move_note") as tx:
        tx.move_file(source, dest)

    assert not source.exists()
    assert dest.is_file()

    result = journal.undo()
    assert result.success
    assert source.is_file()
    assert not dest.exists()


def test_undo_conflict_detection(mock_vault: Path) -> None:
    """Verify undo aborts if file was modified after the transaction."""
    journal = TransactionJournal(mock_vault)
    target = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"

    with journal.begin_transaction("edit1") as tx:
        tx.write_content(target, "Version 2")

    # Simulate subsequent manual edit by user
    target.write_text("Version 3 Manual Edit", encoding="utf-8")

    with pytest.raises(UndoConflictError, match="modified after transaction"):
        journal.undo()


def test_prune_history(mock_vault: Path) -> None:
    """Verify transaction history rotation limits stored transactions."""
    journal = TransactionJournal(mock_vault, max_transactions=3)
    target = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"

    for i in range(5):
        with journal.begin_transaction(f"edit_{i}") as tx:
            tx.write_content(target, f"Version {i}")

    files = list((mock_vault / ".vaultkeeper" / "history").glob("*.json.gz"))
    assert len(files) == 3


def test_undo_empty_history(mock_vault: Path) -> None:
    """Verify undo returns clean failure if history is empty."""
    journal = TransactionJournal(mock_vault)
    result = journal.undo()
    assert not result.success
    assert "No reversible transactions" in result.message


def test_move_nonexistent_fails(mock_vault: Path) -> None:
    """Verify moving non-existent file raises JournalError."""
    journal = TransactionJournal(mock_vault)
    fake_source = mock_vault / "nonexistent.md"
    dest = mock_vault / "dest.md"

    with pytest.raises(JournalError, match="Cannot move nonexistent"):
        with journal.begin_transaction("bad_move") as tx:
            tx.move_file(fake_source, dest)


def test_undo_create_and_delete(mock_vault: Path) -> None:
    """Verify undo on file creation and deletion."""
    journal = TransactionJournal(mock_vault)
    created = mock_vault / "20-29_Aree" / "Created_Note.md"

    # 1. Create file & undo
    with journal.begin_transaction("create_cmd") as tx:
        tx.create_file(created, "# Newly Created")

    assert created.is_file()
    res1 = journal.undo()
    assert res1.success
    assert not created.exists()

    # 2. Delete file & undo
    to_delete = mock_vault / "20-29_Aree" / "Nota_Beta.md"
    orig_text = to_delete.read_text(encoding="utf-8")

    with journal.begin_transaction("delete_cmd") as tx:
        tx.delete_file(to_delete, soft=False)

    assert not to_delete.exists()
    res2 = journal.undo()
    assert res2.success
    assert to_delete.is_file()
    assert to_delete.read_text(encoding="utf-8") == orig_text


def test_undo_move_conflicts(mock_vault: Path) -> None:
    """Verify undo conflict detection on move operations."""
    journal = TransactionJournal(mock_vault)
    source = mock_vault / "20-29_Aree" / "Nota_Beta.md"
    dest = mock_vault / "10-19_Progetti" / "Nota_Beta_Moved.md"

    with journal.begin_transaction("move_test") as tx:
        tx.move_file(source, dest)

    # Conflict 1: destination file deleted externally
    dest.unlink()
    with pytest.raises(UndoConflictError, match="missing. Cannot undo move"):
        journal.undo()

    # Recreate dest, occupy source
    dest.write_text("recreated dest", encoding="utf-8")
    source.write_text("occupied source", encoding="utf-8")
    with pytest.raises(UndoConflictError, match="already occupied"):
        journal.undo()


def test_get_transaction_and_undo_by_id(mock_vault: Path) -> None:
    """Verify get_transaction and undo with explicit tx_id."""
    journal = TransactionJournal(mock_vault)
    target = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"

    assert journal.get_transaction("tx_fake_id") is None

    with journal.begin_transaction("edit_step1") as tx1:
        tx1.write_content(target, "Version 2")
    tx1_id = tx1.tx_id

    # Retrieve and verify
    rec = journal.get_transaction(tx1_id)
    assert rec is not None
    assert rec.tx_id == tx1_id
    assert not rec.reverted

    # Nonexistent tx_id undo raises UndoError
    with pytest.raises(UndoError, match="not found in history"):
        journal.undo(tx_id="tx_nonexistent")

    # Undo specific transaction
    res = journal.undo(tx_id=tx1_id)
    assert res.success
    assert res.tx_id == tx1_id


def test_rollback_in_memory_on_move_and_delete(mock_vault: Path) -> None:
    """Verify in-memory rollback handles move and delete actions."""
    journal = TransactionJournal(mock_vault)
    source = mock_vault / "20-29_Aree" / "Nota_Beta.md"
    dest = mock_vault / "20-29_Aree" / "Nota_Beta_Temp.md"
    alpha = mock_vault / "10-19_Progetti" / "Progetto_Alpha.md"
    orig_alpha = alpha.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="Rollback move test"):
        with journal.begin_transaction("move_and_delete") as tx:
            tx.move_file(source, dest)
            tx.delete_file(alpha, soft=False)
            raise ValueError("Rollback move test")

    assert source.is_file()
    assert not dest.exists()
    assert alpha.is_file()
    assert alpha.read_text(encoding="utf-8") == orig_alpha
