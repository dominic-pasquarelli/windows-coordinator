---
title: NEXT — Windows Coordinator tactical state
tier: platform
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/CONDUIT.md
  - docs/ATLAS.md
  - docs/OPERATING_MODEL.md
  - docs/AUDIT.md
  - docs/TECH_DEBT.md
  - docs/HISTORY.md
  - docs/INBOX.md
  - docs/vision.md
  - docs/audit-log.md
  - docs/runbooks/dev-setup.md
  - docs/runbooks/manual-validation.md
  - docs/runbooks/release-and-update.md
---

# NEXT — Windows Coordinator

> The tactical entry point: what is true right now, the one next executable action, and the hooks
> that bring deferred things back. **Active work only.**
>
> **One sentence:** if you have been away for six months, read the START HERE block, do the Active
> focus, and write down what happened — everything else on this page is context for that.
>
> Where things live, so this page stays short: completed narratives drain to
> [HISTORY.md](HISTORY.md) · durable contracts live in [COORDINATOR.md](COORDINATOR.md),
> [MODULE_SPEC.md](MODULE_SPEC.md), [CONDUIT.md](CONDUIT.md), [ATLAS.md](ATLAS.md) and the ADRs in
> [`docs/decisions/`](decisions/) · known limitations live in [TECH_DEBT.md](TECH_DEBT.md) · raw
> unsorted ideas live in [INBOX.md](INBOX.md) · long-horizon direction lives in
> [vision.md](vision.md).
>
> This page owns the **ordered executable work**. It does not own the phase gates — those are
> defined canonically in [COORDINATOR.md §8](COORDINATOR.md#8-roadmap) and are named here in short
> form so you can see what each step is buying.

---

## ▶▶ START HERE — 2026-08-08: the project is bootstrapped and nothing has been compiled

This repository was created today in a single authoring pass. Read the next three paragraphs before
you touch anything; they are the difference between resuming correctly and resuming confidently.

**What exists and is verified.** The documentation system and the operating protocols are in place:
governance ([CLAUDE.md](../CLAUDE.md)), the platform architecture, both pillar spines, the module and
documentation specs, the operating model, the audit protocol, the decision log, the runbooks and the
capture buffers. The **Python tooling is written and has actually been executed** — `coord`
(`tools/coord/coord.py`) and the doc-audit checker (`tools/doc-audit/audit.py`,
`tools/doc-audit/genmap.py`) are stdlib-only Python 3.11 and were deliberately built to work with no
.NET installed, which is the only reason any part of this repository can be checked today. When
`coord audit` or `coord map --check` reports a result, that result is real. Both were run at
bootstrap closeout: the first run surfaced one ERROR — a stale `MAP.md` — regenerating the map fixed
it, and the gate now stands at **0 ERROR**. The same closeout found and fixed four defects in the
guards themselves; they are written up in [audit-log.md](audit-log.md) and are the most useful thing
on that page.

**What exists and is not verified at all.** A C# skeleton — project files and contract interfaces
for the platform core and the two pillars — is **written and has never been compiled.** The
bootstrap ran in a Linux container with **no .NET SDK present**, so not one line of C# has been
through a compiler, a linter, or a test runner. The correct phrasing everywhere in this repository is
**"not compiled."** Never "builds," never "works," never "passes." That is
[OPERATING_MODEL §7](OPERATING_MODEL.md#7-the-evidence-standard--what-it-works-is-allowed-to-mean),
and it is the spine of the project, not a caveat.

**What does not exist.** There is **no module.** Zones and Chrono are roadmap entries with a
directory-level plan and nothing more — deliberately not scaffolded, because an empty directory is a
claim. There is **no solution file** (`.sln` files carry GUIDs that cannot be verified in a
container; generating it is step 1 below). **Nothing has ever run on Windows.** No hotkey has been
registered, no monitor enumerated, no window moved, no tray icon shown. The first honest signal this
project has ever received is the one you are about to generate.

### Three traps for anyone resuming from this page

1. **A green `coord test` will never mean "it works."** Because of the Core/Shell split
   ([COORDINATOR.md §3](COORDINATOR.md#3-the-coreshell-split--the-central-architectural-commitment)),
   host tests prove Core logic — geometry math, schedule arithmetic, settings migration, state
   machines — and prove *nothing* about window placement, hotkey capture, DPI behavior, tray
   lifecycle, or anything a user can see. Those are closed by a human executing
   [runbooks/manual-validation.md](runbooks/manual-validation.md) on a real desktop, and by nothing
   else. This is permanent, not a bootstrap condition.
2. **The boundary check reads text, not a compiled assembly graph.** It inspects `using`
   directives, `[DllImport]` attributes and `ProjectReference` elements in source. That is a real,
   working check — but it is defeated by reflection or a fully-qualified type name, so a green
   boundary result is evidence, not proof (**TD-3** in [TECH_DEBT.md](TECH_DEBT.md)).
3. **Do not scaffold anything to make the tree look finished.** The scope discipline in
   [COORDINATOR.md §9](COORDINATOR.md#9-scope-discipline) is load-bearing: no speculative module
   directories, no stub pillar, no third pillar. The parked ideas live in [vision.md](vision.md) and
   nowhere else.

---

## Active focus — restore the toolchain and compile the skeleton, then record what happened

*(A bounded detour drops its resume anchor as the first line of this section — `↩ RESUME AFTER
DETOUR: <where work stopped>` — and clears it on snap-back. Mode 3 of the snapshot protocol in
[../CLAUDE.md](../CLAUDE.md). If you see one, start there instead.)*

**One action, on a Windows machine with the .NET 9 SDK installed.** Everything else on this page is
blocked behind it, because until it happens the repository contains exactly one unverified claim
repeated in a dozen places.

Setup detail is in [runbooks/dev-setup.md](runbooks/dev-setup.md). The sequence:

1. **`coord doctor`** — first, before anything else. It must report the SDK it finds (or does not
   find), the workloads, and the Python version. If `doctor` is wrong about the machine, fix
   `doctor` before trusting anything downstream; a diagnostic that cannot be wrong is a diagnostic
   that carries no information (failure shape 1 in
   [OPERATING_MODEL §7](OPERATING_MODEL.md#7-the-evidence-standard--what-it-works-is-allowed-to-mean)).
2. **Generate the solution.** `dotnet new sln --name Coordinator` at the repository root, then add
   the three projects that exist today — run verbatim:

   ```sh
   dotnet new sln --name Coordinator
   dotnet sln add src/platform/Coordinator.Platform.Core/Coordinator.Platform.Core.csproj
   dotnet sln add src/pillars/conduit/Coordinator.Conduit.Core/Coordinator.Conduit.Core.csproj
   dotnet sln add src/pillars/atlas/Coordinator.Atlas.Core/Coordinator.Atlas.Core.csproj
   ```

   Every project name carries the **`.Core`** suffix because each one will eventually sit beside a
   `.Shell` adapter of the same stem — `Coordinator.Atlas.Core` / `Coordinator.Atlas.Shell` — which
   is the shape `coord new-module` already generates
   ([COORDINATOR §3](COORDINATOR.md#3-the-coreshell-split--the-central-architectural-commitment)).
   The C# **namespaces** do not carry the suffix: the assembly is `Coordinator.Atlas.Core`, the
   namespace is `Coordinator.Atlas`. **No `.Shell` project exists yet** — `src/shell/` holds a README
   and nothing else — so do not go looking for one to add. Commit the `.sln`. This closes **TD-2**.
3. **`coord build`** — the first compile in this project's history. Expect errors.
4. **`coord test`** — the Core test projects. Expect the test projects themselves to need work
   before they run at all.
5. **Fix what the compiler surfaces**, smallest change first, without redesigning anything. If a
   fix requires a decision with trade-offs, write an ADR rather than deciding it silently in a
   commit message.
6. **Record the result** — here, replacing the START HERE block above, and as an entry in
   [audit-log.md](audit-log.md). Name the date, the machine, the SDK version, and the honest
   outcome. If it did not compile, say what failed; a recorded failure is worth more to the next
   session than a vague "in progress."
7. **Re-run `coord audit` and `coord map --check`** before you stop, and bump the `updated` flag on
   every doc you touched ([DOC_SPEC §6](DOC_SPEC.md#6-lifecycle--created--maintained--accuracy-audited--closed-out--frozen)).

> **The skeleton is expected to need fixes. That is not failure — it is the first honest signal this
> project has ever had.** Code written without a compiler in the loop is a hypothesis. The value of
> this step is not that it will go smoothly; it is that afterwards, for the first time, a statement
> about this codebase can be *checked*. Budget a session for it, not ten minutes, and resist the
> urge to expand scope while you are in there.

**Do not** start Conduit, Atlas, or a module before this closes. Building on an uncompiled base means
every later error arrives mixed with this one, which is failure shape 3 — an error discovered after
the expensive step.

---

## The near path

Ordered, with the evidence that closes each step. The canonical phase gates live in
[COORDINATOR.md §8](COORDINATOR.md#8-roadmap); this is the task decomposition beneath them.

### P1 — The skeleton compiles and the platform core comes up

1. **The Active focus above** — solution generated, first compile, first honest result recorded.
2. **Contract interfaces settle.** Whatever the compiler forces you to change in the module
   membrane, reflect it in [MODULE_SPEC.md](MODULE_SPEC.md) in the same session. A spec that
   describes an interface the compiler rejected is worse than no spec.
3. **The module host and registry.** Load, start, stop, unload; stable module identity
   (retrofit-expensive — see the table in
   [OPERATING_MODEL §3](OPERATING_MODEL.md#3-capture-is-free-building-costs)); a module that throws
   on load must be isolated so the host and the other modules survive (principle 12).
4. **The settings store.** Versioned, additive-by-default, with an explicit `Migrate()` path. Write
   the migration test **before** the migration and watch it fail — a migration guard that has never
   been observed to fail is a comment.
5. **One no-op reference module, end to end.** Loaded by the host, listed in the Shell, its settings
   surviving a restart. It is a test fixture, not a product module, and it does not go in
   [vision.md](vision.md).

**Closes when:** every project builds; `coord test` is green for Core on Linux *and* on Windows; the
reference module appears in the Shell and its settings survive a restart; the build result is
recorded here with a date and a machine.

### P2 — Conduit and Atlas, minimum viable

Both Core-first, both with adapters kept deliberately dull. The contracts are already written
([CONDUIT.md](CONDUIT.md), [ATLAS.md](ATLAS.md)); this is the first implementation of them.

1. **Conduit minimum — one hotkey intent, end to end.** A module declares a chord intent, Conduit
   registers it, the chord fires, dispatch lands on the module **off the hook thread**. That single
   path is the whole proof.
2. **Conduit arbitration.** Two modules declaring the same chord must resolve centrally and
   deterministically, with the loser told it lost. This is the retrofit-expensive part — it cannot
   be added after modules own raw hooks — so it is built now even though there is one module.
3. **Atlas minimum — monitor enumeration and one coherent snapshot.** Monitors, work areas, DPI and
   scaling, read once into a single immutable snapshot that a module consumes whole. Not two
   independent reads that can disagree; coherence is the point of the pillar.
4. **The pure layout math, host-tested.** Zone rectangles from a template plus a work area, as a
   table-driven Core test including a non-100% scaling case.

**Closes when:** Core tests cover arbitration (including the two-modules-one-chord case) and the
geometry math and pass on Linux; **and** a human has run
[runbooks/manual-validation.md](runbooks/manual-validation.md) on Windows recording a real chord
firing, a real schedule firing, and a real multi-monitor topology read correctly with at least one
non-100% scaling monitor. Host tests alone do not close this. Anything touching windows, hotkeys or
DPI is closed by the runbook or it is not closed.

### P3 — Zones (M1)

The first real module and the first outside consumer of both pillars. **Layout math first, placement
second** — the ordering is deliberate: the math is pure and host-testable, so proving it before any
window moves means that when placement misbehaves you already know the geometry is not the cause.

1. Layout templates and per-monitor zone sets as pure Core types, host-tested against a table of
   work areas, templates and mixed DPI.
2. Settings shape for zone sets, with its migration path, before any UI.
3. Drag-to-snap through Conduit intents and Atlas snapshots — no raw hooks, no direct enumeration.
   The boundary check enforces this mechanically.
4. Shelve it properly before moving on: the shelving contract in
   [MODULE_SPEC.md §7](MODULE_SPEC.md#7-the-shelving-contract).

**Closes when:** the math is host-tested as above; drag-to-snap is validated by hand on a real
multi-monitor desktop and **recorded in the manual-validation runbook**; the module satisfies the
shelving contract.

### P4 — Chrono (M2)

Timers, pomodoro, reminders. Its real job is to be the **second independent consumer** of the module
contract — which is the only thing that actually tests a contract.

1. Schedule arithmetic as pure Core logic, host-tested including a DST transition and a
   machine-sleep-and-resume.
2. Every wake comes from a declared Conduit schedule intent. **Chrono owns no timer of its own**, and
   the boundary check confirms it.
3. Notifications through the platform path, validated by hand.

**Closes when:** the arithmetic tests pass including DST and sleep-resume; the boundary check
confirms no module-owned timer; notification behavior is manually validated and recorded.

### P5 — The update / delivery channel

The seam is built in P1 because it is retrofit-expensive; P5 turns it into a working pipe. Until this
closes, *"we can add that later"* is a promise the architecture cannot keep for any install that is
not on the machine you are sitting at.

1. Package and deliver a build.
2. Install over an existing install without losing settings.
3. Exercise a deliberate structural settings change end to end, with a test that **fails without the
   migration**.
4. Write the procedure down in [runbooks/release-and-update.md](runbooks/release-and-update.md) as it
   actually happened, not as it was designed.

**Closes when:** an update installs over a previous install on a real machine, old settings load in
the new version, and the migration test has been observed failing without the fix.

Beyond P5 there is no committed plan, on purpose ([COORDINATOR.md §9](COORDINATOR.md#9-scope-discipline)).

---

## Trip-wires and recall hooks

Deferred things and the condition that brings each one back. A deferral without a trip-wire is not a
decision, it is an oversight — this table is what keeps the difference honest
([OPERATING_MODEL §3](OPERATING_MODEL.md#3-capture-is-free-building-costs)).

| Deferred thing | Trip-wire — bring it back when… | Where it goes when it fires |
|---|---|---|
| **Shell graduates to a pillar** | a **second independent consumer** needs the module-settings registry — a `coord` subcommand or a web view rendering the identical schema. One consumer is a feature; two is a pillar. | an ADR, then a pillar spine doc alongside [CONDUIT.md](CONDUIT.md) / [ATLAS.md](ATLAS.md) |
| **Binding-conflict UI** | a **third** module wants a chord another module already holds. Two is arbitration logic (P2); three is a user problem that needs a surface for resolving it. | Conduit's Shell adapter + [CONDUIT.md](CONDUIT.md) |
| **The update channel becomes urgent** | the first module ships to a **second machine** — one you are not sitting at. Until then P5 is planned; after that it is the only way any fix reaches that install. | P5 above, promoted to Active focus |
| **A third pillar** | two unrelated modules independently need the same cross-cutting subsystem. The candidate is named in [vision.md](vision.md); it stays named and unbuilt until then. | an ADR first, code second |
| **CI covers more than Core** | a Shell-adapter regression escapes to a real desktop that CI could plausibly have caught (**TD-4**). Then price a Windows runner against the pain. | `.github/workflows/ci.yml` + TECH_DEBT |
| **The boundary check needs real teeth** | it reads **source text**, not a compiled assembly graph, so it is defeated by reflection, an inline fully-qualified type name, a source generator, or a package that transitively drags Windows types in — a green result is evidence, not proof. Bring it back when a Core project legitimately needs a Windows type, when someone works around it in one of those ways, **or the first moment a compiler exists** — from then on a Roslyn or assembly-reference check can enforce the rule against what actually builds, with the text check kept as the fast pre-build pass. See the boundary-check rows in [TECH_DEBT.md](TECH_DEBT.md) (**TD-3**). | `tools/doc-audit/audit.py` + an ADR if the rule changes; **prove the replacement fails without the fix** before trusting it |
| **MODULE_SPEC gets its first real validation** | Zones is implemented (**TD-5**). Until a module nobody wrote against the spec has been built from it, the spec is a hypothesis. | [MODULE_SPEC.md](MODULE_SPEC.md), revised against reality |
| **Settings schema needs a structural change** | any change that is not a new field read with a default. Additive is free; structural needs `Migrate()` plus a test that fails without it. | an ADR + the migration test |
| **Performance becomes a topic** | the resident process is measurably annoying — memory, idle CPU, or a hook callback that stalls the desktop. Measure before optimizing; there is no baseline yet. | a runbook with real numbers |

---

## Parking lot · rabbit holes & whimsy

This is the single lane the snapshot protocol routes to when an idea is *for this project, later* —
both the parking lot and the rabbit-holes-and-whimsy entries land here. Ideas are welcome **if they
name their tie-back** to the goal; anything without one is a raw capture and belongs in
[INBOX.md](INBOX.md) instead. A whole module idea belongs in [vision.md](vision.md). Nothing here is
committed — promoting an item means it earns an ADR or a real step above, in that order.

- **`coord` grows a `coord watch`** that re-runs the audit on doc save. *Tie-back:* doc freshness is
  load-bearing for resumability, and the cheapest way to keep it true is to make staleness visible
  immediately rather than at closeout.
- **A "what changed while I was away" summary** generated from git history plus the audit's accuracy
  check, printed by `coord doctor` when the last commit is older than a month. *Tie-back:* directly
  attacks context re-acquisition, the one cost the whole design exists to eliminate.
- **Zone layouts as shareable text files** rather than opaque settings blobs. *Tie-back:* a text
  format is diffable, reviewable and survives a settings migration, and it makes the layout math
  testable against real-world fixtures instead of hand-written ones.
- **A deliberately ugly diagnostic overlay** drawing Atlas's current snapshot on the actual desktop —
  monitor bounds, work areas, DPI factors, the zone grid. *Tie-back:* manual validation is the only
  evidence that closes the pillar gates, and right now that validation is a human squinting at
  windows. Making the snapshot visible turns a subjective check into a comparison.
- **A tray-icon easter egg.** *Tie-back:* none. Stays here as an honest example of an idea that has
  not earned a lane.
