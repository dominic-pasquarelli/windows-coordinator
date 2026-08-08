---
name: freeze
description: >-
  Put the whole Windows Coordinator project "on ice" — run the save-point ceremony that certifies the
  project is resumable from cold after months away, then write a dated freeze record. Use when the
  user says to "freeze", "save point", "put this on ice", "I'm stepping away", "bank this milestone",
  or wants to shelve the entire project (not just one module). Implements DOC_SPEC §7 +
  docs/freezes/.
---

# Freeze mode — project save point

You are running the **freeze ceremony**: a deliberate, certified save point for the *whole project*,
so it can be put down and picked back up without friction. It is the macro version of the module
shelving contract — that one certifies a module; a freeze certifies everything at once, including the
connective tissue between modules that no individual shelving check ever looks at.

The gate and the record format live in
[docs/freezes/README.md](../../../docs/freezes/README.md) and
[DOC_SPEC §7](../../../docs/DOC_SPEC.md); the checks are
[docs/AUDIT.md](../../../docs/AUDIT.md).

> **Do not declare the project frozen until every gate item passes or is honestly recorded as unmet.**
> A false freeze is worse than none — it banks rot as safe. See "The rule" below; it is the whole
> reason this ceremony exists.

## The rule you must not bend

**A freeze is a certification, and its entire value is that a future reader can trust it without
re-deriving it.** That trust is an asset, and it is *spent* — not earned — by a freeze that was not
actually run.

The damage has a specific mechanism. A cold reader opening this repository after eight months reads
the newest freeze record **first** and treats it as ground truth: this compiled, that was validated,
this module is resumable, that decision is settled. Then they build on top of it. If any of those
claims was rounded up, they have been handed a false map at exactly the moment they have the least
context to detect it, and the cost surfaces later, tangled into whatever they were actually doing —
which is failure shape 3, *an error found after the expensive step*
([OPERATING_MODEL §7](../../../docs/OPERATING_MODEL.md)).

> **A freeze with an honest gap is a good freeze. A freeze with a tick it did not earn is a lie with
> a date on it.**

If the gate cannot pass and the user must stop anyway — which is allowed; life happens — **do not
write a freeze record at all.** Update [docs/NEXT.md](../../../docs/NEXT.md) with the honest state
and stop there. An un-frozen project that says so is recoverable. A falsely-frozen one is a trap.

## Run the gate, in order

1. **Mechanical drift → zero ERROR.**
   - `coord audit` over the whole repository must be **0 ERROR**.
   - `coord audit --since origin/main` (closeout) must be **0 ERROR** — every changed doc bumped its
     `updated`, no boundary breaks. Fix anything red before continuing. This is the point of the
     step, not an obstacle to it.

2. **Verification status — Core tests green, *and* an explicit, honest statement of what is
   unverified because it needs a real Windows desktop.** Both halves are required; the second is not
   a fallback for the first.
   - Run `coord test`. Record **the real result — the actual exit status and output you observed**,
     never the result you expected. If the command could not run, that *is* the result: write "not
     runnable" and why. **You may never write that the C# builds, compiles, tests, or works on the
     strength of anything other than a compiler you watched run**, and there is no .NET SDK here.
   - Then write the sentence that names what a green run does **not** cover — because a Core suite is
     `net9.0` logic only and touches no Shell adapter, no window placement, no hotkey capture, no
     DPI behavior, no tray, no UI. Every one of those is
     [runbooks/manual-validation.md](../../../docs/runbooks/manual-validation.md), performed by a
     human, on a named machine, on a date. **Undated validation is not validation.**
   - **Today this gate item cannot be ticked at all.** No .NET SDK has ever been present in the
     environment this repository was authored in; no C# in it has ever been compiled. The correct
     record entry is not a blank and not a tick:

     ```
     C#: never compiled (no toolchain has ever been present — TD-1).
     Core tests: not runnable.
     Python tooling (coord, doc-audit): executed and verified.
     Manual validation: never performed — nothing has ever run on Windows.
     ```

     That is a **legitimate freeze**. What would not be legitimate is a ticked box, or the phrase
     "tests pass" standing in for "the tooling ran." Never let a green `coord audit` — which is a
     statement about *text* — drift into sounding like a green build.
   - Once a toolchain exists, the same discipline applies one level up: a green build proves the C#
     **compiles**. Compiling is not running, and running is not working.

3. **The map is current.** Run `coord map`. If it changed, the index had drifted — commit the
   regeneration as part of the freeze, and note in the record that it had drifted, because that is a
   small signal about how the last stretch of work went.

4. **Shelving contract, per module and per pillar.** For each, confirm **all five** items:

   1. **A README** stating what it does, what's **done vs. TODO**, and what capabilities it
      publishes.
   2. **A "Where to resume" section** — in the README or the module's `docs/NEXT.md` — naming a
      **specific next action**: the function, the decision, the test that is failing. Not "continue
      work on layouts."
   3. **ADRs for the non-obvious decisions**, in the unified decision log, so future-you does not
      re-litigate a settled call or quietly reverse it.
   4. **Tests that pass** — `coord test` green for the module's Core project. **While there is no
      toolchain this item cannot be ticked at all** — record it as *unverified: no toolchain*, never
      as satisfied-by-default.
   5. **An honest status line** on anything Windows-desktop-dependent: what was manually validated,
      on what machine, with what monitor arrangement and scaling, and when. Undated validation is
      not validation.

   *(Mirrors [MODULE_SPEC §7](../../../docs/MODULE_SPEC.md#7-the-shelving-contract) — if these
   disagree, §7 wins.)*

   The `shelving` check covers *presence*; **you** judge sufficiency. "Continue work on layouts" is
   not a resume anchor. "The multi-monitor path is stubbed at the work-area union — decide whether a
   zone may span monitors before writing it" is.

5. **Resume anchors are specific.** [NEXT.md](../../../docs/NEXT.md) Active focus — and each module's
   own resume section — must name a concrete next action: a file, a method, a decision, a failing
   test. Tighten anything vague now, while the state is still warm. This is the one line a cold
   reader trusts completely and verifies least.

6. **Drain the buffers.** A freeze is the natural drain point — git is the archive, and
   [HISTORY.md](../../../docs/HISTORY.md) holds the shipped history. The `inbox-recall` and
   `adr-lifecycle` advisories are the pre-screen:
   - **[INBOX](../../../docs/INBOX.md)** — every entry is either `captured` *with a recall hook*, or
     `triaged → <where it landed>`. Prune the landed `triaged` entries to git: the INBOX is a
     *buffer, not an archive*.
   - **ADRs** — a decision whose code shipped is `Accepted`, not `Proposed`. A fully-shipped one-shot
     gets a closure token on its Status line (`Status: Accepted · Closed <date>`, or
     `· Superseded by ADR NNNN`) so the actively-guiding set stays a one-line grep.
   - **[NEXT.md](../../../docs/NEXT.md)** — settled "landed" blocks move to
     [HISTORY.md](../../../docs/HISTORY.md). NEXT is active work only; a NEXT full of completed
     history is a resume anchor buried in a changelog.
   - **[TECH_DEBT.md](../../../docs/TECH_DEBT.md)** — paid-down rows move to the ledger, and every
     remaining active row still names the trip-wire that brings it back.

   Draining happens **at a freeze or at a threshold, never as a gate** on ordinary work.

## Then write the record

Create `docs/freezes/YYYY-MM-DD-<label>.md` — the date it was taken, plus a short kebab-case label
naming what was banked (`bootstrap`, `first-compile`, `zones-shipped`). Ask the user for the date if
you cannot determine it; **never invent one.** Use the skeleton in
[docs/freezes/README.md](../../../docs/freezes/README.md) and fill:

- **Health at freeze** — the real numbers from steps 1–3: audit counts, closeout result, map state,
  the C# compile state, the Core test result, and the manual-validation line. This is the block a
  cold reader will believe without checking, so it is the block where rounding up does the most
  damage.
- **State of the world** — what is done, what is in flight, what is deliberately deferred and why.
  **Link, do not restate** (single-source rule, [DOC_SPEC §4](../../../docs/DOC_SPEC.md)).
- **Resume here** — mirroring NEXT.md's Active focus: the one action to take first on return,
  specific enough to start on without reading anything else.
- **Open risks / carry-forwards** — what is most likely to have decayed, or to bite whoever comes
  back. Name the trip-wires.
- **Per-module shelving table** — tests, README, where-to-resume, manually-validated, notes. Write
  `unverified: no toolchain` where that is the truth; the honest gap is the most useful cell in the
  table.

Write both weight-bearing sections — *Health at freeze* and *Resume here* — as if you will not be
available to clarify them. That is the actual situation.

Then:

- Set the record's frontmatter `status: historical`. It is **immutable** once written: a
  summary-as-of-its-date, never edited to stay true. If it later turns out to be wrong, that belongs
  in the *next* record and in [audit-log.md](../../../docs/audit-log.md), not in a retroactive
  correction. (For the same reason it carries no `audited:` key.)
- Point [docs/NEXT.md](../../../docs/NEXT.md) at the new record and bump its `updated`.
- Consider setting `status: frozen` on modules genuinely going dormant.
- Re-run `coord map` (the new record shifts the index) and `coord audit` to confirm still-green.
- A **comprehensive audit** ([`/comprehensive-audit`](../comprehensive-audit/SKILL.md)) before a deep
  freeze is worth its cost: it certifies the *interconnected* state, not merely each doc individually.

## Report

End with a tight certification: the gate results (audit, closeout, tests, map), the path to the
freeze record, and the single "resume here" line — so the user knows exactly what was banked and
where to restart.

State the unverified half in the same breath as the verified half, in plain words: what the Python
tooling actually proved, and what remains unproven because no compiler and no Windows desktop have
touched this. That sentence is the freeze's honesty, and it is what makes the record worth trusting.

Do not commit or push unless the user asked. Present the record and let them decide.
