"""Minimal YAML-frontmatter parser for the Windows Coordinator doc tooling.

Stdlib only (no pyyaml, no `pip install`) — like everything under `tools/`, because the tooling has
to run on a bare checkout with nothing bootstrapped, including a machine that has no .NET SDK at all.
It parses ONLY the small frontmatter dialect the doc spec uses ([docs/DOC_SPEC.md](../../docs/DOC_SPEC.md)
§3): a leading `---` fenced block of `key: value` scalars, plus one list key (`related:`) in either
inline `[a, b]` or block (`- item`) form. Anything fancier is deliberately unsupported so the format
stays trivially writable and reviewable by hand.

Schema (DOC_SPEC §3):

    ---
    title:   <human title>                     # required
    tier:    platform|pillar|module|tool|meta  # required — `module`, never `engine`
    status:  living|stable|frozen|historical   # required
    updated: YYYY-MM-DD                        # required — the REVIEW flag; bump on every edit
    audited: YYYY-MM-DD                        # optional — the ACCURACY flag: "re-read against the
                                               #   code and confirmed still TRUE on this date".
                                               #   Omitted entirely on the four append-only record
                                               #   docs (MAP/INBOX/audit-log/HISTORY).
    module:  <grouping key>                    # optional — the pillar, module or tool this doc
                                               #   belongs to. Deliberately NOT validated against a
                                               #   fixed list: `coord new-module` must be able to
                                               #   introduce a new id without editing this parser.
                                               #   See DOC_SPEC §3 for the ids in use today.
    related:                                   # optional — repo-root-relative cross-links that
      - docs/DOC_SPEC.md                       #   the audit requires to resolve
    ---

`updated` and `audited` are two different claims and the distinction is the whole point: `updated`
says *someone looked at the prose*, `audited` says *the prose still matches the thing it describes*.
Nothing here enforces that difference — only a human or an AI re-reading the doc can — but the parser
keeps them as separate fields so the checker can hold them to separate rules.
"""
from __future__ import annotations

import re
from pathlib import Path

REQUIRED_KEYS = ("title", "tier", "status", "updated")

#: The five doc tiers (DOC_SPEC §2.1). NOTE: this project's third tier is **module**, not `engine`
#: — the modular unit here is a Module, and "engine" is embedded vocabulary that would mean nothing
#: to a reader of a Windows desktop toolbox (ADR 0001, ADR 0004).
VALID_TIERS = {"platform", "pillar", "module", "tool", "meta"}
VALID_STATUS = {"living", "stable", "frozen", "historical"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Stable key order for `render()` — so a regenerated doc (docs/MAP.md) is byte-identical run to run.
KEY_ORDER = ("title", "tier", "status", "updated", "audited", "module", "related")

#: A UTF-8 byte-order mark. It defeats `split_frontmatter`'s `startswith("---")` while leaving the
#: file LOOKING perfectly correct in every editor, so the doc silently drops out of the accuracy
#: machinery and its map row degrades. Callers should diagnose it as a BOM, not as "no frontmatter" —
#: the honest cause, not the symptom.
BOM = b"\xef\xbb\xbf"


def has_bom(path: Path) -> bool:
    """True if the file starts with a UTF-8 BOM (which silently breaks frontmatter parsing)."""
    try:
        with path.open("rb") as fh:
            return fh.read(3) == BOM
    except OSError:
        return False


def split_frontmatter(text: str) -> tuple[dict | None, str, str]:
    """Return `(data, raw_block, body)`.

    data       — the parsed dict, or None when there is no frontmatter block at all.
    raw_block  — the exact text between the `---` fences (fences excluded), or "".
    body       — everything after the closing fence (or the whole text when there is none).
    """
    if not text.startswith("---\n"):
        return None, "", text
    end = text.find("\n---", 4)
    if end == -1:
        return None, "", text
    raw = text[4:end + 1]          # between the fences (keep the last line's trailing newline)
    after = text[end + 4:]         # past the closing ---
    if after.startswith("\n"):
        after = after[1:]
    return _parse(raw), raw, after


def _parse(raw: str) -> dict:
    data: dict = {}
    key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue                                  # a comment line inside the block
        if line.startswith(("  - ", "- ")) and key:   # block-list item under the previous key
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(line.split("-", 1)[1].strip())
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        val = re.sub(r"\s+#.*$", "", val).strip()     # strip a trailing `# comment`
        if val == "":
            data[key] = []                            # an empty value means a block list follows
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            data[key] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
        else:
            data[key] = val.strip().strip("\"'")
    return data


def validate(data: dict) -> list[str]:
    """Return a list of human-readable problems with a frontmatter dict (empty list = valid).

    Shape only. Whether the doc is *true* is not a question a parser can answer — that is the
    judgement half of the audit protocol (docs/AUDIT.md §4).
    """
    problems: list[str] = []
    for k in REQUIRED_KEYS:
        if not data.get(k):
            problems.append(f"missing required key '{k}'")
    tier = data.get("tier")
    if tier and tier not in VALID_TIERS:
        extra = " (this project's third tier is 'module', not 'engine')" if tier == "engine" else ""
        problems.append(f"invalid tier '{tier}' — expected one of {sorted(VALID_TIERS)}{extra}")
    status = data.get("status")
    if status and status not in VALID_STATUS:
        problems.append(f"invalid status '{status}' — expected one of {sorted(VALID_STATUS)}")
    for key in ("updated", "audited"):
        val = data.get(key)
        if val and not DATE_RE.match(str(val)):
            problems.append(f"'{key}' must be YYYY-MM-DD, got '{val}'")
    related = data.get("related")
    if related is not None and not isinstance(related, list):
        problems.append("'related' must be a list of repo-root-relative paths — use the block form "
                        "(`- docs/AUDIT.md`) or the inline form (`[docs/AUDIT.md]`), "
                        f"got {type(related).__name__}")
    return problems


def read(path: Path) -> tuple[dict | None, str]:
    """`(frontmatter_dict_or_None, body)` for a file on disk."""
    data, _raw, body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    return data, body


def render(data: dict) -> str:
    """Serialize a frontmatter dict back to a `---` block, in the canonical key order.

    Used by `genmap.py` to write docs/MAP.md. Key order is fixed rather than dict-insertion order so
    that regeneration is deterministic — `coord map --check` has to be a stable equality test, not a
    source of spurious diffs.
    """
    keys = [k for k in KEY_ORDER if k in data] + [k for k in data if k not in KEY_ORDER]
    out = ["---"]
    for k in keys:
        v = data[k]
        if isinstance(v, list):
            if v:
                out.append(f"{k}:")
                out += [f"  - {item}" for item in v]
            else:
                out.append(f"{k}: []")
        else:
            out.append(f"{k}: {v}")
    out.append("---")
    return "\n".join(out) + "\n"
