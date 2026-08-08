---
title: Shell — the WinUI host (Windows-only)
tier: platform
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/runbooks/manual-validation.md
  - docs/runbooks/release-and-update.md
  - docs/NEXT.md
---

# Shell — the tray host and settings surface

> **The part of Windows Coordinator a person actually sees.** One tray icon, one tray menu, one
> settings and dashboard window, one process that starts with the session and stays out of the way.
> It is the only Windows-only thing in this repository that is not an adapter for something else.
>
> **One sentence:** this directory will hold the WinUI 3 host that owns the process, renders every
> module's settings from that module's own declarations, and shows what the toolbox is currently
> doing — and **it does not exist yet**.

## Status: nothing here but this file

There is no project, no window, no tray icon, no line of code. Nothing has ever run on Windows: no
hotkey has been registered, no window placed, no tray icon shown, no settings page opened. The UI
stack is *decided* (WinUI 3 on the Windows App SDK, ADR 0002) and *unexercised* — chosen on
reputation for stock-Windows fidelity, with none of its known-fiddly areas measured. That gap is
tracked as **TD-10** in [docs/TECH_DEBT.md](../../docs/TECH_DEBT.md), and the areas it names —
tray-icon behaviour, packaged versus unpackaged deployment, the runtime bootstrapper dependency,
per-monitor DPI awareness in the settings window, and start-up cost for a process that sits resident
all day — are exactly where a resident tray utility lives or dies.

| | State |
|---|---|
| Stack decision (ADR 0002) | **done** — and unvalidated by any build (**TD-10**) |
| The host process and tray presence | **TODO** — not created |
| The settings and dashboard window | **TODO** — not created |
| Generic capability rendering | **TODO** — not created |
| Fault and diagnostics surface | **TODO** — not created |
| Manual-validation rows for any of it | **TODO** — there is nothing to validate yet (**TD-9**) |

## What the Shell will own

**The process.** Windows Coordinator is one tray-resident host, not a suite of applications. This
project is where `Main` lives, where the module host is started and supervised, and where the
process declares itself per-monitor-DPI-aware. That last one is a whole-process property that
affects every measurement anywhere in the application — get it wrong and the operating system hands
the process virtualised coordinates, at which point every number the desktop pillar reports is
wrong on any monitor that is not at 100%.

**One tray icon and one tray menu.** Modules contribute items; they do not each get an icon. A
toolbox that installs six tray icons has stopped being one thing.

**The settings surface, rendered from declarations.** A module publishes typed capabilities with
stable ids ([docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md)); the Shell turns those into a settings
page without knowing what the module does. **The generic form is the floor, not the ceiling** — a
module may add rich custom UI as progressive enhancement, but no capability may be reachable *only*
through a bespoke panel. That rule is what keeps a second surface possible later.

**The fault surface.** A module that fails to load is a first-class state that the user can see,
retry, and disable — not a crash, and never a vanished tray icon. "The tray icon disappeared" is
not an acceptable failure mode for something whose entire value proposition is being unobtrusively
present.

## Why it is Windows-only, and why that is contained

WinUI 3 requires a `net9.0-windows` target, so this project cannot be built or tested on a Linux
runner or in a container. That is not a compromise of the Core/Shell split
([docs/COORDINATOR.md §3](../../docs/COORDINATOR.md)) — it is the split working as designed. The
untestable region is *deliberately concentrated here*, and kept as thin as possible, so that
everything worth reasoning about lives somewhere it can be reasoned about.

The consequences are worth stating plainly, because they are permanent rather than temporary:

- **CI cannot see this project at all** (**TD-4**). A green continuous-integration run covers the
  Core projects — the half of the codebase that was already easiest to verify — and covers none of
  this one. The danger is not the gap; it is reading a green badge as coverage.
- **A green `coord test` says nothing about anything in this directory.** Not that the window opens,
  not that the tray icon appears, not that a settings page renders, not that a value survives a
  restart. Those claims come from a human running
  [docs/runbooks/manual-validation.md](../../docs/runbooks/manual-validation.md) on a real desktop
  and writing down what they observed, with a date and a machine.
- **Whatever decides something is in the wrong project.** If an `if` appears here that is not a null
  check or an error check, the decision belongs in a Core project. The Shell collects facts, hands
  them to Core, and carries out Core's answer.

## The graduation trigger — why the Shell is not a pillar

The Shell has every surface feature of a pillar — cross-cutting, touched by every module, the most
visible part of the product — and is nonetheless **platform core**, because it has exactly one
consumer: itself. The argument for that (what earns a subsystem pillar status, why
[Conduit](../../docs/CONDUIT.md) and [Atlas](../../docs/ATLAS.md) qualify, and why promoting this
one now would be the speculative abstraction the operating model exists to prevent) is
[docs/COORDINATOR.md §5.1](../../docs/COORDINATOR.md#51-why-the-shell-is-platform-core-and-not-a-pillar)
and is deliberately not restated here.

**The trigger, stated so it can actually fire:** *the Shell becomes a pillar when a second
independent surface needs to render the same module settings from the same declarations* — a
`coord` settings subcommand, a web view, a companion application. It is carried in the trip-wire
table in [docs/NEXT.md](../../docs/NEXT.md) so it can resurface on its own rather than depending on
someone remembering it.

**What that day costs this directory** is the part worth knowing while writing code here, and it is
the reason the generic-form rule above is a rule. On the day the trigger fires, the rendering
contract gets extracted and this directory splits into a contract project and an implementation
project. Every capability that is reachable *only* through a bespoke panel is a capability the
second surface cannot render — so it is a piece of that future split that has to be untangled by
hand, by someone who no longer remembers why the panel was bespoke.

## Where to resume

**Blocked on the toolchain, and then on a decision.** Nothing here can be written until a
`dotnet build` has succeeded once on a Windows machine with the .NET 9 SDK and the Windows App SDK
workload — the Active focus in [docs/NEXT.md](../../docs/NEXT.md).

When that unblocks, the first action is deliberately the smallest and ugliest thing that could
possibly work:

> Build a spike: a tray icon that appears, a menu with one item, and one empty settings window that
> opens when it is clicked. **Unpackaged first.** Then write down what deployment actually required
> — the bootstrapper, the workload, the manifest entries, the DPI declaration, whether unpackaged
> worked at all — in [docs/runbooks/dev-setup.md](../../docs/runbooks/dev-setup.md) and
> [docs/runbooks/release-and-update.md](../../docs/runbooks/release-and-update.md), as it happened
> rather than as it was designed.

Do that **before** any settings rendering, because it is the step that can invalidate ADR 0002. The
question it answers is not "does WinUI look right" — it is whether a resident, unpackaged tray
application is something this stack does comfortably. If the answer turns out to be no, that is an
ADR revisiting the stack, not a workaround buried in a host class.

Two things to record while you are there, because they are cheap in that session and expensive
later: the first **manual-validation** rows this project has ever had (**TD-9** — that runbook has
never been executed by anyone, and an unexecuted checklist produces an unreproducible pass), and the
first **performance baseline** (**TD-11** — idle working set, idle CPU over a few minutes, and cold
start, with the machine they came from). Without a baseline, "lightweight" is unfalsifiable and any
later regression is invisible.
