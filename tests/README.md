---
title: Tests — Core test projects, runnable on any OS
tier: tool
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/OPERATING_MODEL.md
  - docs/runbooks/manual-validation.md
  - docs/NEXT.md
---

# Tests — what a green run is allowed to mean

> **Every test project in this repository targets `net9.0` and runs on any operating system.** They
> exercise Core logic — geometry, arbitration, schedule arithmetic, settings migration, capability
> declarations — and they can prove those correct on Linux, in a container, with no desktop present.
>
> **One sentence:** a green `coord test` is a claim about decision logic and nothing else; every
> claim about window placement, hotkey capture, DPI behaviour, the tray or the UI comes from a human
> running [docs/runbooks/manual-validation.md](../docs/runbooks/manual-validation.md) on a real
> Windows desktop, and from nowhere else.

## Status: no test project exists

There is no test project, no test, and no test run. There is also no compiler: the C# in this
repository was authored in an environment with **no .NET SDK**, so nothing has ever been built, let
alone tested (**TD-1** in [docs/TECH_DEBT.md](../docs/TECH_DEBT.md)). Nothing in this directory has
produced a result of any kind.

The Python tooling is the exception worth naming, because it is the one place this project currently
has anything runnable: `coord audit` and `coord map` are stdlib-only Python and they execute against
this repository with no .NET installed at all — they were written here and run here, not sketched.
What any particular run *reported*, though, is a fact about that run and lives in
[docs/audit-log.md](../docs/audit-log.md); a clean audit is not a standing property of the
repository, and this file should never be read as claiming one. They check documents. They are not a
build and they are not a test.

## The testing model

The whole model follows from the Core/Shell split
([docs/COORDINATOR.md §3](../docs/COORDINATOR.md#3-the-coreshell-split--the-central-architectural-commitment),
ADR 0003) — what each half contains and what each targets is defined there and not repeated here.
The consequence that belongs to *this* directory is that which half something is in decides how it
is verified, and there is no third option:

| | **Core** | **Shell adapter** |
|---|---|---|
| Verified by | unit tests here, via `coord test` | a human, against a runbook, at a real Windows desktop |
| Automatable | yes | no, and pretending otherwise is the failure mode |

**This is what CI can cover, and it is the only thing it can cover.** On a Linux runner, only the
Core projects are buildable and testable at all; everything Windows-targeted is invisible to it —
both pillar adapters, the WinUI host, and every P/Invoke path. That is tracked as **TD-4**, and the
danger it names is not the gap itself but reading a green badge as coverage.

## What belongs in a Core test

The rule of thumb: **if a test needs a real monitor, a real window handle, or a real keystroke, the
logic is in the wrong project.** Move the decision into Core and give the adapter nothing to decide.

Worth testing, and cheap to:

- **The zone-rectangle math** — a table of work areas and templates with literal expected
  rectangles, including a work area smaller than the template's minimum, an inverted one, negative
  origins (a monitor arranged left of the primary one), and mixed scale factors. The first row to
  write is *adjacent zones share an exact edge at every work-area width*, and it should be watched
  failing against a naive per-zone-width implementation before it is trusted.
- **Trigger arbitration** — two modules declaring the same chord resolve centrally and
  deterministically, and the loser is told it lost, by name. This is an assertion on a value
  returned by a pure function, and it is the scenario the input pillar exists for.
- **Schedule arithmetic** — drift policy, missed fires across a machine sleep, and a civil-time
  discontinuity in both directions. All of it is arithmetic over an injected clock.
- **Settings migration** — a document written under the old schema loads under the new one. Write
  the test first, watch it fail without the migration, then add the migration.
- **Capability declarations** — the ids a module claims to publish are the ids it publishes, with
  the kinds it says. Cheap, and it catches a renamed id before a user's binding does.

## What a green run does not mean

This is the sentence to keep saying, in reviews and in commit messages, because it is the one that
gets blurred every session:

> **A green test run is never a claim about window placement, hotkey capture, DPI behaviour, tray
> presence, or the UI.**

Specifically, no result from this directory can establish: that a chord actually fired; that the
operating system granted a registration; that a hook callback returned fast enough on a loaded
machine; that a real multi-monitor arrangement enumerated correctly; that a cloaked window was
excluded; that visible-bounds compensation produced a flush edge on a real screen; that placement
survived a DPI transition; that the tray icon appeared; that settings survived a restart on a real
install.

Every one of those is a row in
[docs/runbooks/manual-validation.md](../docs/runbooks/manual-validation.md), performed by a person,
recorded with the date and the machine. Core-verified and Windows-validated are different words
because they are different facts — the full statement of the standard, its three recurring failure
shapes, and the "prove the guard fails without the fix" rule are in
[docs/OPERATING_MODEL.md](../docs/OPERATING_MODEL.md).

## Layout and conventions

One test project per Core project, named after it with a `.Tests` suffix, living here rather than
inside the module or pillar it tests — so that a module subtree stays liftable and so that the test
projects can be built and run as one set:

```text
tests/
├── README.md                              ← you are here
├── Coordinator.Platform.Core.Tests/       the module membrane
├── Coordinator.Conduit.Core.Tests/        intents, arbitration, refusal, schedules
├── Coordinator.Atlas.Core.Tests/          geometry, the snapshot, THE LAYOUT MATH
└── Coordinator.<Name>.Core.Tests/         one per module
```

The `.Core.Tests` suffix tracks the project under test — every Core project carries a `.Core` suffix
so it pairs with its `.Shell` adapter — and it is what `coord new-module` generates, so a
hand-written test project should match rather than invent a shorter name.

Every project here targets `net9.0` with no Windows suffix. A test project that needs a
`-windows` target is a signal that the thing it is testing is on the wrong side of the split, and
the fix is to move the logic rather than to move the target framework.

Shared MSBuild properties come from `Directory.Build.props` at the repository root, so nullable
reference types, the language version and warnings-as-errors apply here exactly as they do to the
code under test.

## Where to resume

**Blocked on the toolchain.** No test can run until a `dotnet build` has succeeded once on a
machine with the .NET 9 SDK — the Active focus in [docs/NEXT.md](../docs/NEXT.md).

When that unblocks, the first action is the one that needs no Windows at all and proves the most:

> Create `Coordinator.Atlas.Core.Tests`, and write the seam test first: for a two-cell template
> split at 0.5, assert that the left zone's right edge **equals** the right zone's left edge, for a
> table of work-area widths including odd ones. Because `LayoutMath.Resolve` is already written, the
> test will go green on its first run and prove nothing — so substitute an implementation that
> computes each zone's width independently and lays the zones end to end, watch the test catch the
> one-pixel seam and overlap that independent rounding produces, and only then restore
> `LayoutMath.Resolve` and confirm it passes.

That single test is worth writing before any other because of what it establishes at once: that the
test runner works on a non-Windows machine, that a Core project really is Windows-free, that the
split earns its two-project cost, and that this project's first guard was observed failing before it
was trusted. A guard nobody has seen fail is decoration.

Only then widen: the rest of the geometry table, arbitration, schedule arithmetic, and the settings
migration — and add the first row to the manual-validation runbook for everything the tests above
have just proved they cannot reach.
