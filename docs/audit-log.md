---
title: Audit Log — code↔doc & modularity health over time
tier: meta
status: living
updated: 2026-08-08
related:
  - docs/AUDIT.md
  - docs/DOC_SPEC.md
---

# Audit log — code↔doc & modularity health over time

> The durable record of every audit. **Newest entry at top.** This is what makes repository health a
> tracked quantity rather than a vibe: when an audit last ran, what it found, what got fixed, and
> what is still owed.
>
> **One sentence:** if it is not written here, the audit did not happen.
>
> Protocol: [AUDIT.md](AUDIT.md). Run the mechanical half with `coord audit`; run the full pass with
> the `/audit` skill. The entry format is defined in [AUDIT.md §7](AUDIT.md#7-the-audit-log).
>
> **"Accepted" findings** are recurring non-drift — frozen historical references, illustrative
> paths, deliberately planned-but-unbuilt entries. They are listed once so future audits do not
> re-triage them. This doc carries **no `audited:` key**: it is a record of summaries as of their
> dates, not a living claim about current code ([DOC_SPEC §3](DOC_SPEC.md)).

---

## 2026-08-08 — PR #1 external code review (human reviewer, seven findings)

**Scope:** the whole bootstrap PR, reviewed by a human against the guarantees the documentation
states. Every finding was confirmed against the code before it was acted on. This entry is worth
reading before the bootstrap entry below it, because it corrects that entry's central claim.

### The pattern worth remembering

The bootstrap's own verification was **documentation-shaped**. Four adversarial verifiers hunted
broken links, single-source violations, vocabulary leakage and overclaiming, and they were good at
it — the entry below records four real defects they found in the project's own guards. **Not one of
them asked whether the code did what its doc-comment promised**, because none of them could compile
it. The human reviewer went straight at semantics and found seven things a compiler and a test would
have surfaced on day one.

The lesson is not "add another lens". It is that **an unverifiable artifact attracts verification of
the things about it that *are* verifiable**, and that substitution is invisible from the inside.

### Fixed this pass

- 🔴 **CI never compiled anything, and did not have to be that way.** Both .NET jobs *skipped* the
  build whenever no solution file existed — while `actions/setup-dotnet` installed a .NET 9 SDK three
  lines above. A `.csproj` compiles perfectly well without a solution. The repository shipped an
  elaborate, carefully-worded account of an unverified state when the verification had been available
  the whole time. **Both jobs now compile every project on every push**; the Linux job additionally
  runs the Core suites. *This is the finding that matters most on this page.*
- 🔴 **`coord new-module` emitted a `ProjectReference` to a project that does not exist.** Renaming
  the Core projects to carry a `.Core` suffix (this round) updated the one hand-written reference and
  missed the one the generator *writes* — so every module scaffolded afterwards would have been born
  unbuildable. Fixed, plus two new guards: a `projectref` ERROR check in `tools/doc-audit/audit.py`
  (every `ProjectReference` must resolve) and `tools/coord/tests/test_scaffold.py`, which scaffolds a
  module into a throwaway checkout and asserts its references resolve. **Both were A/B-proven against
  the broken template before being trusted.** A generated file is code; nothing had ever run the
  generator and looked at the output.
- 🔴 **The settings migration API could not perform the migrations it existed for.**
  `IVersionedSettings.Migrate(int)` ran on the *already-deserialized* current type, by which point the
  deserializer has discarded every property the current type no longer declares — so a renamed field's
  old value was gone before the migration could move it, and the doc-comment's own two examples were
  exactly the two cases it could not do. Silent data loss, in the one artifact a user cannot
  regenerate. Redesigned onto the persisted document
  ([ADR 0011](decisions/0011-settings-migrate-the-persisted-document-not-the-deserialized-object.md)),
  with tests for rename, collection reshape, future-schema refusal, malformed-document refusal and
  chain integrity.
- 🟠 **The coherent-snapshot guarantee was not enforced.** `DesktopSnapshot`, `LayoutTemplate` and
  `ZoneSet` accepted `IReadOnlyList<T>` — which promises only that *that reference* has no mutators —
  so a caller could keep its `List<T>` and mutate the "snapshot" afterwards. Now defensively copied,
  with tests that mutate the caller's list and assert the value did not move.
- 🟠 **`Capability` defaulted `Bindable` to `true` three lines below a comment saying a `Reading` is
  never bindable.** Now rejected at construction. `Kind` and `Bindable` are get-only so a `with`
  expression cannot rebuild the illegal state — a record's `with` runs the copy constructor and does
  **not** re-run validating initializers, which would have left the hole open.
- 🟠 **`coord test` ran `dotnet test <solution>` when a solution existed**, which would eventually
  drag Windows-targeted Shell projects into the Linux Core-test job and silently widen what a green
  run means. It now always runs discovered test projects individually.
- 🟠 **`docs/NEXT.md` prescribed a sequence that guaranteed a red build** — generate a solution with
  the three production projects, while CI fails a solution that has no test project. Reconciled: the
  documented commands now include the two test projects, and the incoherent `coord test` step is
  rewritten.

### Health

- `coord audit` **0 ERROR / 0 WARN / 0 INFO**; `coord map --check` clean.
- `tools/coord/tests/` — **4 tests, passing**, and proven to fail against the defect they exist for.
- **C#: still not compiled locally** (no SDK in the authoring environment). CI is now the first
  compiler this project has ever had; the first run of the new jobs is the first compile in its
  history. **Read the run — do not read this page — for whether it builds.**

### Carry-forward

Every `.cs` file, both pillar READMEs, `Directory.Build.props` and several docs carry a
`NEVER COMPILED` banner. The moment a CI run is observed green those banners are false and must be
replaced with what was actually observed — the run, the date, and what it does not cover. Tracked in
[NEXT.md](NEXT.md) Active focus. A banner that overclaims in the *other* direction is the same defect
mirrored.

---

## 2026-08-08 — project bootstrap (AI-assisted authoring pass, owner-supervised)

**Mechanical:** **run at closeout — the first real execution.** The checker
(`tools/doc-audit/audit.py`) was authored during this same pass, so for most of the pass there was no
stable doc set to run it against. At closeout it was run over the finished doc set. It surfaced one
ERROR — `map-sync`: [MAP.md](MAP.md) was stale relative to the doc set that had grown around it.
Regenerating the map (`coord map`) fixed it, and the re-run finished at **0 ERROR**. That is the
mechanical baseline this repository did not have an hour earlier; the WARN/INFO advisories are not
tallied here because no clean count was taken, and inventing one would be the exact failure the
evidence standard names.

The stale map is worth reading as more than a chore. Until the checker ran, the record docs said the
checker had never run and the status docs said the Python tooling was "executed and verified" — and
the stale `MAP.md` is what settled the disagreement in favour of the record docs. **A gate nobody has
executed is indistinguishable from a gate that passes.**

**Lenses walked:** D and E in full; A partially. B, C, and F were **not meaningfully applicable** and
were deliberately skipped, for the reason recorded below rather than by oversight.

**Type:** a baseline entry, not a drift audit. Bootstrap creates the artifacts that later audits
measure against; there is nothing yet for them to have drifted from. The value of this entry is that
it fixes the starting position honestly, so the second audit has a real reference point.

### What exists as of today

Three things, in three very different states of verification:

1. **The documentation set.** Governance, the platform architecture, both pillar spines, the module
   and documentation specs, the operating model, this audit protocol, the roadmap and capture
   buffers, the decision log, runbooks, and recipes. Authored in this pass; internally cross-linked;
   checked by the mechanical checker exactly once, at closeout, as recorded above.
2. **The Python tooling.** `tools/coord/coord.py` (the `coord` CLI) and the doc-audit checker under
   `tools/doc-audit/`. Stdlib-only Python 3.11, deliberately designed to work with **no .NET
   installed** — which is the only reason any part of this repository can be checked at all today.
3. **An uncompiled C# skeleton.** Three projects and their contract interfaces —
   `Coordinator.Platform.Core`, `Coordinator.Conduit.Core`, `Coordinator.Atlas.Core` (the `.Core`
   suffix is on the project and the assembly; the namespaces are `Coordinator.Platform`,
   `Coordinator.Conduit`, `Coordinator.Atlas`). **Written, never compiled.** No `.sln`, no `.Shell`
   project, and no module (Zones, Chrono) implemented or scaffolded — both are roadmap entries only.

### Fixed this pass

- 🔴 **`map-sync` ERROR — [MAP.md](MAP.md) was stale.** Found by the first mechanical run described
  above; fixed by regenerating the map with `coord map`; the re-run went to 0 ERROR.

**And four defects in the guards themselves** — found by an adversarial verification pass at closeout,
all four fixed here. These are the most useful thing on this page for a future reader, because each
one is a *guard that could not have failed*, which is the first of the three failure shapes in
[OPERATING_MODEL §7](OPERATING_MODEL.md#7-the-evidence-standard--what-it-works-is-allowed-to-mean):

1. **The `updated-flag` closeout check could not catch a back-dated doc.** It compared a changed
   doc's `updated` for *equality* against the baseline, so a doc edited and dated *backwards* in the
   same commit passed silently — the one shape the check exists to catch. It now compares "did not
   move forward" instead. Recorded as part of **TD-8**.
2. **`genmap.py` treated any unrecognised argument — including `--help` — as "rewrite the map".** So
   a mistyped gate invocation silently *repaired* the very drift it had been asked to detect, and
   reported success. A drift detector that fixes drift instead of reporting it is worse than absent,
   because its green result is now evidence of nothing. It now validates argv. Also **TD-8**.
3. **The CI `windows-build` job hard-failed on the project's own documented bootstrap state.** There
   is no `.sln` (**TD-2**) and no compiled C# (**TD-1**) — both deliberate, both written down — and
   the workflow nonetheless treated that state as a build failure. A gate that is red for a reason
   the project has already accepted trains everyone to ignore it, which costs the next, real failure.
4. **The repository asserted a green documentation gate while its own checker exited 1.** README,
   CLAUDE.md and [NEXT.md](NEXT.md) described the Python tooling as "executed and verified" while
   this log and [HISTORY.md](HISTORY.md) recorded that it had never been run — and the stale map
   proved the record docs right. The reconciliation was forward: run the checker, fix what it found,
   and write down what it found rather than softening the claim.

The pattern across all four: **every one of them was a check whose passing carried no information.**
None would have been found by running the gate — only by trying to make it fail. That is the
operational rule, restated: *when you add a guard, prove it fails without the fix.*

### Backlog (real drift, deferred)

- 🟡 **The checker has no self-test suite.** The four guard defects above were found by hand and
  fixed with one-shot proofs; nothing re-runs those proofs, so a future edit can re-open any of the
  holes and nothing will notice. Tracked as **TD-8** — the standing rule until it is paid down is to
  break a check on purpose and watch it go red before trusting it.
- 🟡 **No solution file.** No `.sln` was generated: solution files carry GUIDs that cannot be
  produced or verified without a toolchain. Generating it on a Windows machine is an explicit
  [NEXT.md](NEXT.md) task, not an omission.
- 🟡 **Lenses B, C, and F have never run against real code.** B (modularity) needs more than one
  module to have an opinion; C (shelving) needs a module to shelve; F (forward-compatibility) needs
  something built that could have foreclosed something planned. All three become meaningful the
  moment the first module exists, and the audit at the end of that phase must walk them.

### Accepted (not drift — will recur, do not re-triage)

- **Every C# statement in the docs is a design claim, not a build claim.** This is the repository's
  known and deliberately recorded state, not drift — *provided the phrasing stays honest*. It stops
  being accepted the moment a doc says "builds", "works", "passes", or "verified" about C#, and it
  must be revisited in both directions the first time a compile is actually attempted.
- **Zones and Chrono are described but do not exist.** Planned-not-built by design
  ([COORDINATOR.md](COORDINATOR.md) roadmap). Not a documented-but-not-built violation as long as
  every mention reads as future tense.
- **The Shell is documented as platform, not as a pillar.** A recorded decision with a named
  graduation trigger — a second independent consumer of the registry-driven settings surface — not an
  unfinished classification.

### Health

- **C#: never compiled.** `dotnet` is absent from the authoring environment (`command -v dotnet`
  returns nothing). No .NET SDK has ever been present. Nothing has been through a compiler.
- **Core tests: not runnable.** No test has ever been executed, because no runner exists here. This
  is *unverified*, not *passing*.
- **Manual validation: never performed.** No Windows desktop has been involved at any point. Nothing
  is known about window placement, hotkey capture, DPI behavior, or tray lifecycle.
- **Toolchain actually measured here:** Python 3.11.15 ✓ · Node v22.22.2 ✓ · .NET SDK ✗ (absent).
- **Counts: not measured.** Doc, ADR, and source file totals are deliberately omitted — files were
  being authored in parallel during this pass and no clean enumeration was taken. Inventing a number
  here would be precisely the "claim stronger than its evidence" failure the evidence standard names.
  The regenerated [MAP.md](MAP.md) is the authoritative inventory; read it, do not trust a number
  quoted here.
- **Ground-truth reconciliations actually performed this pass:**
  - toolchain: `command -v dotnet` → not found; `python3 --version` → 3.11.15; `node --version` →
    v22.22.2. This is the one hard measurement behind the carry-forward below.
  - module set: `src/modules/` contains no module — reconciled against the roadmap, which lists Zones
    and Chrono as planned. ✓ consistent.
  - ADR frontier: reconciled mechanically at closeout — the `adr-gap` and `adr-format` checks are
    part of the 0-ERROR run above, so the sequence has no gaps or duplicates and every ADR carries a
    `Date:` and a `Status:`. That is a structural result, not a judgement about the decisions.

### Carry-forward — the one thing that matters most

> **No C# in this repository has ever been compiled, and the toolchain is unverified.**

Every description of a project, a type, an interface, or a lifecycle is a **specification**, not a
report of working software. The correct phrase everywhere is **"not compiled"** — never "builds",
never "works", never "passes". Restoring the toolchain on a Windows machine, generating the solution
file, compiling the skeleton, and **recording the honest result including any failure** is the active
focus in [NEXT.md](NEXT.md).

Two things follow that the next auditor should hold onto:

1. **That first compile will be a large drift event.** It will convert many "specified" statements
   into either "compiles" or "does not compile, here is why", and both outcomes contradict docs
   written before it. Run a full Lens A pass immediately afterwards, in the same sitting — the
   temptation to bank a green build and move on is exactly how the honesty position quietly decays.
2. **A green audit is not a green build, and never will be.** The checker reads text. Once a
   toolchain exists, a green Core test run proves Core logic and nothing a user can see; only a human
   executing [runbooks/manual-validation.md](runbooks/manual-validation.md) on a real desktop can
   speak to the Windows half ([OPERATING_MODEL §7](OPERATING_MODEL.md)).
