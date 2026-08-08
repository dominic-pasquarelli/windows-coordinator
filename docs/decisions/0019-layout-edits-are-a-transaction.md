# ADR 0019 — A layout edit is one transaction over template, occupancy and placement

Date: 2026-08-08
Status: Accepted · Corrects [ADR 0018](0018-layout-editing-grid-split-merge.md)

## Context

[ADR 0018](0018-layout-editing-grid-split-merge.md) described `Grid`, `Split` and `Merge` as pure
functions **over a `LayoutTemplate`**, and separately claimed that merging combines the merged cells'
occupancy rings. (`Grid` is a constructor and stays one — see the Decision; the problem below is
about the two operations that edit an existing layout.) Review of PR #2 established two problems with that, and they are the same problem
seen from two sides.

**A template-only function cannot transform occupancy.** Merge is specified to concatenate rings; a
function whose input and output are both `LayoutTemplate` has no occupancy to concatenate. The
description and the signature disagree, and an implementer would have to invent the missing half.

**Nothing signals that a surviving ring must be re-placed.** Split and merge deliberately *preserve*
a cell id ([ADR 0018](0018-layout-editing-grid-split-merge.md)) while changing the geometry that id
refers to. But `StackMember` is stamped only with the Atlas **topology** generation
([ADR 0016](0016-zone-occupancy-member-states.md)), and a layout edit changes no monitor. So after
splitting a cell in half, its windows keep a zone address that still resolves, under a topology
generation that still matches — and ordinary reconciliation concludes everything is fine while the
windows sit at the old, now-wrong size.

That is the same class of defect as the one ADR 0016 fixed for `PlacedDifferently`: the model was
missing the state that makes a real transition detectable.

## Decision

### 1. Geometry is stamped by a pair, not by topology alone

```csharp
// SKETCH — illustrative, not compiled.
readonly record struct GeometryStamp(int TopologyGeneration, int LayoutRevision);
```

`LayoutRevision` is a monotonic counter on the template, bumped by **every** edit. A `StackMember`
records the `GeometryStamp` it was placed under, and **either component differing makes it
re-placeable**. A monitor change and a layout edit are now the same kind of event to the reconciler:
*the geometry this was placed against no longer exists*.

### 2. An edit returns a transaction, not a template

```csharp
// SKETCH — illustrative, not compiled.
sealed record LayoutEdit(
    LayoutTemplate Template,                          // the new template
    int LayoutRevision,                               // bumped
    IReadOnlyDictionary<string, string> CellRemap,    // old cell id -> surviving cell id
    IReadOnlyList<string> RetiredCellIds,             // never reissued
    ZoneOccupancy Occupancy,                          // already transformed
    IReadOnlyList<PlacementAction> Placements);       // every geometrically affected member
```

**`Split` and `Merge` return one of these, or a refusal. `Grid` does not** — it is a *constructor*,
not an edit, and [ADR 0018](0018-layout-editing-grid-split-merge.md) decided that deliberately. It
takes two integers and returns a fresh `LayoutTemplate` at revision 1; there is no prior template to
remap from, no occupancy to transform, and nothing to re-place. Putting the new layout on a monitor is
a **layout switch**, which releases the previous layout's windows as unassigned — a different
operation with a different consequence.

*The first draft of this ADR listed `Grid` alongside the other two and gave it an occupancy
parameter, which quietly reinstated the grid-as-edit design ADR 0018 had rejected. Corrected here:
the transaction applies to the two operations that genuinely edit a layout in place.*

The six outputs are produced together because they are one decision: you cannot know which members
need re-placing without knowing how cells were remapped, and you cannot remap rings without knowing
which ids survived.

**Every geometrically affected member gets a `PlacementAction`** — including members of a ring whose
cell id did not change. That is the whole point: id stability is what makes stacks survive an edit,
and it is exactly what hides the need to re-place them.

### 3. The transaction is applied in one step, or not at all

Template, revision, occupancy and armed regions move together. A partially-applied edit — new
template with old occupancy, or new geometry with stale armed regions — is the state this decision
exists to make unrepresentable.

## Consequences

- **Split and merge now re-place their windows.** The behaviour a user would assume, which the
  previous design silently did not deliver.
- **The reconciler gets simpler, not more complex.** One stamp comparison covers monitor changes and
  layout edits; there is no separate "was this cell edited?" path.
- **`CellRemap` makes the id rules from ADR 0018 executable** rather than prose. Split's
  first-fragment rule and merge's reading-order rule become entries in a map that tests can assert on
  directly.
- **`LayoutRevision` must be persisted with the template**, or an edit made in one session would look
  identical to a fresh load in the next. It is one integer.
- **An edit is now a bigger unit of work**, which is the cost. It is also the honest size of the
  operation: changing a layout genuinely does change where windows go.
- **Placement actions can still fail individually** (`Refused`, `PlacedDifferently`), and that is
  reported per member rather than failing the edit — the template change has already been decided,
  and an application refusing to resize is not a reason to reject the user's layout.

## Alternatives considered

- **Bump the topology generation on a layout edit.** Tempting: one counter, no new type. Rejected —
  topology generation is Atlas's, and it means *the desktop changed shape*. Overloading it to also
  mean "a module edited its own settings" would make every other consumer of the generation re-place
  geometry for a reason that has nothing to do with them, and would put a module in the position of
  incrementing a pillar's counter.
- **Mint a fresh cell id on every edit**, so the address changes and the existing machinery notices.
  Rejected in [ADR 0018](0018-layout-editing-grid-split-merge.md) for the same reason as here: it
  destroys every stack on every edit, which is the outcome id preservation exists to prevent.
- **Have the module re-place everything after any settings save**, without a stamp. Works, and it
  re-places windows that did not move — visible churn on every unrelated preference change, and it
  makes "which members actually needed this?" unanswerable in a test.
- **Keep the operations template-only and let the caller reconcile afterwards.** This is the current
  design, and the review's point is that it pushes an under-specified step onto the implementer at
  exactly the moment the information needed to do it correctly has already been discarded.

## See also

- [ADR 0018](0018-layout-editing-grid-split-merge.md) — the operations this makes transactional.
- [ADR 0016](0016-zone-occupancy-member-states.md) — the member states this extends.
- [ARCHITECTURE §7](../../src/modules/zones/docs/ARCHITECTURE.md#7-the-layout-designer).
