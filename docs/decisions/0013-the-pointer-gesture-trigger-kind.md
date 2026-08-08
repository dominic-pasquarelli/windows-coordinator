# ADR 0013 — A sixth Conduit trigger kind: the pointer gesture, decided from pre-resolved regions

Date: 2026-08-08
Status: Accepted

## Context

Zones cycles a stack with `Win` + mouse wheel over the zone
([ADR 0012](0012-zones-stacking-model.md)). Nothing in Conduit's taxonomy expresses that.

[CONDUIT §7](../CONDUIT.md#7-adding-a-trigger-kind--the-extension-contract) says the first test is
whether it is a new kind at all — a need expressible as a filter or parameter on an existing kind is
not one. Walking the five:

- **Hotkey chord** — no. There is no key-down transition that means "the wheel moved".
- **Window event** — no. Wheel input is not a window transition.
- **Schedule** — no.
- **Tray action** — no.
- **Input gesture** — the closest, and still no. That kind is a *span*: `Started`, throttled
  `Updated`, exactly one `Ended` carrying `Committed` or `Cancelled`, and its guarantees exist so an
  overlay put up at the start is always taken down. A wheel tick is **discrete**. There is nothing to
  clean up, no cancellation, and forcing it into a span would mean synthesising a start and an end
  around a burst of ticks — inventing lifecycle events with no referent purely to fit the shape.

So it is a genuinely new kind. The harder question is the one that actually shapes it.

**The hook-thread problem.** Deciding whether to swallow a wheel event happens on the low-level input
hook thread, within the microsecond budget in [CONDUIT §5.1](../CONDUIT.md#51-the-hard-constraint),
on **every wheel event the machine processes** — including scrolling this page. The naive design asks
the module: *"is the cursor over one of your zones, and does it have a stack?"* That puts arbitrary
module code on the critical path of every scroll on the desktop, which is precisely what Conduit
exists to prevent.

## Decision

**Add the pointer gesture as trigger kind #6, and require its recognizer to be evaluable on the hook
thread without consulting any module.**

### The intent record

A module declares: a capability id · a modifier requirement · a wheel axis · and an **armed region
set** — pre-resolved rectangles in
[`PhysicalVirtualScreen`](../ATLAS.md#51-the-spaces) space, which the module republishes whenever
they change. Conduit stores them. The hook does a rectangle test and nothing else.

### The rule that makes it safe

> **A pointer-gesture recognizer must be answerable from data Conduit already holds.** No callback,
> no query, no module code on the hook thread. If a kind cannot be decided that way, it does not
> get added — [CONDUIT §7](../CONDUIT.md#7-adding-a-trigger-kind--the-extension-contract) already
> says a kind that can only be dispatched on the hook thread means the design is wrong, and this is
> the same rule one step earlier, applied to the *decision* rather than the dispatch.

### The rest of the §7 checklist

| Required | This kind |
|---|---|
| **Refusal reasons** | `RegionsOverlapAnotherOwner` (another module armed an intersecting region with the same modifier) · `ModifierReserved` (a modifier Conduit will not hook) · `TooManyRegions` (the per-module cap that keeps the hook test bounded) |
| **Conflict rule** | Two intents conflict when their modifier matches **and** their armed regions intersect. Disjoint regions with the same modifier are fine — that is the normal case, and it is why the conflict rule is geometric rather than modifier-wide |
| **Dispatch class** | Hook for the *decision*; the **dispatch runs on a worker**. The hook's entire job is: test, swallow-or-pass, queue |
| **Guarantee statement** | Delivered as a discrete event carrying the capability id, the cursor position, and a tick delta. **Coalesced** under load. **Not** guaranteed: one dispatch per physical detent, ordering against other input kinds, or delivery at all when the queue is saturated — a dropped cycle tick is a cosmetic loss, and pretending otherwise would mean buffering on the hook path |
| **Core model with a fake source** | The recognizer is a pure function `(cursor, modifiers, armed regions) -> Swallow \| PassThrough`, driven in tests by a fake input source. Fully testable with no desktop |
| **Manual-validation row** | `Z-3` (hook latency under load) and `Z-5` (swallowing does not break scrolling in a stacked window) |

### Fail-open, always

Any doubt — empty region set, unknown modifier state, a queue that is full — passes the event through
untouched. A dropped cycle is a cosmetic annoyance; a swallowed scroll is a desktop that feels
broken.

## Consequences

- **The per-event cost is a bounded rectangle test** against a small array, with an early-out when
  the modifier is not held. All the real work happens when a layout or a stack changes, which is
  rare. This is [principle 7](../COORDINATOR.md#7-non-negotiable-principles) applied to the hottest
  path in the system.
- **Zones only arms zones with a stack of two or more**, so `Win`+wheel over an ordinary window
  passes through and the feature is invisible until it is useful.
- **The taxonomy grew from five kinds to six**, which is a real cost — a wider surface every module
  reads and every future arbitration rule covers. Paid because there is a consumer today, not a
  speculative one.
- **Conduit now stores geometry**, which it did not before. It does not *interpret* it — it never
  asks what a rectangle means, only whether a point is inside one — but the coordinate space is now
  part of Conduit's contract, and a module that publishes rectangles in the wrong space gets a
  gesture that fires in the wrong place. The space is named in the intent for exactly that reason.
- **Stale armed regions are possible.** A module that fails to republish after a layout change leaves
  Conduit testing against rectangles that no longer exist. Bounded by carrying the Atlas topology
  generation with the region set, so Conduit can drop a set that is provably stale rather than acting
  on it.

## Alternatives considered

- **Ask the module from the hook callback.** The obvious design and the one this ADR exists to
  refuse. It puts arbitrary module code on every scroll on the machine; one slow module — or one
  module that takes a lock — stalls the entire desktop. The pillar exists to make this impossible,
  not merely discouraged.
- **Give the module the whole screen as its region and let it decide after dispatch.** That means
  swallowing every modified wheel event before knowing whether it is wanted, so `Win`+wheel would
  stop working everywhere else. Fails the fail-open rule.
- **Do not swallow at all — dispatch and let the event through.** Then cycling *also* scrolls the
  window it cycles to, which is visibly wrong the first time you try it.
- **Express it as a filter on the existing gesture kind.** Considered seriously, since it avoids
  growing the taxonomy. Rejected: the span guarantees (`Ended` always follows `Started`) would be
  synthesised fiction for a discrete event, and a guarantee that is technically delivered but
  meaningless is worse than an absent one — a consumer will eventually rely on it.
- **A polling design** — read cursor position and modifier state on a timer. No hook, no swallowing,
  but it cannot prevent the underlying window from scrolling, which is the whole problem.

## See also

- [CONDUIT §3](../CONDUIT.md#3-the-trigger-intent-taxonomy) — where kind #6 lands.
- [ADR 0012](0012-zones-stacking-model.md) — the consumer that justifies it.
- [ARCHITECTURE §3.1](../../src/modules/zones/docs/ARCHITECTURE.md#31-the-hook-thread-rule-this-forces) — the module-side view.
