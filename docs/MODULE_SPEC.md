---
title: Windows Coordinator Module Specification
tier: platform
status: stable
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/COORDINATOR.md
  - docs/CONDUIT.md
  - docs/ATLAS.md
  - docs/recipes/add-a-module.md
  - docs/runbooks/manual-validation.md
  - docs/DOC_SPEC.md
---

# Windows Coordinator — the module specification

> The contract between the platform and a **Module**. Read this before creating a module or resuming
> work on one. It tells you what you must implement, what you get for free, where the boundaries are,
> and what "done enough to put down" means.
>
> **One sentence:** a module implements a small lifecycle interface, declares its **capabilities** and
> its **trigger intents**, keeps every decision in a Windows-free Core project, and in exchange
> inherits identity, settings, logging, triggers, desktop truth, a settings page, and an update path.
>
> **⚠ Nothing in this document has been compiled.** The C# below is an interface *sketch* — the
> intended shape of the contract, written in a container with no .NET SDK. Treat every signature as a
> proposal to be verified the first time the solution builds ([COORDINATOR.md §1](COORDINATOR.md)).
> The platform architecture this contract sits inside is [COORDINATOR.md](COORDINATOR.md); the
> step-by-step how-to is [recipes/add-a-module.md](recipes/add-a-module.md), scaffolded by
> `coord new-module <name>`.

---

## 1. What a module is — and is not

A **Module** is a named, self-contained unit that does **one** thing a person would recognize as a
feature: snap windows into zones, run a pomodoro timer. It publishes typed **capabilities** (what it
can do), declares **trigger intents** (when it wants to be woken), and reacts. The platform handles
identity, persistence, updates, input plumbing, desktop truth, and the settings UI.

**The deal:** write one behavior, inherit everything else — and keep inheriting it. A module written
this year and shelved gets next year's platform improvements without being touched, because it speaks
through the membrane rather than around it.

A module **is not**:

- **a separate app.** It runs inside the one host process. It has no `Main`, no window of its own
  unless its behavior genuinely needs one, and no independent update mechanism.
- **a plugin in the runtime-scripting sense.** Modules are compile-time units, registered types
  (COORDINATOR.md principle 11). There is no scripting host, no dynamic code loading from user
  directories, and no third-party extension surface to secure.
- **a place to put shared infrastructure.** If a second, unrelated module would need it, it belongs in
  the platform or a pillar — not in your module written generically. See COORDINATOR.md §9.
- **allowed to know another module exists.** Cross-module coordination, if it is ever needed, will be
  a platform feature with an ADR, not a project reference.

One module alone is a complete, shippable product. Build a module because a real need exists, never to
fill out a category.

---

## 2. The membrane — what a module MUST implement

Three things: a **lifecycle**, a **capability declaration**, and **trigger-intent declarations**. All
three live in the module's **Core** project. The Shell adapter implements none of them.

> Sketches only — these code blocks are illustrative prose and are not compiled by anything. The
> real types in `src/platform/Coordinator.Platform.Core/` do compile (CI `7aef6ff`) and are the
> authority where the two disagree; reconciling them is a named task in that project's README.

### 2.1 The lifecycle interface

```csharp
// Project: Coordinator.Platform.Core — ILLUSTRATIVE, NOT COMPILED.
// (The project/assembly carries the .Core suffix; the namespace does not.)
namespace Coordinator.Platform;

public interface IModule
{
    /// Permanent identity. The Id is chosen once and never changed (§3, §4).
    ModuleIdentity Identity { get; }

    /// Everything this module exposes for binding, settings, and the Shell. Stable ids (§3).
    IReadOnlyList<Capability> Capabilities { get; }

    /// "Wake me when…" — declarations only. The module never registers input itself (§9).
    IReadOnlyList<TriggerIntent> TriggerIntents { get; }

    /// Construction is cheap; this is where real setup happens. Settings are already loaded.
    /// May do I/O. Runs before any trigger can fire.
    ValueTask InitializeAsync(IModuleContext context, CancellationToken ct);

    /// Begin responding. After this returns, dispatch may arrive at any time.
    ValueTask EnableAsync(CancellationToken ct);

    /// A declared trigger fired. Never called on the input hook thread (§5).
    ValueTask HandleAsync(TriggerEvent evt, CancellationToken ct);

    /// A capability was set — from the Shell, a binding, or a command surface.
    /// This is the single setter the whole system funnels through.
    ValueTask<CapabilityResult> ApplyAsync(CapabilityId id, CapabilityValue value, CancellationToken ct);

    /// Stop responding. Must be safe to call after a failed EnableAsync. Must not throw.
    ValueTask DisableAsync(CancellationToken ct);
}
```

Disposal is ordinary `IAsyncDisposable` on the implementing class; the host calls it after
`DisableAsync`. A module that holds no unmanaged resources need not implement it.

**The context** is how a module reaches the platform. It is the *only* way — there are no statics, no
service locator, and no ambient globals. If something is not on the context, a module does not get it.

```csharp
public interface IModuleContext
{
    ModuleIdentity        Identity { get; }
    IModuleLog            Log      { get; }   // scoped to this module; never Console
    ISettingsStore        Settings { get; }   // this module's settings only (§3)
    IAtlas                Atlas    { get; }   // desktop truth — read-only snapshots (ATLAS.md)
    IClock                Clock    { get; }   // injected time; never DateTime.Now in Core
    ITriggerRegistrations Triggers { get; }   // what Conduit granted or refused (CONDUIT.md)
}
```

`IClock` is not decoration. Anything that reads the wall clock directly is untestable, and scheduling
logic that cannot be tested is scheduling logic that will be wrong across a DST boundary or a machine
sleep.

### 2.2 Capability declarations

```csharp
/// A forever-stable address. "zones.apply", "chrono.pomodoro.minutes". Never renamed, never reused.
public readonly record struct CapabilityId(string Value);

public enum CapabilityKind { Action, Toggle, Number, Choice, Text, Reading }

public sealed record Capability(
    CapabilityId   Id,
    CapabilityKind Kind,
    string         Label,        // human-facing; may be renamed freely
    ValueSpec      Value,        // type, range, options — drives validation AND the Shell form
    bool           Bindable = true);
```

`ValueSpec` carries the type and its bounds — a `Number`'s min/max/step, a `Choice`'s options with
their labels, a `Toggle`'s default. Declaring it once is what lets the Shell render a correct settings
form, the settings store validate a loaded value, and a binding surface know what it may send, without
any of them knowing what the module does.

A `Reading` is read-only: `ApplyAsync` must reject it. Readings exist so a module can expose state
(current layout, time remaining) to the Shell and to future bindings without inventing a side channel.

### 2.3 Trigger-intent declarations

```csharp
public readonly record struct TriggerIntentId(string Value);   // stable, like a CapabilityId

public abstract record TriggerIntent(TriggerIntentId Id, string Label)
{
    // The intent kinds and their fields are Conduit's contract — see docs/CONDUIT.md.
    // What THIS spec fixes: a module declares intents and never touches input itself.
}
```

A declaration is a request, not a guarantee. Conduit may refuse one — most obviously when another
module already holds a chord — and the module learns the outcome through `context.Triggers`. A module
must remain useful with a refused intent: report reduced function, do not fault. The intent taxonomy,
the arbitration rules, and the refusal semantics are owned by [CONDUIT.md](CONDUIT.md) and are not
restated here.

### 2.4 Capabilities are the currency

| Field | What it is |
|---|---|
| `Id` | stable string address. Settings and bindings reference this **forever**. |
| `Kind` | presentational category — Action, Toggle, Number, Choice, Text, Reading. |
| `Label` | human-readable, freely changeable, never load-bearing. |
| `Value` | type plus range or options; validated at load and at apply. |
| `Bindable` | whether this may be a hotkey/binding target, or is settings-only. |

**The stability contract.** Once a capability id is published, it must not change meaning and must not
be reused for something else. Saved settings and user-assigned bindings reference ids by string; a
renamed id is a silently broken binding on somebody's machine, and a reused id is worse — it points a
user's old binding at a new behavior. **Add new capabilities freely; never break existing ones.** If a
capability genuinely dies, leave its id retired and unclaimed.

The same rule governs `ModuleIdentity.Id` and `TriggerIntentId`. Three id spaces, one discipline: ids
are permanent, labels are free.

---

## 3. What the platform provides for free

| Service | What you get | You do **not** write |
|---|---|---|
| **Settings** | typed load/save, version stamp, additive-by-default reads, an explicit `ISettingsMigration` chain, validation against your `ValueSpec`s | file paths, serializer setup, backup/restore, "did the update wipe my settings" handling |
| **Identity** | a permanent module id, independent of assembly name, path, or display name | any id scheme of your own |
| **Logging & diagnostics** | a scoped logger, fault attribution by module, state visible in the Shell | log files, rotation, a crash handler |
| **Update delivery** | your module ships in the host's update payload; settings survive by contract | an updater, a version check, a download path |
| **Conduit dispatch** | your declared intents registered, arbitrated, and dispatched off the hook thread | `RegisterHotKey`, hooks, a timer, a message loop |
| **Atlas snapshots** | monitors, work areas, DPI, virtual desktops, window geometry, layout math | monitor enumeration, DPI awareness plumbing, geometry caching |
| **Shell settings page** | a settings page rendered from your declared capabilities | any UI at all, unless your behavior truly needs custom UI |

**The rule:** a module takes **all** platform services through the context. If you need the time, use
`IClock`. If you need to persist something, use `ISettingsStore`. If you need to be woken, declare a
trigger intent. If you need to know where a monitor is, ask Atlas. Reaching around the membrane works
exactly once — and then costs the next person a day.

**The floor is the generic UI.** Every capability must be reachable through your declarations alone.
A module may add rich custom UI as progressive enhancement, but **no capability may be controllable
only through a bespoke panel** — the generic form is what a second surface (§5.1 of
[COORDINATOR.md](COORDINATOR.md)) will one day render for free.

---

## 4. File structure

Every module lives under `src/modules/` in its own directory:

```
src/modules/<name>/
├── README.md                          Front door (required). Frontmatter: tier module,
│                                      module: <name>. States done-vs-TODO and
│                                      "Where to resume" (§7).
├── Coordinator.<Name>.Core/           net9.0 — ALL decision logic (required)
│   ├── Coordinator.<Name>.Core.csproj
│   ├── <Name>Module.cs                implements IModule
│   ├── <Name>Capabilities.cs          CapabilityId constants + declarations
│   ├── <Name>Triggers.cs              TriggerIntent declarations
│   ├── <Name>Settings.cs              versioned settings record + migrations
│   └── ...                            pure domain logic (geometry, state machines, scheduling)
├── Coordinator.<Name>.Shell/          net9.0-windows10.0.19041.0 — thin adapter
│   ├── Coordinator.<Name>.Shell.csproj    (omit this project entirely if the module
│   ├── <Name>ShellAdapter.cs               needs no Windows surface of its own)
│   └── <Name>SettingsPage.xaml            optional rich UI, on top of the generic floor
└── docs/
    ├── ARCHITECTURE.md                internal design (required, even if brief)
    └── NEXT.md                        where to resume (required)
```

Tests live outside the module, with the other test projects:

```
tests/
└── Coordinator.<Name>.Core.Tests/     runs on any OS (§6)
```

**Why this shape.** The module is self-contained: its code, its docs, and its decisions travel
together, and a reader landing in the directory can orient without leaving it. Core and Shell are
separate *projects*, not separate folders in one project, because the split has to be enforceable —
the `boundary` check reads project references and `using` directives, and a single project with a
Windows target would defeat it silently. Module docs co-locate here; the repository `docs/` directory
is platform and pillar material only ([DOC_SPEC.md](DOC_SPEC.md)).

### Naming conventions

| Thing | Pattern | Example |
|---|---|---|
| Module directory | lowercase, plain, descriptive | `zones`, `chrono` |
| Core project | `Coordinator.<Name>.Core` | `Coordinator.Zones.Core` |
| Shell project | `Coordinator.<Name>.Shell` | `Coordinator.Zones.Shell` |
| Test project | `Coordinator.<Name>.Core.Tests` | `Coordinator.Zones.Core.Tests` |
| Namespace | matches the project | `Coordinator.Zones.Core` |
| Module type | `<Name>Module` | `ZonesModule` |
| Settings type | `<Name>Settings` | `ZonesSettings` |
| Module id | lowercase, dotted, permanent | `zones` |
| Capability id | `<moduleid>.<thing>[.<param>]` | `zones.layout.apply` |

Module names are **plain and descriptive**, not evocative codenames — a deliberate departure from the
project this documentation system was adapted from, recorded in ADR 0009. A user reading a tray menu
should know what "Zones" does; nobody should have to learn a vocabulary to use a window snapper.

---

## 5. Lifecycle

```
discovery → construction → settings load → trigger registration → enable
                                                                     │
                                              ┌──────────────────────┤
                                              ▼                      ▼
                                     HandleAsync (trigger)   ApplyAsync (capability)
                                              └──────────────────────┘
                                                                     │
                                                        disable → dispose
```

| Phase | What happens | May it block? |
|---|---|---|
| **Discovery** | the host finds registered module types | n/a — no module code runs |
| **Construction** | the type is instantiated | **No I/O, no throwing.** A constructor that touches the disk delays startup for every module. |
| **Settings load** | the store reads, validates, migrates; your typed settings are ready | platform-side; your migration chain runs here and must be pure and fast |
| **Trigger registration** | Conduit arbitrates your declared intents and records outcomes | platform-side; you are told the results, you do not register |
| **Enable** | `InitializeAsync` then `EnableAsync` | **Yes — I/O is allowed here.** This is the only place expensive setup belongs (principle 7). |
| **Dispatch** | `HandleAsync` / `ApplyAsync` | **Not on the hook thread** — Conduit already moved off it. Still: do not block on network or slow disk; the user is waiting. |
| **Disable** | `DisableAsync` — stop responding, release hooks-adjacent state | must complete promptly and **must not throw** |
| **Dispose** | `DisposeAsync` if implemented | last resort cleanup only |

Two rules fall out of the table and are worth stating alone.

**Resolve once, execute cheap.** Parse settings, compile bindings, precompute geometry, and allocate
buffers during enable or on settings-save. The dispatch path should be pre-resolved and pointer-cheap.
A drag loop is not the place to discover you need to re-read a template.

**Settings changes re-enter through the same door.** When the user edits settings, the platform hands
you the new values and expects the expensive work to happen *there*, not on the next dispatch. Treat
settings-save as a second enable.

**Settings discipline** (COORDINATOR.md principle 6): additive fields read with a safe default so old
settings still load; structural changes take an explicit migration step plus a version bump; a reset is
only ever explicit. Adding a field is the default move — it is compatible in both directions and costs
nothing. Restructuring is the exception and needs a migration with a test that **fails without it**.

---

## 6. Testing requirements

### 6.1 Core tests — required, and they run anywhere

Every module **must** have tests for its Core logic, runnable via `coord test` on any operating system.
No Windows, no monitors, no real desktop required.

What to test:

- **Capability declarations** — every expected id appears, with the right kind and value spec.
- **Apply** — setting a capability actually mutates state; a `Reading` is rejected.
- **Settings** — round-trip, defaults for absent fields, and each `ISettingsMigration` step, with a case that
  fails if the migration is removed.
- **The domain logic** — the geometry, the state machine, the schedule arithmetic. This is the part
  that will be wrong, and it is the part that is cheap to test.
- **Trigger declarations** — the intents you claim to declare are the intents you declare.

Keep Core pure and this is easy. If a test needs a real monitor or a real window handle, the logic is
in the wrong project.

### 6.2 The Shell adapter — validated by hand, on purpose

The Shell adapter is not unit-tested. It is validated by a human at **a real Windows desktop**, working
through [`docs/runbooks/manual-validation.md`](runbooks/manual-validation.md), with the result
recorded. That is the deal the Core/Shell split buys: the untestable part is small enough to check by
hand in one pass, so keep it that way.

### 6.3 The evidence rule

**A green test run is never a claim about window placement, hotkey capture, DPI behavior, or the UI.**
It is a claim about Core logic and nothing more. When you cannot validate on Windows, say exactly what
is host-verified and what is pending, and leave the manual checklist ready — do not round up. This is
the project's evidence standard applied at module scale ([OPERATING_MODEL.md](OPERATING_MODEL.md)); the
same standard governs the C# in this very document, none of which has been compiled.

---

## 7. The shelving contract

Modules are designed to be put down for months or years. Before you stop working on one, it must have
**all five** of the following. This section is the **canonical home** of the list — every other
enumeration in the repository ([AUDIT.md](AUDIT.md) Lens C, [freezes/README.md](freezes/README.md),
the `/audit` and `/freeze` skills) is a mirror, and **if a mirror disagrees with this section, this
section wins**.

1. **A README** stating what it does, what's **done vs. TODO**, and what capabilities it publishes.
2. **A "Where to resume" section** — in the README or the module's `docs/NEXT.md` — naming a
   **specific next action**: the function, the decision, the test that is failing. Not "continue work
   on layouts." Something like: *"`ZoneLayout.Compute` handles one monitor; the multi-monitor path is
   stubbed at the work-area union — decide whether zones span monitors before writing it."*
3. **ADRs for the non-obvious decisions**, in the unified decision log, so future-you does not
   re-litigate a settled call or, worse, quietly reverse it.
4. **Tests that pass** — `coord test` green for the module's Core project. Not "feature-complete";
   just "correct as far as it goes." **Until a .NET SDK is present, this item cannot be ticked at
   all** — record it as *unverified: no toolchain*, never as satisfied-by-default. A silently-ticked
   box is worse than an honest gap, because the gap is the first thing a cold reader needs to see.
5. **An honest status line** on anything Windows-desktop-dependent: what was manually validated, on
   what machine, with what monitor arrangement and scaling, and when. Undated validation is not
   validation.

A module meeting this contract is resumable in **under an hour** after any gap. A module that does not
is a liability — the first session back is spent re-deriving where you left off, and that cost recurs
every single time. This is the highest-leverage habit in the repository; treat it as part of the work,
not as paperwork after it.

---

## 8. Do's and Don'ts

### Do

- **Put every decision in Core.** If it branches on anything but a null or a Win32 error code, it
  belongs on the testable side of the split.
- **Declare capabilities for everything controllable.** If a user could plausibly want to change it or
  bind a key to it, it is a capability — that is how settings, the Shell, and future bindings find it.
- **Declare trigger intents and let Conduit arbitrate.** Handle refusal gracefully; a module with a
  taken chord still works, it just says so.
- **Take the desktop from Atlas, as one snapshot.** Compound state read piecemeal tears; a snapshot is
  internally consistent by construction.
- **Take time from `IClock`.** Every scheduling bug you will ever have is a test you could have written.
- **Resolve once at enable and on settings-save**, then keep dispatch cheap.
- **Write the module's `docs/NEXT.md` as you go**, not at the end. It is the resume anchor.
- **Keep the Shell adapter dull.** Collect facts, call Core, carry out the answer.

### Don't

- **Don't call Win32 from Core.** Not "just this once for a DPI value." The boundary check reads
  `[DllImport]` and Windows namespaces as text and will fail the build gate — which is the point.
- **Don't register your own hotkey.** Conduit owns the input surface so conflicts can be arbitrated
  centrally. Two modules that each grabbed a chord cannot be reconciled after the fact.
- **Don't enumerate monitors or windows.** Atlas is the single canonical model; a second cache is a
  second truth, and the two will disagree exactly when it matters.
- **Don't block a hook callback.** Input hooks sit on the desktop's critical path. Blocking one does
  not slow your module down — it slows the machine down, and the user will blame the toolbox.
- **Don't reach into another module.** No project reference, no shared static, no "just reading its
  settings." If two modules need to cooperate, that is a platform feature with an ADR.
- **Don't hardcode a path.** Settings, logs, and data locations come from the platform. A hardcoded
  path breaks on the next machine, the next user profile, or the next install layout.
- **Don't reuse or rename a capability id.** Ids are permanent (§2.4). Retire, never recycle.
- **Don't build a speculative module.** One real module with clean seams beats three abstractions with
  no consumer (COORDINATOR.md §9).

---

## 9. Creating a new module — checklist

Run `coord new-module <name>` to scaffold, then walk this list. The narrative version, with the
reasoning at each step, is [recipes/add-a-module.md](recipes/add-a-module.md).

```
[ ] Confirm it deserves to exist — a real need, not a category to fill
[ ] Pick the name: plain, descriptive, lowercase; it becomes the permanent module id
[ ] coord new-module <name>          (creates the directory, projects, README, docs/)
[ ] README.md          — what it does, capabilities, done-vs-TODO, Where to resume
[ ] docs/ARCHITECTURE.md — internal design, even if brief
[ ] docs/NEXT.md         — the resume anchor, filled in from day one
[ ] Core project:
    [ ] <Name>Module.cs         implements IModule
    [ ] <Name>Capabilities.cs   ids declared as constants — they are permanent
    [ ] <Name>Triggers.cs       trigger intents; handle refusal
    [ ] <Name>Settings.cs       versioned record, defaults for every field, migrations
    [ ] the domain logic         pure, deps injected, no statics
[ ] Shell project (only if the module needs a Windows surface):
    [ ] adapter — collect facts, call Core, carry out the answer; no decisions
    [ ] optional rich settings page ON TOP OF the generic floor, never instead of it
[ ] Tests: tests/Coordinator.<Name>.Core.Tests/ — declarations, apply, settings, migration,
    and the domain logic; must pass on a non-Windows machine
[ ] Register the module with the host (compile-time registration, not discovery-by-scanning)
[ ] Add a row to the module table in the root README.md
[ ] Add the module to docs/NEXT.md
[ ] ADRs for any non-obvious decision made along the way
[ ] Run: coord test, coord audit, coord map --check
[ ] Manual pass on Windows per docs/runbooks/manual-validation.md — and record what you
    actually observed, not what you expected
[ ] Before stopping: satisfy the shelving contract (§7)
```

---

## 10. Quick reference — what a module touches

| Where | What | Relationship |
|---|---|---|
| `src/platform/` | `IModule`, `IModuleContext`, `Capability`, `TriggerIntent`, settings | **implement / consume** |
| `src/pillars/conduit/` | trigger intents and dispatch — [CONDUIT.md](CONDUIT.md) | **declare**, never call into input |
| `src/pillars/atlas/` | desktop snapshots and layout math — [ATLAS.md](ATLAS.md) | **read**, never enumerate yourself |
| `src/shell/` | the settings-page host | your capabilities are rendered here; you write nothing |
| `src/modules/` | your directory, and everyone else's | **yours only** — never reference a sibling |
| `tests/` | your Core test project | **required** |
| `tools/coord/` | `coord test` · `coord audit` · `coord map` · `coord new-module` | the developer entry point |
