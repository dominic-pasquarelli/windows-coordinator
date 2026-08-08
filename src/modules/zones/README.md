---
title: Zones — module front door
tier: module
module: zones
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - src/modules/zones/docs/ARCHITECTURE.md
  - docs/decisions/0019-layout-edits-are-a-transaction.md
  - docs/decisions/0020-dormant-stacks-and-the-displacement-rules.md
  - docs/MODULE_SPEC.md
  - docs/ATLAS.md
  - docs/CONDUIT.md
  - docs/NEXT.md
---

# Zones — window layouts with stacks

> **M1, the first module.** A layout divides each monitor into zones; dragging a window into one
> snaps it there. Unlike FancyZones, **a zone can hold several windows at once** — dropping a second
> window stacks it, and `Win` + mouse wheel over the zone cycles which one is in front.
>
> **One sentence:** a zone is a container with depth, not a slot you keep swapping.

## Status: designed, no code

Nothing in this directory is implemented. What exists is the design —
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — written against a platform contract that compiles
(CI `7aef6ff`) but that nothing yet implements.

| | State |
|---|---|
| Internal design ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)) | **done** — addressing, occupancy and member states, dormancy, stacking, cycling, reconciliation, the layout designer, dragons |
| Decisions (ADR 0012 – 0020) | **done** — stacking, the pointer-gesture kind, raise/activate, zone addressing, member states, invocation context, layout editing, edits as a transaction, dormancy and displacement |
| `Coordinator.Zones.Core` | **TODO** — not created. `coord new-module zones` adds it around these docs |
| `Coordinator.Zones.Shell` (the drag overlay) | **TODO** — not created |
| Core tests | **TODO** — not created |
| Manual-validation rows `Z-1` … `Z-6` | **written, never executed** |

**Zones is blocked, and the blockage is real rather than bureaucratic.** A module needs a host to
load it (P1) and needs both pillars to have implementations behind their declarations (P2). Building
Zones first means every error it produces arrives mixed with errors from two layers underneath —
the "error found after the expensive step" failure this project names explicitly. The ordered path
is in [docs/NEXT.md](../../../docs/NEXT.md).

## Designing a layout

Three operations, all pure and all host-testable
([ARCHITECTURE §7](docs/ARCHITECTURE.md#7-the-layout-designer)):

- **Grid** — type a column and row count, get that grid.
- **Split** — divide an existing cell along either axis.
- **Merge** — combine cells back together, **refused unless they tile their bounding box exactly**.

The interesting part is not the arithmetic; it is that a cell id is a permanent contract, so an edit
has to say what happens to the stacks addressed by the cells it changes. Split keeps the id on the
first fragment; merge keeps the first cell's id in reading order, retires the rest permanently, and
concatenates their stacks into the survivor.

**Which is why an edit is a transaction, not a new template.** Each operation returns the new
template *and* its bumped revision, the cell remapping, the retired ids, the transformed occupancy,
and a placement for every geometrically affected window — including windows in a cell whose id did
not change, which is exactly the case id stability hides
([ADR 0019](../../../docs/decisions/0019-layout-edits-are-a-transaction.md)).

## The two things worth knowing before you read the design

**1. Stacking is z-order, not minimising.** Every window in a stack sits at the same rectangle;
only the front one is visible. Cycling raises the next. Nothing is minimised, nothing is hidden, and
the windows behind stay in Alt-Tab and on the taskbar — because they are open windows and pretending
otherwise would be a lie the desktop can see through.

**2. The wheel gesture cannot be bare.** The zone is full of an application that wants wheel events,
so cycling is `Win`+wheel and Zones only arms zones that actually hold a stack of two or more. Over
an ordinary window, `Win`+wheel passes straight through. The reasoning, and the hook-thread rule it
forces, is [ARCHITECTURE §3](docs/ARCHITECTURE.md#3-cycling-and-the-gesture-problem).

## Read order

1. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — this module's design. Start at §2, the occupancy
   model; everything else is plumbing around it.
2. [docs/MODULE_SPEC.md](../../../docs/MODULE_SPEC.md) — the contract every module implements.
3. [docs/ATLAS.md](../../../docs/ATLAS.md) and [docs/CONDUIT.md](../../../docs/CONDUIT.md) — the two
   pillars Zones is built on. Zones needs several extensions from each — zone addressing and
   durable monitor keys, z-order, `Show`, the pointer-gesture kind, and the invocation context —
   all specified in ADRs 0013–0017.

## Decisions that shaped this module

The unified log is [`docs/decisions/`](../../../docs/decisions/). The nine that govern Zones:

- **[ADR 0012](../../../docs/decisions/0012-zones-stacking-model.md)** — a zone holds an ordered
  stack; stacking is z-order; membership is intent reconciled against the desktop; stacks are
  session-scoped.
- **[ADR 0013](../../../docs/decisions/0013-the-pointer-gesture-trigger-kind.md)** — the sixth
  Conduit trigger kind, and the rule that its hook-thread decision is answerable from pre-resolved
  regions without consulting a module.
- **[ADR 0014](../../../docs/decisions/0014-atlas-explicit-raise-and-activate.md)** — Atlas gains
  raise and activate as explicit operations, and treats the Windows foreground lock as a refusal
  rather than a failure.
- **[ADR 0015](../../../docs/decisions/0015-zone-addressing-and-durable-monitor-identity.md)** — a
  zone is addressed by (monitor, layout, cell), and persisted settings key on a **durable**
  `MonitorKey` rather than a snapshot-local handle.
- **[ADR 0016](../../../docs/decisions/0016-zone-occupancy-member-states.md)** — a stack member
  carries state, ring order is not a claim about visibility, and reconciliation is generation-aware.
- **[ADR 0017](../../../docs/decisions/0017-invocation-context-and-one-drag-lifecycle.md)** — every
  dispatch carries an invocation context, and a drag has exactly one lifecycle.
- **[ADR 0018](../../../docs/decisions/0018-layout-editing-grid-split-merge.md)** — the layout
  designer: grid, split and merge as pure operations, and what happens to cell ids.
- **[ADR 0019](../../../docs/decisions/0019-layout-edits-are-a-transaction.md)** — an edit is one
  transaction over template, occupancy and placement, and geometry is stamped by
  `(topology generation, layout revision)` so a split re-places its own windows.
- **[ADR 0020](../../../docs/decisions/0020-dormant-stacks-and-the-displacement-rules.md)** — an
  absent monitor makes a stack dormant rather than unassigned, and a refused displacement degrades to
  a stack rather than an orphan.

## Where to resume

**Do not start here.** P1 (the module host) and P2 (pillar minimums) come first — see
[docs/NEXT.md](../../../docs/NEXT.md).

When they close, the first action in this directory:

> Run `coord new-module zones` — it fills the code projects in around these docs and leaves them
> untouched — then write `ZoneOccupancy` and its tests **before anything that touches a window**.
> Assign, cycle, reconcile: all pure, all testable with no desktop, with the three invariants in
> [ARCHITECTURE §2](docs/ARCHITECTURE.md#2-the-occupancy-model--the-heart-of-the-module) written as
> failing tests first — and **start with the case the first design could not represent**: the same
> template applied to two monitors, keeping two independent stacks.

Then, in order:

1. **Armed-region computation**, with the test that a zone leaves the set when its depth drops below
   two. That test is what stops `Win`+wheel swallowing scroll events over ordinary windows. Then the
   refusal path — a refused publication leaves the previous set active, and the empty set is always
   accepted — because §7.3's recovery is built on that guarantee and a guarantee nobody has seen hold
   is decoration.
2. **The Atlas raise path** (ADR 0014) and manual-validation row `Z-4` — the foreground lock is the
   module's largest unknown and the cheapest thing to find out. Do it before building the overlay,
   not after: if activation is refused in a way that cannot be worked around, the *design* absorbs it
   (raise-without-activate is already the default), but you want to know on day one.
3. **The drag overlay**, which is the module's only Windows code and its only visual affordance for
   stack depth in M1.
