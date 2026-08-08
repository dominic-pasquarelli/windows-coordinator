---
title: doc-audit — the code↔documentation drift checker
tier: tool
status: living
updated: 2026-08-08
audited: 2026-08-08
module: doc-audit
related:
  - docs/AUDIT.md
  - docs/DOC_SPEC.md
  - docs/OPERATING_MODEL.md
  - docs/TECH_DEBT.md
---

# doc-audit — the code↔documentation drift checker

> The **mechanical half** of the [audit protocol](../../docs/AUDIT.md): a dependency-free,
> stdlib-only Python program that finds the drift a script *can* find — rotted links, dead path
> references, gaps in the decision log, a module that lost its resume point, a generated index that
> has fallen behind, a doc edited without re-confirming it, and the modularity violations that
> quietly turn a reusable platform back into a pile of one-offs.
>
> **One sentence:** it exists so the boring drift is free to find, leaving the audit's scarce
> attention for the six judgement lenses that need a brain — and so that ERROR means *unambiguous
> breakage*, never "someone should look at this eventually."

**Three files, no dependencies.** `audit.py` is the checker, `genmap.py` regenerates
[docs/MAP.md](../../docs/MAP.md), and `frontmatter.py` is the shared parser both use. Stdlib only,
Python 3.11+, nothing to install. `coord audit` and `coord map`
([tools/coord/README.md](../coord/README.md)) wrap them.

---

## What a green run is allowed to mean

This project has an evidence standard, and its first rule is that a successful command must mean the
claimed outcome actually occurred ([OPERATING_MODEL §7](../../docs/OPERATING_MODEL.md)). So, plainly:

**This tool has been executed.** Its own guards have been deliberately broken and observed to go red
(see [Proving a check can fail](#proving-a-check-can-fail-the-operational-rule)). What it reports
about links, paths, frontmatter, the ADR sequence and the generated map is real, and its findings are
about files that really are or are not on disk.

**No .NET SDK is present in the environment this project is authored in, so this checker never has a
compiler available.** (CI does: as of `7aef6ff` it compiles every project on Ubuntu and Windows. That
does not soften anything below — this tool's answer is textual either way, on every machine.) The
`boundary` check reads `using` directives, namespace
declarations, `[DllImport]` attributes and `.csproj` `<ProjectReference>` elements as *text*. It does
genuine work — it will catch Win32 leaking into a Core project — but a green boundary result means
*"the obvious leaks are absent"*, never *"the boundary is proven"*, and a green audit is never a
green build. That limitation is registered as **TD-3** in
[TECH_DEBT.md](../../docs/TECH_DEBT.md), not glossed.

---

## Usage

```sh
python3 tools/doc-audit/audit.py                       # full report; exit 1 if any ERROR
python3 tools/doc-audit/audit.py --quiet               # summary + ERRORs only
python3 tools/doc-audit/audit.py --format json         # machine-readable (tooling, the audit log)
python3 tools/doc-audit/audit.py --no-fail             # report only; always exit 0
python3 tools/doc-audit/audit.py --since origin/main   # branch closeout (diff-aware)
python3 tools/doc-audit/audit.py --accuracy            # only the accuracy backlog; always exit 0
python3 tools/doc-audit/audit.py --stale-days 14 --stale-commits 40    # loosen the thresholds

python3 tools/doc-audit/genmap.py                      # rewrite docs/MAP.md
python3 tools/doc-audit/genmap.py --check              # exit 1 if docs/MAP.md is stale
```

Or, the way you will actually type it:

```sh
coord audit                      # the gate
coord audit --since origin/main  # closing out a branch
coord audit --accuracy           # the daily "what needs re-reading" list
coord map --check                # is the index current?
```

### The modes, and when each one is the right one

| Mode | What it does | Reach for it when |
|---|---|---|
| *(default)* | Every check in the table below, over the whole repository. Exits **1** if any ERROR. | Before you call a phase done, before you shelve a module, and any time you have been away. |
| `--quiet` | Same checks; prints only the ERROR group and the summary. | CI logs, and any run where you only care whether the gate is green. |
| `--format json` | The same findings as `{summary, findings[]}`, each with `severity`, `check`, `file`, `line`, `message`, `remedy`. | Feeding another tool, or pasting counts into [audit-log.md](../../docs/audit-log.md). |
| `--no-fail` | Runs everything, always exits 0. | Looking at the current state without a non-zero exit derailing a script. Never use it *as* the gate — that turns the gate into a comment. |
| `--since <ref>` | Adds the two diff-aware closeout checks on top of the full run: `updated-flag` and `doc-touch`, comparing `<ref>...HEAD`. | Closing out a branch, exactly as [DOC_SPEC §6](../../docs/DOC_SPEC.md) describes. |
| `--accuracy` | Runs **only** `accuracy`, and always exits 0. | The periodic sweep: "which docs are overdue for a re-read against the code?" |

`--since` diffs `<ref>...HEAD`, i.e. from the merge base to the last **commit**. Uncommitted
working-tree edits are therefore not covered — commit first if you meant to check them.

---

## What it checks

Sixteen checks. The ids are stable, and **this table is their single canonical home** —
[AUDIT.md §8](../../docs/AUDIT.md) discusses what the mechanical half can and cannot judge, and
links here for the list itself rather than keeping a second copy.

| Check | Severity | Catches |
|---|---|---|
| `frontmatter` | ERROR | A required doc with missing or invalid frontmatter — an unknown tier, an unknown status, a malformed date, or a **UTF-8 BOM** (which parses as "no frontmatter" while the file looks perfect in every editor). |
| `doc-link` | ERROR | A relative Markdown link to a repo file that does not exist. |
| `related` | ERROR | A `related:` frontmatter edge that does not resolve. These are **repo-root-relative**, unlike body links. |
| `code-ref` | ERROR | An inline-code token that looks like a repo path (`src/…`, `tools/…`, `tests/…`, `docs/…`, `.github/…`) and does not exist. |
| `map-sync` | ERROR | [docs/MAP.md](../../docs/MAP.md) differs from a fresh generation. |
| `adr-gap` | ERROR | A gap or a duplicate in the `docs/decisions/NNNN-…` sequence. |
| `adr-format` | ERROR | An ADR missing its `Date:` or `Status:` header — without which it is invisible to the lifecycle checks. |
| `boundary` | ERROR | Platform-side code referencing a module; a module referencing another module; Windows inside a **Core** project. The modularity teeth — see below. |
| `projectref` | ERROR | A `<ProjectReference>` pointing at a `.csproj` that does not exist. Cheap, and it catches the exact regression that motivated it: a project renamed without updating the generator that emits references to it. Textual, so it works with no compiler — which is the point, because without a compiler nothing else would notice until CI. |
| `shelving` | WARN | A module or pillar directory with no `README.md`, or a README with no **"Where to resume"** section. |
| `updated-flag` | ERROR *(`--since` only)* | A doc changed on the branch whose `updated` **did not move forward** — which covers both shapes of the same lie: left unchanged, and *moved backward*. An unchanged value is **accepted when it already equals today** (a date is day-granular and cannot advance twice in one day). Both dates must be well-formed for the comparison to mean anything; adding a date where the base revision had none is an improvement, not drift. |
| `doc-touch` | WARN *(`--since` only)* | Code changed under an area with no doc under that area touched. |
| `accuracy` | WARN / INFO | `audited` older than 7 days **or** more than 15 commits (WARN); a living doc with no `audited` baseline at all (INFO). |
| `orphan` | INFO | A canonical doc that no other doc links to. |
| `adr-lifecycle` | INFO | A `Proposed` ADR whose number appears nowhere in [NEXT.md](../../docs/NEXT.md) (no recall hook), or an aged `Accepted` ADR that reads as a shipped one-shot with no closure token (no drain). |
| `inbox-recall` | INFO | An [INBOX.md](../../docs/INBOX.md) entry still `captured`/`parked` with no triage route recorded. |

**Exemptions, and why each one exists.**

- **No frontmatter at all** on `docs/decisions/*` (ADRs use their own dated header), `CLAUDE.md` and
  `AGENTS.md` (standing instruction files with their own shape), `.claude/` (Claude Code owns that
  schema) and `.github/pull_request_template.md` (YAML would render as literal text).
- **No `audited:` key** — and therefore no `accuracy` finding — on the four append-only record docs:
  `docs/MAP.md`, `docs/INBOX.md`, `docs/audit-log.md`, `docs/HISTORY.md`. Each is a summary as of its
  own date, so "is this still true?" is not a meaningful question to ask it.
- **`code-ref` skips dated records** — `docs/decisions/`, `docs/freezes/`, and `docs/audit-log.md`.
  A dated ADR is correct as of its date even after the tree moves, and the audit log *records* drift
  by naming the dead paths it found; failing on those would punish the log for doing its job.
- **Placeholders and build outputs** are skipped by `code-ref`: any token containing `*`, `<`, `>`,
  `{`, `}`, `…`, `?`, `|`, or `NNNN`, and any path with a `bin`/`obj`/`out`/`TestResults`/
  `node_modules` segment.

---

## The boundary check — the modularity teeth

This is the only check that is about the *code*, and it is the one worth understanding before you
trust it. It enforces three rules from [ADR 0003](../../docs/decisions/0003-the-core-shell-split.md),
[ADR 0005](../../docs/decisions/0005-conduit-modules-declare-trigger-intents.md) and
[ADR 0006](../../docs/decisions/0006-atlas-one-canonical-desktop-model.md):

1. **Platform-side code must not reference a module.** The dependency runs one way. The moment the
   host knows a module's types, "the app is useful with any single module and no others" stops being
   true, and every future module inherits a coupling nobody chose.
2. **A module must not reference another module.** Modules compose over named capabilities. One
   cross-reference and the two can only be lifted, shelved, or broken together — which is exactly the
   property the module boundary exists to prevent.
3. **A Core project must contain no Windows.** No `[DllImport]` or `[LibraryImport]`, no `using` of
   `System.Windows.*`, `Microsoft.UI.*`, `Microsoft.Win32.*`, `Windows.*`, and no
   `System.Runtime.InteropServices` in a file that also P/Invokes. One P/Invoke in a Core project and
   the host-testability of the whole project is gone.

**How it decides what is what — by reading, not guessing.**

- **Projects** come from every `.csproj` in the tree. `<TargetFramework>` / `<TargetFrameworks>` is
  read from the file itself, and `<ProjectReference Include="…">` paths are resolved relative to the
  referring project. Malformed XML falls back to a regex rather than silently disabling the check.
- **A project is Core** if its path contains a `*.Core` project directory **or** its declared target
  frameworks all lack a `-windows` suffix. A project that declares no framework at all is treated as
  *not* Core — manufacturing findings against a project whose shape nobody has stated would be noise.
- **Namespace ownership** is built from the `namespace` declarations actually present in `src/`, so
  the check follows whatever naming the code settles on rather than a convention hard-coded here. It
  is seeded with `Coordinator.Modules.<Name>` and `Coordinator.<Name>` for each directory under
  `src/modules/`, so a `using` of a module that has a directory but no source yet is still caught.
  Lookup takes the **most specific** declared namespace that is a prefix of the `using`.
- **A `.cs` file's project** is the nearest enclosing `.csproj`, found by walking up the tree.

**One deliberate scope choice worth flagging:** "platform-side" here means `src/platform/`,
`src/shell/` **and** `src/pillars/`. A pillar reaching into a module is the same dependency inversion
as the host doing it — Conduit is a substrate every module builds on, so it cannot know about one.
The rule is usually stated as "platform importing a module"; this implementation reads that as the
architectural *direction* rather than the literal directory, and the finding message names which of
the two it was.

**What it cannot see** (TD-3): reflection, a fully-qualified type name written inline, a source
generator, or a package that drags Windows types in transitively. It reads text. It catches the
ordinary way the rule gets broken — someone adding an import — and that is worth having, but the
honest replacement is a Roslyn analyzer or an assembly-reference check once a toolchain exists.

---

## What it deliberately does **not** check

The checker reads text; it does not understand it. It structurally cannot tell you:

- whether a doc is still **true**, as opposed to still **present** — only whether a path still exists;
- whether a solution is **bespoke when it should be reusable**, or whether the same layout math has
  been written twice in two modules;
- whether two docs are quietly **restating** the same concern instead of cross-linking;
- whether [NEXT.md](../../docs/NEXT.md) points at a **useful** next step or a finished one;
- whether a "manually validated" claim ever actually **happened** on a real desktop;
- whether a design **forecloses** something it will later have to connect back to.

Those are Lenses A–F in [AUDIT.md §4](../../docs/AUDIT.md), and they need a person or an AI. The
division of labor is the point: this script makes the mechanical drift free to find so the judgement
half has attention left to spend.

It also does not distinguish a path that is missing because it was **deleted** from one that is
missing because it was **never built yet**. That classification is a human step in the audit
workflow, not a thing a checker can infer.

---

## Extending it

Adding a check is a drop-in:

1. Write `check_<id>(rep: Report) -> None` in `audit.py`.
2. Report findings with `rep.add(severity, check_id, file, line_or_None, message, remedy)`. The
   **remedy** is not optional decoration — a finding that does not say what to do about it gets
   scrolled past.
3. Append the function to the `CHECKS` list.
4. Add a row to the table above. **This file is the single home of that table** — tool docs live
   with their code ([DOC_SPEC §2.1](../../docs/DOC_SPEC.md)), and [AUDIT.md §8](../../docs/AUDIT.md)
   links here rather than restating it. It used to carry a second copy, and within one authoring
   pass the two had already disagreed on four rows — the docs lying about the tool that checks the
   docs. Do not reintroduce it.

**Severity is a contract, not a preference.** ERROR is reserved for breakage nobody would argue
about: a link that does not resolve, a sequence with a hole, a boundary that has been crossed.
Everything requiring judgement is WARN or INFO. This is what keeps the gate meaningful — a gate that
fires on debatable findings is a gate people learn to bypass, and at that point the ERRORs stop being
read too.

Known, reasoned exceptions belong in the allow-lists at the top of `audit.py` (`CODE_REF_ALLOW`,
`EPHEMERAL_SEGMENTS`, `FRONTMATTER_EXEMPT_*`, `RECORD_DOCS`), each with a comment naming the doc that
justifies it. Weakening a check to make a finding disappear is the failure mode these lists exist to
prevent — an exception with a stated reason is fine; a silently narrowed pattern is not.

### Proving a check can fail (the operational rule)

> **When you add a guard, prove it fails without the fix.**

A check whose pattern silently matches nothing reports success forever and is indistinguishable from
a comment. That is the first of this project's three named failure shapes — *a check that cannot
fail* — and it is at its most dangerous inside the tool that enforces the project's standards.

So: build the violation on purpose, watch it go red, then repair it and watch it go silent. The
cheapest way is a throwaway fixture repository — copy these three files into `<fixture>/tools/
doc-audit/` (they locate the repo root from their own path, so the copy audits the fixture, not this
repo), write the offending files, and run it. Include a **negative control** in the same fixture: for
the boundary check, the identical `[DllImport]` inside a `net9.0-windows…` Shell adapter project must
stay silent, which is what proves the check discriminates rather than merely matching a string.

This tool's checks were exercised exactly that way at bootstrap, including the counterfactual for the
`SKIP_DIRS` bug described below. There is still **no automated self-test suite** — that gap is
registered as **TD-8** in [TECH_DEBT.md](../../docs/TECH_DEBT.md), and until it is closed, "break it
on purpose" is the standing practice rather than a nicety.

---

## Two implementation details that are load-bearing

**`SKIP_DIRS` is matched against the path *relative to the repo root*, never against
`Path.parts`.** Using `p.parts` also tests every ancestor directory *above* the checkout, so a clone
living under any directory named `build/`, `dist/`, `out/`, `venv/`, or `scratchpad/` — which is
where sandbox and CI working directories routinely land — would skip **every file in the project**,
generate an empty index, and report a confident, silent success. The comment in both files says so;
please do not "simplify" it back.

**The map generator is deterministic — a pure function of the doc set.** No timestamps, no ordering
by modification time, POSIX-relative sort keys so Windows and Linux emit identical bytes, and a
`updated` field derived from the newest `updated` among the docs it lists. That is what makes
`coord map --check` a real gate instead of a generator of spurious diffs.

**Git failures fail closed on the closeout path, and only there.** `--since` treats an unreachable
ref or an undecodable diff as an **ERROR**, because a gate that could not run must never report as a
gate that passed. The one place a git failure is softened is the commit count inside `accuracy`,
which is advisory and never gates — an unavailable count degrades to "unknown". The asymmetry is
deliberate.

---

## See also

- [docs/AUDIT.md](../../docs/AUDIT.md) — the audit protocol: the six judgement lenses this tool
  cannot replace, the severity contract, the workflow, and where findings go.
- [docs/DOC_SPEC.md](../../docs/DOC_SPEC.md) — the documentation contract this tool enforces:
  placement, tiers, the frontmatter schema, the `updated`/`audited` distinction, closeout, freeze.
- [docs/OPERATING_MODEL.md](../../docs/OPERATING_MODEL.md) — the evidence standard, its three failure
  shapes, and the prove-the-guard-fails rule.
- [tools/coord/README.md](../coord/README.md) — the CLI that wraps all of this.
