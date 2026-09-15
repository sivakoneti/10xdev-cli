"""Frontmatter parsing with zero hard dependencies.

Prefers PyYAML when importable; otherwise falls back to a small YAML-subset
parser that covers everything tenx templates and agents write:

- flat ``key: value`` scalars (strings, numbers, dates kept as strings)
- inline lists ``[a, b, c]``
- block lists of scalars
- block lists of flat mappings (used for ``tickets:``)
- one level of nested flat mappings
- comments and quoted strings
"""

from __future__ import annotations

import re
from typing import Any

try:  # pragma: no cover - depends on environment
    import yaml as _pyyaml  # type: ignore
except Exception:  # pragma: no cover
    _pyyaml = None

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (frontmatter_text_or_None, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def _strip_comment(line: str) -> str:
    # Remove trailing comments not inside quotes.
    out = []
    quote = None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(raw: str) -> Any:
    s = raw.strip()
    if not s:
        return ""
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s  # dates and everything else stay strings


def _inline_list(raw: str) -> list[Any]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    parts, buf, quote = [], "", None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            buf += ch
            continue
        if ch == ",":
            parts.append(buf)
            buf = ""
            continue
        buf += ch
    parts.append(buf)
    return [_scalar(p) for p in parts if p.strip()]


def yamlite_load(text: str,
                 problems: list[str] | None = None) -> dict[str, Any]:
    """Parse the YAML subset used by tenx frontmatter.

    If `problems` is given, lines the fallback parser cannot understand
    are reported there instead of being silently dropped (SPC-023-T12:
    silent data loss is worse than a visible error).
    """
    def skip(raw: str) -> None:
        if problems is not None and raw.strip():
            problems.append(f"line not understood by the fallback parser: "
                            f"{raw.strip()[:80]!r}")

    root: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = _strip_comment(lines[i].replace("\t", "  "))
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line.startswith(" "):
            # Unexpected indentation at top level.
            skip(line)
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):(.*)$", line)
        if not m:
            skip(line)
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest:
            root[key] = _inline_list(rest) if rest.startswith("[") else _scalar(rest)
            i += 1
            continue
        # Block value: collect indented lines. YAML also allows list items
        # at the SAME indent as their key (`key:\n- item`), so accept
        # indent-0 lines that start a list item (SPC-023-T12).
        block: list[str] = []
        i += 1
        while i < n:
            nxt = lines[i].replace("\t", "  ")
            if not nxt.strip():
                block.append("")
                i += 1
                continue
            indent = len(nxt) - len(nxt.lstrip(" "))
            if indent == 0 and not nxt.lstrip().startswith("- "):
                break
            block.append(nxt)
            i += 1
        root[key] = _parse_block(block, problems)
    return root


def _parse_block(block: list[str],
                 problems: list[str] | None = None) -> Any:
    # Trim common indent.
    items = [b for b in block if b.strip()]
    if not items:
        return ""
    indents = [len(b) - len(b.lstrip(" ")) for b in items]
    pad = min(indents)
    block = [b[pad:] if b.strip() else "" for b in block]
    if block and any(b.lstrip().startswith("- ") or b.strip() == "-" for b in block if b.strip()):
        return _parse_list(block, problems)
    return _parse_map(block, problems)


def _parse_list(block: list[str],
                problems: list[str] | None = None) -> list[Any]:
    out: list[Any] = []
    cur: dict[str, Any] | None = None
    for raw in block:
        if not raw.strip():
            continue
        s = raw.strip()
        if s.startswith("- "):
            if cur is not None:
                out.append(cur)
                cur = None
            item = s[2:].strip()
            m = re.match(r"^([A-Za-z0-9_.-]+):(.*)$", item)
            if m:
                cur = {m.group(1): _scalar(m.group(2))}
            else:
                out.append(_scalar(item))
        elif cur is not None:
            m = re.match(r"^([A-Za-z0-9_.-]+):(.*)$", s)
            if m:
                cur[m.group(1)] = _scalar(m.group(2))
            elif problems is not None:
                problems.append(f"list continuation not understood: "
                                f"{s[:80]!r}")
        elif problems is not None:
            problems.append(f"list line outside any item not understood: "
                            f"{s[:80]!r}")
    if cur is not None:
        out.append(cur)
    return out


def _parse_map(block: list[str],
               problems: list[str] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw in block:
        if not raw.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):(.*)$", raw.strip())
        if m:
            out[m.group(1)] = _scalar(m.group(2))
        elif problems is not None:
            problems.append(f"map line not understood: "
                            f"{raw.strip()[:80]!r}")
    return out


def load_frontmatter(text: str) -> tuple[dict[str, Any] | None, str, str | None]:
    """Parse a document. Returns (meta, body, error)."""
    fm, body = split_frontmatter(text)
    if fm is None:
        return None, body, "missing frontmatter (expected leading '---' block)"
    if _pyyaml is not None:
        try:
            meta = _pyyaml.safe_load(fm)
            if not isinstance(meta, dict):
                return None, body, "frontmatter is not a mapping"
            return meta, body, None
        except Exception as exc:  # pragma: no cover
            return None, body, f"invalid YAML frontmatter: {exc}"
    try:
        problems: list[str] = []
        meta = yamlite_load(fm, problems)
        if problems:
            # SPC-023-T12: keep the partial parse BUT make the loss
            # visible — silent data loss is how harnesses rot.
            return meta, body, ("fallback parser dropped frontmatter "
                                "lines: " + "; ".join(problems[:3]))
        return meta, body, None
    except Exception as exc:  # pragma: no cover
        return None, body, f"invalid frontmatter: {exc}"


def dump_frontmatter(meta: dict[str, Any]) -> str:
    """Serialize metadata back to YAML (subset writer, stable key order)."""
    if _pyyaml is not None:
        return _pyyaml.safe_dump(meta, sort_keys=False, default_flow_style=False, allow_unicode=True).rstrip()
    lines: list[str] = []
    for key, val in meta.items():
        if val is None:
            lines.append(f"{key}:")
        elif isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        elif isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            elif all(isinstance(v, dict) for v in val):
                lines.append(f"{key}:")
                for item in val:
                    first = True
                    for k, v in item.items():
                        prefix = "  - " if first else "    "
                        lines.append(f"{prefix}{k}: {_quote(v)}")
                        first = False
            else:
                lines.append(f"{key}:")
                for v in val:
                    lines.append(f"  - {_quote(v)}")
        else:
            lines.append(f"{key}: {_quote(val)}")
    return "\n".join(lines)


def _quote(v: Any) -> str:
    s = str(v)
    if s == "":
        return '""'
    if re.search(r"[:#\[\]{},&*!|>'\"%@`]", s) or s != s.strip():
        return '"' + s.replace('"', '\\"') + '"'
    return s
