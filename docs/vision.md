---
title: Vision — long-horizon directions (parked, not the contract)
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/CONDUIT.md
  - docs/ATLAS.md
  - docs/NEXT.md
  - docs/OPERATING_MODEL.md
  - docs/INBOX.md
---

# vision.md — long-horizon directions

> Where this could go, preserved so the ideas are not lost, and quarantined so they cannot be
> mistaken for plans. **Nothing on this page is committed scope.** Nothing here is built, scaffolded,
> stubbed, or given a directory.
>
> **One sentence:** this file is the honest home for everything the toolbox *could* become, kept
> deliberately separate from what it *is* ([NEXT.md](NEXT.md)) and what it has *decided*
> ([COORDINATOR.md](COORDINATOR.md) and the ADRs).
>
> The rule that makes this page safe: **capture is free, building costs**
> ([OPERATING_MODEL §3](OPERATING_MODEL.md#3-capture-is-free-building-costs)). Writing a module idea
> down hardens the architecture against a future need for the price of a paragraph. Building it costs
> memory in a process that sits resident all day, a settings surface that must be migrated forever
> after, a new way for the desktop to misbehave, and a manual validation pass a human has to
> physically perform. This page gets the first without paying the second.

---

## The framing that keeps this page honest

**A single module in the tray is already a complete product.** That is not a consolation prize, it is
the actual bet the architecture makes. If Zones ships and nothing else ever does, the owner has a
tool they use every day and the project succeeded. The platform exists to make the *second* module
cheap — not to make the first one conditional on a roadmap.

So read the list below as **evidence that the module boundary is worth having**, not as a backlog.
Each idea is here because it plausibly fits the existing contract without changing it; that is the
useful information. If one of them turned out to require a new pillar, a new lifecycle hook, or an
escape hatch through the Core/Shell split, *that* would be worth acting on today. None of them does.

**Nothing graduates from this page by enthusiasm.** An idea leaves here when there is a real,
currently-felt need — the specific annoyance, this month, on the owner's actual machine — and it
leaves by becoming an ADR and a [NEXT.md](NEXT.md) step, in that order. An idea that has been written
about four times and never needed is still parked; see the authority warning in
[INBOX.md](INBOX.md).

---

## The Zones tab strip — named, gated, and deliberately not in M1

Stacking ([ADR 0012](decisions/0012-zones-stacking-model.md)) makes a zone a container with depth,
and M1 ships it with almost no visual affordance: the drag overlay shows each zone's depth while you
are dragging, and nothing shows it otherwise.

The obvious answer is a **tab strip** — a thin always-on-top band at the top of a stacked zone, one
tab per window, bare wheel over it cycling. It would solve discoverability completely and would make
the feature legible to someone who has never read a word of documentation.

It is not in M1 because it is a large piece of Windows UI for a feature that has never been used in
anger. The strip must follow its zone through moves and layout changes, survive per-monitor DPI
changes, hide when something goes fullscreen, never steal a click, never appear in Alt-Tab or on the
taskbar, and repaint without flicker. Every one of those is a place a resident tray utility can start
making the desktop worse.

**The gate:** stacking is in daily use, and its invisibility is the top complaint about it. Tracked
as **TD-13** in [TECH_DEBT.md](TECH_DEBT.md) — which is the recall hook, so this cannot be quietly
forgotten.

## Parked module ideas

Six, all deliberately unbuilt. Each names what it would be and, more usefully, **which pillar it
would consume** — because a module that consumes an existing pillar costs one module's worth of work,
while a module that needs something new costs a design.

### Launcher

A keyboard-summoned launcher for applications, files and folders: one chord, type a few characters,
press enter. The familiar shape, made local and boring rather than clever.

*Consumes:* **Conduit** — a single global chord intent, and nothing else. It needs no desktop truth
at all, which makes it the cheapest possible second consumer of the trigger fabric and therefore a
genuinely useful test of whether Conduit's contract holds for a module that wants *only* input.

### Clipboard

A bounded clipboard history — the last N entries, recallable by chord, with pinning for the handful
you keep re-pasting.

*Consumes:* **Conduit** for the recall chord. Notably it needs a platform service that does not exist
yet: watching the system clipboard is neither a trigger nor desktop geometry. That makes it the most
architecturally interesting idea on this page — it is the one most likely to reveal a missing seam,
and the one whose privacy and persistence questions (what gets stored, for how long, in plaintext?)
would need answering in an ADR before a line of it was written.

### PinTop

Keep a chosen window always-on-top, toggled by chord, with an unobtrusive indication of which windows
are currently pinned.

*Consumes:* **Conduit** for the toggle, **Atlas** for the window handle and its identity. Small
enough to be the reference implementation of the module contract if Zones ever proves too large to
serve as the first example — a plausible fallback for P3 rather than a competitor to it.

### Palette

A command palette for the toolbox itself: one chord opens a searchable list of every capability every
loaded module has declared, and running one invokes it.

*Consumes:* **Conduit** for the chord, and the platform's **module registry** for everything else —
which is precisely why it matters more than its size suggests. Palette would be a **second
independent consumer of the registry-driven settings surface**, and that is the written trigger for
the Shell graduating from platform core to a pillar
([COORDINATOR.md §5.1](COORDINATOR.md#51-why-the-shell-is-platform-core-and-not-a-pillar)). If this
idea is ever built, the Shell question comes with it. Noted here so the connection is not rediscovered
the hard way.

### Focus

A do-not-disturb mode: suppress notifications, optionally dim or hide non-essential windows, for a
bounded period.

*Consumes:* **Conduit** for the chord and for the timed end of a session, **Atlas** for knowing which
windows exist. Its natural relationship is with **Chrono** — a focus period is a timer with side
effects — which raises the one genuinely open design question on this page: whether that is one
module or two modules that must somehow cooperate. Cross-module coordination has no answer in the
current contract, and inventing one speculatively is exactly what
[COORDINATOR.md §9](COORDINATOR.md#9-scope-discipline) forbids.

### Restore

Remember window layouts and restore them — after a monitor is unplugged and replugged, after a dock
event, after a machine sleeps and wakes and Windows has cheerfully piled everything onto one screen.

*Consumes:* **Atlas**, more heavily than anything else here — window identity that survives a
topology change, per-monitor geometry, DPI, and the ability to compare a remembered snapshot against
a current one. It is already named in [ATLAS.md](ATLAS.md) as a future consumer, and it is the
strongest argument that Atlas's coherent-snapshot rule is right: a restore built on two independent
reads of the desktop would restore windows to a state that never existed.

---

## The candidate third pillar — a rules layer

There are **exactly two pillars**, Conduit and Atlas, and each exists because it had a real first
consumer ([COORDINATOR.md §5](COORDINATOR.md#5-the-two-pillars-spine-altitude-only)). There is one
plausible candidate for a third, and it is named here specifically so that it stays *named and
unbuilt* rather than quietly accreting.

**What it would be.** A conditional-reaction layer over facts the platform already knows: *when the
second monitor is unplugged, apply layout X* · *when the laptop undocks, move these windows* · *when
this application launches, put it in that zone* · *between 9 and 5 on weekdays, keep this mode on*. A
small declarative rule surface evaluating conditions over Atlas snapshots and Conduit events, firing
module capabilities as its actions.

**Why it is a credible pillar and not a module.** It is genuinely cross-cutting: the conditions come
from the pillars, the actions are capabilities on arbitrary modules, and its value grows with the
number of modules — which is the actual signature of a pillar rather than a feature. It would also
lean on infrastructure that already exists for other reasons: typed capabilities as named binding
targets (principle 5), Conduit's event dispatch, Atlas's snapshots.

**Why it does not exist.** It has **zero consumers**. Every scenario above is currently hypothetical:
no module is built, so nothing can be triggered, so no rule can be written. Building it now would be
speculative generality in its purest form — an abstraction sized for consumers that have never
arrived — and the one shape of mistake the operating model spends the most words preventing.

**It deliberately has no name.** Naming a subsystem is most of the work of making it feel real, and a
named pillar in a docs tree is a claim that something exists. It gets a name in the ADR that decides
to build it, and not before.

| | |
|---|---|
| **Trigger — build it when…** | **two unrelated modules independently need the same conditional-reaction machinery.** Not one module wanting it (that is a module feature written generically), not a hypothetical second (that is this page). Two real ones, both shipped, both wanting it. |
| **What must be true first** | at least two modules exist and expose capabilities worth firing; Atlas emits topology *change* events, not just snapshots; there is a real remembered-layout consumer, most likely **Restore**. |
| **Written down as** | a trip-wire row in [NEXT.md](NEXT.md) — that is the recall hook, and it is the only thing that lets a deferral resurface on its own. |
| **What it must not become** | a scripting engine. Compile-time modularity, not runtime scripting (principle 11). A rule surface that grows a language has stopped being a rules layer and become a second product. |

---

## What is deliberately *not* here

Recorded so the absences read as decisions rather than gaps:

- **No mobile companion, no cloud sync, no account.** The toolbox is local software on one machine.
  Every one of those would add a network surface, a privacy question and a service to keep alive, in
  exchange for capability the owner has not wanted once.
- **No plugin marketplace, no third-party module API.** Modules are compiled in
  ([MODULE_SPEC.md](MODULE_SPEC.md)). A stable public extension API is a permanent compatibility
  obligation, and this project has exactly one module author.
- **No AI features.** Not on principle — simply that no annoyance the owner actually has is best
  solved that way, and a feature adopted for its category rather than its need is precisely what
  [COORDINATOR.md §9](COORDINATOR.md#9-scope-discipline) rules out.
- **No replacement of things Windows already does adequately.** The bar is *"I wish Windows did
  this"*, not *"I could rewrite that"*. Keeping the stock feel means adding what is missing, not
  substituting what is present.
