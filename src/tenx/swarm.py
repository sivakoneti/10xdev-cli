"""Swarm coordinator engine: automated DAG wave scheduling and parallel subagent dispatch.

Zero runtime dependencies (Python standard library only, CON-002).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifacts import Harness, load_harness
from .dag import SpecDAG, build_spec_dag
from .dispatch import dispatch_ticket
from .reconcile import ReconcileResult, reconcile_subagent_ticket


@dataclass
class SwarmTicketPlan:
    ticket_id: str
    wave: int
    status: str
    depends_on: List[str]
    ready: bool
    agent: Optional[str] = None
    model: Optional[str] = None


@dataclass
class SwarmPlan:
    spec_id: str
    total_tickets: int
    waves: List[List[str]]
    tickets: List[SwarmTicketPlan]
    ready_tickets: List[str]
    completed_tickets: List[str]
    blocked_tickets: List[str]


def plan_spec_swarm(
    project_root: Path,
    spec_id: str,
    agent: Optional[str] = None,
    model: Optional[str] = None,
) -> SwarmPlan:
    """Generate the DAG execution plan and wave partition for a spec."""
    harness = load_harness(project_root)
    spec = harness.get(spec_id)
    if not spec:
        raise ValueError(f"Spec {spec_id} not found.")

    dag = build_spec_dag(spec)
    ticket_plans: List[SwarmTicketPlan] = []
    ready: List[str] = []
    completed: List[str] = []
    blocked: List[str] = []

    # Map ticket to wave index
    ticket_wave: Dict[str, int] = {}
    for w_idx, wave in enumerate(dag.waves):
        for tid in wave:
            ticket_wave[tid] = w_idx

    for tid, node in dag.nodes.items():
        is_ready = dag.is_ticket_ready(tid)
        if node.status == "done":
            completed.append(tid)
        elif is_ready:
            ready.append(tid)
        else:
            blocked.append(tid)

        ticket_plans.append(
            SwarmTicketPlan(
                ticket_id=tid,
                wave=ticket_wave.get(tid, 0),
                status=node.status,
                depends_on=node.depends_on,
                ready=is_ready,
                agent=agent or "omp",
                model=model,
            )
        )

    return SwarmPlan(
        spec_id=spec_id,
        total_tickets=len(dag.nodes),
        waves=dag.waves,
        tickets=ticket_plans,
        ready_tickets=ready,
        completed_tickets=completed,
        blocked_tickets=blocked,
    )


@dataclass
class SwarmExecutionResult:
    spec_id: str
    status: str  # "completed", "partial", "error", "no_work"
    executed_waves: int
    dispatched_tickets: List[str] = field(default_factory=list)
    reconciled_tickets: List[str] = field(default_factory=list)
    failed_tickets: List[str] = field(default_factory=list)
    details: str = ""


def execute_spec_swarm(
    project_root: Path,
    spec_id: str,
    agent: Optional[str] = None,
    model: Optional[str] = None,
    visual: bool = False,
    multiplexer: Optional[str] = None,
    max_parallel: int = 4,
    dry_run: bool = False,
    auto_reconcile: bool = False,
) -> SwarmExecutionResult:
    """Execute ready tickets across DAG waves.
    
    If dry_run=True, plans execution without spawning workers.
    If auto_reconcile=True, attempts reconcile_subagent_ticket for completed work.
    """
    plan = plan_spec_swarm(project_root, spec_id, agent=agent, model=model)

    if not plan.ready_tickets:
        if len(plan.completed_tickets) == plan.total_tickets:
            return SwarmExecutionResult(
                spec_id=spec_id,
                status="completed",
                executed_waves=len(plan.waves),
                details="All tickets in spec DAG are already completed.",
            )
        return SwarmExecutionResult(
            spec_id=spec_id,
            status="no_work",
            executed_waves=0,
            details=f"No tickets ready to execute (waiting on dependencies: {plan.blocked_tickets}).",
        )

    dispatched: List[str] = []
    reconciled: List[str] = []
    failed: List[str] = []

    from .multiplexers import wait_for_subagent_completion

    # Filter ready tickets bounded by max_parallel
    to_dispatch = plan.ready_tickets[:max_parallel]
    dispatch_records = []

    for tid in to_dispatch:
        try:
            res = dispatch_ticket(
                project_root=project_root,
                spec_id=spec_id,
                ticket_id=tid,
                agent=agent or "omp",
                model=model,
                visual=visual,
                dry_run=dry_run,
            )
            dispatched.append(tid)
            dispatch_records.append((tid, res))
        except Exception:
            failed.append(tid)

    if auto_reconcile and not dry_run:
        for tid, res in dispatch_records:
            try:
                # Wait reactively if visual
                if visual and isinstance(res, dict):
                    mux_name = res.get("multiplexer", "none")
                    target = res.get("pane_id")
                    wait_for_subagent_completion(mux_name, target, timeout_sec=180)

                rec = reconcile_subagent_ticket(project_root, tid)
                if rec.status == "merged":
                    reconciled.append(tid)
                else:
                    failed.append(tid)
            except Exception:
                failed.append(tid)

    status = "completed" if not failed else "partial"
    return SwarmExecutionResult(
        spec_id=spec_id,
        status=status,
        executed_waves=1,
        dispatched_tickets=dispatched,
        reconciled_tickets=reconciled,
        failed_tickets=failed,
        details=f"Dispatched {len(dispatched)} ticket(s) in parallel.",
    )
