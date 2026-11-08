"""Johnny.Decimal hierarchical map generator and Master MOC (00_Vault_Map.md)."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..models import AreaSummary, VaultConfig, VaultMapReport
from ..utils.helpers import format_bytes
from .indices import IndexManager, is_index_file


class VaultMapEngine:
    """Generates high-level Johnny.Decimal area telemetry and master vault maps."""

    def __init__(self, config: VaultConfig) -> None:
        self.config = config
        self.index_manager = IndexManager(config)

    def generate_report(self) -> VaultMapReport:
        """Scan Johnny.Decimal areas and aggregate note, attachment, and index metrics."""
        areas: List[AreaSummary] = []
        total_notes = 0
        total_attachments = 0
        total_bytes = 0

        # Scan first-level Johnny.Decimal categories
        subdirs: List[Path] = sorted(
            [
                d
                for d in self.config.root_path.iterdir()
                if d.is_dir() and d.name not in self.config.ignored_folders and not d.name.startswith(".")
            ],
            key=lambda p: p.name,
        )

        for area_dir in subdirs:
            area_notes = 0
            area_attachments = 0
            area_bytes = 0

            # Scan recursively inside the area
            for f in area_dir.rglob("*"):
                if not f.is_file():
                    continue
                # Skip ignored folders in path
                if any(part in self.config.ignored_folders or part.startswith(".") for part in f.parts):
                    continue

                try:
                    size = f.stat().st_size
                except OSError:
                    size = 0

                area_bytes += size

                if f.suffix.lower() == ".md":
                    if not is_index_file(f, self.config):
                        area_notes += 1
                else:
                    area_attachments += 1

            idx_path = self.index_manager.get_index_path(area_dir)
            has_index = idx_path.is_file()

            areas.append(
                AreaSummary(
                    area_name=area_dir.name,
                    path=area_dir,
                    notes_count=area_notes,
                    attachments_count=area_attachments,
                    total_bytes=area_bytes,
                    has_index=has_index,
                    index_path=idx_path if has_index else None,
                )
            )

            total_notes += area_notes
            total_attachments += area_attachments
            total_bytes += area_bytes

        return VaultMapReport(
            vault_root=self.config.root_path,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_notes=total_notes,
            total_attachments=total_attachments,
            total_bytes=total_bytes,
            areas=areas,
        )

    def render_markdown_map(self, report: VaultMapReport) -> str:
        """Generate Master MOC Markdown text suitable for 00_Vault_Map.md."""
        table_rows: List[str] = []
        table_rows.append("| Area / Categoria | Note | Allegati | Dimensione | Indice MOC |")
        table_rows.append("| :--- | :--- | :--- | :--- | :--- |")

        for a in report.areas:
            idx_display = f"[[{a.index_path.stem}]]" if a.has_index and a.index_path else "Assente"
            row = (
                f"| `{a.area_name}/` "
                f"| {a.notes_count} "
                f"| {a.attachments_count} "
                f"| {format_bytes(a.total_bytes)} "
                f"| {idx_display} |"
            )
            table_rows.append(row)

        table_md = "\n".join(table_rows)

        content = f"""---
{self.config.type_field}: Indice
tags:
  - tipo/indice
---

# Mappa Strutturale del Vault (Johnny.Decimal)

> **Telemetria Generale:**
> - Totale Note Attive: **{report.total_notes}**
> - Totale Allegati: **{report.total_attachments}**
> - Dimensione Archiviazione: **{format_bytes(report.total_bytes)}**

## Aree Johnny.Decimal

{table_md}
"""
        return content

    def write_map_file(
        self,
        output_path: Optional[Path] = None,
        report: Optional[VaultMapReport] = None,
    ) -> Path:
        """Render and persist master vault map file."""
        if report is None:
            report = self.generate_report()

        content = self.render_markdown_map(report)
        dest = output_path.resolve() if output_path else self.config.root_path / "00_Vault_Map.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        return dest
