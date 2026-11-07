"""Implementation of 'vk audit' command."""

import json
import logging
from argparse import Namespace
from pathlib import Path

from ...vault import Vault

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_ISSUES_FOUND = 2


def handle_audit(args: Namespace, logger: logging.Logger) -> int:
    """Execute unified multi-phase audit and format results."""
    try:
        v = Vault(root_path=getattr(args, "root", None), config_file=getattr(args, "config", None))
    except Exception as exc:
        logger.error("Failed to initialize vault: %s", exc)
        return EXIT_ERROR

    steps = [int(args.step)] if getattr(args, "step", None) else [1, 2, 3, 4, 5]
    logger.info("Executing VaultKeeper audit for: %s", v.root)
    logger.info("Phases to execute: %s", ", ".join(str(s) for s in steps))

    report = v.audit(phases=steps)

    logger.info("-" * 60)
    for phase in report.phases:
        status_text = "OK" if phase.is_clean() else f"{len(phase.issues)} ISSUES"
        logger.info("[Phase %d] %s: %s (%d warnings)", phase.phase_id, phase.title, status_text, len(phase.warnings))
        for issue in phase.issues[:10]:
            logger.warning("  - %s", issue)
        if len(phase.issues) > 10:
            logger.warning("  ... and %d more issues", len(phase.issues) - 10)

    logger.info("-" * 60)
    logger.info("Total Issues: %d", report.total_issues)
    logger.info("Vault Health Score: %.2f / 100.0", report.health_score)

    # Export JSON if requested
    if getattr(args, "json", None):
        out_json = Path(args.json).resolve()
        out_json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        logger.info("Saved JSON audit report to: %s", out_json)

    # Export Markdown if requested
    if getattr(args, "report_md", None):
        out_md = Path(args.report_md).resolve()
        md_lines = [
            f"# Audit Report - {report.vault_root.name}",
            f"**Timestamp:** {report.timestamp}",
            f"**Health Score:** {report.health_score:.2f} / 100.0",
            f"**Total Issues:** {report.total_issues}",
            "",
        ]
        for phase in report.phases:
            md_lines.append(f"## Phase {phase.phase_id}: {phase.title}")
            md_lines.append(f"- Issues: {len(phase.issues)}")
            md_lines.append(f"- Warnings: {len(phase.warnings)}")
            if phase.issues:
                md_lines.append("")
                md_lines.append("### Issues")
                for iss in phase.issues:
                    md_lines.append(f"- {iss}")
            md_lines.append("")

        out_md.write_text("\n".join(md_lines), encoding="utf-8")
        logger.info("Saved Markdown audit report to: %s", out_md)

    return EXIT_SUCCESS if report.is_clean() else EXIT_ISSUES_FOUND
