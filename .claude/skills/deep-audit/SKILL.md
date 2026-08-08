---
name: deep-audit
description: >-
  Run a Windows Coordinator DEEP audit — the heavier, rarer two-blind-passes reconciliation that
  catches drift the ordinary /audit cannot: form an expectation of the code from the docs alone, and
  of the docs from the code alone, then diff the two against reality. Use before a freeze, when
  resuming a pillar or module after a long gap, or periodically (quarterly). Scopeable to the whole
  project, a pillar, or a module. NOT for routine per-PR checks — that is /audit. Drives
  docs/AUDIT.md §4 (the deep-audit method).
---

# Deep audit — two blind passes, then reconcile

You are running the **Windows Coordinator deep audit**
([AUDIT.md §4](../../../docs/AUDIT.md) → "The deep audit"). It is the heavyweight complement to
[`/audit`](../audit/SKILL.md): where the six lenses read docs and code *together* — which biases
hard toward confirming what is written, because you read the claim and then go looking for the code
that backs it — the deep audit forms an **independent expectation from each side and diffs the
expectations**.

Run it **rarely**: before a [`/freeze`](../freeze/SKILL.md), on resume after a long gap, or roughly
quarterly. It is expensive, and running it every PR would be exactly the hard-gate creep that
never-force forbids ([OPERATING_MODEL §2](../../../docs/OPERATING_MODEL.md)). Its unique payoff is
the **agreed-but-wrong** finding: where the docs and the code match each other, and both drifted from
the design that was actually intended.

## 1. Scope it

Default = the whole project. The user may scope it — honor that and note it in the log.

| Scope | Code side | Doc side |
|---|---|---|
| **Project** | all of `src/`, `tools/`, `tests/` | every `.md` in the repository |
| **Pillar** | `src/pillars/conduit/` or `src/pillars/atlas/` | [CONDUIT.md](../../../docs/CONDUIT.md) or [ATLAS.md](../../../docs/ATLAS.md), plus that pillar's own README |
| **Platform** | `src/platform/` and `src/shell/` | [COORDINATOR.md](../../../docs/COORDINATOR.md), [MODULE_SPEC.md](../../../docs/MODULE_SPEC.md), the platform README |
| **Module** | one directory under `src/modules/` | that module's README and docs |
| **Tooling** | `tools/coord/` and `tools/doc-audit/` | those tools' READMEs, [AUDIT.md](../../../docs/AUDIT.md), [DOC_SPEC.md](../../../docs/DOC_SPEC.md) |

Always pass the **structure docs** — [COORDINATOR.md](../../../docs/COORDINATOR.md),
[MODULE_SPEC.md](../../../docs/MODULE_SPEC.md), [MAP.md](../../../docs/MAP.md) — to Pass B for
**vocabulary only**: names, tiers, and the model. Never their status claims. Pass B exists to say
what the docs *should* say; feeding it what they *do* say destroys the method.

## 2. Run the two passes

Drive it as a workflow: the two passes are parallel subagents, the reconcile is a synthesis stage.
The blindness is the whole mechanism, and you enforce it by giving each pass agent only its half.

- **Pass A — doc → expected code (blind to the code).** Agents read ONLY the `.md` in scope. Each
  emits an *expectation*: the projects, types, members, capability ids, trigger-intent kinds,
  settings keys, behaviors, and test suites the docs imply the code MUST contain. They never open a
  source file.
- **Pass B — code → expected docs (blind to the doc claims).** Agents read ONLY the code in scope,
  plus the structure docs for vocabulary. Each emits an *expectation*: what the docs SHOULD say — the
  real projects, the real interfaces, the real capability ids, the real settings shapes, the real
  toolchain state. They never read the prose claims they are checking.
- **Reconcile** — one synthesis agent (or you) diffs **A ↔ reality**, **B ↔ reality**, and **A ↔ B**:
  1. **Doc over-claim** — A expected code that is not there. Aspiration written as fact. → fix the
     doc.
  2. **Code under-documented** — B expected docs that do not exist. Built, undocumented. → write the
     doc.
  3. **Agreed-but-wrong** — A and B agree with each other *and* with the code, yet all three drift
     from the intended design in [COORDINATOR.md](../../../docs/COORDINATOR.md) or the ADRs: "we
     specified X, documented X, and X was never what we meant." → surface it; it is a design call,
     not a typo.

Use structured-output schemas so the expectations come back as data rather than prose. Scale the
agent count to scope: one module is one agent per pass; the whole project means partitioning the
`.md` set and the code tree into batches.

## 3. The caveat that is specific to this repository — state it in the reconciliation

**The C# compiles and its Core logic is tested (CI `7aef6ff`), but nothing here has ever run.**
Pass B is therefore reading a *partly-verified specification expressed in C#*,
not a running system, and you must say so in the write-up rather than letting the output imply
otherwise.

What that does to the method:

- It still finds real drift — an interface with no doc, a doc describing a member nobody wrote, a
  capability id spelled two ways, a settings key that exists in one place and not the other.
- It **cannot** find behavioral drift, because there is no behavior. Anything a pass "expects" about
  what happens at runtime is an expectation about intent, not about observation.
- Pass B has a standing finding available to it that Pass A can never see: **a doc whose confidence
  exceeds the toolchain's existence.** If the code side shows a project that has never been through
  a compiler and the doc side reads as though it runs, that is a doc over-claim of the most dangerous
  kind ([OPERATING_MODEL §7](../../../docs/OPERATING_MODEL.md)) — flag it at ERROR-grade urgency even
  though the mechanical checker cannot see it.

The **first successful compile is the single highest-value moment to run this**, because it converts
a large number of "compiles but unexercised" statements into either "runs" or "does not run,
here is why" — and both outcomes are drift against every doc written before it.

## 4. Reconcile → fix → log (same routing as /audit)

- **Doc over-claim** and **code under-documented** are ordinary drift: fix the trivial and safe ones
  in this pass, route the rest into [NEXT.md](../../../docs/NEXT.md), a `TD-NN` row in
  [TECH_DEBT.md](../../../docs/TECH_DEBT.md), or an ADR under `docs/decisions/`
  ([AUDIT.md §6](../../../docs/AUDIT.md)).
- **Agreed-but-wrong** is a judgement call about the *design*, not a typo — do **not** auto-"fix" it.
  Surface it to the owner, exactly the way Lens D treats a behavior ↔ model contradiction as two
  co-equal verdicts: the code may be right and the doc's intent stale, or the reverse.
- **Log it** in [docs/audit-log.md](../../../docs/audit-log.md)
  ([AUDIT.md §7](../../../docs/AUDIT.md)) — mark it a **deep** audit, name the scope, and record the
  three finding counts. If it is not logged, the audit did not happen.
- Re-run `coord audit` after the fixes, so ERROR stays 0.

## Principles

- **Blindness is non-negotiable.** The moment a pass sees the other side, the method degrades into
  the ordinary lenses and you have spent the cost without buying the payoff. Keep the halves
  separate, and enforce it in how you construct the agents, not by asking them nicely.
- **The third class is why you ran this.** Doc over-claims and undocumented code get caught
  eventually by `/audit` and the accuracy sweep. *Agreed-but-wrong* — the project quietly building
  something other than what it meant — is what only this pass surfaces. Spend your attention there.
- **Rare by design.** Freeze-time, resume-time, first-compile-time, quarterly. Not a gate.
