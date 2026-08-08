# ADR 0015 — Zones are addressed by (monitor, layout, cell), and monitors get a durable key

Date: 2026-08-08
Status: Accepted

## Context

The first Zones design addressed a zone by **cell id alone** — `Cycle(zoneId, …)`,
`ZoneOccupancy: zoneId -> windows`. That is wrong in two ways that only appear on a real desk:

1. **A cell id is unique within a template, not globally.** Templates are reusable, so the same
   `"left"` exists on every monitor using that template. Two monitors running the same layout would
   share one stack.
2. **A monitor can switch layouts.** Keying by (monitor, cell) still collides when two layouts on
   that monitor both define `"left"`, silently re-homing windows into a different layout's zone.

There is a second, worse version of the same problem in the persisted settings. `monitorLayouts` is
keyed by monitor id, and Atlas's `MonitorId` is explicitly **snapshot-local** — "assigned by whatever
enumerated the display". Persisting it means a settings file whose keys are meaningless after a
restart, a driver update, or a dock cycle. The failure is silent: layouts simply stop applying, or
apply to the wrong screen.

## Decision

### 1. A zone is addressed by a triple

```csharp
// SKETCH — illustrative, not compiled.
readonly record struct ZoneAddress(MonitorKey Monitor, string LayoutId, string CellId);
```

Used consistently in occupancy, cycling, reconciliation, armed regions, and pointer dispatch. There
is no API anywhere in Zones that takes a bare cell id.

### 2. Atlas exposes two monitor identifiers, and they are not interchangeable

| | `MonitorId` | `MonitorKey` |
|---|---|---|
| Scope | one snapshot / topology generation | across restarts, docks, driver updates |
| Derived from | whatever the enumeration returned | display device path plus EDID identity (manufacturer, product code, serial) |
| Use for | in-memory lookup within a snapshot | **anything persisted** |
| Cost | free | a little work at topology change; cached per generation |

**Persisted settings key on `MonitorKey`. Nothing persists a `MonitorId`.**

### 3. `MonitorKey` is best-effort, and says so

Two identical monitors with no serial number in their EDID are genuinely indistinguishable by
identity alone. When that happens the key falls back on connector/adapter position, which is stable
until someone swaps cables.

So a key carries its **confidence**: `Stable` (EDID identity including a serial) or `Positional` (a
fallback that a cable swap can invalidate). A module that matches a `Positional` key may be wrong, and
the contract is that **Zones falls back to the default layout and surfaces that it did so** rather
than applying somebody else's layout to the wrong screen. Guessing quietly is the one option ruled
out.

## Consequences

- **Two monitors running the same template no longer share a stack** — the failure that would have
  looked like windows teleporting between screens.
- **Switching layouts on a monitor does not re-home windows** into an unrelated zone that happens to
  share a cell id. Occupancy for the inactive layout simply is not addressed; reconciliation
  ([ADR 0016](0016-zone-occupancy-member-states.md)) decides what happens to it.
- **Tests must cover the same template on two monitors.** It is the case the old model could not
  represent, so it is the case that proves the new one.
- **Atlas grows a second identifier**, which is real surface for a pillar whose value is being small.
  Paid because the alternative is a settings file that silently rots — and because the distinction is
  genuine rather than cosmetic: one is a handle, the other is an identity.
- **`Positional` confidence will occasionally produce a wrong-looking result** (dock into a different
  port, get the default layout). That is the honest outcome and it is visible, which is what makes it
  acceptable.
- Zone addresses appear in dispatch payloads and armed-region tokens, so they must be cheap to
  compare. A record struct over three small values is; a string concatenation would not be, and is
  explicitly not the design.

## Alternatives considered

- **Globally unique cell ids** (a GUID per cell, minted at authoring time). Rejected: it makes a
  template non-reusable in practice — copying a template to a second monitor would have to rewrite
  every id, and layouts stop being shareable artifacts. It also makes the settings file unreadable by
  a human, which matters for a personal tool whose settings someone will hand-edit.
- **(monitor, cell) without layout.** Rejected: collides whenever two layouts on the same monitor
  share a cell id, which is the normal case since layouts are built from the same grid vocabulary.
- **Persist `MonitorId` and accept the rot.** Rejected. The failure is silent and looks like the tool
  being broken; a user cannot tell "your layouts are gone" from "this tool is unreliable".
- **Ask the user to name each monitor.** Genuinely considered — it is what several tools do, and it
  sidesteps EDID entirely. Rejected as the *primary* mechanism because it front-loads configuration
  onto someone who has not used the tool yet. It stays available as the escape hatch when
  `Positional` confidence is not good enough, which is the right place for it: a fix for a problem
  you have, not a form you fill in first.

## See also

- [ATLAS §3](../ATLAS.md#3-the-model) — where both identifiers live.
- [ADR 0016](0016-zone-occupancy-member-states.md) — the occupancy model this addresses into.
- [ARCHITECTURE §2](../../src/modules/zones/docs/ARCHITECTURE.md#2-the-occupancy-model--the-heart-of-the-module).
