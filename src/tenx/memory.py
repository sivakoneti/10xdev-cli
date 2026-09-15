"""Closed-loop agent memory and capability distillation for tenx.

Inspired by the verified backpass pattern:
- Distills long harness conversation transcripts (pi, omp, prime-agent, codex)
  into compressed verification-coupled takeaways.
- Maintains a Gap Ledger: patterns require multi-session corroboration (>= 2 sessions)
  before graduating into project conventions.
- Couples loss directly to `tenx validate` and automated test results.
- Enforces strict token budgets by refactoring AGENTS.md rules into .tenx/conventions/
  or bundled skills.

Zero runtime dependencies (Python standard library only).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DistilledObservation:
    session_id: str
    harness: str
    category: str  # "rule_violation", "tool_misuse", "workflow_failure", "performance"
    summary: str
    verdict: str   # "pass", "fail", "blocked"
    error_pattern: Optional[str] = None
    recommended_action: Optional[str] = None


@dataclass
class GapLedgerEntry:
    pattern_id: str
    description: str
    occurrences: int
    sessions: List[str]
    graduated: bool
    target_convention: Optional[str] = None


class MemoryDistiller:
    """Manages transcript distillation and the cross-session Gap Ledger."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self.memory_dir = self.root / ".tenx" / "memory"
        self.ledger_file = self.memory_dir / "gap_ledger.json"
        self.distillations_file = self.memory_dir / "distillations.jsonl"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        if not self.ledger_file.exists():
            self.ledger_file.write_text(json.dumps({"entries": []}, indent=2), encoding="utf-8")

    def load_ledger(self) -> List[GapLedgerEntry]:
        try:
            data = json.loads(self.ledger_file.read_text(encoding="utf-8"))
            return [GapLedgerEntry(**item) for item in data.get("entries", [])]
        except Exception:
            return []

    def save_ledger(self, entries: List[GapLedgerEntry]) -> None:
        payload = {"entries": [asdict(e) for e in entries]}
        self.ledger_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def record_observation(self, obs: DistilledObservation) -> Optional[GapLedgerEntry]:
        """Record an observation and update the Gap Ledger.

        Returns the ledger entry if it graduated (occurrences >= 2 across distinct sessions).
        """
        # Append to distillations log
        with open(self.distillations_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(obs)) + "\n")

        # Update Gap Ledger
        entries = self.load_ledger()
        matched = None
        for entry in entries:
            # Match by normalized summary or error pattern
            if obs.error_pattern and entry.pattern_id == obs.error_pattern:
                matched = entry
                break
            elif obs.summary.lower() in entry.description.lower() or entry.description.lower() in obs.summary.lower():
                matched = entry
                break

        graduated_entry = None
        if matched:
            if obs.session_id not in matched.sessions:
                matched.sessions.append(obs.session_id)
                matched.occurrences += 1
            if matched.occurrences >= 2 and not matched.graduated:
                matched.graduated = True
                graduated_entry = matched
        else:
            pat_id = obs.error_pattern or re.sub(r"[^a-zA-Z0-9]+", "-", obs.summary.lower()).strip("-")[:40]
            new_entry = GapLedgerEntry(
                pattern_id=pat_id,
                description=obs.summary,
                occurrences=1,
                sessions=[obs.session_id],
                graduated=False,
            )
            entries.append(new_entry)

        self.save_ledger(entries)
        return graduated_entry
