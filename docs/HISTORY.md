---
title: History — completed arcs
tier: meta
status: living
updated: 2026-08-08
related:
  - docs/NEXT.md
  - docs/COORDINATOR.md
  - docs/audit-log.md
  - docs/TECH_DEBT.md
---

# HISTORY — completed arcs

> The archive of finished work, **newest at top**. This is the companion to
> [NEXT.md](NEXT.md): NEXT holds only what is *active*, and every time a phase closes its narrative
> drains here so the tactical page stays short enough to actually read on a cold resume.
>
> **One sentence:** NEXT answers "what do I do now"; this file answers "how did it get like this".
>
> An entry is written **when the work closes**, in the past tense, naming what was verified and what
> was not. It is a record as of its date — it is never rewritten to match later understanding, and
> it carries **no `audited:` key** for exactly that reason ([DOC_SPEC §3](DOC_SPEC.md#3-structure--frontmatter)).
> If a later session proves an entry was wrong, the correction goes in the newer entry, not by
> editing the old one. The old entry is evidence about what was believed at the time, which is the
> thing a resuming reader most needs and most often cannot recover.

---

## 2026-08-08 — P0 closeout · The first compile, and two rounds of external review

Between the bootstrap pass and this entry, PR #1 was reviewed twice by a human reviewer and corrected
twice. The bootstrap's own four adversarial verifiers had found real defects — but only defects of
the kind an unverifiable artifact permits: broken links, drifted duplicates, overclaimed status. The
reviewer found seven that a compiler and a test would have surfaced on day one, and then an eighth
that only appears after the first two are fixed.

**Round one — seven semantic findings.** A `ProjectReference` in `coord new-module` that pointed at a
project the `.Core` rename had moved; a settings migration API that ran on the deserialized object
and therefore could not perform the renames and reshapes migrations exist for; `IReadOnlyList<T>`
parameters that left the coherent-snapshot guarantee unenforced; a `Capability` that defaulted into
the one state its own comment forbade; `coord test` widening to the whole solution; a documented
bootstrap sequence that guaranteed a red build; and — the one that mattered most — **CI that
installed a .NET 9 SDK and then skipped the build because no solution file existed.** A `.csproj`
compiles on its own. The repository had spent an entire PR documenting an unverified state with
great care while the means of verifying it sat idle in its own pipeline.

**Round two — the evidence closeout.** With CI compiling, roughly sixty-five `NEVER COMPILED` claims
across thirty-nine files became false, and were swept to what was actually observed.

**The observed result, at commit `7aef6ff`:** GitHub Actions built all five projects on Ubuntu and
the three production projects on Windows, **0 warnings** under `TreatWarningsAsErrors`, and ran
**45 Core tests — 0 failed, 0 skipped** (Atlas 25, Platform 20). That is the first compile in the
project's history and the first test run of any kind.

**What it does not license, stated because it is the whole remaining project:** no Shell adapter
exists, no module exists, and nothing has ever run on Windows. No hotkey, no window, no monitor, no
tray icon, no UI. [ADR 0011](decisions/0011-settings-migrate-the-persisted-document-not-the-deserialized-object.md)
records the migration redesign; the full finding-by-finding account is in
[audit-log.md](audit-log.md).

**The durable lesson**, worth more than any individual fix: *a precise description of a limitation
can feel like rigor while being the thing that stops you noticing the limitation was optional.*

---

## 2026-08-08 — P0 · Bootstrap: the documentation system, the operating protocols, and an uncompiled skeleton

The repository was created in a single authoring pass, AI-assisted and owner-supervised. Its purpose
was not to produce working software; it was to produce a structure that makes future bursts of work
resumable, and to do so before there is any code whose weight would make retrofitting the structure
expensive.

### What landed

**The documentation system.** Governance ([CLAUDE.md](../CLAUDE.md)) and the standing agreements; the
platform architecture ([COORDINATOR.md](COORDINATOR.md)) with the Core/Shell split, the platform core
services, the layered model and the P0–P5 roadmap; both pillar spines
([CONDUIT.md](CONDUIT.md) — the input and trigger fabric; [ATLAS.md](ATLAS.md) — desktop spatial
truth); the module contract ([MODULE_SPEC.md](MODULE_SPEC.md)) including the shelving contract; the
documentation spec ([DOC_SPEC.md](DOC_SPEC.md)) with tiers, frontmatter and the single-source rule;
the rationale layer ([OPERATING_MODEL.md](OPERATING_MODEL.md)); the audit protocol
([AUDIT.md](AUDIT.md)) and its log ([audit-log.md](audit-log.md)); the tactical page
([NEXT.md](NEXT.md)); the capture and register buffers ([INBOX.md](INBOX.md),
[TECH_DEBT.md](TECH_DEBT.md)); the long-horizon parking lot ([vision.md](vision.md)); the cold-start
guide ([ONBOARDING.md](ONBOARDING.md)); ten ADRs in [`docs/decisions/`](decisions/); three runbooks
and one recipe.

**The Python tooling — written and actually executed.** `tools/coord/coord.py` provides the single
developer entry point (`test`, `build`, `run`, `audit`, `map`, `new-module`, `doctor`), and
`tools/doc-audit/audit.py` plus `tools/doc-audit/genmap.py` provide the mechanical drift checker and
the generated doc index. Both are stdlib-only Python 3.11 and were deliberately designed to run with
**no .NET installed**, which is the sole reason any part of this repository could be verified during
the pass at all. `coord doctor` reports a missing SDK clearly rather than failing obscurely — a
requirement discovered by being in exactly that situation.

**An uncompiled C# skeleton.** Three projects and their contract interfaces —
`Coordinator.Platform.Core` (`src/platform/`), `Coordinator.Conduit.Core` and
`Coordinator.Atlas.Core` (`src/pillars/`) — plus shared MSBuild properties and the repository
conventions (`.editorconfig`, `.gitignore`). Every project carries the `.Core` suffix because each
will one day sit beside a `.Shell` adapter of the same stem; the C# namespaces do not carry it.
`src/shell/` is a README and a directory — **no Shell project was created**, and no `.sln` ties the
three together.

### What was adapted from Axon, and how

The whole operating apparatus is ported from **Axon**, a mature embedded platform project by the same
owner, on the reasoning that the protocols were earned over years of real multi-year, multi-interest
work and are almost entirely domain-independent. ADR 0001 records the port in full. The shape of the
translation:

| Axon | Windows Coordinator | Why it changed |
|---|---|---|
| Engine (the modular unit) | **Module** | plain descriptive naming for a PowerToys-like toolbox (ADR 0009) |
| doc tier `engine` | doc tier `module` | follows the rename |
| Plexus (multi-modal transport) | **Conduit** (input and trigger fabric) | the structural idea — *a unit never names the mechanism* — survives; the mechanism does not |
| Spatial (physical pose and frames) | **Atlas** (monitors, work areas, DPI, windows) | coherent compound state through one snapshot, translated from a room to a desktop |
| Forge (the authoring plane) | **Shell**, and deliberately *not* a pillar yet | one consumer; the graduation trigger is written down instead |
| hardware validation on a bench | **manual validation** on a real desktop | the evidence category is identical; the apparatus is a human at a multi-monitor PC |
| `axon` CLI | **`coord`** CLI | `wc` would collide with the POSIX word-count command (ADR 0010) |
| effects take deps via a context, so they host-test | the **Core/Shell split** | the same idea one altitude up: Windows-free logic, thin adapter (ADR 0003) |

What was deliberately dropped: the tier/stand-down model (a desktop app has no mesh to degrade
through), the multi-session coordination protocol (one owner, one machine), and everything transport-
or firmware-specific. What was kept without dilution: the evidence standard, the snapshot and
steering protocol, the capture/recall/drain triad, the shelving contract, the audit lenses, and the
insistence that documentation is a load-bearing deliverable rather than polish.

### What this pass explicitly did NOT do

Recorded plainly, because an archive entry that lists only accomplishments is how a project starts
believing its own summary:

- **Nothing was compiled.** The pass ran in a Linux container with **no .NET SDK**. Not one line of
  C# reached a compiler, a linter, or a test runner. Every statement about the C# in this repository
  is a statement about text that has been written, not about software that exists.
- **No solution file was created.** `.sln` files carry GUIDs that could not be generated or verified
  in that environment; generating it is the first task in [NEXT.md](NEXT.md) (**TD-2**).
- **No module was built or scaffolded.** Zones and Chrono are roadmap entries. No empty directories
  were created for them, because an empty directory is a claim.
- **Nothing ran on Windows.** No hotkey registered, no monitor enumerated, no window moved, no tray
  icon shown, no update installed.
- **The mechanical checker ran once, at closeout, and not before** — it was authored during the same
  pass, so for most of the pass there was no stable doc set to point it at. That single first run
  surfaced one ERROR (`map-sync`: a stale [MAP.md](MAP.md)); regenerating the map fixed it and the
  re-run finished at 0 ERROR. The same closeout found four defects in the guards themselves — a
  `updated-flag` check blind to a back-dated doc, a `genmap.py` that rewrote the map on any
  unrecognised argument, a CI job that hard-failed on this project's own documented bootstrap state,
  and a repository asserting a green documentation gate while its checker exited 1 — all four fixed
  here and written up in [audit-log.md](audit-log.md). Nothing re-runs those proofs (**TD-8**).
- **No performance baseline exists**, so any later claim about memory or idle cost has nothing to
  compare against.

### What it bought

One thing, and it is the thing the [operating model](OPERATING_MODEL.md) argues is worth the most:
a cold reader — human or otherwise — can now open [NEXT.md](NEXT.md), learn the true state in a few
minutes, and start executing. The debt this pass created is enumerated honestly in
[TECH_DEBT.md](TECH_DEBT.md) rather than discovered later, and the largest item (**TD-1**: nothing
compiles, no toolchain verified) is already the Active focus. The next entry in this file should be
P1, and it should begin by saying what happened when the skeleton first met a compiler.
