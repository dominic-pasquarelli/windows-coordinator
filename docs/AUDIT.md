---
title: Windows Coordinator Audit Protocol
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/DOC_SPEC.md
  - docs/audit-log.md
  - docs/OPERATING_MODEL.md
  - docs/MODULE_SPEC.md
  - docs/COORDINATOR.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
---

# Windows Coordinator Audit Protocol — keeping code and docs in line

> The discipline that keeps this project resumable. Read it before running an audit; skim it when
> you finish a phase, shelve a module, or come back after a gap. It defines **what an audit checks,
> how to run one, and where the findings go.**
>
> **One sentence:** an audit is the scheduled act of proving the repository's claims are still
> true — a mechanical half (`coord audit`) that finds the drift a human reliably misses, and six
> judgement lenses that find the drift a script structurally cannot see — and it is not an audit
> until it is written into [audit-log.md](audit-log.md).
>
> **Invoke it:** the [`/audit` skill](../.claude/skills/audit/SKILL.md) drives this protocol
> end-to-end. **Automate the cheap half:** `coord audit` (i.e. `tools/doc-audit/audit.py`).

---

## 1. Why this exists

Windows Coordinator is built in bursts around a day job, and its whole bet
([OPERATING_MODEL §1](OPERATING_MODEL.md), [COORDINATOR §7](COORDINATOR.md#7-non-negotiable-principles)
principles 9–10) is that any
module can be put down for months and picked up cold in about an hour — because the documentation is
load-bearing and the seams are clean. Two forces erode that bet quietly, without ever announcing
themselves.

**Documentation drift.** Docs are easy to write well *once*. The hard part is keeping them **true**
while the code moves underneath them. A renamed project, a moved directory, a finished TODO, a
capability id that changed, a "verified" that was never re-verified — each leaves a doc subtly
lying. The lies compound: the next reader trusts a stale map, burns the hour the docs were supposed
to save, and afterwards stops trusting the docs at all. At that point you have all of the
maintenance cost and none of the benefit.

**Modularity drift.** The value of the platform is that work done years apart composes. Every
bespoke solution that should have been a platform service, every module that reaches past its
membrane to grab a hotkey or enumerate monitors itself, every P/Invoke that leaks into a Core
project, quietly turns reusable fabric back into a one-off. Nothing fails when this happens — that
is exactly the problem. It shows up two years later as "why does adding a second module require
touching four files in the first one?"

An audit detects both **before they compound**, and logs the result so the health of the repository
is a tracked quantity rather than a vibe.

> **The point is not to generate documents. The point is to keep the documents *true*.** A doc that
> is present but wrong is worse than no doc: it actively misleads, with the authority of having been
> written down.

**The highest-risk instance in this repository, today.** No .NET SDK has ever been present in the
environment this project was authored in — **not one line of C# has been compiled**
([OPERATING_MODEL §7](OPERATING_MODEL.md)). Every description of a class, a project, an interface,
or a lifecycle is therefore a *design* claim, never a *build* claim. The single most dangerous drift
this protocol guards against is a doc that quietly upgrades one into the other: "the platform host
loads modules" instead of "the platform host is specified to load modules; it has never been
compiled." Lens A hunts that phrasing specifically, and it stays a live hazard until a compile is
attempted on a real Windows machine and its **honest** result — including a failure — is recorded.

---

## 2. The two halves of an audit

An audit has a **mechanical half** (a script catches what a script can catch) and a **judgement
half** (a person or an AI catches what only judgement can). Neither substitutes for the other, and
the division of labor is deliberate: the mechanical half exists to make the boring drift *free to
find*, so the audit's scarce attention goes where only a brain helps.

| | Mechanical (`coord audit`) | Judgement (the six lenses, §4) |
|---|---|---|
| **Catches** | rotted links, dead path references, ADR sequence gaps, missing shelving docs, boundary violations, a stale [MAP.md](MAP.md), a changed doc that never bumped `updated` | bespoke-vs-reusable, a doc that is *present but no longer true*, a claim stronger than its evidence, missing rationale, resumability gaps, foreclosed future seams |
| **Cost** | seconds; stdlib-only Python, needs no .NET | minutes to hours; run at phase ends, before shelving, on request |
| **Output** | exit code + finding list | a log entry + triaged follow-ups |
| **Can it judge "is this still *true*"?** | **No** — only "does this path still *exist*" | **Yes** |

**What the checker structurally cannot judge.** It reads text; it does not understand it. It cannot
tell you whether a doc's description of the settings-migration design still matches the code, whether
a module's layout math *should* have been lifted into Atlas, whether [NEXT.md](NEXT.md) points at a
useful next step or a finished one, whether a decision was quietly reversed rather than superseded,
or whether "manually validated" was ever actually performed on a real desktop. It also cannot tell
the difference between a path that is missing because it was deleted and one that is missing because
it was never built yet — that classification is step 3 of the workflow (§6), and it is judgement.

Crucially, **the checker cannot verify anything about C#**. It reads `using` lines, namespaces,
`[DllImport]` attributes and `.csproj` `ProjectReference` elements as *text*. That is a real,
working boundary check — it will genuinely catch Win32 leaking into a Core project — but a green
`coord audit` is a statement about text, never about a compiler. Do not let a green audit drift into
sounding like a green build.

**On CI.** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) defines the intended gate:
mechanical audit, map check, and (once a toolchain exists) the Core test run. It is a *definition*
of the gate, not evidence that the gate has run. Treat the authoritative gate as **`coord audit`
executed locally at closeout**, and never describe a green or absent workflow as validation.

---

## 3. When to audit

| Trigger | Scope | Half |
|---|---|---|
| **Closing out a branch** | the diff | mechanical — `coord audit --since origin/main` ([DOC_SPEC §6](DOC_SPEC.md)) |
| **End of a phase** (definition of done) | the touched subtree + its docs | both |
| **Before shelving a module or pillar** | that subtree | both, especially Lens C |
| **Resuming after a gap** | what you are resuming | both — audit *first*, trust the docs *second* |
| **On request** (`/audit`) | as scoped | both |
| **Before a freeze** | whole repo | the `/freeze` ceremony ([DOC_SPEC §7](DOC_SPEC.md)) + a comprehensive pass |
| **After a large change or a concept-heavy session** | whole repo | comprehensive (§4) — all six lenses + the deep reconciliation |
| **Periodic** (when it has just been a while) | whole repo | both |

> **Shelving without an audit is the most expensive mistake available in this project.** You bank a
> module as "resumable" when it is not, and you discover the rot only much later — when you have also
> forgotten everything else that would have let you recover quickly.

**One trigger is specific to this repository's current state:** the first time a .NET SDK is present
and the skeleton is compiled, run a full Lens A pass immediately afterwards. That compile will
convert a large number of "specified, not compiled" statements into either "compiles" or "does not
compile, here is why" — and both outcomes are drift against every doc written before it.

---

## 4. The six lenses (the judgement half)

Walk all six. The mechanical checker pre-screens parts of A and B and nudges D and E; C and F, and
the deeper judgement inside every lens, are yours.

### Lens A — Code ↔ Doc alignment ("is every doc still *true*?")

Drift between what the docs say and what the repository actually contains.

- [ ] **Paths and links resolve** (checker: `doc-link`, `code-ref`, `related`). Every file and
      directory a doc names exists.
- [ ] **Status claims still hold.** "Phase N complete", "validated on the desktop", "NN/NN tests
      passing" — are they still true *today*? The checker can surface such a claim for re-reading; it
      cannot evaluate it. Only running the thing evaluates it.
- [ ] **Build and validation language is exactly as strong as its evidence.** This is the sharpest
      instance of Lens A here, so give it its own pass: grep the changed docs for *builds*, *works*,
      *passes*, *verified*, *tested*, *validated*. Until a compiler has actually run, the correct word
      is **"not compiled"**. Until a human has executed
      [runbooks/manual-validation.md](runbooks/manual-validation.md) on a real desktop, no statement
      about window placement, hotkey capture, DPI behavior, or the tray is permitted to sound settled.
      A green Core test run — once one is possible at all — proves Core logic and nothing a user can
      see ([OPERATING_MODEL §7](OPERATING_MODEL.md)).
- [ ] **Governance docs re-read against the frontier.** [CLAUDE.md](../CLAUDE.md),
      [AGENTS.md](../AGENTS.md), and the root [README.md](../README.md) carry no `updated`/`audited`
      frontmatter ([DOC_SPEC §3](DOC_SPEC.md)), so they are exempt from the closeout and accuracy
      checks — which means their Status sections rot **unchecked**. A whole-repo or end-of-phase audit
      must re-read them against the real ADR frontier (`ls docs/decisions/ | tail`), the real module
      set, and the real toolchain state, and bring them current. Exempt from the *gate* is not exempt
      from the *audit*.
- [ ] **Described == built, direction 1: documented-but-not-built.** Anything a doc describes as
      existing must exist; anything that does not must be *unmistakably* marked planned. At this
      stage of the project that is nearly the whole surface — Zones and Chrono are roadmap entries
      with no code at all ([COORDINATOR.md §8](COORDINATOR.md)) — so the failure mode is a sentence
      written in the present tense about something that has never existed.
- [ ] **Described == built, direction 2: BUILT-but-catalogued-as-unbuilt.** This is the direction
      that gets skipped, so give it teeth: **enumerate the ground truth first, then diff it against
      the catalogs.** List `src/modules/` and `src/pillars/`; for every subtree found, confirm the
      module table in [README.md](../README.md) and the roadmap in [COORDINATOR.md](COORDINATOR.md)
      describe it at its real state. A built module sitting in a "planned" row, or missing from the
      table entirely, is ERROR-grade drift. **Heuristic: a partially-updated table is the most
      invisible drift there is** — the presence of *some* current rows signals "tended" and disarms a
      skim. Check every row against the tree, never a sample.
- [ ] **[NEXT.md](NEXT.md) points at the real next step.** A stale "resume here" is a resumability
      landmine: it is the one line a cold reader trusts completely and verifies least.
- [ ] **ADRs match reality.** A decision the code no longer follows must be marked superseded by a
      successor ADR, not silently contradicted. Silent contradiction is how a settled call gets
      re-litigated a year later by someone who reads the ADR and believes it.
- [ ] **Bump `audited` on every doc you re-confirmed.** Re-reading a doc against the code and finding
      it still true *is* an accuracy audit — record it by setting `audited: <today>`
      ([DOC_SPEC §3](DOC_SPEC.md)). Clearing the `accuracy` backlog is exactly this lens, one doc at
      a time.

### Lens B — Modularity & boundaries ("is anything bespoke that should be reusable?")

The standing concern: build-once-use-anywhere. Apply the platform-vs-module test from
[CLAUDE.md](../CLAUDE.md) and the do's and don'ts in [MODULE_SPEC §8](MODULE_SPEC.md).

- [ ] **"Would a second module need this?"** If yes, and it lives inside one module, it is a bespoke
      solution that belongs in `src/platform/` or in a pillar. Flag it — then run the propagation
      step below rather than just noting it.
- [ ] **No Windows in Core** (checker: `boundary`). A `net9.0` Core project containing a
      `[DllImport]`, a `Windows.*` / `Microsoft.UI.*` namespace, or a project reference to a Shell
      adapter is a violation of the central architectural commitment
      ([COORDINATOR.md §3](COORDINATOR.md)). Not "just this once for a DPI value" — that one
      exception is how the testable half stops being testable.
- [ ] **No module names an input mechanism.** A module declares a **trigger intent** and lets
      [Conduit](CONDUIT.md) arbitrate. A `RegisterHotKey`, a `SetWindowsHookEx`, a WinEvent hook, or
      a private timer loop inside a module is the leak — and it is the one that cannot be fixed
      later, because two modules that each grabbed a chord directly cannot be reconciled after the
      fact.
- [ ] **No module enumerates the desktop.** Monitors, work areas, DPI, virtual desktops, and window
      geometry come from an [Atlas](ATLAS.md) snapshot. A second cache is a second truth, and the two
      will disagree at exactly the moment it matters — mid-drag, on a monitor change.
- [ ] **No module reaches into another module.** No project reference, no shared static, no reading
      another module's settings. Two modules that must cooperate is a platform feature with an ADR.
- [ ] **Duplication across modules or pillars.** The same logic written twice is a missing shared
      abstraction. **Two real consumers is the moment to lift it; one is not** — with a single
      consumer, leave the seam and do not over-abstract.
- [ ] **One concern, one home** ([DOC_SPEC §4](DOC_SPEC.md)). The same feature described in
      [COORDINATOR.md](COORDINATOR.md) *and* [CONDUIT.md](CONDUIT.md) *and* a module README is a
      single-source violation — and an early warning that the boundary itself is undecided.
      Consolidate to the owning tier; the others link.
- [ ] **No speculative platform.** The inverse failure: an abstraction with no consumer. The live
      instance is the **Shell's pillar-graduation trigger** ([COORDINATOR.md §5.1](COORDINATOR.md)) —
      check both directions. Has the Shell been promoted to a pillar without the second independent
      consumer that was supposed to trigger it? Or has that consumer arrived while the docs still
      call it "one consumer, deliberately not a pillar"?
- [ ] **Registry pattern used where extension is expected.** Adding a module, a trigger-intent kind,
      or a layout template should be a drop-in plus a registration, not an edit to N files. If adding
      the second one required touching the first one, the seam is wrong.

#### The propagation step — "bespoke in one module → promote for all?"

Lens B does not stop at *flagging*. When you find a pattern, helper, or convention that one module
solved for itself, run it through this decision and act on the answer:

```
Found something bespoke in module X. Ask, in order:
1. Would a SECOND module want this?   (the platform-vs-module test)
   → No  → leave it. One consumer = no abstraction yet; don't over-build.
2. Is it LIFECYCLE, SETTINGS, IDENTITY, UPDATE, DIAGNOSTICS, INPUT, or DESKTOP-GEOMETRY shaped?
   → Yes → it is platform fabric or pillar fabric. LIFT the code to src/platform/,
            or to Conduit / Atlas, and leave the module calling it.
3. Is it a CONVENTION every module should follow (a contract, not shared code)?
   → Yes → promote it into docs/MODULE_SPEC.md and PROPAGATE: file a follow-up to bring the
            other modules into line, so the spec stays a description of reality, not an aspiration.
4. Non-obvious trade-off?  → write an ADR before propagating.
```

> **The asymmetry to remember:** *shared code* belongs in the platform or a pillar — one
> implementation, many callers. A *shared convention* belongs in [MODULE_SPEC.md](MODULE_SPEC.md) —
> each module implements it, the spec describes the contract. Choosing wrong is how you get either a
> god-object platform or a spec nobody follows.

**Do not silently let a good idea stay local.** If one module invented something the others would
benefit from, that *is* a finding — record it exactly like a broken link (Backlog → "lift to
platform" or "propagate to MODULE_SPEC"). A reusable pattern trapped in one module is the
slow-motion version of the drift this whole audit exists to stop.

### Lens C — Resumability & shelving ("could a cold reader pick this up in an hour?")

Apply the shelving contract, [MODULE_SPEC §7](MODULE_SPEC.md#7-the-shelving-contract), item by item —
**all five of them**.

- [ ] **A README** stating what the module does, what is **done vs. TODO**, and what capabilities it
      publishes.
- [ ] **A "Where to resume" section** — in the README or the module's `docs/NEXT.md` — naming a
      **specific** next action: the function, the decision, the test that is failing. "Continue work
      on layouts" is not a resume anchor; "the multi-monitor path is stubbed at the work-area union —
      decide whether zones may span monitors before writing it" is.
- [ ] **ADRs for the non-obvious decisions**, in the unified decision log, so future-you does not
      re-litigate a settled call or quietly reverse it.
- [ ] **Tests that pass** — `coord test` green for the module's Core project. Not
      "feature-complete"; just "correct as far as it goes." **Until a .NET SDK is present, this item
      cannot be ticked at all** — record it as *unverified: no toolchain*, never as
      satisfied-by-default. A silently-ticked box is worse than an honest gap, because the gap is the
      first thing a cold reader needs to see.
- [ ] **An honest status line** on anything Windows-desktop-dependent: what was manually validated,
      on what machine, with what monitor arrangement and scaling, and when. Undated validation is not
      validation.

*(Mirrors [MODULE_SPEC §7](MODULE_SPEC.md#7-the-shelving-contract) — if these disagree, §7 wins.)*

- [ ] **The judgement question the checklist cannot ask:** could someone who has never seen this code
      — including you, in a year — get productive from these docs in an hour? The checker verifies a
      README *exists*; only you can judge whether it is *sufficient*.

### Lens D — Fidelity ("does practice still match the operating model?")

A, B, and C check the *artifacts*. This lens checks the **project's own behavior** against the stated
philosophy in [OPERATING_MODEL.md](OPERATING_MODEL.md). It is the only lens whose referent is not a
file — a code↔doc check passes a philosophy doc green forever while the philosophy quietly erodes
underneath it.

**Evidence — read artifacts, not memory.** "How we have been working lately" *feels* recallable, but
a lens that runs on recollection is precisely the unauditable input this project exists to
externalize. So Lens D reads the **artifacts of behavior** since the doc's last `audited` date: the
commit log over the relevant paths, the [NEXT.md](NEXT.md) delta, the ADRs added, the audit-log
entries. Each box below is a *query against an artifact*. If you cannot point a check at one, you are
guessing — name the artifact first.

- [ ] **Never-force held** ([§2](OPERATING_MODEL.md)). Read the process, tooling, and audit changes:
      did a **hard gate** creep into a workflow that is supposed to steer? This includes the audit's
      own rules — a new check that *blocks* progress on a judgement call is itself the violation.
      Lenses flag; they do not force. On a burst-driven project, friction becomes avoidance, and
      three avoided evenings in a row is a shelved project.
- [ ] **Building stayed gated** ([§3](OPERATING_MODEL.md)). Scan the new-feature commits: was anything
      built speculatively, with no real consumer? A third pillar with one hypothetical user, a module
      scaffolded "so it is ready", an abstraction whose second implementation is imagined. Capture is
      free; *building* costs — a spec, an ADR, or an INBOX capture was the cheap alternative.
- [ ] **The retrofit-expensive set is honored, and nothing joined it by accident**
      ([§3](OPERATING_MODEL.md)). Update channel, module identity, settings migration, trigger
      arbitration — those four get built now, and the discipline is that the list does *not* grow
      because something felt important. A fifth entry needs an argument about shipped installs.
- [ ] **Friction-removal still ranks right** ([§6](OPERATING_MODEL.md)). Where did *discretionary*
      effort go — into making the platform invisible (reliability, diagnostics, the update path, the
      Shell's get-out-of-the-way behavior), or was it all module rabbit holes? This governs
      discretionary choices only; a live module fixation is protected by never-force and always wins.
- [ ] **"The app must never make the desktop worse" was treated as a constraint, not a nice-to-have**
      ([§6](OPERATING_MODEL.md)). Did anything land that could plausibly block a hook, add drag
      stutter, hold a chord the user needed, or burn CPU at idle — without that being examined?
- [ ] **Resume fidelity is practiced, not just preached** ([§4](OPERATING_MODEL.md)). Were modules
      and phases actually shelved with a real "where to resume" and real ADRs? Were detour anchors
      dropped and cleared? The keystone is only load-bearing if it is used.

#### The doctrine step — "behavior drifted from the model → which one bends?"

When behavior contradicts the operating model, **two verdicts are equally legitimate**: the
*practice* drifted, or the *model* is stale and the practice is right. Do **not** default to
correcting the behavior — OPERATING_MODEL is descriptive, and on a one-person, burst-driven project
the model is often the thing that is wrong, because you learn things at the keyboard that the
doctrine did not anticipate.

```
Behavior contradicts OPERATING_MODEL §N. Ask, in order:
1. One-time slip?  (one module left un-shelved, one urgent override)
   → Log it; steer back. It clears next pass.
2. A PATTERN across recent work?  Then one of two CO-EQUAL verdicts holds — decide, don't default:
   • model holds, practice eroded → file "review §N" into docs/NEXT.md + note it in the audit log;
                                     steer practice back.
   • practice is right, model is stale → revise OPERATING_MODEL.md deliberately, plus an ADR if the
                                     change is non-obvious. This is NOT the rare exception.
```

> **The asymmetry:** A/B/C are reactive — find breakage, fix it. D is diagnostic — *is the system
> still being run on its stated principles, and should it be?* Both verdicts keep the system healthy;
> a deliberately evolved model is as good an outcome as corrected practice. The failure is **silent**
> drift: practice diverging while the doc still claims the old philosophy. Guard the "model is stale"
> branch specifically — if it is technically available but never taken, Lens D has quietly become a
> cage, which is the exact failure mode the never-force rule exists to prevent, aimed at the audit
> itself.

### Lens E — Recall, drain & lifecycle ("did the deferred thing get its turn? did the settled thing leave?")

The other lenses run *forward*: does the doc match the code, now. This one closes the **maintenance
loop** that strong capture machinery does not close on its own. This project captures relentlessly —
the snapshot protocol, [INBOX.md](INBOX.md), ADRs, the tech-debt register — and capture needs two
symmetric closing moves: **recall** (a deferred idea can resurface) and **drain** (a settled item
leaves the active working set).

Without recall it is a write-only log: a deferred idea never comes back, an implemented decision is
never marked done. Without drain the buffers clog: the INBOX fills with already-landed captures, the
ADR log becomes an undifferentiated wall of "Accepted", NEXT fills with completed history, and the
live working set drowns in settled noise. Both failures are invisible to A–D — every artifact is
internally consistent, it is just *cold* or *cluttered*.

- [ ] **Deferred-now-feasible.** Walk the `Proposed` ADRs, the `captured` INBOX backlog, and the
      recall hooks in [NEXT.md](NEXT.md): has the **trigger** that gates any of them actually fired?
      Three live ones right now: *a .NET SDK becoming available* (which unblocks the entire
      compile-and-verify chain), *a second independent consumer of the Shell's registry-driven
      surface* (which graduates it to a pillar), and *a second module wanting something the first one
      invented* (which promotes that pattern under Lens B).
- [ ] **Built-but-not-closed-out, both ends.** *Recall end:* a decision whose code shipped while its
      ADR still says `Proposed`; an INBOX entry whose idea landed while it still says
      `Status: captured`. *Drain end:* a settled `Accepted` ADR with no closure token on its Status
      line, so it cannot be told apart from one that is still actively guiding work. Close them out —
      flip the status, add the token, point at what shipped.
- [ ] **Buffer drainage — every buffer names its drain** ([OPERATING_MODEL §3](OPERATING_MODEL.md)).
      `NEXT.md → HISTORY.md` for settled work; `TECH_DEBT.md` active → paid-down ledger; INBOX
      entries marked `triaged → <where>` and then **pruned to git** (it is a *buffer, not an
      archive*); ADRs given a closure token so the active set stays a one-line grep. Drain at a
      freeze or at a threshold, **never as a gate**.
- [ ] **Recall hook present (the deferral convention).** Deferring is fine; *silently* deferring is
      the failure. Every deferred decision or idea names its recall surface — a [NEXT.md](NEXT.md)
      item, a tech-debt row with a trip-wire, or an explicit "revisit when X" trigger. No hook means
      it cannot come back. This is a **convention surfaced by an advisory check**, never a hard gate:
      a blocking "you may not defer" rule would violate capture-is-free outright.
- [ ] **Doc-set hygiene.** Any doc that should no longer exist (superseded, redundant), is cold and
      should be marked `status: historical`, or should consolidate into another under the
      single-source rule. Be conservative — a wrong delete is expensive, and the `orphan` signal is a
      nose, not a verdict.

> **Why this is its own lens and not part of A:** A asks "is what is written *true*?" — a cold but
> accurate doc passes A green. E asks "is the *loop closed*?" — the deferred thing recalled, the
> shipped thing retired, the dead doc cleared. Resume fidelity needs both: an accurate map, and one
> that does not slowly fill with deferred ghosts and tombstones.

### Lens F — Connectivity & forward-compatibility ("does the built foreclose the planned?")

The other lenses ask whether docs and code agree about what *exists*. This one treats the
documentation as load-bearing design and asks the **forward** question: has an *implemented* thing
quietly **foreclosed a planned thing it is required to connect back to?**

This project's entire forward-compatibility discipline — the additive-settings rule
([COORDINATOR §7](COORDINATOR.md#7-non-negotiable-principles) principle 6), stable module identity,
the build-now retrofit-expensive set
([OPERATING_MODEL §3](OPERATING_MODEL.md)) — is a **promise** that the built thing leaves the planned
thing reachable. Nothing else checks that the promise held. This lens does.

- [ ] **The sharpest instance for this project — the two channels.** *Update/delivery:* has anything
      been built that the update channel could not later carry to an install already running on a
      machine you are not sitting at? A resource written outside the managed install layout, a
      component that cannot be replaced while the tray host is resident, a version assumption baked
      into a settings file. *Settings migration:* has anything been built that an **additive** schema
      change could not extend — a positional array where a named field was needed, a value whose
      meaning depends on its neighbors, a shape that forces a structural migration for what should
      have been a new optional field?
- [ ] **Reserved seams still open.** For each reserved, planned, or trip-wired concept — a deferred
      pillar, a "leave this seam empty" decision, a recall hook, a stated forward-compat constraint —
      confirm the shipped code and docs still leave its connection point intact. A flat assumption
      hardened into code that forecloses a reserved seam is exactly the defect this lens catches.
- [ ] **Generic-substrate constraints honored.** Where a doc promised a *substrate* shared by a built
      feature and a planned one, check the built side actually stored it generically. The concrete
      case here is **module identity**: settings, hotkey bindings, and update manifests all reference
      it, so an identity stored in a form specialized to one of those three forces a rewrite to add
      the others.
- [ ] **New work re-connected.** When a feature lands or a concept is captured, was every **sibling**
      doc it should reach updated to point at it — and back? An orphan capture that is true but
      unreachable from its neighbors is a connectivity defect even when A–E are all green.

> **Why this is its own lens:** A asks "is the written thing true *now*?"; E asks "did the loop
> *close*?"; F asks the **relational, forward** question — "does the built thing keep the *planned*
> thing reachable?" A foreclosed forward-connection passes A (everything written is true) and passes
> E (nothing was deferred and forgotten), and still quietly kills a future path. It is mostly
> judgement — reserved concepts live in prose, not in a machine-readable index — so it belongs to the
> **deep and comprehensive tiers, not a cheap per-push gate**. Severity WARN.

### The deep audit — a periodic two-blind-passes reconciliation

The six lenses check docs against code **with both in view**. That is efficient, and it is biased: you
read the claim, then go looking for the code that backs it, and confirmation is the easy find. The
**deep audit** removes that bias by forming an **independent expectation from each side** and diffing
the expectations. It is driven by the [`/deep-audit` skill](../.claude/skills/deep-audit/SKILL.md).

```
Pass A — doc → expected code   (read ONLY the .md in scope; NO code)
   → "Given these docs, what projects/types/members/behaviors MUST the code have?"   → expectation A
Pass B — code → expected docs  (read ONLY the code in scope, plus the structure docs —
                                COORDINATOR / MODULE_SPEC / MAP — for vocabulary, NOT for claims)
   → "Given this code, what SHOULD the docs say?"                                     → expectation B
Reconcile — diff A↔reality, B↔reality, and A↔B:
   • Doc over-claim        — A expects code that is not there (aspiration written as fact)
   • Code under-documented — B expects docs that do not exist (built, undocumented)
   • Agreed-but-wrong      — A and B agree with each other AND with the code, yet all three drift
                             from the intended design: "we built X, documented X, and X was never
                             what we meant"
```

**The blindness is the mechanism.** Pass A must not see the code and Pass B must not see the doc
*claims*, or the expectations stop being independent and the method collapses back into the ordinary
lenses. The third finding class is the unique payoff — it is invisible to all six lenses because
nothing is internally inconsistent.

Run it **less often** than `/audit`: before a freeze, when resuming a pillar or module after a long
gap, or periodically. It is **scopeable** — the whole project, one pillar, or one module. Route its
findings exactly like an ordinary audit (§6) and **log it** (§7).

**A caveat specific to this repository:** while no C# has been compiled, Pass B is reading a
*specification expressed in C#*, not a running system. Say so in the reconciliation. It still finds
real drift — an interface with no doc, a doc describing a member that was never written — but it
cannot find behavioral drift, because there is no behavior yet.

### The comprehensive audit — everything, in one sitting

The heaviest tier: **the full mechanical check + all six judgement lenses + the deep-audit two-blind
passes, over the whole project at once.** It is expensive on purpose and is **not a per-PR gate**. It
is triggered by the owner, or suggested (never forced) by Claude, at the moments where a broad
cross-cutting re-connect earns its cost:

- **After a long or concept-heavy session** — a burst that introduced many concepts across many docs.
  The comprehensive pass verifies they all *connected* (Lens F) and that nothing drifted (A–E) while
  the threads are still warm.
- **Before a deep freeze** — putting the whole project on ice. It certifies that the *interconnected*
  state, not merely each doc individually, is resumable.
- **After a large change or milestone** — a big merge, a pillar landing, the first successful
  compile — where a per-push mechanical gate cannot see cross-cutting judgement drift.

Drive it exactly like §6: mechanical → lenses A–F → the two deep passes → classify → **log it**. Its
log entry is the best single resume artifact for a cold restart, because it is the one pass that
looked at everything at once. The
[`/comprehensive-audit` skill](../.claude/skills/comprehensive-audit/SKILL.md) orchestrates it.

---

## 5. Severity & the gate

| Severity | Meaning | Effect |
|---|---|---|
| 🔴 **ERROR** | Unambiguous breakage. A broken link, a `related:` edge that does not resolve, a path referenced that does not exist, an ADR sequence gap, invalid frontmatter, a stale [MAP.md](MAP.md), a boundary violation, a changed doc that never bumped `updated`. No judgement required to agree it is wrong. | **fails the gate** — `coord audit` exits non-zero |
| 🟡 **WARN** | Probable drift needing judgement. A module directory with no README or no "where to resume"; changed code under a module with no doc touched; a doc overdue for an accuracy re-read. | advisory — logged, does not fail |
| 🔵 **INFO** | Re-confirm-by-hand items. A doc nothing links to; a `Proposed` ADR with no recall hook; an aged `captured` INBOX entry; a missing `audited` baseline. | advisory |

**The gate is deliberately hard on ERROR and soft on WARN, so that it never cries wolf.** A gate that
fires on judgement calls trains you to ignore it, and an ignored gate is worse than no gate — it is a
check that cannot fail ([OPERATING_MODEL §7](OPERATING_MODEL.md), failure shape 1) wearing the
costume of one that can. A WARN backlog is triaged during audits and lives in the log; it never
blocks a merge.

**A phase is not done, and a module is not shelved, with ERROR-level drift outstanding.**

**Accepted-forever findings are recorded in the log.** Some advisories will recur every single run —
an illustrative path in a template, a deliberately planned-but-unbuilt reference, a frozen historical
record. Record them once in the log's *Accepted* section so future audits do not re-triage them. An
accepted finding that stops being accurate is itself a finding.

---

## 6. The audit workflow

```
1. RUN the mechanical half ......... coord audit            (or /audit)
2. WALK the six lenses (§4) ........ scoped to what changed / what you are shelving
3. CLASSIFY each finding ........... real drift | accepted (illustrative / historical / planned)
4. LOG it .......................... append an entry to docs/audit-log.md (§7)
5. TRIAGE the real drift ........... small + safe          → fix it now, in this pass
                                     larger sweep          → file into docs/NEXT.md
                                     known limitation      → a TD-NN row in docs/TECH_DEBT.md
                                     bespoke → reusable    → propagate (Lens B propagation step)
                                     non-obvious decision  → write an ADR in docs/decisions/
                                     stray idea            → capture into docs/INBOX.md
6. STAMP accuracy .................. for each doc you re-read and confirmed true, bump `audited:`
                                     (and `updated:` if you changed it) — DOC_SPEC §3
7. RE-RUN until the ERROR count is 0 ....... the gate must be green to bank the audit
```

Steps 4 and 5 reuse the **snapshot and steering protocol** in [CLAUDE.md](../CLAUDE.md): an audit is
a structured drift-finding session whose findings land in the same living docs as everything else.
Fix the trivial-and-safe drift in the same pass — progress beats paperwork — and route the rest so
nothing is lost.

**Step 4 is not optional and not last-in-practice.** Writing the log is what converts an audit from
an activity into a record; see §7.

**At branch closeout the same gate appears as a form.**
[The PR checklist](../.github/pull_request_template.md) is this workflow's last mile made visible at
merge time — the mechanical run, `coord audit --since origin/main`, the boundary question, the
bespoke-vs-reusable question, and the evidence statement that separates *Core-verified* from
*Windows-validated*. It carries the same rule as everything else here: **an honest "N/A — why" beats
a checked box that is not true**, because a ticked box is a claim and this project holds claims to
their evidence ([OPERATING_MODEL §7](OPERATING_MODEL.md)).

---

## 7. The audit log

[docs/audit-log.md](audit-log.md) is the durable record, **newest entry at top** (matching INBOX and
the README's Pitfalls). It is what makes repository health a **tracked quantity over time**: when an
audit last ran, what it found, what got fixed, what is still owed. It carries no `audited:` key,
because it is a record doc — a set of summaries-as-of-their-date, not a living claim about current
code ([DOC_SPEC §3](DOC_SPEC.md)).

Each entry uses this skeleton:

```markdown
## YYYY-MM-DD — <scope> (<auditor>)

**Mechanical:** N error / N warn / N info  (coord audit)   — or "not run", and why
**Lenses walked:** A / B / C / D / E / F   (or which subset, and why the rest were skipped)

### Fixed this pass
- <finding> → <what changed>

### Backlog (real drift, deferred)
- 🟡 <finding> → filed in NEXT.md / a new ADR / a TD-NN row

### Accepted (not drift — will recur, do not re-triage)
- <finding> → <why it is fine: historical / illustrative / planned>

### Health
- C#: <compiled / never compiled> · Core tests: <N/N passing / not runnable, no toolchain>
- Manual validation: <what, on what machine, when / never performed>
- Ground-truth reconciliations actually performed this pass:
  - module set: `ls src/modules/` = {…} ✓ reconciled against the README table + the roadmap
  - ADR frontier: log at NNNN · governance Status sections reference NNNN ✓
  - <any other filesystem ↔ doc diff actually performed>
```

> **Why Health carries the reconciliation lines.** "If it is not logged, the audit did not happen"
> tracks *that* an audit ran and *which* lenses were checkbox-walked — but a lens can be walked
> without its diff ever being performed. Recording the reconciliations **actually done** makes a
> silently-skipped dimension visible as a *missing line* instead of an invisible omission. It mirrors
> Lens D's "name the artifact first" discipline, applied to the audit's own evidence.

---

## 8. What the mechanical checker covers (and deliberately doesn't)

`tools/doc-audit/audit.py` ([README](../tools/doc-audit/README.md)) is stdlib-only Python 3.11 and
runs with **no .NET installed** — which is why it is the only half of this protocol that is
executable in a non-Windows environment. `coord audit` wraps it
([tools/coord/README.md](../tools/coord/README.md)).

The complete check list, with severities and exemptions, is
[tools/doc-audit/README.md](../tools/doc-audit/README.md) — one table, kept beside the code it
describes ([DOC_SPEC §2.1](DOC_SPEC.md)). That README also documents the invocation modes
(`--quiet`, `--format json`, `--no-fail`, `--since <ref>`, `--accuracy`) and the exit-code contract.
What follows here is the **protocol commentary**: what a green run is and is not allowed to mean.

**The boundary check is the modularity teeth, and it is real.** Because no C# has been compiled, it
operates on **text**: `using` directives, namespace declarations, `[DllImport]` attributes in `.cs`
files, and `ProjectReference` elements in `.csproj` files. That genuinely catches the violations that
matter most — Win32 in a Core project, a module referencing another module — and it is the one
modularity guarantee available without a compiler. It is also, unavoidably, textual: it cannot see a
violation smuggled through reflection, a type alias, or an indirect dependency. Treat a green
boundary check as "the obvious leaks are absent", never as "the boundary is proven".

**What it deliberately does not do.** It does not judge whether a doc is *true*, whether a solution
is bespoke or duplicated in prose across two docs, whether [NEXT.md](NEXT.md) is *useful*, whether a
"validated" claim ever happened, or whether a design forecloses a planned one. Those are Lenses A, B,
C, E, and F — they need a brain. The checker exists so that the mechanical drift is free to find,
leaving the audit's attention for the parts where only judgement helps.

**Two limits worth stating plainly**, because they are the places a green run is easiest to
over-read:

1. **A green audit says nothing about C#.** No compiler has run. See
   [OPERATING_MODEL §7](OPERATING_MODEL.md).
2. **`code-ref` at ERROR severity is strict on purpose while the repo is young** — every path token
   in every doc must resolve. If it starts firing on legitimately frozen or illustrative references
   (a dated ADR naming a path that has since moved, a template placeholder), that is the signal to
   narrow its scope by an explicit decision and an ADR — not to start ignoring it. An ignored ERROR
   is how the gate stops meaning anything.

**Extending the checker is a drop-in:** add a `check_*` function and register it. Keep ERROR for
unambiguous breakage only; anything needing judgement is WARN or INFO. And per the evidence standard,
**when you add a check, prove it fails without the fix** — break the thing deliberately, watch it go
red, then repair it. A check that has never been observed to fail is indistinguishable from a
comment.

---

## 9. Quick reference

```sh
coord audit                      # full report; exits non-zero on ERROR (the gate)
coord audit --quiet              # summary + ERRORs only
coord audit --format json        # machine-readable, for tooling or the log
coord audit --since origin/main  # branch closeout: changed docs must bump `updated`
coord audit --accuracy           # only the accuracy-staleness backlog (report-only)
coord map --check                # is docs/MAP.md current?
/audit                           # the full protocol: checker + lenses + log + triage
/deep-audit                      # the two-blind-passes reconciliation
/comprehensive-audit             # mechanical + all six lenses + the deep passes, one sitting
```

- **Hard drift (ERROR) must be 0** before a phase is done or a module is shelved.
- **Soft drift (WARN/INFO)** is triaged in the audit log, never in the gate.
- **Findings flow** into the same living docs as everything else — [NEXT.md](NEXT.md),
  [TECH_DEBT.md](TECH_DEBT.md), `docs/decisions/`, [INBOX.md](INBOX.md).
- **The log is the memory.** If it is not in [audit-log.md](audit-log.md), the audit did not happen.
- **Say what is verified and what is not.** A green `coord audit` is a statement about text. A green
  Core test run — once a toolchain exists — is a statement about Core logic. Neither is a statement
  about the desktop; only [runbooks/manual-validation.md](runbooks/manual-validation.md), executed by
  a human, is.

---

## See also

- [DOC_SPEC.md](DOC_SPEC.md) — the documentation contract this protocol enforces: placement, tiers,
  frontmatter, the `updated` / `audited` distinction, closeout, and freeze.
- [OPERATING_MODEL.md](OPERATING_MODEL.md) — the *why* beneath the rules, and the evidence standard
  Lens A and §8 both rest on.
- [MODULE_SPEC.md](MODULE_SPEC.md) — the module contract, including the shelving requirements Lens C
  checks.
- [COORDINATOR.md](COORDINATOR.md) — the platform architecture: the Core/Shell split and the boundary
  Lens B defends.
- [audit-log.md](audit-log.md) — the running record; entry format is §7 above.
- [CLAUDE.md](../CLAUDE.md) — standing orientation and the snapshot protocol that steps 4–5 of the
  workflow reuse.
