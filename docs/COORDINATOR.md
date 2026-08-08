---
title: Windows Coordinator Platform Architecture
tier: platform
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/MODULE_SPEC.md
  - docs/CONDUIT.md
  - docs/ATLAS.md
  - docs/OPERATING_MODEL.md
  - docs/NEXT.md
  - docs/runbooks/manual-validation.md
---

# Windows Coordinator — the platform architecture

> **This is the primary architecture document.** It answers "what *is* this system": the host, the
> platform core, the two pillars, and the modules that sit on top. Module-internal design lives in
> each module's own docs; the contract a module must satisfy is [MODULE_SPEC.md](MODULE_SPEC.md).
>
> **One sentence:** Windows Coordinator is a single tray-resident host that loads independent
> **Modules** through one membrane, giving each of them identity, settings, triggers, desktop truth,
> a settings UI, and an update path — so a module author writes one behavior and inherits everything
> else.
>
> **Read order:** [../CLAUDE.md](../CLAUDE.md) → [NEXT.md](NEXT.md) → **this** →
> [MODULE_SPEC.md](MODULE_SPEC.md) → the pillar docs ([CONDUIT.md](CONDUIT.md), [ATLAS.md](ATLAS.md)).

---

## 1. What Windows Coordinator is

Windows Coordinator is a personal Windows productivity toolbox in the spirit of PowerToys: one
tray-resident process that hosts a set of small, independent utilities — window zones, timers, and
whatever else earns its place later. It is deliberately *not* a suite of separate apps and *not* a
launcher shell. It is one host, one settings surface, one update channel, and N modules.

Three commitments shape everything below.

**It feels like stock Windows.** The Shell UI is WinUI 3 (Windows App SDK) because the target look is
the one the operating system already ships: the same typography, the same Mica surfaces, the same
settings-page idiom. A utility that announces itself with a custom chrome language has already failed
the brief. The user should not be able to tell where Windows ends and the toolbox begins.

**A module is the unit of everything.** One module owns one behavior, ships with its own docs and
tests, and can be built, shelved, and resumed independently. The app is useful with a single module
installed and no others — that is the honest MVP, not a milestone on the way to one. Everything the
platform does exists so that a module author can write domain logic and nothing else.

**Logic is Windows-free.** Every module and pillar is split into a pure `net9.0` **Core** and a thin
Windows **Shell adapter** (§4). This is the load-bearing decision of the whole architecture: it is
what makes any of this testable, and it is why an evidence claim in this project can mean something.

**Provenance.** The documentation system, audit protocol, snapshot/capture protocol, and evidence
standard are adapted from a mature embedded project (Axon) that this project's owner also maintains.
The adaptation is recorded in ADR 0001; the *why* beneath the rules is [OPERATING_MODEL.md](OPERATING_MODEL.md).

**Honesty boundary, stated up front.** At the time of writing, **no C# in this repository has ever
been compiled.** The bootstrap was authored in a container with Python 3.11 and Node and **no .NET
SDK**. The Python tooling (`tools/coord/`, `tools/doc-audit/`) is executed and verified; every C#
artifact — including the interface sketches in [MODULE_SPEC.md](MODULE_SPEC.md) — is written and
unverified. The first task in [NEXT.md](NEXT.md) is to restore the toolchain on a Windows/.NET
machine, generate the solution, compile the skeleton, and record the result. Until that is done,
nothing here may be described as building, passing, or working.

---

## 2. The mental model (memorize this)

```
   the host          the platform core        the pillars            the modules
   ────────          ─────────────────        ───────────            ───────────
   one tray-         module host, registry,   Conduit (input &       Zones, Chrono,
   resident          identity, settings,      trigger fabric)        and whatever
   process           update channel,          Atlas (desktop         earns its place
                     logging, the Shell UI    spatial truth)
```

**Host + core + two pillars + N modules.** The *host* is the process: it starts, loads, and supervises.
The *platform core* is the set of services every module gets without asking. The *pillars* are the two
cross-cutting subsystems that every module builds on and that no module may bypass. The *modules* are
the product.

A module never talks to Windows about input and never talks to Windows about the desktop. It
**declares** what it wants to be woken by (Conduit) and **reads** what the desktop currently looks
like (Atlas). Those two rules are the reason the toolbox can grow without turning into a pile of
competing hooks and stale monitor caches.

### 2.1 The layered model

```
┌── WINDOWS COORDINATOR — platform core (domain-agnostic) ──────────────────────┐
│  module host & lifecycle · module registry & stable identity                  │
│  settings (versioned, migrated) · update / delivery channel                    │
│  logging & diagnostics · the Shell (WinUI settings + dashboard)                │
│  ══ the module membrane ══  ◄──── IModule + capabilities + trigger intents     │
├── PILLARS ────────────────────────────────────────────────────────────────────┤
│  Conduit — the input & trigger fabric   │  Atlas — desktop spatial truth       │
│  hotkeys, window events, schedules,     │  monitors, work areas, DPI, virtual  │
│  tray actions; one owner, arbitrated    │  desktops, window geometry, layout   │
└────────────────────────────────────────────────────────────────────────────────┘
        ▲  modules declare capabilities + trigger intents; they call down, never sideways
┌── MODULES ────────────────────────────────────────────────────────────────────┐
│  Zones (M1 — planned)  ·  Chrono (M2 — planned)  ·  future utilities           │
└────────────────────────────────────────────────────────────────────────────────┘
```

- **Platform core** = `src/platform/` (the contract interfaces and the host services) plus
  `src/shell/` (the WinUI host, Windows-only).
- **Pillars** = `src/pillars/conduit/` and `src/pillars/atlas/`.
- **Modules** = `src/modules/` — one directory per module, self-contained.
- **Tests** = `tests/` — Core test projects, runnable on any OS.

The arrows only point one way. A module depends on the platform and the pillars. The platform never
depends on a module, and a module never depends on another module. That boundary is mechanically
enforced by the `boundary` check in [`tools/doc-audit/`](../tools/doc-audit/README.md), which reads
`using` directives, namespaces, `[DllImport]` attributes, and `ProjectReference` elements as text —
so it works even while the C# remains uncompiled.

---

## 3. The Core/Shell split — the central architectural commitment

Every module and every pillar is **two projects**.

| | **Core** | **Shell adapter** |
|---|---|---|
| Target | `net9.0` | `net9.0-windows10.0.19041.0` |
| Windows dependencies | **zero** | all of them |
| Contains | decision logic, geometry math, state machines, scheduling, settings shapes, capability declarations | P/Invoke, window handles, hook plumbing, WinUI pages |
| Runs on | any OS — Linux CI, a container, a Mac | Windows only |
| Verified by | unit tests (`coord test`) | [`docs/runbooks/manual-validation.md`](runbooks/manual-validation.md) |
| Size goal | as large as it needs to be | **as thin as physically possible** |

```
        any OS · unit-tested                     Windows only · manually validated
   ┌────────────────────────────┐           ┌────────────────────────────────────┐
   │  Coordinator.Zones.Core     │  ◄──────  │  Coordinator.Zones.Shell           │
   │  "given this work area and  │  calls    │  "here is the real work area;      │
   │   this template, the zone   │  into     │   now move this real window there" │
   │   rectangles are …"         │           │                                    │
   └────────────────────────────┘           └────────────────────────────────────┘
```

The Shell adapter's job is to **collect facts, hand them to Core, and carry out Core's answer**. It
decides nothing. If you find yourself writing an `if` in a Shell adapter that isn't a null check or a
Win32 error check, the decision belongs in Core.

**Why this is the load-bearing decision.** Without it, nothing about this project could be verified
anywhere except a Windows desktop with a human watching. With it, the part that is easy to get wrong —
geometry across mixed DPI, trigger arbitration, settings migration, scheduling arithmetic — is ordinary
testable code, and the part that cannot be automated is reduced to a short, boring adapter whose
failure modes are visible in one manual pass.

**Consequence for honesty, and it is not optional.** A green `coord test` proves Core logic. It proves
**nothing** about window placement, hotkey capture, DPI behavior, tray integration, or the UI. Those
require a run through [`docs/runbooks/manual-validation.md`](runbooks/manual-validation.md) performed
by a human at a real Windows desktop with real monitors. Any sentence that lets a green test run stand
in for a desktop behavior
claim is a defect in the documentation, not a shortcut. The full statement of the standard, its three
recurring failure shapes, and the "prove the guard fails without the fix" rule live in
[OPERATING_MODEL.md](OPERATING_MODEL.md).

**The cost, stated plainly.** Two projects per unit, and a mapping layer between Core's own types and
whatever Win32 hands you. That is real friction, paid on every module. It is worth it, and the
reasoning is recorded in ADR 0003 so it is not re-litigated every time it stings.

---

## 4. The platform core services

These are the services a module gets by existing. Each entry states what the platform **guarantees**;
the module-facing shapes are specified in [MODULE_SPEC.md](MODULE_SPEC.md).

| Service | What a module gets | Guarantee |
|---|---|---|
| **Module host & lifecycle** | discovery, construction, ordered enable/disable, supervised dispatch | the phases run in a fixed order (§6); a module is never dispatched before enable or after disable |
| **Module registry & stable identity** | a permanent module id, independent of assembly name, file path, or display name | the id survives renames, moves, and reinstalls; settings and bindings key on it |
| **Settings** | typed load/save, versioning, additive-by-default schema, explicit `Migrate()` | settings survive an update; a reset only ever happens because someone asked for one |
| **Update / delivery channel** | the module ships inside the host's update payload; no per-module updater | a module written today can be changed tomorrow on an install that already exists |
| **Logging & diagnostics** | a scoped logger, a crash/fault record, module state visible in the Shell | a fault is attributable to a module by name, not to "the app" |
| **The Shell (settings UI)** | a hosted settings page rendered from the module's declared capabilities | a module with no custom UI at all is still fully configurable |

Two of these deserve their reasoning in the open.

**Identity is not the display name.** A module's id is a stable string chosen once and never changed.
Settings files, hotkey bindings, and the update manifest all reference it. Renaming a module in the UI
must be free; renaming its id must be impossible. This is the same rule that governs capability ids
(§7, principle 5) applied one level up.

**The update channel is built now, before anything needs it.** This looks like premature work and is
not. The operating model's build-now test is "is this painful to graft onto shipped installs?" — and a
delivery channel is the canonical yes: without one, every feature deferred to later is stranded on
every copy already running. The same test admits module identity, settings migration, and trigger
arbitration to the build-now set, and defers everything else to a clean empty seam plus a recall hook.
Recorded in ADR 0008.

---

## 5. The two pillars (spine altitude only)

A **pillar** is a first-class cross-cutting subsystem that every module builds on and that no module
may bypass. There are exactly two. Each exists because a real module needs it and because the thing it
centralizes is impossible to retrofit once modules have gone around it.

**Conduit — the input & trigger fabric.** Modules declare typed **trigger intents** ("wake me on this
chord", "wake me when a window moves", "wake me every 25 minutes", "wake me from this tray item") and
receive dispatched events. Conduit alone owns the low-level input surface, and it alone arbitrates
conflicts when two modules want the same chord. *A module never names an input mechanism.* The full
contract — intent taxonomy, arbitration rules, dispatch threading, and what happens when a
registration is refused — is [CONDUIT.md](CONDUIT.md). First consumers: Zones (drag-snap and a chord),
Chrono (schedules).

**Atlas — desktop spatial truth.** One canonical model of monitors, work areas, DPI and scaling,
virtual desktops, and window handles with their geometry, plus the pure layout math that turns a
template and a work area into rectangles. Modules never enumerate the desktop themselves. *Compound
state stays coherent through a single Atlas snapshot* — two modules independently caching window state
will disagree, and the disagreement will surface as a placement bug nobody can reproduce. The full
contract — snapshot shape, coordinate spaces, freshness, and the layout primitives — is
[ATLAS.md](ATLAS.md). First consumers: Zones (layout and placement), and a future window-restore module.

Those two paragraphs are the whole of what this document says about the pillars. Their contracts have
exactly one home each; this document links, it does not restate. If you find pillar detail creeping in
here, that is a single-source violation and an early sign the boundary is undecided — see
[DOC_SPEC.md](DOC_SPEC.md).

### 5.1 Why the Shell is platform core and not a pillar

The Shell — the WinUI settings and dashboard host — has every surface feature of a pillar: it is
cross-cutting, every module touches it, and it is the most visible part of the product. It is
nonetheless **platform core**, deliberately.

A pillar earns its status by having a contract that more than one consumer needs to hold it to. Conduit
has that (two modules competing for one chord). Atlas has that (two modules needing the same desktop
truth simultaneously). The Shell today has exactly one consumer: itself. Promoting it to a pillar now
would mean designing a surface-agnostic rendering contract against a single implementation — the
speculative-abstraction failure the operating model exists to prevent.

**The graduation trigger, stated so it can actually fire:** *the Shell becomes a pillar when a second
independent surface needs to render the same module settings from the same declarations* — a CLI
settings editor, a web surface, or a companion app. On that day the registry-driven rendering contract
gets extracted, `src/shell/` splits into contract and implementation, and this section is replaced by a
link to a new pillar document. Until that day the Shell is core, and its "contract" is whatever the one
implementation does. This is not indecision; it is the gate-don't-build discipline the operating model
demands, written down where it can be checked.

---

## 6. Lifecycle and degradation

The host's supervision contract is short and absolute: **a module that fails must not take down the
host or any other module.**

Concretely, at each phase:

| Phase | If a module fails here | Result |
|---|---|---|
| Discovery | the candidate is skipped and logged | other modules load normally |
| Construction | the module is recorded **Faulted** with its exception | host continues; Shell shows the fault |
| Settings load | the module is offered defaults, or Faulted if it refuses them | no other module's settings are touched |
| Trigger registration | the refused intent is reported to the module and surfaced in the Shell | the module may run with reduced function |
| Enable | the module is Faulted and left disabled | the host and every other module are unaffected |
| Dispatch | the exception is caught, attributed, and counted | repeated faults disable the module rather than let it wedge input |

The ordered phases themselves, and the rules about what may block on what, are the module contract —
[MODULE_SPEC.md §5](MODULE_SPEC.md). Two host-side guarantees are worth stating here because they are
architectural rather than per-module:

**Dispatch never happens on the input hook.** Conduit's own thread does the minimum required to
acknowledge an input event and hands the work to a dispatch context. A module that does something slow
in a handler makes *itself* sluggish; it cannot make the desktop sluggish. The mechanics belong to
[CONDUIT.md](CONDUIT.md).

**A Faulted module is a first-class state, not a crash.** The registry keeps it, the Shell shows it,
the logs explain it, and the user can retry or disable it. "The tray icon vanished" is never an
acceptable failure mode for a toolbox whose whole value proposition is being unobtrusively present.

---

## 7. Non-negotiable principles

**This section is the canonical home of the principle list.** Other documents link here; they do not
restate it. Changing a principle means editing it here and recording an ADR.

1. **A module is a self-contained unit.** It owns one behavior; the app is useful with any single
   module and no others.
2. **Core/Shell split** — logic is Windows-free and host-testable; the Windows adapter is thin (§3).
3. **A module never names an input mechanism.** Trigger intents go through Conduit (§5).
4. **A module never enumerates the desktop.** Monitors, windows, and geometry come from Atlas (§5).
5. **Every capability is a named, typed binding target** — stable ids; settings and hotkey bindings
   reference them by name, so ids are a permanent contract.
6. **Settings are the source of truth and survive updates** — versioned, additive-by-default (a new
   field read with a default → old settings still load), explicit `Migrate()` for structural changes.
   A reset is only ever explicit.
7. **Resolve once, execute cheap** — parse, compile, and allocate at load or settings-save, never in a
   hook callback or a drag loop. Input hooks are on the UI's critical path; blocking one stalls the
   whole desktop.
8. **Never block the hook or UI thread on I/O.** Disk, network, and process work go off-thread.
9. **Documentation is a load-bearing deliverable, not polish.** A phase isn't done until a cold reader
   could resume from the docs.
10. **Rigid structure, accommodating interests.** Strict enough that work years apart composes; open
    enough that a new interest slots in as a Module.
11. **Compile-time modularity** (registered types), not runtime scripting.
12. **The app degrades, never breaks.** A module that fails to load must not take down the host or any
    other module.

---

## 8. Roadmap

Each phase names its **gate** — the specific, checkable condition that ends it. A phase is not done
because the work feels finished; it is done when its gate is satisfied and the evidence is recorded.
The live, task-level plan is [NEXT.md](NEXT.md); completed arcs drain to [HISTORY.md](HISTORY.md).

### P0 — Bootstrap *(this pass)*

The repository, the documentation system, the operating protocols, the audit tooling, and the `coord`
developer entry point. No product code beyond contract interfaces.

**Gate:** a cold reader can resume from the docs alone; `coord audit` and `coord map --check` run green
with **Python only**, no .NET installed; `coord doctor` correctly reports the missing SDK rather than
failing obscurely; [NEXT.md](NEXT.md) names the first executable task. **Explicitly not claimed:** that
any C# compiles.

### P1 — The skeleton compiles

Generate the solution on a Windows/.NET 9 machine. Bring up the platform core: the contract interfaces,
the module host, the registry with stable identity, and the settings store with versioning and
migration. Load one no-op reference module end to end and list it in the Shell.

**Gate:** `dotnet build` succeeds for every project; `coord test` is green for the Core test projects on
a non-Windows machine *and* on Windows; the reference module appears in the Shell, and its settings
survive a restart. The build result is recorded in [NEXT.md](NEXT.md) with the date and the machine —
a claim that cannot be made from a container.

### P2 — Conduit and Atlas, minimum viable

Conduit: hotkey chord registration, central conflict arbitration, the schedule/interval wheel, and
dispatch off the hook thread. Atlas: the monitor and work-area snapshot, DPI and scaling, and the pure
layout math. Both Core-first, both with Shell adapters kept deliberately dull.

**Gate:** Core tests cover arbitration (including the two-modules-one-chord case) and the geometry
math, and pass on Linux; a manual-validation run on Windows records a real chord firing, a real
schedule firing, and a real multi-monitor topology read correctly — including one non-100% scaling
monitor. Host tests alone do not close this gate.

### P3 — Zones (M1)

The first real module: layout templates, per-monitor zone sets, drag-to-snap. The first real consumer
of both pillars, and the proof that the module contract is usable by someone who did not write it.

**Gate:** zone-rectangle math is host-tested against a table of work areas and templates including
mixed DPI; drag-to-snap validated manually on a multi-monitor desktop and recorded in
[`docs/runbooks/manual-validation.md`](runbooks/manual-validation.md); the module satisfies the
shelving contract ([MODULE_SPEC.md §7](MODULE_SPEC.md)) before the phase closes.

### P4 — Chrono (M2)

Timers, pomodoro, reminders. The first consumer of scheduled trigger intents and of the notification
path, and the second independent consumer of the module contract — which is what actually tests it.

**Gate:** Chrono owns **no timer of its own** — every wake comes from a declared Conduit intent, and
the boundary check confirms it; schedule arithmetic is host-tested including a DST transition and a
machine-sleep resume; notification behavior validated manually and recorded.

### P5 — The update / delivery channel

Turn the seam built in P1 into a working path: package, deliver, install over an existing install.

**Gate:** an update installs over a previous install on a real machine; settings written by the old
version load in the new one; a deliberate structural settings change exercises `Migrate()` end to end
with a test that **fails without the migration**; the procedure is recorded in
`docs/runbooks/release-and-update.md`.

Beyond P5 there is no committed plan, and that is intentional — see §9.

---

## 9. Scope discipline

The vision is allowed to be large. What gets built stays small and real.

**Build a module only for a real need.** Not to round out a category, not because PowerToys has one,
not to exercise an abstraction. The named-but-unbuilt ideas — a launcher, a clipboard history, a
pin-on-top, a command palette, a focus mode, a window-restore — live in [vision.md](vision.md) and
nowhere else. They are not scaffolded, not stubbed, and not given empty directories. An empty directory
is a claim, and this project does not make claims it has not earned.

**One module alone is a valid product.** Zones on its own, with no Chrono and no future utilities, is
a finished, useful thing. The platform exists to make the *second* module cheap, not to make the first
one conditional on the second.

**Platform versus module — the test.** Ask: *would a second, unrelated module need this?* If no, it
belongs in the module. Two modules needing the same thing is what earns a platform service; one module
wanting it is a module feature that happens to be written generically. The same test, applied to
cross-cutting subsystems, is what gates a third pillar — and no candidate passes it today; the one
parked possibility is named, deliberately without a name of its own, in [vision.md](vision.md).

**Prefer a clean seam with one proven consumer over a speculative abstraction.** The Shell's
graduation trigger (§5.1) is the worked example: the seam is named, the trigger is written down, and
the abstraction waits for its second consumer. Known limitations and couplings accumulate in
[TECH_DEBT.md](TECH_DEBT.md) rather than being papered over; drift between these documents and the code
is caught by the audit protocol in [AUDIT.md](AUDIT.md).

**Interests shift; accumulated capability should compound.** A module put down for a year and picked
back up should inherit every platform improvement made while it was dormant — for free, because it
speaks through the membrane and the platform handles the rest. That only works if it was shelved
properly. The shelving contract is [MODULE_SPEC.md §7](MODULE_SPEC.md), and it is the single most
important habit in this repository.

---

## 10. Where to go next

| You want | Read |
|---|---|
| What to do right now | [NEXT.md](NEXT.md) |
| To write or resume a module | [MODULE_SPEC.md](MODULE_SPEC.md), then [recipes/add-a-module.md](recipes/add-a-module.md) |
| The trigger/input contract | [CONDUIT.md](CONDUIT.md) |
| The desktop-truth contract | [ATLAS.md](ATLAS.md) |
| Why the rules are shaped this way | [OPERATING_MODEL.md](OPERATING_MODEL.md) |
| Where a document belongs | [DOC_SPEC.md](DOC_SPEC.md) |
| To set up a machine | [runbooks/dev-setup.md](runbooks/dev-setup.md) |
| To verify anything about the desktop | [runbooks/manual-validation.md](runbooks/manual-validation.md) |
| The whole doc index | [MAP.md](MAP.md) |
