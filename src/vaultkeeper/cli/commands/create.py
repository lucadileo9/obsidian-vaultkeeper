"""Implementation of 'vk create' command."""

import logging
from argparse import Namespace
from typing import List, Optional

from ...exceptions import CreationError, TaxonomyError, TemplateError, VaultKeeperError
from ...utils.formatters import format_output, render_markdown_table
from ...vault import Vault
from ..constants import EXIT_ERROR, EXIT_SUCCESS


def handle_create(args: Namespace, logger: logging.Logger) -> int:
    """Create a standardized note using templates, strict validation, and folder auto-routing."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    title = getattr(args, "title")
    tipo = getattr(args, "tipo")
    folder = getattr(args, "folder", None)
    raw_tags = getattr(args, "tags", None)
    template = getattr(args, "template", None)
    dry_run = getattr(args, "dry_run", False)
    fmt = getattr(args, "format", "md")

    tags_list: Optional[List[str]] = None
    if raw_tags:
        tags_list = [t.strip().lstrip("#") for t in raw_tags.split(",") if t.strip()]

    try:
        res = v.create(
            title=title,
            tipo=tipo,
            folder=folder,
            tags=tags_list,
            template=template,
            dry_run=dry_run,
        )
    except (CreationError, TaxonomyError, TemplateError, VaultKeeperError) as exc:
        logger.error("Creation failed: %s", exc)
        return EXIT_ERROR
    except Exception as exc:
        logger.error("Unexpected error during note creation: %s", exc)
        return EXIT_ERROR

    if fmt in ("json", "yaml", "csv"):
        print(format_output(res, format=fmt))
        return EXIT_SUCCESS

    # Markdown format
    idx_info = f"Aggiornato (`{res.index_path.name}`)" if res.index_updated and res.index_path else "Invariato"
    status_info = (
        "[DRY-RUN] Nessun file scritto"
        if res.dry_run
        else f"Transazione `{res.tx_id or 'N/A'}` (annullabile con `vk undo`)"
    )
    tags_str = ", ".join(f"`{t}`" for t in res.tags) if res.tags else "(Nessuno)"

    table = render_markdown_table(
        headers=["Proprietà", "Valore"],
        rows=[
            ["Percorso", f"`{res.rel_path.as_posix()}`"],
            ["Stem", f"[[{res.stem}]]"],
            ["Tipo", f"`{res.tipo}`"],
            ["Tag", tags_str],
            ["Template", f"`{res.template_used or 'Predefinito Standard'}`"],
            ["Indice Cartella", idx_info],
            ["Stato", status_info],
        ],
    )

    prefix = "[DRY-RUN] " if res.dry_run else ""
    print(f"# {prefix}Nuova Nota: {res.title}\n\n{table}")
    return EXIT_SUCCESS
