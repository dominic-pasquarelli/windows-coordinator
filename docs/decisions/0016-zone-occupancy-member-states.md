# ADR 0016 — A stack member carries state, and reconciliation is generation-aware

Date: 2026-08-08
Status: Accepted

## Context

[ADR 0012](0012-zones-stacking-model.md) modelled a zone's occupancy as an **ordered list of
`WindowRef`**. Review of PR #2 established that a bare list cannot maintain the invariants the same
ADR claims. Five concrete transitions have no representable answer:

1. **A taskbar click changes which member is visible.** Only cycling updated the stored order, and
   Atlas exposed no z-order — so the model's idea of "the front one" silently diverges from the
   screen, and nothing can detect it.
2. **A minimised member is retained, but `Raise` does not restore it.** Cycling can therefore select
   a window the user cannot see, and the stack appears to skip.
3. **`PlacedDifferently` is supposed to stay in the stack** — but membership was tested by comparing
   the window's bounds to the *zone rectangle*, and a clamped window by definition does not match it.
   The very next reconciliation drops it.
4. **A topology change moves windows.** The bounds test then reads "the user dragged it out" for
   every member of every stack, discarding intent wholesale at exactly the moment geometry is least
   trustworthy.
5. **`stackOnDrop = false` removes the previous occupant from the model** without moving,
   minimising, or hiding it — leaving an unmanaged window sitting in the same rectangle as the new
   one, which looks exactly like the bug the setting was meant to avoid.

Each is a case where the *model* is too thin, not where the *policy* is undecided.

## Decision

### 1. A member is a record with state, not a bare reference

```csharp
// SKETCH — illustrative, not compiled.
enum MemberState { Placed, Minimized, Oversized, AwaitingReplacement }

sealed record StackMember(
    WindowRef Window,
    MemberState State,
    Rect PlacedBounds,        // what we asked for
    Rect ObservedBounds,      // what we actually got back (may differ — PlacedDifferently)
    int PlacedAtGeneration);  // the Atlas topology generation it was placed under
```

### 2. Stored order is the **cycle ring**, not a claim about what is visible

The list says what order cycling walks. It does **not** assert which window is in front. That is read
from the snapshot — which requires Atlas to expose z-order, so **Atlas's snapshot window list is
ordered front-to-back** (a real property of the enumeration, not a new computation).

Cycling means *raise the ring member after whichever member is currently frontmost*. A taskbar click
therefore needs no reconciliation at all: it changed which member is frontmost, and the next cycle
simply continues from there. **Case 1 stops being a divergence to detect and becomes a value to
read.**

### 3. Membership is tested against `ObservedBounds`, never the zone rectangle

A member has left when its current bounds differ from **what we last observed after placing it**,
beyond tolerance. A window that clamped its own size is still exactly where we last saw it, so it
stays — **case 3**. It is marked `Oversized` so the module can say why a stack looks wrong rather
than pretending it does not.

### 4. Reconciliation is generation-aware

If `snapshot.TopologyGeneration != member.PlacedAtGeneration`, the bounds test **is not applied**.
The member is marked `AwaitingReplacement` and Zones re-places it against the re-resolved zone;
bounds testing resumes only after a placement under the current generation. This is
[ATLAS §4.1](../ATLAS.md#41-topology-generation)'s existing rule — geometry computed at generation N
must not be judged at N+1 — applied to membership rather than only to rectangles. **Case 4.**

### 5. Cycling to a minimised member restores it

`Show(window)` = restore-if-minimised, then raise. Cycling calls `Show`, not `Raise`, so it can never
select a window the user cannot see. Cycling *away* does **not** re-minimise — silently changing a
window's state on the way past is the surprise this design avoids elsewhere. **Case 2.**

### 6. `stackOnDrop = false` **swaps**; it does not evict into limbo

The displaced occupant goes where the incoming window came from — its previous zone if it had one,
otherwise its pre-drag bounds, both of which Zones already knows because it initiated the drag. When
neither is available (a window dragged in from nowhere Zones was tracking), the occupant is unmanaged
and **left in place**, and that outcome is recorded as `Displaced` so the surface can say so rather
than leaving a window mysteriously stacked under another. **Case 5.**

## Consequences

- **Reconciliation grows from a filter into a state machine**, and it remains pure — no desktop, no
  clock, no I/O. Every one of the five cases becomes a named test rather than an argument.
- **Atlas must order snapshot windows by z-order.** Cheap (the platform enumeration is already
  ordered) and independently useful — any future module asking "what is on top here" needs it.
- **Atlas gains `Show`** alongside `Raise` and `Activate` ([ADR 0014](0014-atlas-explicit-raise-and-activate.md)),
  which is a third operation on a pillar that should stay small. Accepted: the alternative is Zones
  performing restore-then-raise as two calls with a window of time between them where the state is
  neither.
- **The model carries two rectangles per member**, which reads like redundancy until the first
  clamped window. `PlacedBounds` is intent; `ObservedBounds` is fact; conflating them is precisely
  how case 3 arose.
- **`AwaitingReplacement` is observable state**, so a stack mid-topology-change is explicable rather
  than briefly wrong for reasons nobody can see.
- **More state means more ways to be inconsistent.** Mitigated by the invariants being testable and
  by every transition above having a named test in the implementation plan.

## Alternatives considered

- **Keep the bare list and fix each case with policy.** Rejected — that is what produced the five
  cases. Without state, "is this window still a member?" and "why does this stack look wrong?" have
  no representable answers, and every fix becomes a special case in the reconciler.
- **Track the front member ourselves rather than reading z-order.** Rejected: it is a cache of
  something the OS already knows and the user can change behind our back at any moment. Reading it is
  both simpler and correct; caching it re-creates case 1 in a new place.
- **Drop minimised members from the stack.** Simpler, and wrong — the user put that window there, and
  minimising is not leaving. It would also make minimise-then-cycle silently destroy a stack.
- **Re-minimise on cycle-away**, keeping only one member non-minimised. Rejected: it animates on every
  cycle, and it changes window state the user did not ask to change — the same reasoning that made
  [ADR 0012](0012-zones-stacking-model.md) choose z-order over minimising in the first place.
- **Refuse the drop when `stackOnDrop = false` and the zone is occupied.** Honest, and worse in
  practice: the user's drag simply does nothing, which reads as the tool being broken. Swapping is
  what they almost certainly meant.

## See also

- [ADR 0012](0012-zones-stacking-model.md) — the model this corrects.
- [ADR 0014](0014-atlas-explicit-raise-and-activate.md) — `Raise` / `Activate`, now joined by `Show`.
- [ADR 0015](0015-zone-addressing-and-durable-monitor-identity.md) — how a zone is addressed.
- [ARCHITECTURE §5](../../src/modules/zones/docs/ARCHITECTURE.md#5-reconciliation--where-the-bugs-would-otherwise-live).
