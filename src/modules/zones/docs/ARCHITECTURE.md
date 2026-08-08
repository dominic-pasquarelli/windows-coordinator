---
title: Zones — internal design
tier: module
module: zones
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - src/modules/zones/README.md
  - docs/MODULE_SPEC.md
  - docs/ATLAS.md
  - docs/CONDUIT.md
  - docs/decisions/0012-zones-stacking-model.md
  - docs/decisions/0013-the-pointer-gesture-trigger-kind.md
  - docs/decisions/0014-atlas-explicit-raise-and-activate.md
  - docs/runbooks/manual-validation.md
---

# Zones — internal design

> **Window layouts with stacks.** A monitor is divided into zones by a layout template; a window
> dragged into a zone snaps to it; a zone can hold **more than one** window, and the mouse wheel with
> a modifier held cycles which one is in front.
>
> **One sentence:** everything here is a decision about *which window belongs where*, expressed as
> pure functions over an [Atlas](../../../../docs/ATLAS.md) snapshot — the desktop is read, never
> queried, and every actual Windows call belongs to a pillar.
>
> **Status: designed, not built.** No code exists in this module. The contract this design is
> written against does compile (CI `7aef6ff`), and this document is what the first line of Zones
> code should be written from.

---

## 1. What Zones is, and what it deliberately is not

Zones owns **one behaviour: which window belongs in which region of which monitor.** That is the
whole domain. It reads the desktop from Atlas, it declares what it wants to be woken for through
Conduit, and it decides.

**It is not a window manager.** It does not tile automatically, does not manage focus policy, does
not intercept window creation, and has no opinion about any window it has not been explicitly told
to place. A window the user has never dragged into a zone is invisible to Zones.

**The distinctive part is stacking.** PowerToys' FancyZones treats a zone as holding one window;
dropping a second displaces the first. Zones treats a zone as a **container with depth**: several
windows can occupy the same zone, sharing its rectangle, and the wheel cycles which is in front.
That single change is what makes a small monitor usable — a zone becomes a slot you keep a *set* of
related windows in, rather than a slot you keep swapping.

---

## 2. The occupancy model — the heart of the module

Everything else in Zones is plumbing around this type.

```csharp
// SKETCH — illustrative, not compiled.
sealed record ZoneOccupancy(IReadOnlyDictionary<string, IReadOnlyList<WindowRef>> Stacks);
```

A map from zone id to an **ordered list of windows, front to back**. Index 0 is the window the user
currently sees. Three invariants, and all three are worth testing before anything else exists:

1. **A window appears in at most one zone**, across every monitor. Assigning it somewhere removes it
   from wherever it was; there is no such thing as a window in two places, because there is no such
   thing on the desktop.
2. **Order is stack order.** Cycling rotates it. Nothing else reorders it implicitly.
3. **Occupancy is *intent*, not observation.** It records what the user asked for. The desktop is
   free to disagree — a window gets closed, an application moves itself, the user drags a window out
   by hand — and reconciling that disagreement (§5) is a first-class operation rather than an
   afterthought.

Point 3 is the one that decides whether this module feels solid or haunted. The tempting design is
to treat occupancy as a *cache of what the desktop looks like*, which turns every disagreement into
a bug with no correct answer. Treating it as intent means every disagreement has an obvious
resolution: the desktop wins about what exists, the user's intent wins about where things go.

### 2.1 Why stacking is z-order, and not minimising

A stacked zone places every one of its windows at **the same rectangle**. Only the front one is
visible; the others are behind it, unmodified. Cycling raises the next one.

The rejected alternative — minimise the ones behind, restore the one in front — is worse in every
dimension that matters. It animates (so cycling becomes slow and visually noisy), it changes a
window state the user did not ask to change, it disturbs Alt-Tab and taskbar ordering, applications
behave unpredictably when minimised out from under them, and restoring is a second chance to fail.
Z-order costs one call and touches nothing else. Recorded as
[ADR 0012](../../../../docs/decisions/0012-zones-stacking-model.md).

**The visible consequence, stated because it will be noticed:** windows behind the front one are
still *there*. They appear in Alt-Tab and on the taskbar, which is correct — they are open windows —
and clicking one in the taskbar raises it, which is a perfectly good second way to cycle a stack.

---

## 3. Cycling, and the gesture problem

**Bare wheel-over-zone cannot work.** The zone is full of an application that wants wheel events. A
module that swallowed them would break scrolling inside every stacked window; one that did not
swallow them could not cycle. The gesture has to be distinguishable from ordinary scrolling before
it is anything else.

**The decision: `Win` + wheel, anywhere over the zone.** `Ctrl`+wheel is zoom in nearly everything,
`Shift`+wheel is horizontal scroll in a great deal, and `Alt`+wheel is claimed by enough
applications to be a poor default. `Win`+wheel is close to unclaimed. The modifier is a setting, so
a collision on one machine is a preference change rather than a redesign.

### 3.1 The hook-thread rule this forces

Deciding whether to swallow a wheel event happens **on the low-level input hook thread**, inside a
budget measured in microseconds, on every wheel event the machine processes
([CONDUIT §5.1](../../../../docs/CONDUIT.md)). Zones cannot be consulted there — a module reached
from a hook callback is a desktop-wide stall waiting for a slow module.

So the decision must be answerable **without asking Zones anything**:

> Zones publishes an **armed region set** — the rectangles of zones that currently hold a stack of
> two or more windows — and republishes it whenever occupancy or layout changes. Conduit's hook
> tests the cursor against that set and nothing else. Match plus modifier held → swallow the event
> and queue a dispatch. Anything else → pass through, untouched, immediately.

This is [principle 7](../../../../docs/COORDINATOR.md#7-non-negotiable-principles) — *resolve once,
execute cheap* — in its sharpest form: all the thinking happens when a layout or a stack changes,
which is rare, and the per-event path is a rectangle test against a small pre-resolved array.

It also means **a zone with fewer than two windows is not armed at all**, so `Win`+wheel over an
ordinary un-stacked window passes straight through. The feature is invisible until it is useful.

### 3.2 What "cycle" actually does

```
Cycle(zoneId, direction) -> WindowRef?      // pure; null when the zone holds 0 or 1 windows
```

Rotate the order, return the new front window, ask Atlas to raise it. **Raise, not activate** — see
§4.2, where this turns out to be the most technically uncertain thing in the module.

---

## 4. What Zones needs from the pillars

Zones needs two things neither pillar offers today. Both are pillar extensions, specified as part of
this design because a module may never add them for itself.

### 4.1 Conduit — a pointer-gesture trigger kind

None of Conduit's five existing kinds expresses "a wheel tick, with a modifier, over one of these
rectangles". It is not a chord (no key-down moment), not a window event, not a schedule, and not the
existing gesture kind (which is a `Started`/`Updated`/`Ended` span with cleanup semantics; a wheel
tick is a discrete event with nothing to clean up).

It therefore satisfies [CONDUIT §7](../../../../docs/CONDUIT.md#7-adding-a-trigger-kind--the-extension-contract)'s
test for a genuinely new kind, and the full contract — intent record, refusal reasons, conflict rule,
dispatch class, guarantee statement — is specified in
[ADR 0013](../../../../docs/decisions/0013-the-pointer-gesture-trigger-kind.md) and lands in
[CONDUIT.md](../../../../docs/CONDUIT.md) as kind #6.

### 4.2 Atlas — explicit raise, and the foreground-lock dragon

[ATLAS §7.2](../../../../docs/ATLAS.md#72-what-atlas-will-not-do) currently says Atlas will not steal
focus as a side effect of placement and will not reorder z-order beyond what a move requires. Both
remain right: they forbid these things as *side effects*. Cycling needs them as an **explicit,
separately-requested operation**, which [ADR 0014](../../../../docs/decisions/0014-atlas-explicit-raise-and-activate.md)
adds.

**And here is the sharpest technical risk in the module.** Windows restricts which process may call
`SetForegroundWindow`; a process that has not recently received input generally cannot steal
foreground, and the call fails or merely flashes the taskbar button. Coordinator will be trying to
activate *another application's* window in response to input that went to a *third* application's
window. Whether the foreground lock permits that is genuinely unknown until it is tried.

The design absorbs this rather than betting on it:

| Operation | Mechanism | Reliability |
|---|---|---|
| **Raise** (default) | z-order change with no activation | Expected to work; needs no foreground rights |
| **Activate** (opt-in setting) | raise, then request foreground | **May be refused by the OS.** Surfaced as a refusal, never silently ignored |

Raise-without-activate is the default for a second reason beyond reliability: not stealing focus is
probably the better behaviour anyway. You cycle to see a window; you click it when you want to type
in it. `zones.activate-on-cycle` exists for people who disagree, and it is honest about the fact
that the OS may overrule them.

**This is the first thing to validate on real hardware** and the module's design should not be
trusted until it has been. The runbook row is `Z-4` in
[manual-validation.md](../../../../docs/runbooks/manual-validation.md).

---

## 5. Reconciliation — where the bugs would otherwise live

Every time Zones reads a fresh Atlas snapshot, it reconciles intent against reality:

```
Reconcile(occupancy, snapshot, resolvedZones) -> (occupancy', actions)
```

Pure. No desktop, no I/O, no clock. This is the single most test-worthy function in the module:

| Situation | Resolution |
|---|---|
| Window is no longer in the snapshot | Drop it from its stack. Closing a window leaves the zone. |
| Window's visible bounds no longer match its zone (beyond tolerance) | The user moved it out by hand. Drop it — the desktop wins about where things are. |
| Topology generation changed | Every resolved rectangle is stale. Re-resolve layouts, then re-evaluate membership against the new geometry. |
| A zone id no longer exists (layout changed) | Its windows become unassigned. They are not moved; they simply stop being managed. |
| Window is minimised | Keep it in the stack. Minimising is not leaving. |

**The tolerance is not a rounding fudge, it is a contract detail.** A window's reported `Bounds`
include an invisible resize border, so an exact comparison against a zone rectangle would find every
correctly-placed window to be in the wrong place. Membership compares `VisibleBounds`
([ATLAS §3](../../../../docs/ATLAS.md#3-the-model)) with a tolerance, and applications that clamp
their own size report `PlacedDifferently` — a first-class Atlas outcome that must not be treated as
failure.

### 5.1 The consequence of `PlacedDifferently` on a stack

If a stacked window enforces a minimum size larger than the zone, or refuses to resize at all, it
does not cover the zone and the window behind it peeks out around the edges. This looks like a bug
and is not one: it is an application exercising a right it has.

The design **surfaces rather than fights** it — the window stays in the stack, and Zones records that
the zone contains a window it could not size. Fighting it (repeated resize attempts, forcing a
maximise) produces a flickering window and an application in a state its author never anticipated.

---

## 6. Drag to snap

Uses two Conduit facilities that already exist:

- **The window-event pair** `MoveSizeStart` / `MoveSizeEnd`, which Conduit guarantees is delivered as
  a pair specifically so that an overlay put up at the start is always taken down
  ([CONDUIT §3.2](../../../../docs/CONDUIT.md#32-window-event)). An overlay whose end event was lost
  stays on the user's screen forever, which is the "makes the desktop worse" failure this project
  treats as disqualifying.
- **The gesture kind**, for *drag in progress with the snap modifier held*, which is what decides
  whether the overlay appears at all.

**On drop, the window joins the stack at the front** (the M1 default). This is what makes stacks
emerge from ordinary use rather than requiring a separate thing to learn: you drop a second window on
a zone and now the zone has two. `zones.stack-on-drop` turns it off for anyone who wants classic
displace-the-occupant behaviour.

**The overlay is the module's only Shell surface,** and it lives in `Coordinator.Zones.Shell` rather
than in the platform — the "would a second, unrelated module need this?" test says *maybe eventually*
(a timer HUD, a layout-restore preview), and *maybe eventually* is not a second consumer. It gets
lifted to a platform service the day something else genuinely needs it, and not before. The overlay
also carries the only visual answer to "is this zone stacked?" in M1: it draws the depth of each zone
while a drag is in progress.

---

## 7. The contract Zones publishes

### 7.1 Capabilities

Ids are permanent — settings files and user bindings reference them as strings, so they are added
freely, never renamed, never reused.

| Id | Kind | What it does |
|---|---|---|
| `zones.snap-focused` | Action | Snap the focused window into the zone under the cursor |
| `zones.cycle-forward` | Action | Cycle the stack under the cursor forward |
| `zones.cycle-back` | Action | Cycle it backward |
| `zones.next-layout` | Action | Switch the active layout on the monitor under the cursor |
| `zones.stack-on-drop` | Toggle | Whether a drop joins the stack or displaces the occupant |
| `zones.activate-on-cycle` | Toggle | Whether cycling also takes focus (§4.2 — may be refused) |
| `zones.padding` | Number | Work-area inset, in pixels |
| `zones.gap` | Number | Separation between neighbouring zones |
| `zones.active-layout` | Reading | The layout currently applied. **Not bindable** |
| `zones.stack-depth` | Reading | Depth of the zone under the cursor. **Not bindable** |

`cycle-forward` and `cycle-back` are Actions and therefore bindable to chords, which is deliberate:
it gives the feature a **keyboard path that does not depend on the wheel hook at all**. If §4.2's
foreground dragon or the hook budget turns out worse than expected, the module still works.

### 7.2 Trigger intents

| Intent | Purpose |
|---|---|
| Hotkey chord | snap, cycle forward/back, next layout |
| Window event (`MoveSizeStart`/`End`) | drag detection |
| Input gesture (drag + modifier) | overlay lifecycle |
| **Pointer gesture** (modifier + wheel over armed regions) | cycling — the new kind, §4.1 |

Every one of these is a **request that can be refused**. A chord may already be held by another
module or by Windows itself; the pointer gesture may be refused if another module has armed an
overlapping region. Zones must remain useful when refused — which is why the wheel and the chords are
alternative paths to the same capability rather than one depending on the other.

### 7.3 Settings, v1

```jsonc
{
  "schemaVersion": 1,
  "layouts": [ { "id": "…", "name": "…", "cells": [ … ], "padding": 8, "gap": 8 } ],
  "monitorLayouts": { "<monitor id>": "<layout id>" },
  "snapModifier": "Shift",
  "cycleModifier": "Win",
  "stackOnDrop": true,
  "activateOnCycle": false
}
```

Additive by default; a structural change ships an `ISettingsMigration`
([ADR 0011](../../../../docs/decisions/0011-settings-migrate-the-persisted-document-not-the-deserialized-object.md)).

**`monitorLayouts` is keyed by monitor id, and monitor identity across reconfiguration is an open
Atlas question** ([ATLAS §10](../../../../docs/ATLAS.md#10-open-questions-and-known-dragons)). Undock
a laptop and dock it again and the ids may not match, in which case a user's per-monitor layouts
silently fail to apply. Zones must not paper over this with a guess: an unmatched monitor falls back
to the default layout and says so, rather than applying somebody else's layout to the wrong screen.

---

## 8. The Core/Shell split, applied here

| | `Coordinator.Zones.Core` (`net9.0`) | `Coordinator.Zones.Shell` (`net9.0-windows`) |
|---|---|---|
| Occupancy model, stack ordering, cycling arithmetic | ✔ | |
| Reconciliation against a snapshot | ✔ | |
| Which zone a drop lands in (hit-testing) | ✔ (Atlas `LayoutMath.HitTest`) | |
| Armed-region computation | ✔ | |
| Settings shape and migrations | ✔ | |
| The drag overlay window and its painting | | ✔ |
| Everything else Windows-facing | | *neither — it belongs to a pillar* |

The bottom row is the interesting one. Zones needs no P/Invoke of its own: placement and raising are
Atlas, hooks and hotkeys are Conduit. Its Shell adapter exists **only** because it draws an overlay.
If the overlay were ever lifted to a platform service, `Coordinator.Zones.Shell` would be deleted
entirely — a module with no Windows code at all, which is the split working exactly as intended.

---

## 9. Testing plan

Core tests, all runnable on any OS with no desktop:

- **Occupancy invariants** — assigning a window removes it from its previous zone; a window is never
  in two stacks; order survives assignment.
- **Cycling** — rotation is cyclic in both directions; a 0- or 1-window zone is a no-op; cycling
  twice on a 2-stack returns to the start.
- **Reconciliation** — each row of §5's table, plus the combination that will actually happen in
  practice: a topology change *and* a closed window in the same snapshot.
- **Membership tolerance** — a correctly-placed window whose `Bounds` differ from its zone by the
  invisible border is still a member; one moved 200px away is not.
- **Armed regions** — a zone drops out of the armed set the moment its depth falls below two, which
  is what stops `Win`+wheel from swallowing scroll events over an ordinary window.
- **Settings migration** — round-trip and defaults, per MODULE_SPEC §6.

Manual-validation rows (`Z-1` … `Z-6`) cover what no test can: placement on a real desktop, the
mixed-DPI case, wheel-hook latency under load, the foreground lock, and the overlay surviving a drag
that ends outside any zone.

---

## 10. Dragons

| # | Dragon | Current answer |
|---|---|---|
| 1 | **Foreground lock may refuse activation** (§4.2) | Default to raise-without-activate; surface refusals; validate first |
| 2 | **Wheel hook is on every scroll on the machine** | Armed-region test only, pre-resolved, fail-open; measured latency budget |
| 3 | **Swallowing a wheel event wrongly breaks scrolling** | Arm only zones with depth ≥ 2; modifier required; pass through on any doubt |
| 4 | **Stacks are invisible without UI** | Overlay shows depth during drag in M1; a tab strip is the named next milestone |
| 5 | **Monitor identity across reconfiguration** (§7.3) | Fall back to default layout and say so; upstream question belongs to Atlas |
| 6 | **`PlacedDifferently` breaks stack coherence** (§5.1) | Surface it; never fight the application |
| 7 | **Stack membership does not survive a restart** | Accepted for M1 — window handles do not survive either. Re-associating by process and title is a heuristic that will be wrong silently, which is worse than starting empty |

---

## See also

- [README.md](../README.md) — the module front door, and where to resume.
- [docs/MODULE_SPEC.md](../../../../docs/MODULE_SPEC.md) — the contract every module implements.
- [docs/ATLAS.md](../../../../docs/ATLAS.md) — desktop truth, the layout math, the placement contract.
- [docs/CONDUIT.md](../../../../docs/CONDUIT.md) — trigger intents, arbitration, the hook-thread budget.
