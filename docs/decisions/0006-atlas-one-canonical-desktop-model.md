# ADR 0006 — Atlas — one canonical desktop model; modules never enumerate the desktop

Date: 2026-08-08
Status: Accepted

## Context

A window-management module needs to know things about the desktop: which monitors exist, what each
one's usable work area is, what scale factor it runs at, which virtual desktop is active, where a
given window currently sits, and whether it is minimized. The obvious implementation is for the module
to ask Windows directly — `EnumDisplayMonitors`, `EnumWindows`, `GetWindowRect`,
`GetMonitorInfo` — and cache what it needs.

The obvious implementation is wrong in a way that does not show up until there are two consumers, at
which point it is very hard to see.

### The failure story that motivates the rule

The desktop is a laptop panel at 150% scaling plus an external 4K monitor at 100% — an ordinary
configuration, not a corner case.

Zones enumerated monitors when it was enabled and cached each work area. Since then, the user docked
the laptop and moved the taskbar to the left edge of the external display, so monitor 2's work area
has changed. A Restore module, enabled later, enumerated at *its* moment and holds the newer numbers.
Both modules now believe they know where monitor 2's usable region is. They disagree by 48 pixels, and
**neither of them is wrong** — each is correct as of the instant it looked.

The user drags a window into a zone and it lands 48 pixels beneath the taskbar. There is no bug to
find. Every component's arithmetic checks out; the incoherence is *between* two observations taken at
different instants, and nothing in the system records which instant either one came from, so there is
nothing to compare and nothing to blame.

The same shape has a second, nastier form. "What rectangle is this window?" has more than one correct
answer — the geometry rectangle the placement API accepts, and the visible bounds a human perceives,
which differ by the invisible resize border — and the answer is expressed in a coordinate space whose
scale factor belongs to a *specific* monitor. When two components each answer that question
independently, they produce two different, both-plausible rectangles for the same window, and the
disagreement surfaces as a window that is consistently a few pixels off in a way that looks like
sloppiness rather than a contract violation.

## Decision

**Atlas is the single canonical model of the desktop. Modules never enumerate it.**

Atlas exposes a **snapshot**: monitors with their work areas and per-monitor scale factors, the
virtual desktop, and windows represented as an opaque `WindowRef` plus a `WindowInfo`, all carried
together with a **validity generation**. A module takes a snapshot, does its work against that
snapshot, and does not mix facts drawn from different ones. The types, the two-rectangle model, and
the placement-result taxonomy are specified in [ATLAS.md](../ATLAS.md); this ADR decides ownership and
the coherence rule.

The prohibition, stated as flatly as [ADR 0005](0005-conduit-modules-declare-trigger-intents.md)'s:
**a module never calls `EnumWindows` or `EnumDisplayMonitors`, never handles an `HWND`, and never
caches desktop state of its own.**

### The coherence rule, precisely

Any **compound** answer — which monitor a window is on, where a zone's rectangle falls, whether a
window fits a region — must be derived from **one** snapshot, and any rectangle must be attributable
to the frame and scale factor it was expressed in. Compound state is where independent observation
does its damage: two scalars read a millisecond apart are usually harmless, but a *relationship*
between them computed across a topology change is arbitrary rather than approximately right.

This is why a resolved zone set carries the generation it was resolved against. A drag holds a single
snapshot from the moment it starts to the moment it ends — which is safe only because Conduit
guarantees that a drag's end is always delivered if its start was
([ADR 0005](0005-conduit-modules-declare-trigger-intents.md)) — and a topology change during the drag
invalidates the generation rather than silently permitting arithmetic against a desktop that no longer
exists. The two pillars interlock most tightly here, and neither guarantee is much use without the
other.

### Placement results are typed, not boolean

Windows may honor a placement request approximately: a window with a minimum size, a maximized window,
a window whose owner intervenes. A call that returns success while the window went somewhere else is
failure shapes one and two at once — a check that cannot fail, reported as a claim stronger than its
evidence. Atlas therefore reports what actually happened, including "placed, but not where you asked,"
so a module can tell the user something true.

## Consequences

**A module that wants one number takes a whole snapshot.** That is a real cost, and it is bounded by
the resolve-once principle in [COORDINATOR.md](../COORDINATOR.md): the snapshot is taken at a decision
point, not inside a drag loop, and everything after it is comparison arithmetic.

**Atlas gates its consumers.** A module needing a desktop fact Atlas does not yet model waits for Atlas
to model it. This is the same deliberate ordering cost that Conduit imposes, and it is accepted for
the same reason — the alternative is a module reaching around the pillar once, which is the first of
the five reasonable exceptions that end the design.

**Opacity costs a mapping layer.** `WindowRef` being opaque is what keeps Core free of Windows types
([ADR 0003](0003-the-core-shell-split.md)), and the translation between it and a real handle lives in
the Shell adapter where there are no tests. That tax is paid here, deliberately, at one place instead
of in every module.

**Snapshot lifetime becomes something to reason about.** A snapshot can go stale. The trade is not
"staleness eliminated" but "staleness made explicit and detectable" — a generation that no longer
matches is a condition a module can handle, whereas the 48-pixel failure above is a condition nothing
can even notice.

**Nothing here has been observed.** No monitor has ever been enumerated by this project, no window has
ever been moved by it. The Core half compiles and its arithmetic is tested (CI `7aef6ff`, 2026-08-08); no monitor has ever been enumerated. The mixed-DPI behavior
that motivates the entire design is exactly the class of thing that only a real desktop can confirm,
which is what [runbooks/manual-validation.md](../runbooks/manual-validation.md) exists for — and that
runbook has itself never been executed ([TD-9](../TECH_DEBT.md)).

## Alternatives considered

**A live query API instead of snapshots** — `Atlas.GetWindowRect(window)`, `Atlas.MonitorOf(window)`,
each answering from the system at call time. This is the design that looks simpler and reads better at
the call site, and it was the first thing considered. Rejected because it reintroduces the exact
incoherence the pillar exists to remove: two queries a millisecond apart can straddle a monitor
change, a taskbar move, or a DPI change, and **no caller could possibly tell**. A snapshot makes
"these facts are from the same instant" a property of a type rather than a hope about timing.

**Modules enumerate the desktop themselves; Atlas is just a library of geometry helpers.** Rejected
because it divides the problem along the wrong line. The math is the easy half — rectangles, work
areas, scale conversion — and helpers can supply it. The hard half is coherence, and a helper library
cannot enforce coherence over data it did not gather.

**Aggressive internal caching invalidated by window events.** *Partially adopted, deliberately not as
the contract.* Atlas may cache internally and refresh on the window events Conduit delivers — that is
an implementation freedom. What is not permitted is exposing that cache as the module-facing model,
because an invisible cache with an invalidation bug produces the identical 48-pixel failure with
better performance and no way to see it. The generation-stamped snapshot is the contract; caching
lives behind it.

**Expose the real window handle to Core for convenience.** Rejected: it breaks the boundary check in
`tools/doc-audit/audit.py`, and it would make every module's decision logic Windows-only for the sake
of one field — surrendering the testability that [ADR 0003](0003-the-core-shell-split.md) buys, in
exchange for avoiding one indirection.

**Fold Atlas into Conduit as a single "system" pillar.** Rejected: they answer different questions
(*when* something happens versus *where* things are), they have different lifetimes (an event versus a
model), and merging them would produce one subsystem large enough that nobody would be able to say
what belonged in it. Their interlock at the drag boundary is a contract between two named things,
which is exactly the kind of seam this project wants visible.
