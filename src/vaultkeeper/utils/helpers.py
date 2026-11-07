"""Generic helper utilities for text formatting, byte humanization and hashing."""

import hashlib
from pathlib import Path


def format_bytes(size_bytes: int) -> str:
    """Format an integer byte count into a human-readable string.

    Examples:
        512 -> "512 B"
        2048 -> "2.00 KB"
        10485760 -> "10.00 MB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ["KB", "MB", "GB", "TB"]
    val = float(size_bytes)
    for unit in units:
        val /= 1024.0
        if val < 1024.0 or unit == units[-1]:
            return f"{val:.2f} {unit}"
    return f"{size_bytes} B"


def truncate_text(text: str, max_chars: int = 250) -> str:
    """Truncate a string cleanly at word boundary up to max_chars."""
    clean = " ".join(text.split())
    if len(clean) <= max_chars:
        return clean
    truncated = clean[:max_chars].rsplit(" ", 1)[0]
    return f"{truncated}..."


def compute_file_hash(path: Path, block_size: int = 65536) -> str:
    """Compute the SHA256 hex digest of a file efficiently."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
