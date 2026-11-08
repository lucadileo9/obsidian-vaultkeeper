"""Implementation of 'vk search' command."""

import logging
from argparse import Namespace
from pathlib import Path

from ...exceptions import SearchError, VaultKeeperError
from ...utils.formatters import format_output
from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_search(args: Namespace, logger: logging.Logger) -> int:
    """Execute semantic query and filter search across notes."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    query = getattr(args, "query", None)
    tag = getattr(args, "tag", None)
    tipo = getattr(args, "type", None)
    links_to = getattr(args, "links_to", None)
    folder = getattr(args, "folder", None)
    fmt = getattr(args, "format", "md")

    try:
        res = v.search(
            query=query,
            tag=tag,
            tipo=tipo,
            links_to=links_to,
            folder=folder,
        )
    except (SearchError, VaultKeeperError) as exc:
        logger.error("Search failed: %s", exc)
        return EXIT_ERROR

    if fmt == "md":
        if not res.items:
            print("*(Nessuna nota trovata corrispondente ai criteri specificati)*")
            return EXIT_SUCCESS

        rows = []
        for it in res.items:
            tags_str = ", ".join(f"#{t}" for t in it.tags[:3])
            rows.append(
                {
                    "Nota": f"[[{Path(it.rel_path).stem}|{it.title}]]",
                    "Percorso": it.rel_path,
                    "Tipo": it.tipo or "-",
                    "Tag": tags_str or "-",
                    "Estratto": it.snippet or "-",
                }
            )

        title = f"Risultati Ricerca ({res.total_matches} note trovate)"
        rendered = format_output(
            rows,
            format="md",
            headers=["Nota", "Percorso", "Tipo", "Tag", "Estratto"],
            title=title,
        )
        print(rendered)
    else:
        rendered = format_output(res.to_dict(), format=fmt)
        print(rendered)

    return EXIT_SUCCESS
