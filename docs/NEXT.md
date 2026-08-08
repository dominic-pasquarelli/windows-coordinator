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

## ▶▶ START HERE — 2026-08-08: bootstrapped, compiling, and nothing a user can see

This repository was created today in a single authoring pass, then corrected twice under review.
Read the next four paragraphs before you touch anything; they are the difference between resuming
correctly and resuming confidently.

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

**What exists, and what verifies it.** A C# skeleton — project files and contract interfaces for the
platform core and the two pillars — plus two Core test projects covering the layout arithmetic, the
snapshot immutability guarantee, the settings migration chain, and the capability invariants. **It
compiles and the tests pass:** GitHub Actions at `7aef6ff` (2026-08-08) built all five projects on
Ubuntu and the three production projects on Windows, 0 warnings under `TreatWarningsAsErrors`, and
ran 45 tests with 0 failures (Atlas 25, Platform 20). Nothing has been compiled *locally* — the
authoring container has no .NET SDK — so `coord build` and `coord run` remain unexercised
([OPERATING_MODEL §7](OPERATING_MODEL.md#7-the-evidence-standard--what-it-works-is-allowed-to-mean)).

**CI is the compiler, and that is new as of the review round on 2026-08-08.** The first
revision of [`ci.yml`](../.github/workflows/ci.yml) *skipped* both .NET jobs whenever no solution
file existed — so the repository could ship indefinitely having never run a compiler over its own
C#, while a .NET 9 SDK sat installed and idle in that very pipeline. **The absence of a solution
never prevented compiling anything: a `.csproj` builds on its own.** Both jobs now compile every
project on every push, and the Linux job runs the Core suites. So the honest statement is no longer
"nothing has been compiled" — it is **"read the latest CI run and report what it returned."** If you
are resuming and the run was green, say so with the date; if it was red, the errors are the work.

**What does not exist — and this is the part that matters now that it compiles.** There is **no
module code.** Zones (M1) is now **fully designed** —
[src/modules/zones/](../src/modules/zones/README.md) holds its architecture, and ADRs 0012–0024
settle its thirteen non-obvious decisions — but not one line of it is written, and its code projects are
deliberately not scaffolded. Chrono (M2) is still a roadmap entry only. There is **no Shell adapter**, so
not one line of Windows-facing code exists in this repository. There is **no solution file** (`.sln`
files carry GUIDs that cannot be verified in a container; generating it is step 2 below).
**Nothing has ever run on Windows.** No hotkey has been registered, no monitor enumerated, no window
moved, no tray icon shown. A green build and 45 green tests move none of that — the distance between
"compiles" and "does something" is the entire remaining project.

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
   [COORDINATOR.md §9](COORDINATOR.md#9-scope-discipline) is load-bearing: no stub pillar, no third
   pillar, no module code before its host exists. `src/modules/zones/` is **documentation only** and
   that is the point — a module here starts as a design, and `coord new-module zones` fills the code
   in around those docs when P1 and P2 close. The parked ideas live in [vision.md](vision.md) and
   nowhere else.

---

## Active focus — get a developer machine building, then start the platform host

*(A bounded detour drops its resume anchor as the first line of this section — `↩ RESUME AFTER
DETOUR: <where work stopped>` — and clears it on snap-back. Mode 3 of the snapshot protocol in
[../CLAUDE.md](../CLAUDE.md). If you see one, start there instead.)*

**First, read the latest CI run** — it compiles every portable project and runs the Core suites, so
it, not this page, is the current truth about whether the C# builds. Then do the rest **on a Windows
machine with the .NET 9 SDK installed**: the solution, the Windows-targeted half, and everything a
Linux runner structurally cannot reach.

**The evidence sweep is done.** The `NEVER COMPILED` banners that used to sit at the top of every
`.cs` file, both pillar READMEs and `Directory.Build.props` were replaced on 2026-08-08 with what was
actually observed at `7aef6ff` — the run, the date, and what it does *not* cover. If you add a file,
match that shape: state the observation and its boundary, never a bare "compiles".

Setup detail is in [runbooks/dev-setup.md](runbooks/dev-setup.md). The sequence:

1. **`coord doctor`** — first, before anything else. It must report the SDK it finds (or does not
   find), the workloads, and the Python version. If `doctor` is wrong about the machine, fix
   `doctor` before trusting anything downstream; a diagnostic that cannot be wrong is a diagnostic
   that carries no information (failure shape 1 in
   [OPERATING_MODEL §7](OPERATING_MODEL.md#7-the-evidence-standard--what-it-works-is-allowed-to-mean)).
2. **Generate the solution.** `dotnet new sln --name Coordinator` at the repository root, then add
   the five current projects — three production and two test projects — run verbatim:

   ```sh
   dotnet new sln --name Coordinator
   dotnet sln add src/platform/Coordinator.Platform.Core/Coordinator.Platform.Core.csproj
   dotnet sln add src/pillars/conduit/Coordinator.Conduit.Core/Coordinator.Conduit.Core.csproj
   dotnet sln add src/pillars/atlas/Coordinator.Atlas.Core/Coordinator.Atlas.Core.csproj
   dotnet sln add tests/Coordinator.Platform.Core.Tests/Coordinator.Platform.Core.Tests.csproj
   dotnet sln add tests/Coordinator.Atlas.Core.Tests/Coordinator.Atlas.Core.Tests.csproj
   ```

   **The test projects are in that list on purpose, and leaving them out breaks CI.** The
   `windows-build` job fails when a solution exists that omits a project under `src/`, and the
   `core-tests` job fails when portable code exists with no test project — so a solution containing
   only the three production projects would be a guaranteed red build. An earlier revision of this
   page prescribed exactly that; it was caught in review before anyone ran it.

   Every project name carries the **`.Core`** suffix because each one will eventually sit beside a
   `.Shell` adapter of the same stem — `Coordinator.Atlas.Core` / `Coordinator.Atlas.Shell` — which
   is the shape `coord new-module` already generates
   ([COORDINATOR §3](COORDINATOR.md#3-the-coreshell-split--the-central-architectural-commitment)).
   The C# **namespaces** do not carry the suffix: the assembly is `Coordinator.Atlas.Core`, the
   namespace is `Coordinator.Atlas`. **No `.Shell` project exists yet** — `src/shell/` holds a README
   and nothing else — so do not go looking for one to add. Commit the `.sln`. This closes **TD-2**.
3. **`coord build`** — the first compile of the **whole** solution, including anything
   Windows-targeted. CI already compiles the portable half on every push, so read the latest run
   first: if it is green, the errors you are hunting here are Windows-specific, which is a much
   smaller search than "everything".
4. **`coord test`** — the Core suites, locally. `coord test` deliberately runs each discovered test
   project individually rather than the solution, so that its meaning cannot widen as `.Shell`
   projects are added to the solution later; a green run here is a claim about portable logic and
   nothing else.
5. **Fix what the compiler surfaces**, smallest change first, without redesigning anything. If a
   fix requires a decision with trade-offs, write an ADR rather than deciding it silently in a
   commit message.
6. **Record the result** — here, replacing the START HERE block above, and as an entry in
   [audit-log.md](audit-log.md). Name the date, the machine, the SDK version, and the honest
   outcome. If it did not compile, say what failed; a recorded failure is worth more to the next
   session than a vague "in progress."
7. **Re-run `coord audit` and `coord map --check`** before you stop, and bump the `updated` flag on
   every doc you touched ([DOC_SPEC §6](DOC_SPEC.md#6-lifecycle--created--maintained--accuracy-audited--closed-out--frozen)).

> **Expect this to be less dramatic than it once would have been.** CI already compiles every
> project and runs the Core suites, so the code is not a hypothesis any more — what is unproven is
> the *developer path*: the solution, `coord build` and `coord test` against a real SDK, `coord run`,
> and anything Windows-targeted, none of which CI exercises through the tool. Budget a session
> rather than ten minutes, and resist expanding scope while you are in there.

**Do not** start Conduit, Atlas, or a module before this closes. A machine that cannot build or run
the thing cannot tell you whether your change worked, so every later error arrives mixed with a
toolchain question — failure shape 3, an error discovered after the expensive step.

---

## The near path

Ordered, with the evidence that closes each step. The canonical phase gates live in
[COORDINATOR.md §8](COORDINATOR.md#8-roadmap); this is the task decomposition beneath them.

### P1 — A developer machine can build and run it, and the platform core comes up

1. **The Active focus above** — solution generated, first *local* build and test, first `coord run`,
   result recorded. (The code already compiles in CI at `7aef6ff`; what this buys is a machine a
   human can iterate on.)
2. **Contract interfaces settle.** Whatever the compiler forces you to change in the module
   membrane, reflect it in [MODULE_SPEC.md](MODULE_SPEC.md) in the same session. A spec that
   describes an interface the compiler rejected is worse than no spec.
3. **The module host and registry.** Load, start, stop, unload; stable module identity
   (retrofit-expensive — see the table in
   [OPERATING_MODEL §3](OPERATING_MODEL.md#3-capture-is-free-building-costs)); a module that throws
   on load must be isolated so the host and the other modules survive (principle 12).
4. **The settings store.** Versioned, additive-by-default, with an explicit `ISettingsMigration` chain (ADR 0011). Write
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

The first real module and the first outside consumer of both pillars. **Fully designed** — read
[src/modules/zones/docs/ARCHITECTURE.md](../src/modules/zones/docs/ARCHITECTURE.md) before writing a
line, and note that Zones needs extensions from both pillars which are specified but unbuilt:
**Conduit** gains the pointer-gesture kind (ADR 0013), its request-vs-grant arbitration with
automatic restoration (ADR 0021), a **control-plane dispatch class** that never drops the final state
(ADR 0023) with `GrantVersion` as the single authoritative version stamped into the hook table and
every dispatch (ADR 0024), and the recognition-time invocation context (ADR 0017); **Atlas** gains explicit
raise/show/activate (ADR 0014) and the published `DesktopFacts` record that hook-thread capture reads
— with a heartbeat that **re-samples the foreground** and a **single publication sequencer** so a
higher sequence always means a later sample (ADR 0022).

**Pure logic first, placement second, Windows last** — the ordering is deliberate: the interesting
parts are pure and host-testable, so proving them before any window moves means that when placement
misbehaves you already know the model is not the cause.

1. **The occupancy model** — `ZoneAddress`, `StackMember` states, `GeometryStamp`, assign, cycle, and
   `Reconcile`, with the three invariants written as failing tests first. This is the whole module;
   everything below is plumbing around it. Start with the same template on two monitors — the case the
   first design could not represent (ADR 0015, ADR 0016). Then the two edge clusters ADR 0020 closes:
   **dormancy** (a monitor leaving the snapshot, and the `Positional`-match case that must *not* wake
   a stack) and the six **displacement** rows of ARCHITECTURE §6.1.
1b. **The layout designer** — `Grid` as a **constructor** (two integers → a fresh template; no
   occupancy, no remap, no placements), and `Split` / `Merge` as **edits** returning a `LayoutEdit`
   transaction (ADR 0019), with merge's tiles-its-bounding-box predicate tested exhaustively over a
   3×3 grid and the cell-id survival rules from ADR 0018. The tests that matter most are the ones
   asserting a split and a merge **re-place members whose cell id did not change** — a template-only
   assertion passes while the windows sit at the old size. Pure arithmetic, no UI, no desktop.
2. **Armed-region computation**, with the test that a zone leaves the armed set the moment its depth
   drops below two — the test that stops `Win`+wheel swallowing scroll over ordinary windows — and the
   grant lifecycle (ADR 0021, ADR 0023): a contested publication is accepted and reports what was
   granted, and every later change arrives as one `GrantChanged` carrying the **whole** current grant.
   Zones **adopts the set** rather than diffing, through **one** `ApplyGrant` that both the publication
   result and every `GrantChanged` go through (ADR 0024), and never republishes (§7.4). Four tests
   carry the weight: applying only the newest message reaches the same state as applying every
   message · a non-newer version is ignored · a tick recognized at grant v1 is dropped after a
   preempt-to-v2-and-restore-to-v3 · a held v1 publication result cannot overwrite an applied v2.
3. **Settings shape** and its migration path, before any UI.
4. **The Atlas raise path** (ADR 0014) and manual-validation `Z-4` — *do this early*. The foreground
   lock is the module's largest unknown and among the cheapest to resolve; the design already
   defaults to raise-without-activate, so a bad answer costs a setting rather than a redesign.
5. **The pointer-gesture kind in Conduit** (ADR 0013), with its recognizer host-tested against a fake
   input source, then `Z-3` and `Z-5` on a real desktop.
6. **Drag-to-snap and the overlay** — the module's only Windows code.
7. Shelve it properly before moving on:
   [MODULE_SPEC.md §7](MODULE_SPEC.md#7-the-shelving-contract).

**Closes when:** the occupancy model and reconciliation are host-tested; `Z-1`…`Z-6` are performed on
a real multi-monitor desktop and **recorded**; the module satisfies the shelving contract.

> **Deliberately not in M1:** the stack tab strip. Stacks are invisible in M1 except during a drag,
> which is a real cost accepted on purpose — the strip is a per-zone always-on-top overlay that must
> follow its zone, survive DPI changes, hide for fullscreen and never steal a click, and it is not
> worth building before daily use has shown whether stacking earns its place at all. **Recall hook:**
> if stacking is used daily and the invisibility is the top complaint, the strip becomes its own
> milestone. Parked in [vision.md](vision.md).

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
| **Settings schema needs a structural change** | any change that is not a new field read with a default. Additive is free; structural needs an `ISettingsMigration` step plus a test that fails without it. | an ADR + the migration test |
| **Performance becomes a topic** | the resident process is measurably annoying — memory, idle CPU, or a hook callback that stalls the desktop. Measure before optimizing; there is no baseline yet. | a runbook with real numbers |
| ⚠ **Plain-text ADR references become unverifiable** (**TD-12**) | **FIRED, 2026-08-08.** The row set its own threshold at "roughly twenty ADRs"; the log now holds **24**, and PR #2 added thirteen with several correcting each other — precisely the renumber-and-supersede traffic that plain-text `ADR NNNN` mentions cannot survive, because `doc-link` cannot see them. | Convert them to Markdown links, **or** add an `adr-ref` check resolving `ADR NNNN` by number (more robust to renaming). Do it in the next docs pass — see the item below |

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
