---
id: SPC-021
type: spec
title: Hardened universal mandate block + forced-tier wiring
status: in_progress
epic: EPC-011
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-021-T1
    title: harden AGENT_MD_BLOCK to HARD-RULES mandate language
    status: done
  - id: SPC-021-T2
    title: document per-harness forced tiers (claude/prime/omp/dsh)
    status: done
  - id: SPC-021-T3
    title: "smoke: mandate block carries the hard rules"
    status: done
---

## Summary

Upgrade the managed instruction block that every advisory-file harness reads
(AGENTS.md, CLAUDE.md, GEMINI.md, ...) from passive "project context" to an
explicit HARD-RULES mandate, mirroring the DSH acqos persona pattern. Also
document each harness's strongest (forced) tier so users on claude, prime-
agent, omp, and dsh can opt into runtime-level injection.

## Context and scope

Most of the ~29 adapters only get an instruction file. The block's language
determines how strongly those agents comply. Hard-rule persona phrasing
("before you call work done, `tenx validate` MUST pass") measurably raises
compliance versus a neutral context dump.

## Goals / non-goals

Goal: the managed block states the mandatory loop as hard rules and points to
the git pre-commit gate as the backstop. Non-goal: changing adapter data
beyond documenting forced tiers.

## Design

- `hooks.py` AGENT_MD_BLOCK: add a "Hard rules" section — run `tenx context`
  at session start; `tenx validate` must pass before marking work complete;
  write back with `tenx log --ref`; no archive/merge without human approval;
  note the pre-commit hook enforces this at commit time.
- `adapters.py` notes: record each harness's forced tier (claude SessionStart,
  prime-agent system-prompt injection, omp --append-system-prompt, dsh preset).
- README: a short "Enforcement tiers" section.

## Validation

- The managed block contains the hard-rule language.
- Smoke asserts the block carries "MUST pass" / landing-gate phrasing.
