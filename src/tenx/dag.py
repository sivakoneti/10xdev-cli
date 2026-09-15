"""DAG dependency solver, cycle detection, and wave partitioning for spec tickets.

Zero external dependencies (Python standard library only, CON-002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .artifacts import Artifact


class CyclicDependencyError(Exception):
    """Raised when ticket dependencies contain a cycle."""
    pass


class MissingDependencyError(Exception):
    """Raised when a ticket depends on an unknown ticket within the spec."""
    pass


@dataclass
class TicketNode:
    id: str
    title: str
    status: str
    depends_on: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpecDAG:
    spec_id: str
    nodes: Dict[str, TicketNode] = field(default_factory=dict)
    waves: List[List[str]] = field(default_factory=list)

    def is_ticket_ready(self, ticket_id: str) -> bool:
        """A ticket is ready if it is not done and all its dependencies are done."""
        node = self.nodes.get(ticket_id)
        if not node or node.status == "done":
            return False
        for dep in node.depends_on:
            dep_node = self.nodes.get(dep)
            if not dep_node or dep_node.status != "done":
                return False
        return True

    def get_ready_tickets(self) -> List[str]:
        """Return list of ticket IDs ready to execute right now."""
        return [tid for tid in self.nodes if self.is_ticket_ready(tid)]


def build_spec_dag(spec: Artifact) -> SpecDAG:
    """Construct a directed acyclic graph from a spec's ticket definitions.
    
    Parses `depends_on` from ticket frontmatter.
    Validates that:
    1. All dependencies exist in the same spec.
    2. There are no self-dependencies or cycles.
    Partitions tickets into topological execution waves.
    """
    nodes: Dict[str, TicketNode] = {}
    tickets = spec.tickets or []

    for t in tickets:
        tid = t.get("id")
        if not tid:
            continue
        deps = t.get("depends_on", [])
        if isinstance(deps, str):
            deps = [d.strip() for d in deps.split(",") if d.strip()]
        elif not isinstance(deps, list):
            deps = []
        nodes[tid] = TicketNode(
            id=tid,
            title=str(t.get("title", "")),
            status=str(t.get("status", "todo")),
            depends_on=list(deps),
            meta=t,
        )

    # 1. Validate all dependencies exist within the spec
    for tid, node in nodes.items():
        for dep in node.depends_on:
            if dep == tid:
                raise CyclicDependencyError(f"Ticket {tid} depends on itself.")
            if dep not in nodes:
                raise MissingDependencyError(f"Ticket {tid} depends on unknown ticket '{dep}' in spec {spec.id}.")

    # 2. Detect cycles using Tarjan's / DFS cycle detection
    _detect_cycles(nodes)

    # 3. Compute topological waves
    waves = _compute_waves(nodes)

    return SpecDAG(spec_id=spec.id, nodes=nodes, waves=waves)


def _detect_cycles(nodes: Dict[str, TicketNode]) -> None:
    visited: Dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = visited

    def dfs(node_id: str, path: List[str]) -> None:
        visited[node_id] = 1
        path.append(node_id)
        for dep in nodes[node_id].depends_on:
            state = visited.get(dep, 0)
            if state == 1:
                # Found cycle
                cycle_idx = path.index(dep)
                cycle_str = " -> ".join(path[cycle_idx:] + [dep])
                raise CyclicDependencyError(f"Cyclic dependency detected: {cycle_str}")
            elif state == 0:
                dfs(dep, path)
        visited[node_id] = 2
        path.pop()

    for nid in nodes:
        if visited.get(nid, 0) == 0:
            dfs(nid, [])


def _compute_waves(nodes: Dict[str, TicketNode]) -> List[List[str]]:
    """Compute topological execution waves (Kahn-style layer assignment).
    
    Wave 0: Tickets with no dependencies.
    Wave N: Tickets whose dependencies are all in waves < N.
    """
    if not nodes:
        return []

    # Map node to the wave index it belongs to
    wave_map: Dict[str, int] = {}

    def get_wave(node_id: str) -> int:
        if node_id in wave_map:
            return wave_map[node_id]
        node = nodes[node_id]
        if not node.depends_on:
            wave_map[node_id] = 0
            return 0
        w = max(get_wave(dep) for dep in node.depends_on) + 1
        wave_map[node_id] = w
        return w

    for nid in nodes:
        get_wave(nid)

    max_wave = max(wave_map.values()) if wave_map else -1
    waves: List[List[str]] = [[] for _ in range(max_wave + 1)]
    for nid, w in wave_map.items():
        waves[w].append(nid)

    # Sort ticket IDs within each wave for deterministic execution
    for w in waves:
        w.sort()

    return waves
