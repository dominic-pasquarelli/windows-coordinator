# ADR 0023 — Conduit has two dispatch classes, and the control plane may not drop the final state

Date: 2026-08-08
Status: Accepted · Corrects [ADR 0021](0021-requested-versus-granted-regions.md)

## Context

[ADR 0021](0021-requested-versus-granted-regions.md) split a module's **requested** regions from its
**granted** ones and notified changes with two delta events, `RegionsRevoked` and `RegionsRestored`,
described as *"ordinary dispatches on a worker"*.

Review of PR #2 pointed out what "ordinary" means in this pillar.
[CONDUIT §5.3](../CONDUIT.md#53-the-hand-off) specifies a **bounded queue** that, under overload,
**drops the oldest coalescible item** and never blocks the producer. That policy is correct and
deliberate for input: a dropped wheel tick is a cosmetic loss, and buffering on the hook path would be
worse than the loss.

It is wrong for these messages, in two ways:

- **A dropped `RegionsRestored` is permanent.** Conduit has re-armed the region; the module never
  learns; the zone shows as unavailable forever. Nothing retries, because
  [ADR 0021](0021-requested-versus-granted-regions.md) correctly forbids the module from re-requesting.
- **Reordering inverts the outcome.** A revoke delivered after a restore leaves the module believing
  it lost a region it holds. Deltas are only correct if **every** message arrives, **in order**.

`GrantVersion` does not save this. It protects **queued pointer events** from executing under a
superseded lease, which is a different job; it does nothing for a consumer that missed the
notification carrying the state.

The root cause is broader than the bug: **Conduit had one queue policy and two kinds of message.**

## Decision

### 1. Name the two classes, and give them opposite guarantees

| | **Event plane** | **Control plane** |
|---|---|---|
| Carries | something happened — a tick, a chord, a gesture | what the world **is** — the current grant |
| Examples | every trigger dispatch | `GrantChanged` |
| Under overload | **drop the oldest coalescible**, and count the drop | **never drop the final state**; replace pending with newer |
| Ordering | none across kinds | **serial per owner** |
| A lost message costs | a cosmetic miss | **permanent desynchronization** |

The event plane's policy is unchanged and stays right. The control plane is new because these
messages were being carried by a mechanism whose correctness argument does not apply to them.

### 2. The control plane carries absolute state, not deltas

```csharp
// SKETCH — illustrative, not compiled.
sealed record GrantChanged(ArmedRegionSet Granted, int GrantVersion);
```

**This is the decision that makes the rest cheap.** A delta is correct only if every delta is
delivered in order. **An absolute snapshot is correct if the last one is delivered** — which is a
guarantee a bounded queue can actually make, and it makes a late or coalesced-away intermediate
harmless rather than corrupting.

`RegionsRevoked` and `RegionsRestored` are replaced by this one message. A consumer stops diffing and
simply **adopts the set**, which is idempotent and order-insensitive.

### 3. Serial per owner, with latest-state coalescing

- Grant updates for one owner are delivered **in order**, one at a time.
- Under pressure a pending update is **replaced** by the newer one, never dropped — so the per-owner
  queue depth for control messages is effectively **one**, and the message that survives is always
  the most complete.
- **The final state is always delivered.** Coalescing may skip intermediates; it may not skip the end.

**A version gap is therefore normal and not an error.** A module may see `GrantVersion` go 5 → 9
because 6–8 were superseded. This must be said plainly, or an implementer writes a gap-detected-resync
loop that fires constantly under exactly the load it was meant to help.

### 4. A module ignores a version it has already passed

Applying a `GrantChanged` whose version is **≤** the last applied version is a no-op. Cheap, local,
and it makes the module's correctness independent of any delivery guarantee it cannot verify.

### 5. There is a current-grant read

```csharp
// SKETCH — illustrative, not compiled.
(ArmedRegionSet Granted, int GrantVersion) QueryGrant(ModuleId module);
```

For **recovery**, not routine operation: a module whose handler faulted, or that is re-initialising,
resynchronizes in one call rather than waiting for the next arbitration change that may never come.
Routine gap-filling is not its purpose — see §3.

## Consequences

- **A lost or reordered notification stops being able to desynchronize a module.** The failure the
  review found is removed rather than made unlikely.
- **The consumer handler gets simpler.** Adopt the set; no diffing, no accumulated state, no
  reconciliation of two event types. Zones' version is
  [ARCHITECTURE §7.4](../../src/modules/zones/docs/ARCHITECTURE.md#74-losing-and-regaining-a-region),
  and it shrank.
- **Conduit's dispatch surface grows a second policy**, which is a real cost for a pillar whose value
  is being small. Paid because the alternative is a queue policy silently wrong for a class of message
  it was already carrying.
- **Control-plane messages cannot be starved by input load**, since they occupy a separate per-owner
  slot rather than competing for the input queue's capacity.
- **The distinction is now available to future work.** Any "here is the current state of X" message —
  a settings change, a module enable/disable, a capability becoming unavailable — belongs on the
  control plane, and the question "is this an event or a state?" now has a place to be answered.

## Alternatives considered

- **Make the existing queue lossless for these messages.** An unbounded queue on a path with a
  bounded producer is how a slow handler becomes a memory leak. Latest-state coalescing gets the same
  correctness in constant space, because state supersedes rather than accumulates.
- **Keep deltas and add sequence numbers so the consumer can detect a gap and resync.** Every consumer
  then implements gap detection and a resync path — correctly, forever. Absolute state removes the
  requirement instead of distributing it.
- **Acknowledgement and retry.** Reliable, and it makes Conduit wait on module handlers, which is the
  coupling the whole dispatch design exists to avoid. It also cannot help a module that has stopped
  responding, which is when it would matter.
- **Have the module poll `QueryGrant` on a timer.** Works, and makes every module pay a polling cost
  forever to cover a case that a correct delivery contract removes. The read stays for recovery.
- **Deliver on the hook thread to guarantee ordering.** Never. Ordering is not worth putting module
  code on the input path, and §5.2 forbids it outright.

## See also

- [ADR 0021](0021-requested-versus-granted-regions.md) — the grant model whose delivery this fixes.
- [CONDUIT §5.3](../CONDUIT.md#53-the-hand-off) — the hand-off table this adds a class to.
- [CONDUIT §3.6.1](../CONDUIT.md#361-requested-and-granted-are-two-different-values) — the contract.
