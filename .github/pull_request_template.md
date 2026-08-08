<!--
Windows Coordinator PR template — the definition-of-done as a checklist, assembled from the working
agreements in CLAUDE.md, the audit protocol in docs/AUDIT.md, and the documentation contract in
docs/DOC_SPEC.md.

Delete the sections that genuinely do not apply. And the rule that governs every box below:

    an honest "N/A — why" beats a checked box that is not true.

A checked box is a claim, and this project's evidence standard (docs/OPERATING_MODEL.md §7) says a
successful command must mean the claimed outcome actually occurred. The three failure shapes it
names — a check that cannot fail · a claim stronger than its evidence · an error found after the
expensive step — all start here, with someone ticking a box because the shape of the form asked for
a tick. An unticked box with a sentence next to it costs the reviewer five seconds. A wrongly ticked
one costs a future reader a day, and it costs them the ability to trust every other box on every
other PR.
-->

## What & why

<!-- One paragraph. What this changes, and the motivation. Link the issue, the ADR, or the
     docs/NEXT.md item it came from. If it came from an audit finding, say which lens. -->

## How it was verified

<!-- Be specific about which half of the evidence you have. Core-verified and Windows-validated are
     different words because they are different facts, and the gap between them is where this
     project's honesty is won or lost. -->

- [ ] `coord test` — Core suites green *(net9.0 logic only)*
- [ ] `coord audit` — **0 ERROR**
- [ ] `coord audit --since origin/main` — closeout clean: every changed doc bumped `updated`
- [ ] `coord build` — the C# compiles
- [ ] **Manual validation on a real Windows desktop** — the relevant entries of
      [docs/runbooks/manual-validation.md](../docs/runbooks/manual-validation.md) actually
      performed, **or** an explicit `N/A — <why>`

**Manual validation, when performed, must be recorded — not asserted.** Name the scenarios, the
machine, the monitor arrangement and scaling, and the date. Undated validation is not validation.

```
Manually validated: <scenarios>  ·  <machine>  ·  <n monitors, scaling>  ·  <YYYY-MM-DD>
Not validated:      <what still needs a real desktop, and why it could not be done here>
```

> **What each green tick is allowed to mean.** `coord audit` green is a statement about *text* —
> links, frontmatter, paths, the boundary as written. `coord test` green is a statement about *Core
> logic* — geometry, scheduling, arbitration, settings migration — and about nothing a user can see.
> `coord build` green is a statement that the C# *compiles*. **None of the three says anything about
> window placement, hotkey capture, DPI behavior, the tray, or the UI.** Only a human at a real
> desktop, following the runbook, can say that.
>
> While no .NET SDK is available, the honest state of the last three boxes is `N/A — no toolchain;
> nothing has been compiled` (TD-1 in [docs/TECH_DEBT.md](../docs/TECH_DEBT.md)). Write that. Do not
> leave them blank, and do not tick them.

## Modularity & docs (the load-bearing parts)

- [ ] **Boundary intact** — no Windows type, `Microsoft.UI` / `Windows.*` namespace, or
      `[DllImport]` / `[LibraryImport]` in a **Core** project; no module referencing another module;
      no module registering its own input hook (that is [Conduit](../docs/CONDUIT.md)); no module
      enumerating monitors, windows, or work areas itself (that is [Atlas](../docs/ATLAS.md))
- [ ] **Bespoke → reusable considered** — would a *second*, unrelated module want this? If yes, it
      was lifted to the platform or a pillar (shared **code**), or promoted into
      [docs/MODULE_SPEC.md](../docs/MODULE_SPEC.md) (a shared **convention**), rather than left
      local. If no, say so — one consumer is not yet an abstraction, and over-lifting is its own
      failure
- [ ] **Docs follow the code** — every touched canonical doc bumped its `updated` frontmatter;
      `audited` stamped on anything re-read and confirmed still true;
      [docs/NEXT.md](../docs/NEXT.md) still points at the *real* next step, not a finished one
- [ ] **Non-obvious decision?** — an ADR added under `docs/decisions/`, in sequence, with its
      Context / Decision / Consequences / Alternatives considered
- [ ] **New or changed known limitation?** — a `TD-NN` row in
      [docs/TECH_DEBT.md](../docs/TECH_DEBT.md), with the trip-wire that brings it back
- [ ] **Nothing built speculatively** — every new seam has a real consumer, or is an empty seam plus
      a recall hook. Capture is free; building costs ([docs/OPERATING_MODEL.md](../docs/OPERATING_MODEL.md) §3)

## Notes for the reviewer

<!-- The single most important thing to look at, and anything you are unsure about. If you added a
     guard, say whether you watched it fail without the fix — a guard nobody has seen fail is
     decoration, and "I proved it fails without the fix" is the most useful sentence in this box. -->
