---
title: Modules — where the product lives
tier: module
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/MODULE_SPEC.md
  - docs/recipes/add-a-module.md
  - docs/COORDINATOR.md
  - docs/vision.md
  - docs/NEXT.md
---

# Modules — one self-contained directory each

> **The modules are the product.** The host, the platform core and the two pillars exist so that a
> module author can write one behaviour and inherit identity, settings, updates, triggers, desktop
> truth and a settings page without asking for any of them.
>
> **One sentence:** each module gets exactly one directory here, self-contained — its code, its
> docs, its decisions and its resume point travel together — and **right now there are none, on
> purpose**.

## Status: empty, deliberately

There is no module in this repository. Not a directory, not a stub, not a placeholder. That is a
decision, not an omission: an empty directory is a claim, and this project does not make claims it
has not earned. The scope discipline behind that is
[docs/COORDINATOR.md §9](../../docs/COORDINATOR.md).

| Module | What it will do | State |
|---|---|---|
| **Zones** (M1) | Window management in the FancyZones idiom: layout templates, per-monitor zone sets, drag-to-snap. The first real consumer of **both** pillars, and the first outside consumer of the module contract. | **PLANNED — no code, no directory** |
| **Chrono** (M2) | Timers, pomodoro, reminders. The first consumer of scheduled triggers and of the notification path — and, more usefully, the *second independent* consumer of the module contract, which is the only thing that actually tests a contract. | **PLANNED — no code, no directory** |
| Launcher · Clipboard · PinTop · Palette · Focus · Restore | Ideas, parked. | **NOT PLANNED** — they live in [docs/vision.md](../../docs/vision.md) and nowhere else |

Neither Zones nor Chrono is scaffolded. When one is built it will be built from
[docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md), not from a skeleton someone left lying here
months earlier with no memory of what it was for.

Note also that no C# anywhere in this repository has been compiled *locally* — there is no .NET SDK in the
environment it was authored in — so the contract a module will be written against is itself
unverified (**TD-1** and **TD-5** in [docs/TECH_DEBT.md](../../docs/TECH_DEBT.md)).

## The shape of a module directory

One directory per module, named in lowercase, plain and descriptive. The name becomes the permanent
module id, so it is chosen once and never changed.

```text
src/modules/<name>/
├── README.md                      front door: what it does, what it publishes,
│                                  done-vs-TODO, and "Where to resume"
├── Coordinator.<Name>.Core/       net9.0 · zero Windows dependencies · every decision
│                                  lives here: geometry, state machines, scheduling,
│                                  settings shapes, capability and trigger declarations
├── Coordinator.<Name>.Shell/      net9.0-windows · the thin adapter · omit the project
│                                  entirely if the module needs no Windows surface
└── docs/
    ├── ARCHITECTURE.md            internal design, even if brief
    └── NEXT.md                    the resume anchor, written from day one
```

Tests live outside the module, with the other test projects, in [`tests/`](../../tests/README.md) —
Core tests, runnable on any operating system.

**Why the code and the docs sit together.** A module is meant to be put down for months and picked
back up in under an hour. That works when everything needed to resume is in one subtree a reader
can land in without leaving; it fails the moment the design notes are in one tree, the decisions in
another, and the code in a third. The placement rule is
[docs/DOC_SPEC.md](../../docs/DOC_SPEC.md); the exception is the decision log, which stays unified
in [`docs/decisions/`](../../docs/decisions/) because reading a project's reasoning in the order it
happened is worth more than filing each decision beside its code.

**Why Core and Shell are separate projects rather than folders.** The split has to be enforceable.
The `boundary` check reads project references, `using` directives and target frameworks as text, so
a single project with a Windows target would defeat it silently — and the whole testability
argument with it.

## Adding one

1. **Confirm it deserves to exist.** A real want, or a genuine need to validate the contract. Not to
   round out a category, not because another toolbox has one.
2. Read [docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md) — the complete contract: what to implement,
   what you get free, the lifecycle, the testing requirements, the do's and don'ts.
3. Follow [docs/recipes/add-a-module.md](../../docs/recipes/add-a-module.md) — the same steps with
   the reasoning at each one.
4. Run `coord new-module <name>`, which lays down the directory, the README with its resume section,
   the docs, and the Core/Shell project pair so the shape is right from the first commit.

## The two rules that are not negotiable

A module **never names an input mechanism**. It does not register a hotkey, install a hook, own a
timer, or subscribe to a window-event source. It declares a trigger intent and
[Conduit](../../docs/CONDUIT.md) decides the mechanism. Once two modules own raw registrations,
central arbitration cannot be retrofitted: "who has this chord?" stops having an answer, and the
loser cannot be told it lost.

A module **never enumerates the desktop**. Monitors, work areas, scaling, windows and geometry come
from one [Atlas](../../docs/ATLAS.md) snapshot. Once two modules cache desktop state, coherence
cannot be retrofitted either — and the resulting bug is a window landing twenty pixels off, only
sometimes, on somebody else's monitor arrangement, with no exception and no log line.

Both are enforced mechanically as far as text inspection can enforce anything, and the boundary
check will fail the gate on a module referencing another module or on a Windows type appearing in a
Core project.

## Where to resume

**No module work starts yet.** The ordered path is in [docs/NEXT.md](../../docs/NEXT.md), and it
puts two things ahead of the first module for a specific reason: the platform contract has never
been compiled, and the pillars a module would depend on do not exist. Building the first module on
that base means every error it produces arrives mixed with errors from two layers underneath —
which is the "error found after the expensive step" failure this project names explicitly.

The first action in this directory, when P1 and P2 have closed:

> Run `coord new-module zones`, then write `ZoneSettings` and the layout-template settings shape
> **before any UI and before any window is moved** — because the settings shape is the thing that is
> expensive to change once a real person has saved one, and it is pure Core logic that can be
> host-tested the same afternoon.

Then implement drag-to-snap strictly through declared Conduit intents and Atlas snapshots, and
before stopping, satisfy every item of the shelving contract — whose canonical definition, and the
list of what "all five" actually are, is
[docs/MODULE_SPEC.md §7](../../docs/MODULE_SPEC.md#7-the-shelving-contract). Do not work from a
paraphrase; work from that section, because a mirror that drops an item is how a module ends up
looking shelved without being resumable. A module that does not meet it is a liability — the first
session back is spent re-deriving your own reasoning, and that cost recurs every single time.
