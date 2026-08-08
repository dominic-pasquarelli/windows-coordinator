---
name: audit
description: >-
  Run a Windows Coordinator audit — detect and remediate drift between the code and its
  documentation, and review for modularity (bespoke solutions that should be
  build-once-use-anywhere, Windows types leaking into Core). Use when the user asks to "audit",
  "check the docs are in line", "look for drift", "review modularity", before shelving a
  module/pillar, at the end of a phase, or when resuming after a long gap. Drives docs/AUDIT.md.
---

# Audit mode

You are running the **Windows Coordinator audit protocol**. The full contract is
[docs/AUDIT.md](../../../docs/AUDIT.md) — read it first if you have not this session. Your job: find
drift (code ↔ docs, and modularity), fix what is trivial and safe, route the rest, and **log the
audit** so repository health stays a tracked quantity rather than a vibe.

Scope to what the user asked for. Default scope = the whole repository. They may scope it ("audit
Conduit", "audit before I shelve Zones", "just the docs") — honor that, and name the scope in the log
entry.

## Before anything else: the honesty hazard specific to this project

**No .NET SDK was present in the environment this repository was authored in, and no C# in it has
ever been compiled.** Every description of a class, a project, an interface, or a lifecycle is a
*design* claim, never a *build* claim ([OPERATING_MODEL §7](../../../docs/OPERATING_MODEL.md)).

The single most dangerous drift this protocol guards against is a doc quietly upgrading one into the
other — "the host loads modules" where the truth is "the host is *specified* to load modules; it has
never been compiled." Lens A hunts that phrasing specifically. Carry it into every lens: a green
`coord audit` is a statement about text, a green `coord test` (once one is possible) is a statement
about Core logic, and neither is a statement about the desktop.

## Run it in this order

1. **Mechanical half — run the checker.**
   `coord audit` (i.e. `python3 tools/doc-audit/audit.py`). Use `--format json` if you want to parse
   it, `--quiet` for the summary plus ERRORs. This pre-screens Lens A (paths, links, frontmatter,
   the ADR sequence, map freshness) and Lens B (the Core/Shell and module boundary). Record the
   error / warn / info counts — you need them for the log, before and after.

2. **Judgement half — walk the six lenses** ([AUDIT.md §4](../../../docs/AUDIT.md)) over the scope:

   - **Lens A — alignment:** Is every doc still *true*, not merely present? Do the status claims
     ("phase N complete", "validated on the desktop", "NN/NN tests passing") still hold *today*?
     Is described == built in **both** directions — documented-but-not-built *and* the direction
     everyone skips, **built-but-catalogued-as-unbuilt**? Does [NEXT.md](../../../docs/NEXT.md)
     point at the real next step?
     **Reconcile ground truth against the catalogs before you log.** Run `ls src/modules/
     src/pillars/ src/platform/` and confirm the module table in the root README, the roadmap in
     [COORDINATOR.md](../../../docs/COORDINATOR.md), and the Status sections of
     [CLAUDE.md](../../../CLAUDE.md) / AGENTS.md describe each real module and pillar *as it
     actually is*. A **partially-updated** table is the most invisible drift there is — some current
     rows signal "tended" and disarm a skim. Verify every row, never a sample.
     Then grep the changed docs for *builds*, *works*, *passes*, *verified*, *tested*, *validated*,
     and hold each word to its evidence.

   - **Lens B — modularity & boundaries:** the standing concern. Ask **"would a *second* module need
     this?"** — if yes and it lives inside one module, it is bespoke code that belongs in the
     platform or in a pillar. And ask the question the checker exists for: **is any Windows type
     leaking into a Core project?** A `[DllImport]` / `[LibraryImport]`, a `Microsoft.UI` /
     `Windows.*` / `System.Windows` namespace, or a project reference to a Shell adapter inside a
     `net9.0` Core project breaks the central architectural commitment — not "just this once for a
     DPI value", because that one exception is how the testable half stops being testable.
     Also: does any module name an input mechanism instead of declaring a trigger intent to
     [Conduit](../../../docs/CONDUIT.md)? Does any module enumerate monitors or windows itself
     instead of reading an [Atlas](../../../docs/ATLAS.md) snapshot? Does any module reach into
     another module? Conversely — is there **speculative platform with no consumer** (the live
     instance is the Shell's pillar-graduation trigger; check both directions)?
     The checker pre-screens the mechanical part; the calls below are yours.
     **Run the propagation step** ([AUDIT.md Lens B](../../../docs/AUDIT.md)) on anything bespoke you
     find: lift shared **code** to the platform or a pillar; promote a shared **convention** into
     [MODULE_SPEC.md](../../../docs/MODULE_SPEC.md) *and propagate it*, so the spec stays a
     description of reality rather than an aspiration; write an ADR when the trade-off is
     non-obvious. A reusable pattern trapped in one module is a finding — record it, do not merely
     notice it.

   - **Lens C — resumability:** Could a cold reader — including the author, in a year — resume this
     in an hour? Walk the shelving contract, **all five items**:
     1. **A README** stating what it does, what's **done vs. TODO**, and what capabilities it
        publishes.
     2. **A "Where to resume" section** — in the README or the module's `docs/NEXT.md` — naming a
        **specific next action**: the function, the decision, the test that is failing. Not
        "continue work on layouts."
     3. **ADRs for the non-obvious decisions**, in the unified decision log, so future-you does not
        re-litigate a settled call or quietly reverse it.
     4. **Tests that pass** — `coord test` green for the module's Core project. **While there is no
        toolchain this item cannot be ticked at all** — record it as *unverified: no toolchain*,
        never as satisfied-by-default. A silently-ticked box is worse than an honest gap, because
        the gap is the first thing a cold reader needs to see.
     5. **An honest status line** on anything Windows-desktop-dependent: what was manually
        validated, on what machine, with what monitor arrangement and scaling, and when. Undated
        validation is not validation.

     *(Mirrors [MODULE_SPEC §7](../../../docs/MODULE_SPEC.md#7-the-shelving-contract) — if these
     disagree, §7 wins.)*

   - **Lens D — fidelity:** Does recent *behavior* still match
     [OPERATING_MODEL.md](../../../docs/OPERATING_MODEL.md)? Read **artifacts, not memory** — the
     commit log, the NEXT delta, the ADRs added, the audit-log entries since the last `audited` date.
     Did a **hard gate** creep into a workflow meant to steer (never-force)? Was anything built
     speculatively with no consumer? Did the retrofit-expensive set grow by feel rather than by an
     argument about shipped installs? Did discretionary effort go into making the platform invisible,
     or entirely into module rabbit holes? Was "the app must never make the desktop worse" treated as
     a constraint? On a contradiction, **two verdicts are co-equal**: practice drifted (steer it
     back) or the model is stale (revise it, plus an ADR). Do not default to correcting the behavior.

   - **Lens E — recall, drain & lifecycle:** Is the **maintenance loop closed**? Walk the `Proposed`
     ADRs, the `captured` [INBOX](../../../docs/INBOX.md) backlog, and the trip-wire table in
     [NEXT.md](../../../docs/NEXT.md): has any **deferral's trigger fired** (a .NET SDK arriving; a
     second consumer of the Shell's registry-driven surface; a second module wanting something the
     first one invented)? Is anything **built-but-not-closed-out** — shipped code with a `Proposed`
     ADR, a landed idea still marked `captured`? Does every deferral carry a **recall hook**, or is
     it buried rather than captured? Does every buffer drain —
     NEXT → [HISTORY](../../../docs/HISTORY.md), tech-debt rows → the paid-down ledger, triaged INBOX
     entries pruned to git? Capture is strong here; recall and drain are the weak sides.

   - **Lens F — connectivity / forward-compat:** Has a *built* thing **foreclosed a planned thing it
     must connect back to**? The two sharpest instances here are the **update/delivery channel**
     (could it carry this to an install already running on a machine you are not sitting at?) and
     **settings migration** (could an *additive* schema change extend this, or did a positional array
     or a neighbor-dependent value force a structural migration?). Then: are the reserved seams still
     open, were shared-substrate promises honored (module identity is the concrete one — settings,
     hotkey bindings and update manifests all reference it), and was new work **re-connected** to
     every sibling doc it should reach, and back? An orphan capture that is true but unreachable is a
     connectivity defect even when A–E are green. Mostly judgement, no mechanical pre-screen,
     WARN-grade.

3. **Classify every finding:** `real drift` vs `accepted` (illustrative / historical / planned — a
   template placeholder, a dated ADR path, a deliberately-not-built reference). Accepted findings get
   recorded so future audits do not re-triage them, and an accepted finding that stops being accurate
   is itself a finding.

4. **Log it.** Prepend an entry to [docs/audit-log.md](../../../docs/audit-log.md) using the skeleton
   in [AUDIT.md §7](../../../docs/AUDIT.md) — Fixed / Backlog / Accepted / Health. The Health block
   carries the **ground-truth reconciliations you actually performed**, not the ones you intended to,
   so a skipped dimension shows up as a missing line instead of an invisible omission. **If it is not
   logged, the audit did not happen.**

5. **Triage the real drift** (reuse the snapshot and steering protocol in
   [CLAUDE.md](../../../CLAUDE.md)):
   - *small + safe* → fix it now, in this pass (progress beats paperwork). Re-run the checker.
   - *larger sweep* → file it into [docs/NEXT.md](../../../docs/NEXT.md).
   - *known limitation / accepted coupling* → a `TD-NN` row in
     [docs/TECH_DEBT.md](../../../docs/TECH_DEBT.md), with the trip-wire that brings it back.
   - *non-obvious decision* → propose an ADR under `docs/decisions/`.
   - *stray idea* → capture it into [docs/INBOX.md](../../../docs/INBOX.md).

6. **Stamp accuracy.** For every doc you re-read and confirmed still true, set `audited: <today>` —
   and `updated:` too if you changed it. Confirming a doc is accurate *is* an audit; clearing the
   accuracy backlog is exactly this, one doc at a time.

7. **Drive ERROR to 0.** ERROR-level drift fails the gate by design. Do not call an audit complete —
   or a phase done, or a module shelved — with hard drift outstanding. A WARN backlog is fine to
   carry: it lives in the log, never in the gate.

## Principles

- **The point is true docs, not more docs.** A present-but-wrong doc is worse than none: it misleads
  with the authority of having been written down.
- **Be a skeptic, not a rubber stamp — especially Lens B.** The whole value of this platform is that
  work done years apart composes. A bespoke solution that should have been platform fabric, or a
  P/Invoke that crept into a Core project, is exactly what this audit exists to catch, and nothing
  fails at the moment it happens.
- **Never round evidence up.** "Not compiled" is the correct phrase until a compiler has run.
  "Manually validated" requires a scenario, a machine, and a date.
- **Do not auto-restructure the living docs.** Fix unambiguous drift; for judgement calls, propose
  and let the user confirm — the same rule as the snapshot protocol.
- **Report concisely.** End with: counts (error / warn / info, before → after), what you fixed, what
  you filed, and the single most important thing the human should look at.
