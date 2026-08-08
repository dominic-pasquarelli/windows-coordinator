# CLAUDE.md — Windows Coordinator

Standing context for any LLM (or human) working on this project. Read this, then
[docs/NEXT.md](docs/NEXT.md) for what to do right now, then
[docs/COORDINATOR.md](docs/COORDINATOR.md) for the platform architecture. Creating or resuming a
module? Read [docs/MODULE_SPEC.md](docs/MODULE_SPEC.md) — the complete contract. **If you do one
thing: keep `docs/NEXT.md` current** — it's how anyone resumes this cold months later.

---

## What this is

**Windows Coordinator** is a personal Windows productivity toolbox in the spirit of PowerToys: one
tray-resident host that loads independent **Modules** and keeps the native "stock Windows" feel. It
exists to enhance Windows and add the features it should already have — the owner's own version of
PowerToys, built to be lived in rather than demoed.

The modular unit is a **Module**. A module owns one domain behavior — window zones, timers,
whatever earns its place next — and takes platform services only through the platform's seams. It
never reaches around them. Module names are plain and descriptive (**Zones**, **Chrono**), not
codenames: for a toolbox whose whole job is legibility, a name that explains itself beats a name
with personality.

Two cross-cutting concerns are **pillars** — first-class subsystems every module builds on and no
module may bypass:

- **[Conduit](docs/CONDUIT.md)** is the input & trigger fabric. A module declares a typed **trigger
  intent** ("wake me on this chord", "wake me when a window moves", "wake me every 25 minutes") and
  Conduit owns every actual mechanism behind it — and arbitrates the conflicts centrally.
- **[Atlas](docs/ATLAS.md)** is desktop spatial truth. One canonical model of monitors, work areas,
  DPI and scaling, virtual desktops, and window geometry, plus the pure layout math over it.

The **Shell** — the WinUI settings and dashboard surface — is deliberately **platform core, not a
pillar**. It graduates to a pillar when a second independent consumer needs the same registry-driven
surface (a CLI or web view rendering the same module settings), and not before. That gate is stated
wherever the Shell is described on purpose: it is the discipline of *don't build the abstraction
until a second consumer proves it* made visible.

**Current honesty boundary — read this before you claim anything.** What exists today is the
documentation system, the operating protocols, the audit tooling, and the `coord` entry point. That
is real and it runs. Everything else is design.

- The Python tooling (`tools/coord/coord.py`, `tools/doc-audit/audit.py`) is **executed and
  verified**. `coord audit` and `coord map` work with no .NET installed at all.
- **The C# compiles, and the Core logic is tested.** GitHub Actions at commit `7aef6ff` (2026-08-08) built every project on **Ubuntu** and on **Windows** — 0 warnings, under `TreatWarningsAsErrors` — and the Core suites passed: **45 tests, 0 failed, 0 skipped** (Atlas 25, Platform 20). The authoring container has no
  .NET SDK, so CI was the first compiler this project ever had.
- **That is a claim about compilation and pure logic — nothing more.** No module exists (Zones and
  Chrono are roadmap entries, deliberately unscaffolded), there is no Shell adapter, and **nothing
  has ever run on Windows**: no hotkey registered, no window placed, no monitor enumerated, no tray
  icon shown, no UI opened.
- **There is still no solution file** (TD-2), and `coord build` / `coord run` have never executed
  their `dotnet` path — CI builds projects directly.

Never say "works" about any of it. "Compiles" and "the Core tests pass" are now true and checkable;
everything a user could see is still design intent, and only
[manual-validation.md](docs/runbooks/manual-validation.md) on a real desktop can change that.

**Operating philosophy:** interests shift; accumulated capability should compound. Build a module
only for a real want or to validate the contract. Prefer a clean seam with one proven consumer over
a speculative abstraction. A single module running alone in the tray is a complete product. The
reasoning beneath all of this is [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md).

## The mental model (memorize this)

### The system

```
   the host          the platform core        the pillars            the modules
   ────────          ─────────────────        ───────────            ───────────
   one tray-         module host, registry,   Conduit (input &       Zones, Chrono,
   resident          identity, settings,      trigger fabric)        and whatever
   process           update channel,          Atlas (desktop         earns its place
                     logging, the Shell UI    spatial truth)
```

**Host + core + two pillars + N modules.** The host is the process — it starts, loads, and
supervises. The platform core is what every module gets without asking. The pillars are the two
subsystems no module may bypass. The modules are the product.

Dependencies point **one way**. A module depends on the platform and on the pillars. The platform
never depends on a module, and no module depends on another module. That is enforced mechanically by
the `boundary` check in the audit tool, which reads `using` directives, namespaces, `[DllImport]`
attributes and `ProjectReference` elements as **text** — so it does real work even while the C#
stays uncompiled. Full model: [docs/COORDINATOR.md](docs/COORDINATOR.md).

### The Core/Shell split — the one thing you cannot get wrong

Every module and every pillar is **two projects**: a **Core** (`net9.0`, zero Windows dependencies)
holding the decision logic, and a **Shell adapter** (`net9.0-windows10.0.19041.0`) holding the
P/Invoke, window handles, hooks and WinUI, kept as thin as it can possibly be made. Core is where the
thinking lives — which is the whole reason `coord test` can mean something on a machine that has
never seen a taskbar.

The full comparison — targets, contents, size goal, and what verifies each half — is
[COORDINATOR §3](docs/COORDINATOR.md#3-the-coreshell-split--the-central-architectural-commitment),
which owns it. Don't let this paragraph grow back into a second copy of that table.

**And the consequence you must internalize:** a green `coord test` proves **Core logic and nothing
else**. It says nothing about window placement, hotkey capture, DPI behavior, or whether the UI even
opens. Those claims come only from
[docs/runbooks/manual-validation.md](docs/runbooks/manual-validation.md), performed on a real
Windows desktop, with the result written down.

### The two rules a module lives by

A module **never names an input mechanism** — it declares a trigger intent and Conduit decides
whether that becomes a registered chord, a low-level hook, a window-event subscription, or a timer.
A module **never enumerates the desktop** — monitors, windows and geometry come from one Atlas
snapshot, so two modules can never disagree about what the desktop looks like.

Both rules exist because the alternative is unfixable later. Once five modules own raw hooks,
central conflict arbitration cannot be retrofitted; once five modules cache window state, coherence
cannot be retrofitted either.

## Non-negotiable principles

1. **A module is a self-contained unit.** It owns one behavior; the app is useful with any single
   module and no others.
2. **Core/Shell split** — logic is Windows-free and host-testable; the Windows adapter is thin.
3. **A module never names an input mechanism.** Trigger intents go through
   [Conduit](docs/CONDUIT.md).
4. **A module never enumerates the desktop.** Monitors, windows, and geometry come from
   [Atlas](docs/ATLAS.md).
5. **Every capability is a named, typed binding target** — stable ids; settings and hotkey bindings
   reference them by name, so ids are a permanent contract.
6. **Settings are the source of truth and survive updates** — versioned, additive-by-default (a new
   field read with a default → old settings still load), an explicit migration step
   (`ISettingsMigration`, [ADR 0011](docs/decisions/0011-settings-migrate-the-persisted-document-not-the-deserialized-object.md))
   for structural changes. A reset is only ever explicit.
7. **Resolve once, execute cheap** — parse, compile, and allocate at load or settings-save, never in
   a hook callback or a drag loop. Input hooks are on the UI's critical path; blocking one stalls
   the whole desktop.
8. **Never block the hook or UI thread on I/O.** Disk, network, and process work go off-thread.
9. **Documentation is a load-bearing deliverable, not polish.** A phase isn't done until a cold
   reader could resume from the docs.
10. **Rigid structure, accommodating interests.** Strict enough that work years apart composes; open
    enough that a new interest slots in as a Module.
11. **Compile-time modularity** (registered types), not runtime scripting.
12. **The app degrades, never breaks.** A module that fails to load must not take down the host or
    any other module.

> **Note for the audit — this restatement is deliberate.** The **canonical home** of this list is
> [COORDINATOR §7](docs/COORDINATOR.md#7-non-negotiable-principles); this copy exists because
> CLAUDE.md is the first and often only file an LLM reads, and a principle you have to follow a link
> to read is a principle that gets broken. It is the **one accepted duplication of normative text**
> in the project — Lens B and the single-source rule in [DOC_SPEC §4](docs/DOC_SPEC.md) should not
> flag it. (The layered-model schematic is also repeated in README and COORDINATOR §2.1, but a
> diagram states no rule: it is a shared illustration, not a second source of truth. Anything else
> that starts appearing twice *is* drift — the Core/Shell comparison table used to live here and had
> already diverged from COORDINATOR §3 before it was cut.) If the two lists ever disagree,
> **COORDINATOR §7 wins**, and this copy is the bug. Changing a principle means editing it there,
> recording an ADR, and re-syncing here in the same commit.

## How to extend

### Adding a module

**Start with [docs/MODULE_SPEC.md](docs/MODULE_SPEC.md)** — the complete contract: what you must
implement, what the platform gives you free, the file structure, the lifecycle, the testing
requirements, the do's and don'ts, and the new-module checklist. The step-by-step is
[docs/recipes/add-a-module.md](docs/recipes/add-a-module.md); the scaffold is `coord new-module
<name>`, which lays down the directory, the README, the "Where to resume" section, and the
Core/Shell project pair so the shape is right from the first commit.

A module must speak the platform contract: declare typed capabilities, declare trigger intents,
take platform services through the interfaces, keep its decisions in Core.

**The shelving contract.** Modules are designed to be put down for months, so before shelving one it
must satisfy every item of the contract in
[MODULE_SPEC §7](docs/MODULE_SPEC.md#7-the-shelving-contract) — which defines the list and wins over
any restatement of it, here or anywhere else. A module meeting it resumes in under an hour after any
gap. One that doesn't is a liability: you'll spend the first session re-deriving your own reasoning.

### Adding a trigger kind

New ways to be woken up are a **Conduit** extension, never a module feature. Read
[docs/CONDUIT.md](docs/CONDUIT.md) → "Adding a trigger kind" for the contract: the intent type, the
arbitration rule (what counts as a conflict, and who wins), the registration path, and the dispatch
guarantee. If you find yourself adding a hook inside a module because "it's just this once", stop —
that is exactly the retrofit the pillar exists to prevent. Same shape for a new desktop fact: it
belongs in [Atlas](docs/ATLAS.md), on the snapshot, not in a module's private cache.

### Make it verifiable, not just buildable

Every user-facing capability ships with **both** halves of its evidence:

1. **A Core test** for the pure logic — the zone-rectangle math, the schedule arithmetic, the
   settings migration, the arbitration decision. It runs anywhere and it is the only thing a green
   `coord test` licenses you to claim.
2. **A manual-validation entry** — a named, repeatable check in
   [docs/runbooks/manual-validation.md](docs/runbooks/manual-validation.md) that someone at a real
   Windows desktop can perform in a minute and record. Placement, hotkey capture, DPI behavior,
   multi-monitor arrangement, tray behavior, and settings survival across a restart are *only ever*
   established this way.

This is a standing practice, not optional polish. When you cannot get to a Windows machine, say
plainly what is Core-verified and what is pending-manual, and leave the runbook entry written and
ready.

## Working agreements

- **Match the design.** If a change would violate a principle above, stop and flag it — don't
  quietly work around the architecture. Propose an ADR (`docs/decisions/`) for non-obvious calls.
- **Platform vs module.** Ask "would a *second*, unrelated module need this?" — if no, it belongs in
  the module, not in `src/platform/` and not in a pillar. Keep the boundary clean; the `boundary`
  check enforces the mechanical half, but the judgement half is yours.
- **Keep [docs/NEXT.md](docs/NEXT.md) pointing at the next step** — update it as you go, especially
  before stopping. Scope-creep and whimsy are welcome in their lane *if* they name their tie-back to
  the toolbox.
- **Each phase ends compiling, with the app still working.** Once there is something to compile,
  every phase ends with the solution building and the previously-validated behavior still validated.
  Do not leave a phase boundary with the tray host in a state nobody has launched.
- **Host-test the pure logic** — layout math, schedule arithmetic, arbitration, settings migration,
  capability binding — via `coord test` before assuming any of it is right.
- **Hold the evidence standard: a successful command must mean the outcome occurred.** The full
  statement lives in [OPERATING_MODEL §7](docs/OPERATING_MODEL.md), along with the three recurring
  failure shapes — **a check that cannot fail** · **a claim stronger than its evidence** · **an
  error found after the expensive step** — and the operational rule: **when you add a guard, prove
  it fails without the fix.** Write the failing case first, watch it fail, then fix it. A guard
  nobody has seen fail is decoration. And the concrete instance for this project, which you will be
  tempted to blur every single session: **a green test run is never a claim about window placement,
  hotkey capture, DPI behavior, or the UI.** Core-verified and Windows-validated are different
  words because they are different facts.
- **Never commit secrets.** No API keys, tokens, telemetry endpoints, update-feed credentials or
  machine-specific paths in tracked files. Anything environment-specific gets an `.example` file
  committed and the real one gitignored.
- **Honor the snapshot protocol** (below) — capture stray ideas safely and steer rabbit holes.
- **Audit for drift before a phase ends or a module is shelved.** Docs are easy to write once and
  hard to keep *true*; bespoke solutions quietly erode the build-once-use-anywhere goal. Run `coord
  audit` (mechanical drift: broken links, dead paths, missing frontmatter, ADR gaps, boundary
  violations) and walk the six lenses in [docs/AUDIT.md](docs/AUDIT.md) (alignment · modularity ·
  resumability · fidelity · recall/lifecycle · connectivity). **A phase isn't done with ERROR-level
  drift outstanding.** Log every audit in [docs/audit-log.md](docs/audit-log.md), and invoke the
  full pass with the `/audit` skill.
- **Documentation follows the spec ([docs/DOC_SPEC.md](docs/DOC_SPEC.md)).** Where a doc goes is
  already decided — it follows its code (platform / pillar / module / tool / meta). **One concern
  has one canonical home** — cross-link, never restate; duplication between COORDINATOR, CONDUIT and
  ATLAS is a single-source violation and an early sign the boundary is undecided. Every canonical
  doc carries frontmatter; **bump its `updated` flag whenever you touch it**, and **set `audited:
  <today>` whenever you re-read a doc against the code and confirm it is still TRUE** (an accuracy
  flag, distinct from `updated`). Closing out a branch includes `coord audit --since origin/main` —
  changed docs must be re-confirmed. Traverse everything from the generated
  [docs/MAP.md](docs/MAP.md) (`coord map` regenerates it). Putting the *whole project* on ice → the
  `/freeze` ceremony, which writes a record under [docs/freezes/](docs/freezes/README.md).
- **Help the accuracy machinery as you work.** This project will be built in bursts, so doc
  freshness is load-bearing. Two cheap habits keep it honest: (1) **update
  [docs/NEXT.md](docs/NEXT.md) whenever you touch related work**, and (2) **bump `audited` on any
  doc you verify in passing** — even if you changed nothing, confirming a doc is accurate *is* an
  audit. The accuracy check flags docs stale beyond 7 days or 15 commits; every confirmation you
  stamp is one less it has to chase.
- **Capture is free; recall AND drain are the discipline. Every buffer names both how items come
  back and how they leave.** This project captures relentlessly — [INBOX](docs/INBOX.md), ADRs, the
  snapshot protocol — and the weak sides of capture are always *recall* and *drain*. **Recall:**
  when you **defer** something (a `Proposed` ADR, a parked INBOX item, a "later" in a README), give
  it a **recall hook** — a [NEXT.md](docs/NEXT.md) item, a trip-wire, a "revisit-when" trigger — or
  it cannot resurface, and an idea that cannot resurface was never captured, only buried. **Drain:**
  when something **settles**, move it *out* of the active set — flip the ADR `Proposed → Accepted`
  and add a closure token once it is fully shipped (`Status: Accepted · Closed <date>` /
  `· Superseded by ADR NNNN`); mark an INBOX entry `triaged → <where>` and prune landed entries to
  git at a freeze (INBOX is a buffer, not an archive); drain settled blocks from
  [NEXT.md](docs/NEXT.md) to [HISTORY.md](docs/HISTORY.md). This is a **convention**, surfaced by
  the `adr-lifecycle` and `inbox-recall` checks and by Lens E of [docs/AUDIT.md](docs/AUDIT.md) —
  a nudge, never a wall. Capture must stay frictionless or it stops happening.
- **Leave every module resumable.** Before stopping work on any module — the one you're focused on
  *or* the one you detoured into — make sure it meets the shelving contract. This is the single most
  important habit for a project worked in bursts: it is what lets you put something down for a year
  and pick it up in an hour instead of a day.
- **Flush to docs before compaction (the context-loss guard).** A long session gets **summarized**
  when context fills. Compaction keeps the durable artifacts — NEXT.md, ADRs, the map, git history —
  but **loses conversational detail**: the reasoning you never wrote down, the thing you decided at
  message 40, the dead end you must not walk into again. So when context fills toward that threshold
  — treat **~90%** as the trigger and don't wait for the auto-summary — proactively run a **full doc
  sweep**: update [docs/NEXT.md](docs/NEXT.md) (the resume anchor), update every doc and ADR the
  session touched, write down any decision that isn't recorded anywhere (an ADR, or an
  [INBOX](docs/INBOX.md) capture if it isn't settled), run `coord audit` and `coord audit --since
  origin/main`, and **commit**. The goal: a post-compaction reader — LLM or human — resumes from
  *current docs*, not from a lossy summary. A `PreCompact` hook in `.claude/settings.json` echoes
  this as a backstop, but the discipline of flushing as pressure rises, rather than only at phase
  boundaries, is the real mechanism.

## Snapshot intake & steering protocol

The docs are **structured but living.** This protocol guarantees a stray idea is never lost *and*
always ends up in the right place. It has three modes. (*Why* it is shaped this way —
steer-but-never-force, resume anchors, capture-is-free — is in
[docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md).)

### Mode 1 — User-initiated capture

**Trigger:** the user starts a message with `SNAPSHOT:` or `IDEA:`, **or** otherwise clearly signals
capture intent ("capture this idea…", "don't lose this, but…", "parking-lot thought:"). Treat any of
these the same way.

**Do, in order:**

1. **Capture first, verbatim.** Append the full thought to [docs/INBOX.md](docs/INBOX.md) under
   `## Captured` (newest at top) as a `Status: captured` entry. This happens *immediately*, before
   any discussion, so nothing is lost even if triage is deferred forever.
2. **Propose triage, don't auto-apply.** Tell the user where it should land — possibly several of:
   - **[docs/COORDINATOR.md](docs/COORDINATOR.md)** — a new or changed principle, abstraction,
     section, or open question; or a roadmap phase (§8).
   - **[docs/CONDUIT.md](docs/CONDUIT.md) / [docs/ATLAS.md](docs/ATLAS.md)** — a pillar-level
     capability, constraint, or dragon.
   - **[docs/NEXT.md](docs/NEXT.md)** — an actionable next step, a *Rabbit holes & whimsy* entry
     (with its required tie-back to the toolbox), or the *Parking lot*.
   - **[docs/ONBOARDING.md](docs/ONBOARDING.md)** — a new term or a mental-model change.
   - **[README.md](README.md)** — a new on-ramp, or a **Pitfalls** entry if the idea is a gotcha or
     a "thing that bit me" worth warning future-you about (newest at top).
   - **[docs/vision.md](docs/vision.md)** — a module idea that is real but not next.
   - **[docs/TECH_DEBT.md](docs/TECH_DEBT.md)** — a known limitation or coupling to track.
   - **`docs/decisions/`** — a new ADR if it is a non-obvious decision with trade-offs.
3. **Assess for a complete-in-reply fast path.** After capturing, judge whether the idea can simply
   be *done* in this same reply — small, safe, self-contained. If so, **offer to just do it now**
   rather than only filing it. Progress beats paperwork. Do it in the same turn when the user says
   so, or when it is trivial and low-risk; otherwise offer.
4. **On user confirm,** make the edits, then mark the INBOX entry
   `Status: triaged → <where it landed>` (it may later be pruned — git keeps history).
5. **Then return** to whatever was happening before the snapshot.

Keep capture friction near zero: never refuse or interrogate a snapshot. Capture it, then (assess →)
propose or do. The user stays in control of the living docs — no silent restructuring — but an idea
that is trivially completable should turn into progress, not just a note.

### Mode 2 — LLM-initiated steering (you notice the drift)

When the user is going deep on a tangent that is really a **future** item — not what they should be
working on right now — **pause and offer the choice** rather than silently following or silently
refusing:

> "This is turning into its own thing. Want me to **(a) park it as a snapshot** and we resume
> {current task}, or **(b) think it through now** as a focused detour and then jump back?"

Use this when the tangent would change architecture, when it is clearly a later-phase concern, or
when it is pulling focus from the Active-focus item in NEXT.md. Don't nag — offer once, respect the
answer.

**The inverse nudge — promote snapshot → active.** If the conversation *about* a captured idea runs
long — you've gone several exchanges deep designing or debating it — then in practice it **has
become the real work**. Nudge the other way: stop treating it as a parked note and offer to make
actual progress on it now if feasible: *"we've been on this a while; want me to start it rather than
keep it a snapshot?"* Same one-offer, no-nag rule. This is the mirror of the park-it steer — there
we demote an over-deep tangent, here we promote a parked idea that has graduated.

### Mode 3 — Bounded think-through (the snap-back mechanism)

If the user chooses to dig in (or says "think it through now"):

1. **Drop a resume anchor.** *Before* diving in, write a one-line anchor into
   [docs/NEXT.md](docs/NEXT.md) **Active focus** — e.g. `↩ RESUME AFTER DETOUR: was writing the
   Atlas work-area snapshot, at the per-monitor scale-factor conversion`. This survives a long
   detour *and* a context summarization; it is how the snap-back actually works instead of relying
   on memory.
2. **Run the focused session** — explore, decide, capture as needed. It often ends in a Mode-1
   capture or an ADR.
3. **Snap back.** When the detour resolves, explicitly return to the anchored task, then **clear the
   anchor** from NEXT.md. Confirm to the user: "Back to {task}."

> The anchor is the contract. A think-through is only "bounded" if it reliably ends by returning to
> the parked work — otherwise the rabbit hole quietly becomes the new main thread.

## Build / test (quick ref — see the runbooks for detail)

**Use the `coord` tool.** It is the single developer entry point: `./coord <cmd>` on POSIX,
`coord.cmd <cmd>` on Windows, both thin launchers over `tools/coord/coord.py`. It is stdlib-only
Python 3.11+, so it needs no bootstrap of its own. *(It is `coord`, not `wc` — `wc` is the POSIX
word-count command and shadowing it on a dev machine is a bad afternoon.)*

```sh
coord audit                  # code↔docs drift + boundary check      — NO .NET REQUIRED
coord audit --since origin/main   # closeout: changed docs must bump `updated`
coord map                    # regenerate docs/MAP.md, the doc index — NO .NET REQUIRED
coord map --check            # fail if the map is stale
coord doctor                 # toolchain report: .NET SDK, workloads, Python — honest about gaps
coord test                   # dotnet test over the Core test projects
coord build                  # dotnet build
coord run                    # launch the Shell app (Windows only)
coord new-module <name>      # scaffold a module from the template
```

**`coord audit` and `coord map` are pure Python and require no .NET at all** — that is deliberate,
and it is why the documentation gate is runnable everywhere, including this repository's own
bootstrap container and any CI runner. `coord doctor` is written to **detect and clearly report a
missing .NET SDK** rather than failing obscurely; if it ever fails obscurely, that is a bug worth
fixing before the thing you were actually doing.

**The local gate.** Run the smallest relevant check while working; run the whole thing before
calling a phase done:

- `coord audit` — must be free of ERROR-level findings. This is the gate that works today.
- `coord map --check` — the doc index must not be stale.
- `coord audit --since origin/main` — before closing out a branch.
- `coord test` — once the solution exists, green Core tests on the projects you touched.
- `coord build` — once the solution exists, every project compiles.
- The relevant entries of [docs/runbooks/manual-validation.md](docs/runbooks/manual-validation.md),
  performed on a real Windows desktop, **for any claim about window placement, input, DPI, the tray,
  or the UI** — with the result and the date written down.

**Do not assert project health from memory — run the gate and report what it actually returned.**
`coord audit` and `coord map --check` must each exit 0; a green documentation gate is a fact about
the run you just performed, not a standing property of this repository, and it goes red the moment a
doc changes without the map being regenerated. The build half is answered the same way: **read the
latest CI run**, which compiles every project on Ubuntu and Windows and runs the Core suites. At
`7aef6ff` (2026-08-08) that was green — 0 warnings, 45 tests, 0 failed.

So an honest status has this shape: *"`coord audit` exits 0, CI at `<sha>` compiled every project
and passed N tests — and no desktop behavior exists or has been manually validated."* The last
clause is not a caveat you may drop when the first two are green; it is the part a user would
actually care about, and it is unchanged since day one.

## Status

**Read [docs/NEXT.md](docs/NEXT.md) for the executable plan and
[docs/HISTORY.md](docs/HISTORY.md) for completed arcs.** The snapshot as of 2026-08-08:

- **P0 (bootstrap) is the current phase.** The documentation system, the operating protocols, the
  audit tooling, and the `coord` entry point exist. That is the deliverable, and it is done in the
  sense that a cold reader can resume from it.
- **The Python tooling is executed and verified.** `coord audit`, `coord map`, and `coord doctor`
  run in an environment with no .NET SDK, which is exactly the environment they were written in.
- **No C# has been compiled — ever.** There is no `.sln`; solution files carry GUIDs that cannot be
  generated meaningfully here, so generating it with `dotnet new sln` on a Windows machine is
  literally the first task in NEXT.md. The platform contract interfaces are written and unverified.
- **No module exists.** Zones (M1, FancyZones-like window snapping) and Chrono (M2, timers and
  reminders) are planned, with a directory-level plan and no code. Further module ideas are parked
  in [docs/vision.md](docs/vision.md) and are explicitly not scaffolded.
- **Nothing has run on Windows.** No hotkey registration, no window placement, no tray presence, no
  UI. Every Windows-facing statement in the docs is *design intent* backed by documented API
  behavior, not observation.
- **The pillars are specified, not built.** [Conduit](docs/CONDUIT.md) and
  [Atlas](docs/ATLAS.md) each have a full contract, a threading model, and a named set of dragons;
  neither has an implementation.
- **Known boundaries are explicit** and tracked in [docs/TECH_DEBT.md](docs/TECH_DEBT.md).

The gate that ends P0 and the gate that ends P1 are both written down in
[COORDINATOR §8](docs/COORDINATOR.md). A phase is not done because the work feels finished; it is
done when its gate is satisfied and the evidence is recorded.

## Map of the docs

| File | Purpose |
|------|---------|
| [`README.md`](README.md) | Launchpad — 30-second model, on-ramps, module table, **Pitfalls** (living) |
| `CLAUDE.md` (this) | Standing orientation + working agreements + the snapshot protocol |
| [`AGENTS.md`](AGENTS.md) | Short pointer for any agent runtime → this file |
| [`docs/COORDINATOR.md`](docs/COORDINATOR.md) | **The platform architecture** — host, core, pillars, modules, Core/Shell split, principles, roadmap |
| [`docs/MODULE_SPEC.md`](docs/MODULE_SPEC.md) | **The module contract** — what a module implements, file structure, lifecycle, testing, shelving, checklist |
| [`docs/CONDUIT.md`](docs/CONDUIT.md) | **Pillar — the input & trigger fabric**: trigger intents, arbitration, the hook-thread constraint, adding a trigger kind |
| [`docs/ATLAS.md`](docs/ATLAS.md) | **Pillar — desktop spatial truth**: monitors, work areas, the three coordinate spaces, the snapshot contract, the layout math |
| [`docs/OPERATING_MODEL.md`](docs/OPERATING_MODEL.md) | **Why this project is shaped this way** — resume fidelity, capture-is-free/building-costs, friction-first, the evidence standard |
| [`docs/AUDIT.md`](docs/AUDIT.md) | **The audit protocol** — the six lenses, severity, the workflow (`/audit`, `/deep-audit`, `coord audit`) |
| [`docs/audit-log.md`](docs/audit-log.md) | Running record of audits — health over time (newest at top) |
| [`docs/DOC_SPEC.md`](docs/DOC_SPEC.md) | **The documentation spec** — tiers, placement, frontmatter, single-source rule, lifecycle, freeze |
| [`docs/MAP.md`](docs/MAP.md) | **Generated** doc index — the traversable front door (`coord map`; drift-checked) |
| [`docs/NEXT.md`](docs/NEXT.md) | The living "what to do now" tree — **active work only** |
| [`docs/HISTORY.md`](docs/HISTORY.md) | Completed-paths archive — shipped milestones + ADRs (newest at top) |
| [`docs/TECH_DEBT.md`](docs/TECH_DEBT.md) | Tech-debt register — known limitations and couplings, with ids |
| [`docs/INBOX.md`](docs/INBOX.md) | Raw idea capture buffer — the snapshot protocol's landing zone |
| [`docs/ONBOARDING.md`](docs/ONBOARDING.md) | Cold-start setup for a human or an LLM |
| [`docs/vision.md`](docs/vision.md) | Long-horizon module ideas — parked, not the contract |
| [`docs/decisions/`](docs/decisions/) | Short dated ADRs — the unified decision log |
| [`docs/recipes/add-a-module.md`](docs/recipes/add-a-module.md) | Step-by-step: create a module |
| [`docs/runbooks/dev-setup.md`](docs/runbooks/dev-setup.md) | Getting a machine able to build and run this |
| [`docs/runbooks/manual-validation.md`](docs/runbooks/manual-validation.md) | **The on-Windows checklist** — the only source of a placement/input/DPI/UI claim |
| [`docs/runbooks/release-and-update.md`](docs/runbooks/release-and-update.md) | Packaging and the update/delivery channel |
| [`docs/freezes/`](docs/freezes/README.md) | Project save points — dated "on ice" records (`/freeze`) |
| [`src/platform/README.md`](src/platform/README.md) | The platform core — module host, registry, settings, update channel |
| [`src/pillars/conduit/README.md`](src/pillars/conduit/README.md) | Conduit's code home |
| [`src/pillars/atlas/README.md`](src/pillars/atlas/README.md) | Atlas's code home |
| [`src/modules/README.md`](src/modules/README.md) | Where modules live — one self-contained directory each |
| [`src/shell/README.md`](src/shell/README.md) | The WinUI host — settings and dashboard, Windows-only |
| [`tests/README.md`](tests/README.md) | Where Core test projects will live (none yet) — and what a green run is allowed to mean |
| [`tools/coord/README.md`](tools/coord/README.md) | The `coord` developer entry point |
| [`tools/doc-audit/README.md`](tools/doc-audit/README.md) | The mechanical drift checker (`coord audit` wraps it) |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | CI pipeline definition |
