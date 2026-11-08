"""Journal models representing transactions, reversible actions, and undo operations."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActionRecord:
    """Represents an atomic reversible filesystem or content modification."""

    action_type: str  # "write_content", "move_file", "delete_file", "create_file"
    path: str
    target_path: Optional[str] = None
    content_before: Optional[str] = None
    content_after: Optional[str] = None
    hash_before: Optional[str] = None
    hash_after: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a JSON-serializable dictionary."""
        return {
            "action_type": self.action_type,
            "path": self.path,
            "target_path": self.target_path,
            "content_before": self.content_before,
            "content_after": self.content_after,
            "hash_before": self.hash_before,
            "hash_after": self.hash_after,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRecord":
        """Reconstruct record from a dictionary."""
        return cls(
            action_type=data["action_type"],
            path=data["path"],
            target_path=data.get("target_path"),
            content_before=data.get("content_before"),
            content_after=data.get("content_after"),
            hash_before=data.get("hash_before"),
            hash_after=data.get("hash_after"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TransactionRecord:
    """Represents a logged atomic transaction composed of one or more actions."""

    tx_id: str
    timestamp: str
    command: str
    description: str
    actions: List[ActionRecord] = field(default_factory=list)
    reverted: bool = False
    reverted_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to a JSON-serializable dictionary."""
        return {
            "tx_id": self.tx_id,
            "timestamp": self.timestamp,
            "command": self.command,
            "description": self.description,
            "actions": [a.to_dict() for a in self.actions],
            "reverted": self.reverted,
            "reverted_at": self.reverted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionRecord":
        """Reconstruct transaction from a dictionary."""
        return cls(
            tx_id=data["tx_id"],
            timestamp=data["timestamp"],
            command=data["command"],
            description=data.get("description", ""),
            actions=[ActionRecord.from_dict(a) for a in data.get("actions", [])],
            reverted=data.get("reverted", False),
            reverted_at=data.get("reverted_at"),
        )


@dataclass(frozen=True)
class UndoResult:
    """Outcome of an undo/revert operation on a historical transaction."""

    tx_id: str
    success: bool
    reverted_actions: int
    message: str
    affected_files: List[str] = field(default_factory=list)
