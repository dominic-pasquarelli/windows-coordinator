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

## 2026-08-08 — Corrections to the accuracy audit (review of the audit itself)

**Scope:** the previous entry's own output. Four findings, three of which are the **same class the
audit was hunting** — which makes them the most useful entries in this log.

**Counts:** `coord audit` 0/0/0 · closeout 0/0/0 · `coord map --check` clean · 11 scaffold tests
green.

### Fixed

1. 🔴 **`tools/doc-audit/audit.py` and `tools/doc-audit/README.md` both still said "not one line of
   its C# has been compiled."** The sentence conflated two claims — *no SDK in the authoring
   environment* (still true) and *never compiled anywhere* (false since `7aef6ff`) — and the true
   half kept the false half looking correct. Now separated: the checker has no compiler; CI does;
   neither changes what a textual check means.
2. 🟡 **The README said "Fifteen checks" above a sixteen-row table** — stale by exactly the
   `projectref` row the previous entry added. Verified mechanically this time: **16 table rows, 16
   emitted ids, no difference in either direction.**
3. 🟡 **`README.md` and `docs/ONBOARDING.md` still called `src/modules/` "empty by design today."**
   The previous pass fixed the `tests/` line **in the same two tree diagrams** and did not read the
   line above it.
4. 🔴 **The accuracy fix was a postponement, not a fix** — see below.

### Finding 3 is the one worth internalising

The previous entry named the pattern — *status text in structural positions* — and then fixed one
line of a two-line diagram twice. **Knowing the pattern did not produce a systematic sweep; it
produced a targeted grep for the specific string already in hand.** The correct move, once a
structural position is implicated, is to re-read *that whole structure* — every row of the table,
every line of the diagram — rather than the line matching the current query. Lens A already says
"verify every row, never a sample" about tables; the same applies to any structural block, and this
is the second consecutive round where a tree diagram carried the drift.

### The accuracy anchor — a real fix this time

The previous entry skipped the commit arm while `audited` was **today**. Review: that only moves the
defect a day. The arm counted commits since **midnight on the audited date**, so on 2026-08-09 a doc
audited at the end of a busy 2026-08-08 is charged for every commit that day — **including the ones
that landed before the audit** — and reports stale with nothing changed since.

Both failures are one root cause: **the date is day-granular, the audit is an instant, and only git
knows which.** So the count is now anchored to the **commit that introduced the doc's current
`audited:` line** (`git log -1 -S`), and counts `anchor..HEAD`. No schema change, exact regardless of
how many commits share a day, and it answers the question actually being asked — *how much has landed
since someone last confirmed this doc?*

**A/B on the reviewer's scenario** (`tests/README.md`, audited 2026-08-08, evaluated as 2026-08-09):

| Basis | Count | Stale? |
|---|---|---|
| Old — since date midnight | **18** | **yes** ← false positive |
| New — since the audit commit | **15** | **no** ✓ |

Guard intact: a doc anchored at the root commit sees 17 → **stale**. An uncommitted or untracked
stamp returns `None` and the arm is dropped — "unknown" rather than a false warning, the same
asymmetry `_repo_commits_since` already documented.

> ### ⚠ Correction, same day: that A/B proved the wrong case
>
> **CI caught this before merge** — 25 warnings there against 0 locally. The A/B above ran against a
> `tests/README.md` whose `audited` value had been *changed* (back-dated, then restored). The case
> that actually applies here is a re-stamp of the **same** value, and `git log -S` detects a change
> in the *number of occurrences* of a string: rewriting `audited: 2026-08-08` over an identical line
> produces no diff, so the anchor resolves to the **bootstrap** commit, not to the audit. Every doc
> re-stamped today still counted 16+ commits.
>
> **The information does not exist in git.** A same-day re-audit that changes nothing is
> unrepresentable, and no query can recover it. So the anchor is right for every audit on a later
> day and blind to this one, and the same-day skip is restored alongside it — the two together cover
> day zero and day one, which is as far as a date-valued field can reach. The real fix is to give
> the stamp a commit; that is a schema change, so it is **TD-15** with a trip-wire, not a smuggled
> edit.
>
> **This is the project's own named failure — "a claim stronger than its evidence" — committed in
> the act of fixing one.** The A/B was real, ran green, and tested a case the repository was not in.
> The lesson is narrower than "test more": *when a fix is validated by constructing a scenario,
> check that the constructed scenario matches the one that motivated the fix.* Back-dating the file
> to make the test work was precisely the step that made it test something else.
>
> Consequence to carry: **the 20 docs stamped in this pass are attested in this log and not in their
> frontmatter**, because the field cannot hold a same-day re-audit.

### Backlog

- **`audit.py` has no test harness**, so the three guard proofs in this log and the last are recorded
  numbers rather than a regression test. CI discovers only `tools/coord/tests`; adding a second
  discover path plus `tools/doc-audit/tests/` is the fix, and it is the right home for the anchor A/B
  above. Filed rather than done: it is a CI-config change, out of scope for a correction pass.
- The five normative docs from the previous entry remain unstamped and unread end to end.

### Note on scope

This audit work is **scope creep on a PR whose subject is the Zones design** — authorised (it was
requested before merge) but not thematically part of it. Recorded because the reviewer was right to
flag it: the Zones design was approved at `04710b8`, and everything after that commit is repository
maintenance that happens to share a branch.

---

## 2026-08-08 — Accuracy audit before merging PR #2 (`/audit`, whole repository)

**Scope:** the whole repository, driven by the 27-doc accuracy backlog. Requested explicitly as
"confirm or correct each, stamp only what is verified" — so the interesting output is as much the
**coverage boundary** as the fixes.

**Counts:** `coord audit` **0 error · 27 warn · 0 info → 0 · 0 · 0**. `coord audit --since
origin/main` 0/0/0 · `coord map --check` clean · 11 scaffold tests green. **No C# behaviour changed**
(one Python fix to the checker). Nothing has run on Windows.

### Ground truth reconciled (Lens A, performed — not intended)

`ls src/modules src/pillars src/platform src/shell tests` · `find -name '*.csproj'` (**5**: 3
production + 2 test) · `find -name '*.sln'` (**0**) · `ls docs/decisions` (**24 ADRs**) · `coord.py`
subcommands vs `tools/coord/README.md` (**match**) · `audit.py` emitted check names vs
`tools/doc-audit/README.md` (**mismatch — see Fixed #6**).

### Fixed

1. 🔴 **`docs/COORDINATOR.md` §1 still said "no C# in this repository has ever been compiled" and
   "nothing here may be described as building, passing, or working."** False since CI `7aef6ff`. The
   canonical architecture doc was the single worst place in the repository for this to survive.
2. 🔴 **`CLAUDE.md`'s Status section contradicted `CLAUDE.md`'s own opening** — "No C# has been
   compiled — ever", "No module exists … a directory-level plan and no code", "the pillars are
   specified, not built". The opening block was corrected in the PR #1 evidence sweep and the Status
   section, ~370 lines down the same file, was not.
3. 🟡 **The `tests/` directory was described as empty in three places** — `README.md`,
   `docs/ONBOARDING.md` (both directory-tree diagrams) and `CLAUDE.md`'s doc-map table ("none yet").
   Two test projects have existed since PR #1.
4. 🟡 **`README.md`'s module table listed Zones as "Planned — not implemented, not scaffolded"**,
   with no hint that a full architecture doc and thirteen ADRs exist. Implementation status was right;
   a reader would not have known there was anything to read.
5. 🟡 **`src/modules/README.md` said Zones' decisions are "ADR 0012–0014."** Now 0012–0024.
6. 🟡 **`tools/doc-audit/README.md` documented 15 of the checker's 16 checks** — `projectref`,
   added earlier the same day, was missing from the table it belongs in.
7. 🟡 **`docs/recipes/add-a-module.md` invented `zones.layout.*` capability ids** that do not match
   the real ones in Zones' ARCHITECTURE §8.1, under a note saying "`zones` does not exist" — no longer
   true, and ids are a permanent contract. Now says so explicitly.
8. 🟡 **TD-12's trip-wire had FIRED unnoticed** (Lens E). The row set its own threshold at "roughly
   twenty ADRs" while saying "ten ADRs, all fresh"; there are 24, thirteen added by PR #2 with several
   cross-correcting. Marked fired, and given a recall hook in NEXT.md's trip-wire table — a fired
   trigger with no route back is the failure Lens E exists to catch.
9. 🔴 **The `accuracy` check could not pass** — see below.

### The check that could not pass

The accuracy backlog would not clear no matter how honestly the docs were audited. Its commit arm
counts **repo-wide commits since the `audited` date**, so on a project whose entire history is one
calendar day it counts commits that landed *before* the pass as well as after. Re-auditing changed
nothing; 27 stayed 27.

**That is a check that cannot pass — the mirror of
[OPERATING_MODEL §7](OPERATING_MODEL.md#7-the-evidence-standard--what-it-works-is-allowed-to-mean)'s
"a check that cannot fail", and just as useless.** A guard that is unsatisfiable teaches people to
ignore it, which then hides the real findings it was meant to surface.

Fixed by skipping the commit arm while `audited` is **today** — the same accommodation `updated-flag`
already makes for an unchanged value that equals today, and for the identical reason: *a date is
day-granular, and a check may not demand a precision the field cannot carry.* The day arm is
untouched.

**Proved in all three directions**, because a fix that merely silences a warning is indistinguishable
from one that removes a guard:

| Case | Expected | Result |
|---|---|---|
| `audited` = today, 27 same-day commits | no warning | **0 stale** ✓ |
| `audited` 8 days ago | day arm fires | **fires** ✓ |
| `audited` 1 day ago, 17 commits | commit arm fires | **fires — "17 commits since"** ✓ |

### Coverage — what was and was not verified

**20 docs stamped `audited`**, each verified in substance against ground truth this pass.

**5 docs deliberately NOT stamped:** `docs/AUDIT.md`, `docs/DOC_SPEC.md`, `docs/MODULE_SPEC.md`,
`docs/OPERATING_MODEL.md`, `docs/vision.md`. They were checked for the two failure modes that could be
established mechanically — no superseded PR #2 contract is referenced, and no false evidence claim
appears — but they were **not read end to end**, and they are normative documents where the risk is a
rule that quietly stopped matching practice. **They now show as clean under the repaired check while
being unverified**, which is the honest cost of the day-granularity fix and is recorded here precisely
because the flag can no longer carry it.

### Backlog

- **Re-read the five unstamped docs end to end.** Best done as a `/deep-audit`, which is built for
  exactly the normative-drift question they pose.
- **TD-12** — convert plain-text `ADR NNNN` references to links, or add an `adr-ref` check resolving
  them by number. Trip-wire fired; hook in NEXT.md.
- **The accuracy baseline cannot express same-day precision.** Storing a commit sha alongside the date
  would fix it properly. Not done here: it is a frontmatter schema change and a judgement call, and
  the protocol says propose rather than auto-apply.

### Accepted (not drift)

- `docs/runbooks/dev-setup.md`'s "no `.sln` exists yet (TD-2)" — still true.
- `COORDINATOR §8` P0's gate not requiring a compile — a gate is a minimum; CI exceeding it is not
  drift. Reworded so it cannot be misread as "the C# does not compile".
- The CLAUDE.md ↔ COORDINATOR §7 principle duplication — the one accepted duplication, per its note.

### Health

- **Lens A:** 8 real findings, all fixed. The pattern across all of them: **status text in structural
  positions** — tree diagrams, map tables, a Status section far from the summary it contradicts. The
  PR #1 sweep fixed ~65 body-text claims and left every one of these.
- **Lens B:** clean. `boundary` and `projectref` green; no Windows type in any Core project; no module
  reaching around a pillar; no speculative platform without a consumer.
- **Lens C:** Zones satisfies four of five shelving items; item 4 (tests green) is **unverified — no
  toolchain**, recorded rather than ticked.
- **Lens D:** practice matched the operating model. Eight review rounds produced ADRs rather than
  quiet fixes, and no hard gate was added to a steering path.
- **Lens E:** one fired trigger found (TD-12). INBOX empty, no `Proposed` ADRs outstanding.
- **Lens F:** settings remain additive-extendable; `layoutRevision` was added as a field rather than a
  reshape; module identity still threads settings, bindings and update manifests.

---

## 2026-08-08 — PR #2 round 8: two versions doing one job, and a metric that could not measure itself

**Scope:** the pointer-gesture payload's version contract and the `DesktopFacts` repair metric,
re-read against a review that accepted round 7's two fixes and found a contract mismatch the new
arbitration model had opened underneath them.

**Mechanical result:** `coord audit` 0/0/0 · `coord audit --since origin/main` 0/0/0 ·
`coord map --check` clean · 11 scaffold tests green. **No C# changed.** Nothing has run on Windows.

### The blocker

[ADR 0013](decisions/0013-the-pointer-gesture-trigger-kind.md) stamped a dispatch with the **region-set
version** — correct when written, because the set a module published *was* the set the hook tested.
[ADR 0021](decisions/0021-requested-versus-granted-regions.md) split that into **requested** and
**granted**, and nobody went back to the payload. The two versions stopped being interchangeable: a
module's requested-set version sits unchanged while `GrantVersion` moves through lease epochs, because
arbitration changes without the module publishing anything.

Which admits: recognize a tick at grant v1 · preempt to v2 · restore to v3 · deliver the v1 tick · its
requested-set version still matches · it executes against an epoch replaced twice. **The guard was
checking the one value that had not changed.**

[ADR 0024](decisions/0024-grantversion-is-the-single-authoritative-version.md) makes `GrantVersion` the
only version, stamped into the hook lookup table, every dispatch, the publication result and every
`GrantChanged`, with **exact-equality** execution. The same review found the second instance of the
same root cause: the publication result had no version and no guard, so an in-flight result for v1
could land after a `GrantChanged` v2 and overwrite it. Both now go through one `ApplyGrant`.

### The pattern — a refactor that left a contract behind

New shape, and the most self-inflicted of the eight rounds. Rounds 4–7 were defects *within* a
decision. This one was created **by an earlier fix**: ADR 0021 was correct, and it silently invalidated
a contract written three ADRs earlier that nothing linked it to. The payload and the arbitration model
were edited in different sittings, and neither edit had a reason to look at the other.

**The generalisable check: when a model splits one concept into two, grep for every consumer of the
old one.** "Region-set version" survived as a phrase because it still parsed — it named a real value,
just no longer the right one. A rename would have caught this; a split did not, because both halves
kept plausible names.

This is why the count of correction notes on ADR 0013 is now four. That is not noise: an ADR that
keeps getting corrected is an ADR whose consumers keep changing, and the log is doing its job.

### The smaller finding, which is about honest metrics

Round 7 attributed a coalesced publication as event-driven "if any request was event-driven". That
cannot support the guarantee it was written for: if the event path reports a change to X while a
*different* change to Y was missed, a batch containing the X event suppresses the count — the metric
under-reports **exactly when the event path is partly working**, which is the interesting failure.

Fixed by carrying identity: an event request names the foreground it was notified about, and a
correction is counted when the sampled foreground was named by **no** request in the batch. And the
residual is now stated rather than implied — under rapid switching this can over-count a notification
still in flight, which is the safe direction for a health signal and the reason it is read as a rate
rather than a tally.

**Worth keeping: a metric needs its precision stated, not just its intent.** "Counts missed
notifications" sounded exact and was not; "counts publications whose value no request named, read as a
rate" is weaker and true.

### Guards

Both new failure modes get their sequence written out in
[CONDUIT §5.4](CONDUIT.md#54-proving-the-guard-not-asserting-it), each specified to go red against the
design it replaced: **v1 → preempt v2 → restore v3 → deliver v1** must drop (a requested-set guard lets
it through), and **hold a v1 publication result, apply v2, deliver v1** must not overwrite (a separate
unguarded result path lets it through).

### Still owed

- P1 and P2 before any Zones code. `Z-1`…`Z-6` remain written and never executed.
- Eight rounds. The specification is materially better; the implementation has not started.

---

## 2026-08-08 — PR #2 round 7: two concurrency contracts that atomicity did not provide

**Scope:** the `DesktopFacts` publication path and the grant-notification delivery path, re-read
against a review that accepted round 6's two fixes and found each had specified a *primitive* where a
*protocol* was needed.

**Mechanical result:** `coord audit` 0/0/0 · `coord audit --since origin/main` 0/0/0 ·
`coord map --check` clean · 11 scaffold tests green. **No C# changed.** Nothing has run on Windows.

### The two

| # | Gap | Landed as |
|---|---|---|
| 1 | Publication was an **atomic reference swap** — which orders the *write* but not the *writers*. A heartbeat could sample foreground A, lose the CPU while the event path published B at seq 41, then swap A at seq 42: content backwards, sequence forwards, inverting the one rule consumers are given | [ADR 0022](decisions/0022-one-publication-sequencer-for-desktop-facts.md) — one Atlas-owned sequencer does sample → allocate → swap as one ordered operation. Invariant: **a higher `Sequence` was sampled later** |
| 2 | Grant changes were **delta events on the ordinary dispatch queue** — which §5.3 explicitly allows to drop the oldest coalescible item. A dropped `RegionsRestored` leaves a module showing a zone unavailable forever, and a revoke arriving after a restore inverts the end state | [ADR 0023](decisions/0023-the-control-plane-carries-state-not-deltas.md) — a second dispatch class carrying **absolute state**: `GrantChanged(Granted, GrantVersion)`, serial per owner, latest-state coalescing, final state never dropped, plus a `QueryGrant` read for recovery |

### The pattern — a correct primitive assumed to be a correct protocol

Both defects have the same shape, and it is a new one for this project's ledger. In each case the
mechanism named was **genuinely correct at what it does**, and was doing a *different job* than the
one the design needed:

- an atomic swap **is** the right way to hand an immutable record to a concurrent reader. It says
  nothing about which of two writers samples first, and the design needed an ordering between *writes*
  that no property of the *write* provides;
- the bounded drop-oldest queue **is** the right policy for input, and its correctness argument is
  explicitly *"a dropped wheel tick is cosmetic"*. That argument was never checked against the second
  kind of message the queue had started carrying.

**The generalisable question: for each mechanism, what exactly does it guarantee, and is that the
property being relied on?** "Atomic" and "queued on a worker" both read as sufficient at a glance;
neither was, and neither was wrong — they were answering a question nobody had asked.

Round 2's finding sits in the same family in hindsight: content age was a *correct measure of
elapsed time* being used as a proxy for correctness.

### The architectural residue, which is the useful part

Blocker 2 forced a distinction Conduit had been eliding: it has an **event plane** (something
happened; droppable; a loss is cosmetic) and a **control plane** (what the world is; the final state
may not be dropped; a loss desynchronizes permanently). That is now a table in
[CONDUIT §5.3](CONDUIT.md#53-the-hand-off), and it has forward value — any future *"here is the current
state of X"* message has a place to go, and the question "is this an event or a state?" now has an
answer with consequences attached.

The delta-vs-absolute choice is what makes the guarantee affordable, and it is worth remembering
independently: **a delta is correct only if every message arrives in order; an absolute snapshot is
correct if the last one arrives.** The second is a promise a bounded queue can actually keep.

### Guards, with their proofs

Both are guards that can be implemented as decoration, so §5.4 specifies how each must be seen
failing:

- **Publication ordering by injected schedule, not by racing threads.** Hold the sequencer after a
  heartbeat request is enqueued, deliver a foreground event, release, then assert: final record is the
  new foreground · sequence never carries an older observation · **the repair counter did not
  increment** (an event reported the change, so nothing was repaired). Red against independent
  sample-then-swap. Racing real threads and hoping is not a test.
- **Control-plane delivery under saturation**, because the guarantee is *specifically* about overload
  and is vacuous when nothing is under pressure. Fill the event queue until it drops, drive revoke →
  restore, assert the module observes the restored grant and never afterwards applies the revoked one
  — then assert the same when the two coalesce. A version-ignoring consumer must fail.

### Still owed

- P1 and P2 before any Zones code. `Z-1`…`Z-6` remain written and never executed.
- Seven review rounds: the specification is materially better and the implementation has not started.

---

## 2026-08-08 — PR #2 round 6: two lifecycle gaps, both "what happens afterwards?"

**Scope:** the `DesktopFacts` publication contract and the pointer-gesture arbitration lifecycle,
re-read against a review that accepted round 5's four fixes and found each had answered the *steady
state* while leaving the *recovery* undefined.

**Mechanical result:** `coord audit` 0/0/0 · `coord audit --since origin/main` 0/0/0 ·
`coord map --check` clean · 11 scaffold tests green. **No C# changed.** Nothing has run on Windows.

### The two

| # | Gap | Landed as |
|---|---|---|
| 1 | The heartbeat proved the publisher was **alive** but republished the record unchanged — so a missed foreground notification stayed wrong forever with the sequence advancing normally. The named correctness check, `TopologyGeneration`, only covers *geometry*: foreground can change while topology is identical | The heartbeat **re-samples the foreground** each interval. Guarantee: a missed foreground publication is repaired within one interval, and each repair is **counted** so a broken event path is visible |
| 2 | A revoked region was never restored. The low-priority module's request was discarded by the refusal, it was told not to retry, and nothing brought the region back when the winner withdrew — so the final armed map depended on history, contradicting the property round 5 had just bought | [ADR 0021](decisions/0021-requested-versus-granted-regions.md) — **requested** and **granted** are separate values, grants are recomputed from `(all requests, priorities)` on every change, and both `RegionsRevoked` and `RegionsRestored` are notified and bump the version |

### The pattern — three rounds, three distinct shapes

Worth recording together, because they are not the same failure and looking for one will not find
the others:

| Round | Shape | Where it hides |
|---|---|---|
| 4 | Prose the **type signature** could not express | In the gap between a description and a declaration on the same page |
| 5 | A rule contradicted by the **mechanism named elsewhere** | In the join between two documents, or two sections written months apart |
| 6 | A **steady state defined, a recovery left undefined** | After the last sentence. Nothing contradicts anything — the design simply stops early |

Round 6's shape is the hardest of the three to catch by reading, because there is no contradiction to
notice. Both gaps read as complete and were: complete descriptions of the *first* transition. The
question that finds them is **"and then what?"** — asked of every state a design introduces. What
happens after the heartbeat proves liveness on wrong content? After a region is taken and the taker
leaves?

**A lens-D addition earned by this round:** for every new state or transition, ask what returns the
system to the previous state, and whether anything triggers it. A one-way transition is a design that
works once.

### The self-check both fixes now carry

Each gap also produced a guard whose *proof* had to be specified, because both are the kind that can
be implemented as decoration:

- **The heartbeat's repair path** — suppress a foreground-change notification, advance exactly one
  heartbeat, assert the published foreground matches reality and the missed-notification counter
  moved. Run against a build whose heartbeat republishes unchanged and it must go red.
- **Arbitration by permutation, including the full lease cycle** — low requests · high preempts ·
  high withdraws · low regains automatically, in every order, same final map. A permutation test
  *without* the withdraw step passes under the design ADR 0021 replaced, which is precisely why the
  round-5 version of this test would not have caught the gap it was written to prevent.

That second one is its own small lesson: **a permutation test is only as good as the operations it
permutes.** Round 5 specified permutation and still missed the defect, because the operation set did
not include a winner leaving.

### Still owed

- P1 and P2 before any Zones code. `Z-1`…`Z-6` remain written and never executed.
- Six review rounds have improved the specification and moved the implementation not at all.

---

## 2026-08-08 — PR #2 round 5: four contradictions between a rule and its own mechanism

**Scope:** the two pillar contracts and the Zones designer, re-read against a review that found four
places where a decision and the mechanism implementing it disagreed.

**Mechanical result:** `coord audit` 0/0/0 · `coord audit --since origin/main` 0/0/0 ·
`coord map --check` clean · 11 scaffold tests green. **No C# changed.** Nothing has run on Windows.

### The four

| # | Contradiction | Landed as |
|---|---|---|
| 1 | §5.5 classified a hotkey chord as `Hook` origin and said its cursor came from the event structure — but §3.1 makes plain chords **kernel registrations**, and neither `WM_HOTKEY` nor `KBDLLHOOKSTRUCT` carries a cursor | Chords are **`OsCallback`** origin, sampled live while handling `WM_HOTKEY`. `Hook` is now exactly the two **mouse**-driven kinds, so "cursor from the event structure" holds by construction |
| 2 | `ContextStale` fired on the *age* of the `DesktopFacts` record — which is event-driven, so age measures how quiet the desktop has been, not whether the record is right | **Heartbeat + monotonic sequence.** Staleness is a liveness check on the publisher; content age is never on its own a refusal reason; correctness comes from the generation comparison |
| 3 | Arbitration was "user priority, then stable module id" **and** "a lower-priority incumbent keeps what it holds" | A grant is a **revocable lease**. Higher priority preempts and the loser is told (`RegionsRevoked`); lower priority is refused. Zones §7.4 handles the inbound case |
| 4 | ADR 0018 made `Grid` a constructor and explicitly rejected grid-as-edit; ADR 0019 and ARCHITECTURE gave it a template, occupancy, and a `LayoutEdit` return | **`Grid` is a constructor**, restored. `Split`/`Merge` are the edits. Applying a new grid to a monitor is a *layout switch*, a different operation with a different consequence |

### The pattern — and it is not last round's pattern

Round 4's three defects were **prose the type signature could not express**. These four are the
mirror: **a rule contradicted by the mechanism named elsewhere in the same document.** Every one is
findable by holding two sections side by side —

- §5.5's origin table against §3.1's "registrations for plain chords, hooks only for the two pointer
  kinds";
- the age threshold against §3.6's "republishes *when it changes*";
- "priority decides" against "the incumbent keeps it";
- ADR 0019's signature against ADR 0018's rejected alternative.

None needed new information. Each needed the two statements read together, which is exactly what
authoring them in separate sittings prevents. **Worth adding to the audit's Lens B habit: when a
decision is made in one doc and implemented in another, read the pair — the drift lives in the join,
not in either half.**

Two of the four also share a sharper root: **a proxy standing in for the thing it approximates.**
Content age was a proxy for correctness; arrival order was a proxy for priority. Both read as
principled until you ask what happens when the proxy and the real property diverge — an idle desktop,
a reordered load. The heartbeat and the lease are what it costs to stop approximating.

### Guards added, with their proofs specified

[CONDUIT §5.4](CONDUIT.md#54-proving-the-guard-not-asserting-it) gains two entries, both written so
the guard has to be *seen* failing:

- **Liveness, tested in both directions** — a fake clock advancing far past the heartbeat interval
  *with the publisher alive* must **not** produce `ContextStale`. That is the assertion the rejected
  age-threshold design fails, and without it a liveness check is indistinguishable from an age check.
- **Arbitration by permutation** — the same request set published in several orders must produce an
  identical armed map. A single-order test passes just as happily under "first wins".

### Still owed

- P1 and P2 before any Zones code. `Z-1`…`Z-6` remain written and never executed.
- The design is now *fully specified and entirely unimplemented*; five rounds of review have improved
  the specification and moved the implementation not at all, which is the honest summary of this PR.

---

## 2026-08-08 — PR #2 round 4: the four implementation-forcing gaps in the Zones design

**Scope:** the Zones module design and the two pillar contracts it extends, re-read against a review
that named four gaps that would force an implementer to invent missing decisions, plus a semantic
sweep for statements the earlier rounds left behind.

**Mechanical result:** `coord audit` 0/0/0 · `coord audit --since origin/main` 0/0/0 ·
`coord map --check` clean · 11 scaffold tests green. **No C# changed, so nothing here is a claim
about compilation**, and nothing in this repository has yet run on Windows.

### The four gaps, and what each turned out to be

| # | Gap | Root cause | Landed as |
|---|---|---|---|
| 1 | A layout edit could not transform occupancy, and nothing signalled that a surviving cell's stack needed re-placing | The operations were typed `LayoutTemplate → LayoutTemplate`, so the occupancy half of their own described behaviour had nowhere to live | [ADR 0019](decisions/0019-layout-edits-are-a-transaction.md) — `LayoutEdit` transaction + `GeometryStamp(topology, layoutRevision)` |
| 2 | `InvocationContext` was specified as *sampled at dispatch* | Dispatch is on the far side of a queue from recognition, so the doc asserted both "sample at dispatch" and "the state when it happened" | [CONDUIT §5.5](CONDUIT.md#55-what-every-dispatch-carries--the-invocation-context) rewritten around capture-at-recognition; [ADR 0017](decisions/0017-invocation-context-and-one-drag-lifecycle.md) corrected |
| 3 | Pointer-region arbitration resolved overlaps by "earlier registration wins", and the payload contradicted ADR 0013 | Registration order is a property of how the host happened to load modules that run — an unstable sort | [CONDUIT §3.6](CONDUIT.md#36-pointer-gesture) — user priority then stable module id; withdrawal-always-succeeds; token-not-coordinates reconciled |
| 4 | A removed monitor had two contradictory answers, and `stackOnDrop = false` was defined for one shape of drop | Both are ADR 0016 cases that were closed for the common case and left open at the edges | [ADR 0020](decisions/0020-dormant-stacks-and-the-displacement-rules.md) — dormancy, and displacement fully specified |

### The pattern worth recording

**Three of the four are the same defect: a decision recorded in prose that its own type signature
cannot express.** Merge was described as concatenating rings by a function with no ring in scope; the
invocation context was described as event-time truth by a mechanism that reads after the queue; the
pointer payload was described as a cursor position by a contract that had already replaced it with a
token. In each case the prose was the correct intent and the signature was the bug — which is the
argument for writing the sketch types out in the design rather than only describing behaviour, since
the contradiction is invisible until the two sit next to each other.

**Gap 3's root cause generalises past this pillar.** "First one wins" reads as deterministic and is
not: it is deterministic *given a load order*, and load order is not an input anyone controls or can
see. Any future arbitration rule in this project should be checked against the same question — would
two runs of the same configuration produce the same winner?

### Semantic sweep — found by grepping for consequences, not for the claim

The earlier rounds established that grepping for a retracted sentence misses the places that state
its *consequence* in different words. Four such places this pass:

- **[ATLAS §4.2](ATLAS.md#42-drag-take-the-snapshot-once)** anchored the drag snapshot's release to
  `MoveSizeEnd` — a correct sentence about the wrong stream once Zones moved to the gesture. Rewritten
  around "pick one stream and hold the snapshot against that one".
- **[ADR 0016 §6](decisions/0016-zone-occupancy-member-states.md)** still ended by recording an orphan
  as `Displaced`. ADR 0020 §4 removes the orphan, so the state has nothing left to name.
- **`src/pillars/atlas/README.md` and `src/pillars/conduit/README.md`** each carried the heading
  *"Status: contract types written, never compiled"* directly above a body citing the green CI run —
  **self-contradicting inside one screen**, and missed by the PR #1 evidence sweep because that sweep
  searched for banner text and these were section headings.
- **`coord.py`'s generated placeholder** told every future scaffolded module that "nothing in this
  repository has ever been through a C# compiler".

That last pair is the reusable lesson: the PR #1 sweep fixed 65 claims and still left four, all of
them in *headings and generated output* rather than in prose. **A sweep that greps the body text does
not see the table of contents or the code generator.**

### Still owed

- Everything in [NEXT.md](NEXT.md) — P1 and P2 come before any Zones code exists.
- `Z-1`…`Z-6` remain **written and never executed**; `Z-6` was rewritten this pass around the single
  gesture lifecycle and gained two aborts (process killed mid-drag; overlay count after a normal drop).
- The Zones design is now *fully specified and entirely unimplemented*, which is the honest state to
  shelve it in — and the gap between those two words is the whole of P3.

---

## 2026-08-08 — PR #1 evidence closeout (repository-wide sweep after the first green CI run)

**Scope:** every claim in the repository about build and test status, re-stated against an observed
run rather than an assumption. Triggered by review: with CI compiling, the repository's own honesty
machinery had inverted — roughly 65 claims across 39 files asserted something that was no longer
true.

### The observed result — verified from the run, not from the reviewer's summary

Commit `7aef6ff`, GitHub Actions, all six checks green:

| Job | What it actually did |
|---|---|
| Core build + tests (ubuntu) | built **5 portable projects** (3 production + 2 test), each `0 Warning(s) 0 Error(s)` |
| Core suites (ubuntu) | **45 tests, 0 failed, 0 skipped** — Atlas 25, Platform 20, run per-project by `coord test` |
| Windows build | built the **3 projects under `src/`**, each `0 Warning(s) 0 Error(s)` |
| Docs audit | `audit.py`, `genmap.py --check`, and the 4 scaffold tests, all green |

The zero-warning result is the load-bearing part: `TreatWarningsAsErrors` is on, so a single warning
anywhere would have failed the build. **Read from the job logs, not from the check-run conclusions** —
a green tick is a claim about a job, and this project's standard is that the claim gets checked.

**Precision worth keeping:** the Windows job compiled the same three *portable* projects with a
Windows toolchain. There is no Windows-*targeted* project in the repository at all, so nothing said
here is evidence about P/Invoke, WinUI, or the Shell.

### Fixed this pass

- 🔴 **~65 stale evidence claims across 39 files.** `NEVER COMPILED` banners in every `.cs` file, the
  three `.csproj` headers, `Directory.Build.props`, `coord.py`'s module docstring, the `ci.yml`
  header, three pillar/platform READMEs, `tests/README.md`, and the status sections of CLAUDE.md,
  README.md, AGENTS.md, NEXT.md, ONBOARDING.md, OPERATING_MODEL.md, AUDIT.md, TECH_DEBT.md, the four
  skills, and five ADRs. Each replaced with the observation **and its boundary** — never a bare
  "compiles".
- 🟠 **`docs/NEXT.md` said "the three projects" immediately above a list of five.** Now "the five
  current projects — three production and two test projects", which is also the list CI requires.
- 🟠 **TD-1, TD-2 and TD-4 narrowed** to what remains true: no *local* toolchain, no solution file,
  and Windows-targeted code compiled-but-never-run.

### Accepted (not drift — do not re-triage)

- The `// SKETCH — not compiled` markers in ATLAS.md, CONDUIT.md and the add-a-module recipe are
  **correct**: those snippets are illustrative prose, genuinely not part of any project.
- The bootstrap entries below this one still say "nothing has been compiled". They are **dated
  records and were true when written**; rewriting history to match the present is the opposite of an
  audit trail. ADRs got dated amendment notes instead of edits.

### Health

- `coord audit` **0 ERROR / 0 WARN / 0 INFO**; `coord map --check` clean; closeout clean.
- Scaffold tests **4 passing**. Core suites **45 passing** (CI).
- **C#: compiles** (CI `7aef6ff`, Ubuntu + Windows, 0 warnings). **Desktop behaviour: none
  implemented, none validated.**

### Carry-forward — the one thing that matters most

The evidence machinery now has to defend the *opposite* error from the one it was built for. For
three rounds the risk was overclaiming an unverified state; from here the risk is that "compiles" and
"45 tests pass" quietly become "it works". They are not close. There is no Shell adapter, no module,
no process, and no window has ever moved. **The distance between a green build and a tool someone can
use is the entire remaining project**, and [manual-validation.md](runbooks/manual-validation.md) —
still never executed by anyone (TD-9) — is the only thing that can close it.

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
