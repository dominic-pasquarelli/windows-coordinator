# ADR 0004 — Module is the modular unit; module docs co-locate, the ADR log stays unified

Date: 2026-08-08
Status: Accepted

## Context

[ADR 0001](0001-adopt-the-axon-documentation-and-operating-protocols.md) ports a documentation system
whose central placement rule is *documentation follows its code*. That rule is only meaningful once
you have said what the unit of code is, and where a unit's documentation goes relative to it.

Axon learned this the expensive way. Its source was split into a platform tree and per-engine trees,
but the documentation did not follow: engine architecture, engine recipes, and engine findings sat in
the top-level docs directory next to genuinely platform-level material, and the complaint that
eventually forced the fix was that *it all blends together*. Untangling it meant moving files and
rewriting links across the whole tree.

This project can have the answer for free, because no module exists yet. That is the entire reason to
decide it now: the cost of getting the shape right is zero today and grows with every file written
against the wrong shape. It also has to be decided before `coord new-module` exists, since the
scaffold encodes whatever this ADR says and every future module inherits it without thinking.

Two questions are genuinely open, and this ADR answers both.

## Decision

### 1. The modular unit is the **Module**, and it is self-contained

A module owns exactly one behavior. It lives in one subtree under `src/modules/`, and that subtree
carries **everything the module needs — code and documentation both**, so it could in principle be
lifted into its own repository with its documentation intact. The unit is defined in full by
[MODULE_SPEC.md](../MODULE_SPEC.md); this ADR decides only its shape and its boundary.

Concretely, a module subtree carries its own `README.md`, its own `docs/` for anything only meaningful
when that module is present, and the two projects the Core/Shell split requires
([ADR 0003](0003-the-core-shell-split.md)).

"Module" also carries a specific technical meaning that is worth pinning here so it does not drift
toward "plugin": a module is a **compile-time participant**, registered at build time, shipped inside
the host's payload. It is not a binary someone drops into a folder. That follows from the
compile-time-modularity principle in [COORDINATOR.md](../COORDINATOR.md), and it is what makes the
boundary check meaningful — a modularity rule enforced by inspecting project references only works if
the set of modules is known when the project is built.

### 2. The top-level `docs/` tree is platform, pillar and meta only

The split test is the one Axon converged on, restated for this project:

- **Module documentation** = only meaningful when that module is present — its internal design, its
  extension recipes, its own resume notes, its own validation history. Goes in the module subtree.
- **Platform documentation** = true with zero modules or with ten — the host and lifecycle, the two
  pillars, the module contract itself, the operating model, the audit and documentation specs, the
  runbooks that describe a *discipline* rather than one module's checklist. Goes in `docs/`.

The pillars ([CONDUIT.md](../CONDUIT.md), [ATLAS.md](../ATLAS.md)) are platform documentation by this
test — they are true with no modules present — even though their code lives under `src/pillars/`.

### 3. The module README is the seam

Platform documents link to a module's `README.md` and **never deeper**. The README curates the module:
what it is, what state it is in, how it is laid out, what to read in what order, which ADRs apply, and
a **"Where to resume"** section. Module-internal documents cross-link freely among themselves; links
back up to platform documents use the long relative path, which is an accepted cost of co-location.

The "Where to resume" section is not a suggestion. The `shelving` check in
`tools/doc-audit/audit.py` warns on a module directory with no README, or a README without it,
because a module put down without one is a module that costs a day to pick back up instead of an hour.

### 4. The ADR log stays **unified** in `docs/decisions/`

One numbered, chronological log for the whole project. A module does not get its own decision log.

Two reasons. Most decisions are cross-cutting even when they look local — a decision about zone
geometry immediately touches [Atlas](../ATLAS.md)'s snapshot contract, and filing it under a module
would hide it from the pillar it constrains. And a split log fractures the one artifact whose value is
that it is a *sequence*: renumbering, gaps, and duplicate numbers become possible the moment there is
more than one log, which is exactly what the `adr-gap` ERROR check exists to prevent.

Instead, each module README **curates** the ADRs relevant to it by number and title. If a module is
ever genuinely extracted into its own repository, its curated ADRs are copied at that point — a
one-time cost paid once, versus a structural cost paid continuously.

## Consequences

- The top-level `docs/` tree cannot silently accumulate module material; a module document placed
  there is a placement error the documentation spec can name, not a matter of taste.
- A module subtree is liftable, which is what makes shelving credible: the thing you put down is one
  directory, and the thing you pick up is that same directory plus its README.
- Deep links from a module's documentation back up to platform documentation are long
  (`../../../docs/…`). Markdown renderers resolve them and there are few of them; this is the accepted
  price of the co-location, and it was Axon's experience that it stays tolerable.
- The decision log remains a single one-line grep, which is what makes the lifecycle discipline
  (closure tokens on settled decisions, recall hooks on deferred ones) mechanically checkable.
- `coord new-module` must scaffold exactly this shape, which means the scaffold is a load-bearing
  artifact rather than a convenience: it is how the rule propagates without anyone reading this ADR.
- **The rule is untested.** No module exists, so this shape has never been used in anger
  ([TD-5](../TECH_DEBT.md) makes the same point about the module contract generally). The first module
  is expected to find something wrong with the template; revising it in that same session is the plan.

## Alternatives considered

**A parallel documentation tree mirroring the source** — a per-module folder under the top-level
documentation tree instead of under the module. Tidy, and it keeps
all prose in one place, which has real navigational appeal. Rejected because it defeats the property
the whole decision is for: with documentation in a separate tree, a module is no longer a single
liftable subtree, and the shelving contract loses the thing it promises — that putting a module down
means putting down *one directory*.

**Per-module ADR logs.** Rejected as described above: it fractures a chronological record, invites
renumbering confusion, and would file cross-cutting decisions under whichever component happened to
prompt them. The curation approach in the module README captures the discoverability benefit — "which
decisions govern this module" — without paying for it with the log's integrity. Worth revisiting only
if a module is actually extracted, which is the point at which the copy cost becomes real.

**No co-location at all — keep every document in `docs/` and rely on naming.** Rejected: this is
exactly the state Axon had to dig itself out of, and the digging was expensive precisely because it
happened after the files existed. Choosing it here would mean knowingly buying a migration.

**Treat modules as runtime-loadable plugins with independent documentation and versioning.** Rejected
on a different axis than the others. It would make the boundary check impossible (the module set would
not be known at build time), it would multiply the delivery surface that
[ADR 0008](0008-the-update-delivery-channel-is-built-now.md) has to cover by the module count, and it
would buy an extensibility nobody has asked for — there is one developer and no third-party module
author. Compile-time modularity is the decision; "module" names a compiled participant.
