# ADR 0020 — An absent monitor makes a stack dormant, and a displacement degrades to a stack

Date: 2026-08-08
Status: Accepted · Completes [ADR 0016](0016-zone-occupancy-member-states.md)

## Context

[ADR 0016](0016-zone-occupancy-member-states.md) gave a stack member state and made reconciliation
generation-aware, which closed five transitions that previously had no representable answer. Review
of PR #2 found that it left four more, in two clusters.

**Cluster 1 — a removed monitor has two contradictory answers.** ADR 0016 says a stamp mismatch marks
a member `AwaitingReplacement` and *re-places it against the re-resolved zone*. The Zones design also
says a zone address that no longer exists releases its windows as unassigned. Unplug a monitor and
both apply: the stamp changed, and the address stops resolving. One says re-place, the other says
release, and there is nothing to re-place *to* — the zone's monitor is not in the snapshot. Worse,
"release" is the outcome
[ARCHITECTURE §5.1](../../src/modules/zones/docs/ARCHITECTURE.md#51-why-the-stamp-rule-matters-more-than-it-looks)
exists to prevent: undocking a laptop would discard every stack on the external screen.

**Cluster 2 — `stackOnDrop = false` is defined for exactly one shape of drop.** ADR 0016 §6 specified
the swap for *one* occupant coming from *nowhere in particular*, with the displacement assumed to
succeed. Three real cases fall outside it:

1. the destination ring already holds **two or more** windows — which one is displaced, and does the
   rest of the ring survive?
2. the incoming window came **from another zone Zones manages** — the "previous zone" it would send
   the occupant to is a live ring with its own members and its own order;
3. the displaced window's placement is **refused** — the case the whole rule exists to avoid, since a
   window that cannot be moved out is a window sitting invisibly underneath the new one.

## Decision

### 1. A stack whose monitor is absent is **dormant**, not unassigned

Dormancy is a property of the **address**, not of each member: a stack is dormant when its
`ZoneAddress.Monitor` does not resolve in the current snapshot. For a dormant stack, reconciliation:

| Does | Does not |
|---|---|
| Drop members whose window is no longer in the snapshot (a closed window needs no geometry to detect) | Run the bounds test — Windows itself relocated those windows when the monitor went away |
| Keep the ring and its order | Place anything, or mark anything `AwaitingReplacement` |
| Leave the zone out of the armed region set — it has no rectangle, so this falls out rather than being a rule | Release members as unassigned |

**Reactivation** happens when the `MonitorKey` resolves again: every member becomes
`AwaitingReplacement` and is re-placed under the current `GeometryStamp`, which is exactly the
existing path.

**Reactivation requires the same confidence as applying a layout.** A `Positional`-only match — one
[ADR 0015](0015-zone-addressing-and-durable-monitor-identity.md) says may be the wrong physical screen
— does **not** wake a dormant stack. The monitor gets the default layout and says so, and the dormant
stack keeps waiting for a match good enough to trust. Guessing here would fling a stack of windows
onto a screen the user never associated with them.

**Unbounded growth is already bounded**: occupancy is session-scoped
([ADR 0012](0012-zones-stacking-model.md)), so a monitor that never returns costs a dictionary entry
until exit.

**"Unassigned" keeps its own, narrower meaning:** the monitor is present and the zone genuinely no
longer exists on it, because the user switched that monitor to a different layout. The windows are
visible, on a screen we can see, in a region nobody has claimed. That is a different situation from a
screen that is not there, and conflating the two is what produced the contradiction.

### 2. `stackOnDrop = false` is a rule about drops, not an invariant about depth

**It displaces the front member only.** The rest of the destination ring is untouched.

This must be stated because the intuitive reading — "this zone holds one window" — is wrong and would
be written as an assertion by the first person to implement it. A ring of two or more can exist with
the setting off: the user may have built it with the setting on, or via `zones.snap-focused` bound to
a chord, or changed the setting afterwards. The setting governs what a **drop** does; it never
retroactively unstacks anything, and nothing may assume depth ≤ 1.

### 3. A swap between two managed zones exchanges ring positions

When the incoming window came from another zone Zones manages, the displaced occupant takes **the
exact ring position the incoming window vacated**. Both rings keep their depth, both keep their order,
and the operation is a genuine exchange rather than an append that quietly reorders the source.

When the source and destination are the same zone, there is no displacement at all: the window moves
to the front of its own ring.

When the incoming window was not managed, the occupant goes to the incoming window's **pre-drag
bounds**, which Zones knows because it owned the drag.

### 4. A refused displacement degrades to a stack, never to an orphan

If placing the displaced occupant is `Refused` — an elevated window, a window that will not move —
the occupant **stays in the destination ring, behind the incoming window**, and the outcome is
recorded so the surface can say what happened.

`PlacedDifferently` is not a failure and needs no special case: the occupant is a member of its new
zone, marked `Oversized`, exactly as after any other placement.

The reasoning is that the setting's entire purpose is to avoid a hidden unmanaged window, so its
failure mode must not be a hidden unmanaged window. Stacking violates the preference; orphaning
violates the point.

## Consequences

- **Undocking stops being destructive.** The stacks on an absent screen survive and come back, which
  is the behaviour that makes per-monitor layouts worth having on a laptop at all.
- **Dormancy costs no new member state.** It is derived from the address against the snapshot, so
  there is nothing to keep in sync and no way for a member to be "dormant" while its stack is not.
- **A conservative reactivation rule means a dormant stack can stay dormant on a monitor the user
  believes is the same one.** Accepted, and it is the same trade
  [ADR 0015](0015-zone-addressing-and-durable-monitor-identity.md) already made: doing nothing
  visible is recoverable, moving windows onto the wrong screen is not.
- **`stackOnDrop = false` is now fully defined**, including the case where it cannot be honoured. Four
  named tests replace four arguments.
- **The setting is weaker than its name suggests**, and saying so is the cost of it being honest. It
  is a drop policy, not a depth constraint.
- **A degraded displacement produces a stack the user did not ask for.** Visible, cyclable, and
  explicable — which is strictly better than the alternative, and it is surfaced rather than silent.

## Alternatives considered

- **Treat an absent monitor as a layout change and unassign.** Simple, and it throws away the user's
  arrangement at the exact moment they are least able to recover it — plugging the monitor back in
  would not restore anything. Rejected on the same grounds as ADR 0016's case 4.
- **Re-home a dormant stack onto a remaining monitor.** Tempting, since Windows has already moved the
  windows there. Rejected: it silently rewrites the user's intent, and undocking-then-docking would
  leave every stack on the wrong screen with no way back. Windows moved the *windows*; it did not
  change what the user meant.
- **Wake a dormant stack on a positional match anyway.** Rejected — see §1. The one thing worse than a
  stack that stays asleep is a stack that wakes onto a stranger's screen.
- **Displace the whole destination ring** when `stackOnDrop = false`. Rejected: three windows flying
  to one origin, from a gesture the user reads as "put this here".
- **Refuse the drop when the destination is occupied and the setting is off.** ADR 0016 already
  rejected it: the drag visibly does nothing, which reads as a broken tool.
- **Roll back the whole drop when the displacement is refused.** Consistent, and it converts a
  partially-successful gesture into a total no-op for a reason the user cannot see. Degrading to a
  stack keeps the thing they actually asked for.
- **Add a `Displaced` member state for the orphan case.** This is what the design said before, and it
  names the bad outcome instead of removing it. With §4 there is no orphan left to name.

## See also

- [ADR 0016](0016-zone-occupancy-member-states.md) — the member states and the five cases this
  completes.
- [ADR 0015](0015-zone-addressing-and-durable-monitor-identity.md) — `MonitorKey` and its confidence,
  which decides reactivation.
- [ADR 0019](0019-layout-edits-are-a-transaction.md) — per-member placement outcomes, applied here to
  a displacement.
- [ARCHITECTURE §5](../../src/modules/zones/docs/ARCHITECTURE.md#5-reconciliation--where-the-bugs-would-otherwise-live)
  and [§6](../../src/modules/zones/docs/ARCHITECTURE.md#6-drag-to-snap) — the module-side view.
