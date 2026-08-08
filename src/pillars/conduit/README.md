---
title: Conduit (pillar) — code front door
tier: pillar
status: living
updated: 2026-08-08
audited: 2026-08-08
module: conduit
related:
  - docs/CONDUIT.md
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/NEXT.md
---

# Conduit — the input & trigger fabric

> **The pillar that owns every way a module can be woken up** — hotkey chords, window events,
> schedules, tray actions, and input gestures. Modules declare typed *trigger intents*; Conduit
> arbitrates who gets what and dispatches the result somewhere it is safe to do work.
>
> **One sentence:** this directory holds Conduit's declaration types; the contract they must satisfy
> is [docs/CONDUIT.md](../../../docs/CONDUIT.md). The declarations **compile**; the arbiter that
> gives them meaning is unwritten.

## Status: declarations compile; the arbiter that gives them meaning is unwritten

`Coordinator.Conduit.Core/` exists. It holds `Coordinator.Conduit.Core.csproj` and three source
files — the **declaration** half of the pillar:

| File | What it declares |
|---|---|
| `TriggerIntent.cs` | `TriggerIntentId`, the abstract `TriggerIntent`, and four of the five intent kinds: `HotkeyIntent`, `WindowEventIntent` (with the `WindowEventKinds` mask), `ScheduleIntent` (with `ScheduleDrift` and `MissedFirePolicy`), `TrayActionIntent`. The input-gesture recogniser that [docs/CONDUIT.md §3](../../../docs/CONDUIT.md) specifies is deliberately not declared — no recogniser and no consumer exists to shape it. |
| `TriggerRegistration.cs` | The `RefusalReason` enum and the `TriggerRegistration` result type with its `Granted` and `Refused` cases — a registration answer as a value the caller has to look at. |
| `TriggerDispatch.cs` | `TriggerEvent` (intent id, capability id, monotonic stamp — no key code, no handle, no mechanism) and the `TriggerDispatchHandler` delegate. |

**What is declared is not what is decided.** These are records, enums and one delegate. There is no
registry, no arbiter, no interface a module registers through, and no dispatcher — so the behaviour
this pillar exists for, central conflict arbitration, has not been written.

The C# here was authored in an environment with **no .NET SDK** (**TD-1** in
[docs/TECH_DEBT.md](../../../docs/TECH_DEBT.md)), so CI was its first reader. It compiles: GitHub
Actions at `7aef6ff` (2026-08-08) — Ubuntu and Windows, 0 warnings under `TreatWarningsAsErrors`.
Nothing here has been compiled on a developer machine, and **no hook has ever been installed and no
chord has ever been registered**.

**It has no tests, and that is the honest gap here** — unlike Atlas, this pillar's interesting logic
(the arbiter that decides who gets a contested chord) is not written yet, so there is nothing to
test. Compiling a set of declarations proves they are well-formed and nothing more. Not one input
event has ever been dispatched.

| | State |
|---|---|
| Architecture spine ([docs/CONDUIT.md](../../../docs/CONDUIT.md)) | **done** — intent taxonomy, arbitration model, dispatch contract, extension contract |
| Decisions (ADR 0003, ADR 0005) | **done** |
| `Coordinator.Conduit.Core` — the declaration types | **compiles** (CI `7aef6ff`), **no tests** |
| The chord grammar, the registry, the arbiter, the dispatcher | **TODO** — not started |
| `Coordinator.Conduit.Shell` | **TODO** — not created |
| Core tests | **TODO** — not created |
| Manual-validation rows | **TODO** — nothing here has ever run on Windows |

## Intended layout

The pillar follows the same Core/Shell split as every module
([docs/COORDINATOR.md §3](../../../docs/COORDINATOR.md#3-the-coreshell-split--the-central-architectural-commitment)),
and today only part of the Core half exists:

```text
src/pillars/conduit/
├── README.md                            ← you are here (the pillar's front door)
├── Coordinator.Conduit.Core/            net9.0 · zero Windows dependencies · testable on any OS
│   ├── Coordinator.Conduit.Core.csproj
│   ├── TriggerIntent.cs                 written
│   ├── TriggerRegistration.cs           written
│   └── TriggerDispatch.cs               written
│                                        still missing here: the chord grammar, the registry, the
│                                        ARBITER, the lease lifecycle, schedule arithmetic, the
│                                        queue/coalescing policy, recogniser state machines
└── Coordinator.Conduit.Shell/           NOT CREATED — net9.0-windows · the thin adapter
                                         hotkey registration, low-level hooks, the window-event
                                         source, timer plumbing, the tray icon and menu, thread
                                         ownership
```

The **project and assembly** carry the `.Core` suffix so they pair with a future
`Coordinator.Conduit.Shell`; the **namespace** is plain `Coordinator.Conduit`, because a consumer
should not have to name which half of the split a type came from.

Core decides everything; Shell decides nothing. If an `if` appears in the Shell adapter that is not
a null check or an error check, the decision belongs in Core — see
[docs/CONDUIT.md §6](../../../docs/CONDUIT.md).

## Read order

1. [docs/CONDUIT.md](../../../docs/CONDUIT.md) — **the contract.** The trigger-intent taxonomy, the
   arbitration ladder, the hook-thread constraint, and how to add a trigger kind.
2. [docs/COORDINATOR.md](../../../docs/COORDINATOR.md) — the platform frame: the Core/Shell split,
   the principle list, the host lifecycle this pillar's refusals plug into, and the roadmap.
3. [docs/MODULE_SPEC.md](../../../docs/MODULE_SPEC.md) — the consumer side: how a module declares an
   intent and receives a dispatch.
4. [CLAUDE.md](../../../CLAUDE.md) and [docs/NEXT.md](../../../docs/NEXT.md) — standing orientation
   and what to do right now.

## Decisions that shaped Conduit

ADRs live in the **unified** log at [`docs/decisions/`](../../../docs/decisions/) — a single
chronological project record, never split per pillar ([docs/DOC_SPEC.md
§2.3](../../../docs/DOC_SPEC.md)). The two that govern this directory:

- **ADR 0003 — the Core/Shell split.** Why every pillar is two projects, what the testability buys,
  and what the two-project tax costs.
- **ADR 0005 — Conduit: modules declare trigger intents and never own raw input hooks.** Why central
  conflict arbitration is the retrofit-expensive part, and therefore why this pillar is scheduled to
  be built first.

## Where to resume

**Conduit is blocked on the toolchain, not on design.** Do not add more types here until a
`dotnet build` has judged the ones already written — that build succeeding at least once on a
Windows/.NET 9 machine is the active focus in [docs/NEXT.md](../../../docs/NEXT.md).

When that unblocks, the **first action is the arbiter** — the thing this pillar exists for, and the
one part of it that is not yet written:

> In the existing `Coordinator.Conduit.Core` project, add the in-memory registry and the arbitration
> ladder from [docs/CONDUIT.md §4](../../../docs/CONDUIT.md) over the `TriggerIntent` types that are
> already declared, returning the `TriggerRegistration.Granted` and `TriggerRegistration.Refused`
> values that already exist. Then — *before any Shell adapter exists* — write the test that proves
> two modules requesting the same chord produce
> `Refused(intent, RefusalReason.AlreadyHeldByAnotherModule, HeldByModuleId: "zones")`,
> deterministically, in that order, every run.

That single test is the reason this pillar exists, it runs on any OS with no desktop attached, and
having it green before a single line of Win32 is written is what keeps the arbiter in Core where it
belongs. Everything else in [docs/CONDUIT.md](../../../docs/CONDUIT.md) — the chord grammar, the
schedule arithmetic and its DST and sleep-resume cases, the queue policy — follows the same pattern
and can be built in any order after it.

**Do not** begin with `RegisterHotKey`. A working hotkey with no arbiter behind it is the exact
shape this pillar was created to prevent, and it is much harder to unwind than to not write.
