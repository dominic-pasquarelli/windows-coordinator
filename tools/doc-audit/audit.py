#!/usr/bin/env python3
"""Windows Coordinator doc-audit — the mechanical drift detector for code↔documentation alignment.

This is the *automated half* of the audit protocol ([docs/AUDIT.md](../../docs/AUDIT.md) §2). It
catches the drift a human reviewer reliably misses: a link that rots when a file moves, a `src/…`
path named in prose that no longer exists, a gap in the ADR sequence, a module that lost its shelving
docs, a stale generated map, a doc edited without its review flag being bumped — and the modularity
violations that quietly turn a reusable platform back into a pile of one-offs.

It does NOT, and structurally cannot, judge the parts of an audit that need a brain: is this doc
still *true*, not merely *present*? is this solution bespoke when it should be a platform service?
does this claim outrun its evidence? Those are the six lenses in docs/AUDIT.md §4. This script exists
to make the mechanical drift **free to find**, so the audit's scarce attention goes where only
judgement helps.

⚠ **What a green run means here.** No .NET SDK has ever been present in the environment this project
was authored in — not one line of its C# has been compiled. The `boundary` check is real and it does
genuine work, but it reads *text*: `using` directives, namespace declarations, `[DllImport]`
attributes, and `.csproj` `ProjectReference` elements. A green boundary result means "the obvious
leaks are absent". It never means "the boundary is proven", and a green audit is never a green build
([docs/OPERATING_MODEL.md](../../docs/OPERATING_MODEL.md) §7).

Design constraints:
  - **Stdlib only, Python 3.11+.** No `pip install`, no toolchain, no .NET. It has to run on a bare
    checkout and in CI, which is precisely why it is the only half of the protocol that is executable
    in a non-Windows environment.
  - **High signal.** ERROR means unambiguous breakage and fails the gate. WARN and INFO are advisory
    and never fail, so the gate cannot cry wolf and get ignored — an ignored ERROR is how a gate
    stops meaning anything.

Usage:
  python3 tools/doc-audit/audit.py                      # full report; exit 1 on any ERROR
  python3 tools/doc-audit/audit.py --quiet              # summary + ERRORs only
  python3 tools/doc-audit/audit.py --format json        # machine-readable
  python3 tools/doc-audit/audit.py --no-fail            # always exit 0 (report only)
  python3 tools/doc-audit/audit.py --since origin/main  # branch closeout (changed docs must bump)
  python3 tools/doc-audit/audit.py --accuracy           # only the accuracy backlog; always exit 0

Wrapped by `coord audit` (tools/coord/coord.py) and run in CI (.github/workflows/ci.yml).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as fm  # noqa: E402   (the shared frontmatter parser, same directory)
import genmap  # noqa: E402              (the map generator — reused for the map-sync check)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent   # tools/doc-audit/ -> repo root

# Directories never descended into: build outputs, dependency trees, editor state. Kept in sync with
# genmap.SKIP_DIRS so the two halves can never disagree about what "the project" is.
SKIP_DIRS = genmap.SKIP_DIRS

# --- what the doc spec says about frontmatter (DOC_SPEC §3) ------------------------------------

#: Exempt from frontmatter ENTIRELY. ADRs use their own dated `Date:`/`Status:` header; CLAUDE.md and
#: AGENTS.md are standing instruction files with their own shape; `.claude/` skill definitions use
#: Claude Code's schema; the GitHub PR template would render YAML as literal text.
FRONTMATTER_EXEMPT_PREFIXES = ("docs/decisions/", ".claude/")
FRONTMATTER_EXEMPT_EXACT = {"CLAUDE.md", "AGENTS.md", ".github/pull_request_template.md"}

#: The four append-only record/buffer docs. They carry frontmatter but NO `audited:` key: each is a
#: summary as of its own date, not a living claim about current code, so "is this still true?" is not
#: a meaningful question to ask them. Exempt from the accuracy check (DOC_SPEC §3).
RECORD_DOCS = {"docs/MAP.md", "docs/INBOX.md", "docs/audit-log.md", "docs/HISTORY.md"}

#: Docs that are correct *as of their date* even after the tree moves underneath them, so the
#: current-path checks skip them: a dated ADR, a pinned freeze record, and the audit log — which
#: records drift by NAMING the dead paths it found.
DATED_RECORD_PREFIXES = ("docs/decisions/", "docs/freezes/")
DATED_RECORD_EXACT = {"docs/audit-log.md"}

# --- patterns -----------------------------------------------------------------------------------

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
#: An inline-code token that *looks like* a repo path: a known top-level directory + a slashy tail.
PATH_TOKEN_RE = re.compile(r"^(?:src|tools|tests|docs|\.github)/[A-Za-z0-9._/+-]+$")
#: Markers meaning "illustrative, not a literal path" — a placeholder, a glob, a template name.
PLACEHOLDER_CHARS = set("*<>{}…?|")
PLACEHOLDER_WORDS = ("NNNN", "yyyy-mm-dd", "YYYY-MM-DD")
#: Build/tool output segments: a doc naming one is correct, the path just isn't in a fresh checkout.
EPHEMERAL_SEGMENTS = {"bin", "obj", "out", "publish", "TestResults", "node_modules", "dist",
                      "build", "packages", ".vs", "__pycache__"}
ADR_RE = re.compile(r"^(\d{4})-.+\.md$")
#: A closure token on an ADR's Status line — the *drain* half of the capture/recall/drain loop.
ADR_CLOSURE_RE = re.compile(r"·\s*(?:Superseded|Closed|Historical)", re.IGNORECASE)
#: A body callout declaring supersession — the drift the Status line ought to mirror.
ADR_BODY_SUPERSEDED_RE = re.compile(r"(?im)^\s*>?\s*\*\*(?:Superseded|HISTORICAL note)")
#: A strong "this fully shipped" signal, kept deliberately specific so a still-guiding reference ADR
#: that merely says "implemented" is not mistaken for a spent one-shot.
ADR_SHIPPED_RE = re.compile(
    r"(?i)\b(?:shipped|released|manually[- ]validated|fully implemented|SHIPPED 20)\b")

#: Paths a doc may legitimately name that are absent from a fresh checkout — gitignored secrets,
#: per-machine state, generated artifacts. Each entry should be justified by the doc that names it.
CODE_REF_ALLOW: set[str] = {
    # The solution file is deliberately NOT committed from this environment: a .sln carries project
    # GUIDs that cannot be generated or verified without a .NET SDK, and a hand-written one would be
    # a fabricated artifact. Generating it is the first task in docs/NEXT.md.
    "Coordinator.sln",
    "src/Coordinator.sln",
}

# --- thresholds ---------------------------------------------------------------------------------

#: Accuracy staleness (DOC_SPEC §3): a living doc whose `audited` date is older than this many days,
#: OR which has seen more than this many repo commits since, is flagged for a re-read. WARN, never
#: ERROR — staleness is driven by time and churn, so a hard gate would block unrelated work after a
#: quiet fortnight. Overridable with --stale-days / --stale-commits.
STALE_DAYS = 7
STALE_COMMITS = 15

#: Recall/drain windows (AUDIT.md Lens E). Advisory only — capture is free, recall is the discipline,
#: and a nudge that becomes a wall gets routed around.
ADR_RECALL_DAYS = 30
ADR_CLOSED_CANDIDATE_DAYS = 60
INBOX_STALE_DAYS = 30

# --- the modularity boundary --------------------------------------------------------------------

#: Namespaces that only exist on Windows. A **Core** project (`net9.0`, no `-windows` suffix) that
#: names one of these has broken the Core/Shell split (ADR 0003): its logic is no longer host-testable
#: on any OS, and the whole testability argument for the split evaporates.
WINDOWS_ONLY_NAMESPACES = (
    "System.Windows",            # WPF / Forms
    "Microsoft.UI",              # WinUI 3 / Windows App SDK
    "Microsoft.Win32",           # registry, native shell interop
    "Windows.",                  # WinRT projections (Windows.Foundation, Windows.UI, …)
    "WinRT",
)
#: P/Invoke attributes. `LibraryImport` is the .NET 7+ source-generated form of the same thing, so
#: checking only `DllImport` would leave the modern spelling as an open door.
PINVOKE_RE = re.compile(r"\[\s*(DllImport|LibraryImport)\s*\(")
USING_RE = re.compile(r"^\s*(?:global\s+)?using\s+(?:static\s+)?([A-Za-z_][\w.]*)\s*;", re.M)
NAMESPACE_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w.]*)", re.M)


@dataclass
class Finding:
    severity: str            # "error" | "warn" | "info"
    check: str               # the check id — the same ids AUDIT.md §8 tabulates
    file: str                # repo-relative path
    line: int | None         # 1-indexed, when a specific line is meaningful
    message: str             # what is wrong
    remedy: str              # what to DO about it

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity: str, check: str, file: str, line: int | None,
            message: str, remedy: str) -> None:
        self.findings.append(Finding(severity, check, file, line, message, remedy))

    def by_severity(self, sev: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == sev]


# --- filesystem helpers --------------------------------------------------------------------------

def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """Every file under `root` with one of `suffixes`, skipping SKIP_DIRS, in a stable order."""
    out: list[Path] = []
    for p in root.rglob("*"):
        # ⚠ Same fix as genmap._all_md, for the same reason: match SKIP_DIRS against the path
        # RELATIVE to the repo root, never against `p.parts`. `p.parts` also tests every ancestor
        # directory ABOVE the checkout, so a clone living under any directory named build/ dist/
        # out/ venv/ scratchpad/ … skips every single file and reports a confident, empty success.
        # A checker that cannot fail is indistinguishable from a comment.
        try:
            rel = p.relative_to(REPO_ROOT)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.is_file() and p.suffix in suffixes:
            out.append(p)
    return sorted(out, key=lambda p: p.relative_to(REPO_ROOT).as_posix())


def _iter_md() -> list[Path]:
    return _iter_files(REPO_ROOT, (".md",))


def _rel(p: Path) -> str:
    """Repo-relative, always forward-slashed — so prefix and allow-list checks match on Windows."""
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _subdirs(rel_parent: str) -> list[str]:
    """Immediate subdirectory names of a repo-relative directory (skipping hidden/tooling dirs)."""
    d = REPO_ROOT / rel_parent
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith("."))


def _module_dirs() -> list[str]:
    """The modules that exist on disk — the single source of truth for "what modules exist"."""
    return _subdirs("src/modules")


def _pillar_dirs() -> list[str]:
    return _subdirs("src/pillars")


def _required_frontmatter_docs() -> list[Path]:
    """Docs that MUST carry frontmatter (DOC_SPEC §3): every `*.md` under `docs/` at any depth, plus
    every `README.md` — minus the deliberate exemptions."""
    out: list[Path] = []
    docs = REPO_ROOT / "docs"
    if docs.is_dir():
        out += [p for p in _iter_files(docs, (".md",))]
    out += [p for p in _iter_md() if p.name == "README.md"]
    keep: list[Path] = []
    seen: set[str] = set()
    for p in out:
        rel = _rel(p)
        if rel in seen:
            continue
        seen.add(rel)
        if rel in FRONTMATTER_EXEMPT_EXACT or rel.startswith(FRONTMATTER_EXEMPT_PREFIXES):
            continue
        keep.append(p)
    return keep


def _is_dated_record(rel: str) -> bool:
    return rel.startswith(DATED_RECORD_PREFIXES) or rel in DATED_RECORD_EXACT


# --- checks: paths, links, frontmatter -----------------------------------------------------------

def check_doc_link(rep: Report) -> None:
    """`doc-link` (ERROR) — every relative Markdown link must resolve to a file that exists.

    Links rot hard and silently: the file moves, the link survives, and the next cold reader burns
    the hour the docs were supposed to save. The `#anchor` is stripped — we verify the file, not the
    heading.
    """
    for md in _iter_md():
        text = md.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                continue
            path_part = target.split("#", 1)[0].strip()
            if not path_part:
                continue
            if (md.parent / path_part).resolve().exists():
                continue
            rep.add("error", "doc-link", _rel(md), _line_of(text, m.start()),
                    f"broken link → {target}",
                    "create the target, correct the path, or remove the link")


def check_related(rep: Report) -> None:
    """`related` (ERROR) — every `related:` frontmatter edge must resolve.

    `related:` entries are **repo-root-relative** (`docs/AUDIT.md`, `CLAUDE.md`), unlike body links
    which are relative to the doc's own location. They are the wiki graph's explicit edges: a dead
    one is a broken edge in the structure the whole traversal story rests on.
    """
    for md in _iter_md():
        data, _ = fm.read(md)
        if not data:
            continue
        related = data.get("related")
        if not isinstance(related, list):
            continue        # a scalar `related:` is reported by check_frontmatter
        for target in related:
            if not (REPO_ROOT / str(target)).exists():
                rep.add("error", "related", _rel(md), None,
                        f"`related:` entry does not resolve → {target}",
                        "entries are repo-root-relative (docs/AUDIT.md, CLAUDE.md) — fix the path "
                        "or drop the edge")


def check_code_ref(rep: Report) -> None:
    """`code-ref` (ERROR) — an inline-code token that looks like a repo path must exist.

    This is the check that catches a doc describing a file layout that has quietly moved on. It is
    ERROR severity on purpose while the repo is young: every path token in every living doc must
    resolve. If it ever starts firing on legitimately illustrative references, that is the signal to
    narrow its scope by an explicit decision and an ADR — never to start ignoring it.

    Skipped: dated records (an ADR, a freeze record, the audit log — each correct as of its date,
    and the log *records* drift by naming the dead paths it found), placeholder/glob tokens, and
    build-output segments that no fresh checkout contains.
    """
    for md in _iter_md():
        rel_md = _rel(md)
        if _is_dated_record(rel_md):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        seen: set[str] = set()
        for m in INLINE_CODE_RE.finditer(text):
            raw = m.group(1).strip()
            token = re.sub(r":\d+(-\d+)?$", "", raw).rstrip(").,;:")     # drop a `file.cs:42` tail
            if token in seen or not PATH_TOKEN_RE.match(token):
                continue
            if any(c in PLACEHOLDER_CHARS for c in token) or any(w in token for w in PLACEHOLDER_WORDS):
                continue
            parts = token.split("/")
            if any(seg in EPHEMERAL_SEGMENTS for seg in parts):
                continue
            if token in CODE_REF_ALLOW:
                continue
            if (REPO_ROOT / token).exists():
                continue
            seen.add(token)
            rep.add("error", "code-ref", rel_md, _line_of(text, m.start()),
                    f"referenced path does not exist → {token}",
                    "create it, correct the reference, or — if it is a planned path — say so in "
                    "prose instead of naming it as if it were there")


def check_frontmatter(rep: Report) -> None:
    """`frontmatter` (ERROR) — required docs carry valid frontmatter; any frontmatter present is valid.

    Validates shape only: the required keys, a tier from the five, a status from the four, and
    `YYYY-MM-DD` dates. Whether the doc is *true* is Lens A's job, not a parser's.
    """
    required = {_rel(p) for p in _required_frontmatter_docs()}
    for md in _iter_md():
        rel = _rel(md)
        if rel in FRONTMATTER_EXEMPT_EXACT or rel.startswith(FRONTMATTER_EXEMPT_PREFIXES):
            continue
        # A UTF-8 BOM defeats the `startswith("---")` test while leaving the file LOOKING correct in
        # every editor, so the doc silently drops out of accuracy tracking and its map row degrades.
        # Report it as a BOM, not as "missing frontmatter" — the honest cause, not the symptom.
        if fm.has_bom(md):
            rep.add("error", "frontmatter", rel, 1,
                    "file starts with a UTF-8 BOM, so its frontmatter does not parse — the doc "
                    "falls out of accuracy tracking and its docs/MAP.md row degrades",
                    "rewrite the file as plain UTF-8 (encoding='utf-8', never 'utf-8-sig')")
            continue
        data, _ = fm.read(md)
        if data is None:
            if rel in required:
                rep.add("error", "frontmatter", rel, 1,
                        "missing frontmatter (DOC_SPEC §3 requires it on every docs/*.md and every "
                        "README.md)",
                        "add the `---` block: title, tier, status, updated (+ audited, module, "
                        "related as appropriate)")
            continue
        for problem in fm.validate(data):
            rep.add("error", "frontmatter", rel, None, problem,
                    "fix the frontmatter block against the schema in DOC_SPEC §3")


def check_map_sync(rep: Report) -> None:
    """`map-sync` (ERROR) — docs/MAP.md must equal a fresh generation.

    The map is the wiki front door, and it is only trustworthy because it is generated and
    drift-checked. Generation is deterministic, so a difference here is always a real difference in
    the doc set, never noise.
    """
    map_path = REPO_ROOT / "docs" / "MAP.md"
    fresh = genmap.build_map()
    cur = map_path.read_text(encoding="utf-8", errors="replace") if map_path.exists() else ""
    if cur == fresh:
        return
    what = "is out of date versus a fresh generation" if cur else "does not exist"
    rep.add("error", "map-sync", "docs/MAP.md", None,
            f"the generated documentation index {what}",
            "run `coord map` (i.e. python3 tools/doc-audit/genmap.py) and commit the result")


# --- checks: the decision log --------------------------------------------------------------------

def _adr_files() -> list[Path]:
    adr_dir = REPO_ROOT / "docs" / "decisions"
    if not adr_dir.is_dir():
        return []
    return sorted(p for p in adr_dir.glob("*.md") if ADR_RE.match(p.name))


def check_adr_gap(rep: Report) -> None:
    """`adr-gap` (ERROR) — ADR numbers are contiguous from 0001, with no duplicates.

    The sequence being unbroken is what makes the log a *record* rather than a pile: a gap means a
    decision was written and lost, or renamed and orphaned, and either way something that was
    reasoned about is now unfindable.
    """
    nums: dict[int, list[str]] = {}
    for p in _adr_files():
        m = ADR_RE.match(p.name)
        assert m
        nums.setdefault(int(m.group(1)), []).append(p.name)
    if not nums:
        return
    for n, names in sorted(nums.items()):
        if len(names) > 1:
            rep.add("error", "adr-gap", "docs/decisions/", None,
                    f"duplicate ADR number {n:04d}: {', '.join(sorted(names))}",
                    "renumber one of them to the next free number and fix any inbound links")
    for n in range(1, max(nums) + 1):
        if n not in nums:
            rep.add("error", "adr-gap", "docs/decisions/", None,
                    f"gap in the ADR sequence: {n:04d} is missing",
                    "restore the missing decision, or renumber so the log is contiguous")


def _adr_header(text: str) -> tuple[str | None, str | None, str]:
    """`(status_word, date, raw_status_line)` from an ADR's header block.

    `re.search` rather than `re.match`, and `\\**` around the value, so a bolded `**Status:**
    Proposed` still parses — a very common Markdown spelling that would otherwise drop the ADR out
    of the lifecycle check silently.
    """
    status = date_s = None
    status_line = ""
    for line in text.splitlines()[:20]:
        m = re.search(r"\bStatus:\s*\**\s*([A-Za-z][A-Za-z-]*)", line)
        if m and status is None:
            status, status_line = m.group(1).lower(), line
        m = re.search(r"\bDate:\s*\**\s*(\d{4}-\d{2}-\d{2})", line)
        if m and date_s is None:
            date_s = m.group(1)
    return status, date_s, status_line


def check_adr_format(rep: Report) -> None:
    """`adr-format` (ERROR) — every ADR carries a `Date:` and a `Status:` header.

    ADRs are exempt from frontmatter precisely because they use this dated header instead; an ADR
    missing it has no machine-readable date or state at all, so the lifecycle checks below cannot
    see it and it cannot be recalled or drained.
    """
    for p in _adr_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        status, date_s, _ = _adr_header(text)
        missing = [k for k, v in (("Date:", date_s), ("Status:", status)) if not v]
        if missing:
            rep.add("error", "adr-format", _rel(p), None,
                    f"ADR header is missing {' and '.join(missing)}",
                    "add the header block under the title: `Date: YYYY-MM-DD` then "
                    "`Status: Proposed|Accepted|…` (DOC_SPEC §2.3)")


def check_adr_lifecycle(rep: Report) -> None:
    """`adr-lifecycle` (INFO) — the two ends of the loop: recall in, drain out.

    **Recall.** A `Proposed` ADR is a deferred decision. If its number appears nowhere in
    docs/NEXT.md it has no way back — it will not resurface on its own, and deferral quietly becomes
    abandonment.

    **Drain.** An `Accepted` ADR that reads as a fully-shipped one-shot, or whose body already
    declares itself superseded, should carry a closure token on its Status line
    (`· Closed <date>` / `· Superseded by ADR NNNN`) so the active set stays the set that is actually
    active.

    INFO throughout: capture is free, so this is a nudge, never a wall.
    """
    next_path = REPO_ROOT / "docs" / "NEXT.md"
    next_text = next_path.read_text(encoding="utf-8", errors="replace") if next_path.exists() else ""
    today = date.today()
    candidates: list[str] = []
    for p in _adr_files():
        m = ADR_RE.match(p.name)
        assert m
        num = m.group(1)
        rel = _rel(p)
        text = p.read_text(encoding="utf-8", errors="replace")
        status, date_s, status_line = _adr_header(text)
        age = None
        if date_s:
            try:
                age = (today - date.fromisoformat(date_s)).days
            except ValueError:
                age = None

        if status == "proposed":
            if not re.search(rf"\b0*{int(num)}\b", next_text):
                rep.add("info", "adr-lifecycle", rel, None,
                        f"Proposed ADR {num} has no recall hook in docs/NEXT.md — a deferred "
                        "decision with no way back cannot resurface",
                        "add a NEXT.md item, a trip-wire row, or a 'revisit when …' trigger naming "
                        f"ADR {num}")
            if age is not None and age > ADR_RECALL_DAYS:
                rep.add("info", "adr-lifecycle", rel, None,
                        f"Proposed ADR {num} has sat {age} days",
                        "recall review: is it feasible now? already built and never closed out "
                        "(→ Accepted)? or still genuinely deferred?")
            continue

        if ADR_CLOSURE_RE.search(status_line):
            continue                                   # already drained
        if ADR_BODY_SUPERSEDED_RE.search(text):
            rep.add("info", "adr-lifecycle", rel, None,
                    f"ADR {num} reads as superseded/historical in its body, but its Status line "
                    "carries no closure token",
                    "mirror it on the Status line: `Status: Accepted · Superseded by ADR NNNN "
                    "(<date>)` or `· Historical <date>`")
            continue
        if age is not None and age > ADR_CLOSED_CANDIDATE_DAYS and ADR_SHIPPED_RE.search(text):
            candidates.append(num)
    if candidates:
        head = ", ".join(candidates[:8]) + (" …" if len(candidates) > 8 else "")
        rep.add("info", "adr-lifecycle", "docs/decisions/", None,
                f"{len(candidates)} aged Accepted ADR(s) read as shipped one-shots with no closure "
                f"token ({head})",
                "review each for `Status: Accepted · Closed <date> — shipped` so the active set "
                "stays the set that is actually active")


# --- checks: the modularity boundary (the teeth) -------------------------------------------------
#
# Everything below reads TEXT, because nothing here has been compiled. That is a real limitation and
# it is recorded as TD-3, not glossed: the check is defeated by reflection, by a fully-qualified type
# name written inline, by a source generator, or by a package that drags Windows types in
# transitively. It still catches the ordinary way the rule gets broken, which is someone adding an
# import — and it is the only modularity guarantee available without a toolchain.

def _csproj_info(path: Path) -> tuple[list[str], list[str]]:
    """`(target_frameworks, project_reference_includes)` for a `.csproj`.

    Reads the real `<TargetFramework>`/`<TargetFrameworks>` rather than guessing from the path, so
    the Core/Shell classification is grounded in what the project actually declares. Falls back to a
    regex when the XML does not parse — a malformed project file must not silently disable the
    boundary check.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    tfms: list[str] = []
    refs: list[str] = []
    try:
        root = ET.fromstring(text)
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag in ("TargetFramework", "TargetFrameworks") and el.text:
                tfms += [t.strip() for t in el.text.split(";") if t.strip()]
            elif tag == "ProjectReference":
                inc = el.get("Include")
                if inc:
                    refs.append(inc)
    except ET.ParseError:
        for raw in re.findall(r"<TargetFrameworks?>([^<]+)</TargetFrameworks?>", text):
            tfms += [t.strip() for t in raw.split(";") if t.strip()]
        refs += re.findall(r'<ProjectReference[^>]*\sInclude="([^"]+)"', text)
    return tfms, refs


def _area_of(rel: str) -> tuple[str | None, str | None]:
    """`(kind, name)` for a repo-relative path: the architectural area it belongs to.

    kind ∈ {"platform", "pillar", "module", "tests"}; name is the pillar/module directory name.
    Mirrors the placement rule in DOC_SPEC §2.1 and the tree in COORDINATOR.md.
    """
    parts = rel.split("/")
    if rel.startswith("src/platform/"):
        return "platform", "platform"
    if rel.startswith("src/shell/"):
        return "platform", "shell"
    if rel.startswith("src/pillars/") and len(parts) > 2:
        return "pillar", parts[2]
    if rel.startswith("src/modules/") and len(parts) > 2:
        return "module", parts[2]
    if rel.startswith("tests/"):
        return "tests", parts[1] if len(parts) > 1 else None
    return None, None


def _is_core_project(rel: str, tfms: list[str]) -> bool:
    """Is this project a **Core** project — `net9.0`, Windows-free, host-testable on any OS?

    Two independent tells, either sufficient (ADR 0003):
      1. the path contains a `*.Core` project directory (the naming convention), or
      2. the declared TargetFramework(s) carry no `-windows` suffix (the actual build shape).
    An undeclared framework is treated as NOT Core: guessing "Core" there would manufacture findings
    against a project whose shape nobody has stated.
    """
    if any(seg.endswith(".Core") for seg in rel.split("/")[:-1]):
        return True
    if tfms:
        return all("-windows" not in t.lower() for t in tfms)
    return False


def _projects() -> list[dict]:
    out: list[dict] = []
    for p in _iter_files(REPO_ROOT, (".csproj",)):
        rel = _rel(p)
        tfms, refs = _csproj_info(p)
        kind, name = _area_of(rel)
        out.append({"rel": rel, "path": p, "tfms": tfms, "refs": refs,
                    "kind": kind, "name": name, "core": _is_core_project(rel, tfms)})
    return out


def _project_for(cs: Path, projects: list[dict]) -> dict | None:
    """The nearest enclosing project for a `.cs` file (walk up until a `.csproj` is found)."""
    d = cs.parent
    while True:
        for pr in projects:
            if pr["path"].parent == d:
                return pr
        if d == REPO_ROOT or d.parent == d:
            return None
        d = d.parent


def _namespace_owners(projects: list[dict]) -> dict[str, tuple[str, str]]:
    """Map declared namespace → `(kind, name)` of the area that declares it.

    Built from the `namespace` declarations actually present in the tree, so the check works whatever
    naming convention the code settles on, rather than hard-coding one. Seeded with the conventional
    module roots (`Coordinator.Modules.<Name>`, `Coordinator.<Name>`) for each module directory that
    exists, so a `using` of a module that has directories but no source yet is still caught.
    """
    owners: dict[str, tuple[str, str]] = {}
    for mod in _module_dirs():
        owners[f"Coordinator.Modules.{mod}"] = ("module", mod)
        owners[f"Coordinator.{mod}"] = ("module", mod)
    for cs in _iter_files(REPO_ROOT / "src", (".cs",)) if (REPO_ROOT / "src").is_dir() else []:
        kind, name = _area_of(_rel(cs))
        if not kind or not name:
            continue
        text = cs.read_text(encoding="utf-8", errors="replace")
        for m in NAMESPACE_RE.finditer(text):
            owners.setdefault(m.group(1), (kind, name))
    return owners


def _owner_of(ns: str, owners: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """The most specific declared namespace that is `ns` or a prefix of it."""
    best: tuple[str, str] | None = None
    best_len = -1
    for declared, area in owners.items():
        if (ns == declared or ns.startswith(declared + ".")) and len(declared) > best_len:
            best, best_len = area, len(declared)
    return best


def check_boundary(rep: Report) -> None:
    """`boundary` (ERROR) — the modularity teeth, and the one check that is about the code.

    Three rules, enforced over `.csproj` `ProjectReference` elements and over `using` /
    `namespace` / `[DllImport]` text in `.cs` files:

    (a) **Platform-side code must not reference a module.** The dependency runs one way: a module
        depends on the platform and its pillars, never the reverse. The moment the host knows a
        module's type, "the app is useful with any single module and no others" stops being true.
        Platform-side means `src/platform/`, `src/shell/`, and `src/pillars/` — a pillar reaching
        into a module is the same inversion (see the note in the tool README).
    (b) **A module must not reference another module.** Modules compose over named capabilities, not
        by direct reference. One cross-reference and the two are a single unit that can only be
        lifted, shelved, or broken together.
    (c) **A Core project must contain no Windows.** No `[DllImport]`/`[LibraryImport]`, no `using` of
        a Windows-only namespace. This is the Core/Shell split (ADR 0003) and it is the reason any
        of this logic is testable without a Windows desktop at all; one P/Invoke in a Core project
        and that property is gone for the whole project.
    """
    projects = _projects()
    owners = _namespace_owners(projects)

    # (a)+(b) via project references — works even with zero source files.
    for pr in projects:
        if not pr["kind"]:
            continue
        for inc in pr["refs"]:
            target = (pr["path"].parent / inc.replace("\\", "/")).resolve()
            t_rel = _rel(target)
            t_kind, t_name = _area_of(t_rel)
            if t_kind != "module":
                continue
            if pr["kind"] in ("platform", "pillar"):
                rep.add("error", "boundary", pr["rel"], None,
                        f"{pr['kind']} project references module '{t_name}' "
                        f"(<ProjectReference Include=\"{inc}\" />)",
                        "invert it: the module references the platform/pillar, never the reverse — "
                        "expose what the module needs as a platform contract or a capability")
            elif pr["kind"] == "module" and pr["name"] != t_name:
                rep.add("error", "boundary", pr["rel"], None,
                        f"module '{pr['name']}' references module '{t_name}' "
                        f"(<ProjectReference Include=\"{inc}\" />)",
                        "modules compose over named capabilities, never by project reference — "
                        "route it through the platform's capability registry")

    # (a)+(b)+(c) via source text.
    src = REPO_ROOT / "src"
    for cs in _iter_files(src, (".cs",)) if src.is_dir() else []:
        rel = _rel(cs)
        kind, name = _area_of(rel)
        text = cs.read_text(encoding="utf-8", errors="replace")
        pr = _project_for(cs, projects)
        is_core = pr["core"] if pr else any(seg.endswith(".Core") for seg in rel.split("/")[:-1])
        has_pinvoke = bool(PINVOKE_RE.search(text))

        for m in USING_RE.finditer(text):
            ns = m.group(1)
            line = _line_of(text, m.start())
            owner = _owner_of(ns, owners)
            if owner and owner[0] == "module" and (kind, name) != owner:
                if kind in ("platform", "pillar"):
                    rep.add("error", "boundary", rel, line,
                            f"{kind} code does `using {ns};` — that namespace belongs to module "
                            f"'{owner[1]}'",
                            "invert the dependency: the platform must not know a module's types")
                elif kind == "module":
                    rep.add("error", "boundary", rel, line,
                            f"module '{name}' does `using {ns};` — that namespace belongs to module "
                            f"'{owner[1]}'",
                            "modules compose over named capabilities, never by direct reference")
            if not is_core:
                continue
            if ns.startswith(WINDOWS_ONLY_NAMESPACES):
                rep.add("error", "boundary", rel, line,
                        f"Core project ({pr['rel'] if pr else 'by *.Core path'}) does "
                        f"`using {ns};` — a Windows-only namespace in Windows-free logic",
                        "move the Windows-touching code into the Shell adapter project and keep "
                        "Core as pure decision logic (ADR 0003)")
            elif ns == "System.Runtime.InteropServices" and has_pinvoke:
                rep.add("error", "boundary", rel, line,
                        "Core project imports System.Runtime.InteropServices and P/Invokes in the "
                        "same file",
                        "P/Invoke belongs in the Shell adapter, never in a Core project (ADR 0003)")

        if is_core:
            for m in PINVOKE_RE.finditer(text):
                rep.add("error", "boundary", rel, _line_of(text, m.start()),
                        f"Core project contains a [{m.group(1)}] P/Invoke declaration",
                        "move it to the Windows-only Shell adapter — a Core project must run and "
                        "unit-test on any OS (ADR 0003)")


# --- checks: the shelving contract ---------------------------------------------------------------

def check_shelving(rep: Report) -> None:
    """`shelving` (WARN) — every module and pillar directory carries a README with a resume point.

    The shelving contract (MODULE_SPEC §7) is the single habit that makes a multi-year, put-it-down
    project survivable: a README saying what is done versus TODO, and a **"Where to resume"** section
    naming a specific next action — the file, the method, the half-finished thought. WARN rather than
    ERROR because a directory that exists but is not yet a real module is a normal in-progress state,
    and the fix is judgement about what to write, not a mechanical repair.
    """
    for kind, parent in (("pillar", "src/pillars"), ("module", "src/modules")):
        for name in _subdirs(parent):
            d = REPO_ROOT / parent / name
            readme = d / "README.md"
            if not readme.exists():
                rep.add("warn", "shelving", f"{parent}/{name}", None,
                        f"{kind} directory has no README.md",
                        "add one: what it does, its capabilities, done-vs-TODO, and a "
                        "'Where to resume' section (MODULE_SPEC §7)")
                continue
            text = readme.read_text(encoding="utf-8", errors="replace")
            if not re.search(r"^#{1,6}\s+.*where to resume", text, re.I | re.M):
                rep.add("warn", "shelving", _rel(readme), None,
                        f"{kind} README has no 'Where to resume' section",
                        "add one naming a SPECIFIC next action — the file, the method, the "
                        "decision. 'Continue the work' is not a resume point")


# --- checks: accuracy, orphans, the inbox --------------------------------------------------------

def _repo_commits_since(date_str: str) -> int | None:
    """Repo commits since the start of a `YYYY-MM-DD` date, or None when git cannot answer.

    ⚠ This is the ONE place a git failure is deliberately softened, and the asymmetry is the point.
    Staleness is an advisory churn signal that never gates, so an unavailable count degrades to
    "unknown". The CLOSEOUT check is the exact opposite: there, a git failure is an ERROR, because a
    gate that could not run must never report as a gate that passed.
    """
    try:
        out = _git(["rev-list", "--count", f"--since={date_str} 00:00:00", "HEAD"])
    except GitError:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def check_accuracy(rep: Report) -> None:
    """`accuracy` (WARN / INFO) — which docs are overdue for a re-read against the code.

    `updated` says *someone looked at the prose*; `audited` says *the prose still matches the thing
    it describes*. Only the second is a claim about truth, and only a human or an AI re-reading the
    doc can make it. This check produces the worklist: WARN when `audited` is older than the day or
    commit threshold, INFO when a living doc has no `audited` baseline at all.

    Never ERROR. Staleness is a function of time and churn, so a blocking gate would fail unrelated
    work after a quiet fortnight — and a gate that fails for reasons unconnected to the change is a
    gate people learn to bypass.
    """
    today = date.today()
    for p in _iter_md():
        rel = _rel(p)
        if (rel in FRONTMATTER_EXEMPT_EXACT or rel.startswith(FRONTMATTER_EXEMPT_PREFIXES)
                or rel in RECORD_DOCS or rel.startswith(".github/")):
            continue
        data, _ = fm.read(p)
        if data is None:
            continue                                   # check_frontmatter owns that
        if data.get("status") in {"frozen", "historical"}:
            continue                                   # accuracy pinned to its date by design
        audited = data.get("audited")
        if not audited:
            rep.add("info", "accuracy", rel, None,
                    "no `audited` date — this doc has never been accuracy-checked",
                    "re-read it against the code and set `audited: <today>` once you have confirmed "
                    "it is still true (DOC_SPEC §3)")
            continue
        try:
            ad = date.fromisoformat(str(audited))
        except ValueError:
            continue                                   # an invalid date is check_frontmatter's job
        age = (today - ad).days
        commits = _repo_commits_since(str(audited))
        reasons = []
        if age > STALE_DAYS:
            reasons.append(f"{age}d since the last accuracy pass")
        if commits is not None and commits > STALE_COMMITS:
            reasons.append(f"{commits} commits since")
        if reasons:
            rep.add("warn", "accuracy", rel, None,
                    f"accuracy stale ({'; '.join(reasons)}; audited {audited})",
                    "re-read it against the code, fix any drift you find, then bump `audited`")


def check_orphan(rep: Report) -> None:
    """`orphan` (INFO) — a canonical doc that no other doc links to.

    The wiki story is "start anywhere, reach everywhere". A doc nothing points at is either missing
    an edge or missing a reason to exist, and both are worth a look. INFO only — the generated map
    is excluded from conferring reachability (it links everything, so it would make every doc look
    connected), and roots like the README are expected to be linked *from* rather than *to*.
    """
    inbound: dict[str, int] = {}
    for md in _iter_md():
        rel_md = _rel(md)
        if rel_md == "docs/MAP.md":
            continue                    # the map links everything — it cannot confer non-orphanhood
        text = md.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            t = m.group(1).split("#")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                continue
            resolved = (md.parent / t).resolve()
            try:
                inbound[resolved.relative_to(REPO_ROOT).as_posix()] = 1 + inbound.get(
                    resolved.relative_to(REPO_ROOT).as_posix(), 0)
            except ValueError:
                pass
        data, _ = fm.read(md)
        for t in (data or {}).get("related", []) or []:
            if isinstance(t, str):
                inbound[t.strip()] = inbound.get(t.strip(), 0) + 1

    roots = {"README.md", "CLAUDE.md", "AGENTS.md",
             "docs/NEXT.md", "docs/MAP.md", "docs/INBOX.md"}
    for p in _required_frontmatter_docs():
        rel = _rel(p)
        if rel in roots or inbound.get(rel, 0):
            continue
        rep.add("info", "orphan", rel, None,
                "no other doc links here",
                "weave it into the graph — link it from the doc that owns the surrounding concern, "
                "and add a `related:` edge back")


def check_inbox_recall(rep: Report) -> None:
    """`inbox-recall` (INFO) — a captured INBOX entry with no triage route.

    Capture is free and must stay free; recall is the discipline. An entry that is still
    `Status: captured` has been safely written down and has no way out: no proposed destination, no
    NEXT item, nothing that would make it resurface. INBOX is a buffer, not an archive.

    Entry shape (DOC_SPEC / the INBOX header):
        ### <title> — YYYY-MM-DD
        Status: captured | triaged → <where it landed>
    """
    p = REPO_ROOT / "docs" / "INBOX.md"
    if not p.exists():
        return
    today = date.today()
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    heads = [(i, ln) for i, ln in enumerate(lines) if ln.startswith("### ")]
    for idx, (i, head) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        body = "\n".join(lines[i:end])
        sm = re.search(r"Status:\s*\**\s*(\w+)", body)
        # `parked` is a live, un-triaged status too — skipping it would silently exempt exactly the
        # entries most likely to be forgotten.
        if not sm or sm.group(1).lower() not in ("captured", "parked"):
            continue
        if re.search(r"triaged\s*(?:→|->)", body, re.I):
            continue                                   # a route is recorded even if not yet flipped
        title = head.lstrip("# ").strip()
        dm = re.search(r"(\d{4}-\d{2}-\d{2})\s*$", head.strip())
        age: int | None = None
        if dm:
            try:
                age = (today - date.fromisoformat(dm.group(1))).days
            except ValueError:
                age = None
        aged = f", captured {age}d ago" if age is not None else ""
        overdue = (" — past the recall window; promote it or prune it"
                   if age is not None and age > INBOX_STALE_DAYS else "")
        rep.add("info", "inbox-recall", "docs/INBOX.md", i + 1,
                f"'{title[:60]}' is still `{sm.group(1).lower()}` with no triage route"
                f"{aged}{overdue}",
                "propose a destination (NEXT.md, an ADR, TECH_DEBT, vision) and mark the entry "
                "`Status: triaged → <where it landed>`, or prune it — git keeps the history")


def check_projectref(rep: Report) -> None:
    """Every `<ProjectReference Include="...">` must resolve to a file that exists.

    A dangling ProjectReference is a build failure, but it is a build failure nobody sees until a
    machine with an SDK gets to it — and this repository's whole premise is that useful checking
    happens before that point. `check_boundary` reads the same elements and stays green on a broken
    one, because a reference to a project that does not exist crosses no architectural boundary; it
    just does not build. Those are different questions and they need different checks.

    Earned 2026-08-08, on review: renaming the three Core projects to carry a `.Core` suffix updated
    the one hand-written ProjectReference in the repository and missed the one that
    `coord new-module` WRITES, so every module scaffolded from then on would have been born with a
    reference to `Coordinator.Platform/Coordinator.Platform.csproj` — a path that no longer existed.
    Two audits and four verifiers passed it. A generated artifact is code; this check plus the
    scaffold test in tools/coord/tests/ is what makes that true mechanically.
    """
    for pr in _projects():
        base = pr["path"].parent
        for inc in pr["refs"]:
            # MSBuild accepts backslashes on every platform; normalise before touching the disk.
            target = (base / inc.replace("\\", "/")).resolve()
            if target.exists():
                continue
            rep.add("error", "projectref", pr["rel"], None,
                    f"references a project that does not exist: `{inc}`",
                    f"fix the path (resolved to {_rel(target) if str(target).startswith(str(REPO_ROOT)) else target}) "
                    "or add the missing project — this reference cannot build")


CHECKS = [
    check_frontmatter,
    check_doc_link,
    check_related,
    check_code_ref,
    check_map_sync,
    check_adr_gap,
    check_adr_format,
    check_boundary,
    check_projectref,
    check_shelving,
    check_accuracy,
    check_orphan,
    check_adr_lifecycle,
    check_inbox_recall,
]


# --- the diff-aware closeout (--since REF) --------------------------------------------------------

class GitError(Exception):
    """A git invocation, or the decoding of its output, failed.

    ⚠ NEVER SWALLOW THIS on the closeout path. A git failure that returns an empty-but-successful
    result is indistinguishable from "there is nothing to check" — which is a gate that did not run
    reporting itself as a gate that passed. That is the second of this project's three named failure
    shapes (a claim stronger than its evidence) wearing the costume of the first (a check that cannot
    fail). Callers turn it into a visible ERROR instead.
    """


def _git_bytes(args: list[str]) -> tuple[int, bytes, str]:
    """Run git; return `(returncode, stdout_bytes, stderr_text)`. Never decodes stdout.

    ⚠ Deliberately passes NEITHER `text=True` NOR `encoding=`. With `capture_output=True`, subprocess
    decodes on a reader THREAD, so a `UnicodeDecodeError` there never reaches the caller: it kills
    the thread and hands back an empty `stdout`. Docs in this repo are full of em-dashes, arrows and
    ⚠ glyphs, and a Windows console default of cp1252 would therefore turn every closeout check into
    a silent skip. Capturing bytes and decoding in our own frame makes every failure ours to see, and
    makes the result locale-independent by construction rather than by remembering an argument.
    """
    try:
        r = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True)
    except OSError as e:
        raise GitError(f"git {' '.join(args)}: could not run git ({e})") from e
    return r.returncode, (r.stdout or b""), (r.stderr or b"").decode("utf-8", "replace").strip()


def _decode(raw: bytes, what: str) -> str:
    """STRICT utf-8. A loud wrong answer is recoverable; a quiet one is not."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise GitError(f"{what}: output is not valid UTF-8 (byte {e.start}: {e.reason})") from e


def _git(args: list[str]) -> str:
    """git stdout as text. Raises `GitError` on failure — a caller must not read that as "empty"."""
    code, out, err = _git_bytes(args)
    if code != 0:
        raise GitError(f"git {' '.join(args)}: exit {code}{': ' + err[:200] if err else ''}")
    return _decode(out, f"git {' '.join(args)}")


#: `_file_at` sentinel: the path genuinely did not exist at that revision, i.e. the doc is NEW.
#: Distinct from a failure, which raises. ONLY this value may be read as "newly added".
ABSENT = object()


def _file_at(ref: str, path: str) -> str | object:
    """The file's text at `ref`, or `ABSENT` if it truly did not exist there. Raises on failure.

    ⚠ The three-way answer is the point, and collapsing it to two is how this check goes blind: a
    single `None` for both "absent from the base revision" (a legitimately new doc, correctly
    skipped) and "git or the decode failed" makes the caller skip the file either way, and the run
    reports a clean closeout while checking almost nothing. Existence is settled with `ls-tree`
    rather than by pattern-matching `git show`'s stderr, so "absent" is a fact confirmed rather than
    a message recognised.
    """
    code, out, err = _git_bytes(["ls-tree", "--name-only", ref, "--", path])
    if code != 0:
        raise GitError(f"git ls-tree {ref} -- {path}: exit {code}{': ' + err[:200] if err else ''}")
    if not _decode(out, f"git ls-tree {ref} -- {path}").strip():
        return ABSENT
    return _git(["show", f"{ref}:{path}"])


def check_closeout(rep: Report, ref: str) -> None:
    """`updated-flag` (ERROR) and `doc-touch` (WARN) — the branch-closeout pair (DOC_SPEC §6).

    Compares `<ref>...HEAD` (i.e. merge-base to HEAD) and applies two rules:

    1. **Every changed doc bumps `updated`.** The flag is a claim — "I re-read this and it is
       accurate as of this date" — so editing a doc without moving it is a silent patch. The one
       exemption: an unchanged value that already equals **today** is accepted, because the date is
       day-granular and cannot advance twice in one day. A genuinely stale value left unchanged still
       fails.
    2. **Changed code has a doc touched in the same area.** Not proof the docs are right — just the
       prompt to confirm they still describe reality while the change is fresh.
    """
    # FAIL CLOSED. "The closeout could not run" and "the closeout found nothing" must never look
    # alike: the second is a pass, the first is an unrun gate reported as a pass.
    try:
        base = _git(["merge-base", ref, "HEAD"]).strip() or ref
        changed = [l.strip() for l in _git(["diff", "--name-only", f"{ref}...HEAD"]).splitlines()
                   if l.strip()]
    except GitError as e:
        rep.add("error", "updated-flag", f"(diff {ref})", None,
                f"CLOSEOUT DID NOT RUN — {e}",
                "this is an error, not a pass: an unreachable ref (a shallow clone, an unfetched "
                "base) leaves every changed doc unchecked, and a silent skip is indistinguishable "
                "from a clean branch. Fetch the base ref and re-run")
        return
    if not changed:
        rep.add("info", "updated-flag", f"(diff {ref})", None,
                f"no committed changes versus {ref} — nothing to close out",
                "note that this mode diffs `<ref>...HEAD`, so uncommitted working-tree edits are "
                "not covered; commit first if you meant to check them")
        return

    required = {_rel(p) for p in _required_frontmatter_docs()}
    today_iso = date.today().isoformat()

    # 1) updated-flag
    for path in changed:
        if not path.endswith(".md") or path == "docs/MAP.md":
            continue
        if path in FRONTMATTER_EXEMPT_EXACT or path.startswith(FRONTMATTER_EXEMPT_PREFIXES) \
                or path.startswith(".github/"):
            continue
        cur = REPO_ROOT / path
        if not cur.exists():
            continue                                   # deleted on the branch
        new_data, _ = fm.read(cur)
        if new_data is None:
            continue                                   # check_frontmatter owns that
        try:
            old_text = _file_at(base, path)
        except GitError as e:
            rep.add("error", "updated-flag", path, None,
                    f"could not read this file at the base revision — {e}",
                    "treated as UNCHECKED, not as unchanged and not as newly added; fix the git "
                    "access and re-run before trusting this closeout")
            continue
        if old_text is ABSENT:
            continue                                   # a new doc has nothing to bump from
        old_data = fm.split_frontmatter(str(old_text))[0] or {}
        new_upd, old_upd = new_data.get("updated"), old_data.get("updated")
        new_s, old_s = str(new_upd), str(old_upd)
        # Fire when `updated` did not move FORWARD. That covers both shapes of the same lie:
        # left unchanged, and moved BACKWARD. An equality test (`old == new`) caught only the
        # first, so a doc could be edited and its date rewritten to an older one in the same
        # commit and pass silently — a check that cannot fail in the direction that matters most,
        # since a stale date is exactly what reads as "reviewed" when it was not
        # (OPERATING_MODEL §7, failure shape 1). ISO dates compare lexicographically =
        # chronologically, so `<=` is the entire rule.
        #
        # A date is day-granular and cannot advance twice in one day, so an `updated` that already
        # equals today is accepted: the doc is confirmed-fresh as of now (DOC_SPEC §3).
        #
        # Both dates must be well-formed for the comparison to mean anything. When the BASE
        # revision had no valid `updated`, adding one is an improvement, not drift — and a
        # malformed value on either side is check_frontmatter's finding, not this one's.
        if (fm.DATE_RE.match(old_s) and fm.DATE_RE.match(new_s)
                and new_s <= old_s and new_s != today_iso):
            sev = "error" if path in required else "warn"
            how = ("was not bumped" if new_s == old_s
                   else f"was moved BACKWARD (from {old_s})")
            rep.add(sev, "updated-flag", path, None,
                    f"changed on this branch but `updated` {how} (still {new_s})",
                    f"set `updated: {today_iso}` — bumping it is the claim that you re-read the doc "
                    "and it is accurate as of now (DOC_SPEC §3)")

    # 2) doc-touch — areas discovered from the tree, never hardcoded, so a new module is covered the
    # moment its directory exists.
    doc_touched = {p for p in changed if p.endswith(".md")}
    areas: dict[str, list[str]] = {
        "src/platform/": ["docs/", "src/platform/"],
        "src/shell/": ["docs/", "src/shell/"],
        "tests/": ["tests/"],
    }
    for pil in _pillar_dirs():
        areas[f"src/pillars/{pil}/"] = [f"src/pillars/{pil}/", f"docs/{pil.upper()}.md"]
    for mod in _module_dirs():
        areas[f"src/modules/{mod}/"] = [f"src/modules/{mod}/"]
    for tool in _subdirs("tools"):
        areas[f"tools/{tool}/"] = [f"tools/{tool}/"]
    for area, doc_prefixes in sorted(areas.items()):
        code = [p for p in changed if p.startswith(area) and not p.endswith(".md")]
        if not code:
            continue
        if any(d.startswith(tuple(doc_prefixes)) for d in doc_touched):
            continue
        rep.add("warn", "doc-touch", area, None,
                f"{len(code)} code file(s) changed but no doc under {area} was touched",
                "confirm the docs still describe reality while the change is fresh, and bump "
                "`updated` on whatever you re-read (DOC_SPEC §6)")


# --- reporting -----------------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty()
_SEV = {
    "error": ("31", "ERROR", "these fail the gate — a phase is not done with any outstanding"),
    "warn": ("33", "WARN", "advisory — probable drift that needs judgement, triaged in the log"),
    "info": ("36", "INFO", "advisory — a worklist, not a problem"),
}
_ORDER = ("error", "warn", "info")


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _USE_COLOR else s


def _sort_key(f: Finding) -> tuple:
    return (_ORDER.index(f.severity), f.check, f.file, f.line or 0)


def print_text(rep: Report, quiet: bool, scope: str = "full") -> None:
    for sev in _ORDER:
        items = sorted(rep.by_severity(sev), key=_sort_key)
        if not items or (quiet and sev != "error"):
            continue
        color, label, blurb = _SEV[sev]
        print()
        print(_c(color, f"── {label}S ({len(items)}) ").ljust(78, "─"))
        print(_c("2", f"   {blurb}"))
        print()
        for f in items:
            print(f"  {_c(color, label)}  {_c('1', f.location)}  {_c('2', '[' + f.check + ']')}")
            print(f"        {f.message}")
            print(f"        {_c('2', '→ ' + f.remedy)}")
    n_err, n_warn, n_info = (len(rep.by_severity(s)) for s in _ORDER)
    print()
    if scope == "accuracy":
        print(_c("32" if not (n_warn or n_info) else "33",
                 f"doc-audit --accuracy: {n_warn} stale · {n_info} un-baselined"))
        print(_c("2", "advisory worklist only — this mode never fails. Re-read each doc against "
                      "the code, then bump `audited`."))
        return
    print(_c("32" if n_err == 0 else "31",
             f"doc-audit: {n_err} error(s) · {n_warn} warning(s) · {n_info} info"))
    if n_err == 0:
        print(_c("32", "no hard code↔docs drift detected."))
    else:
        print(_c("31", "hard drift outstanding — the gate fails until these are 0."))
    print(_c("2", "a green run is a statement about text. It is not a build, and it is not a "
                  "statement about the desktop (docs/OPERATING_MODEL.md §7)."))


def print_json(rep: Report) -> None:
    print(json.dumps({
        "summary": {s: len(rep.by_severity(s)) for s in _ORDER},
        "findings": [
            {"severity": f.severity, "check": f.check, "file": f.file, "line": f.line,
             "location": f.location, "message": f.message, "remedy": f.remedy}
            for f in sorted(rep.findings, key=_sort_key)
        ],
    }, indent=2))


def main(argv: list[str]) -> int:
    global STALE_DAYS, STALE_COMMITS
    ap = argparse.ArgumentParser(
        prog="audit.py",
        description="Windows Coordinator doc-audit — the mechanical half of the audit protocol "
                    "(docs/AUDIT.md). Stdlib-only; needs no .NET.")
    ap.add_argument("--format", choices=["text", "json"], default="text",
                    help="output format (default: text)")
    ap.add_argument("--quiet", action="store_true", help="summary + ERRORs only")
    ap.add_argument("--no-fail", action="store_true", help="always exit 0 (report only)")
    ap.add_argument("--since", metavar="REF",
                    help="closeout mode: also diff <REF>...HEAD — changed docs must bump `updated`, "
                         "changed code should have a doc touched (e.g. --since origin/main)")
    ap.add_argument("--accuracy", action="store_true",
                    help="run ONLY the accuracy backlog (report-only, always exits 0)")
    ap.add_argument("--stale-days", type=int, default=STALE_DAYS,
                    help=f"accuracy staleness threshold in days (default {STALE_DAYS})")
    ap.add_argument("--stale-commits", type=int, default=STALE_COMMITS,
                    help=f"accuracy staleness threshold in repo commits (default {STALE_COMMITS})")
    args = ap.parse_args(argv)
    STALE_DAYS, STALE_COMMITS = args.stale_days, args.stale_commits

    rep = Report()
    if args.accuracy:
        check_accuracy(rep)
        print_json(rep) if args.format == "json" else print_text(rep, args.quiet, "accuracy")
        return 0

    for check in CHECKS:
        check(rep)
    if args.since:
        check_closeout(rep, args.since)

    print_json(rep) if args.format == "json" else print_text(rep, args.quiet)
    if args.no_fail:
        return 0
    return 1 if rep.by_severity("error") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
