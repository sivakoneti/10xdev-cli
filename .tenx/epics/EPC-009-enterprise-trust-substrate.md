---
id: EPC-009
type: epic
title: Enterprise trust substrate
status: complete
created: 2026-08-25
updated: 2026-08-25
---

## Objective

Turn tenx from a single-operator tool into a coordination layer that passes
enterprise security/platform review. The agent-facing PM loop (priority,
watchdog, triage, evidence gate) is the wedge; this epic ships the trust
substrate it must run on: concurrency-safe state, attributable tamper-evident
audit, authenticated identity, pluggable/offline backends, and light ACLs.

## Key results

- Shared `.tenx` state is safe under a fleet of concurrent agents (no lost or
  corrupt writes).
- Every mutation is attributable to an actor and tamper-evident.
- tenx runs against non-GitHub and air-gapped backends.

## Scope

SPC-017 (concurrency) is the first delivered spec. Audit+identity, pluggable
backends, self-host/residency, and ACLs are follow-up specs scoped on demand.

## Non-goals

- Coding-agent/platform concerns tenx should integrate with, not rebuild:
  sandboxing code execution, model-cost metering, secret isolation during agent
  runs, inference HA, line-level AI-code provenance.

## Milestones

1. SPC-017 concurrency-safe state (this release).
2. Audit integrity + actor identity.
3. Pluggable/offline sync backends.
