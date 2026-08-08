---
title: Windows Coordinator Documentation Specification
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - docs/AUDIT.md
  - docs/MAP.md
  - docs/MODULE_SPEC.md
  - docs/OPERATING_MODEL.md
  - docs/NEXT.md
---

# Windows Coordinator Documentation Specification

> Where documentation lives, why, and how it stays in line. This is the **contract for docs** — the
> dual of [MODULE_SPEC.md](MODULE_SPEC.md) (the contract for modules). The [audit
> protocol](AUDIT.md) enforces it; the generated [doc map](MAP.md) is its front door; the reasoning
> underneath it is [OPERATING_MODEL.md](OPERATING_MODEL.md).
>
> **One sentence:** every concern has exactly one canonical home, every doc declares structured
> frontmatter (an `updated` review flag and an `audited` accuracy flag), and the whole set is
> traversable from one generated map that cannot drift.

---

## 1. Why this exists

Windows Coordinator is a personal toolbox built in bursts around a day job. Any module may be put
down for months and picked up cold, and the whole architecture exists to make that resumption nearly
free ([OPERATING_MODEL §1](OPERATING_MODEL.md),
[COORDINATOR §7](COORDINATOR.md#7-non-negotiable-principles) principles 9–10). That only
works if the documentation never quietly stops being true — and documentation falls out of sync in
three specific ways this spec closes:

1. **No placement rule** → the same concern gets written up in two or three places, the copies
   diverge, and you end up with bespoke duplicated explanations instead of one reusable one. The risk
   here is concrete and immediate: Conduit, Atlas, the platform host, and a module could each
   plausibly "own" hotkey conflict resolution or monitor-change handling.
2. **No structure** → a doc's tier, status, and freshness are invisible, so a reader cannot tell
   whether it is current, who owns it, or when it was last checked against the code.
3. **No traversal** → docs sit under `docs/`, beside pillar code in `src/pillars/`, beside module
   code in `src/modules/`, and beside tooling in `tools/`, so you hand-jump between trees and lose
   the thread.

The payoff is larger than tidiness. **A single canonical home per concern forces you to decide "is
this a platform, a pillar, or a module concern?" *before* you write it down** — which is exactly when
a boundary contradiction is cheap to resolve, rather than after three diverging implementations
exist. Deciding that hotkey arbitration belongs to Conduit is a paragraph today and a rewrite of
every module later.

**A note on this repo's honesty position.** The tooling that enforces this spec
(`tools/doc-audit/audit.py`, `tools/doc-audit/genmap.py`, driven by `tools/coord/coord.py`) is
stdlib-only Python and has actually been executed. The C# in this repository has **never been
compiled** — no .NET SDK has ever touched it. Nothing in this spec should be read as implying
otherwise; see [OPERATING_MODEL §7](OPERATING_MODEL.md).

---

## 2. Placement — where a doc goes and why

### 2.1 The rule: documentation follows its code

A doc lives **with the thing it documents**, at the same level of the tree that thing's code lives.
Two exceptions are deliberate: a **pillar gets a top-level architecture spine** in `docs/` (it is a
first-class, project-wide subsystem that every module builds on), and **ADRs stay unified** (§2.3). A
third — runbooks — is described below.

| Tier | What it is | Code lives | Docs live |
|------|-----------|-----------|-----------|
| **platform** | The host itself — true with zero modules or ten: module host + lifecycle, registry and stable module identity, settings (versioned, migrated), the update/delivery channel, logging/diagnostics, and the WinUI **Shell** | `src/platform/` · `src/shell/` | top-level `docs/` ([COORDINATOR.md](COORDINATOR.md)) |
| **pillar** | A first-class cross-cutting subsystem every module builds on — **Conduit** (input & trigger fabric) and **Atlas** (desktop spatial truth) | `src/pillars/conduit/` · `src/pillars/atlas/` | **architecture spine** top-level in `docs/` ([CONDUIT.md](CONDUIT.md), [ATLAS.md](ATLAS.md)); **implementation detail** co-locates with its code |
| **module** | One self-contained behavior (Zones, Chrono) — a liftable subtree | its own subtree under `src/modules/` | co-located in that subtree (`README.md` + a `docs/` folder if it needs one) |
| **tool** | Developer tooling — the `coord` CLI, the doc-audit checker | `tools/coord/` · `tools/doc-audit/` | co-located with the tool |
| **meta** | Governance and process about the *project itself* — this spec, the audit protocol, onboarding, NEXT, HISTORY, INBOX, tech debt, vision, the map | — | top-level `docs/` (plus root `README.md`, `CLAUDE.md`, `AGENTS.md`) |

**Why a pillar spine is top-level, not co-located.** A pillar is a project-wide architectural
commitment: every module declares trigger intents to Conduit and reads the desktop through Atlas, so
their spines are read the way platform docs are read — before you write any module. They therefore
live in `docs/` next to [COORDINATOR.md](COORDINATOR.md). Implementation specifics (the P/Invoke
surface, the timer wheel's internals, the DPI-change bookkeeping) stay with the pillar's code. The
spine names `tier: pillar` plus its `module:` key; the co-located detail names the same pair.

**Why a module co-locates.** A module must stay a **liftable subtree** — you could move it to its own
repository and its documentation would come with it intact. That property is what makes shelving a
module for a year survivable ([MODULE_SPEC.md](MODULE_SPEC.md), the shelving contract).

**The Shell is `tier: platform`, not a pillar — and that is a decision, not an oversight.** The WinUI
settings/dashboard host in `src/shell/` is today a platform component with exactly one consumer.
**It graduates to a pillar (its own top-level spine in `docs/`) when a second independent consumer
needs the same registry-driven surface** — for example a `coord` subcommand or a web surface
rendering the identical module settings schema. Until that consumer exists, writing a Shell pillar
spine would be documenting a boundary nobody has tested. Naming the graduation trigger is how the
gate-don't-build discipline ([OPERATING_MODEL §3](OPERATING_MODEL.md)) shows up in the doc tree.

**The test:** ask *"is this a project-wide architecture spine?"* → top-level `docs/` (platform or
pillar). *"Is it only meaningful with this specific module's code present?"* → co-locate.

**Operational runbooks are a deliberate exception — they live together in `docs/runbooks/`.** A run
sheet usually spans tiers: `manual-validation.md` walks a real desktop through Shell UI, Conduit
hotkey capture, Atlas monitor enumeration, and a module's behavior in one sitting, and
`release-and-update.md` exercises the platform's delivery channel plus the `coord` tool. You want
**one place to find every run sheet**, not a hunt across module trees. A runbook therefore keeps the
`tier`/`module` of whatever it primarily exercises but lives in `docs/runbooks/`. This is a conscious
call, not drift, and the mechanical placement check never flags it.

### 2.2 Decision shortcut

```
Writing a doc about …
├─ a decision with trade-offs                            → docs/decisions/ (an ADR — always unified)
├─ the project's own process / orientation / roadmap     → docs/ (meta)
├─ host behavior: module lifecycle, identity, settings,
│  the update channel, the Shell                         → docs/COORDINATOR.md (platform)
├─ a pillar's architecture spine                         → docs/CONDUIT.md · docs/ATLAS.md
├─ a pillar's implementation detail                      → with its code, under src/pillars/
├─ a module (Zones, Chrono, …)                           → with its code, under src/modules/
├─ a tool (coord, doc-audit)                             → with its code, under tools/
└─ a run sheet a human executes on a real desktop        → docs/runbooks/ (exception, §2.1)
```

### 2.3 The one exception: ADRs stay unified

Decisions are a **single chronological project record** in `docs/decisions/`, even when a decision is
about one pillar or one module. Splitting the log per module would destroy the property that makes it
useful — that you can read the project's reasoning in the order it happened, and that a numbered gap
is a detectable error. A module's `README.md` *curates* the ADRs relevant to it (a short list of
links); the log itself is never split.

ADRs carry no YAML frontmatter. They use a dated header instead:

```markdown
# ADR NNNN — <title>

Date: 2026-08-08
Status: Accepted
```

The audit checks the sequence for gaps and duplicates, and checks that every ADR has both a `Date:`
and a `Status:` line.

---

## 3. Structure — frontmatter

Every **canonical doc carries YAML frontmatter**. It makes tier, ownership, and freshness
machine-readable — which is what lets [MAP.md](MAP.md) be generated rather than hand-curated, and
what lets the audit have an opinion about staleness.

```yaml
---
title: Windows Coordinator Audit Protocol   # required — human title (used by the map)
tier: meta                                  # required — platform | pillar | module | tool | meta
status: living                              # required — living | stable | frozen | historical
updated: 2026-08-08                         # required — bump on EVERY substantive edit (review flag)
audited: 2026-08-08                         # optional — last ACCURACY re-read (accuracy flag)
module: conduit                             # optional — pillar/module/tool grouping for the map
related:                                    # optional — cross-links (wiki edges; must resolve)
  - docs/DOC_SPEC.md
---
```

**Field meanings:**

- **`title`** — the human name. The map uses it verbatim, so make it say what the doc is.
- **`tier`** — one of the five in §2.1. It is the doc's answer to "who owns this concern," and the
  map groups by it.
- **`status`** — `living` (changes often), `stable` (settled; rarely changes, like this project's
  operating model), `frozen` (on ice / shelved — §7), `historical` (an immutable record, e.g. an
  entry in the audit log).
- **`updated`** — the **review flag**. *Bumping it is a claim: "I re-read this and it is accurate as
  of this date."* The closeout audit (§6) **fails** when a doc changed on a branch without `updated`
  moving, so the act of editing forces a freshness re-confirmation rather than allowing a silent
  patch. *Same-day edits:* the date is day-granular and cannot advance twice in one day, so closeout
  accepts an unchanged `updated` **when it already equals today** — the doc is confirmed fresh as of
  now. A genuinely stale doc (an *older* date left unchanged on a changed file) still fails.
- **`audited`** — the **accuracy flag**, and it is *not* the same claim as `updated`. Set it to the
  date you last **re-read the whole doc against the code and confirmed it is still TRUE** — not
  merely "edited it." A doc can be `updated` today and not re-audited (you fixed a typo); an
  untouched doc can be re-audited to renew its accuracy without any edit at all. This distinction is
  the entire point: `updated` says *someone looked at the prose*, `audited` says *the prose still
  matches the thing it describes*. The audit flags a `living` doc as accuracy-stale when `audited` is
  more than 7 days or 15 commits old, and reports a missing `audited` as INFO so it gets a baseline.
  This is **advisory (WARN/INFO), never a hard gate** — staleness is driven by time and churn, so a
  blocking gate would fail unrelated work after a quiet fortnight. Anyone, human or AI, who verifies
  a doc in passing should bump it.
- **`module`** — optional grouping key — the pillar, module or tool the doc belongs to (`conduit`,
  `atlas`, `coord`, `doc-audit` today; a new module adds its own id). Not validated against a fixed
  list, because a new module must be able to add one. It is how the map produces a per-subsystem view
  instead of one flat list.
- **`related`** — explicit cross-links forming the wiki graph. Entries are **repo-root-relative**
  (`docs/AUDIT.md`, `CLAUDE.md`) and the audit **errors** if one does not resolve. Body links, by
  contrast, are ordinary Markdown relative to the doc's own location.

**Required on:** every `*.md` under `docs/` (at any depth — including `docs/runbooks/`,
`docs/recipes/`, and `docs/freezes/`), and every `README.md` (the root one plus each pillar, module,
and tool).

**No `audited:` key on the four append-only record docs** — [MAP.md](MAP.md), [INBOX.md](INBOX.md),
[audit-log.md](audit-log.md), and [HISTORY.md](HISTORY.md). They are summaries-as-of-their-date, not
living claims about current code, so "is this still true?" is not a meaningful question to ask them.

**Exempt from frontmatter entirely:** `docs/decisions/` (ADRs use the dated header in §2.3),
`CLAUDE.md` and `AGENTS.md` (standing instruction files with their own shape), `.claude/` skill
definitions (Claude Code owns that schema), and the GitHub pull-request template.

---

## 4. Single source of truth — one concern, one home

**A concern is documented in exactly one canonical place; everything else links to it and never
restates it.** This is the rule that prevents duplicated, quietly diverging explanations.

- **A feature's design and status live in one doc.** If [CONDUIT.md](CONDUIT.md),
  [COORDINATOR.md](COORDINATOR.md), and a module README all mention hotkey conflict arbitration,
  exactly one of them *owns* it — the lowest tier that fully contains it — and the others link. A
  concern spanning a pillar and a module is owned by the **pillar**, because the pillar is the shared
  substrate and the module is one consumer of it.
- **Cross-link, do not copy.** Needing the same fact in two places means putting it in one and
  linking from the other. A copied paragraph is a future contradiction with a delay fuse.
- **When you cannot tell who owns it, that is a design signal, not a formatting problem.** If it is
  genuinely unclear whether DPI-change handling belongs to Atlas or to the platform host, resolve
  *that* before documenting — it usually means the boundary itself needs a decision (an ADR). Writing
  it in three places would have hidden the question and let three implementations grow.

The mechanical checker can hint at this (a duplicated heading across docs is a signal of likely
restatement) but the real call is judgement — [AUDIT.md](AUDIT.md) walks it as a dedicated lens.

---

## 5. Navigation — the wiki front door

[**docs/MAP.md**](MAP.md) is the single traversable index of every doc, grouped tier → module. It is
**generated** from frontmatter (`coord map`, i.e. `tools/doc-audit/genmap.py`) and **drift-checked**
by the audit — a stale map is an ERROR — so it can never fall behind the real doc set. You get the
benefit of a hand-curated hub with none of the maintenance rot.

- **Start anywhere, reach everywhere.** The map links every doc; every doc declares `related` edges
  back into the graph. You never hand-jump between `docs/` and `src/modules/` again.
- **Orphan check.** The audit reports (INFO) a canonical doc that nothing links to — weave it in or
  ask why it exists.
- **Regenerate, never hand-edit.** MAP.md carries a generated marker; edits are overwritten on the
  next `coord map`. Generation is deterministic — a pure function of the doc set with no timestamps —
  so `coord map --check` is a meaningful gate rather than a source of spurious diffs.

---

## 6. Lifecycle — created → maintained → accuracy-audited → closed out → frozen

| Stage | What happens | Enforced by |
|-------|-------------|-------------|
| **Created** | The new doc gets frontmatter and a home per §2, and is linked into the graph (§5). | `coord audit` (frontmatter, related, orphan) |
| **Maintained** | Every substantive edit bumps `updated` (§3) — editing *is* re-confirming. | `coord audit --since <ref>` |
| **Accuracy-audited** | The doc is periodically **re-read against the code** and `audited` bumped. Proactive, plus a sweep of anything stale by more than 7 days or 15 commits. | `coord audit --accuracy` |
| **Closed out** | At phase end or before a merge: changed docs must be re-confirmed, and changed code with no touched doc is flagged. | `coord audit --since origin/main` |
| **Frozen** | At a save point the whole project is swept and certified resumable from cold. | the `/freeze` ceremony (§7) |

### Closeout: the documentation audit as a definition-of-done step

Finishing a branch includes running **`coord audit --since origin/main`** — the diff-aware mode. It
looks at every file changed on the branch and applies two rules:

- a **changed doc** whose `updated` did not move → **ERROR**. You edited it; re-confirm it.
- **changed code** under a pillar or module with **no doc touched** → **WARN**. Not every code change
  needs a doc change, so this is a prompt, not a wall: confirm the docs still describe reality, then
  proceed.

This is the mechanical form of "look at every file on the branch and make sure the documentation is
up to date." A phase is not done with ERROR-level drift outstanding.

---

## 7. Save points — putting the project on ice

A **freeze** is the whole-project version of the module shelving contract
([MODULE_SPEC.md](MODULE_SPEC.md)): a deliberate, certified save point, so the project can be put
down for months and resumed without friction. It is the strongest expression of this spec's goal —
*frictionless resume is only possible if the documentation never fell out of sync*, and a freeze is
where we prove it did not.

The [`/freeze` skill](../.claude/skills/freeze/) runs the ceremony and writes a dated record to
[`docs/freezes/`](freezes/). The gate: zero ERROR drift, the map current, [NEXT.md](NEXT.md) pointing
at a real next action, every module and pillar meeting its shelving contract, and a one-screen "how
to resume" snapshot that states plainly what is verified and what is not.

---

## 8. Quick reference

- **Where does this doc go?** → the §2.2 shortcut. Documentation follows its code; meta and platform
  and pillar spines go top-level in `docs/`.
- **One concern, one home.** Cross-link; never restate (§4).
- **Frontmatter on every canonical doc**, and **bump `updated` whenever you touch it** (§3).
- **`audited` is a different claim than `updated`** — it means you re-read the doc *against the code*
  and it is still true (§3).
- **Traverse from [the map](MAP.md)**; regenerate with `coord map` (§5).
- **Closeout = `coord audit --since origin/main`** (§6). **Save point = `/freeze`** (§7).
- **The audit ([AUDIT.md](AUDIT.md)) enforces all of the above.** This spec is the *what*; the audit
  is the *check*; [OPERATING_MODEL.md](OPERATING_MODEL.md) is the *why*.
