"""Topological graph telemetry: non-punitive analysis of orphans, dead-ends, hubs, and isolated clusters."""

from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..models import GraphHealthReport, GraphHub, VaultCatalog, VaultConfig
from .indices import is_index_file
from .links import WikilinkEngine
from .traversal import walk_vault_files


class GraphTelemetry:
    """Non-punitive topological telemetry for the vault conceptual knowledge graph."""

    def __init__(self, config: VaultConfig, catalog: Optional[VaultCatalog] = None) -> None:
        self.config = config
        self.catalog = catalog
        self.link_engine = WikilinkEngine(config)

    def analyze(self) -> GraphHealthReport:
        """Construct knowledge graph and compute topological metrics."""
        # 1. Discover all active markdown notes (excluding indices)
        all_notes: Dict[str, Path] = {}
        index_referenced_stems: Set[str] = set()

        for note_path in walk_vault_files(self.config, target_dir=self.config.root_path, extensions={".md"}):
            stem = note_path.stem
            if is_index_file(note_path, self.config):
                # Extract referenced notes from indices
                try:
                    content = note_path.read_text(encoding="utf-8")
                    links = self.link_engine.extract_links(content, note_path)
                    for _, _, clean_target, _, _, _ in links:
                        index_referenced_stems.add(Path(clean_target).stem)
                except Exception:
                    pass
                continue

            all_notes[stem] = note_path

        # 2. Build graph adjacency structures
        outgoing_edges: Dict[str, Set[str]] = defaultdict(set)
        incoming_edges: Dict[str, Set[str]] = defaultdict(set)
        total_edges = 0

        for stem, note_path in all_notes.items():
            try:
                content = note_path.read_text(encoding="utf-8")
            except Exception:
                continue

            links = self.link_engine.extract_links(content, note_path)
            for _, _, clean_target, _, _, _ in links:
                target_stem = Path(clean_target).stem
                if target_stem in all_notes and target_stem != stem:
                    if target_stem not in outgoing_edges[stem]:
                        outgoing_edges[stem].add(target_stem)
                        incoming_edges[target_stem].add(stem)
                        total_edges += 1

        # 3. Compute True Orphans (in=0, out=0, not in any 00_Indice)
        true_orphans: List[str] = []
        for stem in all_notes:
            in_deg = len(incoming_edges[stem])
            out_deg = len(outgoing_edges[stem])
            if in_deg == 0 and out_deg == 0 and stem not in index_referenced_stems:
                true_orphans.append(stem)
        true_orphans.sort()

        # 4. Compute Dead-Ends (in > 0, out == 0)
        dead_ends: List[str] = []
        for stem in all_notes:
            in_deg = len(incoming_edges[stem])
            out_deg = len(outgoing_edges[stem])
            if in_deg > 0 and out_deg == 0:
                dead_ends.append(stem)
        dead_ends.sort()

        # 5. Compute Top 10 Hubs (highest in-degree)
        hubs_list: List[GraphHub] = []
        for stem, note_path in all_notes.items():
            in_deg = len(incoming_edges[stem])
            out_deg = len(outgoing_edges[stem])
            if in_deg > 0:
                hubs_list.append(
                    GraphHub(
                        stem=stem,
                        file_path=note_path,
                        in_degree=in_deg,
                        out_degree=out_deg,
                    )
                )

        hubs_list.sort(key=lambda h: (-h.in_degree, -h.out_degree, h.stem))
        top_hubs = hubs_list[:10]

        # 6. Compute Disconnected Components (undirected graph clusters with <= 3 notes)
        undirected_adj: Dict[str, Set[str]] = defaultdict(set)
        for u, neighbors in outgoing_edges.items():
            for v in neighbors:
                undirected_adj[u].add(v)
                undirected_adj[v].add(u)

        visited: Set[str] = set()
        disconnected_components: List[List[str]] = []

        # Only evaluate connected components containing at least 2 nodes or isolated notes
        for stem in sorted(all_notes.keys()):
            if stem not in visited:
                comp: List[str] = []
                queue: deque = deque([stem])
                visited.add(stem)

                while queue:
                    curr = queue.popleft()
                    comp.append(curr)
                    for nbr in undirected_adj[curr]:
                        if nbr not in visited and nbr in all_notes:
                            visited.add(nbr)
                            queue.append(nbr)

                # Isolated cluster of 1, 2, or 3 notes
                if 1 < len(comp) <= 3:
                    comp.sort()
                    disconnected_components.append(comp)

        disconnected_components.sort(key=lambda c: (len(c), c[0] if c else ""))

        return GraphHealthReport(
            vault_root=self.config.root_path,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_nodes=len(all_notes),
            total_edges=total_edges,
            true_orphans=true_orphans,
            dead_ends=dead_ends,
            top_hubs=top_hubs,
            disconnected_components=disconnected_components,
        )
