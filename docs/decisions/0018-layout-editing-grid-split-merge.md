# ADR 0018 — Layout editing is three pure operations, and cell ids survive them

Date: 2026-08-08
Status: Accepted · **Corrected by [ADR 0019](0019-layout-edits-are-a-transaction.md)** — the three
operations return a `LayoutEdit` transaction (template + revision + remap + retired ids + transformed
occupancy + placements), not a bare `LayoutTemplate`. The id rules below stand unchanged; the
signature and the hand-off in *"Editing is a settings-save"* are superseded.

## Context

Authoring a layout by typing fractions is not a thing anyone will do twice. The owner asked for three
editor affordances:

1. type a horizontal and vertical count and get that grid;
2. **split** an existing cell;
3. **merge** cells back together.

All three are geometry, so all three belong in Core where they can be tested with no desktop. The
part that needs deciding is not the arithmetic — it is what happens to **cell ids**, because a cell id
is a permanent contract ([ADR 0012](0012-zones-stacking-model.md),
[ADR 0015](0015-zone-addressing-and-durable-monitor-identity.md)): occupancy addresses it, and
settings reference it. Editing a layout changes the set of cells, so every edit is also a question
about identity, and getting it wrong means a user's stacks scatter every time they adjust a layout.

Merge has a second problem: **not every selection can be merged.** Two cells combine into a rectangle
only if they tile their bounding box exactly.

## Decision

Three pure operations, each returning a result that can be a **refusal**.

> **Amended by [ADR 0019](0019-layout-edits-are-a-transaction.md), for `Split` and `Merge` only.** As
> first written, both took and returned a `LayoutTemplate` — which cannot express the occupancy
> consequences this ADR goes on to describe (merge concatenating rings), and cannot signal that a
> surviving cell's stack needs re-placing. They now take the template *and* the occupancy over it, and
> return a `LayoutEdit`. Read the id rules below as the content of `CellRemap` and `RetiredCellIds`.
>
> **`Grid` is unchanged and remains a constructor** — see the last entry under *Alternatives
> considered*, which is the decision that keeps it one. It takes two integers, returns a fresh
> template, and has no occupancy, no remapping and no placements, because it has no prior template to
> remap from.

### `Grid(columns, rows)` — a constructor, not an edit

Builds a template of `columns × rows` uniform cells. Ids are positional and stable: `r{row}c{col}`,
zero-based. Refuses `columns < 1`, `rows < 1`, or a product beyond a sanity cap.

**It takes no existing template and no occupancy**, so it produces no cell remapping, no retired ids
and no placement actions. Its result is a new layout in the library; applying it to a monitor is a
**layout switch**, which releases the previous layout's windows as unassigned. That is deliberately a
different operation from the two below — see the final alternative.

### `Split(template, cellId, axis, fraction = 0.5)`

Replaces one cell with two covering exactly the same rectangle. **The original id stays on the
first fragment** (left for a vertical split, top for a horizontal one); the second gets a fresh id.
Refuses an unknown cell, or a fraction that would produce a zero-width fragment.

Consequence for occupancy: the stack stays with the first fragment. Not arbitrary — the first
fragment shares the original's origin, so windows are closest to where they already were.

### `Merge(template, cellIds[])`

Replaces two or more cells with one covering their bounding box. **Valid only if the selected cells
tile that bounding box exactly** — no gap, no overlap. Refuses `NotContiguous` otherwise, naming the
uncovered or doubly-covered area.

**The survivor keeps the id of the first cell in reading order** (topmost, then leftmost). The other
ids are **retired**: recorded in the template's `retiredCellIds` and never reused, because a reused id
would silently point an old saved binding at a different region.

Consequence for occupancy: the retired cells' stacks are **appended to the survivor's ring**, in
reading order. The windows were adjacent and are now genuinely one zone, so keeping them is the
result that matches what the user did; discarding them would punish editing.

### Editing is a settings-save, not a live operation

Layout edits happen at authoring time and go through the ordinary settings path.

> **This paragraph only — corrected by [ADR 0019](0019-layout-edits-are-a-transaction.md).** The
> rest of this ADR stands. It originally continued:
> *"Occupancy is then reconciled against the new template by ADR 0016's reconciler, with cells that
> vanished entirely releasing their windows as unassigned."* That hand-off does not work — the
> reconciler cannot detect a cell whose id survived but whose rectangle changed, because no monitor
> changed and the address still resolves. The edit itself now transforms occupancy and emits the
> placements, and the reconciler sees only surviving cells. It is still a settings-save; what is saved
> is the whole transaction, including the bumped `LayoutRevision`.

## Consequences

- **Layouts become editable without hand-writing fractions**, which is the entire point.
- **All three operations are pure functions over values**, so the editor's *decisions* are host-tested
  and the UI is only a way to invoke them — the Core/Shell split doing real work again.
- **Merge validity is a genuinely interesting predicate** (does this selection tile its bounding
  box?) and it is exactly the kind of thing that is easy to get subtly wrong and cheap to test
  exhaustively on small grids.
- **Editing preserves stacks wherever the geometry survives**, so adjusting a layout does not scatter
  windows. This is the difference between an editor you use and one you avoid.
- **`retiredCellIds` grows monotonically** in a template that is edited a lot. It is a list of short
  strings, and the alternative — reusing ids — silently repoints saved state, which is the failure
  this project treats as unacceptable.
- **Overlapping templates can still be authored by hand** (ARCHITECTURE permits overlap and gaps), and
  `Merge` will refuse on them. That asymmetry is deliberate: the editor produces tilings, and hand
  authoring stays as expressive as it was.
- **`Split` on a cell inside an overlapping template is still well-defined** — it only ever subdivides
  one cell's own rectangle — so the two authoring paths do not conflict.

## Alternatives considered

- **Mint a fresh id for every cell on every edit.** Simplest to implement and it destroys every stack
  and every saved per-zone setting on each edit. Rejected outright.
- **Let `Merge` take a rectangle and absorb whatever it covers.** Friendlier at the UI, and it makes
  partial coverage ambiguous — does a half-covered cell shrink, split, or vanish? Refusing a
  non-tiling selection is the honest version, and the UI can still offer rubber-band selection that
  resolves to a cell set.
- **Auto-repair a non-contiguous merge** by taking the bounding box and deleting whatever was inside.
  Rejected: it silently destroys cells the user did not select, which is data loss dressed as
  convenience.
- **Keep the ring of a retired cell but leave it unassigned.** Rejected: the windows are sitting in a
  region that is now part of the survivor, so leaving them unmanaged means they look stacked but do
  not cycle — the worst of both.
- **Make the grid operation an edit rather than a constructor** (apply a grid to an existing
  template). Rejected for M1: reconciling an arbitrary existing template against a fresh grid is a
  much harder identity problem than the three operations above, and typing a grid is nearly always
  something you do when starting a layout, not when refining one. Revisit if refining-into-a-grid
  turns out to be a real habit.

## See also

- [ADR 0019](0019-layout-edits-are-a-transaction.md) — **read this with the above**; it corrects the
  operation signatures and the occupancy hand-off.
- [ADR 0015](0015-zone-addressing-and-durable-monitor-identity.md) — what a cell id is part of.
- [ADR 0016](0016-zone-occupancy-member-states.md) — the member states an edit stamps.
- [ARCHITECTURE §7](../../src/modules/zones/docs/ARCHITECTURE.md#7-the-layout-designer) — the module-side view.
