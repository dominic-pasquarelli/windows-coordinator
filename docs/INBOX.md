---
title: Inbox — raw idea capture buffer
tier: meta
status: living
updated: 2026-08-08
related:
  - CLAUDE.md
  - docs/NEXT.md
  - docs/AUDIT.md
  - docs/OPERATING_MODEL.md
  - docs/vision.md
---

# INBOX — raw idea capture

> The zero-friction landing zone for stray thoughts, so **nothing is ever lost**. Dump the whole idea
> here the moment it arrives; triage into the living docs happens afterward, on purpose, as a
> separate step.
>
> **One sentence:** this file exists so that having an idea at the wrong moment costs nothing, and
> so that acting on it is still a deliberate decision.
>
> The intake protocol itself — capture first, propose triage second, never restructure the living
> docs silently — is in the **Snapshot intake & steering protocol** in [../CLAUDE.md](../CLAUDE.md).
> Why it is shaped that way is in
> [OPERATING_MODEL §2](OPERATING_MODEL.md#2-the-snapshot-protocol-is-a-throttle-not-a-filing-cabinet).

---

## How it works

**Trigger a capture** by starting a message with `SNAPSHOT:` or `IDEA:` — or just by clearly
signalling capture intent in any other words: *"capture this idea…"*, *"don't lose this, but…"*,
*"parking-lot thought:"*. All of these are treated identically. A capture is **never** refused,
interrogated, or edited down for quality. Friction at this step is the one thing that would break the
file's purpose.

**What happens next, in order:**

1. The full thought is appended below under `## Captured`, verbatim, newest at top, as
   `Status: captured`. This happens immediately, before any discussion, so the idea is safe even if
   triage never happens.
2. A triage destination is **proposed, not applied**. Candidates: a principle or section in
   [COORDINATOR.md](COORDINATOR.md) · a phase change in the roadmap · an actionable step or a
   trip-wire row in [NEXT.md](NEXT.md) · a parking-lot entry with its tie-back · a long-horizon
   direction in [vision.md](vision.md) · a term in [ONBOARDING.md](ONBOARDING.md) · a Pitfalls entry
   in the root [README](../README.md) · a known limitation in [TECH_DEBT.md](TECH_DEBT.md) · a new
   ADR in [`docs/decisions/`](decisions/) if it is a non-obvious decision with trade-offs.
3. If the idea is small, safe and self-contained, **doing it now beats filing it**. Progress beats
   paperwork; the offer is made in the same reply.
4. On confirmation the edits are made and the entry is marked `Status: triaged → <where it landed>`.
5. Work returns to whatever was happening before the capture.

**Format per entry:**

```text
### <short title> — <date>
Status: captured | triaged → <where it landed>
<the full thought, verbatim — as much detail as you want>
```

## This is a buffer, not an archive

An entry marked `triaged` has already done its job: its content lives somewhere real now. Leaving it
here forever means the live section slowly disappears under settled history, and the file you were
supposed to open without hesitation becomes one you avoid.

So **landed `triaged` entries get pruned to git** at a freeze or whenever the buffer is uncomfortably
long. Git keeps the history; this file keeps the working set. That is the *drain* half of the
capture/recall/drain triad in
[OPERATING_MODEL §3](OPERATING_MODEL.md#3-capture-is-free-building-costs) — every buffer in this
repository names both how an item comes back and how it leaves, and pruning is how items leave here.

Draining is a **nudge, never a gate**. Nothing is blocked by a long inbox; the audit's recall lens
just mentions it.

## ⚠ The INBOX must not accrue authority

**Capture is free; *confidence* is not.**

The failure this file is prone to is not losing an idea — it is the opposite. A long, emphatic,
well-argued capture reads like a **conclusion**. Several rounds of enthusiastic elaboration build
confirmation bias **before the cheapest falsifying experiment has been run**. A note that has never
been tested but has been written about four times starts to function as a decision, and that is how a
buffer quietly turns into a contract.

This is a real hazard for this project specifically, because it is a personal toolbox with an owner
who is also the only reviewer. There is no second person to ask *"has anyone actually checked?"* —
which means the format has to ask it instead.

So a **major** capture — one that has grown past a few paragraphs, or one you keep coming back to —
gets restructured into these seven fields. Short captures need none of this: the point is to make
enthusiasm cheap to falsify, not to add friction to the drop-it-here path.

| Field | What it forces |
|---|---|
| **Status** | `captured` · `hypothesis` · `verified` · `promoted` — one word that stops a hypothesis being read as a finding |
| **What is known** | the part backed by something in this repository or a checkable source |
| **What is assumed** | the part that sounds equally confident but is not |
| **Cheapest falsifying experiment** | the smallest thing that could prove it **wrong** — not the smallest thing that could prove it right |
| **Decision / ADR trigger** | what must become true before this earns a decision |
| **Not now** | the adjacent work this must not quietly grow into |
| **Owner value if successful** | why it would be worth doing at all |

**Keep the verbatim thought and a concise triage here. Extended design work moves to its own doc
*after* the trigger fires** — not before, because a design document is itself an authority artifact,
and writing one is how a hypothesis gets promoted without ever being tested.

A useful sanity check, given the current state of the project: nothing in this repository has been
compiled or run on Windows ([NEXT.md](NEXT.md)). Any capture that assumes a Windows API behaves a
particular way — hook latency, DPI change notifications, virtual-desktop enumeration, tray lifecycle
— is a **hypothesis**, however confidently it is written, until a human has watched it happen. Mark
it as one.

---

## Captured

*(empty — nothing captured yet)*
