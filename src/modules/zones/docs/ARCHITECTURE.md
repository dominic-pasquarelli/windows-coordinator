---
title: Zones — internal design
tier: module
module: zones
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - src/modules/zones/README.md
  - docs/MODULE_SPEC.md
  - docs/ATLAS.md
  - docs/CONDUIT.md
  - docs/decisions/0012-zones-stacking-model.md
  - docs/decisions/0013-the-pointer-gesture-trigger-kind.md
  - docs/decisions/0014-atlas-explicit-raise-and-activate.md
  - docs/decisions/0015-zone-addressing-and-durable-monitor-identity.md
  - docs/decisions/0016-zone-occupancy-member-states.md
  - docs/decisions/0017-invocation-context-and-one-drag-lifecycle.md
  - docs/decisions/0018-layout-editing-grid-split-merge.md
  - docs/decisions/0019-layout-edits-are-a-transaction.md
  - docs/decisions/0020-dormant-stacks-and-the-displacement-rules.md
  - docs/decisions/0021-requested-versus-granted-regions.md
  - docs/decisions/0023-the-control-plane-carries-state-not-deltas.md
  - docs/runbooks/manual-validation.md
---

# Zones — internal design

> **Window layouts with stacks.** A monitor is divided into zones by a layout template; a window
> dragged into a zone snaps to it; a zone can hold **more than one** window, and the mouse wheel with
> a modifier held cycles which one is in front.
>
> **One sentence:** everything here is a decision about *which window belongs where*, expressed as
> pure functions over an [Atlas](../../../../docs/ATLAS.md) snapshot — the desktop is read, never
> queried, and every actual Windows call belongs to a pillar.
>
> **Status: designed, not built.** No code exists in this module. The contract this design is
> written against does compile (CI `7aef6ff`), and this document is what the first line of Zones
> code should be written from.

---

## 1. What Zones is, and what it deliberately is not

Zones owns **one behaviour: which window belongs in which region of which monitor.** That is the
whole domain. It reads the desktop from Atlas, it declares what it wants to be woken for through
Conduit, and it decides.

**It is not a window manager.** It does not tile automatically, does not manage focus policy, does
not intercept window creation, and has no opinion about any window it has not been explicitly told
to place. A window the user has never dragged into a zone is invisible to Zones.

**The distinctive part is stacking.** PowerToys' FancyZones treats a zone as holding one window;
dropping a second displaces the first. Zones treats a zone as a **container with depth**: several
windows can occupy the same zone, sharing its rectangle, and the wheel cycles which is in front.
That single change is what makes a small monitor usable — a zone becomes a slot you keep a *set* of
related windows in, rather than a slot you keep swapping.

---

## 2. The occupancy model — the heart of the module

Everything else in Zones is plumbing around this type.

```csharp
// SKETCH — illustrative, not compiled.

// A zone is addressed by three things, never by a cell id alone (ADR 0015). Cell ids are unique
// within a template; templates are reusable across monitors, and a monitor can switch layouts.
readonly record struct ZoneAddress(MonitorKey Monitor, string LayoutId, string CellId);

enum MemberState { Placed, Minimized, Oversized, AwaitingReplacement }

// Geometry is stamped by a pair, never by topology alone (ADR 0019). A monitor change bumps the
// first component; a layout edit bumps the second. Either differing means "the geometry this was
// placed against no longer exists", which is the only question the reconciler needs to ask.
readonly record struct GeometryStamp(int TopologyGeneration, int LayoutRevision);

sealed record StackMember(
    WindowRef Window,
    MemberState State,
    Rect PlacedBounds,        // what we asked for
    Rect ObservedBounds,      // what we actually got (may differ — PlacedDifferently)
    GeometryStamp PlacedUnder);

sealed record ZoneOccupancy(IReadOnlyDictionary<ZoneAddress, IReadOnlyList<StackMember>> Stacks);
```

Three invariants, and all three are worth testing before anything else exists:

1. **A window appears in at most one zone**, across every monitor and every layout. Assigning it
   somewhere removes it from wherever it was; there is no such thing as a window in two places,
   because there is no such thing on the desktop.
2. **Stored order is the *cycle ring*, not a claim about what is visible.** It says what order
   cycling walks. Which member is actually frontmost is **read from the Atlas snapshot**, whose
   window list is ordered front-to-back. So a taskbar click that raises a buried member needs no
   reconciliation at all — it changed which member is frontmost, and the next cycle continues from
   there. ([ADR 0016](../../../../docs/decisions/0016-zone-occupancy-member-states.md))
3. **Occupancy is *intent*, not observation.** It records what the user asked for. The desktop is
   free to disagree, and reconciling that disagreement (§5) is a first-class operation rather than an
   afterthought.

Point 3 is the one that decides whether this module feels solid or haunted. The tempting design is
to treat occupancy as a *cache of what the desktop looks like*, which turns every disagreement into
a bug with no correct answer. Treating it as intent means every disagreement has an obvious
resolution: the desktop wins about what exists, the user's intent wins about where things go.

**Why a member carries state.** A bare `WindowRef` cannot express *minimised but still a member*,
*placed but clamped to a size we did not ask for*, or *placed under a geometry that no longer
exists* — and each of those is a real transition with a different correct answer. The first draft of
this design used a bare list and had five transitions with no representable resolution; they are §5's
table now.

**And why the stamp is a pair.** Split and merge deliberately *preserve* a cell id (§7.1) while
changing the rectangle that id refers to, and they change no monitor. Stamped with the topology
generation alone, a member of a just-split cell has an address that still resolves under a generation
that still matches — so reconciliation concludes everything is fine while the window sits at the old,
now-wrong size. `LayoutRevision` is what makes that transition detectable
([ADR 0019](../../../../docs/decisions/0019-layout-edits-are-a-transaction.md)); it is the same class
of fix as the member states themselves.

### 2.1 Why stacking is z-order, and not minimising

A stacked zone places every one of its windows at **the same rectangle**. Only the front one is
visible; the others are behind it, unmodified. Cycling raises the next one.

The rejected alternative — minimise the ones behind, restore the one in front — is worse in every
dimension that matters. It animates (so cycling becomes slow and visually noisy), it changes a
window state the user did not ask to change, it disturbs Alt-Tab and taskbar ordering, applications
behave unpredictably when minimised out from under them, and restoring is a second chance to fail.
Z-order costs one call and touches nothing else. Recorded as
[ADR 0012](../../../../docs/decisions/0012-zones-stacking-model.md).

**The visible consequence, stated because it will be noticed:** windows behind the front one are
still *there*. They appear in Alt-Tab and on the taskbar, which is correct — they are open windows —
and clicking one in the taskbar raises it, which is a perfectly good second way to cycle a stack.

---

## 3. Cycling, and the gesture problem

**Bare wheel-over-zone cannot work.** The zone is full of an application that wants wheel events. A
module that swallowed them would break scrolling inside every stacked window; one that did not
swallow them could not cycle. The gesture has to be distinguishable from ordinary scrolling before
it is anything else.

**The decision: `Win` + wheel, anywhere over the zone.** `Ctrl`+wheel is zoom in nearly everything,
`Shift`+wheel is horizontal scroll in a great deal, and `Alt`+wheel is claimed by enough
applications to be a poor default. `Win`+wheel is close to unclaimed. The modifier is a setting, so
a collision on one machine is a preference change rather than a redesign.

### 3.1 The hook-thread rule this forces

Deciding whether to swallow a wheel event happens **on the low-level input hook thread**, inside a
budget measured in microseconds, on every wheel event the machine processes
([CONDUIT §5.1](../../../../docs/CONDUIT.md)). Zones cannot be consulted there — a module reached
from a hook callback is a desktop-wide stall waiting for a slow module.

So the decision must be answerable **without asking Zones anything**:

> Zones publishes an **armed region set** — the rectangles of zones that currently hold a stack of
> two or more windows — and republishes it whenever occupancy or layout changes. Conduit's hook
> tests the cursor against that set and nothing else. Match plus modifier held → swallow the event
> and queue a dispatch. Anything else → pass through, untouched, immediately.

**The dispatch names the zone; it does not describe the pointer.** What arrives is the **zone token**
that matched and the **region-set version** it matched under. Zones checks the version is current and
drops the event if it is not — otherwise a layout change between the wheel tick and the dispatch
cycles a different zone than the one under the user's cursor. The cursor position is on the
invocation context and is for positioning and diagnostics only; **re-deriving the zone by hit-testing
it would reintroduce exactly the staleness the token removes**
([CONDUIT §3.6](../../../../docs/CONDUIT.md#36-pointer-gesture)).

**And a region can be granted only in part, or taken later** — a higher-priority module may request
an overlapping rectangle. Contention is arbitrated rather than refused, and a region taken comes back
automatically when the other module withdraws: §7.3 and §7.4.

This is [principle 7](../../../../docs/COORDINATOR.md#7-non-negotiable-principles) — *resolve once,
execute cheap* — in its sharpest form: all the thinking happens when a layout or a stack changes,
which is rare, and the per-event path is a rectangle test against a small pre-resolved array.

It also means **a zone with fewer than two windows is not armed at all**, so `Win`+wheel over an
ordinary un-stacked window passes straight through. The feature is invisible until it is useful.

### 3.2 What "cycle" actually does

```
Cycle(occupancy, snapshot, ZoneAddress, direction) -> WindowRef?   // pure; null when depth < 2
```

Find whichever ring member is currently frontmost **in the snapshot**, take the next one in ring
order, and return it. The caller then asks Atlas to bring it forward.

**`Show`, not `Raise`, and never `Activate` by default.** A minimised member must be restored before
it can be seen, so cycling calls `Show` (restore-if-minimised, then raise). Cycling *away* does not
re-minimise — silently changing a window's state on the way past is exactly the surprise this design
avoids elsewhere. Focus is a separate, opt-in question: see §4.2, the most technically uncertain
thing in the module.

---

## 4. What Zones needs from the pillars

Zones needs two things neither pillar offers today. Both are pillar extensions, specified as part of
this design because a module may never add them for itself.

### 4.1 Conduit — a pointer-gesture trigger kind

None of Conduit's five existing kinds expresses "a wheel tick, with a modifier, over one of these
rectangles". It is not a chord (no key-down moment), not a window event, not a schedule, and not the
existing gesture kind (which is a `Started`/`Updated`/`Ended` span with cleanup semantics; a wheel
tick is a discrete event with nothing to clean up).

It therefore satisfies [CONDUIT §7](../../../../docs/CONDUIT.md#7-adding-a-trigger-kind--the-extension-contract)'s
test for a genuinely new kind, and the full contract — intent record, refusal reasons, conflict rule,
dispatch class, guarantee statement — is specified in
[ADR 0013](../../../../docs/decisions/0013-the-pointer-gesture-trigger-kind.md) and lands in
[CONDUIT.md](../../../../docs/CONDUIT.md) as kind #6.

### 4.2 Atlas — explicit raise, and the foreground-lock dragon

[ATLAS §7.2](../../../../docs/ATLAS.md#72-what-atlas-will-not-do) currently says Atlas will not steal
focus as a side effect of placement and will not reorder z-order beyond what a move requires. Both
remain right: they forbid these things as *side effects*. Cycling needs them as an **explicit,
separately-requested operation**, which [ADR 0014](../../../../docs/decisions/0014-atlas-explicit-raise-and-activate.md)
adds.

**And here is the sharpest technical risk in the module.** Windows restricts which process may call
`SetForegroundWindow`; a process that has not recently received input generally cannot steal
foreground, and the call fails or merely flashes the taskbar button. Coordinator will be trying to
activate *another application's* window in response to input that went to a *third* application's
window. Whether the foreground lock permits that is genuinely unknown until it is tried.

The design absorbs this rather than betting on it:

| Operation | Mechanism | Reliability |
|---|---|---|
| **Raise** | z-order change with no activation | Expected to work; needs no foreground rights |
| **Show** (what cycling calls) | restore if minimised, then raise | Expected to work. Cycling *away* never re-minimises |
| **Activate** (opt-in setting) | `Show`, then request foreground | **May be refused by the OS.** Surfaced as a refusal, never silently ignored |

Raise-without-activate is the default for a second reason beyond reliability: not stealing focus is
probably the better behaviour anyway. You cycle to see a window; you click it when you want to type
in it. `zones.activate-on-cycle` exists for people who disagree, and it is honest about the fact
that the OS may overrule them.

**This is the first thing to validate on real hardware** and the module's design should not be
trusted until it has been. The runbook row is `Z-4` in
[manual-validation.md](../../../../docs/runbooks/manual-validation.md).

---

## 5. Reconciliation — where the bugs would otherwise live

Every time Zones reads a fresh Atlas snapshot, it reconciles intent against reality:

```
Reconcile(occupancy, snapshot, resolvedZones) -> (occupancy', actions)
```

Pure. No desktop, no I/O, no clock. This is the single most test-worthy function in the module, and
each row below is a case the first draft of this design could not represent
([ADR 0016](../../../../docs/decisions/0016-zone-occupancy-member-states.md)):

| Situation | Resolution |
|---|---|
| Window is no longer in the snapshot | Drop it. Closing a window leaves the zone. |
| Window's bounds differ from **`ObservedBounds`** beyond tolerance | The user moved it out by hand. Drop it. |
| Window was placed but came back a different size (`PlacedDifferently`) | **Stays.** Mark `Oversized`, and record `ObservedBounds` as what we actually got — which is why membership is tested against that and never against the zone rectangle. |
| **Either component** of `member.PlacedUnder` differs from the current `GeometryStamp` | **Do not run the bounds test at all.** Mark `AwaitingReplacement` and re-place against the re-resolved zone; testing resumes only after a placement under the current stamp. One comparison covers a monitor change *and* a layout edit ([ADR 0019](../../../../docs/decisions/0019-layout-edits-are-a-transaction.md)). |
| Window is minimised | Keep it, mark `Minimized`. Minimising is not leaving, and cycling to it will `Show` it. |
| Another window is frontmost than the ring implies (taskbar click, Alt-Tab) | **Nothing to do.** Ring order is not a claim about visibility; the next cycle continues from whatever is actually in front. |
| A zone's **monitor is not in the snapshot** (unplugged, undocked) | **The stack goes dormant** — kept, ordered, unplaced, untested, unarmed. It is *not* unassigned; that would discard the layout at the moment it is least recoverable. §5.3. |
| A zone address no longer exists (**layout switched** on a monitor that is present) | Its windows become unassigned. The screen is there and the region is unclaimed, which is a different situation from the row above. |
| A zone address no longer exists (layout **edited**) | **The reconciler never sees this.** An edit is a transaction that has already remapped the rings and produced the placements (§7.3); by the time the reconciler runs, occupancy addresses only surviving cells. |

**The tolerance is a contract detail, not a rounding fudge.** A window's reported `Bounds` include an
invisible resize border, so membership compares `VisibleBounds`
([ATLAS §3](../../../../docs/ATLAS.md#3-the-model)) against `ObservedBounds` with a tolerance.

### 5.1 Why the stamp rule matters more than it looks

Without it, a monitor being unplugged reads as *the user dragged every window out of every zone
simultaneously*, and the whole layout is discarded at exactly the moment geometry is least
trustworthy. [ATLAS §4.1](../../../../docs/ATLAS.md#41-topology-generation) already says geometry
computed at generation N must not be applied at N+1; this applies the same rule to **membership**.

The second component generalises it to the module's own geometry. Atlas owns the topology generation
and it means *the desktop changed shape*; Zones owns `LayoutRevision` and it means *this template
changed shape*. Keeping them as two fields rather than one counter is what stops a module
incrementing a pillar's counter, and what stops every other Atlas consumer re-placing geometry
because Zones edited its settings.

### 5.2 The consequence of `PlacedDifferently` on a stack

If a stacked window enforces a minimum size larger than the zone, it does not cover the zone and the
window behind it peeks out. This looks like a bug and is not one: it is an application exercising a
right it has. The design **surfaces rather than fights** — `Oversized` is observable state, and
repeated resize attempts would produce a flickering window and an application in a state its author
never anticipated.

### 5.3 Dormancy — the difference between "gone" and "not here right now"

A stack whose monitor is absent from the snapshot is **dormant**
([ADR 0020](../../../../docs/decisions/0020-dormant-stacks-and-the-displacement-rules.md)). Dormancy
is a property of the *address* — the `MonitorKey` does not resolve — so there is no member state to
keep in sync and no way for a member to disagree with its stack about it.

While dormant, reconciliation **keeps the ring and its order, and drops only members whose window has
closed** (which needs no geometry to detect). It runs no bounds test: Windows itself relocated those
windows when the screen went away, so the test would read "the user dragged them all out" and be
wrong about every one. It places nothing, and the zone has no rectangle so it cannot be in the armed
region set — that one falls out rather than needing a rule.

**Waking up requires a match good enough to trust.** When the `MonitorKey` resolves again, every
member becomes `AwaitingReplacement` and is re-placed under the current stamp — the ordinary path. But
a `Positional`-only match, which [ADR 0015](../../../../docs/decisions/0015-zone-addressing-and-durable-monitor-identity.md)
says may be a different physical screen, does **not** wake it. That monitor gets the default layout
and says so; the stack keeps waiting. Doing nothing visible is recoverable, and flinging a stack of
windows onto a screen the user never associated with them is not.

Dormant entries are bounded by occupancy being session-scoped
([ADR 0012](../../../../docs/decisions/0012-zones-stacking-model.md)): a monitor that never comes back
costs one dictionary entry until exit.

## 6. Drag to snap

**One gesture, one lifecycle.** Zones subscribes to Conduit's **input gesture** kind and to nothing
else for dragging. The gesture payload carries the dragged `WindowRef` and an `InvocationContext`,
and Conduit guarantees exactly one `Ended` for every `Started` — so the overlay put up at the start
is always taken down.

The first draft used *both* the window-event pair `MoveSizeStart`/`MoveSizeEnd` **and** the gesture
`Started`/`Ended`. Conduit defines no ordering between intent streams, so cleanup ownership was
ambiguous and "which arrived first" was undefined. Collapsing to one stream removes the race rather
than documenting it ([ADR 0017](../../../../docs/decisions/0017-invocation-context-and-one-drag-lifecycle.md)).

**On drop, the window joins the stack at the front** (the M1 default) — which is what makes stacks
emerge from ordinary use rather than requiring a separate thing to learn.

### 6.1 `stackOnDrop = false` — the swap, fully specified

**With `stackOnDrop = false`, the drop *swaps*.** The displaced occupant goes where the incoming
window came from. Every case is named, because the intuitive version of this rule covers exactly one
of them ([ADR 0020](../../../../docs/decisions/0020-dormant-stacks-and-the-displacement-rules.md)):

| Case | Result |
|---|---|
| Destination ring holds **two or more** | **Only the front member is displaced.** The rest of the ring is untouched |
| Incoming window came **from another zone Zones manages** | The occupant takes **the exact ring position the incoming window vacated**. Both rings keep their depth and their order |
| Incoming window came **from the same zone** | No displacement at all — it moves to the front of its own ring |
| Incoming window was **not managed** | The occupant goes to the incoming window's pre-drag bounds, which Zones knows because it owned the drag |
| Placing the occupant is **`Refused`** | It **stays in the destination ring, behind the incoming window**, and the outcome is recorded. A stack the user did not ask for is visible and cyclable; an unmanaged window hidden under a managed one is the bug this setting exists to avoid |
| Placing the occupant is **`PlacedDifferently`** | Not a failure. It is a member of its new zone, marked `Oversized`, as after any placement |

**The setting is a rule about drops, not an invariant about depth** — worth stating because the
opposite reading is natural and would be written as an assertion. A ring of two or more can exist
with the setting off: built while it was on, built by `zones.snap-focused` on a chord, or left over
from before it was changed. Nothing may assume depth ≤ 1, and turning the setting off never
retroactively unstacks anything.

### 6.2 The overlay

**The overlay is the module's only Shell surface,** and it lives in `Coordinator.Zones.Shell` rather
than in the platform — the "would a second, unrelated module need this?" test says *maybe eventually*
(a timer HUD, a layout-restore preview), and *maybe eventually* is not a second consumer. It also
carries the only visual answer to "is this zone stacked?" in M1: it draws each zone's depth during a
drag.

## 7. The layout designer

Authoring a layout by typing fractions is not something anyone does twice. Three operations, all
**pure** and therefore all host-tested with no desktop
([ADR 0018](../../../../docs/decisions/0018-layout-editing-grid-split-merge.md)):

**One of them builds a layout; two of them edit one. That distinction is load-bearing** and was
briefly lost — [ADR 0018](../../../../docs/decisions/0018-layout-editing-grid-split-merge.md) decided
`Grid` constructs, and a later draft of this section gave it an existing template and occupancy,
which is the grid-as-edit design 0018 explicitly rejected for M1.

| Operation | Kind | Signature |
|---|---|---|
| `Grid(columns, rows)` | **Constructor** | `Result<LayoutTemplate>` — a fresh template at `LayoutRevision = 1`. Ids are positional and stable: `r0c0`, `r0c1`, … |
| `Split(cellId, axis, fraction)` | **Edit** | `Result<LayoutEdit>` — one cell becomes two covering exactly the same rectangle |
| `Merge(cellIds[])` | **Edit** | `Result<LayoutEdit>` — several cells become one covering their bounding box |

**`Grid` takes no occupancy and produces no remapping, no retired ids and no placements**, because it
has no prior template to remap *from*. Its output is a new layout, sitting in the library alongside
the others. Putting it on a monitor is a **layout switch**, not an edit — the existing path in §5's
table, where the previous layout's addresses stop resolving and their windows become unassigned. That
is a different operation with a different name and a different consequence, and collapsing the two is
what produced the contradiction.

Adjusting an *existing* layout into a grid is deliberately not offered in M1
([ADR 0018](../../../../docs/decisions/0018-layout-editing-grid-split-merge.md)): reconciling an
arbitrary template against a fresh grid is a much harder identity problem than split or merge, and
typing a grid is what you do when starting a layout rather than refining one. The recall trigger is
in that ADR — revisit if refining-into-a-grid turns out to be a real habit.

### 7.0 What an edit returns

The arithmetic is the easy half. The part worth designing is what happens to **cell ids**, because a
cell id is a permanent contract — occupancy addresses it (§2) and settings reference it. An editor
that mints fresh ids scatters every stack on every edit, which is how you end up with an editor
nobody uses.

**And that is why an edit cannot be a function from `LayoutTemplate` to `LayoutTemplate`.** `Split`
and `Merge` take the template *and* the occupancy over it, and return one transaction
([ADR 0019](../../../../docs/decisions/0019-layout-edits-are-a-transaction.md)) — or a refusal:

```csharp
// SKETCH — illustrative, not compiled.
sealed record LayoutEdit(
    LayoutTemplate Template,                          // the new template
    int LayoutRevision,                               // bumped; monotonic per template
    IReadOnlyDictionary<string, string> CellRemap,    // old cell id -> surviving cell id
    IReadOnlyList<string> RetiredCellIds,             // never reissued
    ZoneOccupancy Occupancy,                          // already transformed
    IReadOnlyList<PlacementAction> Placements);       // every geometrically affected member

Result<LayoutTemplate> Grid(int columns, int rows);                 // constructor — no occupancy
Result<LayoutEdit> Split(LayoutTemplate t, ZoneOccupancy occ, MonitorKey m, string cellId, Axis a, double f);
Result<LayoutEdit> Merge(LayoutTemplate t, ZoneOccupancy occ, MonitorKey m, IReadOnlyList<string> cellIds);
```

The six outputs are produced together because they are one decision: you cannot know which members
need re-placing without knowing how cells were remapped, and you cannot remap rings without knowing
which ids survived. **Every geometrically affected member gets a `PlacementAction` — including
members of a ring whose cell id did not change**, which is the case id stability exists to create and
therefore the case it hides.

An edit is applied to the module's state in **one step or not at all**: template, revision, occupancy
and armed regions move together. A new template with the old occupancy, or new geometry with stale
armed regions, is the state this makes unrepresentable.

### 7.1 Identity through an edit

- **Split keeps the original id on the first fragment** (left for a vertical split, top for a
  horizontal one) and mints one new id. The stack stays with the first fragment, which shares the
  original's origin — so the windows are closest to where they already were.
- **Merge keeps the id of the first cell in reading order** (topmost, then leftmost). The other ids
  are **retired** into the template's `retiredCellIds` and never reused, because a reused id would
  silently point an old saved binding at a different region.
- **Merged stacks combine.** The retired cells' rings are appended to the survivor's, in reading
  order. Those windows were adjacent and are now genuinely one zone; discarding them would punish
  the user for editing.

### 7.2 Merge is refusable, and that is the interesting predicate

**Cells merge only if they tile their bounding box exactly** — no gap, no overlap. Anything else is
`Refused(NotContiguous)`, naming the area that is uncovered or doubly covered.

This is the most testable thing in the whole module: a small grid, every subset, and a predicate with
an exact answer. It is also the one place where the editor is stricter than hand authoring — §2
permits overlapping and gappy templates, and `Merge` will refuse on them. That asymmetry is
deliberate: the editor produces tilings, and hand authoring stays as expressive as it was.

The rejected alternative was to auto-repair a non-contiguous selection by taking the bounding box and
deleting whatever was inside it. That silently destroys cells the user did not select — data loss
dressed as convenience.

### 7.3 Applying an edit

An edit is committed through the ordinary settings path — it is a settings-save, not a live
mutation — but what is saved is the whole transaction, not just the template. In order:

1. **Persist** the new template *and* its bumped `LayoutRevision`. Without the revision on disk, an
   edit made in one session is indistinguishable from a fresh load in the next.
2. **Swap in** the transformed `ZoneOccupancy`. Rings have already been remapped by `CellRemap`;
   rings whose cells were retired have already been concatenated into their survivor (§7.1). Windows
   in a cell that vanished with no survivor are unassigned by the transaction — they are not left
   for the reconciler to discover.
3. **Republish** the armed region set against the new geometry, before any placement runs.
4. **Execute** the `PlacementAction` list, stamping each placed member with the new `GeometryStamp`.

**Step 3 may be granted only in part, and that must not roll back steps 1–2.** A higher-priority
module may request an overlapping region with the same modifier
([CONDUIT §3.6](../../../../docs/CONDUIT.md#36-pointer-gesture)). Contention is **arbitrated, not
refused**: the publication is accepted, Zones' request is recorded whole, and the result names the
rectangles actually granted. Rolling back the *user's layout edit* over an unrelated module's regions
would be absurd — and now nothing tempts anyone to, because there is no failure to recover from.

So step 3 is one call with one answer. The edit stands; what degrades is cycling, on exactly the zones
the result says were withheld. Because Zones knows which, the designer marks them instead of leaving a
zone that silently ignores the wheel. `zones.cycle-forward` / `cycle-back` remain bound to chords and
are unaffected (§8.1), which is the second reason those exist.

**Zones does not retry, and does not track what it lost.** Its standing request already includes the
contested rectangles, so when the other module withdraws the grant returns on its own (§7.4). *An
earlier draft of this section carried a two-step subtraction retry here; it existed only because
contention used to be a refusal, and it is gone.*

### 7.4 Losing and regaining a region

A grant is a **revocable lease**, so a higher-priority module requesting a rectangle Zones holds
**takes it** — and when that module withdraws, unregisters or loses priority, Conduit recomputes
grants from every module's standing request and Zones gets it back. Zones' *request* never changes
through any of this; only the grant does, so there is nothing to re-publish and nothing to remember
([ADR 0021](../../../../docs/decisions/0021-requested-versus-granted-regions.md)).

**Zones is told by one message carrying the whole current grant**, on Conduit's control plane
([CONDUIT §3.6.1](../../../../docs/CONDUIT.md#361-requested-and-granted-are-two-different-values)):

```csharp
// SKETCH — illustrative, not compiled.
void OnGrantChanged(ArmedRegionSet granted, int grantVersion)
{
    if (grantVersion <= _appliedGrantVersion) return;   // already past this
    _appliedGrantVersion = grantVersion;
    _cyclableZones = ZonesCoveredBy(granted);           // adopt, do not diff
}
```

**The handler adopts the set; it never diffs.** That is what makes it correct regardless of what was
delivered before it — a message coalesced away, or one arriving late, cannot leave Zones out of step,
because every message states the whole truth. The version guard makes it independent of a delivery
guarantee Zones cannot verify.

Everything else follows from `_cyclableZones`:

- **Occupancy is untouched.** Losing the wheel gesture over a zone changes nothing about which windows
  belong in it. The grant governs the gesture, not the model.
- **The designer marks zones that are not cyclable**, and un-marks them when they come back — for the
  same reason a refused activation is surfaced rather than swallowed. A zone still shown as
  unavailable an hour after it was restored is exactly as wrong as one silently ignoring the wheel.
- **Zones never re-requests.** Re-publishing a rectangle the user's own priority setting gave to
  someone else is a module fighting its user, and it cannot win.

*An earlier draft handled two delta events, `RegionsRevoked` and `RegionsRestored`. Adopting a state
is strictly less work than reconciling two deltas, and it is the only version that survives a
notification being coalesced away under load.*

**The chord bindings are unaffected throughout**, which is the second time §8.1's decision to make
`cycle-forward` / `cycle-back` Actions pays for itself: the feature loses its pointer affordance and
keeps its keyboard one. A revocation degrades Zones; it does not break it.

**A placement may still fail individually** (`Refused`, `PlacedDifferently`), and that is reported
per member rather than failing the edit. The template change has already been decided by the user;
an application refusing to resize is not a reason to reject their layout. Those members reconcile
through §5's table exactly as they would after any other placement.

The reconciler is therefore *not* the mechanism that repairs a layout edit — by the time it next
runs, occupancy already addresses only surviving cells and every affected member is stamped. It is
the mechanism that notices the desktop disagreeing afterwards.

---

## 8. The contract Zones publishes

### 8.1 Capabilities

Ids are permanent — settings files and user bindings reference them as strings, so they are added
freely, never renamed, never reused.

| Id | Kind | What it does |
|---|---|---|
| `zones.snap-focused` | Action | Snap the focused window into the zone under the cursor |
| `zones.cycle-forward` | Action | Cycle the stack under the cursor forward |
| `zones.cycle-back` | Action | Cycle it backward |
| `zones.next-layout` | Action | Switch the active layout on the monitor under the cursor |
| `zones.edit-layout` | Action | Open the layout designer for the monitor under the cursor (§7) |
| `zones.stack-on-drop` | Toggle | Whether a drop joins the stack or displaces the occupant |
| `zones.activate-on-cycle` | Toggle | Whether cycling also takes focus (§4.2 — may be refused) |
| `zones.padding` | Number | Work-area inset, in pixels |
| `zones.gap` | Number | Separation between neighbouring zones |
| `zones.active-layout` | Reading | The layout currently applied. **Not bindable** |
| `zones.stack-depth` | Reading | Depth of the zone under the cursor. **Not bindable** |

`cycle-forward` and `cycle-back` are Actions and therefore bindable to chords, which is deliberate:
it gives the feature a **keyboard path that does not depend on the wheel hook at all**. If §4.2's
foreground dragon or the hook budget turns out worse than expected, the module still works.

### 8.2 Trigger intents

| Intent | Purpose |
|---|---|
| Hotkey chord | snap, cycle forward/back, next layout |
| Input gesture (drag + modifier) | **the whole drag** — detection, overlay lifecycle, and the dragged window, from one stream |
| **Pointer gesture** (modifier + wheel over armed regions) | cycling — the new kind, §4.1 |

**Three, not four.** The first draft also subscribed to the window-event pair
`MoveSizeStart`/`MoveSizeEnd` for drag detection, alongside the gesture. Conduit defines no ordering
between intent streams, so cleanup ownership was ambiguous and "which arrived first" was undefined
([ADR 0017](../../../../docs/decisions/0017-invocation-context-and-one-drag-lifecycle.md), §6). The
gesture payload already carries the dragged `WindowRef` — Conduit owns the hook and knows which window
is in a move/size loop — so the second stream bought nothing and cost a race. The window-event kind
remains in the taxonomy for consumers that want raw move/size transitions; Zones is not one.

Every one of these is a **request that can be refused**. A chord may already be held by another
module or by Windows itself; the pointer gesture may be refused if another module holds an
overlapping region (§7.3). Zones must remain useful when refused — which is why the wheel and the
chords are alternative paths to the same capability rather than one depending on the other.

### 8.3 Settings, v1

```jsonc
{
  "schemaVersion": 1,
  "layouts": [
    { "id": "…", "name": "…", "layoutRevision": 3, "cells": [ … ],
      "retiredCellIds": [ … ], "padding": 8, "gap": 8 }
  ],
  "monitorLayouts": { "<MonitorKey>": "<layout id>" },
  "snapModifier": "Shift",
  "cycleModifier": "Win",
  "stackOnDrop": true,
  "activateOnCycle": false
}
```

Additive by default; a structural change ships an `ISettingsMigration`
([ADR 0011](../../../../docs/decisions/0011-settings-migrate-the-persisted-document-not-the-deserialized-object.md)).

**`layoutRevision` is persisted with its template, not derived.** Without it on disk, an edit made in
one session is indistinguishable from a fresh load in the next, and §7.3's re-placement never happens
([ADR 0019](../../../../docs/decisions/0019-layout-edits-are-a-transaction.md)). It is one integer,
and it is the cheapest field in the file to forget.

**`monitorLayouts` is keyed by `MonitorKey`, never by the snapshot-local `MonitorId`.** The key is
durable across reconfiguration by construction, and it carries a **confidence**
([ADR 0015](../../../../docs/decisions/0015-zone-addressing-and-durable-monitor-identity.md)) — because
two identical monitors with no serial number in their EDID are genuinely indistinguishable, and no
amount of design makes them otherwise. A `Positional`-only match is therefore treated as *possibly the
wrong screen*: the monitor falls back to the default layout **and says so**, rather than applying
somebody else's layout to it, and a dormant stack does not wake on it (§5.3).

---

## 9. The Core/Shell split, applied here

| | `Coordinator.Zones.Core` (`net9.0`) | `Coordinator.Zones.Shell` (`net9.0-windows`) |
|---|---|---|
| Occupancy model, stack ordering, cycling arithmetic | ✔ | |
| Reconciliation against a snapshot | ✔ | |
| Which zone a drop lands in (hit-testing) | ✔ (Atlas `LayoutMath.HitTest`) | |
| Armed-region computation | ✔ | |
| Settings shape and migrations | ✔ | |
| The drag overlay window and its painting | | ✔ |
| Everything else Windows-facing | | *neither — it belongs to a pillar* |

The bottom row is the interesting one. Zones needs no P/Invoke of its own: placement and raising are
Atlas, hooks and hotkeys are Conduit. Its Shell adapter exists **only** because it draws an overlay.
If the overlay were ever lifted to a platform service, `Coordinator.Zones.Shell` would be deleted
entirely — a module with no Windows code at all, which is the split working exactly as intended.

---

## 10. Testing plan

Core tests, all runnable on any OS with no desktop:

- **Addressing** — the same template applied to two monitors keeps two independent stacks; switching
  layouts on one monitor does not touch the other's occupancy. This is the case the first design
  could not represent, so it is the case that proves the new one.
- **Occupancy invariants** — assigning a window removes it from its previous zone; a window is never
  in two stacks; ring order survives assignment.
- **Cycling** — cyclic in both directions; depth < 2 is a no-op; cycling starts from whichever member
  the *snapshot* says is frontmost, not from stored order; a minimised member is selected and
  `Show`n rather than skipped.
- **Reconciliation** — every row of §5's table, plus the two combinations that actually happen: a
  topology change *and* a closed window in the same snapshot, and a `PlacedDifferently` member
  surviving two consecutive reconciliations (the case the first draft dropped on the second pass).
- **Membership tolerance** — a correctly-placed window whose `Bounds` differ from `ObservedBounds` by
  the invisible border is still a member; one moved 200px away is not.
- **Dormancy** — a stack whose monitor leaves the snapshot keeps its ring and its order, is not
  bounds-tested, and is not armed; a member closed while dormant is still dropped; the monitor
  returning with a confident match wakes every member as `AwaitingReplacement`; the monitor returning
  with a **`Positional`-only** match does **not** wake it. That last one is the test that stops a
  stack landing on a stranger's screen.
- **Displacement** — all six rows of §6.1: front-member-only on a deep ring; ring-position exchange
  between two managed zones; same-zone drop as a no-op; unmanaged source falling back to pre-drag
  bounds; a `Refused` displacement **degrading to a stack rather than an orphan**; `PlacedDifferently`
  landing as `Oversized`.
- **Armed regions** — a zone leaves the armed set the moment its depth falls below two, which is what
  stops `Win`+wheel swallowing scroll events over an ordinary window. Plus the partial-grant path: a
  publication whose rectangles are contested is **accepted**, and the result names what was granted so
  the withheld zones can be marked.
- **Grant adoption, in both directions and out of order.** A `GrantChanged` carrying a reduced set
  marks exactly those zones un-cyclable, leaves occupancy untouched, and triggers **no republication**
  — write that last assertion first, because a handler that "helpfully" re-publishes turns one
  revocation into a loop against the user's own priority setting. A later `GrantChanged` restoring
  them marks them cyclable again and clears the designer's marker. Then the two that matter under
  load: **applying only the newest message must reach the same state as applying every message**
  (which is what lets Conduit coalesce), and a message whose `GrantVersion` is **not newer** must be
  ignored. A suite testing only the revoke direction passes on the half-implementation whose failure
  is a feature that never comes back.
- **Dispatch by token** — a cycle dispatch carrying a stale region-set version is dropped, and cycling
  never hit-tests the context cursor to find its zone. Written as a test because the tempting
  implementation is the wrong one.
- **Designer** — `Grid` produces the expected cell count and ids **and returns a bare template with no
  occupancy, remap or placements** (the assertion that keeps it a constructor); `Split` preserves the original id on
  the first fragment and its stack; `Merge` refuses every non-tiling subset of a 3×3 grid and accepts
  every tiling one; merged rings concatenate in reading order; a retired id is never reissued.
- **Edits re-place their windows** — the tests that would have caught the defect
  [ADR 0019](../../../../docs/decisions/0019-layout-edits-are-a-transaction.md) fixes, and the
  reason they are listed separately from the designer arithmetic:
  - **Split re-places the surviving cell's stack.** Split a cell holding three windows; the surviving
    fragment keeps its id, and the edit still yields a `PlacementAction` for **all three** members
    against the new, smaller rectangle. The assertion is on the placement list, not on the template —
    a template-only test passes here while the windows sit at the old size.
  - **Merge re-places both rings.** Merge two cells holding two windows each; the survivor's own two
    members are re-placed against the enlarged rectangle, not only the four-member concatenated ring.
  - **The stamp forces it even if the placements were ignored.** After an edit, every member's
    `PlacedUnder.LayoutRevision` is stale, so a reconciliation run marks them `AwaitingReplacement`
    rather than testing bounds. This is the guard behind the guard, and it is asserted directly.
  - **`CellRemap` and `RetiredCellIds` are asserted as data** — split's first-fragment rule and
    merge's reading-order rule become map entries a test reads, rather than prose an implementer
    re-derives.
  - **The transaction is all-or-nothing.** A refused `Merge` returns no `LayoutEdit` at all: template,
    revision and occupancy are untouched, and no placement runs.
- **Settings migration** — round-trip and defaults, per MODULE_SPEC §6.

Manual-validation rows (`Z-1` … `Z-6`) cover what no test can: placement on a real desktop, the
mixed-DPI case, wheel-hook latency under load, the foreground lock, and the overlay surviving a drag
that ends outside any zone.

## 11. Dragons

| # | Dragon | Current answer |
|---|---|---|
| 1 | **Foreground lock may refuse activation** (§4.2) | Default to raise-without-activate; surface refusals; validate first |
| 2 | **Wheel hook is on every scroll on the machine** | Armed-region test only, pre-resolved, fail-open; measured latency budget |
| 3 | **Swallowing a wheel event wrongly breaks scrolling** | Arm only zones with depth ≥ 2; modifier required; pass through on any doubt |
| 4 | **Stacks are invisible without UI** | Overlay shows depth during drag in M1; a tab strip is the named next milestone |
| 5 | **Monitor identity across reconfiguration** (§8.3) | `MonitorKey` carries a confidence; a `Positional` match that may be wrong falls back to the default layout **and says so** ([ADR 0015](../../../../docs/decisions/0015-zone-addressing-and-durable-monitor-identity.md)), and does not wake a dormant stack (§5.3) |
| 6 | **`PlacedDifferently` breaks stack coherence** (§5.2) | Surface it as `Oversized`; never fight the application |
| 7 | **Stack membership does not survive a restart** | Accepted for M1 — window handles do not survive either. Re-associating by process and title is a heuristic that will be wrong silently, which is worse than starting empty |
| 8 | **An edit that half-applies** — new template, old occupancy, stale armed regions | One `LayoutEdit` transaction applied in one step (§7.3); the `GeometryStamp` catches anything that escapes it ([ADR 0019](../../../../docs/decisions/0019-layout-edits-are-a-transaction.md)) |
| 9 | **Another module requests a region Zones needs** | Contention is arbitrated, not refused: the publication is accepted and the result names what was granted — never a rollback of the user's layout (§7.3). Cycling degrades on the withheld zones; the chord bindings are unaffected |
| 10 | **A region Zones holds is revoked** mid-session, **and later comes back** | One `GrantChanged` carries the whole current grant; Zones **adopts the set** rather than diffing, guarded by `GrantVersion` (§7.4). Adoption is idempotent and order-insensitive, so a coalesced or late message cannot desynchronize it |

---

## See also

- [README.md](../README.md) — the module front door, and where to resume.
- [docs/MODULE_SPEC.md](../../../../docs/MODULE_SPEC.md) — the contract every module implements.
- [docs/ATLAS.md](../../../../docs/ATLAS.md) — desktop truth, the layout math, the placement contract.
- [docs/CONDUIT.md](../../../../docs/CONDUIT.md) — trigger intents, arbitration, the hook-thread budget.
