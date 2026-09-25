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
    thinking: Optional[str] = None,
    visual: bool = False,
    multiplexer: Optional[str] = None,
    max_parallel: int = 4,
    dry_run: bool = False,
    auto_reconcile: bool = False,
    timeout: int = 600,
    focus: bool = False,
) -> SwarmExecutionResult:
    """Execute ready tickets wave by wave, bounded by ``max_parallel``."""
    if max_parallel < 1:
        return SwarmExecutionResult(
            spec_id=spec_id, status="error", executed_waves=0,
            details="max_parallel must be at least 1",
        )

    plan = plan_spec_swarm(project_root, spec_id, agent=agent, model=model)
    if dry_run:
        return SwarmExecutionResult(
            spec_id=spec_id,
            status="completed",
            executed_waves=len(plan.waves),
            dispatched_tickets=list(plan.ready_tickets),
            details="Dry run: no workers launched.",
        )
    if not plan.ready_tickets:
        if len(plan.completed_tickets) == plan.total_tickets:
            return SwarmExecutionResult(
                spec_id=spec_id, status="completed", executed_waves=len(plan.waves),
                details="All tickets in spec DAG are already completed.",
            )
        return SwarmExecutionResult(
            spec_id=spec_id, status="no_work", executed_waves=0,
            details=f"No tickets ready to execute (waiting on dependencies: {plan.blocked_tickets}).",
        )

    dispatched: List[str] = []
    reconciled: List[str] = []
    failed: List[str] = []
    executed_waves = 0

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from .multiplexers import wait_for_subagent_completion

    while True:
        plan = plan_spec_swarm(project_root, spec_id, agent=agent, model=model)
        if len(plan.completed_tickets) == plan.total_tickets:
            return SwarmExecutionResult(
                spec_id=spec_id, status="completed", executed_waves=executed_waves,
                dispatched_tickets=dispatched, reconciled_tickets=reconciled,
                failed_tickets=failed, details="All dependency waves completed.",
            )
        ready = plan.ready_tickets[:max_parallel]
        if not ready:
            return SwarmExecutionResult(
                spec_id=spec_id, status="partial" if dispatched or failed else "no_work",
                executed_waves=executed_waves, dispatched_tickets=dispatched,
                reconciled_tickets=reconciled, failed_tickets=failed,
                details=f"No tickets ready; dependent tickets remain: {plan.blocked_tickets}.",
            )

        executed_waves += 1
        records: dict[str, dict[str, Any]] = {}
        def launch(ticket_id: str) -> tuple[str, dict[str, Any]]:
            try:
                return ticket_id, dispatch_ticket(
                    project_root=project_root, spec_id=spec_id, ticket_id=ticket_id,
                    agent=agent or "pi", model=model, thinking=thinking,
                    visual=visual, focus=focus, multiplexer=multiplexer,
                    timeout=timeout,
                )
            except Exception as exc:
                return ticket_id, {"status": "error", "error": str(exc)}

        with ThreadPoolExecutor(max_workers=min(max_parallel, len(ready))) as pool:
            futures = [pool.submit(launch, ticket_id) for ticket_id in ready]
            for future in as_completed(futures):
                ticket_id, result = future.result()
                records[ticket_id] = result
                if result.get("status") in ("dispatched", "completed"):
                    dispatched.append(ticket_id)
                else:
                    failed.append(ticket_id)

        for ticket_id in ready:
            result = records.get(ticket_id, {})
            if result.get("status") not in ("dispatched", "completed"):
                continue
            if not auto_reconcile:
                continue
            if visual:
                target = result.get("pane_id") or result.get("window_id")
                wait_result = wait_for_subagent_completion(
                    result.get("multiplexer", "none"), target, timeout_sec=timeout,
                )
                if wait_result.status != "completed":
                    failed.append(ticket_id)
                    continue
            rec = reconcile_subagent_ticket(project_root, ticket_id)
            if rec.status == "merged":
                reconciled.append(ticket_id)
            else:
                failed.append(ticket_id)

        if failed or not auto_reconcile:
            break

    unique_failed = list(dict.fromkeys(failed))
    status = "completed" if not unique_failed and auto_reconcile else "partial"
    return SwarmExecutionResult(
        spec_id=spec_id, status=status, executed_waves=executed_waves,
        dispatched_tickets=list(dict.fromkeys(dispatched)),
        reconciled_tickets=list(dict.fromkeys(reconciled)),
        failed_tickets=unique_failed,
        details="Dependency waves stopped after dispatch failure or without auto-reconcile."
        if unique_failed or not auto_reconcile else "All dependency waves completed.",
    )
