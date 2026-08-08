---
title: Atlas — desktop spatial truth
tier: pillar
status: living
updated: 2026-08-08
audited: 2026-08-08
module: atlas
related:
  - docs/COORDINATOR.md
  - docs/CONDUIT.md
  - docs/MODULE_SPEC.md
  - docs/OPERATING_MODEL.md
  - docs/NEXT.md
  - docs/runbooks/manual-validation.md
  - src/pillars/atlas/README.md
---

# Atlas — desktop spatial truth

> **The pillar that owns what the desktop *is*.** Monitors, work areas, DPI and scaling, virtual
> desktops, windows and their geometry and state — one canonical model, read as one coherent
> snapshot, plus the pure layout math that turns a template and a work area into rectangles. It is
> the dual of [Conduit](CONDUIT.md), which owns what the desktop just *did*.
>
> **One sentence:** a module never enumerates the desktop — it reads a single timestamped snapshot
> whose parts were all true at the same instant, because two modules independently caching window
> state will disagree, and the disagreement surfaces as windows landing in the wrong place with no
> reproducible cause.
>
> **Status: DESIGNED AND DOCUMENTED, NOT BUILT.** No Atlas code exists — not a project, not a type,
> not a line. Every rule on this page is a specification, never an observation. See §9.
>
> **Read order:** [COORDINATOR.md](COORDINATOR.md) (the platform) → **this** →
> [MODULE_SPEC.md](MODULE_SPEC.md) (how a module obtains a snapshot) →
> [`src/pillars/atlas/README.md`](../src/pillars/atlas/README.md) (the code's front door).

---

## 1. What Atlas is

Atlas is the single source of truth for the physical shape of the desktop. Everything a module might
want to know about *where things are* — which monitors exist, how large they are, how much of each
one is usable, how each is scaled, which windows exist, where each one sits, what state it is in —
comes from Atlas, in one shape, with one set of rules about what the numbers mean.

The governing rule:

> **A module never enumerates the desktop.**

A module does not call `EnumWindows`. It does not call `EnumDisplayMonitors`. It does not keep a
dictionary of window handles it saw once and hopes are still valid. It asks Atlas for a snapshot,
computes against that snapshot, and asks Atlas to place a window. Atlas owns both the reading and
the writing, and therefore owns the only account of what happened.

The dual rule in [Conduit](CONDUIT.md) is *a module never names an input mechanism*, and the two
pillars are shaped by the same argument at different targets. Conduit centralizes because a shared
exclusive resource needs one arbiter. Atlas centralizes because **compound state needs one
observer**.

---

## 2. Why this exists — two caches will disagree

Suppose two modules each maintain their own view of the desktop, because each of them, reasonably,
wanted a monitor list and a window list. Nothing about that is wrong in isolation. Both will work.
They will also, eventually and unavoidably, disagree — and the way the disagreement surfaces is what
makes this a pillar rather than a shared helper class.

**The desktop changes while you are reading it.** Between one call and the next, the user drags a
window across a monitor boundary, a laptop is undocked, a projector is plugged in, an application
opens a splash screen and closes it, Windows changes a scale factor, the taskbar auto-hides. A
module that asks "which monitor is this window on?" and then asks "what is that monitor's work
area?" as two separate calls can receive an answer pair that **never coexisted** — window on monitor
2, work area of monitor 2 as it was before the resolution changed. The arithmetic is then perfect
and the result is wrong.

**Nobody can debug it.** The symptom is a window that lands twenty pixels off, or on the wrong
monitor, or straddling a boundary — and only sometimes. There is no exception, no log line, no
failing test. It reproduces on the reporter's machine and nowhere else, because it is a race whose
window is a few milliseconds wide and whose trigger is a human hand.

**Two independent caches make it worse in a specific way.** Once module A believes the work area is
one rectangle and module B believes it is another, the bug is not merely intermittent — it is
*inconsistent between features of the same application*, which destroys the user's ability to form a
mental model. Snap-to-zone puts the window at one edge; a restore feature puts it at another. The
tool now feels unreliable, which [OPERATING_MODEL §6](OPERATING_MODEL.md) identifies as terminal for
a utility that lives in the tray all day.

The fix is not "be careful." It is **structural**: make the coherent read the only read there is
(§4), and make the derived geometry a pure function of that read (§6). Recorded as ADR 0006.

---

## 3. The model

Five record types and the relationships between them. All of these live in Core (§8) and none of
them contains a Windows handle type, a Win32 struct, or a raw `IntPtr`.

| Type | Carries | Notes |
|---|---|---|
| **Monitor** | a stable-for-the-session id · the full monitor rect · the **work area** rect · the **scale factor** · primary flag | Work area ≠ monitor rect: the taskbar and any registered appbars are subtracted |
| **VirtualDesktop** | an opaque id · a "is this the current one" flag | Deliberately thin — §7 explains why |
| **WindowRef** | an opaque, comparable handle-shaped id · a validity generation | Opaque so Core never sees an `HWND`; comparable so a module can hold one across a snapshot |
| **WindowInfo** | `WindowRef` · the geometry rect · the *visible* bounds rect · state (normal / minimized / maximized) · owning monitor · virtual-desktop id · a small set of classification flags | Two rects, not one — §5 explains why that is not redundancy |
| **DesktopSnapshot** | every monitor · every qualifying window · the virtual-desktop id · a **monotonic capture stamp** · a **topology generation** | The unit of reading. Immutable. §4 |

Plus the layout types, which are pure geometry with no desktop in them at all:

| Type | Carries |
|---|---|
| **LayoutTemplate** | a named set of relative cells (fractions of a work area), plus padding and gap |
| **ZoneRect** | one resolved rectangle in a named coordinate space, with the zone's index and id |
| **ZoneSet** | the resolved rectangles for one monitor, plus the template and work area they came from |

**"Every qualifying window" is a decision, not a detail.** A naive enumeration returns hundreds of
things the user has never seen: tool windows, owned dialogs, zero-size helpers, message-only
windows, and — the modern trap — **cloaked** windows, which are the mechanism by which a store
application on another virtual desktop remains a real, visible-looking, enumerable window that is
not actually on screen. The predicate that decides "is this a window a user would say is open" is
**pure Core logic over flags the Shell collects**, which means it is one shared answer, testable
against a table of cases. It is exactly the sort of thing two modules would each get subtly and
differently wrong.

---

## 4. The snapshot contract

**A module reads one snapshot. It does not issue queries.**

```csharp
// SKETCH — not compiled. See §9.
DesktopSnapshot snap = atlas.Capture();          // one instant, everything consistent
Monitor        mon  = snap.MonitorOf(window);    // pure lookup INSIDE the snapshot
ZoneSet        set  = LayoutMath.Resolve(template, mon.WorkArea);  // pure math (§6)
```

Four properties define the contract.

**Coherent.** Every field in a snapshot was true at the same instant. The monitor list, the work
areas, the scale factors, the window list, and each window's geometry are one observation, not a
sequence of observations stitched together. This is the entire point: `MonitorOf` is a lookup
*inside* the value, not a fresh call to the operating system, so nothing can change between the two
lines above.

**Immutable and re-readable.** A snapshot is a value. Reading it twice gives the same answer.
Passing it to another method cannot change it. If a module wants a newer view, it takes a new
snapshot — there is no "refresh" that mutates the one it is holding, because that would reintroduce
the tearing the type exists to prevent.

**Stamped, but not self-aging.** A snapshot carries a **monotonic** capture stamp and nothing else
about time. It does not carry an "age" field, and Atlas never tells a consumer how old a snapshot
is. **Freshness is computed by the reader**, from its own monotonic clock, at the moment it actually
matters:

```csharp
// SKETCH — not compiled.
var age = clock.Now - snap.CapturedAt;    // the READER decides what "too old" means, and when
```

This looks like a small distinction and is not. An age computed by the producer is a claim about a
moment that has already passed by the time the consumer reads it, and it silently becomes more wrong
the longer the value is held. An age computed by the consumer at the point of use is always exactly
correct. It also means different consumers can hold different, equally valid thresholds — a drag
overlay tolerates a snapshot that a placement operation must reject — without Atlas having to guess
for them.

**The clock is monotonic, never wall-clock**, because system time jumps: clock sync, daylight-saving
transitions, and the user setting the clock all move it backwards and forwards. A freshness check
against wall-clock time can conclude that a snapshot taken one second ago is an hour old, or that a
snapshot from an hour ago is fresh.

### 4.1 Topology generation

A snapshot also carries a **topology generation**: an integer bumped whenever the *shape* of the
desktop changes — a monitor added or removed, a resolution or scale factor changed, a work area
resized by the taskbar. It is the cheap, comparable answer to "is the geometry I computed still
meaningful?"

The rule that makes it worth having: **a layout computed against generation N must not be applied at
generation N+1.** It must be recomputed. A zone set derived from a work area that no longer exists
is not approximately right; it is arbitrary. Carrying the generation into the `ZoneSet` makes the
mistake detectable instead of invisible.

Generation bumps come from display-topology notifications, which arrive through
[Conduit](CONDUIT.md) — Conduit owns the event source, Atlas owns what the event *means*. Atlas does
not install its own hooks; that would put a second owner on a surface that exists to have one.

### 4.2 Drag: take the snapshot once

The concrete payoff, and the case that will otherwise be got wrong. During a window drag, the
temptation is to re-read the desktop on every mouse move. That is a full enumeration on the
interaction path, at mouse-event frequency, and it is precisely what
[principle 7 — *resolve once, execute cheap*](COORDINATOR.md#7-non-negotiable-principles) forbids.

The design instead: **take one snapshot at `MoveSizeStart`, resolve the zone rectangles once, and
run the entire drag against pre-computed geometry.** Hit-testing the cursor against a resolved
`ZoneSet` is comparison arithmetic. The only thing that can invalidate it mid-drag is a topology
generation bump, which is rare, detectable, and can be handled by recomputing once rather than
continuously.

This is where the two pillars interlock most tightly: Conduit's guarantee that `MoveSizeEnd` always
follows `MoveSizeStart` ([CONDUIT.md §3.2](CONDUIT.md)) is what makes a snapshot held across a drag
safe to release.

---

## 5. Coordinate spaces and the DPI problem

**This section is the single most common source of "why is my window twenty pixels off" bugs, and it
is worth reading before writing any geometry code at all.**

Windows presents window and monitor geometry differently depending on how the *process* declared its
DPI awareness, and mixing spaces is silent — no error, no exception, just numbers that are wrong by
a scale factor or an offset.

### 5.1 The spaces

| Space | What one unit is | Where the origin is |
|---|---|---|
| **Physical (device) pixels** | one actual pixel on the panel | the **virtual screen** origin: the top-left of the *primary* monitor |
| **Effective pixels (DIPs)** | 1/96 inch — a logical unit that is `physical / scaleFactor` | whatever the UI framework's layout root is |
| **Monitor-local** | physical pixels, but measured from that monitor's own top-left | the monitor's own corner |

Three consequences that catch people:

**Secondary monitors have negative coordinates.** The virtual screen's origin is the primary
monitor's top-left, so a monitor placed to the left of it starts at a negative X. Code that assumes
`(0,0)` is the top-left of the desktop, or that clamps coordinates to be non-negative, is broken the
first time someone arranges their monitors right-to-left.

**Scale factor is per-monitor, not per-machine.** A 150% laptop panel next to a 100% external
display is the normal case, not an exotic one. Any conversion between effective and physical pixels
must name *which monitor's* scale factor it used, which is why the `ZoneRect` type (§3) carries its
space rather than being a bare rectangle.

**A process must be per-monitor-DPI-aware v2, or none of this is available.** A DPI-unaware process
is handed *virtualized* coordinates — Windows lies to it, scales its output, and everything it
measures is wrong on a non-100% monitor. A system-DPI-aware process is told the primary monitor's
DPI everywhere, which is right on one monitor and wrong on the others. Only per-monitor-v2 awareness
reports true physical pixels and delivers the DPI-change notification a window needs when it moves
between monitors. This is a manifest-level declaration on the application, and getting it wrong
poisons every measurement in the system.

### 5.2 Naming which space each surface speaks

Atlas's rule: **the space is part of the type, and conversion happens exactly once, at the Shell
boundary.** Core never holds a rectangle whose space is ambiguous, and never holds an effective-pixel
rectangle without the scale factor that produced it.

| Surface | Speaks | Notes |
|---|---|---|
| Window rect / set-position APIs (in a per-monitor-v2 process) | physical pixels, virtual-screen origin | the space Atlas normalizes *to* |
| Monitor info — full rect and work area | physical pixels, virtual-screen origin | work area already has the taskbar subtracted |
| Per-monitor / per-window DPI queries | a DPI number; `scale = dpi / 96` | the only legitimate source of a scale factor |
| WinUI / XAML layout and window sizing | **effective pixels** | the Shell converts at the boundary — Core never sees these |
| The extended-frame-bounds attribute | physical pixels, **visible** bounds | see below |

**The two-rects problem, stated plainly.** On modern Windows the reported window rectangle includes
an *invisible* resize border — a few pixels of transparent frame outside the pixels the user can
see. Position a window flush to a monitor edge using that rectangle and it will appear to overhang
by a handful of pixels; align two windows edge to edge and they appear to overlap. The visible
bounds come from a separate, DWM-provided attribute. Atlas therefore carries **both** rects in
`WindowInfo` (§3): the geometry rect the placement API will accept, and the visible bounds a human
perceives. Layout reasons about the visible bounds; placement compensates by the difference. This is
the concrete mechanism behind the twenty-pixel complaint, and it is a per-window, per-state,
per-Windows-version difference — so it is measured, never assumed constant.

---

## 6. The pure layout math

**Given a layout template and a work area, produce zone rectangles.** That is arithmetic. It has no
Windows in it, no handles, no API calls, no I/O, and no ambient state:

```
LayoutTemplate  ×  WorkArea  →  ZoneSet
```

It is therefore **completely host-testable** — on Linux, in CI, in the container this repository was
bootstrapped in, with no monitor attached and no .NET-on-Windows anywhere. That is not a happy
accident; it is the concrete payoff of the Core/Shell split (§8, ADR 0003), and it is the reason the
hardest-to-get-right part of the first module is also the cheapest part to verify.

**The algorithm, decided here because getting it wrong is invisible.** Compute the cumulative
*boundaries* first, round each boundary exactly once, then derive each zone from its adjacent
boundaries. Do **not** compute each zone's width independently and lay them end to end: independent
rounding accumulates, and the result is a one-pixel seam between some pairs of zones and a one-pixel
overlap between others, depending on the work area's width. The user perceives this as a hairline of
wallpaper between two snapped windows — the exact class of small wrongness that makes a tool feel
cheap.

The cases the test table must cover, named now so they are not discovered later:

| Case | Required behavior |
|---|---|
| Adjacent zones | share an **exact** edge — no gap, no overlap, at every work-area width |
| Fractions that do not sum to 1 | normalized, or refused — declared either way, never silently stretched |
| Gaps and padding | subtracted before division, so gaps do not shrink the last zone disproportionately |
| A work area smaller than the template's minimum | refused with a reason, not silently producing zero-width zones |
| Zero-size or inverted work area | refused; never a negative-width rectangle escaping into a placement call |
| Mixed scale factors | each monitor resolved against its own work area and scale — never the primary's |
| Very wide and very tall work areas | no overflow, no accumulated drift across many zones |

Every row is a unit test with a literal expected rectangle. None of them needs a monitor. When
[COORDINATOR.md §8](COORDINATOR.md)'s P3 gate says the zone math is "host-tested against a table of
work areas and templates including mixed DPI," this table is what it means.

---

## 7. The placement contract

Reading is half of Atlas. The other half is the one operation that writes: **move this window to
this rectangle.** It is stated as a contract because the failure modes are numerous, mostly outside
our control, and individually easy to swallow.

### 7.1 What Atlas will do

- Move and resize a top-level window to a rectangle in a named space, converting exactly once.
- Restore a maximized window before positioning it, when the requested rectangle demands it.
- Compensate for the visible-bounds difference (§5.2) so the *perceived* result matches the request.
- Handle the DPI transition when a window crosses a scale boundary, which is not a single operation:
  the window is told to move, the system notifies it of the DPI change, the application resizes
  itself in response, and the final rectangle must be re-applied. A naive single call lands wrong on
  exactly the multi-monitor mixed-scaling setup this pillar exists to get right.
- **Verify and report.** Placement returns an outcome, not `void`.

### 7.2 What Atlas will not do

- It will not steal focus as a side effect of placement. Moving a window is not activating it.
- It will not reorder z-order beyond what the move itself requires.
- It will not move a window the user is actively dragging, except as the committed result of an
  explicit gesture ([CONDUIT.md §3.5](CONDUIT.md)).
- It will not persist anything. Where a window "should" be is a module's settings, not desktop truth.
- It will not retry indefinitely against an application that fights it (§7.3). One correction pass,
  then report what actually happened.

### 7.3 What cannot be done at all, and why

These are not bugs to be fixed later. They are properties of the platform, and the contract is that
each becomes a **surfaced refusal** rather than a silent failure — the same discipline as
[Conduit's refusals](CONDUIT.md).

| Case | Why | Outcome |
|---|---|---|
| **Elevated process** | An unelevated process cannot manipulate windows owned by an elevated one — the isolation is the security model working correctly | `Refused(Elevated)`, surfaced, with the honest explanation that running Coordinator elevated is the only workaround and carries its own cost |
| **Exclusive fullscreen** | The application owns the display mode; moving its window is meaningless and can desynchronize or crash it | `Refused(Fullscreen)` |
| **System and shell surfaces** | The taskbar, Start, and the shell's own windows are not application windows | `Refused(NotAnApplicationWindow)` |
| **Window enforces its own geometry** | Applications legitimately clamp to minimum, maximum, or aspect-ratio constraints, or reposition themselves in response to being moved | `PlacedDifferently(actualRect)` — a first-class outcome, not an error |
| **Stale target** | The window closed between snapshot and placement | `Refused(WindowGone)` — expected, not exceptional |

**`PlacedDifferently` is the interesting one.** The naive design assumes a successful call means the
window is where it was asked to go, which is [OPERATING_MODEL §7](OPERATING_MODEL.md)'s *claim
stronger than its evidence* in its purest form: the call succeeded, and the window is somewhere else.
Atlas re-reads the geometry after placing and reports what is actually true. A module that snapped
three windows and got `PlacedDifferently` for one of them can tell the user something useful; a
module that got three `true` values cannot.

---

## 8. The Core/Shell split, applied here

Atlas is two projects, per [COORDINATOR.md §3](COORDINATOR.md) and ADR 0003.

| | `Coordinator.Atlas.Core` | `Coordinator.Atlas.Shell` |
|---|---|---|
| Target | `net9.0`, zero Windows dependencies | `net9.0-windows…`, all of them |
| Owns | the model types (§3) · coordinate-space types and conversions · the snapshot shape and freshness rules (§4) · the qualifying-window predicate · **the layout math** (§6) · placement *policy* and the outcome taxonomy (§7) · the topology-generation rule | window and monitor enumeration · DPI queries · the position/size call · the visible-bounds query · virtual-desktop interop · turning notifications into generation bumps |
| Decides | everything | nothing |
| Verified by | unit tests, on any OS | [manual-validation](runbooks/manual-validation.md), on a real multi-monitor desktop |

The Shell adapter **collects facts, hands them to Core, and carries out Core's answer.** It converts
raw geometry into space-tagged Core rectangles at the boundary and never lets an untagged number
past. It reports an access-denied result as `Refused(Elevated)` rather than deciding what that means.
It re-reads geometry after a placement so Core can compare — it does not do the comparing.

**What that buys.** The zone math table (§6), the qualifying-window predicate, the space conversions,
the freshness rule, the generation rule, the placement-outcome logic, and the "which monitor owns a
window that straddles two" rule are all pure functions with literal expected values, running
anywhere.

**The honest other half.** A green Core run proves none of this: that a real window moved; that the
work area matched the real taskbar; that a real mixed-DPI arrangement enumerated correctly; that a
cloaked window was excluded; that the visible-bounds compensation produced a flush edge on a real
screen; that placement survived a real DPI transition. Those are
[manual-validation](runbooks/manual-validation.md) rows on a real desktop with at least two monitors
at different scale factors, and nothing else substitutes for them.

---

## 9. Status — designed and documented, not built

**No Atlas code exists.** There is no project, no namespace, no type, no test. What exists is this
document and [`src/pillars/atlas/README.md`](../src/pillars/atlas/README.md).

Both honesty statements apply, and both are required whenever this pillar's status is described:

1. **Nothing here has been compiled.** The bootstrap environment had Python 3.11 and Node and **no
   .NET SDK**. The sketches on this page have never been through a compiler. The Python tooling
   (`tools/coord/coord.py`, `tools/doc-audit/audit.py`) *has* been executed and its results are
   real; nothing C#-shaped in this repository shares that status.
2. **Nothing here has been measured.** No monitor has been enumerated, no window moved, no DPI
   transition observed. Every rule above is a specification the implementation will be held to.

**Where it sits in the plan.** [COORDINATOR.md §8](COORDINATOR.md) puts Atlas in **P2 — Conduit and
Atlas, minimum viable**, gated on Core tests covering the geometry math plus a manual run on Windows
reading a real multi-monitor topology correctly, *including one non-100% scaling monitor*. That
qualifier is the point of the gate — a single-monitor pass would be a check that cannot fail. The
live task list is [NEXT.md](NEXT.md); this pillar's resume instructions are in its
[README](../src/pillars/atlas/README.md).

---

## 10. Open questions and known dragons

- **Virtual desktops are deliberately modelled thin.** The documented surface answers little more
  than "is this window on the current desktop" and "move this window to that desktop by id."
  Enumerating desktops, naming them, or observing switches requires undocumented interfaces that
  change between Windows builds and break without warning. **Rejected**: Atlas models a virtual
  desktop as an opaque id and exposes only what is documented. Revisit only if a real module needs
  more, and then as an ADR that accepts the maintenance cost explicitly.
- **Auto-hide taskbars make the work area lie.** When the taskbar is auto-hidden, the work area
  equals the full monitor rect — so a zone placed flush to that edge covers the strip the user must
  reach to reveal it. The fix is a policy question (reserve a sliver? only on the taskbar's edge?
  only when auto-hide is detected?), and it is a real behavior decision rather than a geometry one.
  Deferred to the first module that snaps to an edge, with the trigger written here.
- **Which monitor owns a straddling window?** The rule is "the monitor with the largest
  intersection," matching the platform's own nearest-monitor semantics. It is pure math and belongs
  in Core; it is listed here because it is the sort of thing that gets reimplemented three times if
  it is not named once.
- **Snapshot cost is unmeasured.** Enumerating every window on every capture may be cheap enough to
  do freely or may not; the answer depends on how many windows a real session has and cannot be
  derived from first principles. The design assumes a maintained model invalidated by events with a
  full re-enumeration on a generation bump — but the threshold at which that optimization becomes
  necessary is a measurement, taken on a real desktop, not a guess made now.
- **Per-monitor-v2 awareness is a whole-process property.** It is declared once and affects every
  measurement in the application, including the Shell UI's own. It is listed as a dragon because it
  is the kind of setting that is easy to get wrong once and then rationalize for a year.

Anything that hardens into a decision becomes an ADR in [`docs/decisions/`](decisions/); anything
still speculative belongs in [INBOX.md](INBOX.md) with a recall hook, per
[OPERATING_MODEL §3](OPERATING_MODEL.md).

---

## See also

- [COORDINATOR.md](COORDINATOR.md) — the platform architecture, the principle list, and the roadmap
  whose P2 and P3 gates this pillar has to satisfy.
- [CONDUIT.md](CONDUIT.md) — the other pillar. Conduit delivers the notification; Atlas decides what
  it means. The drag path (§4.2) depends on Conduit's paired move/size guarantee.
- [MODULE_SPEC.md](MODULE_SPEC.md) — how a module obtains a snapshot and requests a placement.
- [OPERATING_MODEL.md](OPERATING_MODEL.md) — why coherent compound state is worth a pillar, and the
  evidence standard (§7) that forbids describing any of §5–§7 as verified.
- [`src/pillars/atlas/README.md`](../src/pillars/atlas/README.md) — the code front door, the intended
  layout, and **where to resume**.
- [runbooks/manual-validation.md](runbooks/manual-validation.md) — the human-executed multi-monitor
  pass that is the only thing which can validate §5 and §7.
