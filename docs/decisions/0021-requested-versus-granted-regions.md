# ADR 0021 — A module states a standing request; Conduit computes the grants and keeps recomputing them

Date: 2026-08-08
Status: Accepted · Corrects [ADR 0013](0013-the-pointer-gesture-trigger-kind.md)

## Context

[ADR 0013](0013-the-pointer-gesture-trigger-kind.md) made a pointer-gesture region grant a
**revocable lease**, arbitrated by explicit user priority and then by stable module id, and claimed
the property that justifies the whole design:

> the armed map is a pure function of the current request set and the priority order.

Review of PR #2 established that the design as written does **not** have that property, and the
counter-example is short. A low-priority module holds a region. A higher-priority module claims it and
the lease is revoked. The higher-priority module then withdraws, unregisters, or has its priority
lowered by the user. Nothing restores the region — the low-priority module was told not to retry, and
Conduit has no record that it ever wanted it. The final armed map depends on **what happened and in
what order**, which is precisely the history-dependence that replacing "first registration wins" was
supposed to eliminate.

There is a second, quieter version of the same defect. A publication overlapping a higher-priority
owner was **refused**, so the contested rectangle never entered any durable record of what the module
wanted. A refusal discards the request. Restoration is impossible for something nobody remembers
asking for.

## Decision

### 1. Two values per owner, not one

```csharp
// SKETCH — illustrative, not compiled.
sealed record RegionOwner(
    ModuleId Module,
    int Priority,                            // explicit user setting; ties break on ModuleId
    ArmedRegionSet Requested,                // what the module asked for — its standing desire
    ArmedRegionSet Granted,                  // what it currently holds — Conduit's answer
    int GrantVersion);                       // bumped on EVERY change to Granted
```

`Requested` is durable and belongs to the module: it changes **only** when the module publishes.
`Granted` is derived and belongs to Conduit: it changes whenever anything in the system changes.

### 2. Grants are recomputed, never patched

```
grants = arbitrate(all owners' Requested, priority order)
```

Recomputed in full whenever a module publishes, a module registers or unregisters, or a priority
setting changes. For each contested rectangle the highest-priority requester wins; ties break on
stable module id. Nothing in the computation reads arrival order, and no previous grant map is an
input — so the same requests and priorities always produce the same grants, whatever route the system
took to get there.

### 3. Contention is arbitrated, not refused

A publication that overlaps a higher-priority owner is **accepted**. The request is recorded whole;
the grant is whatever arbitration awards, which may be a subset or empty. **The result reports the
granted set explicitly**, so a module never has to infer what it holds.

This retires ADR 0013's rule that such a publication is refused, and with it the subtraction-retry
protocol that rule forced. Genuine errors still refuse the whole publication — `ModifierReserved`,
`TooManyRegions` — because those are malformed or over-quota requests rather than contention.

**The invariant that mattered survives in a better form.** "No silent trimming" was there to stop a
module believing it armed regions it does not own. Reporting the grant on every publication *and* on
every later change answers that directly, where a refusal answered it only by refusing to proceed.

### 4. Both transitions are notified, and both bump the version

- **`RegionsRevoked`** — rectangles this owner has lost, because someone with higher priority now
  requests them.
- **`RegionsRestored`** — rectangles this owner has regained, because the higher-priority requester
  withdrew, unregistered, or lost priority.

Both are ordinary dispatches on a worker, never on the hook thread. **Both bump `GrantVersion`**, and
a queued gesture carries the version it was recognized under, so an event recognized under a lease
that has since changed is dropped rather than executed. Without the bump on *restoration*, an event
recognized before a revocation could execute after the region came back — acting on an arbitration
state that no longer exists.

**A module never re-publishes to regain a region.** Restoration is Conduit's job precisely because the
module's request never went away.

## Consequences

- **The stated property becomes true.** `grants = f(requests, priorities)`, with history nowhere in
  it. That is testable by permutation, and [CONDUIT §5.4](../CONDUIT.md#54-proving-the-guard-not-asserting-it)
  now requires the permutation test to include a full preempt-then-withdraw-then-restore cycle —
  the sequence that fails under the old design.
- **The consumer protocol gets simpler, not more complex.** Publish once, be told what you hold, and
  be told when it changes. The refuse-then-subtract-then-retry dance from
  [ADR 0013](0013-the-pointer-gesture-trigger-kind.md) is gone, along with the question of how many
  times to retry.
- **Conduit now holds state it did not**: every module's standing request, including rectangles it is
  not currently granted. That is the real cost. It is bounded by the same per-module region cap that
  already bounds the hook test, and it is what restoration is made of.
- **Recomputation is not free**, but it happens on registration, settings-save and unregistration —
  never on the input path. This is [principle 7](../COORDINATOR.md#7-non-negotiable-principles): the
  hook still reads one pre-resolved immutable set through one atomic swap.
- **A module must handle regions arriving as well as leaving.** Slightly more surface, and it is
  honest surface: a feature whose availability changes needs to notice in both directions or it will
  show a permanently-disabled affordance that has actually been available for an hour.
- **A user changing a priority now moves regions immediately**, which is what makes the setting worth
  having. Under the old design it only affected future publications, so the knob appeared to do
  nothing until something unrelated happened to republish.

## Alternatives considered

- **Keep refusal, and have the loser poll or retry.** Rejected. Retry has no natural interval, and a
  module re-requesting a rectangle the user's own priority setting gave to someone else is a module
  fighting its user. It also cannot work: the loser was explicitly told not to retry, which is the
  right instruction and the reason nothing restores the region.
- **Have the winner notify the losers when it withdraws.** Makes modules responsible for each other's
  arbitration, which is exactly the coupling the pillar exists to prevent — and it fails whenever the
  winner exits abnormally, which is when it matters most.
- **Restore only on unregistration, not on priority change or withdrawal.** Cheaper, and it leaves the
  armed map history-dependent in the remaining cases, so it does not actually fix the defect — it
  narrows the counter-example.
- **Grant everything and let overlapping modules both receive the event.** Rejected in
  [ADR 0013](0013-the-pointer-gesture-trigger-kind.md): two modules acting on one wheel tick is not a
  behaviour anyone wants, and the hook cannot ask which one meant it.
- **Let the module keep a rectangle it holds until it republishes** — the previous design. Rejected
  above: it makes arrival order decide the winner, which is the rule stable priority replaced.

## See also

- [ADR 0013](0013-the-pointer-gesture-trigger-kind.md) — the trigger kind whose arbitration this
  corrects.
- [CONDUIT §3.6](../CONDUIT.md#36-pointer-gesture) — the contract this is written into.
- [ARCHITECTURE §7.4](../../src/modules/zones/docs/ARCHITECTURE.md#74-losing-and-regaining-a-region) —
  the consumer side.
