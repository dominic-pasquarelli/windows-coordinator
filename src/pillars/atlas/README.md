---
title: Atlas (pillar) — code front door
tier: pillar
status: living
updated: 2026-08-08
audited: 2026-08-08
module: atlas
related:
  - docs/ATLAS.md
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/NEXT.md
---

# Atlas — desktop spatial truth

> **The pillar that owns what the desktop is** — monitors, work areas, DPI and scaling, virtual
> desktops, windows and their geometry and state — read as one coherent snapshot, plus the pure
> layout math that turns a template and a work area into rectangles.
>
> **One sentence:** this directory holds Atlas's model types and the layout math; the contract they
> must satisfy is [docs/ATLAS.md](../../../docs/ATLAS.md), and **none of it has ever been
> compiled**.

## Status: contract types written, never compiled

`Coordinator.Atlas.Core/` exists. It holds `Coordinator.Atlas.Core.csproj` and four source files:

| File | What is in it |
|---|---|
| `Geometry.cs` | The `CoordinateSpace` enum — every rectangle carries the space it is in, so an ambiguous rectangle cannot exist — and `Rect`, an integer rectangle with `Width`, `Height`, `IsEmpty`, `Contains` and `FromSize`. |
| `DesktopModel.cs` | The model: `MonitorId`, `WindowRef`, `WindowState`, `MonitorInfo`, `WindowInfo`, and `DesktopSnapshot` with its `Primary`, `FindMonitor`, `FindWindow` and `MonitorOf` accessors. |
| `Layout.cs` | `LayoutCell` and `LayoutTemplate` (fractions, never pixels), and the resolved side: `ZoneRect` and `ZoneSet`, which carries the topology generation it was computed at. |
| `LayoutMath.cs` | **The zone-rectangle math** — `LayoutMath.Resolve(template, workArea, topologyGeneration)` implementing the boundary-first rounding algorithm, `LayoutMath.HitTest(zoneSet, x, y)`, and the `LayoutResult` / `LayoutRefusalReason` outcome types. |

This is more than declarations: `LayoutMath.Resolve` is written as real arithmetic, not a stub. That
makes the honesty boundary sharper rather than softer — **an algorithm nobody has executed is a
hypothesis**, and the seam property it was written to guarantee (adjacent zones sharing an exact
edge at every work-area width) has never been observed holding or failing.

What is **not** here: the placement policy and its outcomes, the qualifying-window predicate, and
any interface through which a snapshot is obtained. There is no type in this project that a module
would call to *get* a desktop; there is only the shape a desktop has.

And it compiles, and the arithmetic is tested. GitHub Actions at `7aef6ff` (2026-08-08) — Ubuntu and Windows, 0 warnings under `TreatWarningsAsErrors`; `Coordinator.Atlas.Core.Tests` passes
**25 tests** across the layout math (the seam property swept over widths, refusals, negative-origin
monitors, gap and padding, hit-testing) and the snapshot immutability guarantee.

That is the Core/Shell split paying for itself: this ran on a Linux runner with no monitor attached.
It is also the entire claim — **no monitor has ever been enumerated and no window has ever been
moved**, because the Shell adapter that would do either does not exist. Nothing here has been
compiled on a developer machine (**TD-1** in [docs/TECH_DEBT.md](../../../docs/TECH_DEBT.md)).

| | State |
|---|---|
| Architecture spine ([docs/ATLAS.md](../../../docs/ATLAS.md)) | **done** — model, snapshot contract, coordinate spaces, layout math, placement contract |
| Decisions (ADR 0003, ADR 0006) | **done** |
| `Coordinator.Atlas.Core` — model types, geometry, the layout math | **compiles, 25 tests passing** (CI `7aef6ff`) |
| Placement policy, the qualifying-window predicate, the snapshot source | **TODO** — not started |
| `Coordinator.Atlas.Shell` | **TODO** — not created |
| Core tests | **TODO** — not created |
| Manual-validation rows | **TODO** — nothing here has ever run on Windows |

## Intended layout

The pillar follows the same Core/Shell split as every module
([docs/COORDINATOR.md §3](../../../docs/COORDINATOR.md#3-the-coreshell-split--the-central-architectural-commitment)),
and today only part of the Core half exists:

```text
src/pillars/atlas/
├── README.md                          ← you are here (the pillar's front door)
├── Coordinator.Atlas.Core/            net9.0 · zero Windows dependencies · testable on any OS
│   ├── Coordinator.Atlas.Core.csproj
│   ├── Geometry.cs                    written — coordinate spaces, Rect
│   ├── DesktopModel.cs                written — monitors, windows, the snapshot shape
│   ├── Layout.cs                      written — templates, cells, zones
│   └── LayoutMath.cs                  written — THE LAYOUT MATH
│                                      still missing here: the qualifying-window predicate,
│                                      snapshot freshness rules, placement policy and outcomes
└── Coordinator.Atlas.Shell/           NOT CREATED — net9.0-windows · the thin adapter
                                       window and monitor enumeration, DPI queries, the position
                                       call, visible-bounds queries, virtual-desktop interop,
                                       generation bumps
```

The **project and assembly** carry the `.Core` suffix so they pair with a future
`Coordinator.Atlas.Shell`; the **namespace** is plain `Coordinator.Atlas`, because a consumer should
not have to name which half of the split a type came from.

Core decides everything; Shell decides nothing. Every geometry value is converted into a
space-tagged Core type exactly once, at the Shell boundary — see
[docs/ATLAS.md §5](../../../docs/ATLAS.md) and [§8](../../../docs/ATLAS.md).

## Read order

1. [docs/ATLAS.md](../../../docs/ATLAS.md) — **the contract.** The model, the snapshot contract, the
   coordinate spaces and the DPI problem, the layout math, and what placement will and will not do.
2. [docs/COORDINATOR.md](../../../docs/COORDINATOR.md) — the platform frame: the Core/Shell split,
   the principle list, and the roadmap whose P2 and P3 gates this pillar has to satisfy.
3. [docs/CONDUIT.md](../../../docs/CONDUIT.md) — the sibling pillar. Atlas installs no hooks of its
   own; display-topology and window notifications arrive through Conduit.
4. [docs/MODULE_SPEC.md](../../../docs/MODULE_SPEC.md) — the consumer side: how a module obtains a
   snapshot and requests a placement.
5. [CLAUDE.md](../../../CLAUDE.md) and [docs/NEXT.md](../../../docs/NEXT.md) — standing orientation
   and what to do right now.

## Decisions that shaped Atlas

ADRs live in the **unified** log at [`docs/decisions/`](../../../docs/decisions/) — a single
chronological project record, never split per pillar ([docs/DOC_SPEC.md
§2.3](../../../docs/DOC_SPEC.md)). The two that govern this directory:

- **ADR 0003 — the Core/Shell split.** Why every pillar is two projects. Atlas is the sharpest
  example: the layout math is the hardest part of the first module to get right and needs no
  desktop to verify.
- **ADR 0006 — Atlas: one canonical desktop model; modules never enumerate the desktop.** Why
  compound state must stay coherent, and why two independent caches produce a bug nobody can
  reproduce.

## Where to resume

**Atlas is blocked on the toolchain, not on design.** Do not add more types here until a
`dotnet build` has judged the ones already written — that build succeeding at least once on a
Windows/.NET 9 machine is the active focus in [docs/NEXT.md](../../../docs/NEXT.md).

When that unblocks, the **first action is the part that needs no Windows at all** — and it is not
writing the math, which is already written, but finding out whether it is right:

> In the existing `Coordinator.Atlas.Core` project, compile `LayoutMath.Resolve` and then write the
> table-driven test for every row of the case table in
> [docs/ATLAS.md §6](../../../docs/ATLAS.md), starting with *adjacent zones share an exact edge at
> every work-area width*. Then widen to the rows that are easy to get wrong: a work area smaller
> than the template's minimum, an inverted one, negative origins from a monitor arranged left of the
> primary, and odd widths where the rounding decision actually shows.

**Make the seam test fail before you trust it.** The usual instruction — write the guard, watch it
fail, then fix — has to be adapted here, because the implementation it guards already exists and
would go green on the first run. A test that has only ever been seen passing has demonstrated
nothing ([docs/OPERATING_MODEL.md §7](../../../docs/OPERATING_MODEL.md) — a check that cannot fail).
So substitute the naive per-zone-width computation, which lays each zone end to end and rounds each
width independently, confirm the test catches the one-pixel seam and overlap that produces, and then
restore `LayoutMath.Resolve`. That exercise runs on Linux, needs no monitor, and is the concrete
proof that the Core/Shell split earns its two-project tax.

Only after the math is green should the Shell adapter start — beginning with enumeration and the
space conversions (§5), because everything downstream is wrong if the numbers arriving at the
boundary are in the wrong space.
