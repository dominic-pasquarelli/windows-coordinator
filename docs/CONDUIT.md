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
means the two pointer-driven kinds — gestures (§3.5) and pointer gestures (§3.6) — and nothing else.
Revisit when a real intent arrives that needs more.

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
**and** their regions intersect — two modules requesting disjoint regions with the same modifier is
the normal case, not a conflict. A collision is **arbitrated by priority, not refused** (§3.6.1);
the refusals are `ModifierReserved` and `TooManyRegions`, which are malformed and over-quota requests
rather than contention.

**Fail open, always.** Empty region set, unknown modifier state, saturated queue — pass the event
through untouched. A dropped cycle tick is cosmetic; a swallowed scroll is a desktop that feels
broken, and the user cannot tell which component did it.

**Staleness is bounded by the topology generation.** An armed region set carries the Atlas generation
it was computed at, so Conduit can drop a provably-stale set rather than acting on rectangles that
no longer describe any monitor.

**Publication is an atomic swap of an immutable set, and this is a hard requirement rather than an
implementation note.** A module computes a region set on a worker thread; the hook thread reads it on
every wheel event. Those are different threads, and the naive shape — a mutable collection the module
edits in place while the hook walks it — is a data race on the input path of the whole desktop, which
is the worst place in this system to have one.

So the contract is:

- A region set is **immutable once published.** A module that wants different regions builds a new
  set and publishes that; it never edits a published one.
- Publication **replaces the current set in a single atomic reference swap.** The hook thread reads
  the reference once per event and works with whatever set it got — a set that was current a
  microsecond ago is a perfectly good answer, and a torn read is not.
- **Conduit owns the published set's lifetime**, not the module. A module that unregisters, or is
  unloaded mid-drain, must not be able to free memory the hook is reading. The last set stays alive
  until Conduit is certain no reader holds it.
- **Unregistration is not immediate disarmament.** It stops future dispatches; a swallow decision
  already in flight completes. A module must therefore tolerate one dispatch arriving after it asked
  to stop, which is cheaper for everyone than making the hook thread synchronise with a module's
  shutdown.

*(Recorded because the shape is a known trap rather than a hypothetical: a borrowed pointer read
concurrently by another task, with no ownership rule, no lifetime guarantee, and no protection
against the owner detaching mid-read. The first draft of this kind specified staleness and forgot
the swap entirely.)*

**Updating a live region set is its own operation, and it can be refused.** A module republishes
constantly — every layout change, every stack that crosses depth two. So:

| Question | Answer |
|---|---|
| A publication overlaps **any** other owner | **Accepted.** Contention is arbitrated, not refused. The request is recorded whole; the **grant** is whatever arbitration awards, and the result reports it explicitly |
| Is a grant ever partial | **Yes** — and it is always *reported*. What is forbidden is silent trimming, not partial granting: a module must never have to infer what it holds |
| What can still refuse a whole publication | `ModifierReserved` and `TooManyRegions` — malformed or over-quota requests, which are errors rather than contention |
| Who wins a contested rectangle | **Explicit user priority, then stable module id** — see below. Never "whoever got there first" |
| How an owner loses a region | By reducing its own request, by unregistering, **or by arbitration awarding it to a higher-priority requester** |
| How an owner **regains** one | **Automatically**, when the higher-priority requester withdraws, unregisters or loses priority. The module does not re-publish and must not — see §3.6.1 |
| Can **withdrawing** be refused | **Never.** Publishing a set that adds nothing you did not already request, or the empty set, always succeeds |
| Where the topology generation comes from | **Atlas**, carried on the set by the publishing module, which got it from the snapshot it computed against. Conduit compares it with the generation it last observed from Atlas |

#### Stable priority — why "earlier registration wins" is not good enough

Registration order is a property of **how the host happened to load modules this run**: it changes
when a module is disabled, when one fails to load and is retried, when the registry is reordered, or
when loading is parallelised later. An arbitration rule built on it produces a different winner on
different runs of the same configuration, and the loser has no way to find out why. That is the same
class of defect as an unstable sort — invisible until it matters, then impossible to reason about.

The order is:

1. **Explicit user priority.** A per-module integer in platform settings, default 0, higher wins.
   This is the only knob, it is visible in the Shell, and it exists so an overlap the user cares about
   has an answer the *user* chose.
2. **Stable module identity.** Ties break on the module's permanent string id, ordinal comparison.
   Arbitrary, and *deterministic across runs, machines and load orders*, which is the property that
   matters. Nothing here depends on when anything registered.

#### A region grant is a revocable lease, because the alternative smuggles registration order back in

**Stable priority and "the incumbent always keeps it" cannot both hold.** If a lower-priority module
keeps a contested rectangle merely because it published first, then the winner is still decided by who
arrived first — the priority order is decoration, and the arbitration rule is the very thing it
claimed to replace, one level down. *An earlier draft of this section asserted both, and this
paragraph is the retraction.*

So a grant is a **lease**, in the sense the [Core/Shell table](#6-the-coreshell-split-applied-here)
already gives Conduit, and preemption is real.

### 3.6.1 Requested and granted are two different values

A lease that is only ever *taken* has the same defect one level further on, and it took a second
review to see it. If Conduit forgets what a preempted module asked for, then when the winner later
withdraws nothing brings the region back — and the final armed map depends on the sequence of events
rather than on the current state. So Conduit keeps **two values per owner**
([ADR 0021](decisions/0021-requested-versus-granted-regions.md)):

```csharp
// SKETCH — illustrative, not compiled.
sealed record RegionOwner(
    ModuleId Module,
    int Priority,                 // explicit user setting; ties break on ModuleId
    ArmedRegionSet Requested,     // the module's standing desire — changes only when it publishes
    ArmedRegionSet Granted,       // Conduit's current answer — changes when anything changes
    int GrantVersion);            // bumped on EVERY change to Granted
```

**Grants are recomputed in full, never patched:**

```
grants = arbitrate(every owner's Requested, priority order)
```

— re-run whenever a module publishes, a module registers or unregisters, or **a priority setting
changes**. No previous grant map is an input, and arrival order appears nowhere in the computation.

**Recomputation is serialized**, for the same reason publication is
([ADR 0022](decisions/0022-one-publication-sequencer-for-desktop-facts.md)): two overlapping
recomputations could each read the request set, arbitrate, and swap, with the loser's older result
landing last. Since a recomputation reads all requests at execution time, concurrent triggers coalesce
into one run — the same property, for the same reason. It happens on registration, settings-save and
unregistration, never on the input path.

**Every change to `Granted` bumps `GrantVersion` and emits one control-plane message:**

```csharp
// SKETCH — illustrative, not compiled.
sealed record GrantChanged(ArmedRegionSet Granted, int GrantVersion);
```

**Absolute state, not a delta** ([ADR 0023](decisions/0023-the-control-plane-carries-state-not-deltas.md)).
The obvious design is a `RegionsRevoked` / `RegionsRestored` pair, and it is wrong here: deltas are
correct only if *every* message is delivered in order, and §5.3's event-plane queue promises neither.
A dropped restore leaves a module showing a zone as unavailable **forever** — nothing retries, because
a module must not re-request — and a revoke arriving after a restore produces the same wrong end state.
One absolute message removes both failures: the consumer **adopts the set**, which is idempotent and
order-insensitive.

Delivery is the **control plane**: serial per owner, latest-state coalescing, **the final state is
never dropped**. Under pressure a pending update is *replaced* by the newer one, so the per-owner
depth is effectively one and the survivor is always the most complete.

- **A version gap is normal, not an error.** A module may see `GrantVersion` go 5 → 9 because 6–8 were
  superseded. Stated plainly because the alternative is an implementer writing a gap-detected-resync
  loop that fires hardest under exactly the load it was meant to help.
- **A module ignores a version it has already passed** (`≤` the last applied). Cheap, local, and it
  makes the module correct independently of a delivery guarantee it cannot verify.
- **There is a current-grant read** — `QueryGrant(module) -> (Granted, GrantVersion)` — for
  **recovery**: a handler that faulted, or a module re-initialising, resynchronizes in one call rather
  than waiting for an arbitration change that may never come. Not for routine gap-filling.

#### One path in, and the publication result uses it

```csharp
// SKETCH — illustrative, not compiled.
(ArmedRegionSet Granted, int GrantVersion) Publish(ArmedRegionSet requested);

void ApplyGrant(ArmedRegionSet granted, int version);   // the ONLY way grant state changes
```

**`Publish` returns a versioned grant, and that result goes through the same `ApplyGrant` as every
`GrantChanged`** ([ADR 0024](decisions/0024-grantversion-is-the-single-authoritative-version.md)). There
is deliberately no separate publication-result path.

*This is not symmetry for its own sake.* An unversioned result is a second writer to the same state
with no guard, so an in-flight result for grant v1 can land **after** a `GrantChanged` for v2 and
overwrite it — leaving the module acting on a grant that has already been superseded, with nothing to
detect it. Two paths mutating one state where only one is guarded is the bug; one guarded path is the
fix, and it is smaller than guarding the second path carefully.

**The version bump on *restoration* is as load-bearing as the one on revocation:** a gesture recognized
under the old lease and still queued must not execute against an arbitration state that has since
changed, and "changed back" is still changed.

**A module never re-publishes to regain a region**, and must not try. Its request never went away;
restoration is Conduit's job. A module that re-requests on revocation is fighting the user's own
priority setting, and it cannot win.

**Now the property is actually true:** `grants = f(requests, priorities)`, with history nowhere in it.
Publish order changes which notifications fire, never which module ends up holding what — including
across a full preempt-then-withdraw cycle, which is the case the previous design got wrong.
[§5.4](#54-proving-the-guard-not-asserting-it) requires the permutation test to include exactly that
cycle.

The cost is honest, and it is two things. Conduit now stores rectangles a module is **not** currently
granted, bounded by the same per-module cap that bounds the hook test. And a module must **adopt a
grant set** rather than react to a change — which is less work than handling two delta events, and is
the shape that survives a message being coalesced away. Zones' side is
[ARCHITECTURE §7.4](../src/modules/zones/docs/ARCHITECTURE.md#74-losing-and-regaining-a-region).

#### Withdrawal always succeeds

Arming is a request that arbitration answers. **Disarming is not a request at all** — a module may
always publish a set that adds no rectangle it did not already request, and the empty set is always
accepted. Without this rule a module can get stuck holding regions it has decided are wrong, with no
safe state to fall back to.

It is also what keeps §3.6.1's recomputation total: shrinking a request can never fail, so a module
withdrawing is always able to complete, and the grant map that follows is always computable.

**With contention arbitrated rather than refused, publishing is one step.** A module publishes what it
wants and is told what it was granted; if part is withheld, the result says which rectangles and the
module reports that surface as unavailable. There is no retry loop to bound and no question of how
many attempts to make — *an earlier draft specified a two-step subtraction retry, which existed only
to work around contention being a refusal.* The consumer's side is
[Zones ARCHITECTURE §7.3](../src/modules/zones/docs/ARCHITECTURE.md#73-applying-an-edit).

#### The queued event carries a token, not coordinates

A dispatch carries the **opaque zone token** that matched and the **`GrantVersion`** it matched under.
On delivery the module executes only when that version **exactly equals** the grant version it has
applied, and drops the event otherwise. Without this, a change between recognition and dispatch cycles
*a different zone than the one the user pointed at*, which is both wrong and untraceable.

**The version is `GrantVersion` and nothing else** ([ADR 0024](decisions/0024-grantversion-is-the-single-authoritative-version.md)).
*An earlier draft stamped the module's **requested**-set version, which was the same value back when a
module's published set was the set the hook tested. Once §3.6.1 split requested from granted, they
stopped being interchangeable — a requested-set version sits unchanged while `GrantVersion` moves
through lease epochs, because arbitration changes without the module publishing anything.* That let a
tick recognized at grant v1 survive a preempt (v2) and a restore (v3) and still pass its guard, because
the guard was checking the one value that had not changed.

**Exact equality, not `>=`.** An *older* version means the event was recognized under a lease epoch
that has been replaced. A *newer* one means Conduit has swapped the hook table but the module has not
yet applied that grant — so acting would mean acting on a state the module has not adopted. Both drop.
This can lose a tick in the narrow window around an arbitration change, which is consistent with what
this kind guarantees: delivery was never promised, and a dropped cycle tick is cosmetic where a tick
executed against the wrong epoch is not.

The **zone token stays**, because it answers *which zone* and `GrantVersion` does not. The two answer
different questions.

**The cursor position is still present — as context, never as an address.** §5.5's
`InvocationContext` carries the cursor captured at recognition (a `Hook` origin reads it from the
event structure, which already holds it). The distinction is what each is *for*: the token answers
**which zone**, and it is the only thing permitted to; the cursor answers *where the pointer was*, for
a module that wants to position an overlay or log a diagnostic. A module that re-derives a zone by
hit-testing the cursor has reintroduced exactly the staleness the token exists to eliminate.

*(This reconciles the guarantee statement in
[ADR 0013](decisions/0013-the-pointer-gesture-trigger-kind.md), which as first written listed the
cursor position as the payload.)*

**Coalescing key: `(intent, zone token)`.** Ticks for the same zone coalesce and their deltas sum;
ticks for different zones never coalesce with each other.

**The swallow happens only after the bounded queue has accepted the event.** The order is: test →
**try-enqueue** → if enqueued, swallow; if not, pass through. This is what makes fail-open real
rather than aspirational — a saturated queue produces a scroll that works, not a scroll that
vanishes.

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
| Recognize | the hook / OS callback | yes — table lookup + **context capture** (§5.5) + enqueue | drop, and count the drop |
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

#### Two dispatch classes, with opposite guarantees

Everything above describes the **event plane**, and its drop policy is right for it: a wheel tick
that never arrives is a cosmetic loss, and buffering on the hook path would be worse than the loss.

That reasoning does **not** transfer to a message that says *what the world currently is*. Conduit
carries those too — the grant updates in §3.6.1 — and a dropped one desynchronizes a module
permanently, because there is nothing to retry and no later event that repairs it
([ADR 0023](decisions/0023-the-control-plane-carries-state-not-deltas.md)):

| | **Event plane** | **Control plane** |
|---|---|---|
| Carries | something happened — a tick, a chord, a gesture | what the world **is** — the current grant |
| Under overload | **drop the oldest coalescible**, and count the drop | **never drop the final state**; replace pending with the newer |
| Ordering | none across kinds | **serial per owner** |
| Payload | a delta — this happened | **absolute state** — this is how things are |
| A lost message costs | a cosmetic miss | **permanent desynchronization** |

**The payload row is what makes the guarantee affordable.** A delta is correct only if every message
arrives in order; an absolute snapshot is correct if **the last one** arrives — which is a promise a
bounded queue can keep, and it makes a coalesced-away intermediate harmless instead of corrupting.

*This distinction was implicit and wrong: these messages were specified as "ordinary dispatches" and
were therefore droppable by a policy whose correctness argument never covered them.*

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
- **The publisher-liveness check (§5.5) gets tests in both directions, and the second one is the
  point.** A fake clock advances well past the heartbeat interval *with the publisher heartbeating*
  and the context must **not** be `ContextStale` — that is the assertion the rejected age-threshold
  design would fail, and without it nothing distinguishes a liveness check from the age check it
  replaced. Then the publisher stops and the same elapsed time must produce `ContextStale`.
- **The heartbeat's repair path gets a test that suppresses an event**, because a self-healing
  mechanism that is never observed healing is indistinguishable from one that does not work. Drive a
  fake desktop source: change the foreground **with its change notification suppressed**, assert the
  published record is now wrong, advance exactly one heartbeat, and assert the published foreground
  **matches reality** and the missed-notification counter moved. Run the same test against a build
  whose heartbeat republishes the previous record unchanged — the shape the first draft specified —
  and it must go red.
- **Arbitration determinism (§3.6) is tested by permutation, not by example**, and the permutation
  must include a **full lease cycle**: low priority requests a region · high priority preempts it ·
  high priority withdraws · low priority **regains it automatically**. Then the same operations in
  every other order, all ending in the identical armed map. A permutation test without the withdraw
  step passes under the design [ADR 0021](decisions/0021-requested-versus-granted-regions.md)
  replaced, because that design's defect only appears once a winner leaves.
- **Publication ordering (§5.5) gets a deterministic race, driven by an injected schedule rather than
  by timing.** Hold the sequencer after a heartbeat request is enqueued, deliver a foreground change
  that publishes at sequence *n*, release the sequencer, and assert three things: the final record is
  the **new** foreground, `Sequence` never carries an older observation than a lower one, and the
  repair counter **did not** increment — the event reported the change, so nothing was repaired. Run
  it against a build where each path samples then swaps independently and it must go red on the first
  assertion. Racing by real threads and hoping is not a test; the schedule is what makes the failure
  reproducible.
- **Control-plane delivery (§3.6.1) gets a saturation test**, because the guarantee is specifically
  about behaviour *under overload* and is vacuous when nothing is under pressure. Fill the event queue
  so it is dropping, then drive **revoke → restore**, and assert the module eventually observes the
  **restored** grant and never afterwards applies the revoked one. Then assert the same holds when the
  two updates coalesce — the survivor must be the newer, complete state. A version-ignoring consumer
  must fail this test.
- **The `GrantVersion` guard (§3.6, §3.6.1) gets the two sequences it exists for**, both of which pass
  under the design [ADR 0024](decisions/0024-grantversion-is-the-single-authoritative-version.md)
  replaced:
  1. **Stale epoch.** Recognize a pointer event at grant **v1** · preempt to **v2** · restore to
     **v3** · then deliver the v1 event. It must be **dropped**. Run it against a build that guards on
     the module's requested-set version and it must go red — that version never changed, so the event
     executes.
  2. **Out-of-order publication result.** Hold a `Publish` result for **v1**, apply `GrantChanged`
     **v2**, then deliver the v1 result. It must **not** overwrite v2. Run it against a build with a
     separate unguarded publication-result path and it must go red.
- **Latency itself cannot be tested this way**, and pretending otherwise would be the exact failure
  §7 names. Actual hook latency is a [manual-validation](runbooks/manual-validation.md) row, measured
  on a real desktop, recorded with a date and a machine. No Core test result may ever be described as evidence about it.

---

### 5.5 What every dispatch carries — the invocation context

A dispatch says *that* something happened. A module almost always also needs *the state of the world
when it happened*: which window had focus when the chord fired, where the cursor was, which monitor
that was over. Without it, a capability like "snap the focused window" or "cycle the zone under the
cursor" cannot be implemented at all without a module reaching for Windows itself — which
[principle 4](COORDINATOR.md#7-non-negotiable-principles) forbids, and building a focus cache from
§3.2's coalesced hints is worse.

So **every payload carries an `InvocationContext`**.

#### The timing rule

> **The context is captured at recognition — the moment the event is recognized and enqueued — never
> reconstructed at dispatch.**

This is the whole point of the type, and it is worth being blunt about why the obvious alternative
fails. §5.3's hand-off puts **Recognize** on the hook or OS callback and **Dispatch** on a worker,
with a queue in between. A context sampled on the worker describes the world after an unbounded queue
delay, on the far side of exactly the interval during which the user moved the mouse and switched
windows. "Sample it at dispatch" and "give the module the state when it happened" are not compatible
statements; the first draft of this section asserted both.

**Captured, derived, reconstructed — the distinction that makes this workable:**

| | Meaning | Allowed |
|---|---|---|
| **Captured** | Read at recognition, on the recognizing thread, into the payload | Yes — this is the mechanism |
| **Derived** | A pure function of already-captured facts, computed later | Yes. Same answer whenever it runs, so *when* is irrelevant |
| **Reconstructed** | A **live** source read on the worker, presented as event-time truth | **No.** This is the failure the rule exists to prevent |

`MonitorUnderCursor` is *derived*: a rectangle test of a captured cursor point against the monitor
list at a captured generation. Computing it on the worker keeps a loop off the hook thread and
changes no answer. Reading `GetForegroundWindow()` on the worker would be *reconstruction*, and is
forbidden however convenient the value looks.

#### What each source may capture

Recognition happens on different threads with different budgets, so what is capturable differs by
source. The context names its own origin so a module can tell which guarantees it has:

| Origin | Recognized on | Captures | Notes |
|---|---|---|---|
| **Hook** — pointer gesture (§3.6), input gesture (§3.5) | the low-level hook thread, under §5.1's budget | cursor and timestamp **from the event structure itself**; everything else from the **atomically-published desktop facts** — one reference read | **May not call Atlas, or anything else.** §5.2's forbidden list is not relaxed for context capture |
| **OS callback** — **hotkey chord (§3.1)**, window event (§3.2) | a message-loop or callback thread, with no microsecond budget | a live Atlas point sample at recognition | The origin where "sample now" is both allowed and accurate |
| **UI** — tray action, menu item | the UI thread | a live point sample, plus the invoking menu item | Cursor is where the user clicked the menu, which is what they mean |
| **Timer** — schedule | a timer thread | **no cursor and no foreground at all** | A 25-minute tick has no event-time cursor. The fields are null and `Origin` says why — not a fabricated "wherever the mouse happens to be" |

**`Hook` is exactly the two pointer-driven kinds, and that is not an arbitrary grouping — it is what
makes the row above true.** §3.1's mechanism decision means plain chords are **kernel registrations,
not hooks**: they arrive as `WM_HOTKEY` on a message loop, where a live point sample is both permitted
and correct. The two pointer kinds are the only hook-recognized intents Conduit has, they are both
**mouse**-driven, and a mouse hook's event structure carries the cursor. So "the cursor comes from the
event structure" holds for every `Hook` context by construction rather than by luck.

> **The trip-wire, recorded because §3.1 invites the revisit.** If a future intent ever needs a
> low-level **keyboard** hook, it does **not** join this row. A keyboard hook's event structure has no
> cursor coordinates, and the hook thread may not sample one — so such an intent would capture a
> **null** cursor, and Conduit must refuse to bind a cursor-dependent capability to it **at
> registration time**, not fail at dispatch. Adding a keyboard-hook kind without answering that is
> adding a capability that silently does nothing.
>
> *An earlier draft of this section listed the chord under `Hook` and claimed its cursor came from the
> event structure. Neither `WM_HOTKEY` nor `KBDLLHOOKSTRUCT` carries one — the row was describing a
> mouse hook and labelling it "keyboard or mouse".*

#### The published desktop facts

Hook-thread capture reads one immutable record, republished by [Atlas](ATLAS.md) whenever the
foreground window or the topology changes:

```csharp
// SKETCH — illustrative, not compiled.
sealed record DesktopFacts(
    WindowRef? ForegroundWindow,
    IReadOnlyList<MonitorGeometry> Monitors,
    int TopologyGeneration,
    long Sequence,              // monotonic; bumped by every publication, change or heartbeat
    long HeartbeatAtTicks);     // when the publisher last proved it was alive
```

**Publication follows §3.6's contract exactly** — immutable value, atomic reference swap, Conduit owns
the lifetime, the reader never blocks. It is deliberately the same mechanism as the armed region set
rather than a second one: there is one way in this pillar to hand data to the hook thread.

#### Age is not staleness — the publisher's liveness is

These are **event-driven** facts. Atlas republishes when the foreground window or the topology
changes, so on a desktop nobody is touching, a record can be an hour old and **completely correct**.
A threshold on content age is therefore wrong in both directions, and each direction is its own bug:

- **False positives that get worse the longer things are fine.** An hour of no window switching would
  make every hook gesture refuse `ContextStale` — the feature breaking *because* the desktop was
  stable, which is the failure mode hardest to reproduce and easiest to disbelieve.
- **False negatives.** A record published 5 ms ago is *recent* and still wrong if the publication
  after it was missed. Recency was never evidence of correctness; it was a proxy for it.

So the staleness test is a **liveness check on the publisher, not an age check on the facts**:

| Mechanism | What it establishes |
|---|---|
| **Heartbeat.** On a fixed interval Atlas **requests a publication**, and the sequencer re-samples the foreground, bumping `Sequence` and `HeartbeatAtTicks` | Separates *"nothing has changed"* from *"the publisher has died"* — and **repairs** a missed foreground update rather than certifying it |
| **`Sequence` is monotonic and gap-free** | A reader that sees it stop advancing across heartbeat intervals knows publication has stopped, whatever the content says |
| **`ContextStale` fires on missed heartbeats only** — `now - HeartbeatAtTicks` beyond a small multiple of the interval | The refusal now means *"Atlas stopped publishing"*, which is a genuine fault, rather than *"the desktop has been quiet"*, which is not |

> **Content age is never, on its own, a refusal reason.** An unchanged event-driven fact does not
> decay.

#### One sequencer: sampling, sequencing and swapping are one operation

**An atomic swap orders the write; it does not order the writers.** Two paths publish `DesktopFacts`
— the event path and the heartbeat — and if each samples independently and then swaps, this
interleaving is available:

| Step | Thread | Effect |
|---|---|---|
| 1 | heartbeat | samples the foreground: **A** |
| 2 | — | the user switches windows; the foreground becomes **B** |
| 3 | event path | samples **B**, takes sequence **41**, swaps |
| 4 | heartbeat | takes sequence **42**, swaps its step-1 sample — **A** |

The record now reads **A at sequence 42**: the content has gone *backwards* while carrying the
*higher* sequence, so every consumer rule of the form "a higher sequence is a later observation" now
points at the older one. The repair mechanism has become the corruption mechanism.

So **neither path publishes. Both request publication**, and one Atlas-owned sequencer does the whole
thing as one ordered operation ([ADR 0022](decisions/0022-one-publication-sequencer-for-desktop-facts.md)):

```
request(reason) ──▶ ┌─────────── the sequencer ───────────┐
                    │  1. sample the live facts           │
                    │  2. allocate the next Sequence      │
                    │  3. swap the immutable record       │
                    └─────────────────────────────────────┘
```

> **Invariant.** A record with a higher `Sequence` was **sampled** later. Sequence order is
> observation order — which is what the previous design claimed and did not have.

**It is a serial agent, not a lock callers hold.** Requests enqueue; nobody blocks. A topology
publication samples monitor geometry, and a lock held across an enumeration by whichever thread
noticed the change is the shape that eventually stalls something that matters.

**The hook thread is untouched.** It only ever *reads* the published reference — one atomic load, no
coordination. Publication ordering is a producer-side concern and stays there.

**Pending requests coalesce for free**, because the sequencer samples at execution time: N pending
requests collapse to one sample of the same world.

**An event request names the foreground it was notified about.** It still carries no sample to publish
— the sequencer does all the sampling — but it does carry an *identity claim*: `EVENT_SYSTEM_FOREGROUND`
names a window, so the event path knows which one it is reporting. The sequencer then counts a
**heartbeat correction** when:

> the foreground it just sampled was named by **no** request in this batch.

*A coarser rule — "attributed event-driven if any request was" — cannot support the guarantee it was
written for.* If the event path reports a change to X while a *different* change to Y was missed, a
coalesced batch containing that X event suppresses the count, and the missed Y repair goes unrecorded.
The metric would then under-report precisely when the event path is *partly* working, which is the
interesting failure.

**And the residual imprecision, stated rather than hidden.** Under rapid switching the sequencer can
sample a foreground whose notification is still in flight, and count a correction the event path was
about to report. That is an **over**-count — the safe direction for a health signal, since it prompts
a look rather than concealing a fault — and it is why this is read as a **rate over time**, not as an
exact tally of dropped notifications.

#### The heartbeat re-samples; it does not rubber-stamp

**A heartbeat that republishes the previous record unchanged is worse than no heartbeat**, and this is
the subtlest thing in the section. If a foreground-change notification is missed — the event path
hiccups, a notification is coalesced away, the subscription drops and re-establishes — then a
liveness-only heartbeat keeps advancing `Sequence` on a record whose foreground is **wrong**, and it
does so forever. The mechanism built to detect staleness would be actively attesting to it.

So each heartbeat **re-reads the current foreground window** before publishing. A missed notification
is therefore corrected within one interval, which turns an unbounded, undetectable error into a
bounded one:

> **Guarantee.** A missed foreground-change publication is repaired within one heartbeat interval.

**When a heartbeat finds a foreground it was not told about, that is counted**, not silently fixed.
Self-healing that leaves no trace hides a broken event path — the repair works, nobody learns the
subscription is failing, and the counter is the only thing that distinguishes "healthy" from "quietly
running on the fallback".

**Why foreground and not the whole record.** Reading the foreground window is one call. Enumerating
monitors is what a *snapshot* is for, and putting it on a timer would burn a full desktop enumeration
forever to catch an event that has its own detection path. The asymmetry is not laziness, it is the
difference in what a consumer can check:

| Fact | Can a consumer detect a missed update? |
|---|---|
| **Monitor geometry / topology** | **Yes** — `TopologyGeneration` travels on the context, and a module that reads a full snapshot compares generations and refuses on a mismatch |
| **Foreground window** | **No.** There is no generation to compare and nothing to compare it against; a wrong foreground is indistinguishable from a right one at the point of use |

**The fact a consumer cannot validate is the one the publisher must repair.** That is the whole
argument for re-sampling exactly this field.

*The first version of this decision described the heartbeat as republishing an unchanged immutable
record, and pointed at the generation comparison as the correctness check for everything. The
generation comparison covers geometry only — foreground can change while topology is identical — so a
missed foreground update would have stayed wrong indefinitely with the sequence advancing normally.*

#### Facts that are unavailable are null, and facts that are cached say when

```csharp
// SKETCH — illustrative, not compiled.
enum ContextOrigin { Hook, OsCallback, UserInterface, Timer }

sealed record InvocationContext(
    ContextOrigin Origin,
    long CapturedAtTicks,            // monotonic, at recognition
    Point? CursorPosition,           // PhysicalVirtualScreen; null for Timer
    WindowRef? ForegroundWindow,     // null when there is none, or none resolvable
    int TopologyGeneration,
    long? FactsSequence);            // Hook origin: which DesktopFacts publication it read. Else null
```

Two honesty requirements the shape enforces:

- **Nullable means "there may not be one", not "we did not bother".** A null foreground window is
  ordinary — the desktop itself can have focus, and an elevated or secure window may not be
  resolvable.
- **A cached fact says which publication it came from, not how old it was.** On a `Hook` context,
  `ForegroundWindow` is whatever publication `FactsSequence` identifies. A module that needs to know
  the facts were live rather than published takes an `OsCallback`-origin path or reads a snapshot;
  **it does not reason about the number of ticks that have passed**, because for an event-driven fact
  that number means nothing.

**Dispatch stamps a second time, and only a second time.** The payload also carries
`DispatchedAtTicks`, so a module can see how long it sat in the queue and refuse work that has gone
cold — without reading a clock in its handler, and without any part of the *context* being rewritten.
Every field above is frozen at recognition.

**Freshness against a full snapshot is still the caller's check.** A module that goes on to read an
Atlas snapshot compares `TopologyGeneration`; a mismatch means refuse rather than proceed on mixed
data.

Refusals are values as everywhere else: `NoForegroundWindow`, `ForegroundNotManageable`,
`NoMonitorUnderCursor`, `NoCursorForOrigin`, `ContextStale`.

### 5.6 One interaction, one stream

**A module must not compose two intent streams to reconstruct one interaction.** There is no ordering
guarantee between kinds and there is deliberately not going to be one — providing it would mean
specifying cross-stream ordering across the whole taxonomy to serve one consumer.

The concrete case: a drag is the **input gesture** kind, whose payload carries the dragged
`WindowRef` and an `InvocationContext`, and whose `Started`/`Ended` pairing is the cleanup guarantee.
The window-event pair remains for consumers that want raw move/size transitions — but a drag-to-snap
module subscribes to the gesture and nothing else. Zones' first draft used both and had an undefined
race over which stream owned taking the overlay down
([ADR 0017](decisions/0017-invocation-context-and-one-drag-lifecycle.md)).

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

The six kinds in §3 exist because a real consumer needed each one. A seventh needs the same
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

## 8. Status — contract types compile, the fabric does not exist

**`Coordinator.Conduit.Core` exists and compiles** — the trigger-intent model, the registration
outcome including first-class refusal, and the dispatch shape. CI built it on Ubuntu and Windows at
`7aef6ff` (2026-08-08) with 0 warnings.

**Nothing behind those declarations exists.** There is no registry, no arbiter, no dispatcher, no
hook, no `Coordinator.Conduit.Shell`, and **no tests** — unlike Atlas, this pillar's interesting
logic (arbitration) is not written yet, so there is nothing to test. Compiling a set of declarations
proves they are well-formed and nothing more.

Two honesty statements, both required whenever this pillar's status is described:

1. **Not one input event has ever been dispatched.** No chord has been registered, no hook installed,
   no gesture recognised, no wheel event swallowed or passed through.
2. **Nothing here has been measured.** Every latency budget, every guarantee, every "always" and
   every "never" on this page is a specification the implementation will be held to — not an
   observation. §5.4 exists precisely because those numbers have to be *earned*.

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
