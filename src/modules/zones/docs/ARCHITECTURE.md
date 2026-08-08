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
  - docs/decisions/0015-zone-addressing-and-durable-monitor-identity.md
  - docs/decisions/0016-zone-occupancy-member-states.md
  - docs/decisions/0017-invocation-context-and-one-drag-lifecycle.md
  - docs/decisions/0018-layout-editing-grid-split-merge.md
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

// A zone is addressed by three things, never by a cell id alone (ADR 0015). Cell ids are unique
// within a template; templates are reusable across monitors, and a monitor can switch layouts.
readonly record struct ZoneAddress(MonitorKey Monitor, string LayoutId, string CellId);

enum MemberState { Placed, Minimized, Oversized, AwaitingReplacement }

sealed record StackMember(
    WindowRef Window,
    MemberState State,
    Rect PlacedBounds,        // what we asked for
    Rect ObservedBounds,      // what we actually got (may differ — PlacedDifferently)
    int PlacedAtGeneration);  // the Atlas topology generation it was placed under

sealed record ZoneOccupancy(IReadOnlyDictionary<ZoneAddress, IReadOnlyList<StackMember>> Stacks);
```

Three invariants, and all three are worth testing before anything else exists:

1. **A window appears in at most one zone**, across every monitor and every layout. Assigning it
   somewhere removes it from wherever it was; there is no such thing as a window in two places,
   because there is no such thing on the desktop.
2. **Stored order is the *cycle ring*, not a claim about what is visible.** It says what order
   cycling walks. Which member is actually frontmost is **read from the Atlas snapshot**, whose
   window list is ordered front-to-back. So a taskbar click that raises a buried member needs no
   reconciliation at all — it changed which member is frontmost, and the next cycle continues from
   there. ([ADR 0016](../../../../docs/decisions/0016-zone-occupancy-member-states.md))
3. **Occupancy is *intent*, not observation.** It records what the user asked for. The desktop is
   free to disagree, and reconciling that disagreement (§5) is a first-class operation rather than an
   afterthought.

Point 3 is the one that decides whether this module feels solid or haunted. The tempting design is
to treat occupancy as a *cache of what the desktop looks like*, which turns every disagreement into
a bug with no correct answer. Treating it as intent means every disagreement has an obvious
resolution: the desktop wins about what exists, the user's intent wins about where things go.

**Why a member carries state.** A bare `WindowRef` cannot express *minimised but still a member*,
*placed but clamped to a size we did not ask for*, or *placed under a topology that no longer
exists* — and each of those is a real transition with a different correct answer. The first draft of
this design used a bare list and had five transitions with no representable resolution; they are §5's
table now.

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
Cycle(occupancy, snapshot, ZoneAddress, direction) -> WindowRef?   // pure; null when depth < 2
```

Find whichever ring member is currently frontmost **in the snapshot**, take the next one in ring
order, and return it. The caller then asks Atlas to bring it forward.

**`Show`, not `Raise`, and never `Activate` by default.** A minimised member must be restored before
it can be seen, so cycling calls `Show` (restore-if-minimised, then raise). Cycling *away* does not
re-minimise — silently changing a window's state on the way past is exactly the surprise this design
avoids elsewhere. Focus is a separate, opt-in question: see §4.2, the most technically uncertain
thing in the module.

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
| **Raise** | z-order change with no activation | Expected to work; needs no foreground rights |
| **Show** (what cycling calls) | restore if minimised, then raise | Expected to work. Cycling *away* never re-minimises |
| **Activate** (opt-in setting) | `Show`, then request foreground | **May be refused by the OS.** Surfaced as a refusal, never silently ignored |

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

Pure. No desktop, no I/O, no clock. This is the single most test-worthy function in the module, and
each row below is a case the first draft of this design could not represent
([ADR 0016](../../../../docs/decisions/0016-zone-occupancy-member-states.md)):

| Situation | Resolution |
|---|---|
| Window is no longer in the snapshot | Drop it. Closing a window leaves the zone. |
| Window's bounds differ from **`ObservedBounds`** beyond tolerance | The user moved it out by hand. Drop it. |
| Window was placed but came back a different size (`PlacedDifferently`) | **Stays.** Mark `Oversized`, and record `ObservedBounds` as what we actually got — which is why membership is tested against that and never against the zone rectangle. |
| `snapshot.TopologyGeneration != member.PlacedAtGeneration` | **Do not run the bounds test at all.** Mark `AwaitingReplacement` and re-place against the re-resolved zone; testing resumes only after a placement under the current generation. |
| Window is minimised | Keep it, mark `Minimized`. Minimising is not leaving, and cycling to it will `Show` it. |
| Another window is frontmost than the ring implies (taskbar click, Alt-Tab) | **Nothing to do.** Ring order is not a claim about visibility; the next cycle continues from whatever is actually in front. |
| A zone address no longer exists (layout edited or switched) | Its windows become unassigned — unless an edit preserved the region, in which case §7's rules move the ring instead. |

**The tolerance is a contract detail, not a rounding fudge.** A window's reported `Bounds` include an
invisible resize border, so membership compares `VisibleBounds`
([ATLAS §3](../../../../docs/ATLAS.md#3-the-model)) against `ObservedBounds` with a tolerance.

### 5.1 Why the generation rule matters more than it looks

Without it, a monitor being unplugged reads as *the user dragged every window out of every zone
simultaneously*, and the whole layout is discarded at exactly the moment geometry is least
trustworthy. [ATLAS §4.1](../../../../docs/ATLAS.md#41-topology-generation) already says geometry
computed at generation N must not be applied at N+1; this applies the same rule to **membership**.

### 5.2 The consequence of `PlacedDifferently` on a stack

If a stacked window enforces a minimum size larger than the zone, it does not cover the zone and the
window behind it peeks out. This looks like a bug and is not one: it is an application exercising a
right it has. The design **surfaces rather than fights** — `Oversized` is observable state, and
repeated resize attempts would produce a flickering window and an application in a state its author
never anticipated.

## 6. Drag to snap

**One gesture, one lifecycle.** Zones subscribes to Conduit's **input gesture** kind and to nothing
else for dragging. The gesture payload carries the dragged `WindowRef` and an `InvocationContext`,
and Conduit guarantees exactly one `Ended` for every `Started` — so the overlay put up at the start
is always taken down.

The first draft used *both* the window-event pair `MoveSizeStart`/`MoveSizeEnd` **and** the gesture
`Started`/`Ended`. Conduit defines no ordering between intent streams, so cleanup ownership was
ambiguous and "which arrived first" was undefined. Collapsing to one stream removes the race rather
than documenting it ([ADR 0017](../../../../docs/decisions/0017-invocation-context-and-one-drag-lifecycle.md)).

**On drop, the window joins the stack at the front** (the M1 default) — which is what makes stacks
emerge from ordinary use rather than requiring a separate thing to learn.

**With `stackOnDrop = false`, the drop *swaps*.** The displaced occupant goes where the incoming
window came from — its previous zone if it had one, otherwise its pre-drag bounds, both of which
Zones knows because it owned the drag. Only when neither is available is the occupant unmanaged and
left in place, recorded as `Displaced` so the surface can say so. The rejected alternative — remove
it from the model and leave it sitting in the same rectangle — produces an unmanaged window hidden
under a managed one, which is the exact bug the setting exists to avoid.

**The overlay is the module's only Shell surface,** and it lives in `Coordinator.Zones.Shell` rather
than in the platform — the "would a second, unrelated module need this?" test says *maybe eventually*
(a timer HUD, a layout-restore preview), and *maybe eventually* is not a second consumer. It also
carries the only visual answer to "is this zone stacked?" in M1: it draws each zone's depth during a
drag.

## 7. The layout designer

Authoring a layout by typing fractions is not something anyone does twice. Three operations, all
**pure functions over a `LayoutTemplate`** and therefore all host-tested with no desktop
([ADR 0018](../../../../docs/decisions/0018-layout-editing-grid-split-merge.md)):

| Operation | What it does |
|---|---|
| `Grid(columns, rows)` | Type two numbers, get that grid. Ids are positional and stable: `r0c0`, `r0c1`, … |
| `Split(cellId, axis, fraction)` | Replace one cell with two covering exactly the same rectangle |
| `Merge(cellIds[])` | Replace several cells with one covering their bounding box |

The arithmetic is the easy half. The part worth designing is what happens to **cell ids**, because a
cell id is a permanent contract — occupancy addresses it (§2) and settings reference it. An editor
that mints fresh ids scatters every stack on every edit, which is how you end up with an editor
nobody uses.

### 7.1 Identity through an edit

- **Split keeps the original id on the first fragment** (left for a vertical split, top for a
  horizontal one) and mints one new id. The stack stays with the first fragment, which shares the
  original's origin — so the windows are closest to where they already were.
- **Merge keeps the id of the first cell in reading order** (topmost, then leftmost). The other ids
  are **retired** into the template's `retiredCellIds` and never reused, because a reused id would
  silently point an old saved binding at a different region.
- **Merged stacks combine.** The retired cells' rings are appended to the survivor's, in reading
  order. Those windows were adjacent and are now genuinely one zone; discarding them would punish
  the user for editing.

### 7.2 Merge is refusable, and that is the interesting predicate

**Cells merge only if they tile their bounding box exactly** — no gap, no overlap. Anything else is
`Refused(NotContiguous)`, naming the area that is uncovered or doubly covered.

This is the most testable thing in the whole module: a small grid, every subset, and a predicate with
an exact answer. It is also the one place where the editor is stricter than hand authoring — §2
permits overlapping and gappy templates, and `Merge` will refuse on them. That asymmetry is
deliberate: the editor produces tilings, and hand authoring stays as expressive as it was.

The rejected alternative was to auto-repair a non-contiguous selection by taking the bounding box and
deleting whatever was inside it. That silently destroys cells the user did not select — data loss
dressed as convenience.

### 7.3 Editing is a settings-save, not a live mutation

An edit produces a new template and goes through the ordinary settings path. Occupancy is then
reconciled against it by §5's reconciler; cells that vanished entirely release their windows as
unassigned rather than moving them somewhere nobody chose.

---

## 8. The contract Zones publishes

### 8.1 Capabilities

Ids are permanent — settings files and user bindings reference them as strings, so they are added
freely, never renamed, never reused.

| Id | Kind | What it does |
|---|---|---|
| `zones.snap-focused` | Action | Snap the focused window into the zone under the cursor |
| `zones.cycle-forward` | Action | Cycle the stack under the cursor forward |
| `zones.cycle-back` | Action | Cycle it backward |
| `zones.next-layout` | Action | Switch the active layout on the monitor under the cursor |
| `zones.edit-layout` | Action | Open the layout designer for the monitor under the cursor (§7) |
| `zones.stack-on-drop` | Toggle | Whether a drop joins the stack or displaces the occupant |
| `zones.activate-on-cycle` | Toggle | Whether cycling also takes focus (§4.2 — may be refused) |
| `zones.padding` | Number | Work-area inset, in pixels |
| `zones.gap` | Number | Separation between neighbouring zones |
| `zones.active-layout` | Reading | The layout currently applied. **Not bindable** |
| `zones.stack-depth` | Reading | Depth of the zone under the cursor. **Not bindable** |

`cycle-forward` and `cycle-back` are Actions and therefore bindable to chords, which is deliberate:
it gives the feature a **keyboard path that does not depend on the wheel hook at all**. If §4.2's
foreground dragon or the hook budget turns out worse than expected, the module still works.

### 8.2 Trigger intents

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

### 8.3 Settings, v1

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

## 9. The Core/Shell split, applied here

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

## 10. Testing plan

Core tests, all runnable on any OS with no desktop:

- **Addressing** — the same template applied to two monitors keeps two independent stacks; switching
  layouts on one monitor does not touch the other's occupancy. This is the case the first design
  could not represent, so it is the case that proves the new one.
- **Occupancy invariants** — assigning a window removes it from its previous zone; a window is never
  in two stacks; ring order survives assignment.
- **Cycling** — cyclic in both directions; depth < 2 is a no-op; cycling starts from whichever member
  the *snapshot* says is frontmost, not from stored order; a minimised member is selected and
  `Show`n rather than skipped.
- **Reconciliation** — every row of §5's table, plus the two combinations that actually happen: a
  topology change *and* a closed window in the same snapshot, and a `PlacedDifferently` member
  surviving two consecutive reconciliations (the case the first draft dropped on the second pass).
- **Membership tolerance** — a correctly-placed window whose `Bounds` differ from `ObservedBounds` by
  the invisible border is still a member; one moved 200px away is not.
- **Armed regions** — a zone leaves the armed set the moment its depth falls below two, which is what
  stops `Win`+wheel swallowing scroll events over an ordinary window.
- **Designer** — `Grid` produces the expected cell count and ids; `Split` preserves the original id on
  the first fragment and its stack; `Merge` refuses every non-tiling subset of a 3×3 grid and accepts
  every tiling one; merged rings concatenate in reading order; a retired id is never reissued.
- **Settings migration** — round-trip and defaults, per MODULE_SPEC §6.

Manual-validation rows (`Z-1` … `Z-6`) cover what no test can: placement on a real desktop, the
mixed-DPI case, wheel-hook latency under load, the foreground lock, and the overlay surviving a drag
that ends outside any zone.

## 11. Dragons

| # | Dragon | Current answer |
|---|---|---|
| 1 | **Foreground lock may refuse activation** (§4.2) | Default to raise-without-activate; surface refusals; validate first |
| 2 | **Wheel hook is on every scroll on the machine** | Armed-region test only, pre-resolved, fail-open; measured latency budget |
| 3 | **Swallowing a wheel event wrongly breaks scrolling** | Arm only zones with depth ≥ 2; modifier required; pass through on any doubt |
| 4 | **Stacks are invisible without UI** | Overlay shows depth during drag in M1; a tab strip is the named next milestone |
| 5 | **Monitor identity across reconfiguration** (§8.3) | `MonitorKey` carries a confidence; a `Positional` match that may be wrong falls back to the default layout **and says so** ([ADR 0015](../../../../docs/decisions/0015-zone-addressing-and-durable-monitor-identity.md)) |
| 6 | **`PlacedDifferently` breaks stack coherence** (§5.2) | Surface it as `Oversized`; never fight the application |
| 7 | **Stack membership does not survive a restart** | Accepted for M1 — window handles do not survive either. Re-associating by process and title is a heuristic that will be wrong silently, which is worse than starting empty |

---

## See also

- [README.md](../README.md) — the module front door, and where to resume.
- [docs/MODULE_SPEC.md](../../../../docs/MODULE_SPEC.md) — the contract every module implements.
- [docs/ATLAS.md](../../../../docs/ATLAS.md) — desktop truth, the layout math, the placement contract.
- [docs/CONDUIT.md](../../../../docs/CONDUIT.md) — trigger intents, arbitration, the hook-thread budget.
