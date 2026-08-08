---
title: Recipe — add a module
tier: platform
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/MODULE_SPEC.md
  - docs/COORDINATOR.md
  - docs/CONDUIT.md
  - docs/ATLAS.md
  - docs/OPERATING_MODEL.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
  - docs/runbooks/manual-validation.md
  - src/modules/README.md
---

# Recipe — add a module

> The step-by-step walkthrough for adding a module, with the reasoning at each step. The **contract**
> — what you must implement, the interfaces, the lifecycle table, the do's and don'ts — is
> [MODULE_SPEC.md](../MODULE_SPEC.md), and this recipe links to it rather than restating it. Read the
> spec once; come back here when you are actually building.
>
> **One sentence:** run one command, then work **outward from pure logic** — Core and its tests
> before any Windows code exists, capabilities and trigger intents declared with permanent ids, the
> desktop taken from Atlas as one snapshot, the Shell adapter last and dull, and a "Where to resume"
> section written before you stop.
>
> **⚠ No module has ever been created.** [MODULE_SPEC.md](../MODULE_SPEC.md) is a specification with
> zero implementations (**TD-5**), the scaffold has never produced a module that compiled, and no C#
> in this repository has been through a compiler (**TD-1**). This recipe describes the intended
> workflow. **The first person to walk it should expect the spec to fight back — and should revise
> both the spec and this recipe in the same session, against what actually happened.** That
> correction is the deliverable, not an interruption.

**The payoff you are buying.** Adding a module should be *one directory plus one registration*. No
edits to the host, no changes to another module, no new plumbing. If adding your module required
touching an existing one, the seam is wrong and that is a finding, not a workaround
([AUDIT.md Lens B](../AUDIT.md)).

---

## Step 0 — decide it should exist, then name it

**Two questions before any code.**

*Does it deserve to exist?* Build a module for a real want, never to round out a category, never
because a comparable toolbox has one, and never to exercise an abstraction. Ideas that are real but
not next live in [vision.md](../vision.md) and are deliberately **not** scaffolded — an empty
directory is a claim ([COORDINATOR §9](../COORDINATOR.md)).

*What is it called?* Module names are **plain and descriptive**, lowercase, and boring: `zones`,
`chrono`. Not codenames. A user reading a tray menu should know what it does without learning a
vocabulary; the reasoning is ADR 0009.

The name is not cosmetic. It becomes the **permanent module id**, and the id is referenced by settings
files and user bindings on machines you are not looking at. Renaming the *display* name later is free;
renaming the id is impossible ([MODULE_SPEC §2.4](../MODULE_SPEC.md)). Spend the extra minute now.

---

## Step 1 — scaffold

```sh
./coord new-module <name>
```

What it lays down:

```
src/modules/<name>/
├── README.md                          front door — frontmatter (tier: module, module: <name>),
│                                      what it does, capabilities, done-vs-TODO,
│                                      and a "Where to resume" section (step 9)
├── Coordinator.<Name>.Core/           net9.0 — ALL decision logic
│   ├── Coordinator.<Name>.Core.csproj
│   ├── <Name>Module.cs                implements IModule
│   ├── <Name>Capabilities.cs          CapabilityId constants + declarations
│   ├── <Name>Triggers.cs              TriggerIntent declarations
│   └── <Name>Settings.cs              versioned settings record + migrations
├── Coordinator.<Name>.Shell/          net9.0-windows10.0.19041.0 — thin adapter
│   └── Coordinator.<Name>.Shell.csproj    (delete this project if the module needs no
│                                           Windows surface of its own)
└── docs/
    ├── ARCHITECTURE.md                internal design — required, even if brief
    └── NEXT.md                        where to resume — required, filled from day one

tests/
└── Coordinator.<Name>.Core.Tests/     runs on any OS
```

**Why the scaffold rather than copying a sibling.** The shape has to be right from the *first* commit,
because the two things that are expensive to fix later are both structural: Core and Shell must be
separate **projects** (a single project with a Windows target defeats the boundary check silently),
and the docs must exist before there is anything to document, or they never get written at all.

The scaffold is a starting point, not a cage. Delete the Shell project if your module has no Windows
surface — plenty of useful behavior does not.

---

## Step 2 — write Core first, and its tests before any Windows code exists

**This ordering is the recipe's one hard rule.** Write the module's decision logic and its unit tests,
and run them green, *before* the Shell project contains anything at all.

The reason is not purity. It is that the moment a Windows project exists and can be launched, the
cheapest way to check anything becomes "run it and look" — and from then on, when something is wrong,
you cannot tell whether the geometry is wrong or the adapter is wrong. Proving the math first means
that when placement misbehaves, you already know the arithmetic is not the cause. That is the entire
argument for the [Core/Shell split](../COORDINATOR.md), applied to your afternoon.

What belongs in Core: every branch that is not a null check or a Win32 error check. Geometry,
schedules, state machines, the decision about *what should happen*, settings shapes, capability and
intent declarations.

Two habits that make Core stay testable:

- **Everything arrives through the context.** No statics, no service locator, no ambient globals. If
  it is not on `IModuleContext`, the module does not get it ([MODULE_SPEC §2.1](../MODULE_SPEC.md)).
- **Time comes from `IClock`.** Not decoration: anything reading the wall clock directly is untestable,
  and untestable scheduling logic will be wrong across a DST boundary or a machine sleep — the two
  cases you cannot reproduce on demand.

Test the domain logic against a **table** of cases rather than a handful of examples. Layout math wants
a table of work areas × templates × scale factors; schedule arithmetic wants a table that includes a
DST transition and a resume-from-sleep. This is the part of the module most likely to be wrong and
cheapest to pin.

---

## Step 3 — declare capabilities, with ids you can never change

A **capability** is anything a user could plausibly want to change or bind a key to. Declaring it is
how settings, the Shell form, and any future binding surface all find it — you write the declaration
once and get the rest.

```csharp
// ILLUSTRATIVE SKETCH — not compiled. These ids are invented for this walkthrough; the REAL Zones
// capability ids are in its ARCHITECTURE §8.1 and do not match these. Never copy an id from a
// recipe — ids are a permanent contract. See MODULE_SPEC §2.2.
public static class ZonesCapabilities
{
    public static readonly CapabilityId Apply      = new("zones.layout.apply");
    public static readonly CapabilityId ShowOverlay= new("zones.overlay.show");
    public static readonly CapabilityId GapPixels  = new("zones.layout.gap");
    public static readonly CapabilityId ActiveSet  = new("zones.layout.active");   // Reading
}
```

**Declare ids as constants in one file, and treat that file as a contract.** Convention:
`<moduleid>.<thing>[.<param>]`.

**The stability rule, stated once so it sticks:** *add capabilities freely; never break existing
ones.* A renamed id is a silently broken binding on somebody's machine. A **reused** id is worse — it
points an old binding at new behavior. If a capability dies, leave its id retired and unclaimed. The
same discipline governs the module id and every trigger-intent id: **ids are permanent, labels are
free** ([MODULE_SPEC §2.4](../MODULE_SPEC.md)).

Give each capability a `ValueSpec` with its real bounds and options. That single declaration drives
the settings form, the validation on load, and what a binding surface is allowed to send — so a
sloppy spec produces a sloppy UI *and* a validation hole, from one place.

Mark read-only state as a `Reading`. Readings are how a module exposes what it is currently doing
without inventing a side channel, and `ApplyAsync` must reject them.

---

## Step 4 — declare trigger intents through Conduit

**A module never names an input mechanism.** You do not call `RegisterHotKey`, do not install a hook,
do not own a timer. You declare what you want to be woken *for*, and Conduit decides how
([CONDUIT.md](../CONDUIT.md)).

```csharp
// ILLUSTRATIVE SKETCH — not compiled. The intent taxonomy is CONDUIT §3.
public static class ZonesTriggers
{
    public static readonly TriggerIntentId SnapChord = new("zones.snap.chord");
    public static readonly TriggerIntentId DragSnap  = new("zones.snap.drag");
}
```

**A declaration is a request, and the answer is a value.** Conduit may refuse — because another module
won the chord, because another application holds it, because the system reserves it, or because the
user disabled it. You learn the outcome through `context.Triggers`, and you must **remain useful with
a refused intent**: report reduced function, do not fault ([CONDUIT §4](../CONDUIT.md)).

Handling refusal is not a nicety. The failure it prevents — a feature that is installed, enabled,
documented, and simply does not happen — is the worst outcome a utility can produce, because the user
cannot tell it apart from their own misunderstanding. It is scenario
[S2](../runbooks/manual-validation.md) for exactly that reason.

**A grant is a lease, not a fact.** The user can rebind a chord while the app runs; the lease notifies
its holder. A module that was told "granted" once and never listened again will eventually be wrong.

And the constraint underneath all of it: **your handler never runs on the input hook.** Conduit already
moved off it. That does not license you to block — a slow handler makes your module sluggish — but it
does mean the desktop's critical path is not yours to stall ([CONDUIT §5](../CONDUIT.md)).

---

## Step 5 — take desktop state from Atlas, as one snapshot

**A module never enumerates the desktop.** No monitor enumeration, no window enumeration, no
dictionary of window handles you saw once. You ask [Atlas](../ATLAS.md) for a snapshot.

```csharp
// ILLUSTRATIVE SKETCH — not compiled. See ATLAS §4.
DesktopSnapshot snap = context.Atlas.Capture();   // one instant, everything consistent
Monitor        mon   = snap.MonitorOf(window);    // a lookup INSIDE the value
ZoneSet        set   = LayoutMath.Resolve(template, mon.WorkArea);   // pure Core math
```

**Take the snapshot once and compute against it.** Every field in it was true at the same instant, so
`MonitorOf` cannot disagree with the window list. Re-capturing mid-computation reintroduces exactly the
tearing the type exists to prevent — and during a drag, re-capturing on every mouse move is also the
performance mistake.

Three things to get right, each of which is a real bug someone has shipped:

- **Freshness is computed by you, at the point of use**, from the snapshot's monotonic stamp. Atlas
  never tells you how old a snapshot is, because an age computed by the producer is already wrong by
  the time you read it ([ATLAS §4](../ATLAS.md)).
- **The coordinate space is part of the type.** Never hold a bare rectangle. Physical pixels,
  effective pixels, and monitor-local pixels are three different things, and mixing them produces no
  error — just a window that is wrong by a scale factor, on one monitor
  ([ATLAS §5](../ATLAS.md)).
- **Placement returns an outcome, not `void`.** Handle `PlacedDifferently` and every `Refused` case:
  elevated windows, fullscreen, shell surfaces, a window that closed between snapshot and placement.
  A module that treats placement as "it worked" is making a claim stronger than its evidence
  ([ATLAS §7.3](../ATLAS.md)) — and it is scenario [S4](../runbooks/manual-validation.md).

---

## Step 6 — settings: versioned, additive, migrated

```csharp
// ILLUSTRATIVE SKETCH — not compiled. See MODULE_SPEC §5.
public sealed record ZonesSettings
{
    public int    SchemaVersion { get; init; } = 2;
    public int    GapPixels     { get; init; } = 8;      // every field has a default
    public string ActiveLayout  { get; init; } = "halves";

    public static ZonesSettings Migrate(ZonesSettings old) => /* structural changes only */;
}
```

**Additive is the default move.** A new field read with a safe default means the old settings file
still loads, in both directions, for free. Reach for that shape first, every time.

**A structural change needs an explicit migration step and a version bump — and a test that fails without
the migration.** Write the failing test first and watch it go red. A migration guard nobody has seen
fail is a comment, not a guard ([OPERATING_MODEL §7](../OPERATING_MODEL.md)).

**Settings-save is a second enable.** When the user changes something, do the expensive work *there* —
recompile the layout, reallocate the buffers, re-resolve the bindings — not on the next dispatch. That
is *resolve once, execute cheap* ([principle 7](../COORDINATOR.md#7-non-negotiable-principles)), and a
drag loop is not the place to discover you need to re-read a template.

**A reset is only ever explicit.** Nothing your module does may quietly discard a user's configuration.

---

## Step 7 — add the Shell adapter (and keep it dull)

Only now, with Core green, write the Windows side.

The adapter's job is exactly three moves: **collect facts, hand them to Core, carry out Core's
answer.** It decides nothing. If you are writing an `if` in an adapter that is not a null check or a
Win32 error check, that decision belongs in Core.

What legitimately lives here: P/Invoke, window handles, hook plumbing your pillar hands you, WinUI
pages, and the mapping between Core's own types and whatever the platform gives you.

What must never appear in **Core**: `[DllImport]`, `Windows.*` or `Microsoft.UI.*` namespaces, or a
project reference to a Shell project. The `boundary` check reads these as **text** and will fail the
gate — which is the point ([AUDIT §8](../AUDIT.md)). It is defeatable by reflection or a
fully-qualified name (**TD-3**), so treat a green boundary result as "the obvious leaks are absent,"
never as "the boundary is proven."

**The adapter is not unit-tested, on purpose.** That is the deal the split buys: the untestable part is
small enough to check by hand in one pass. Keeping it that way is your job — every decision you leave
in the adapter is a decision no test will ever see.

---

## Step 8 — the settings page

**You get one for free.** The Shell renders a settings page from your declared capabilities and their
`ValueSpec`s. A module with no custom UI at all is still fully configurable, and for most modules that
is the correct amount of UI.

If your behavior genuinely needs richer UI — a visual layout editor, a live preview — add it as
**progressive enhancement on top of the generic floor**. The rule that makes this safe:

> **No capability may be controllable only through a bespoke panel.**

Everything must remain reachable through the declarations alone, because that generic surface is what
a second consumer would one day render for free — and it is the concrete thing that would graduate the
Shell to a pillar ([COORDINATOR §5.1](../COORDINATOR.md)). A capability that exists only inside your
custom page has quietly foreclosed that.

---

## Step 9 — write the README, including "Where to resume"

Write it now, while the reasoning is in your head. Not at the end.

Your module's `README.md` needs frontmatter (`tier: module`, `module: <name>`), a statement of what
the module does, the capabilities it publishes, an honest **done vs. TODO**, and — the load-bearing
part — a **"Where to resume"** section naming a **specific next action**.

The difference between a resume anchor and a note:

| Not a resume anchor | A resume anchor |
|---|---|
| "Continue work on layouts." | "`ZoneLayout.Compute` handles one monitor; the multi-monitor path is stubbed at the work-area union — decide whether zones may span monitors before writing it." |
| "Finish the settings UI." | "The layout editor renders zones but cannot delete one; the delete path needs a decision about what happens to windows already snapped there." |

The second kind gets you productive in ten minutes after six months away. The first kind costs you an
evening re-deriving your own reasoning — every single time, because the cost recurs.

The module's own `NEXT.md` (inside its `docs/` folder) carries the same anchor at task granularity,
and its `ARCHITECTURE.md` carries the internal design even if it is three paragraphs — see the tree in
step 12 for where each lands. Non-obvious decisions become **ADRs in the
unified log** (`docs/decisions/`), never a per-module log — a numbered gap in one chronological record
is detectable, and split logs destroy that.

---

## Step 10 — add a validation scenario

**Every user-facing capability ships with a scenario** in
[runbooks/manual-validation.md](../runbooks/manual-validation.md): a written, numbered, reproducible
desktop setup that someone can recreate in a couple of minutes and step through.

Write it even if you cannot get to a Windows machine today — a scenario written while the design is
fresh is far better than one reconstructed six weeks later, and leaving it visibly unrun is the honest
state.

Then say plainly what is Core-verified and what is pending-manual. **A green `coord test` is never a
claim about window placement, hotkey capture, DPI behavior, or the UI**, and no amount of confidence in
the math changes that ([MODULE_SPEC §6.3](../MODULE_SPEC.md)).

---

## Step 11 — register, wire up, and run the gates

- **Register the module with the host** — compile-time registration of a type, not discovery by
  scanning ([principle 11](../COORDINATOR.md#7-non-negotiable-principles)).
- **Add its test project** to the solution so `coord test` actually runs it. A test project nobody
  runs is a check that cannot fail.
- **Add a row to the module table** in the root [README.md](../../README.md), at its *real* state. A
  built module sitting in a "planned" row is ERROR-grade drift, and a partially-updated table is the
  most invisible drift there is ([AUDIT.md Lens A](../AUDIT.md)).
- **Add the module to [NEXT.md](../NEXT.md)** so the resume anchor is reachable from the tactical page.

```sh
./coord test          # Core suites, including yours
./coord audit         # frontmatter, links, boundary, shelving — zero ERROR
./coord map --check   # the doc index must include your new docs
```

Then the relevant scenarios from step 10, on a real desktop, **recorded**.

---

## Step 12 — what it looks like when you are done

```
src/modules/<name>/
├── README.md                          done-vs-TODO · capabilities · Where to resume
├── Coordinator.<Name>.Core/           net9.0 — no Windows types anywhere
│   ├── Coordinator.<Name>.Core.csproj
│   ├── <Name>Module.cs                IModule: Identity, Capabilities, TriggerIntents,
│   │                                  Initialize/Enable/Handle/Apply/Disable
│   ├── <Name>Capabilities.cs          permanent ids + ValueSpecs
│   ├── <Name>Triggers.cs              intent declarations; refusal handled
│   ├── <Name>Settings.cs              versioned record, defaults, migrations
│   └── <domain>.cs                    the pure logic — the reason the module exists
├── Coordinator.<Name>.Shell/          net9.0-windows10.0.19041.0 — thin, dull
│   ├── Coordinator.<Name>.Shell.csproj
│   ├── <Name>ShellAdapter.cs          collect facts → call Core → carry out the answer
│   └── <Name>SettingsPage.xaml        OPTIONAL, on top of the generic floor
└── docs/
    ├── ARCHITECTURE.md                internal design
    └── NEXT.md                        the resume anchor at task granularity

tests/
└── Coordinator.<Name>.Core.Tests/     declarations · apply · settings · migration · domain logic

docs/decisions/                        an ADR per non-obvious call (unified log)
docs/runbooks/manual-validation.md     + your scenario
README.md                              + your row in the module table
```

Nothing outside that list changed. No host edit, no sibling-module edit, no new plumbing. **If your
module required either, stop and record it** — the seam is wrong, and it is a Lens B finding, not
something to work around.

---

## Step 13 — before you stop: the shelving contract

Modules are designed to be put down for months or years. This checklist is the difference between
resuming in an hour and losing an evening. The canonical definition is
[MODULE_SPEC §7](../MODULE_SPEC.md); this is the operational form.

```
[ ] README states what it does, what's DONE and what's TODO, and the capabilities it publishes
[ ] "Where to resume" names a SPECIFIC next action — the file, the method, the decision, the
    failing test. Re-read it as a stranger: would it get you moving in ten minutes?
[ ] docs/ARCHITECTURE.md exists (brief is fine) and docs/NEXT.md carries the same anchor
[ ] ADRs written for every non-obvious decision — in the unified log, so future-you does not
    re-litigate a settled call or quietly reverse it
[ ] coord test green for this module's Core project
      ⚠ Until a .NET SDK exists, this box CANNOT be ticked. Record it as
        "unverified: no toolchain" — never as satisfied by default (TD-1)
[ ] An honest status line on anything desktop-dependent: WHAT was manually validated, on WHAT
    machine, with how many monitors and what scaling, and WHEN. Undated validation is not validation
[ ] coord audit clean of ERROR; coord map --check current
[ ] docs/NEXT.md at the platform level reflects where this module actually stands
```

**A module that meets this is resumable in under an hour after any gap. One that does not is a
liability**, and the cost recurs every time you come back. This is the single highest-leverage habit
in the repository — treat it as part of the work, not as paperwork after it.

---

## Common mistakes

| Mistake | Why it hurts | Instead |
|---|---|---|
| Building the Shell adapter first "to see it work" | you lose the ability to tell a geometry bug from an adapter bug | step 2 — Core and its tests first |
| Grabbing a hotkey directly, "just this once" | two modules that each grabbed a chord cannot be reconciled after the fact | declare an intent (step 4) |
| Enumerating monitors or windows yourself | a second cache is a second truth; the two disagree exactly mid-drag | one Atlas snapshot (step 5) |
| Renaming a capability id to something nicer | a silently broken binding on somebody's machine | add a new id; retire the old one |
| Putting a decision in the adapter | no test will ever see it | move it to Core |
| A capability only reachable from your custom page | forecloses the generic surface and the Shell's graduation | declare it; enhance on top (step 8) |
| Writing "Where to resume" as you shelve it | you have already forgotten the useful part | write it in step 9 and keep it current |
| Marking desktop work done on a green test run | the claim is stronger than its evidence | step 10, and say what is pending |
| Reaching into another module | there is no supported way, and no test will catch it early | it is a platform feature with an ADR, or it is not happening |

---

## See also

- [MODULE_SPEC.md](../MODULE_SPEC.md) — **the contract**: interfaces, lifecycle, testing, the
  shelving contract, and the terse version of this checklist (§9).
- [CONDUIT.md](../CONDUIT.md) — the trigger-intent taxonomy, arbitration, and refusal semantics.
- [ATLAS.md](../ATLAS.md) — the snapshot contract, coordinate spaces, and the placement outcomes.
- [COORDINATOR.md](../COORDINATOR.md) — the platform architecture and the principle list.
- [runbooks/manual-validation.md](../runbooks/manual-validation.md) — scenarios, and how to record
  what you actually observed.
- [src/modules/README.md](../../src/modules/README.md) — where modules live.
