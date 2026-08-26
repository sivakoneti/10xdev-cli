---
name: tenx-write-convention
description: How to author a tenx convention artifact (CON). Use when codifying a coding or process rule in .tenx/conventions/.
---

# Writing a convention

Create with `tenx new convention "Rule name"`. Conventions keep agents on
rails; they bind every coding session.

Requirements:
- One imperative rule sentence, then WHY (the failure it prevents).
- Applies-to scope: files, languages, or situations.
- Include a good and a bad example whenever practical.
- Run `tenx validate --fix` so INDEX.md picks the convention up.
- Only humans should retire conventions; agents flag conflicts instead.
