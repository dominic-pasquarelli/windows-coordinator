# ADR 0001 — Adopt the Axon documentation and operating protocols

Date: 2026-08-08
Status: Accepted

## Context

The owner already maintains **Axon**, a multi-year embedded platform built the same way this project
will be: in bursts, around a day job, across shifting interests, with individual pieces put down for
months and picked up completely cold. Under that pressure Axon grew an apparatus — tiered
documentation with machine-checked frontmatter, an audit protocol with a mechanical checker and a set
of judgement lenses, a unified decision log, a tactical NEXT file with a completed-work archive
behind it, capture buffers with named recall and drain paths, a snapshot-and-steering protocol with
restore anchors, a shelving contract per module, and an evidence standard about what a green command
is allowed to mean. None of it was designed up front. All of it exists because something was lost,
re-derived, or believed on insufficient evidence, and the apparatus is what stopped that recurring.

Windows Coordinator has the identical shape and none of the scar tissue. It is a personal Windows
toolbox, built by one developer in evenings, whose modules will sit untouched for months at a time.
The question at bootstrap is therefore not *whether* this project needs resume-fidelity machinery —
it demonstrably will — but **when** to install it: now, on a repository with zero lines of compiled
code, or later, when the first painful gap proves the point.

The argument for "later" is that the apparatus is large and the project is empty. The argument for
"now" is that almost none of it can be added retroactively. Frontmatter can be backfilled; a decision
log cannot, because the reasoning it records evaporates within weeks. A NEXT file that was maintained
is a different artifact from a NEXT file written afterwards from memory. The value of writing down
*why* is highest at the moment of maximum ignorance, which is exactly now.

## Decision

**Port Axon's documentation and operating protocols wholesale**, with the adaptations and the
deliberate omissions recorded below. This is a port of *protocols*, not of text: every concept had to
earn a real Windows-desktop consumer or it was dropped.

### Ported in substance, unchanged

The tier-based placement rule (documentation follows its code) with required frontmatter and the
`updated` / `audited` pair · the one-concern-one-home rule (cross-link, never restate) · the unified
ADR log · the six audit lenses and the ERROR-gating mechanical checker · the four capture buffers
([NEXT.md](../NEXT.md), [HISTORY.md](../HISTORY.md), [INBOX.md](../INBOX.md),
[TECH_DEBT.md](../TECH_DEBT.md)) each naming both its recall hook and its drain · the snapshot intake
and steering protocol with its restore anchors · the shelving contract (a "Where to resume" section
is the price of putting anything down) · the evidence standard, its three failure shapes, and the
"when you add a guard, prove it fails without the fix" rule · the freeze ceremony as a save point.

The rationale beneath all of it is restated for this project in
[OPERATING_MODEL.md](../OPERATING_MODEL.md); the mechanics live in [DOC_SPEC.md](../DOC_SPEC.md) and
[AUDIT.md](../AUDIT.md).

### Adapted — the translation table

| Axon | Windows Coordinator | Why the change |
|---|---|---|
| Doc tier `engine` | Doc tier **`module`** | The modular unit here is a Module; "engine" is embedded vocabulary that would mean nothing to a reader of a desktop toolbox. |
| **Engine** (the modular unit) | **Module** | Same idea, correct noun. Defined in [MODULE_SPEC.md](../MODULE_SPEC.md); named plainly per [ADR 0009](0009-plain-descriptive-module-names.md). |
| Hardware validation — a board on a bench, a preset flashed, a photograph of the result | **Manual validation** — a human at a real desktop with more than one monitor at mixed scaling, following [runbooks/manual-validation.md](../runbooks/manual-validation.md) | The unautomatable half of the evidence is the same idea with different apparatus. What survives is the rule that it cannot be substituted for. |
| "A maintained test preset loaded on a board" | **A reproducible desktop scenario** — a named starting state a different person can recreate later | Evidence has to be re-runnable by someone who was not there. A screenshot is not a scenario. |
| Ten firmware environments, plus a lean-composition build to catch code stranded inside a feature guard | **One solution: `net9.0` Core projects (any OS) and Windows-only projects** | The invariant is *build-shape coverage* — that some real build exercises each shape. The shapes here are Core-versus-Windows rather than board-versus-feature-flag, and the honest consequence is that CI covers only one of the two ([TD-4](../TECH_DEBT.md)). |
| The `axon` CLI wrapping the embedded toolchain | The **`coord`** CLI wrapping `dotnet` and the doc tooling | [ADR 0010](0010-coord-as-the-single-developer-entry-point.md). |
| **Plexus** — the transport fabric; engines declare a QoS class and never name a modality | **Conduit** — the input and trigger fabric; modules declare a trigger intent and never name an input mechanism | [ADR 0005](0005-conduit-modules-declare-trigger-intents.md), [CONDUIT.md](../CONDUIT.md). |
| **Spatial** — physical space, with coherence enforced through a single observation | **Atlas** — desktop space, with coherence enforced through a single snapshot | [ADR 0006](0006-atlas-one-canonical-desktop-model.md), [ATLAS.md](../ATLAS.md). |
| **Forge** — the interaction/authoring plane, a full pillar | The **Shell** — deliberately platform core, *not* a pillar, with a written graduation trigger | Forge earned pillar status by having several independent consumers. The Shell has one. [COORDINATOR.md §5.1](../COORDINATOR.md) states the trigger that would promote it. |
| Effects take every dependency through a context object and never touch hardware globals, which makes them host-testable | The **Core/Shell split** | [ADR 0003](0003-the-core-shell-split.md). This is the single most important thing carried across, and it is carried across as a stronger rule: a project boundary a checker can enforce, rather than a convention. |

### Deliberately dropped

**The parallel-sessions / lane protocol.** Axon carries a whole document for multi-session
coordination — work lanes, presence files, a passed conch for the machine with the hardware attached,
a shared board, a merge protocol, cross-session review. It is not ported. There is one developer, one
machine, no hardware to arbitrate over, and no concurrent agent sessions. A protocol with no pressure
behind it is ceremony, and ceremony is what discredits the parts that are load-bearing.

**The recall hook is explicit:** bring it back the first time two work streams touch this repository
concurrently — a second development machine in regular use, or a background session running while the
owner is also editing. The observable symptom will be either a merge conflict in the docs or the
question "is anyone else in this file right now." Until one of those happens, the omission is a
decision; after one of them happens, continuing to omit it is an oversight.

**Also dropped:** the fleet/bench vocabulary (there is no fleet), and Axon's framing of CI as a paused
authority. This project's CI statement is different and specific — CI builds and tests the Core half
only, and [TD-4](../TECH_DEBT.md) exists so a green badge is never read as coverage of the half where
the risk actually lives.

**Adopted but thin, and labelled as such:** the freeze ceremony exists as a directory and a procedure
with no freeze recorded yet; [audit-log.md](../audit-log.md) is seeded with this bootstrap pass and
nothing else.

## Consequences

**The ratio is absurd, and saying so is part of the decision.** This repository now contains several
thousand lines of protocol, specification, and rationale, and zero lines of code that have ever
reached a compiler. Anyone encountering it cold will think it is over-engineered, and that reaction is
reasonable enough that it deserves an answer written down once rather than re-argued.

The answer has three parts. First, **the protocol is cheap to carry and expensive to retrofit.** The
recurring per-change cost is minutes — bump an `updated` flag, run `coord audit`, add an ADR when a
decision has a real trade-off. The retrofit cost is unbounded, because the reasoning a decision log
captures is gone within weeks and cannot be reconstructed. Second, **the buffers drain.** Every
capture buffer names how items leave, not just how they arrive
([OPERATING_MODEL §3](../OPERATING_MODEL.md)), so the apparatus is not designed to grow
monotonically; an audit that finds a buffer accreting is finding a defect in the practice, not a fact
about the protocol. Third, the alternative was tried by default in every previous personal project
and produced repositories the owner could not resume.

**The real risk is different from the one people will name.** It is not that the documentation is too
heavy; it is that **the documentation describes a system that never gets built**. A specification with
zero implementations reads as authoritative precisely because it is thorough, and the next session
will trust it more than it has earned. [TD-5](../TECH_DEBT.md) exists to say so out loud, and the
first real module is expected to contradict the spec in several places — revising the spec at that
moment, in the same session, is the plan and not a failure.

**Specific accuracy debt is already accrued.** Every document written in this pass describes code that
had never been compiled when this ADR was written ([TD-1](../TECH_DEBT.md); it compiles as of CI `7aef6ff`, 2026-08-08). The `audited` flag and the accuracy check exist for
exactly the correction pass that the first successful build will force.

**The protocols now bind.** A phase is not done with ERROR-level drift outstanding; a module is not
shelved without a "Where to resume" section; a claim about desktop behavior is not made on the
strength of a host test run. These are the terms of the port, and the point of accepting them on day
zero is that they are cheap to honor before there is anything to protect.

## Alternatives considered

**Accrete the apparatus as it hurts** — start with a README, add a decision log the first time a
decision is forgotten, add an audit when the docs first drift. Rejected. This is the default that
produced the projects this port exists to avoid, and it fails on timing rather than on principle: the
machinery's entire value is retroactive, so installing it after the first painful gap means the first
painful gap is uncompensated and every decision made before it is unrecorded. It also gets the
economics backwards — the protocol is at its cheapest when the repository is empty.

**Copy Axon's documents literally and rename the nouns.** Rejected. Roughly half of Axon's content is
inseparable from embedded work — transport modalities, power budgets, flash layout, board targets,
synchronization across a mesh — and a document full of mechanically translated vocabulary reads
authoritative while teaching nothing, which is a worse failure than a missing document. The port
required deciding, concept by concept, whether a real consumer existed here; three did not survive
that test and are listed above.

**Share a repository or a toolchain with Axon.** Rejected. Different language, different platform,
different release cadence, and — decisively — the coupling would cost the ability to shelve either
project independently, which is the exact property both are built to have. The two projects share
ideas; sharing infrastructure would make each a dependency of the other's dormancy.

**Adopt everything, including the parallel-sessions protocol.** Rejected as above: no pressure, no
protocol. The alternative shape considered was to adopt it in a reduced form (a single presence file),
which was also rejected — a partial protocol has all of the ceremony and none of the guarantee. A
named trigger is the honest version of "not yet."
