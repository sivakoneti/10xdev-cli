---
id: CON-002
type: convention
title: Zero runtime dependencies
status: complete
created: 2026-08-25
updated: 2026-08-25
---

## Rule

tenx runs on the Python 3.10+ standard library only. PyYAML is an optional
accelerator used when importable, never a hard requirement.

## Why

The CLI must install and run anywhere an agent runs — no resolver, no
network, no build step. A hard dependency breaks `uv tool install` on a
fresh machine and violates the portability promise.

## Applies to

Every module under `src/tenx/` and any new subcommand. Adding a dependency
requires a spec that justifies it and updates the install story.

## Good example

```
try:
    import yaml  # optional accelerator
except ImportError:
    yaml = None  # fall back to yamlite
```

## Bad example

```
import requests  # hard dependency -> breaks zero-dep install
```
