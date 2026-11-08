"""Polymorphic output serializer supporting Markdown, JSON, YAML, and CSV formats."""

import csv
import io
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, List, Optional, Sequence, Union

import yaml


class OutputFormat(str, Enum):
    """Supported output serialization formats."""

    MD = "md"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"

    @classmethod
    def from_str(cls, val: str) -> "OutputFormat":
        """Convert string to OutputFormat case-insensitively."""
        normalized = val.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        return cls.MD


def _normalize_obj(obj: Any) -> Any:
    """Recursively normalize dataclasses and custom objects to standard Python primitives."""
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return _normalize_obj(obj.to_dict())
    if is_dataclass(obj) and not isinstance(obj, type):
        return _normalize_obj(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _normalize_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_normalize_obj(i) for i in obj]
    return obj


def render_markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Format headers and rows into a clean GitHub Flavored Markdown (GFM) table."""
    if not headers:
        return ""

    header_cols = [str(h).strip() for h in headers]
    separator_cols = [":---" for _ in headers]

    lines = [
        "| " + " | ".join(header_cols) + " |",
        "| " + " | ".join(separator_cols) + " |",
    ]

    for row in rows:
        row_cols = [str(r).replace("|", "\\|").replace("\n", " ") for r in row]
        # Pad row with empty cells if length mismatch
        if len(row_cols) < len(headers):
            row_cols.extend([""] * (len(headers) - len(row_cols)))
        lines.append("| " + " | ".join(row_cols[: len(headers)]) + " |")

    return "\n".join(lines)


def format_output(
    data: Any,
    format: Union[OutputFormat, str] = OutputFormat.MD,
    headers: Optional[List[str]] = None,
    title: Optional[str] = None,
) -> str:
    """Serialize data into the requested format (Markdown, JSON, YAML, CSV)."""
    fmt = OutputFormat.from_str(str(format)) if not isinstance(format, OutputFormat) else format
    normalized = _normalize_obj(data)

    if fmt == OutputFormat.JSON:
        return json.dumps(normalized, indent=2, ensure_ascii=False, default=str)

    if fmt == OutputFormat.YAML:
        return yaml.safe_dump(normalized, sort_keys=False, allow_unicode=True, default_flow_style=False).strip()

    if fmt == OutputFormat.CSV:
        output = io.StringIO()
        writer = csv.writer(output)

        if isinstance(normalized, list) and normalized:
            if isinstance(normalized[0], dict):
                keys = headers or list(normalized[0].keys())
                writer.writerow(keys)
                for item in normalized:
                    if isinstance(item, dict):
                        writer.writerow([str(item.get(k, "")) for k in keys])
            else:
                writer.writerow(["item"])
                for item in normalized:
                    writer.writerow([str(item)])
        elif isinstance(normalized, dict):
            writer.writerow(["property", "value"])
            for k, v in normalized.items():
                writer.writerow([str(k), str(v)])
        else:
            writer.writerow(["value"])
            writer.writerow([str(normalized)])
        return output.getvalue().strip()

    # Markdown format (Default)
    output_lines: List[str] = []
    if title:
        output_lines.append(f"## {title}\n")

    if isinstance(normalized, str):
        output_lines.append(normalized)
    elif isinstance(normalized, list):
        if not normalized:
            output_lines.append("*(Nessun elemento trovato)*")
        elif isinstance(normalized[0], dict):
            keys = headers or list(normalized[0].keys())
            rows = [[item.get(k, "") for k in keys] for item in normalized if isinstance(item, dict)]
            output_lines.append(render_markdown_table(keys, rows))
        else:
            for item in normalized:
                output_lines.append(f"- {item}")
    elif isinstance(normalized, dict):
        keys = ["Proprieta", "Valore"]
        rows = [[str(k), str(v)] for k, v in normalized.items()]
        output_lines.append(render_markdown_table(keys, rows))
    else:
        output_lines.append(str(normalized))

    return "\n".join(output_lines).strip()
