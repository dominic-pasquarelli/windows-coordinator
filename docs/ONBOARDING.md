---
title: Onboarding — cold start for a human or LLM
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - README.md
  - docs/COORDINATOR.md
  - docs/NEXT.md
  - docs/MODULE_SPEC.md
  - docs/runbooks/dev-setup.md
---

# ONBOARDING — start here (human or LLM)

> You're picking up Windows Coordinator cold. This gets you oriented and, as far as the toolchain
> allows, running.
>
> **One sentence:** Windows Coordinator is a tray-resident personal PowerToys — a host that loads
> independent **Modules** over two shared pillars (**Conduit** for input/triggers, **Atlas** for
> desktop truth), with every unit split into Windows-free **Core** logic and a thin Windows **Shell**
> adapter; today the documentation system and Python tooling are real and **no C# has been
> compiled**.

This page is written to be pasteable as LLM context.

---

## 1. What you're looking at

**Windows Coordinator** is a personal Windows productivity toolbox in the spirit of PowerToys —
enhancing Windows and adding the features it should already have, while keeping the native "stock"
feel. One tray-resident host process loads independent **Modules**; you enable the ones you want and
the app is useful with any single one of them.

The modular unit is a **Module**. Two **pillars** are the only routes a module has to input and to
the desktop: [Conduit](CONDUIT.md) (the input & trigger fabric) and [Atlas](ATLAS.md) (desktop
spatial truth). The **Shell** — the WinUI settings and dashboard surface — is platform core today,
and becomes a pillar only when a second independent consumer needs the same registry-driven surface.

**Before you read anything else, calibrate on what exists.** The documentation system, the
operating protocols, the audit tooling and the `coord` entry point are real and they run. The Python
tooling was executed and verified. **The C# compiles and the Core suites pass** — GitHub Actions at
`7aef6ff` (2026-08-08), Ubuntu and Windows, 0 warnings, 45 tests, 0 failed. **But no module exists,
there is no Shell adapter, there is no solution file, and nothing has ever run on Windows.**
Everything Windows-facing in these docs is design intent backed by documented API behavior — not
observation. The full statement is in
[CLAUDE.md](../CLAUDE.md) → "Current honesty boundary", and the first task waiting for a real
machine is at the top of [NEXT.md](NEXT.md).

## 2. Read in this order

1. [CLAUDE.md](../CLAUDE.md) — the mental model, the principles, the working agreements, and the
   snapshot protocol (10 min). This is the standing orientation; everything else assumes it.
2. [docs/NEXT.md](NEXT.md) — what to actually do right now. The **Active focus** line is the next
   task; a `RESUME AFTER DETOUR` line, if present, takes precedence.
3. [docs/COORDINATOR.md](COORDINATOR.md) — the platform architecture: host, core, pillars, modules,
   the Core/Shell split, the principle list (its canonical home), and the phase roadmap with gates.
4. [docs/MODULE_SPEC.md](MODULE_SPEC.md) — the module contract. Read this before creating or
   resuming a module.
5. [docs/CONDUIT.md](CONDUIT.md) and [docs/ATLAS.md](ATLAS.md) — the pillars. Read Conduit before
   touching anything input-shaped; read Atlas before writing a single line of geometry code.
6. [docs/OPERATING_MODEL.md](OPERATING_MODEL.md) — *why* the project is shaped this way. Read it
   when a rule feels arbitrary, or before proposing to change one.

Everything is reachable from the generated index, [docs/MAP.md](MAP.md).

## 3. The one-paragraph mental model

A single tray-resident **host** process starts, loads and supervises **Modules**. The **platform
core** gives every module identity, versioned settings, an update/delivery channel, logging, and a
settings surface in the WinUI **Shell** — without the module asking. Two **pillars** sit between
modules and Windows: a module **declares a trigger intent** ("this chord", "when a window moves",
"every 25 minutes") and **Conduit** owns whatever mechanism satisfies it and arbitrates conflicts
centrally; a module **reads one Atlas snapshot** of monitors, work areas, DPI and window geometry
rather than enumerating the desktop itself. Every module and pillar is two projects — a **Core**
(`net9.0`, zero Windows dependencies, all the decision logic, unit-testable on any OS) and a thin
**Shell adapter** (Windows-only P/Invoke and UI, validated by hand). Dependencies point one way:
modules depend on the platform and the pillars; the platform never depends on a module, and no module
depends on another. That boundary is checked mechanically from source text, so it holds even while
the C# is uncompiled.

## 4. Glossary — use these terms exactly

- **Windows Coordinator** — the platform and the shipped app.
- **Module** — the modular unit: one self-contained behavior (Zones, Chrono). The thing a user
  enables or disables. Names are plain and descriptive, never codenames.
- **Pillar** — a first-class cross-cutting subsystem every module builds on and no module may
  bypass. There are exactly two: Conduit and Atlas.
- **Conduit** — the input & trigger fabric. Owns hotkey registration, hooks, window-event
  subscriptions and the timer wheel; arbitrates conflicts.
- **Atlas** — desktop spatial truth. Owns monitors, work areas, DPI/scaling, virtual desktops,
  window handles and geometry, plus the pure layout math.
- **Shell** — the WinUI settings/dashboard host. Platform core today; a *candidate* pillar, gated on
  a second independent consumer.
- **Core / Shell split** — the pairing of a Windows-free `net9.0` logic project with a thin
  Windows adapter project. The reason tests can run anywhere.
- **Capability** — a named, typed thing a module exposes so settings and bindings can reference it.
  Ids are a permanent contract.
- **Trigger intent** — a declarative "wake me when X" that a module registers with Conduit. The
  module never names the mechanism.
- **The host** — the tray-resident process that loads and supervises modules.
- **`coord`** — the single developer entry point (`./coord` / `coord.cmd`). Not `wc`.

## 5. Where things live

```
CLAUDE.md            standing orientation (read first)
AGENTS.md            short pointer → CLAUDE.md
README.md            launchpad + Pitfalls
coord / coord.cmd    the developer entry point

docs/                architecture, pillars, specs, protocols, ADRs, runbooks
src/platform/        platform core — host, registry, identity, settings, update channel
src/pillars/conduit/ Conduit
src/pillars/atlas/   Atlas
src/modules/         one self-contained directory per module (empty by design today)
src/shell/           the WinUI settings + dashboard host (Windows-only)
tests/               where Core test projects will live — none exists yet
tools/coord/         the `coord` CLI (stdlib-only Python)
tools/doc-audit/     the code↔docs drift checker (`coord audit` wraps it)
```

Placement rules for new documentation — which tier, which directory, what frontmatter — are in
[docs/DOC_SPEC.md](DOC_SPEC.md). Don't guess; the audit checks it.

## 6. Prerequisites

> **Honesty note:** this list is derived from the documented requirements of the chosen toolchain.
> **It has not been executed end to end on a Windows machine.** Nobody has yet installed this stack
> and watched the solution build, because the bootstrap happened in a container with no .NET SDK.
> Treat the steps as a first draft to be corrected on first contact — and when you *do* run them,
> fix what's wrong here and in [docs/runbooks/dev-setup.md](runbooks/dev-setup.md), then bump both
> docs' `updated` flags. That correction is a real deliverable, not a chore.

To do everything:

| Need | For |
|---|---|
| **Windows 11** | running the app at all; the Shell adapters target modern Windows APIs |
| **.NET 9 SDK** | building and testing everything C# |
| **Windows App SDK / WinUI 3 workload** | building the Shell (`src/shell/`) and the Windows-targeted adapters |
| **Visual Studio 2022** (with the .NET desktop + Windows App SDK workloads) *or* the `dotnet` CLI alone | either works; the CLI is enough for build/test, VS is nicer for the UI |
| **Python 3.11+** | the `coord` CLI and the doc-audit tooling (stdlib only — nothing to `pip install`) |
| **git** | everything |

To work on **documentation, the audit tooling, or Core logic** you need far less: **Python 3.11+ and
git**, plus the .NET SDK only when you want to run `coord test`. Core projects are `net9.0` with zero
Windows dependencies by design, so they build and test on Linux and macOS too. That is the whole
point of the split — see [COORDINATOR §3](COORDINATOR.md).

## 7. First commands

```sh
git clone <this repo> && cd windows-coordinator

./coord doctor      # what's installed, what's missing — stated plainly, no guessing
./coord audit       # the documentation + boundary gate      (NO .NET REQUIRED)
./coord map --check # is the generated doc index in sync?     (NO .NET REQUIRED)
```

On Windows, substitute `coord.cmd` for `./coord`.

`coord doctor` is written to **detect and clearly report a missing .NET SDK** rather than failing
obscurely — it was written in exactly that situation. If it ever fails obscurely, fix that before
the thing you were actually doing; a diagnostic that misleads is worse than none
([OPERATING_MODEL §7](OPERATING_MODEL.md)).

Once a .NET 9 SDK is present:

```sh
./coord build       # dotnet build
./coord test        # dotnet test over the Core test projects
./coord run         # launch the Shell app (Windows only)
```

There is **no solution file yet**. Generating it with `dotnet new sln` on a Windows/.NET machine, then
building and recording the result, is the first task in [NEXT.md](NEXT.md). Solution files carry
GUIDs that cannot be generated meaningfully in a container that can't build, so the file was
deliberately not faked. Setup detail and troubleshooting live in
[docs/runbooks/dev-setup.md](runbooks/dev-setup.md).

## 8. Running the docs audit with no .NET installed

This is supported on purpose and it is the gate that works today.

```sh
./coord audit                      # full report; exits 1 on any ERROR
./coord audit --quiet              # only problems
./coord audit --format json        # machine-readable
./coord audit --since origin/main  # branch closeout: changed docs must bump `updated`
./coord audit --accuracy           # just the freshness sweep
./coord map                        # regenerate docs/MAP.md
```

`coord audit` and `coord map` are pure stdlib Python — they never invoke `dotnet`. The audit's
**boundary** check reads `using` directives, namespaces, `[DllImport]` attributes and
`ProjectReference` elements as *text*, so the modularity rules (platform never imports a module; a
module never imports another module; a Core project never touches Win32/WinUI) are enforced even
though nothing compiles. It is a real check, not a placeholder.

ERROR-level findings block a phase. The severity model, the six judgement lenses, and what to do
with what you find are in [docs/AUDIT.md](AUDIT.md); log every pass in
[docs/audit-log.md](audit-log.md).

## 9. You have 30 minutes — what do you read?

1. **[docs/NEXT.md](NEXT.md)** (3 min) — Active focus. If you read nothing else, read this; it is
   the resume anchor.
2. **[CLAUDE.md](../CLAUDE.md)** (10 min) — the mental model, the honesty boundary, the principles,
   the snapshot protocol.
3. **[README.md](../README.md) → Pitfalls** (5 min) — the traps, including the two that will
   otherwise cost you a day: the three DPI coordinate spaces, and what a blocking input hook does to
   the whole desktop.
4. **[docs/COORDINATOR.md](COORDINATOR.md) §2–§3** (7 min) — the layered model and the Core/Shell
   split. Skim the rest; come back for §7 (principles) and §8 (roadmap and gates) when you need them.
5. **The doc closest to your task** (5 min) — [MODULE_SPEC](MODULE_SPEC.md) if you're building a
   module, [CONDUIT](CONDUIT.md) if it's input-shaped, [ATLAS](ATLAS.md) if it's geometry-shaped.

Then run `./coord audit` and start. Don't read the architecture end to end before doing anything —
that's how a session evaporates.

## 10. Capturing stray ideas (the snapshot system)

Got a thought that isn't what you're working on but you don't want to lose it? Start a message with
**`SNAPSHOT:`** or **`IDEA:`** (or just say "capture this idea…"). It is saved verbatim to
[docs/INBOX.md](INBOX.md) *immediately*, before any discussion, then proposed into the right living
doc — architecture, roadmap, NEXT, an ADR, a Pitfalls entry — for you to confirm. If it's small and
safe enough to just *do* in the same reply, you'll be offered that instead: progress beats
paperwork.

The steering works both ways. When a tangent is pulling you off the Active focus you'll be offered
"park it, or think it through now"; and when a conversation *about* a parked idea has clearly become
the real work, you'll be offered the promotion to actual work. Full protocol:
[CLAUDE.md](../CLAUDE.md) → "Snapshot intake & steering".

## 11. Returning to a shelved module

This project is built for shifting interests: you might work on window management for a month, not
touch it for six, and come back. Every module is designed to survive that. When you return to one:

1. Read its **README** — every module directory under `src/modules/` has one, stating what it does,
   what's done, and what's still TODO.
2. Read its **"Where to resume"** section — the exact file, method, or half-finished thought where
   work stopped. If it isn't there, the shelving contract was skipped; fix that before anything else
   ([MODULE_SPEC §7](MODULE_SPEC.md#7-the-shelving-contract)).
3. Run `./coord test` — do its Core tests still pass after platform changes?
4. Run `./coord audit` — did the docs drift while it was dormant?
5. Walk the relevant entries in
   [docs/runbooks/manual-validation.md](runbooks/manual-validation.md) on a real desktop. Core tests
   don't know whether a window still lands where it should.
6. Skim [docs/NEXT.md](NEXT.md) and recent [ADRs](decisions/) — what changed in the platform while
   this module was asleep? The module inherits every platform improvement for free, and occasionally
   a contract change it needs to adapt to.

If something broke during the gap, that's usually a platform regression — fix it at the platform
level, not by patching around it in the module. The membrane is the contract; if the contract holds,
modules survive indefinitely.

## 12. Before you stop working

Update [docs/NEXT.md](NEXT.md) so the next person — or the next LLM, or you in eight months — can
resume in minutes. If you were working on a module, confirm it still meets every item of the
shelving contract in [MODULE_SPEC §7](MODULE_SPEC.md#7-the-shelving-contract) — that section defines
the list and wins over any restatement of it. Run `./coord audit` and clear any ERROR. Bump `updated` on every doc you edited, and `audited` on any
doc you re-read and confirmed still true.

That's the deal. A stale NEXT.md or a module with no resume point breaks the whole "put it down for
months, pick it up in an hour" promise. The last thing you do before stopping is make sure the next
session starts fast.

## See also

[CLAUDE.md](../CLAUDE.md) · [README.md](../README.md) · [docs/COORDINATOR.md](COORDINATOR.md) ·
[docs/MODULE_SPEC.md](MODULE_SPEC.md) · [docs/OPERATING_MODEL.md](OPERATING_MODEL.md) ·
[docs/AUDIT.md](AUDIT.md) · [docs/DOC_SPEC.md](DOC_SPEC.md) · [docs/MAP.md](MAP.md) ·
[docs/runbooks/dev-setup.md](runbooks/dev-setup.md)
