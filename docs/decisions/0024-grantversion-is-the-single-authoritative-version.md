# ADR 0024 — `GrantVersion` is the only version, and it stamps everything

Date: 2026-08-08
Status: Accepted · Corrects [ADR 0013](0013-the-pointer-gesture-trigger-kind.md) · Unifies
[ADR 0021](0021-requested-versus-granted-regions.md) and [ADR 0023](0023-the-control-plane-carries-state-not-deltas.md)

## Context

[ADR 0013](0013-the-pointer-gesture-trigger-kind.md) specified that a pointer-gesture dispatch carries
the matched zone token **and the region-set version it matched under**, and that a module drops the
event when that version is no longer current. That was correct when it was written: the set a module
published *was* the set the hook tested, so there was one set and one version.

[ADR 0021](0021-requested-versus-granted-regions.md) then split the model in two — a module's
**requested** set, versioned by its own publications, and Conduit's **granted** set, versioned by
`GrantVersion` and recomputed on every arbitration change. The hook tests the **granted** set. Nobody
went back and reconciled the payload, and the two versions stopped being interchangeable: **a module's
requested-set version can sit unchanged while `GrantVersion` moves through several lease epochs**,
because arbitration changes without the module publishing anything.

That admits a stale event with a passing check:

| Step | State |
|---|---|
| 1 | a wheel event is recognized under **grant v1** — the region is granted |
| 2 | a higher-priority module preempts: **grant v2**, the region is withheld |
| 3 | that module withdraws: **grant v3**, the region is granted again |
| 4 | the step-1 event is delivered |
| 5 | its **requested**-set version is unchanged, so the guard passes — and it executes against an arbitration epoch that has been replaced twice |

The guard was checking the one thing that had not changed.

There is a second instance of the same root cause. [ADR 0023](0023-the-control-plane-carries-state-not-deltas.md)
version-guards `GrantChanged`, but the **publication result** — what `Publish` hands back — was left as
an ordinary return value with no version and no guard. An in-flight result for an older grant can
therefore land after a newer `GrantChanged` and overwrite it.

## Decision

### 1. One version, stamped into all four places

**`GrantVersion` is the authoritative version.** The requested-set version is not a guard and is not in
any payload. `GrantVersion` is stamped into:

| Stamped into | Why |
|---|---|
| **The immutable hook lookup table** | so the hook stamps the epoch it actually tested against, at zero extra cost — it is already reading that table |
| **Every pointer-gesture dispatch** | so the epoch travels with the event through the queue |
| **The publication result** | so the first grant a module ever receives arrives the same way as every later one |
| **Every `GrantChanged`** | unchanged from [ADR 0023](0023-the-control-plane-carries-state-not-deltas.md) |

The **zone token stays** — it answers *which zone*, which `GrantVersion` does not. The two answer
different questions and both are needed; what is retired is the separate region-set version.

### 2. A pointer event executes only on an exact version match

> `dispatch.GrantVersion == module.AppliedGrantVersion` — **exactly**, not ≥ or ≤.

Both mismatches are real and both must drop:

- **Older** — the event was recognized under a lease epoch that has since been replaced. The
  motivating bug.
- **Newer** — Conduit has swapped the hook table but the module has not yet applied that grant, so the
  module's own idea of which zones are cyclable does not match the epoch the event came from. Acting
  would mean acting on a state it has not adopted.

**This can drop a tick in the brief window around an arbitration change**, and that is acceptable on
this kind's own terms: [ADR 0013](0013-the-pointer-gesture-trigger-kind.md) already guarantees neither
delivery nor one-dispatch-per-detent, and a dropped cycle tick is a cosmetic loss. A tick executed
against the wrong lease epoch is not.

### 3. The publication result flows through the same guarded path

```csharp
// SKETCH — illustrative, not compiled.
(ArmedRegionSet Granted, int GrantVersion) Publish(ArmedRegionSet requested);

void ApplyGrant(ArmedRegionSet granted, int version);   // the ONLY way grant state changes
```

`Publish`'s result and every `GrantChanged` go through **one** `ApplyGrant`, which ignores a version
that is not newer than the applied one. There is deliberately **no separate publication-result path**:
two paths mutating the same state with only one of them version-guarded is how an older result
overwrites a newer update, and the fix is to have one path rather than to guard the second one
carefully.

## Consequences

- **The stale-epoch execution is unrepresentable**, rather than unlikely. The guard now checks the
  value that actually changes.
- **A module holds exactly one version number**, and it means one thing. The previous design had two
  versions with similar names, of which the guard used the one that could not detect the problem —
  the kind of thing that reads as correct in review indefinitely.
- **Conduit stamps a version it already has.** The hook table carries it; the hook copies it into the
  dispatch. No new lookup on the input path.
- **A small number of ticks are dropped around arbitration changes.** Accepted above, and bounded:
  arbitration changes on registration, settings-save and unregistration, not during use.
- **`Publish` gains a return shape** rather than being fire-and-forget, and every consumer must route
  it through `ApplyGrant`. Slightly more ceremony at the call site, in exchange for there being one
  place where grant state changes.

## Alternatives considered

- **Version the requested set too, and check both.** Two versions, two guards, and a rule about how
  they interact — which is more surface to get wrong than deleting the one that answers no question a
  consumer asks. The requested set's version has no consumer once the grant is authoritative.
- **Guard with `>=` instead of exact equality**, so a newer dispatch is allowed. Rejected: it lets a
  module act on an epoch it has not adopted, so its cyclable-zone state and the event disagree — the
  same class of bug in the other direction, and harder to see because it only appears in the window
  between the table swap and the control message.
- **Deliver `GrantChanged` synchronously before swapping the hook table**, removing the "newer"
  case. That would put control-plane delivery in front of an input-path update and make Conduit wait
  on module handlers, which [ADR 0023](0023-the-control-plane-carries-state-not-deltas.md) rejects for
  independent reasons.
- **Have the module re-query `QueryGrant` on every dispatch to decide.** A read on the dispatch path
  to answer a question a stamped integer answers for free.
- **Leave the publication result unguarded and rely on it arriving first.** It usually does, which is
  what makes the failure rare and the debugging miserable.

## See also

- [ADR 0013](0013-the-pointer-gesture-trigger-kind.md) — the payload this corrects.
- [ADR 0021](0021-requested-versus-granted-regions.md) — requested vs granted.
- [ADR 0023](0023-the-control-plane-carries-state-not-deltas.md) — the control plane this unifies with.
- [ARCHITECTURE §7.4](../../src/modules/zones/docs/ARCHITECTURE.md#74-losing-and-regaining-a-region).
