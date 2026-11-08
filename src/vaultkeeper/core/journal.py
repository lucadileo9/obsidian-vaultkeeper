"""Transaction journaling, atomic execution context, and undo engine."""

import gzip
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Union

from ..exceptions import JournalError, UndoConflictError, UndoError
from ..models import ActionRecord, TransactionRecord, UndoResult


def compute_content_hash(text: Optional[str]) -> Optional[str]:
    """Compute SHA-256 hash of a string."""
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TransactionContext:
    """Context manager executing atomic filesystem operations with rollback support."""

    def __init__(
        self,
        journal: "TransactionJournal",
        command: str,
        description: str = "",
    ) -> None:
        self.journal = journal
        self.root_path = journal.root_path
        self.command = command
        self.description = description
        now = datetime.now(timezone.utc)
        short_id = uuid.uuid4().hex[:6]
        self.tx_id = f"tx_{now.strftime('%Y%m%d_%H%M%S_%f')}_{short_id}"
        self.timestamp = now.isoformat()
        self.actions: List[ActionRecord] = []
        self.active: bool = False
        self.committed: bool = False

    def __enter__(self) -> "TransactionContext":
        self.active = True
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.active = False
        if exc_type is not None:
            # Error occurred during execution: perform in-memory rollback
            self._rollback_in_memory()
            return

        # Normal completion: persist transaction record if any actions were recorded
        if self.actions:
            self._commit()

    def _resolve_rel(self, path: Union[str, Path]) -> str:
        """Return path relative to vault root as a normalized POSIX string."""
        abs_p = (self.root_path / path if not Path(path).is_absolute() else Path(path)).resolve()
        try:
            return abs_p.relative_to(self.root_path).as_posix()
        except ValueError:
            return abs_p.as_posix()

    def write_content(
        self,
        file_path: Union[str, Path],
        new_content: str,
        encoding: str = "utf-8",
    ) -> None:
        """Write content to a file while recording pre-state and post-state."""
        abs_path = (self.root_path / file_path if not Path(file_path).is_absolute() else Path(file_path)).resolve()
        rel_path = self._resolve_rel(abs_path)
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        if abs_path.is_file():
            content_before: Optional[str] = abs_path.read_text(encoding=encoding)
            action_type = "write_content"
        else:
            content_before = None
            action_type = "create_file"

        hash_before = compute_content_hash(content_before)
        hash_after = compute_content_hash(new_content)

        abs_path.write_text(new_content, encoding=encoding)

        self.actions.append(
            ActionRecord(
                action_type=action_type,
                path=rel_path,
                content_before=content_before,
                content_after=new_content,
                hash_before=hash_before,
                hash_after=hash_after,
            )
        )

    def create_file(
        self,
        file_path: Union[str, Path],
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """Explicitly create a new file under transaction control."""
        self.write_content(file_path, content, encoding=encoding)

    def move_file(
        self,
        source_path: Union[str, Path],
        dest_path: Union[str, Path],
    ) -> None:
        """Move or rename a file or directory while recording previous and new path."""
        abs_src = (self.root_path / source_path if not Path(source_path).is_absolute() else Path(source_path)).resolve()
        abs_dest = (self.root_path / dest_path if not Path(dest_path).is_absolute() else Path(dest_path)).resolve()

        if not abs_src.exists():
            raise JournalError(f"Cannot move nonexistent path: {abs_src}")

        rel_src = self._resolve_rel(abs_src)
        rel_dest = self._resolve_rel(abs_dest)
        abs_dest.parent.mkdir(parents=True, exist_ok=True)

        hash_before = None
        if abs_src.is_file():
            try:
                hash_before = hashlib.sha256(abs_src.read_bytes()).hexdigest()
            except Exception:
                hash_before = None

        shutil.move(str(abs_src), str(abs_dest))

        self.actions.append(
            ActionRecord(
                action_type="move_file",
                path=rel_src,
                target_path=rel_dest,
                hash_before=hash_before,
            )
        )

    def delete_file(
        self,
        file_path: Union[str, Path],
        soft: bool = False,
        trash_folder: Optional[str] = None,
    ) -> None:
        """Delete or soft-delete a file while logging rollback capabilities."""
        abs_path = (self.root_path / file_path if not Path(file_path).is_absolute() else Path(file_path)).resolve()
        if not abs_path.exists():
            return

        rel_path = self._resolve_rel(abs_path)

        if soft:
            trash_dir_name = trash_folder or ".trash"
            dest_trash = self.root_path / trash_dir_name / abs_path.name
            dest_trash.parent.mkdir(parents=True, exist_ok=True)
            self.move_file(abs_path, dest_trash)
            return

        # Hard delete: preserve text content if possible
        content_before = None
        hash_before = None
        if abs_path.is_file():
            try:
                content_before = abs_path.read_text(encoding="utf-8")
                hash_before = compute_content_hash(content_before)
            except Exception:
                content_before = None
                hash_before = hashlib.sha256(abs_path.read_bytes()).hexdigest()

        abs_path.unlink()

        self.actions.append(
            ActionRecord(
                action_type="delete_file",
                path=rel_path,
                content_before=content_before,
                hash_before=hash_before,
            )
        )

    def _rollback_in_memory(self) -> None:
        """Revert all actions performed so far in reverse chronological order."""
        for action in reversed(self.actions):
            abs_path = self.root_path / action.path
            try:
                if action.action_type == "write_content":
                    if action.content_before is not None:
                        abs_path.write_text(action.content_before, encoding="utf-8")
                elif action.action_type == "create_file":
                    if abs_path.is_file():
                        abs_path.unlink()
                elif action.action_type == "move_file" and action.target_path:
                    abs_dest = self.root_path / action.target_path
                    if abs_dest.exists():
                        abs_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(abs_dest), str(abs_path))
                elif action.action_type == "delete_file":
                    if action.content_before is not None:
                        abs_path.parent.mkdir(parents=True, exist_ok=True)
                        abs_path.write_text(action.content_before, encoding="utf-8")
            except Exception:
                pass
        self.actions.clear()
        self.committed = False

    def _commit(self) -> None:
        """Save the transaction record to the journal storage."""
        record = TransactionRecord(
            tx_id=self.tx_id,
            timestamp=self.timestamp,
            command=self.command,
            description=self.description,
            actions=self.actions,
            reverted=False,
        )
        self.journal._save_transaction(record)
        self.committed = True


class TransactionJournal:
    """Manages transaction persistence, history querying, and undo operations."""

    def __init__(self, root_path: Path, max_transactions: int = 100) -> None:
        self.root_path = Path(root_path).resolve()
        self.max_transactions = max_transactions
        self.history_dir = self.root_path / ".vaultkeeper" / "history"

    def _ensure_history_dir(self) -> Path:
        """Ensure the history directory exists and return it."""
        self.history_dir.mkdir(parents=True, exist_ok=True)
        return self.history_dir

    def _get_tx_file(self, tx_id: str) -> Path:
        """Return the expected gzip path for a given transaction ID."""
        return self.history_dir / f"{tx_id}.json.gz"

    def _save_transaction(self, record: TransactionRecord) -> None:
        """Serialize and gzip-compress a transaction record."""
        self._ensure_history_dir()
        file_path = self._get_tx_file(record.tx_id)
        data = json.dumps(record.to_dict(), indent=2, ensure_ascii=False)
        compressed = gzip.compress(data.encode("utf-8"))
        file_path.write_bytes(compressed)
        self.prune_history(keep=self.max_transactions)

    def begin_transaction(self, command: str, description: str = "") -> TransactionContext:
        """Create and return a new atomic transaction context."""
        return TransactionContext(self, command=command, description=description)

    def list_transactions(self, limit: int = 20) -> List[TransactionRecord]:
        """List historical transactions sorted newest first."""
        if not self.history_dir.is_dir():
            return []

        files = sorted(self.history_dir.glob("*.json.gz"), reverse=True)
        records: List[TransactionRecord] = []
        for file in files:
            record = self._load_record_file(file)
            if record:
                records.append(record)
        records.sort(key=lambda r: (r.timestamp, r.tx_id), reverse=True)
        return records[:limit]

    def _load_record_file(self, path: Path) -> Optional[TransactionRecord]:
        """Load and deserialize a single transaction file."""
        try:
            decompressed = gzip.decompress(path.read_bytes()).decode("utf-8")
            data = json.loads(decompressed)
            return TransactionRecord.from_dict(data)
        except Exception:
            return None

    def get_transaction(self, tx_id: str) -> Optional[TransactionRecord]:
        """Retrieve a specific transaction by ID."""
        path = self._get_tx_file(tx_id)
        if not path.is_file():
            return None
        return self._load_record_file(path)

    def undo(self, tx_id: Optional[str] = None, dry_run: bool = False) -> UndoResult:
        """Revert a transaction and restore filesystem/content state."""
        if tx_id:
            record = self.get_transaction(tx_id)
            if not record:
                raise UndoError(f"Transaction '{tx_id}' not found in history.")
        else:
            candidates = [r for r in self.list_transactions(limit=100) if not r.reverted]
            if not candidates:
                return UndoResult(
                    tx_id="",
                    success=False,
                    reverted_actions=0,
                    message="No reversible transactions found in history.",
                )
            record = candidates[0]

        if record.reverted:
            raise UndoError(f"Transaction '{record.tx_id}' has already been reverted.")

        # Pre-flight check: verify that no files were modified after this transaction
        for idx, action in enumerate(record.actions):
            abs_p = self.root_path / action.path
            is_last_action_for_path = not any(a.path == action.path for a in record.actions[idx + 1 :])

            if action.action_type == "write_content":
                if not abs_p.is_file():
                    raise UndoConflictError(f"Target file '{action.path}' does not exist for undo verification.")
                if is_last_action_for_path:
                    current_hash = compute_content_hash(abs_p.read_text(encoding="utf-8"))
                    if action.hash_after and current_hash != action.hash_after:
                        raise UndoConflictError(
                            f"File '{action.path}' was modified after transaction {record.tx_id} "
                            f"(hash mismatch). Aborting undo to protect recent changes."
                        )
            elif action.action_type == "create_file":
                if abs_p.is_file() and is_last_action_for_path:
                    current_hash = compute_content_hash(abs_p.read_text(encoding="utf-8"))
                    if action.hash_after and current_hash != action.hash_after:
                        raise UndoConflictError(
                            f"Created file '{action.path}' was modified after transaction {record.tx_id}."
                        )
            elif action.action_type == "move_file" and action.target_path:
                abs_target = self.root_path / action.target_path
                if not abs_target.exists():
                    raise UndoConflictError(
                        f"Moved file '{action.target_path}' is missing. Cannot undo move to '{action.path}'."
                    )
                # If a subsequent action in this transaction created or wrote to abs_p, it will be undone first
                created_by_tx = any(
                    a.path == action.path and a.action_type in ("create_file", "write_content")
                    for a in record.actions[idx + 1 :]
                )
                if abs_p.exists() and not created_by_tx:
                    raise UndoConflictError(f"Original location '{action.path}' is already occupied. Cannot undo move.")

        affected_files: List[str] = [a.path for a in record.actions]

        if dry_run:
            return UndoResult(
                tx_id=record.tx_id,
                success=True,
                reverted_actions=len(record.actions),
                message=f"[DRY-RUN] Transaction {record.tx_id} ({record.command}) can be safely reverted.",
                affected_files=affected_files,
            )

        # Apply rollback in reverse order
        reverted_count = 0
        for action in reversed(record.actions):
            abs_p = self.root_path / action.path
            if action.action_type == "write_content":
                if action.content_before is not None:
                    abs_p.write_text(action.content_before, encoding="utf-8")
                    reverted_count += 1
            elif action.action_type == "create_file":
                if abs_p.is_file():
                    abs_p.unlink()
                    reverted_count += 1
            elif action.action_type == "move_file" and action.target_path:
                abs_target = self.root_path / action.target_path
                if abs_target.exists():
                    abs_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(abs_target), str(abs_p))
                    reverted_count += 1
            elif action.action_type == "delete_file":
                if action.content_before is not None:
                    abs_p.parent.mkdir(parents=True, exist_ok=True)
                    abs_p.write_text(action.content_before, encoding="utf-8")
                    reverted_count += 1

        # Mark record as reverted and re-save
        record.reverted = True
        record.reverted_at = datetime.now(timezone.utc).isoformat()
        self._save_transaction(record)

        return UndoResult(
            tx_id=record.tx_id,
            success=True,
            reverted_actions=reverted_count,
            message=f"Successfully reverted transaction {record.tx_id} ({record.command}).",
            affected_files=affected_files,
        )

    def prune_history(self, keep: int = 100) -> int:
        """Prune old transaction records, keeping only the most recent N records."""
        if not self.history_dir.is_dir():
            return 0

        files = sorted(self.history_dir.glob("*.json.gz"), reverse=True)
        if len(files) <= keep:
            return 0

        to_delete = files[keep:]
        deleted_count = 0
        for f in to_delete:
            try:
                f.unlink()
                deleted_count += 1
            except Exception:
                pass
        return deleted_count
