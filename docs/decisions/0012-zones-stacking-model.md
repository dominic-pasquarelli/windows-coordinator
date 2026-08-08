# ADR 0012 — A zone holds an ordered stack, realised as z-order

Date: 2026-08-08
Status: Accepted

## Context

Zones (M1) divides a monitor into zones and snaps windows into them. The feature that makes it worth
building rather than reinstalling PowerToys is that **a zone can hold more than one window**: drop a
second window on an occupied zone and it joins a stack, and the wheel cycles which one is in front.

That is one sentence of product and several decisions of architecture. Three of them are
non-obvious, cannot be deferred without shaping the data model wrongly, and are cheap to get right
now and expensive to change once settings files exist on a machine.

## Decision

### 1. A zone owns an ordered list of windows, front to back

Occupancy is `zone id -> ordered list of WindowRef`. Index 0 is the visible one. Invariants: a
window is in at most one zone across all monitors; order is stack order and only cycling reorders it.

### 2. Stacking is z-order. Nothing is minimised, hidden, or altered

Every window in a stack is placed at the same rectangle. The front one covers the others; cycling
raises the next. Windows behind remain ordinary open windows — present in Alt-Tab, present on the
taskbar, unmodified in every respect except which pixels are on top.

### 3. Occupancy is *intent*, reconciled against the desktop — not a cache of it

Zones records what the user asked for. Atlas reports what is true. When they disagree — a window was
closed, an application moved itself, the user dragged a window out by hand — a pure `Reconcile`
function resolves it, with a fixed rule: **the desktop wins about what exists and where things are;
the user's intent wins about where things belong.**

### 4. Stack membership is session-scoped and is not persisted

A restart starts with empty stacks. Layouts persist; membership does not.

## Consequences

- **Cycling is one call and touches nothing else.** No animation, no state change, no restore that
  can fail.
- **Reconciliation becomes the most test-worthy function in the module**, and it is pure — no
  desktop, no clock, no I/O. Every disagreement listed in
  [ARCHITECTURE §5](../../src/modules/zones/docs/ARCHITECTURE.md#5-reconciliation--where-the-bugs-would-otherwise-live)
  is a test case rather than an open question.
- **Windows behind the front one are still visible to the rest of the system.** Alt-Tab shows them;
  the taskbar shows them; clicking one raises it, which is a perfectly good second way to cycle. This
  is a consequence to explain, not to hide.
- **A stacked window that will not resize leaves the one behind it peeking out** — an application
  exercising a legitimate right, surfaced through Atlas's `PlacedDifferently` and never fought.
- **Stacks are invisible without UI.** In M1 the drag overlay draws each zone's depth, and that is
  the only affordance. Tracked as a dragon with the tab strip as its named successor.
- **Membership not surviving restart is a real limitation** and will occasionally be annoying. It is
  also the honest option: `WindowRef` does not survive a restart either, so anything else is a
  heuristic.

## Alternatives considered

- **Minimise the windows behind the front one.** Rejected on five counts: it animates, so cycling
  becomes slow and visually noisy; it changes a window state the user did not ask to change; it
  disturbs Alt-Tab and taskbar ordering; applications behave unpredictably when minimised out from
  under them; and restoring is a second opportunity to fail. Z-order costs one call.
- **Hide the windows behind (`SW_HIDE` or moving them off-screen).** Worse than minimising. A hidden
  window disappears from Alt-Tab and the taskbar, so a window the user put in a stack becomes
  genuinely unreachable if Coordinator crashes — the module would be able to lose someone's work
  behind an invisible door. Disqualifying for a tool whose first rule is not to make the desktop
  worse.
- **Occupancy as a cache of observed desktop state.** Rejected: it turns every disagreement into a
  bug with no correct answer, because there is no recorded intent to reconcile against. The moment an
  application moves its own window you must choose between "the model is wrong" and "the desktop is
  wrong", and without intent, neither is defensible.
- **Persist stack membership across restart by re-associating windows heuristically** (process path,
  window title, class name). Rejected for M1, and it is the closest call here. Titles change while an
  application runs; several instances of the same process are indistinguishable by path; a partial
  match restores *some* of a stack, which is more confusing than none. The failure is silent and
  looks like the tool being flaky. Revisit if daily use proves stacks are rebuilt often enough to be
  a chore — that is the recall hook.
- **Let a window belong to several zones.** Rejected: there is no such thing on the desktop. A window
  is in one place.

## See also

- [ARCHITECTURE §2](../../src/modules/zones/docs/ARCHITECTURE.md#2-the-occupancy-model--the-heart-of-the-module) — the model this decision fixes.
- [ADR 0013](0013-the-pointer-gesture-trigger-kind.md) — how cycling is triggered.
- [ADR 0014](0014-atlas-explicit-raise-and-activate.md) — how the raise is actually performed.
