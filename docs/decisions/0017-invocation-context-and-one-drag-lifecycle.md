# ADR 0017 — Every dispatch carries an invocation context, and a drag has exactly one lifecycle

Date: 2026-08-08
Status: Accepted · **Corrected twice after review of PR #2** — (1) the context is captured at
**recognition**, not sampled at dispatch, and what is capturable differs by source; (2) a hotkey chord
is an **`OsCallback`** origin, not a hook, and cached-fact staleness is a **publisher-liveness** check
rather than an age threshold. See §1 below and
[CONDUIT §5.5](../CONDUIT.md#55-what-every-dispatch-carries--the-invocation-context).

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

### 1. Every dispatch carries an `InvocationContext`, **captured at recognition**

```csharp
// SKETCH — illustrative, not compiled.
enum ContextOrigin { Hook, OsCallback, UserInterface, Timer }

sealed record InvocationContext(
    ContextOrigin Origin,
    long CapturedAtTicks,            // monotonic, at recognition
    Point? CursorPosition,           // PhysicalVirtualScreen; null for Timer
    WindowRef? ForegroundWindow,     // null when there is none, or none resolvable
    int TopologyGeneration,
    long? FactsSequence);            // Hook origin: which DesktopFacts publication it read
```

**Capture is at recognition, not at dispatch.** *This ADR first said "sampled at dispatch", which is
wrong and worth recording as wrong.* [CONDUIT §5.3](../CONDUIT.md#53-the-hand-off) puts recognition on
the hook or OS callback and dispatch on a worker, with a queue between them. A context sampled on the
worker describes the world after an unbounded queue delay — precisely the interval in which the user
moved the mouse and switched windows. The draft asserted both "sample at dispatch" and "the state
when it happened", and those cannot both hold.

**Captured / derived / reconstructed.** *Captured* means read at recognition. *Derived* means a pure
function of captured facts — `MonitorUnderCursor` from a captured cursor point at a captured
generation — and may be computed later, because *when* changes no answer. *Reconstructed* means
reading a live source on the worker and presenting it as event-time truth; that is what is forbidden.

**What is capturable differs by source, so `Origin` is part of the type.** A hook-thread recognizer is
inside [CONDUIT §5.1](../CONDUIT.md#51-the-hard-constraint)'s budget and **may not call Atlas at all**
— context capture does not earn an exemption from §5.2's forbidden list. It takes the cursor and the
timestamp from the event structure, and everything else from an **atomically-published
`DesktopFacts`** record — one reference read, using §3.6's publication contract rather than a second
mechanism. Window events and tray actions run where a live Atlas point sample is both allowed and
accurate, so they take one. A **schedule tick has no event-time cursor at all**: those fields are null
and `Origin` says why, rather than fabricating "wherever the mouse happens to be".

**`Hook` is exactly the two pointer-driven kinds — and a hotkey chord is not one of them.**
*A first draft of this ADR listed the chord under `Hook` and said its cursor came from the event
structure; neither `WM_HOTKEY` nor `KBDLLHOOKSTRUCT` carries a cursor, so that row was describing a
mouse hook and labelling it "keyboard or mouse".* [CONDUIT §3.1](../CONDUIT.md#31-hotkey-chord) already
decided that plain chords are **kernel registrations, not hooks**, so they arrive on a message loop
where a live point sample is permitted and correct: **chords are `OsCallback` origin.** That leaves
`Hook` as the gesture (§3.5) and pointer gesture (§3.6) — both mouse-driven, both carrying the cursor
in the event structure — so the capture rule holds by construction. If a future intent ever needs a
**keyboard** hook, it captures a null cursor and Conduit must refuse to bind a cursor-dependent
capability to it at registration time.

**"Focused" means** the foreground top-level window as the OS reports it, resolved to a `WindowRef`,
or `null`. Null is ordinary, not exceptional: the desktop itself can have focus, and a secure or
elevated window may not be resolvable.

**A cached fact names its publication, not its age.** *The first draft marked a context `ContextStale`
when the facts' age exceeded a bound, which is wrong for an event-driven record:* `DesktopFacts`
republishes on change, so an hour-old record on a quiet desktop is perfectly correct and an age
threshold would eventually refuse every hook gesture *because nothing had gone wrong*. A recent record
can equally be wrong if a publication was missed. So the context carries `FactsSequence`, staleness is
a **liveness check on the publisher** (a heartbeat and a monotonic sequence — see
[CONDUIT §5.5](../CONDUIT.md#55-what-every-dispatch-carries--the-invocation-context)), and correctness
is established by comparing `TopologyGeneration` against a snapshot rather than by counting ticks.

**Dispatch stamps `DispatchedAtTicks` and nothing else**, so a module can refuse work that went cold
in the queue without reading a clock — and without any captured field being rewritten.

**Freshness against a full snapshot remains the caller's check.** A module that reads an Atlas
snapshot compares `TopologyGeneration`; a mismatch means refuse, not proceed on mixed data.

**Refusals** are values, as everywhere else: `NoForegroundWindow`, `ForegroundNotManageable`
(elevated or system), `NoMonitorUnderCursor`, `NoCursorForOrigin`, `ContextStale`.

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
- **Conduit now depends on Atlas** for the point sample and the published facts, where before the
  pillars were independent. This is the significant cost. Accepted because the alternative is worse in
  both directions: Conduit reading the desktop itself would duplicate the truth Atlas exists to hold
  single, and pushing the problem to modules would put desktop queries in every module that wants a
  cursor position. The dependency is one-way and narrow — Conduit asks and does not interpret.
- **The point sample must be genuinely cheap**, because it runs on every non-hook recognition. It is a
  handful of reads, not an enumeration, and it is explicitly *not* a snapshot: a module that needs the
  full desktop still asks Atlas for one and checks the generation.
- **Atlas gains a publication duty it did not have**: an immutable `DesktopFacts` record, republished
  on foreground and topology change **and on a heartbeat**. Real work, and it is the price of a
  hook-thread recognizer being able to capture a foreground window without calling anything. It reuses
  ADR 0013's swap contract rather than inventing a second way to hand data to the hook thread.
- **The heartbeat is the part that looks like overhead and is not.** Without it, "nothing changed" and
  "the publisher died" are the same observation, and the only available staleness test is content age
  — which for an event-driven fact is not a staleness test at all. A timer republishing an unchanged
  immutable record is a cheap price for making the difference detectable.
- **Two contexts of different origins are not interchangeable**, and a module that ignores `Origin`
  will eventually read a null cursor from a schedule tick. Making the origin part of the type is what
  turns that into a compile-time-visible question instead of a null-reference at 2am.
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
- **Sample the context on the dispatch worker** — the first draft of this ADR. Rejected above: it puts
  the read on the far side of the queue, and the payload would then describe a moment nobody asked
  about while claiming to describe the moment of the event.
- **Let the hook thread call `GetForegroundWindow` directly.** It is widely believed to be cheap.
  Rejected on [CONDUIT §5.2](../CONDUIT.md#52-what-may-happen-inside-a-hook-callback)'s own terms: an
  operation whose *worst* case is not known is not permitted on that path, and "usually fast" is
  exactly the reasoning that budget exists to overrule. The published record makes the read a
  reference load, whose worst case is known.
- **Give every origin the same fields and fill the gaps with defaults** — a zero cursor for a schedule
  tick. Rejected: a fabricated fact is indistinguishable from a real one at the point of use, and
  `(0, 0)` is a real screen coordinate.
- **Refuse a context whose cached facts are older than a threshold.** The first version of this
  decision. Rejected: `DesktopFacts` is event-driven, so age measures *how quiet the desktop has been*
  and not *whether the record is right*. It fails in both directions — refusing correct records on an
  idle machine, accepting a stale one whose update was dropped a millisecond ago — and its false
  positives grow with uptime, which is the worst possible shape for a bug to have.
- **Poll the desktop on a timer instead of publishing on change**, so the record is always recent.
  Rejected: it burns work continuously to answer a question nobody asked most of the time, and it
  still cannot promise the record is right at the instant a gesture fires. The heartbeat is the small
  version of this — it proves the publisher is alive without pretending to be a live read.
- **Keep both drag streams and define an ordering between them.** Possible, and it means specifying
  cross-stream ordering guarantees for the whole taxonomy to solve one consumer's problem. Collapsing
  to one stream is smaller and removes the question instead of answering it.

## See also

- [CONDUIT §3](../CONDUIT.md#3-the-trigger-intent-taxonomy) — the taxonomy this changes.
- [ATLAS §3](../ATLAS.md#3-the-model) — where the cursor and foreground window are defined.
- [ARCHITECTURE §6](../../src/modules/zones/docs/ARCHITECTURE.md#6-drag-to-snap) — the module-side view.
