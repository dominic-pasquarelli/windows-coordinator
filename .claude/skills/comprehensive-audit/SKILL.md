---
name: comprehensive-audit
description: >-
  Run the Windows Coordinator COMPREHENSIVE audit — the heaviest tier: the full mechanical check +
  all six judgement lenses (A–F) + the deep-audit two-blind-passes reconciliation, over the whole
  project in one sitting. Manual or Claude-suggested, NOT a per-PR gate. Use after a long or
  concept-heavy session, before a deep freeze, or after a large change or milestone. Drives
  docs/AUDIT.md "The comprehensive audit".
---

# Comprehensive audit — all six lenses plus the deep reconciliation, at once

You are running the **Windows Coordinator comprehensive audit**
([AUDIT.md §4](../../../docs/AUDIT.md) → "The comprehensive audit"). It is the **heaviest tier** and
it is **expensive on purpose**: the full mechanical check, all six judgement lenses (A–F), *and* the
deep-audit two-blind-passes, over the whole project — or a scoped subtree — in one sitting.

It is **not a per-PR gate**. It is owner-triggered, or **suggested (never forced)** by you at the
moments where a broad cross-cutting re-connect earns its cost: after a long or concept-heavy session,
before a [`/freeze`](../freeze/SKILL.md), or after a large change or milestone. Its log entry is the
single best **cold-resume artifact** this project produces, because it is the one pass that looked at
everything at once.

> **Never force it** ([OPERATING_MODEL §2](../../../docs/OPERATING_MODEL.md)). Suggest it when a
> session crosses the threshold — many new concepts, broad doc edits, an imminent freeze, the first
> successful compile — and let the owner decide. On a project built in bursts around a day job,
> friction becomes avoidance, and three avoided evenings in a row is a shelved project.

## 1. Scope it

Default = **the whole project**. The owner may scope it (a pillar, a module, "just what this session
touched").

For a **session-closeout** run, scope the *judgement* lenses to the session's footprint plus the
concepts it brushed — the changed docs, their cross-links, and any reserved or planned concept they
touched — because that is where new drift hides. The **mechanical half always covers the whole
repository**, no exceptions: it is seconds, and a scoped mechanical pass is how a broken link three
directories away survives a "clean" audit. Find the footprint with `git diff --name-only origin/main`
or the session's commits, and note the scope in the log.

## 2. Mechanical half (whole repository)

`coord audit` (i.e. `python3 tools/doc-audit/audit.py`). **ERROR must be 0** — if it is not, fix that
first: a stale index means running `coord map`; a broken link means fixing the link; a boundary
violation means the Core/Shell split has actually been broken and that outranks everything else on
this list. Also run `coord map --check`. Record the error / warn / info counts for the log.

## 3. The six judgement lenses (A–F) — drive as a parallel workflow

One agent per lens (or per lens × scope-batch), each reading the docs and code relevant to its lens
and returning **structured findings**: `{lens, severity, summary, location, recommendation,
confidence}`. The lenses, in full, are [AUDIT.md §4](../../../docs/AUDIT.md); in one line each:

- **A — alignment.** Is every doc still *true*? Verify the session's **code-grounded claims** against
  the actual source — the highest-value check after a docs-heavy session. Described == built in
  **both** directions, including built-but-catalogued-as-unbuilt. And the phrasing pass: *builds*,
  *works*, *passes*, *verified*, *tested*, *validated* — each held to its evidence.
- **B — modularity & boundaries.** Bespoke-that-should-be-platform; **any Windows type, `Windows.*` /
  `Microsoft.UI` namespace, or P/Invoke inside a Core project**; a module naming an input mechanism
  instead of declaring a trigger intent to [Conduit](../../../docs/CONDUIT.md); a module enumerating
  the desktop instead of reading an [Atlas](../../../docs/ATLAS.md) snapshot; a module reaching into
  another module; a missing shared abstraction — and its inverse, speculative platform with no
  consumer.
- **C — resumability.** Could a cold reader resume in an hour? Walk every module and pillar against
  **all five items** of the shelving contract, which
  [MODULE_SPEC §7](../../../docs/MODULE_SPEC.md#7-the-shelving-contract) owns and enumerates in full
  — do not audit from memory or from a shorter copy. The honesty clause bites on two of them: while
  there is no toolchain the tests item is *unverified: no toolchain*, never satisfied-by-default, and
  a status line about anything Windows-desktop-dependent needs a machine and a date or it is not a
  status line.
- **D — fidelity.** Does recent *behavior* still match
  [OPERATING_MODEL.md](../../../docs/OPERATING_MODEL.md)? Read artifacts, not memory: the commit log,
  the NEXT delta, the new ADRs, the audit-log entries. Never-force held? Nothing built speculatively?
  The retrofit-expensive set unchanged unless argued? Capture still frictionless?
- **E — recall, drain & lifecycle.** Did any deferral's trigger fire? Anything built-but-not-closed-out
  (shipped code with a `Proposed` ADR; a landed idea still `captured`)? Recall hooks present? Buffers
  drained — NEXT → [HISTORY](../../../docs/HISTORY.md), tech-debt rows to the ledger, triaged
  [INBOX](../../../docs/INBOX.md) entries pruned to git?
- **F — connectivity & forward-compat.** Did a *built* thing foreclose a *planned* thing it must
  connect back to? The two sharpest instances here: the **update/delivery channel** (could it carry
  this to an install already running on a machine you are not sitting at?) and **settings migration**
  (could an *additive* change extend this?). Reserved seams still open, shared-substrate promises
  honored (module identity is the concrete one), new work re-connected to every sibling and back.

Use structured-output schemas so findings return as data. **Rank, don't dump** — verify each finding
and score it by confidence, so the output is a prioritized list rather than noise.

## 4. The deep-audit two blind passes — drive as a parallel workflow

The [`/deep-audit`](../deep-audit/SKILL.md) method: **Pass A** (doc → expected code, blind to the
code) ∥ **Pass B** (code → expected docs, blind to the doc *claims*) → **reconcile** A ↔ reality,
B ↔ reality, A ↔ B. The unique payoff is the **agreed-but-wrong** finding: docs and code that match
each other while both drift from the intended design. **Blindness is the mechanism** — each pass agent
sees only its half. Scope to the concept-dense area when whole-project is too heavy.

Carry the deep-audit caveat into the write-up: **no C# here has ever been compiled**, so Pass B reads
a specification expressed in C#, not a running system. It finds documentation drift; it cannot find
behavioral drift, because there is no behavior yet.

## 5. Synthesize → classify → fix → log

Merge all three sources — mechanical, the six lenses, the deep reconciliation — **dedupe** (the same
defect will surface from two or three of them, and a triple-listed finding is not three findings), and
classify each as `real drift` or `accepted` (illustrative / historical / planned).

Then: fix the **trivial and safe** in this pass and re-run the checker; route larger items to
[NEXT.md](../../../docs/NEXT.md), [TECH_DEBT.md](../../../docs/TECH_DEBT.md), or an ADR under
`docs/decisions/`; and **surface agreed-but-wrong plus any Lens D or Lens F judgement call to the
owner** — do not auto-"fix" a design question.

**Log it** in [docs/audit-log.md](../../../docs/audit-log.md)
([AUDIT.md §7](../../../docs/AUDIT.md)): mark it **comprehensive**, name the scope, and record the
counts per lens, the three deep-audit classes, and the **ground-truth reconciliations actually
performed** — the module set listed against the README table and the roadmap, the ADR frontier against
the governance Status sections, the toolchain state against every claim that depends on it. **If it is
not logged, the audit did not happen.** Re-run `coord audit` so ERROR stays 0.

## Principles

- **Heaviest tier, rarest cadence.** The after-a-big-session, pre-freeze, post-milestone tool — never
  a gate. Suggest, do not force; the owner triggers.
- **The all-at-once view is the point.** Per-PR audits are scoped and à la carte; this one runs every
  lens together, so cross-cutting drift — a foreclosed connection, an agreed-but-wrong design drift,
  a module that is real in the tree and planned in the table — surfaces where a scoped pass walks
  straight past it.
- **Rank, don't dump.** Six lenses plus two blind passes generate a lot. Verify and rank by
  confidence. **Lens F and agreed-but-wrong get the most attention** — they are precisely what the
  cheaper audits cannot see.
- **Say what is verified and what is not.** This pass will touch every claim in the repository. Every
  one of them is held to the evidence standard ([OPERATING_MODEL §7](../../../docs/OPERATING_MODEL.md)):
  a green audit is a statement about text, a green Core test run is a statement about Core logic, and
  only [manual validation](../../../docs/runbooks/manual-validation.md) on a real desktop — recorded
  with a machine and a date — is a statement about the product.
