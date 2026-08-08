---
title: Windows Coordinator — README / launchpad
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - docs/NEXT.md
  - docs/COORDINATOR.md
  - docs/MAP.md
  - docs/ONBOARDING.md
---

# Windows Coordinator

Windows Coordinator is a productivity enhancer and aid to Windows, in a similar vein to what
PowerToys is. It is designed to be **my personal version of PowerToys** — to enhance Windows and add
the features I wish it had, while keeping the "stock" feel that apps like PowerToys provide.

Concretely: one tray-resident host that loads independent **Modules**. A module owns exactly one
behavior — window zones, timers, whatever earns its place next — and the host gives it identity,
settings, an update path, a settings surface, and two shared subsystems it must not reinvent. You
run the modules you want and ignore the rest; the app is useful with any single one enabled and
nothing else.

The "stock feel" is a real constraint, not a slogan. It means: native window behavior, no bespoke
chrome fighting the shell, no module that hijacks input from the rest of the desktop, nothing that
makes Windows feel like it's running someone else's software.

> **This README is a cheat sheet, not a spec.** It gets you (or an LLM) moving in under a minute
> after months away. Depth lives elsewhere — links below.

---

## Pick it up in 60 seconds

1. **Where am I?** → open [docs/NEXT.md](docs/NEXT.md). The **Active focus** line is literally the
   next thing to do. (If there's a `RESUME AFTER DETOUR` line, start there.)
2. **What is this again?** → the 30-second model below.
3. **Watch out** → skim [Pitfalls](#pitfalls--things-that-bit-me) before re-entering.
4. **Got a stray idea?** → type `SNAPSHOT: <thought>` and it's captured verbatim and filed safely.

Don't read the whole architecture to start. Read NEXT.md and go.

---

## On-ramps — pick whatever matches your mood

| I want to… | Go here |
|---|---|
| …just continue the work | [docs/NEXT.md](docs/NEXT.md) → Active focus |
| …**add a module** | [docs/MODULE_SPEC.md](docs/MODULE_SPEC.md) (the contract) → [docs/recipes/add-a-module.md](docs/recipes/add-a-module.md) (the steps) → `coord new-module <name>` |
| …**understand the architecture** | [docs/COORDINATOR.md](docs/COORDINATOR.md) — host, core, pillars, modules, the Core/Shell split |
| …understand **input & triggers** | [docs/CONDUIT.md](docs/CONDUIT.md) — the pillar that owns every way a module gets woken up |
| …understand **the desktop model** | [docs/ATLAS.md](docs/ATLAS.md) — monitors, work areas, DPI, window geometry, layout math |
| …**resume cold** after months away | [docs/ONBOARDING.md](docs/ONBOARDING.md) → then [docs/NEXT.md](docs/NEXT.md) |
| …**run the docs audit** | `./coord audit` (needs **no .NET**) → [docs/AUDIT.md](docs/AUDIT.md) |
| …get a machine set up to build this | [docs/runbooks/dev-setup.md](docs/runbooks/dev-setup.md) |
| …validate a change **on real Windows** | [docs/runbooks/manual-validation.md](docs/runbooks/manual-validation.md) — the only source of a placement/input/DPI/UI claim |
| …package or ship an update | [docs/runbooks/release-and-update.md](docs/runbooks/release-and-update.md) |
| …know why a choice was made | [docs/decisions/](docs/decisions/) (ADRs) |
| …know **why the project is shaped this way** | [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) |
| …capture an idea without derailing | `SNAPSHOT: …` → [docs/INBOX.md](docs/INBOX.md) |
| …**find any doc** (the front door) | [docs/MAP.md](docs/MAP.md) — generated index of everything |
| …know where a new doc should live | [docs/DOC_SPEC.md](docs/DOC_SPEC.md) |
| …see what's knowingly imperfect | [docs/TECH_DEBT.md](docs/TECH_DEBT.md) |
| …see parked module ideas | [docs/vision.md](docs/vision.md) |
| …put the whole project on ice | `/freeze` → [docs/freezes/](docs/freezes/README.md) |
| …read the standing LLM orientation | [CLAUDE.md](CLAUDE.md) |

---

## The 30-second model

```
   the host          the platform core        the pillars            the modules
   ────────          ─────────────────        ───────────            ───────────
   one tray-         module host, registry,   Conduit (input &       Zones, Chrono,
   resident          identity, settings,      trigger fabric)        and whatever
   process           update channel,          Atlas (desktop         earns its place
                     logging, the Shell UI    spatial truth)
```

**Host + core + two pillars + N modules.** The host starts, loads, and supervises. The platform core
is what every module gets without asking — identity, versioned settings, the update channel,
logging, and the WinUI settings/dashboard Shell. The **pillars** are the two subsystems no module is
allowed to go around:

- **[Conduit](docs/CONDUIT.md)** — the input & trigger fabric. A module *declares* a trigger intent
  ("this chord", "when a window moves", "every 25 minutes"); Conduit owns the actual hotkey
  registrations, hooks and timers, and arbitrates when two modules want the same thing. A module
  never names an input mechanism.
- **[Atlas](docs/ATLAS.md)** — desktop spatial truth. One canonical snapshot of monitors, work
  areas, DPI/scaling, virtual desktops and window geometry, plus the pure layout math over it. A
  module never enumerates the desktop itself.

Both rules exist because the alternative can't be fixed later: once several modules own raw hooks,
you can't retrofit central arbitration, and once several modules cache window state, you can't
retrofit coherence.

**The Core/Shell split.** Every module and pillar is two projects: a **Core** (`net9.0`, zero Windows
dependencies — all the decision logic, geometry math, scheduling and settings shapes; unit-testable
on any OS) and a **Shell adapter** (`net9.0-windows10.0.19041.0`, as thin as possible — P/Invoke,
window handles, WinUI; validated by hand). This is why the tests can mean something on a machine
that has never seen a taskbar — and why a green test run says **nothing** about window placement.

One rule to remember: **resolve once, execute cheap** — parse, compile and allocate at load or
settings-save, never inside a hook callback or a drag loop.

Full model: [docs/COORDINATOR.md](docs/COORDINATOR.md).

### Modules

| Module | What it will do | Status |
|---|---|---|
| **Zones** (M1) | FancyZones-like window management: layout templates, per-monitor zone sets, drag-to-snap. The first real consumer of both pillars; its zone-rectangle math is pure, so it is host-testable. | 📋 **Planned — not implemented, not scaffolded** |
| **Chrono** (M2) | Timers, pomodoro, reminders. The first consumer of scheduled triggers and notifications. | 📋 **Planned — not implemented, not scaffolded** |
| Launcher, Clipboard, PinTop, Palette, Focus, Restore | Ideas only — parked deliberately, with no code and no directory. | 💭 [docs/vision.md](docs/vision.md) |

**Discipline:** no module without a real reason — built because it's wanted, or to prove the
contract composes. Two planned modules is not a shortage; it's the point. Clean seams beat
abstractions with no consumer.

---

## Current state — read this before believing anything

- **The documentation system, the operating protocols, the audit tooling and the `coord` entry point
  exist and run.** That is the bootstrap deliverable.
- **The Python tooling is executed and verified.** `coord audit`, `coord map` and `coord doctor` were
  written and run in an environment with **no .NET SDK at all**.
- **The C# compiles and the Core suites pass.** GitHub Actions at commit `7aef6ff` (2026-08-08) built every project on **Ubuntu** and on **Windows** — 0 warnings, under `TreatWarningsAsErrors` — and the Core suites passed: **45 tests, 0 failed, 0 skipped** (Atlas 25, Platform 20). There is still no solution file
  (TD-2) — CI builds each `.csproj` directly, because a solution is a tooling convenience rather
  than a compiler prerequisite.
- **Nothing has ever run on Windows.** No hotkey registered, no window placed, no monitor
  enumerated, no tray icon shown, no UI opened — there is no Shell adapter to do any of it. Every
  Windows-facing statement in these docs is design intent backed by documented API behavior, not
  observation.

The honest one-line status is: *the documentation gate is green, the C# compiles, the Core tests
pass — and no desktop behavior exists or has been validated.* **Confirm it rather than repeating
it:** run `./coord audit` and `./coord map --check`, and read the latest CI run. Each is a fact
about that run, not a standing property of the repo.

---

## Repo layout

```
CLAUDE.md            standing orientation for any LLM (or human) working here
AGENTS.md            short pointer → CLAUDE.md
coord / coord.cmd    the single developer entry point (POSIX / Windows launchers)

docs/                all documentation — architecture, pillars, specs, protocols, ADRs
  decisions/         short dated ADRs (the unified decision log)
  recipes/           step-by-step how-tos (add a module)
  runbooks/          dev-setup · manual-validation · release-and-update
  freezes/           dated "on ice" save points

src/
  platform/          the platform core — host, registry, identity, settings, update channel
  pillars/conduit/   Conduit — input & trigger fabric
  pillars/atlas/     Atlas — desktop spatial truth
  modules/           one self-contained directory per module (empty by design today)
  shell/             the WinUI settings + dashboard host (Windows-only)

tests/               where Core test projects will live — none exists yet
tools/
  coord/             the `coord` CLI (stdlib-only Python)
  doc-audit/         the code↔docs drift checker (`coord audit` wraps it)
```

---

## Quick start

```sh
./coord audit          # code↔docs drift + boundary check      — NO .NET REQUIRED
./coord map            # regenerate docs/MAP.md                — NO .NET REQUIRED
./coord doctor         # what's installed, what's missing, stated plainly
./coord test           # dotnet test over the Core test projects
./coord build          # dotnet build
./coord run            # launch the Shell app (Windows only)
./coord new-module zones   # scaffold a module from the template
```

On Windows, use `coord.cmd` instead of `./coord`; both are thin launchers over
`tools/coord/coord.py` and need nothing but Python 3.11+.

**`coord audit` and `coord map` deliberately require no .NET.** The documentation gate is runnable
everywhere — including on a machine with no SDK, which is where this project was bootstrapped.
Setup detail: [docs/runbooks/dev-setup.md](docs/runbooks/dev-setup.md).

---

## Pitfalls — things that bit me

> A **living list** — add to it whenever something trips you up (`SNAPSHOT:` a gotcha, or note it at
> a phase's end). Re-entering the project? Skim this first so you don't relearn the hard way.
> Newest at top. *(Seeded at bootstrap, 2026-08-08.)*

- **The bootstrap pass wrote "the documentation gate is green" while the gate was red — and an
  adversarial reviewer, not the author, caught it.** Three separate docs carried that sentence at a
  moment when `coord audit` was exiting 1 on a `map-sync` ERROR and `coord map --check` was reporting
  `docs/MAP.md` out of date. It had been true earlier in the session, and it was written from memory
  instead of re-derived from a run — *a claim stronger than its evidence*
  ([OPERATING_MODEL §7](docs/OPERATING_MODEL.md)), committed in the very file that names that failure
  shape. The durable lesson is not "run the audit more often." It is that **the author of a claim is
  the worst available judge of it**: the person who just did the work is the one person who cannot
  see the gap between what they did and what they wrote down. So state gate status as a command a
  reader can run and a result they can see — never as a remembered property — and treat an outside
  check on your own output as load-bearing rather than as ceremony.

- **A green compile is easy to over-read, and now there is one to over-read.** CI compiles every
  project and runs the Core suites, so "the C# builds" and "the tests pass" are finally true — and
  the very next sentence anyone reaches for is "so the platform works," which is false and will stay
  false for a long time. There is no Shell adapter, no module, no tray icon and no window placement:
  **nothing a user could see has been written, let alone validated.** The distance between "compiles"
  and "works" is the entire remaining project.

- **The first version of this repository documented its unverified state very carefully instead of
  verifying it.** CI installed a .NET 9 SDK and then skipped the build because no solution file
  existed — for the whole of PR #1, until a reviewer pointed out that a `.csproj` compiles perfectly
  well on its own. The lesson worth keeping: a precise description of a limitation can feel like
  rigor while being the thing that prevents you noticing the limitation was optional.

- **`coord` is not `wc`.** The obvious abbreviation for "Windows Coordinator" collides with the
  POSIX word-count command, and shadowing `wc` on a dev machine breaks scripts in ways that are
  maddening to diagnose (pipelines silently producing the wrong thing, not errors). The CLI is
  `coord` — `./coord` on POSIX, `coord.cmd` on Windows. If you see `wc` anywhere in this repo
  meaning this tool, it's a bug.

- **DPI has three coordinate spaces, and mixing them is *the* classic window-placement bug.**
  Physical (device) pixels on the virtual screen, effective pixels/DIPs (`physical / scaleFactor`),
  and monitor-local pixels are three different things, and converting between them wrong produces no
  error — just a window that's off by a scale factor or an offset. Three specific traps:
  **secondary monitors have negative coordinates** (the virtual-screen origin is the *primary*
  monitor's top-left, so a display arranged to its left starts at negative X — code that clamps to
  non-negative is broken on the first right-to-left setup); **scale factor is per-monitor, not
  per-machine** (a 150% laptop panel beside a 100% external display is the normal case); and **the
  process must declare per-monitor-DPI-aware v2** or Windows hands it virtualized coordinates and
  every measurement in the system is wrong. On top of that, the reported window rectangle includes
  an invisible resize border, so "flush to the monitor edge" using it overhangs by a few pixels —
  the visible bounds come from a separate attribute. Read [docs/ATLAS.md](docs/ATLAS.md) §5 *before*
  writing any geometry code, and keep the space in the type rather than in your head.

- **A blocking low-level input hook stalls the entire desktop, not just this app.** While a
  low-level hook callback runs, the keystroke or mouse event it is inspecting has **not yet been
  delivered to the application the user is typing into** — so a slow handler doesn't make Windows
  Coordinator sluggish, it makes the whole machine sluggish. Worse, Windows applies a timeout to
  low-level hooks and **silently removes** one that exceeds it: the punishment for being slow is
  that input quietly stops working, with no exception and no log entry. The callback may do exactly
  one thing — classify against a table compiled before it ever ran, enqueue a small value, return.
  No allocation, no locks, no disk, no logging, no settings reads, no UI calls. Full contract and
  the reasoning: [docs/CONDUIT.md](docs/CONDUIT.md) §5.

**Known traps baked into the design (read before coding):**

- **Green Core tests ≠ works on Windows.** `coord test` exercises Windows-free logic by
  construction. It cannot see window placement, hotkey registration, DPI behavior, tray presence, or
  the UI. Any such claim comes from
  [docs/runbooks/manual-validation.md](docs/runbooks/manual-validation.md), performed on a real
  desktop, recorded with a date.
- **Never own a hook inside a module.** Input mechanisms belong to [Conduit](docs/CONDUIT.md), and
  "just this once" is precisely the retrofit the pillar exists to prevent.
- **Never cache desktop state inside a module.** Two caches will disagree, and the bug will look
  like a placement bug. Take one [Atlas](docs/ATLAS.md) snapshot and pass it down.
- **Capability ids are a permanent contract.** Settings and hotkey bindings reference them by name;
  renaming or reusing an id silently breaks a user's saved configuration.
- **Settings changes are additive by default.** A new field must be readable with a default so old
  settings still load. Structural changes need an explicit migration step and a version bump. A reset
  is only ever explicit.

---

## Everything, in one place

[docs/MAP.md](docs/MAP.md) · [docs/NEXT.md](docs/NEXT.md) · [docs/COORDINATOR.md](docs/COORDINATOR.md) ·
[docs/MODULE_SPEC.md](docs/MODULE_SPEC.md) · [docs/CONDUIT.md](docs/CONDUIT.md) ·
[docs/ATLAS.md](docs/ATLAS.md) · [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) ·
[docs/AUDIT.md](docs/AUDIT.md) · [docs/DOC_SPEC.md](docs/DOC_SPEC.md) ·
[docs/TECH_DEBT.md](docs/TECH_DEBT.md) · [docs/HISTORY.md](docs/HISTORY.md) ·
[docs/decisions/](docs/decisions/) · [docs/runbooks/](docs/runbooks/manual-validation.md) ·
[tools/coord/](tools/coord/README.md) · [tools/doc-audit/](tools/doc-audit/README.md) ·
[CLAUDE.md](CLAUDE.md)
