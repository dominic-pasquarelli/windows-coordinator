# ADR 0022 — Sampling, sequencing and swapping are one ordered operation

Date: 2026-08-08
Status: Accepted · Corrects [ADR 0017](0017-invocation-context-and-one-drag-lifecycle.md)

## Context

[ADR 0017](0017-invocation-context-and-one-drag-lifecycle.md) gave `DesktopFacts` two publication
paths — an **event path** that publishes when the foreground window or the topology changes, and a
**heartbeat** that re-samples the foreground on an interval so a missed notification is repaired
within one interval. Publication was specified as an **atomic reference swap** with a monotonic
`Sequence`.

An atomic swap prevents a **torn read**. It does not order two **writers**, and review of PR #2
supplied the interleaving that breaks:

| Step | Thread | Effect |
|---|---|---|
| 1 | heartbeat | samples the foreground: **A** |
| 2 | — | the user switches windows; the foreground becomes **B** |
| 3 | event path | samples **B**, takes sequence **41**, swaps |
| 4 | heartbeat | takes sequence **42**, swaps its step-1 sample — **A** |

The published record now says **A at sequence 42**. The content has gone backwards *and* carries the
higher sequence, so every consumer rule built on the sequence — "a higher sequence is a later
observation" — now points at the older one. The repair mechanism has become the corruption mechanism.

The defect is not in the swap. It is that **sample-then-sequence-then-swap was three separate steps**,
so the interval between sampling and publishing was unbounded and unprotected, and a sample could be
published long after it stopped being true.

## Decision

**One Atlas-owned publication sequencer. Neither path publishes; both request publication.**

```
request(reason) ──▶ ┌─────────── the sequencer ───────────┐
                    │  1. sample the live facts           │
                    │  2. allocate the next Sequence      │
                    │  3. swap the immutable record       │
                    └─────────────────────────────────────┘
```

Steps 1–3 execute as **one ordered operation**, serialized against every other publication. The
event path and the heartbeat both call `request(...)` and neither carries a sample of its own.

**The invariant this buys, stated as the thing a consumer may rely on:**

> A record with a higher `Sequence` was **sampled** later. Sequence order is observation order.

That is exactly what the previous design claimed and did not have.

### The sequencer is a serial agent, not a lock held by callers

Requests are enqueued to a single-threaded publication context; no caller blocks. This matters
because a topology publication samples monitor geometry, and a lock held across an enumeration —
taken by whichever thread happened to notice the change — is the shape that eventually stalls
something that matters.

**The hook thread is untouched.** It only ever *reads* the published reference, and that read is
unchanged: one atomic load, no coordination, no waiting. Publication ordering is a producer-side
concern and stays entirely on the producer side.

### Pending requests coalesce, and attribution survives the coalescing

Because the sequencer samples at execution time rather than at request time, N pending requests
collapse to **one** sample and one publication — the later requests would have sampled the same
world. Coalescing is therefore free rather than lossy.

**A coalesced publication is attributed event-driven if any of its requests was.** The repair counter
([ADR 0017](0017-invocation-context-and-one-drag-lifecycle.md)) counts only publications where the
heartbeat found a foreground **no event had reported**. Without this rule a heartbeat coalesced with a
genuine event would record a repair that never happened — a false alarm in a counter whose entire
purpose is to make a broken event path visible.

## Consequences

- **The regression is unrepresentable**, rather than unlikely. There is no longer a moment at which a
  stale sample is holding a sequence number.
- **The heartbeat gets simpler.** It is now a timer that says *"publish"* — it holds no sample, makes
  no comparison, and cannot be preempted between sampling and publishing, because it does neither.
- **The repair counter becomes well-defined.** The comparison between "what we just sampled" and
  "what was published" happens inside the ordered region, against a record that cannot change
  underneath it.
- **Atlas owns a thread it did not.** Real cost, and the smallest version of it: one serial context
  doing three short steps, never on the input path.
- **Publication latency gains a queueing term.** Bounded by the sequencer's own work, which is a
  foreground read in the common case. A publication that waits behind another publication is
  publishing a *fresher* sample when it runs, so the delay does not stale the result.
- **The rule generalises, and should be applied wherever a value is sampled and then published.**
  Atomicity of the write says nothing about the age of what is written.

## Alternatives considered

- **Compare-and-swap, rejecting superseded samples.** Correct, and it collapses into this design: on
  rejection the loser must re-sample and retry, so the sample has to be taken inside the retry loop —
  which is "sample inside the serialized region" with a retry loop bolted on. The sequencer is the
  same guarantee without the loop, the backoff, or the question of how many retries.
- **Timestamp each sample and refuse to publish an older one.** Cheaper-looking and wrong in the
  direction that matters: it drops the heartbeat's publication when it loses, so a heartbeat that
  keeps losing never publishes, and the liveness signal — the thing the heartbeat exists for — goes
  quiet while the desktop is busy. Losing races would look identical to Atlas having died.
- **Let the heartbeat skip publishing when an event published recently.** Same defect, stated as a
  policy: it makes liveness a function of desktop activity, which is precisely the coupling
  [ADR 0017](0017-invocation-context-and-one-drag-lifecycle.md) removed when it rejected age-based
  staleness.
- **Have only one path.** Events alone lose the repair; heartbeat alone means the foreground is up to
  one interval stale on every change, which is far too coarse for `zones.snap-focused`. Both paths
  earn their place; what they may not have is independent write access.

## See also

- [ADR 0017](0017-invocation-context-and-one-drag-lifecycle.md) — the publication contract this
  orders.
- [CONDUIT §5.5](../CONDUIT.md#55-what-every-dispatch-carries--the-invocation-context) — the consumer
  side.
- [ATLAS §3.3](../ATLAS.md#33-the-cursor-and-the-foreground-window-are-desktop-facts-too) — the
  producer side.
