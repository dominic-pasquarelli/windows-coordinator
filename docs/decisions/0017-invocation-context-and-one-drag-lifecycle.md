# ADR 0017 — Every dispatch carries an invocation context, and a drag has exactly one lifecycle

Date: 2026-08-08
Status: Accepted

## Context

Two gaps found in review of PR #2, with one root cause: **Conduit tells a module *that* something
happened and not *the state of the world when it happened*.**

**Gap 1 — cursor- and foreground-dependent capabilities cannot be implemented.** A hotkey dispatch
carries only a capability id. But `zones.snap-focused` needs the focused window; chord-driven
`zones.cycle-forward` needs the zone under the cursor; `zones.next-layout` needs the monitor under
the cursor; the `Reading` capabilities are defined relative to the cursor. Atlas exposes neither the
cursor nor the foreground window. A module left to solve this either calls Windows directly
(forbidden by [principle 4](../COORDINATOR.md#7-non-negotiable-principles)) or caches coalesced focus
events (which [CONDUIT §3.2](../CONDUIT.md#32-window-event) explicitly says is not a log and must not
be treated as one).

**Gap 2 — the drag path races itself.** Zones was specified to use *both* the window-event pair
`MoveSizeStart`/`MoveSizeEnd` **and** the input-gesture `Started`/`Ended`. Conduit defines no ordering
between intent streams, so "which arrived first" is undefined, and cleanup ownership is ambiguous —
each stream believes it owns taking the overlay down.

## Decision

### 1. Every dispatch carries an `InvocationContext`, sampled by Conduit at dispatch time

```csharp
// SKETCH — illustrative, not compiled.
sealed record InvocationContext(
    Point CursorPosition,          // PhysicalVirtualScreen
    MonitorId? MonitorUnderCursor,
    WindowRef? ForegroundWindow,
    int TopologyGeneration,
    long SampledAtTicks);
```

**Conduit samples it; Atlas defines and provides it.** Conduit is on the dispatch path and knows when
"now" is; Atlas is the single source of desktop truth and owns what "the cursor" and "the foreground
window" mean. So Conduit asks Atlas for a **point sample** — a deliberately cheap read, not a full
snapshot — and stamps it onto the payload. A module never queries either.

**Why sample at dispatch rather than let the module read.** By the time a module runs, the user has
moved the mouse. The semantically correct values are the ones at the instant the chord fired, and
only the dispatcher is there at that instant.

**"Focused" means** the foreground top-level window as the OS reports it, resolved to a `WindowRef`,
or `null`. Null is ordinary, not exceptional: the desktop itself can have focus, and a secure or
elevated window may not be resolvable.

**Freshness is the caller's check, not a promise.** The context carries the topology generation and a
monotonic stamp. A module that goes on to read a full snapshot compares generations; a mismatch means
the world moved and the right answer is to refuse, not to proceed on mixed data.

**Refusals** are values, as everywhere else: `NoForegroundWindow`, `ForegroundNotManageable`
(elevated or system), `NoMonitorUnderCursor`, `ContextStale`.

### 2. A drag is one gesture, with the dragged window in the payload

The **input gesture** kind becomes the single authoritative drag lifecycle. Its payload carries the
dragged `WindowRef` and an `InvocationContext`, and it keeps its existing guarantee that exactly one
`Ended` follows every `Started`.

**Zones subscribes to that and to nothing else for dragging.** The window-event pair remains in the
taxonomy for consumers that want raw move/size transitions, but a module must not compose the two
streams to reconstruct one interaction — there is no ordering between them, and there is deliberately
not going to be one.

Conduit derives the dragged window internally. It owns the hook; it already knows which window is in
a move/size loop; making every consumer re-derive that from a second stream is the coupling this
decision removes.

## Consequences

- **The four blocked capabilities become implementable** without a module touching Windows or
  inventing a focus cache.
- **Cleanup ownership is unambiguous.** One `Started`, one `Ended`, one owner of the overlay. The
  race is gone rather than documented.
- **Conduit now depends on Atlas** for the point sample, where before the pillars were independent.
  This is the significant cost. Accepted because the alternative is worse in both directions: Conduit
  reading the desktop itself would duplicate the truth Atlas exists to hold single, and pushing the
  problem to modules would put desktop queries in every module that wants a cursor position. The
  dependency is one-way and narrow — Conduit asks for a sample and does not interpret it.
- **The point sample must be genuinely cheap**, because it runs on every dispatch. It is a handful of
  reads, not an enumeration, and it is explicitly *not* a snapshot: a module that needs the full
  desktop still asks Atlas for one and checks the generation.
- **A stale context is now expressible**, so "the world moved between the keypress and the work" has a
  name and a refusal instead of being an unnoticed source of wrong placements.
- **`InvocationContext` appears in every dispatch payload**, including ones that do not need it (a
  schedule tick does not care where the cursor is). Carrying it uniformly is worth more than the
  bytes: a module that later needs it does not force a payload change, and there is one shape to
  learn.

## Alternatives considered

- **Let Zones query the cursor and foreground directly.** Disqualified by principle 4, and it is the
  first crack in the rule that makes two modules agree about the desktop.
- **Have Zones track focus from window events.** Explicitly refused by CONDUIT §3.2 — those events are
  coalesced hints, not a log. A focus cache built on them is wrong in exactly the cases that matter
  (fast switching), and wrong silently.
- **Attach a full Atlas snapshot to every dispatch.** Correct and far too expensive: a snapshot
  enumerates every window, on every keypress. The point sample exists because the common case needs
  three values, not the whole desktop.
- **Put the cursor and foreground on the Atlas snapshot only**, and have modules take a snapshot on
  every dispatch. Rejected for the same cost reason, plus it reintroduces the timing problem — the
  snapshot is taken *after* the module is running, so it answers "where is the mouse now", not "where
  was it when the user pressed the key".
- **Keep both drag streams and define an ordering between them.** Possible, and it means specifying
  cross-stream ordering guarantees for the whole taxonomy to solve one consumer's problem. Collapsing
  to one stream is smaller and removes the question instead of answering it.

## See also

- [CONDUIT §3](../CONDUIT.md#3-the-trigger-intent-taxonomy) — the taxonomy this changes.
- [ATLAS §3](../ATLAS.md#3-the-model) — where the cursor and foreground window are defined.
- [ARCHITECTURE §6](../../src/modules/zones/docs/ARCHITECTURE.md#6-drag-to-snap) — the module-side view.
