---
title: Conduit — the input & trigger fabric
tier: pillar
status: living
updated: 2026-08-08
audited: 2026-08-08
module: conduit
related:
  - docs/COORDINATOR.md
  - docs/ATLAS.md
  - docs/MODULE_SPEC.md
  - docs/OPERATING_MODEL.md
  - docs/NEXT.md
  - docs/runbooks/manual-validation.md
  - src/pillars/conduit/README.md
---

# Conduit — the input & trigger fabric

> **The pillar that owns every way a module can be woken up.** Modules declare typed **trigger
> intents** — "wake me on this chord", "wake me when a window moves", "wake me every 25 minutes",
> "wake me from this tray item" — and Conduit decides how to satisfy them, arbitrates who gets what,
> and dispatches the result somewhere it is safe to do work. It is the dual of [Atlas](ATLAS.md),
> which owns what the desktop *is*; Conduit owns what the desktop just *did*.
>
> **One sentence:** a module never names an input mechanism — it declares what it wants to be woken
> for, and Conduit alone holds the hotkey registrations, the hooks, the window-event source, and the
> timer wheel, so that "who has Ctrl+Alt+Space?" has exactly one answer and that answer can be shown
> to the user and changed by them.
>
> **Status: DESIGNED AND DOCUMENTED, NOT BUILT.** No Conduit code exists — not a project, not a
> type, not a line. Every guarantee on this page is a specification, never an observation. See §8.
>
> **Read order:** [COORDINATOR.md](COORDINATOR.md) (the platform) → **this** →
> [MODULE_SPEC.md](MODULE_SPEC.md) (how a module declares an intent) →
> [`src/pillars/conduit/README.md`](../src/pillars/conduit/README.md) (the code's front door).

---

## 1. What Conduit is

Conduit is the single owner of **input and time** for the whole application. Everything that can
cause a module's code to start running — a key combination, a change on the desktop, the clock, a
tray click, a drag gesture — enters the process through Conduit and leaves it as a dispatched
trigger addressed to exactly one module capability.

The governing rule, stated the way it will be quoted:

> **A module never names an input mechanism.**

A module does not call `RegisterHotKey`. It does not install a hook. It does not own a `Timer`. It
does not subscribe to a window-event source. It declares an **intent** — a typed, declarative record
saying what it wants to be woken for — and receives dispatched events. Whether that intent is served
by a kernel-arbitrated hotkey registration, a low-level hook, a WinEvent source, or a timer wheel is
Conduit's decision and Conduit's alone, and it can change without any module changing.

This is the direct dual of the rule that governs [Atlas](ATLAS.md) — *a module never enumerates the
desktop* — and both exist for the same underlying reason: the moment two modules each own a piece of
a shared, exclusive, machine-wide resource, no central answer about that resource is possible
anymore.

### 1.1 The consequence that makes it worth the friction

Because the intent is declarative, the thing a module's handler receives is **its own capability
id**, never a key code:

```csharp
// SKETCH — not compiled. See §8.
// The module declares what it does. It does not mention a key anywhere.
yield return TriggerIntent.Hotkey(
    capability: "zones.snap-current",          // stable id — the permanent contract (principle 5)
    defaultChord: Chord.Parse("Ctrl+Alt+Space") // a DEFAULT. Settings may replace it. Code does not care.
);
```

The chord is **data owned by settings**, not code owned by the module. Rebinding is a settings edit
with zero module involvement; arbitration has a human-readable name to report in the Shell ("Zones →
Snap current window"); and the handler signature never mentions input at all. Every property this
pillar exists to provide falls out of that one indirection.

---

## 2. Why this exists — central arbitration is the retrofit-expensive part

Most of Conduit could be deferred. A single module could call `RegisterHotKey` directly and work
perfectly. So could a second one. The thing that cannot be deferred is the part that only exists
when *nobody* has gone around it.

[OPERATING_MODEL §3](OPERATING_MODEL.md) defines the build-now test: *is this painful to graft onto
shipped installs?* Trigger arbitration is on the short list of four that pass it, and the reason is
specific. Suppose two modules each hold their own hotkey registration. Now ask the questions a
productivity toolbox has to be able to answer:

- **"Who has Ctrl+Alt+Space?"** There is no one to ask. The answer lives in whichever module got
  there first, in a variable nobody else can see, and only if that module bothered to remember.
- **"Show me every binding in one list, and let me change one."** The settings UI would have to
  query each module through a bespoke per-module interface that does not exist, and the rebind would
  have to be plumbed back the same way.
- **"Zones and Chrono both want this chord — tell me, and let me pick."** Neither module can detect
  the collision. The second registration simply fails, in the second module's code, where the only
  reasonable thing it can do is log and continue. The user sees a feature that silently does
  nothing.
- **"Why did my hotkey stop working after the update?"** Because a module added a default that
  happens to collide with another module's default, and nothing in the system is in a position to
  notice.

Retrofitting a central registry after modules own raw registrations means rewriting every module —
their declarations, their settings shapes, their handlers, and the settings files already on disk
that reference the old shape. Conduit must own registration from the first release or it never can.
That is the whole argument, and it is recorded as ADR 0005.

**The second, sharper reason** is that a wrong answer here damages the desktop rather than the app.
[OPERATING_MODEL §6](OPERATING_MODEL.md) states the constraint: a utility that steals a chord the
user needed, or introduces a stutter into a window drag, has *negative* value — the user pays a
constant tax for an occasional benefit. Input is the one surface where a mistake is felt
continuously. Concentrating it in one audited, budgeted, testable place is not tidiness; it is the
only way to keep the blast radius bounded.

---

## 3. The trigger-intent taxonomy

Six kinds. Each row below is a *contract*: what the intent carries when a module declares it, and
what Conduit guarantees when it fires. The guarantees are deliberately modest — an honest weak
guarantee a module can rely on beats a strong one that quietly does not hold.

| Kind | What the intent carries | What Conduit guarantees |
|---|---|---|
| **Hotkey chord** | capability id · a default `Chord` (modifier flags + one non-modifier key) · scope (`Global` today) | at most **one** owner per (chord, scope) at any instant; fires once on the key-down transition, never on auto-repeat; the payload is the capability id, never the key |
| **Window event** | capability id · an event mask · an optional coarse filter | **"something changed, re-read [Atlas](ATLAS.md)"** — coalesced, rate-limited, and explicitly **not** a complete log; `MoveSizeStart`/`MoveSizeEnd` are the one guaranteed pair |
| **Schedule** | capability id · a fixed interval, a wall-clock time, or a one-shot instant · a drift policy · a missed-fire policy | fires on a dispatch worker, never a hook thread; **not** real-time — no latency bound; behavior across machine sleep and across a civil-time discontinuity is defined, not incidental |
| **Tray / menu action** | capability id · a label · optional enabled/checked state | invoked on the UI thread; always attributed to the declaring module by name; lives in the **one** host-owned tray menu |
| **Input gesture** | capability id · a recognizer spec (e.g. *window drag in progress* + *modifier held*) | delivered as a **recognized gesture**, never raw input; updates are throttled and coalesced; **`Ended` is always delivered if `Started` was** — including on cancel |
| **Pointer gesture** | capability id · a modifier requirement · a wheel axis · an **armed region set** the module pre-resolves and republishes | a **discrete** event carrying the capability id, cursor position and tick delta; coalesced under load; **explicitly not** one dispatch per physical detent, not ordered against other input kinds, and not guaranteed at all when saturated |

The rest of this section says what each one is actually for and where its sharp edges are.

### 3.1 Hotkey chord

A `Chord` is a set of modifier flags (Ctrl, Alt, Shift, Win) plus exactly one non-modifier key.
Parsing, normalizing, formatting, and comparing chords is pure Core logic and therefore fully
testable — including the cases that bite: a chord with no modifier (refused for a global scope; it
would swallow a bare keystroke from every application), a chord that is only modifiers, and two
textual spellings of the same chord that must compare equal.

**Two arbitration layers, and only one of them is ours.** Conduit's registry arbitrates between
*modules*. The operating system arbitrates between *Coordinator and the rest of the machine*, and it
is the stronger authority — another application, or Windows itself, may already hold the chord.
Conduit must propagate that refusal outward as a first-class result rather than logging it and
continuing, because a module that believes it holds a chord it does not hold is exactly
[OPERATING_MODEL §7](OPERATING_MODEL.md)'s *claim stronger than its evidence*, one layer down.

**The default mechanism is the kernel registration, not a hook** — a decision, not an accident. A
kernel-arbitrated hotkey registration reports its refusal *at registration time*, before anything
expensive has happened, and it cannot be starved by a slow handler because no handler runs on the
input path to begin with. A low-level hook can express things a registration cannot (a modifier held
during a drag), but it puts our code on every keystroke the machine processes. So: **registrations
for plain chords; a hook only where the intent genuinely cannot be expressed as one**, which today
means gestures (§3.5) and nothing else. Revisit when a real intent arrives that needs more.

### 3.2 Window event

The mask names transitions: created, destroyed, focus changed, move/size started, move/size ended,
moved, minimized, restored. The payload carries an opaque window reference, the transition kind, a
monotonic stamp, and the [Atlas](ATLAS.md) topology generation current at the time.

**This is a hint, not a log, and the docs will keep saying so.** A complete, ordered, guaranteed
event stream would require unbounded buffering fed from a thread that must never block — the two
requirements are incompatible, so the guarantee that would have to be broken is stated as absent up
front instead. A module that needs to know the state of the desktop reads a snapshot from Atlas; a
window event only tells it that reading again is now worthwhile.

The one exception is deliberate and load-bearing: **`MoveSizeStart` and `MoveSizeEnd` are delivered
as a pair.** A drag-to-snap module puts an overlay on screen at start and takes it down at end; an
overlay whose end event was dropped stays on the user's screen forever, which is precisely the
"makes the desktop worse" failure this project treats as unacceptable. The high-frequency `Moved`
events *inside* a drag are throttled and coalesced without apology.

**Where display-topology changes land is decided, and it is not here.** A monitor being added,
removed, rescaled, or reconfigured is a change to *desktop truth*, so it belongs to
[Atlas](ATLAS.md), which turns it into a topology-generation bump and republishes. Conduit's job
stops at delivering the notification; interpreting it is Atlas's. This split is written down because
[DOC_SPEC §1](DOC_SPEC.md) names monitor-change handling as one of the two concerns most likely to
end up with three owners. *(Open: whether display-topology notifications ride the window-event intent
or earn their own kind — §9.)*

### 3.3 Schedule

Three shapes: a fixed interval, a wall-clock time of day, and a one-shot at an instant. Two
policies make them survivable on a real machine:

- **Drift policy** — `FixedRate` (the *n*-th fire is at `start + n·interval`, so a late fire does not
  push its successors) or `FixedDelay` (the next fire is measured from the end of the last handler).
  A pomodoro wants fixed rate; a polling loop wants fixed delay. Getting this wrong is invisible for
  an hour and obvious after eight.
- **Missed-fire policy** — `Skip`, `FireOnce`, or a bounded `FireAll`, applied when the machine was
  asleep or the process was not running across a scheduled instant. There is no correct universal
  answer; there is only a declared one.

**Interval schedules run on a monotonic clock; wall-clock schedules run on local civil time**, and
they behave differently on purpose. A 25-minute timer must not become 85 minutes because the clock
jumped an hour. A 07:00 reminder must still be at 07:00 after that same jump. A wall-clock schedule
must therefore also define what happens on the day a local time occurs *twice* and the day it does
not occur *at all*.

Every sentence in this subsection is arithmetic over injected clocks, which means every one of them
is a unit test that runs on any machine. That is the Core/Shell split (§6) paying for itself in the
place it is least expected.

### 3.4 Tray / menu action

There is **one tray icon and one tray menu**, owned by the host. Modules contribute items to it;
they do not each get an icon. A toolbox that installs six tray icons has stopped being one thing.
Items are declared, not drawn: a label, a capability id, and optionally a provider for enabled or
checked state that Conduit calls when the menu is opening — never on a timer.

Menu invocations are the one intent kind that legitimately runs on the UI thread, because the work
they start is usually UI. The blocking rule still applies (§5): the handler may open a window; it
may not do disk or network work inline.

### 3.5 Input gesture

The motivating case is drag-with-modifier: *while a window is being dragged and Shift is held, show
the zone overlay; on release, snap.* This cannot be a chord (there is no key-down moment that means
it) and cannot be a window event (the modifier state is not part of one), so it is its own kind.

A gesture intent supplies a **recognizer spec** — a declarative condition over states Conduit
already tracks — and receives `Started`, throttled `Updated`, and exactly one `Ended`, carrying
`Committed` or `Cancelled`. Cancellation is a first-class outcome with real sources: Escape, the
drag ending outside any target, focus loss, session lock, or the recognizer being revoked mid-drag.

**`Ended` always follows `Started`.** If Conduit cannot determine the real outcome, it synthesizes a
`Cancelled` end rather than leaving the module hanging. This is the same reasoning as §3.2's paired
move/size events, and it is worth restating because it is the guarantee a gesture consumer will
build its cleanup on.

### 3.6 Pointer gesture

The motivating case is Zones' stack cycling: *the wheel moved, with a modifier held, over one of
these rectangles.* It is not §3.5 — that kind is a **span** whose guarantees exist so an overlay put
up at `Started` is always taken down, and a wheel tick is **discrete**, with nothing to clean up.
Forcing it into a span would mean synthesising lifecycle events with no referent. Full reasoning and
the §7 checklist: [ADR 0013](decisions/0013-the-pointer-gesture-trigger-kind.md).

**The rule that makes this kind safe, and the reason it is written here rather than in a module:**

> **A pointer-gesture recognizer must be answerable from data Conduit already holds.** The decision
> to swallow or pass through happens on the hook thread, on every wheel event the machine
> processes — including the one scrolling this page. Asking a module would put arbitrary code on the
> critical path of every scroll on the desktop, which is the failure this pillar exists to prevent.

So a module supplies **pre-resolved rectangles** in
[`PhysicalVirtualScreen`](ATLAS.md#51-the-spaces) space and republishes them when they change. The
hook does an early-out on the modifier, then a bounded rectangle test, then swallow-or-pass. The
dispatch runs on a worker; the hook's whole job is *test, decide, queue*.

**Conflicts are geometric, not modifier-wide.** Two intents collide only when their modifier matches
**and** their regions intersect — two modules arming disjoint regions with the same modifier is the
normal case, not a conflict. Refusals: `RegionsOverlapAnotherOwner`, `ModifierReserved`,
`TooManyRegions`.

**Fail open, always.** Empty region set, unknown modifier state, saturated queue — pass the event
through untouched. A dropped cycle tick is cosmetic; a swallowed scroll is a desktop that feels
broken, and the user cannot tell which component did it.

**Staleness is bounded by the topology generation.** An armed region set carries the Atlas generation
it was computed at, so Conduit can drop a provably-stale set rather than acting on rectangles that
no longer describe any monitor.

---

## 4. Arbitration — registration is a request that can be refused

**A registration is a request, and the answer is a value.** This is the single most important shape
in the pillar. There is no method that "installs a hotkey"; there is a method that returns what
happened.

```csharp
// SKETCH — not compiled. See §8.
public abstract record TriggerRegistration
{
    public sealed record Granted(TriggerLease Lease)              : TriggerRegistration;
    public sealed record Refused(RefusalReason Reason, string? HeldBy) : TriggerRegistration;
}

public enum RefusalReason
{
    AlreadyHeldByAnotherModule,  // another module won this chord — HeldBy names it
    HeldOutsideThisApplication,  // the OS or another application holds it
    ReservedBySystem,            // e.g. Win+L — the OS will never yield it
    Malformed,                   // a global chord with no modifier; a chord with no key
    DisabledByUser,              // the user turned this binding off in the Shell
    ResourceExhausted,           // a bounded table is full
}
```

Three properties follow, and each one is a rule rather than an implementation detail.

**A refusal is never a silent no-op.** It is returned to the module, recorded against the module in
the registry, and shown in the Shell next to the binding that lost, naming the winner. The failure
mode this forbids — a feature that is installed, enabled, documented, and simply does not happen —
is the worst outcome available to a utility, because the user has no way to distinguish it from a
bug in their own understanding.

**The winner is deterministic across restarts.** Arbitration must never depend on module load
timing, because a chord that works on Tuesday and not Wednesday is unfalsifiable and unreportable.
The ladder:

| Order | Rule | Notes |
|---|---|---|
| 0 | **Reserved system chords are refused outright** | The OS will not yield them; refusing at registration turns a mystery into a message |
| 1 | **An explicit user binding wins** | Always, over any module default. At most one module per chord; a settings file containing two is rejected at load with a surfaced error, not silently resolved |
| 2 | **Module defaults, ordered by stable module id** | Not by load order, not by discovery order — by the permanent id from the registry, so the same set of modules always produces the same winner |

**A grant can be revoked.** The user rebinding a chord to a different module, or a session change
forcing re-registration, changes who holds what while the process is running. So a grant is a
**lease**, not a fact: it carries its current state and notifies its holder when that state changes.
A module that was told "granted" once and never told otherwise would eventually be wrong, and being
wrong quietly is the thing this project's evidence standard exists to prevent.

**Refusal is not fatal.** A module whose intent was refused keeps running with reduced function;
this is the "Trigger registration" row of the host lifecycle table in
[COORDINATOR.md §6](COORDINATOR.md). Only the module knows whether one refused chord makes it
useless, so only the module gets to decide.

---

## 5. The dispatch contract — and the constraint everything bends around

### 5.1 The hard constraint

> **A low-level input hook runs on the desktop's critical path. While it runs, the keystroke or
> mouse event it is inspecting has not yet been delivered to the application the user is typing
> into. A handler that blocks does not slow down Windows Coordinator — it stalls every application
> on the machine.**

That is the whole reason this pillar has a threading section at all. Two further facts make it
worse rather than better: Windows applies a timeout to low-level hooks and **silently removes** a
hook that exceeds it — so the punishment for being slow is that input silently stops working, with
no exception and no log — and the timeout's default has varied across Windows versions, which means
the only safe posture is to stay orders of magnitude under any plausible value rather than to budget
against a number.

### 5.2 What a hook callback is allowed to do

Exactly one thing: **classify**. Match the event against a table that was compiled before the
callback ever ran, decide *mine* or *not mine*, enqueue a small value if mine, and return.

Forbidden inside the callback, without exception: allocation, any lock another thread can hold
across I/O, disk or registry access, network access, logging to a file, settings reads, UI or COM
calls, anything that can throw a first-chance exception on a hot path, and any call whose worst case
is unbounded. If a candidate operation's *worst* case is not known, it is not allowed — the average
case is irrelevant when the tail is a machine-wide stall.

This is [principle 7 — *resolve once, execute cheap*](COORDINATOR.md#7-non-negotiable-principles)
made concrete. The table the callback consults is built at registration and rebuilt on settings save,
both of which happen on a worker where doing real work is free. Nothing structural is permitted to happen on the input path;
the input path only reads what was already decided.

**Principle 8 — *never block the hook or UI thread on I/O*** — is the same rule stated from the
other side, and it extends past the hook to the module handler.

### 5.3 The hand-off

| Stage | Thread | Bounded? | On overload |
|---|---|---|---|
| Recognize | the hook / OS callback | yes — table lookup + enqueue | drop, and count the drop |
| Queue | — | yes — fixed capacity, per-intent coalescing | drop the *oldest coalescible* item; never grow, never block the producer |
| Dispatch | a dispatch worker (UI thread only for tray/menu items) | no | the module's own problem, by design |
| Handle | the module's handler | no | overruns counted, surfaced, and eventually fault the module |

**Dispatch never happens on the hook thread.** A module that does something slow in a handler makes
*itself* sluggish and cannot make the desktop sluggish — that is the containment property the whole
design buys, and it is stated once here and cross-linked from
[COORDINATOR.md §6](COORDINATOR.md) rather than restated there.

**A module never sees two concurrent dispatches of the same intent.** Serializing per intent means a
handler that is still running when its trigger fires again gets the second event coalesced or
dropped, not re-entered. Re-entrancy in a hotkey handler is a bug factory, and it is cheaper to
forbid it in the fabric than to document it in every module.

**Overrun is measured, not assumed.** A handler that exceeds its budget is counted against its
module; sustained overruns disable the module rather than let it degrade the input path, which is
the "Dispatch" row of [COORDINATOR.md §6](COORDINATOR.md).

### 5.4 Proving the guard, not asserting it

[OPERATING_MODEL §7](OPERATING_MODEL.md)'s operational rule — *when you add a guard, prove it fails
without the fix* — applies to every budget in this section, and the shape of the proof is decided in
advance so it does not get negotiated later:

- The overrun detector gets a Core test that runs a deliberately slow fake handler and requires the
  counter to move and the module to be disabled. Then the same test is run against a build with the
  detector removed, and it must go red. A budget check that has never been observed to fail is
  indistinguishable from a comment.
- The queue's drop-and-count path gets a test that fills the queue and asserts the drop count,
  because a queue that silently grows under load looks identical to a healthy one right up until the
  machine is out of memory.
- **Latency itself cannot be tested this way**, and pretending otherwise would be the exact failure
  §7 names. Actual hook latency is a [manual-validation](runbooks/manual-validation.md) row, measured
  on a real desktop, recorded with a date and a machine. No Core test result may ever be described as evidence about it.

---

## 6. The Core/Shell split, applied here

Conduit is two projects, per [COORDINATOR.md §3](COORDINATOR.md) and ADR 0003.

| | `Coordinator.Conduit.Core` | `Coordinator.Conduit.Shell` |
|---|---|---|
| Target | `net9.0`, zero Windows dependencies | `net9.0-windows…`, all of them |
| Owns | the intent model · the chord grammar · the registry · **the arbiter** · refusal taxonomy · lease lifecycle · the schedule/drift/missed-fire arithmetic · the queue and coalescing policy · the recognizer state machines | hotkey registration · low-level hooks · the window-event source · the timer plumbing · the tray icon and menu · thread ownership |
| Decides | everything | nothing |
| Verified by | unit tests, on any OS | [manual-validation](runbooks/manual-validation.md), on a real desktop |

The Shell adapter's job is to **collect facts, hand them to Core, and carry out Core's answer**. A
real hotkey registration failure becomes a `RefusalReason` before anything decides what it means. A
raw key event becomes a normalized chord before anything matches it. A tick becomes a monotonic
timestamp before any schedule reasons about it. If an `if` appears in the Shell adapter that is not a
null check or an error check, the decision belongs in Core.

**What that buys, concretely.** The scenario this pillar exists for — two modules wanting the same
chord — is an assertion on a value returned by a pure function, running on Linux, in a container with
no monitor and no Windows API:

```csharp
// SKETCH — not compiled. See §8.
var first  = registry.Register(zonesIntent);      // Granted
var second = registry.Register(chronoIntent);     // same chord
Assert.IsType<TriggerRegistration.Refused>(second);
Assert.Equal(RefusalReason.AlreadyHeldByAnotherModule, ((Refused)second).Reason);
Assert.Equal("zones", ((Refused)second).HeldBy);
```

So is the ladder in §4, the DST case in §3.3, the sleep-resume case, the missed-fire policies, chord
normalization, queue coalescing, and lease revocation. That is most of the interesting surface of
the pillar, and none of it requires a desktop.

**And the honest other half.** A green Core run proves none of the following: that a chord actually
fires; that the OS granted the registration; that a hook callback returns fast enough on a loaded
machine; that the tray icon appears; that gesture events arrive in the right order during a real
drag; that anything survives a session lock, a fast-user-switch, or a UAC prompt. Those are
[manual-validation](runbooks/manual-validation.md) rows and nothing else can stand in for them.

---

## 7. Adding a trigger kind — the extension contract

The five kinds in §3 exist because a real consumer needed each one. A sixth needs the same
justification. This section is the checklist for adding one: the point is that the fabric stays small
and the modules stay ignorant of mechanism.

**The first test is whether it is a new kind at all.** If the need can be expressed as a *filter or a
parameter* on an existing kind, it is not a new kind. A chord that should only fire while a specific
application has focus is a scope parameter on the hotkey intent, not a new taxonomy entry. Keeping
the vocabulary small is the point — a wide taxonomy is a wide surface every module must understand
and every future arbitration rule must cover.

**What a new kind must supply, before any code:**

| Required | Why |
|---|---|
| The intent record — exactly what a module declares | It is a permanent contract; settings files will reference it |
| Its **refusal reasons** | A kind with no way to be refused is a kind that fails silently |
| Its **conflict rule** — what "two modules want the same thing" means here | Arbitration cannot be generic; only the kind knows what collides |
| Its **dispatch class** — hook, timer, or UI | This decides which budget in §5 applies |
| Its **guarantee statement** — delivery, ordering, coalescing, cancellation, and what is explicitly *not* guaranteed | §3's rows are the template; the absent guarantees matter more than the present ones |
| A Core model driven by a **fake source**, so the kind is testable with no desktop | Otherwise the kind is unverifiable forever |
| A row in [manual-validation](runbooks/manual-validation.md) | Everything Core cannot prove has to be provable by a human once |

**Do**

- Express the intent in terms of *what the module wants to be woken for*, never the mechanism.
- Keep every mechanism specific detail inside the Shell adapter; Core must not know the kind is
  served by a hook rather than a timer.
- Make the payload carry a capability id and pre-resolved values — never a raw handle or key code a
  module would have to interpret.
- Write the guarantee down as the weakest true statement, then hold it.

**Don't**

- Don't add a kind for a consumer that does not exist yet. [OPERATING_MODEL §3](OPERATING_MODEL.md):
  capture is free, building is not.
- Don't let a mechanism name leak above the Shell adapter — no `if (source == LowLevelHook)` in Core
  and certainly not in a module.
- Don't add a kind that can only be dispatched on the hook thread. If the work cannot be deferred,
  the design is wrong, not the constraint.
- Don't promise ordering or completeness you have not proven you can deliver under load.

---

## 8. Status — designed and documented, not built

**No Conduit code exists.** There is no project, no namespace, no interface, no test. What exists is
this document and [`src/pillars/conduit/README.md`](../src/pillars/conduit/README.md).

Two separate honesty statements, both required whenever this pillar's status is described:

1. **Nothing here has been compiled.** The environment this bootstrap was authored in had Python 3.11
   and Node and **no .NET SDK**. The sketches on this page have never been through a compiler and
   should be read as notation, not as code. The Python tooling (`tools/coord/coord.py`,
   `tools/doc-audit/audit.py`) *has* been executed and its results are real; nothing C#-shaped in
   this repository shares that status.
2. **Nothing here has been measured.** Every latency budget, every guarantee, every "always" and
   "never" in §3 through §5 is a specification the implementation will be held to — not a
   description of observed behavior. The gap closes in the order the roadmap says, and it closes
   with recorded evidence: Core tests for the decidable half, a
   [manual-validation](runbooks/manual-validation.md) pass for the rest.

**Where it sits in the plan.** [COORDINATOR.md §8](COORDINATOR.md) puts Conduit in **P2 — Conduit
and Atlas, minimum viable**, gated on Core tests covering arbitration (including the
two-modules-one-chord case) plus a manual run on Windows recording a real chord firing and a real
schedule firing. P2 is downstream of P1, whose first task is restoring the toolchain and compiling
anything at all. The live task list is [NEXT.md](NEXT.md); the resume instructions for this pillar
specifically are in its [README](../src/pillars/conduit/README.md).

---

## 9. Open questions and known dragons

Written down so they ambush nobody, and so each one has somewhere to come back to.

- **Display-topology notifications: window-event intent, or their own kind?** §3.2 decides the
  *ownership* (Atlas interprets, Conduit delivers) but not the *shape*. Decide when Atlas's
  invalidation path is built, not before — the answer depends on what that path actually needs.
- **UIPI is a hard ceiling.** An unelevated process cannot receive input directed at an elevated
  window. Hotkeys will not fire while an elevated application has focus, and no amount of
  cleverness changes that. It must be documented as a limitation and surfaced when detected, because
  the alternative is a user concluding the feature is broken.
- **The secure desktop swallows everything.** During a UAC prompt, the lock screen, or
  Ctrl+Alt+Del, hooks and hotkeys are dead. The gesture contract's "`Ended` always follows
  `Started`" (§3.5) has to survive this, which means a synthesized cancel on session-state change.
- **Session change and fast user switching** invalidate registrations. Re-registration is required,
  and re-registration can *fail differently than it did the first time* — so leases (§4) must be
  able to move from granted to refused while the process is running.
- **The reserved-chord list is version-dependent.** A static table would be wrong on some Windows
  build. The honest design is to ask the OS at registration and believe the answer, keeping a small
  static list only to warn the user *before* they pick something that will not work.
- **Rate limits are unmeasurable from here.** The throttle values for `Moved` and gesture `Updated`
  events cannot be chosen from first principles; they are a manual-validation output, measured on a
  real desktop under real input load — the same way the hook-latency budget in §5.4 can only be
  measured, never derived. Ship a conservative value, then measure.

Anything that hardens into a decision becomes an ADR in [`docs/decisions/`](decisions/); anything
still speculative belongs in [INBOX.md](INBOX.md) with a recall hook, per
[OPERATING_MODEL §3](OPERATING_MODEL.md).

---

## See also

- [COORDINATOR.md](COORDINATOR.md) — the platform architecture, the principle list, the roadmap, and
  the host lifecycle table this pillar's refusals and faults plug into.
- [ATLAS.md](ATLAS.md) — the other pillar. Conduit says *something happened*; Atlas says *here is
  what the desktop is*. Almost every window-event consumer uses both.
- [MODULE_SPEC.md](MODULE_SPEC.md) — how a module declares intents and receives dispatches.
- [OPERATING_MODEL.md](OPERATING_MODEL.md) — why arbitration is in the build-now set (§3), why the
  desktop must never get worse (§6), and the evidence standard (§7).
- [`src/pillars/conduit/README.md`](../src/pillars/conduit/README.md) — the code front door, the
  intended layout, and **where to resume**.
- [runbooks/manual-validation.md](runbooks/manual-validation.md) — the human-executed pass that is
  the only thing which can validate anything in §5.
