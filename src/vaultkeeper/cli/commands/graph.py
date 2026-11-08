"""Implementation of 'vk graph-health' command."""

import logging
from argparse import Namespace

from ...exceptions import VaultKeeperError
from ...utils.formatters import format_output
from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1


def handle_graph_health(args: Namespace, logger: logging.Logger) -> int:
    """Execute non-punitive topological graph analysis."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    fmt = getattr(args, "format", "md")

    try:
        report = v.graph_health()
    except VaultKeeperError as exc:
        logger.error("Graph telemetry failed: %s", exc)
        return EXIT_ERROR

    if fmt == "md":
        lines = [
            "# Diagnostica Topologica del Grafo Concettuale",
            "",
            "> [!NOTE] Diagnostica Non-Punitiva",
            "> I valori riportati hanno scopo puramente informativo ed esplorativo.",
            "> Nessuna penalita' viene applicata al Vault Health Score di audit.",
            "",
            f"- **Totale Nodi (Note):** {report.total_nodes}",
            f"- **Totale Archi (Collegamenti):** {report.total_edges}",
            f"- **Note Isolate (True Orphans):** {len(report.true_orphans)}",
            f"- **Vicoli Ciechi (Dead-Ends):** {len(report.dead_ends)}",
            f"- **Componenti Disconnesse (<=3 note):** {len(report.disconnected_components)}",
            "",
            "## Top 10 Note Piu' Collegate (Hub)",
            "",
        ]

        if report.top_hubs:
            hub_rows = [
                {
                    "Nota": f"[[{h.stem}]]",
                    "Backlink in Ingresso": h.in_degree,
                    "Link in Uscita": h.out_degree,
                }
                for h in report.top_hubs
            ]
            lines.append(
                format_output(
                    hub_rows,
                    format="md",
                    headers=["Nota", "Backlink in Ingresso", "Link in Uscita"],
                )
            )
        else:
            lines.append("*(Nessun hub rilevato con collegamenti in ingresso)*")

        lines.extend(["", "## Note Isolate (Senza link ne' indice)", ""])
        if report.true_orphans:
            for o in report.true_orphans:
                lines.append(f"- [[{o}]]")
        else:
            lines.append("*(Nessuna nota totalmente orfana rilevata)*")

        lines.extend(["", "## Vicoli Ciechi (Zero link uscenti)", ""])
        if report.dead_ends:
            for de in report.dead_ends[:20]:
                lines.append(f"- [[{de}]]")
            if len(report.dead_ends) > 20:
                lines.append(f"*... e altri {len(report.dead_ends) - 20} vicoli ciechi*")
        else:
            lines.append("*(Nessun vicolo cieco rilevato)*")

        print("\n".join(lines))
    else:
        rendered = format_output(report.to_dict(), format=fmt)
        print(rendered)

    return EXIT_SUCCESS
