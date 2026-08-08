---
title: Freezes — project save points (on-ice records)
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/DOC_SPEC.md
  - docs/AUDIT.md
  - docs/MODULE_SPEC.md
  - docs/NEXT.md
  - docs/HISTORY.md
  - docs/INBOX.md
  - docs/OPERATING_MODEL.md
---

# Freezes — project save points

> Dated records of every time the **whole project** was put on ice — deliberately swept, certified
> resumable from cold, and parked. This is the macro version of the module shelving contract
> ([MODULE_SPEC §7](../MODULE_SPEC.md#7-the-shelving-contract)): that one certifies a module; a freeze certifies *everything
> at once*, including the connective tissue between the modules that no individual shelving check
> looks at.
>
> **One sentence:** a freeze answers one question for a future reader — *"if I open this repository
> cold, what is the state, and where exactly do I put my hands?"* — and it is only trustworthy
> because the gate below was actually run before the record was written.
>
> Run by the [`/freeze` skill](../../.claude/skills/freeze/SKILL.md). The *why* underneath it is
> [DOC_SPEC §7](../DOC_SPEC.md) and [OPERATING_MODEL §4](../OPERATING_MODEL.md); the checks are
> [AUDIT.md](../AUDIT.md).

---

## 1. What a freeze is

Windows Coordinator is built in bursts around a day job, and its whole bet is that it can be put down
for months and picked up cold in about an hour. A **freeze** is where that bet is *tested and banked*
rather than assumed.

It is heavier than a phase-end audit and heavier than shelving a module. A phase-end audit checks the
subtree you touched. A shelving pass checks one module. A freeze checks that **every** module and
pillar is resumable, that the buffers are drained, that the map is current, that the resume anchors
point at real next actions, and that the honest status of the whole system is written down in one
place a cold reader will find first.

The record it produces is not a summary of what you built. It is a **hand-off letter to a stranger who
happens to be you**, written while you still remember which parts are load-bearing.

---

## 2. When to freeze

**Freeze when:** you are stepping away from the *project* — not just one module — for a while, or you
have reached a milestone worth banking before attention moves elsewhere.

**Do not freeze when:** you are simply finishing a session, or putting down one module. Those are
covered by [NEXT.md](../NEXT.md) staying current and by the shelving contract. Freezing every time
turns the ceremony into paperwork, and paperwork gets skipped precisely when it matters most.

**A good instinct for the timing:** freeze when you notice you are *about* to start something new and
unrelated. The freeze is cheap while the state is warm and expensive once it is not.

---

## 3. The gate — all of it must pass

If any item fails, **you are not frozen — you are stalled with a false sense of safety.** Fix it and
re-run. There is no partial freeze.

| # | Gate | How it is satisfied |
|---|---|---|
| 1 | **Zero ERROR drift** | `coord audit` reports 0 ERROR ([AUDIT §5](../AUDIT.md)) |
| 2 | **Closeout audit clean** | `coord audit --since origin/main` reports 0 ERROR — every doc changed on the branch re-confirmed its `updated` flag |
| 3 | **Tests green, or an honest statement of what is unverified** | `coord test` green — **or** a plain sentence naming exactly what has not been verified and why. See §3.1 |
| 4 | **The map is current** | `coord map --check` passes; [MAP.md](../MAP.md) reflects the real doc set |
| 5 | **Every module and pillar meets its shelving contract** | walked one by one against all five items of [MODULE_SPEC §7](../MODULE_SPEC.md#7-the-shelving-contract) — see §3.3 |
| 6 | **Resume anchors are specific** | [NEXT.md](../NEXT.md) Active focus and every module's `docs/NEXT.md` name a *specific next action* — a file, a method, a decision, a failing test. Not "continue work on X" |
| 7 | **The buffers are drained** | §3.2 |

### 3.1 "Tests green **or** an honest statement" is not a loophole

It is the honest form of the gate, and it is load-bearing for this project specifically.

**Today, a freeze could not tick item 3 at all.** No .NET SDK has ever been present in this
repository's environment; **not one line of C# has been compiled** (**TD-1** in
[TECH_DEBT.md](../TECH_DEBT.md)). The correct record entry is not a blank and not a tick — it is:

> `C#: never compiled (no toolchain has ever been present). Core tests: not runnable.`
> `Python tooling: executed and verified. Manual validation: never performed.`

That is a legitimate freeze. What would **not** be legitimate is a ticked box, or a phrase like
"tests pass" standing in for "the tooling ran." A freeze that rounds an unverified state up to a
verified one is the failure this whole ceremony exists to prevent — see §4.

The same rule governs anything desktop-dependent: state **what** was manually validated, **on what
machine**, with **what monitor arrangement and scaling**, and **when**
([runbooks/manual-validation.md](../runbooks/manual-validation.md)). Undated validation is not
validation.

### 3.2 Draining the buffers

Capture is free; **recall and drain are the discipline** ([OPERATING_MODEL §3](../OPERATING_MODEL.md)).
A freeze is the natural moment to drain, because the alternative is a working set that slowly fills
with settled noise until the live items are unfindable.

- **[INBOX.md](../INBOX.md)** — every entry is either `captured` **with a recall hook**, or
  `triaged → <where it landed>`. Landed `triaged` entries are **pruned to git**: the INBOX is a
  buffer, not an archive, and git keeps the history.
- **ADRs** — a decision whose code shipped is `Accepted`, not `Proposed`. A fully-shipped one-shot
  gets a **closure token** on its Status line (`Status: Accepted · Closed <date>`, or
  `· Superseded by ADR NNNN`) so the actively-guiding set stays a one-line grep.
- **[NEXT.md](../NEXT.md)** — settled "landed" blocks move to [HISTORY.md](../HISTORY.md). NEXT is
  **active work only**; a NEXT full of completed history is a resume anchor buried in a changelog.
- **[TECH_DEBT.md](../TECH_DEBT.md)** — paid-down rows move to the ledger; every remaining active row
  still has a **trip-wire** saying what brings it back.

Draining is done **at a freeze or at a threshold, never as a gate** on ordinary work. A blocking
"you may not defer" rule would violate capture-is-free outright, and capture must stay frictionless or
it stops happening ([AUDIT.md Lens E](../AUDIT.md)).

### 3.3 The shelving contract, in full (gate item 5)

Walk every module and every pillar against **all five** items. A four-item walk is how a module gets
banked as resumable while its least-verified dimension goes unrecorded.

1. **A README** stating what it does, what's **done vs. TODO**, and what capabilities it publishes.
2. **A "Where to resume" section** — in the README or the module's `docs/NEXT.md` — naming a
   **specific next action**: the function, the decision, the test that is failing. Not "continue work
   on layouts."
3. **ADRs for the non-obvious decisions**, in the unified decision log, so future-you does not
   re-litigate a settled call or, worse, quietly reverse it.
4. **Tests that pass** — `coord test` green for the module's Core project. Not "feature-complete";
   just "correct as far as it goes." **Until a .NET SDK is present, this item cannot be ticked at
   all** — record it as *unverified: no toolchain*, never as satisfied-by-default (§3.1).
5. **An honest status line** on anything Windows-desktop-dependent: what was manually validated, on
   what machine, with what monitor arrangement and scaling, and when. Undated validation is not
   validation.

*(Mirrors [MODULE_SPEC §7](../MODULE_SPEC.md#7-the-shelving-contract) — if these disagree, §7 wins.)*

---

## 4. A false freeze is worse than no freeze

**A freeze is a certification, and its whole value is that a future reader can trust it without
re-deriving it.** That trust is the asset, and it is spent — not earned — by a freeze that was not
actually run.

The mechanism of the damage is specific. A cold reader opening this repository after eight months
reads the newest freeze record *first*, and treats it as ground truth: this compiled, that was
validated, this module is resumable, that decision is settled. They then build on top of it. If any of
those claims was rounded up, the reader has been handed a false map at exactly the moment they have
the least context to detect it — and the cost surfaces later, mixed in with whatever they were
actually doing, which is failure shape 3: *an error found after the expensive step*
([OPERATING_MODEL §7](../OPERATING_MODEL.md)).

Worse, the damage compounds. A freeze that banks rot as safe makes the *next* freeze harder to trust
too, and once the records stop being trusted they stop being read — at which point you have paid the
entire cost of the ceremony and receive none of the benefit.

> **The rule:** a freeze with an honest gap is a good freeze. A freeze with a tick it did not earn is
> a lie with a date on it.

If the gate cannot pass and you must stop anyway — which is allowed; life happens — **do not write a
freeze record.** Update [NEXT.md](../NEXT.md) with the honest state and stop. An un-frozen project
that says so is recoverable; a falsely-frozen one is a trap.

---

## 5. The record

One file per freeze, in this directory:

**`YYYY-MM-DD-<label>.md`** — the date it was taken, and a short kebab-case label naming what was
banked (`bootstrap`, `first-compile`, `zones-shipped`). Newest matters most, but every record is kept:
together they are the project's long-term health history.

A freeze record carries `status: historical` and is **immutable once written**. It is a
summary-as-of-its-date, not a living claim about current code, so it is never edited to stay true —
if it later turns out to have been wrong, that fact belongs in the *next* record and in
[audit-log.md](../audit-log.md), not in a retroactive correction. (For the same reason a record
carries no `audited:` key — [DOC_SPEC §3](../DOC_SPEC.md).)

### 5.1 The skeleton

```markdown
---
title: Freeze — <label>
tier: meta
status: historical
updated: YYYY-MM-DD
---

# Freeze — YYYY-MM-DD — <label>

## Health at freeze
- audit: N error / N warn / N info   ·   closeout (vs origin/main): clean
- map: current
- C#: <never compiled | builds, SDK X on machine Y, YYYY-MM-DD>
- Core tests: <N/N passing on <OS> | not runnable — no toolchain>
- Manual validation: <scenarios run, machine, monitor arrangement + scaling, date | never performed>

## State of the world (one screen)
What is done, what is in flight, what is deliberately deferred and why.
Link, do not restate ([DOC_SPEC §4](../DOC_SPEC.md)).

## Resume here
1. The single most important next action — mirroring NEXT.md's Active focus, specific enough
   to start on without reading anything else.
2. …

## Open risks / carry-forwards
- The things most likely to have decayed, or to bite whoever comes back. Name the trip-wires.

## Per-module shelving status
<!-- one column per MODULE_SPEC §7 item, in order — all five, every row -->
| Module / pillar | README | Where to resume | ADRs | Tests | Manually validated |
|---|---|---|---|---|---|
| <name> | ✓ done-vs-TODO | ✓ specific | ✓ \| none needed | <n/n \| unverified: no toolchain> | <what, on what machine, when \| never> |

## Buffers drained
- INBOX: <n> pruned, <n> still captured with hooks   ·   ADRs: <n> given closure tokens
- NEXT → HISTORY: <what moved>   ·   TECH_DEBT: <rows paid down>
```

**The two sections that carry the most weight** are *Health at freeze* — because it is the line a cold
reader will believe without checking — and *Resume here* — because it is the line they will act on.
Write both as if you will not be available to clarify them, which is the actual situation.

---

## 6. Resuming from a freeze

1. **Open the newest record** and read *Resume here* and *Health at freeze*.
2. **Read [NEXT.md](../NEXT.md)** — the record mirrors its Active focus, but NEXT is the living one.
3. **Run `coord audit` before trusting anything.** If it is green, the freeze held and the docs can be
   trusted. If it is not, the freeze **decayed** — something changed outside a freeze — and the audit
   findings are your first task, ahead of whatever you came to do.
4. **Run `coord map --check`** — a stale index means the doc set moved since the record.
5. **Then, and only then**, do the thing the record told you to do.

Step 3 is the one people skip, and it is the one that protects against the failure mode this ceremony
cannot prevent on its own: a freeze is a claim about the moment it was taken, and moments pass.

---

## 7. Records

None yet. This directory is empty of freeze records at bootstrap, which is accurate: nothing has been
frozen because nothing has been finished. The first plausible freeze point is after the first
successful compile is recorded ([NEXT.md](../NEXT.md) Active focus) — that is the first moment this
project will have a fact about itself worth banking.

---

## See also

- [DOC_SPEC.md §7](../DOC_SPEC.md) — save points as a documentation-lifecycle stage.
- [AUDIT.md](../AUDIT.md) — the six lenses; a freeze is preceded by a comprehensive pass.
- [MODULE_SPEC.md §7](../MODULE_SPEC.md#7-the-shelving-contract) — the per-module shelving contract
  this ceremony aggregates, and the canonical owner of its five items.
- [OPERATING_MODEL.md §4](../OPERATING_MODEL.md) — resume fidelity, the keystone this is built on.
- [runbooks/manual-validation.md](../runbooks/manual-validation.md) — what "manually validated" is
  allowed to mean in a Health block.
- [audit-log.md](../audit-log.md) — the running health record between freezes.
