# ADR 0014 — Atlas gains explicit raise and activate, and treats the foreground lock as a refusal

Date: 2026-08-08
Status: Accepted · Extended by [ADR 0016](0016-zone-occupancy-member-states.md), which adds `Show` (restore-if-minimised, then raise)

## Context

Cycling a Zones stack ([ADR 0012](0012-zones-stacking-model.md)) means bringing the next window to
the front. Atlas today refuses to do that:

> [ATLAS §7.2](../ATLAS.md#72-what-atlas-will-not-do): *It will not steal focus as a side effect of
> placement. Moving a window is not activating it. It will not reorder z-order beyond what the move
> itself requires.*

Both sentences remain right, and neither is in the way — they forbid these things **as side effects**
of a placement. A module that asks Atlas to move a window has not asked for its focus to change, and
silently changing it is exactly the kind of surprise that rule exists to prevent. Cycling is
different in kind: it is an explicit, separately-requested operation whose *entire purpose* is to
change what is in front.

There is also a technical problem that shapes the answer, and it is the largest unknown in M1.
Windows restricts `SetForegroundWindow`: a process that has not recently received input generally
cannot take foreground, and the call fails quietly or merely flashes a taskbar button. Coordinator
would be activating **another application's** window in response to input delivered over a **third**
application's window. Whether the foreground lock permits that is not knowable from documentation
with any confidence — it depends on how Windows attributes the input Coordinator's hook consumed.

## Decision

**Add two explicit operations to the Atlas placement contract, and separate them deliberately.**

| Operation | What it does | Expected reliability |
|---|---|---|
| `Raise(window)` | Change z-order so the window is in front of its overlapping siblings. **Does not** change focus | Needs no foreground rights. Expected to work |
| `Activate(window)` | Raise, then request foreground | **May be refused by the OS.** A first-class refusal, never a silent no-op |

**`Raise` is the default for cycling; `Activate` is opt-in** (`zones.activate-on-cycle`, default
off).

**A refused activation is `Refused(ForegroundLocked)`** — a new member of the refusal set in
[ATLAS §7.3](../ATLAS.md#73-what-cannot-be-done-at-all-and-why), alongside `Refused(Elevated)` and
the rest. It joins the existing discipline: the platform tells the truth about what it could not do,
rather than returning success and leaving the caller with a wrong belief.

**§7.2 is amended, not overturned.** The sentences stand as written about *placement*. What changes
is that raising and activating become operations a caller can request by name — which is the
distinction §7.2 was always drawing, now made explicit because there is a caller.

## Consequences

- **Cycling works without focus rights.** The default path changes z-order and nothing else, so the
  feature does not depend on winning an argument with the foreground lock.
- **Not stealing focus is probably better behaviour anyway.** You cycle to *see* a window; you click
  it when you want to type in it. Focus that follows the wheel is the kind of thing that feels clever
  for a day and then eats a keystroke into the wrong window.
- **`activate-on-cycle` is honest about being unreliable.** Its setting description says the OS may
  overrule it, and a refusal is surfaced rather than swallowed. A toggle that silently does nothing
  on some machines is worse than one that explains itself.
- **This is the first thing to validate on real hardware** (`Z-4` in
  [manual-validation.md](../runbooks/manual-validation.md)) — cheap to test, and it decides whether
  an opt-in setting is worth keeping at all.
- **Atlas's surface grows by two operations**, which is a real cost for a pillar whose value is being
  small. Paid because the alternative is worse (below), and bounded: these are the only two, and both
  are explicit rather than modal.
- **A raise still cannot promise the window ends up visible.** An always-on-top window belonging to
  another application will still cover it. Reported honestly rather than retried.

## Alternatives considered

- **Let Zones do it.** Disqualified by [principle 4](../COORDINATOR.md#7-non-negotiable-principles):
  a module never touches the desktop. It is also exactly how coherence rots — once one module owns a
  window-manipulation call, the boundary is a suggestion.
- **Fold raising into `Place` as a flag.** Rejected. It reintroduces as a parameter the thing §7.2
  forbids as a side effect, and a `raiseAfterPlacing: true` argument is precisely the kind of quiet
  default that ends up set everywhere for reasons nobody remembers. Two named operations cannot be
  set by accident.
- **Always activate; treat raise-only as the special case.** Rejected on both reliability (it bets
  the headline feature on the foreground lock) and behaviour (focus theft on every wheel tick).
- **Work around the foreground lock** — the `AttachThreadInput` trick, or synthesising input to make
  Windows believe Coordinator is the active application. Rejected: it is fighting a deliberate OS
  protection, it is exactly the kind of thing that breaks on a Windows update, and it makes
  Coordinator the sort of program that manipulates the input queue behind the user's back. If
  activation is refused, that is an answer, and the default path does not need it.
- **Minimise the other windows instead of raising this one.** Rejected in
  [ADR 0012](0012-zones-stacking-model.md) for independent reasons; it would also mean N calls
  instead of one, each able to fail separately.

## See also

- [ATLAS §7](../ATLAS.md#7-the-placement-contract) — the contract this extends.
- [ADR 0012](0012-zones-stacking-model.md) — the stacking model that needs it.
- [ARCHITECTURE §4.2](../../src/modules/zones/docs/ARCHITECTURE.md#42-atlas--explicit-raise-and-the-foreground-lock-dragon) — the module-side view and the dragon.
