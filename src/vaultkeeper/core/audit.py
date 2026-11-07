"""Unified 5-phase audit diagnostics engine with health score calculation."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from ..models import AuditReport, PhaseResult, VaultCatalog, VaultConfig
from .attachments import find_heavy_files, find_orphan_attachments
from .frontmatter import (
    extract_inline_tags,
    parse_taxonomy_file,
    read_note,
)
from .links import find_stem_collisions, scan_broken_links
from .naming import normalize_name
from .traversal import build_vault_catalog, walk_vault_files


def run_phase_1_storage(config: VaultConfig, catalog: VaultCatalog) -> PhaseResult:
    """Phase 1: Storage and filesystem diagnostics."""
    issues: List[str] = []
    warnings: List[str] = []
    heavy_files_list: List[str] = []

    for file_path in walk_vault_files(config, target_dir=config.root_path, filter_extensions=False):
        # 1. Path length check
        path_len = len(str(file_path))
        if path_len > config.max_path_length:
            issues.append(
                f"Path length {path_len} exceeds limit of {config.max_path_length}: {file_path.name}"
            )

        # 2. Allowed extensions check
        if config.allowed_extensions and file_path.suffix.lower() not in config.allowed_extensions:
            warnings.append(
                f"File extension {file_path.suffix} is not in allowed_extensions: {file_path.name}"
            )

    # 3. Heavy files check
    heavy_files = find_heavy_files(catalog, config)
    for hf, size in heavy_files:
        size_mb = size / (1024 * 1024)
        msg = f"Heavy file: {hf.name} ({size_mb:.1f} MB >= {config.heavy_file_threshold_mb} MB)"
        warnings.append(msg)
        heavy_files_list.append(msg)

    metrics = {
        "total_files": catalog.total_files,
        "total_size_bytes": catalog.total_size_bytes,
        "heavy_files_count": len(heavy_files),
    }

    return PhaseResult(
        phase_id=1,
        title="Storage & Filesystem",
        issues=issues,
        warnings=warnings,
        metrics=metrics,
    )


def run_phase_2_naming(config: VaultConfig, catalog: VaultCatalog) -> PhaseResult:
    """Phase 2: Naming convention diagnostics."""
    issues: List[str] = []
    warnings: List[str] = []

    for file_path in walk_vault_files(config, target_dir=config.root_path, filter_extensions=False):
        expected_name = normalize_name(file_path.name, config, is_directory=False)
        if file_path.name != expected_name:
            issues.append(f"Naming violation: '{file_path.name}' -> expected '{expected_name}'")

    metrics = {
        "naming_violations": len(issues),
        "naming_style": config.naming_style,
    }

    return PhaseResult(
        phase_id=2,
        title="Naming Conventions",
        issues=issues,
        warnings=warnings,
        metrics=metrics,
    )


def run_phase_3_frontmatter(config: VaultConfig, catalog: VaultCatalog) -> PhaseResult:
    """Phase 3: Frontmatter and type taxonomy diagnostics."""
    issues: List[str] = []
    warnings: List[str] = []
    type_counts: Dict[str, int] = {}

    for note_path in walk_vault_files(config, target_dir=config.root_path, extensions={".md"}):
        note = read_note(note_path, config.root_path, type_field=config.type_field)
        rel_str = note.rel_path.as_posix()

        if note.frontmatter is None:
            issues.append(f"Missing YAML frontmatter: {rel_str}")
            continue

        fm = note.frontmatter

        # Check required fields
        for field in config.required_frontmatter_fields:
            if field not in fm.metadata or fm.metadata[field] is None:
                issues.append(f"Missing required field '{field}': {rel_str}")

        # Check allowed tipo
        if not fm.tipo:
            issues.append(f"Empty or missing '{config.type_field}' field: {rel_str}")
        elif not fm.is_valid_type(config.allowed_types):
            issues.append(
                f"Invalid {config.type_field} '{fm.tipo}' (allowed: {config.allowed_types}): {rel_str}"
            )
        else:
            type_counts[fm.tipo] = type_counts.get(fm.tipo, 0) + 1

    metrics = {
        "notes_audited": len(list(catalog.notes_by_stem.keys())),
        "type_distribution": type_counts,
    }

    return PhaseResult(
        phase_id=3,
        title="Frontmatter & Types",
        issues=issues,
        warnings=warnings,
        metrics=metrics,
    )


def run_phase_4_tags(config: VaultConfig, catalog: VaultCatalog) -> PhaseResult:
    """Phase 4: Tag taxonomy compliance diagnostics."""
    issues: List[str] = []
    warnings: List[str] = []
    registered_tags: Set[str] = set()

    taxonomy_path = None
    if config.taxonomy_file:
        cand = config.root_path / config.taxonomy_file
        if cand.is_file():
            taxonomy_path = cand
        else:
            # Search taxonomy file anywhere in vault
            for f in walk_vault_files(config, target_dir=config.root_path, extensions={".md"}):
                if f.name == config.taxonomy_file:
                    taxonomy_path = f
                    break

    if taxonomy_path:
        registered_tags = parse_taxonomy_file(taxonomy_path)
    else:
        warnings.append(f"Taxonomy file not found: {config.taxonomy_file}")

    all_used_tags: Set[str] = set()
    unregistered_found: Set[str] = set()

    for note_path in walk_vault_files(config, target_dir=config.root_path, extensions={".md"}):
        note = read_note(note_path, config.root_path, type_field=config.type_field)
        note_tags: Set[str] = set()

        if note.frontmatter and note.frontmatter.tags:
            note_tags.update(note.frontmatter.tags)

        # Inline tags
        inline_tags = extract_inline_tags(
            note.body,
            protect_c=config.protect_c_directives,
            protect_hex=config.protect_hex_colors,
        )
        note_tags.update(inline_tags)
        all_used_tags.update(note_tags)

        if registered_tags and config.strict_taxonomy:
            for tag in note_tags:
                if tag not in registered_tags:
                    unregistered_found.add(tag)
                    issues.append(f"Unregistered tag '#{tag}' in note: {note.rel_path.as_posix()}")

    metrics = {
        "registered_taxonomy_tags": len(registered_tags),
        "total_unique_tags_used": len(all_used_tags),
        "unregistered_tags_count": len(unregistered_found),
    }

    return PhaseResult(
        phase_id=4,
        title="Tag Taxonomy",
        issues=issues,
        warnings=warnings,
        metrics=metrics,
    )


def run_phase_5_links(config: VaultConfig, catalog: VaultCatalog) -> PhaseResult:
    """Phase 5: Link integrity and attachment diagnostics."""
    issues: List[str] = []
    warnings: List[str] = []

    # 1. Broken links & broken embeds
    broken = scan_broken_links(catalog, config)
    for b in broken:
        link_kind = "media embed" if b.is_media_embed() else "wikilink"
        issues.append(
            f"Broken {link_kind}: [[{b.clean_target}]] in {b.source_file.name}:{b.line_number}"
        )

    # 2. Stem collisions
    collisions = find_stem_collisions(catalog)
    for stem, paths in collisions.items():
        rel_paths_str = ", ".join(p.name for p in paths)
        warnings.append(f"Stem collision for '{stem}': found in {len(paths)} locations ({rel_paths_str})")

    # 3. Orphan attachments
    orphans = find_orphan_attachments(catalog, config)
    for o in orphans:
        warnings.append(f"Orphan attachment: {o.rel_path.as_posix()} ({o.size_bytes} bytes)")

    metrics = {
        "broken_links_count": len(broken),
        "stem_collisions_count": len(collisions),
        "orphan_attachments_count": len(orphans),
    }

    return PhaseResult(
        phase_id=5,
        title="Links & Attachments",
        issues=issues,
        warnings=warnings,
        metrics=metrics,
    )


def compute_health_score(phases: List[PhaseResult]) -> float:
    """Compute overall vault health score (0.0 to 100.0)."""
    score = 100.0

    for phase in phases:
        if phase.phase_id == 1:
            # Storage issues: -2.0 per path issue, -1.0 per unallowed ext
            score -= len(phase.issues) * 2.0
        elif phase.phase_id == 2:
            # Naming violations: -0.5 each
            score -= len(phase.issues) * 0.5
        elif phase.phase_id == 3:
            # Frontmatter violations: -1.5 each
            score -= len(phase.issues) * 1.5
        elif phase.phase_id == 4:
            # Tag violations: -0.5 each
            score -= len(phase.issues) * 0.5
        elif phase.phase_id == 5:
            # Broken links: -3.0 each
            score -= len(phase.issues) * 3.0

    return max(0.0, min(100.0, score))


def run_audit(
    config: VaultConfig,
    phases_to_run: Optional[List[int]] = None,
) -> AuditReport:
    """Execute unified multi-phase vault audit."""
    catalog = build_vault_catalog(config)
    selected_phases = phases_to_run or [1, 2, 3, 4, 5]
    results: List[PhaseResult] = []

    if 1 in selected_phases:
        results.append(run_phase_1_storage(config, catalog))
    if 2 in selected_phases:
        results.append(run_phase_2_naming(config, catalog))
    if 3 in selected_phases:
        results.append(run_phase_3_frontmatter(config, catalog))
    if 4 in selected_phases:
        results.append(run_phase_4_tags(config, catalog))
    if 5 in selected_phases:
        results.append(run_phase_5_links(config, catalog))

    total_issues = sum(len(p.issues) for p in results)
    score = compute_health_score(results)
    timestamp = datetime.now(timezone.utc).isoformat()

    return AuditReport(
        vault_root=config.root_path,
        timestamp=timestamp,
        phases=results,
        total_issues=total_issues,
        health_score=score,
    )
