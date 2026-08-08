---
title: Runbook — release & update (how a build reaches a machine)
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/OPERATING_MODEL.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
  - docs/audit-log.md
  - docs/runbooks/dev-setup.md
  - docs/runbooks/manual-validation.md
---

# Runbook — release & update (how a build reaches a machine)

> How a build becomes something running on one of the owner's machines, and how the *next* build
> replaces it without destroying anything. Versioning, packaging, the delivery channel, the
> settings-survival contract, rollback, and the code-signing problem — which is genuinely unsolved.
>
> **One sentence:** the moment this application is installed anywhere the developer is not sitting,
> *"we can add that later"* stops being true for that install — so the delivery channel is designed
> before it is needed, and this runbook is its target.
>
> **⚠ THE CHANNEL IS DESIGNED, NOT BUILT. Nothing in this document has ever been executed.** No
> package has been produced, no update has been delivered, no install has been upgraded. Every step
> below is a specification. This runbook is written **ahead of the implementation on purpose**, so
> that the implementation has something concrete to satisfy rather than being invented under
> pressure at the moment a second machine needs a fix. It is tracked as **TD-6** in
> [TECH_DEBT.md](../TECH_DEBT.md).

**Marker legend — every step in this document carries one:**

| Marker | Meaning |
|---|---|
| **[D]** | **Designed.** Written here, never executed. Everything in this document is [D] today. |
| **[X]** | **Executed.** Performed at least once, with a dated record. **Nothing yet.** |

The day the first step flips to **[X]**, edit it here with what actually happened — including the
parts of the design that turned out to be wrong. A runbook is a record of a procedure that worked.

---

## 1. Why this runbook exists before the code

[OPERATING_MODEL §3](../OPERATING_MODEL.md) sorts work by one question: *is this painful to graft
onto shipped installs?* Four things answer yes — the **update/delivery channel**, **module
identity**, **settings migration**, and **trigger arbitration** — and they get built now while
everything else waits for a real consumer. The delivery channel is the canonical member of that set:
without it, every feature deferred to "later" is stranded on every copy already running, and the only
remedy is walking to the machine with a USB stick.

Writing the runbook first has a second, quieter benefit. A delivery channel invented in a hurry
optimizes for *shipping the build in front of you*; one specified in advance can be held to the
constraints that actually matter — that settings survive, that a resident process can replace its own
files, that a bad release can be undone. Those constraints are cheap to state now and expensive to
retrofit.

**Where this sits in the plan:** the **seam** is P1 work (packaging identity, version comparison, an
install-over path that preserves settings); the **working pipe** is P5
([COORDINATOR §8](../COORDINATOR.md), [NEXT.md](../NEXT.md)). Today neither exists.

---

## 2. Versioning **[D]**

Three numbers exist in this system and they are **not** the same number. Conflating them is the most
likely early mistake, because it is invisible until an update goes sideways.

| Number | Shape | Changes when | Referenced by |
|---|---|---|---|
| **Product version** | `MAJOR.MINOR.PATCH` | any release | the delivery manifest, the installer, the Shell's about surface, release records |
| **Settings schema version** | a single integer | **only** when the settings shape changes | the settings file itself; drives the migration chain |
| **Ids** — module ids, capability ids, trigger-intent ids | strings | **never** | settings files, user bindings, the update manifest |

**One product version for the whole payload, including every module.** Modules do not version
independently and do not update independently — a module ships inside the host's update payload
(ADR 0008). This is a deliberate simplification for a single-developer toolbox: independent module
versioning buys compatibility matrices nobody wants to reason about, and buys them in exchange for a
problem this project does not have.

**The settings schema version moves on its own clock**, and usually does not move at all. Additive
changes — a new field read with a safe default — do **not** require a bump, which is the entire point
of the additive-by-default rule ([principle 6](../COORDINATOR.md)). A **structural** change requires a
bump plus an explicit migration step plus a test that **fails without the migration**
([OPERATING_MODEL §7](../OPERATING_MODEL.md)).

**Ids are permanent and are not versioned.** A capability id is referenced by a user's saved binding
on a machine you are not looking at; renaming it is a silently broken feature on somebody's desktop,
and reusing it is worse — it points an old binding at new behavior ([MODULE_SPEC §2.4](../MODULE_SPEC.md)).

**Version comparison must be explicit and testable.** "Is the manifest newer than what is installed?"
is Core logic — pure, host-testable, and exactly the kind of thing that is quietly wrong at `1.10.0`
versus `1.9.0` if it is ever compared as text. Put it in Core and test it against a table of pairs
including that one.

---

## 3. Producing a build **[D]**

### 3.1 The closeout gate, before anything is built

Nothing is packaged until the repository's own gate is green ([dev-setup.md §6](dev-setup.md),
[AUDIT.md](../AUDIT.md)):

```sh
./coord audit                    # zero ERROR
./coord audit --since origin/main
./coord map --check
./coord test                     # Core suites — on Linux and on Windows
./coord build                    # every project, Release configuration
```

Then the **always** rows of the per-release checklist in
[manual-validation.md §5](manual-validation.md) — S1, S5, S6 at minimum, plus whatever the release
touched. A release with an unrun applicable scenario is not blocked; it is **recorded as such**.

### 3.2 The artifact

An artifact is not just an executable. Whatever the packaging mechanism turns out to be, the produced
release must carry enough to be identified and verified later:

| Must carry | Why |
|---|---|
| The **product version** | the manifest compares against it; a record without it cannot be regressed against |
| The **commit** it was built from | the only way to reconstruct what a machine is actually running |
| The **SDK version and machine** it was built on | build reproducibility questions start here |
| A **content hash** | the client verifies before installing anything (§4) |
| Whether it is **packaged or unpackaged**, and whether the Windows App SDK runtime is **bundled** | this changes what the target machine needs and is currently unmeasured (**TD-10**) |

**Packaged versus unpackaged is an open decision, not a build flag.** It changes install layout,
where settings land, tray behavior, whether an update can replace files while the process is
resident, and whether signing is required at all. Make it once, deliberately, with an ADR — and note
that the answer interacts with §7.

---

## 4. The delivery channel **[D]**

The designed shape. Every element below is a specification with no implementation.

### 4.1 The manifest

A small document, fetched from a location the app knows, describing the current release:

```json
{
  "version": "1.2.0",
  "artifact": "<url or path>",
  "sha256":  "<hex>",
  "minimumFrom": "1.0.0",
  "notes": "<short human text shown before installing>"
}
```

`minimumFrom` is the one field that is easy to omit and expensive to add later: it lets a release
declare that installs older than a given version cannot upgrade directly. Without it, a two-year-old
install eventually meets a migration chain nobody tested.

### 4.2 The client flow

1. **Check** — on a schedule, **off the UI thread and off any hook path** ([principle 8](../COORDINATOR.md)).
   A check is network I/O; it never runs where it can stall input.
2. **Compare** — pure Core logic (§2). Nothing downloads on a comparison that has not been tested.
3. **Ask** — the user decides. A personal toolbox that updates itself without being asked is a tray
   utility that changes behavior underneath its owner; that is the "never make the desktop worse"
   constraint in [OPERATING_MODEL §6](../OPERATING_MODEL.md) applied to our own release process.
4. **Download and verify** — the hash is checked **before** anything is written into the install
   location. An unverified payload is never staged.
5. **Stage** — write the new payload beside the current install, not over it.
6. **Apply on restart** — the host is resident and holds its own files open. Applying means: stop
   accepting triggers, release the tray, swap, restart. **Never mid-drag, never inside a hook, never
   while a module is handling a dispatch.**
7. **Report** — what version is running now, in the Shell, and in the log.

### 4.3 Constraints the implementation must satisfy

- **A resident process cannot replace its own files while running.** Whatever mechanism is chosen
  (a small updater step, a scheduled swap on next launch, a packaged-app mechanism), it must be
  chosen explicitly. This is the single most likely source of "the update said it worked and nothing
  changed" — which is *a check that cannot fail*, failure shape 1.
- **Settings are never in the payload.** They live outside the replaceable install layout. An update
  that can overwrite settings is an update that will.
- **Interrupted updates leave a working install.** A power loss mid-apply must leave either the old
  version or the new one, never a half-swapped directory.
- **The applied version must be verified after restart, not assumed.** "The installer exited 0" is not
  "the new version is running." Read the running version and report it.

---

## 5. Settings survive the update — the hard requirement **[D]**

This is the contract the whole channel exists to protect, and it is
[principle 6](../COORDINATOR.md) stated as a delivery requirement:

> **An update must never lose a setting, and must never reset one. A reset is only ever explicit.**

The acceptance check is **[S6](manual-validation.md)** in the manual-validation runbook, run over the
**previous release**, not over a clean install. That distinction matters: a clean install tests
nothing about migration, and it is the easy path that quietly becomes the only path.

Three rules that make S6 passable rather than lucky:

- **Additive by default.** A new field is read with a safe default, so the old file still loads. This
  is free and should be the shape of nearly every change.
- **Structural changes get a migration step and a test that fails without it.** Write the failing test
  first and watch it fail. A migration guard nobody has seen fail is a comment
  ([OPERATING_MODEL §7](../OPERATING_MODEL.md)).
- **Back up before migrating.** Copy the settings file, with its schema version in the name, before
  any migration writes. This costs nothing and is the only thing standing between a bad migration and
  an unrecoverable loss of the user's accumulated configuration.

**A settings reset caused by an update is a P0 defect**, not a rough edge — see
[manual-validation.md S6](manual-validation.md).

---

## 6. Rollback **[D]**

Rollback is not symmetric with upgrade, and pretending otherwise is how a rollback destroys the thing
it was meant to save.

**What is straightforward:** keeping the previous artifact and reinstalling it. Retain the last known
good payload rather than re-downloading it — the situation in which you need a rollback is often the
situation in which fetching something is inconvenient.

**What is not:** settings. The additive rule guarantees *forward* compatibility — an old file loads in
a new version. It guarantees nothing backwards. A newer version's settings file may contain fields the
older version does not know about, and the older version will typically **drop them on the next save**.
So:

| Case | Rollback safety |
|---|---|
| No schema change between the two versions | safe |
| **Additive** change only | usually safe, but the new fields are lost on the first save by the old version — the user's newer configuration silently reverts |
| **Structural** change with a migration step | **one-way**, unless a down-migration was deliberately written. Restore the pre-migration backup (§5) instead of trying to reverse it |

**The rule:** roll back the *binary* and restore the *matching settings backup*. Do not roll back the
binary and keep migrated settings, and do not write a down-migration speculatively — write one only
when a real rollback needs it, and record it as an ADR.

**Record every rollback** the same way as a release (§8). A rollback is the most informative event a
delivery channel can produce, and it is the one most likely to go unwritten because the moment is
stressful.

---

## 7. Code signing and SmartScreen — the unsolved problem **[D]**

**This is genuinely unresolved, and it is stated here as an open problem rather than papered over.**

The situation for a personal Windows application:

- An **unsigned** executable downloaded to a machine triggers a SmartScreen warning that a
  non-technical user reads as "this is malware." The owner can click through it on their own machines,
  but the friction is real and it recurs on every release.
- A **signing certificate** costs money annually, and standard-validation certificates now generally
  require the private key to live on hardware or in a managed signing service — which means signing is
  no longer a step you can run casually from a laptop.
- **Signing alone does not remove the warning.** SmartScreen reputation accrues to a publisher
  identity over downloads and time, so a freshly issued certificate still warns until reputation
  builds. Extended-validation certificates historically shortcut this and cost more.
- **Store distribution** would sidestep the warning entirely, but changes the deployment model,
  imposes packaging and review, and is a poor fit for a toolbox that manipulates other applications'
  windows.

The options, with the honest trade:

| Option | Cost | What it actually buys | Fit for this project |
|---|---|---|---|
| **Do nothing** — unsigned | free | nothing; a warning per release on every machine | viable while the audience is the owner |
| **Self-signed certificate**, trusted on the owner's own machines | free, one-time setup per machine | clean installs on *your* machines; verifiable that a build is yours | **the leading candidate** — it matches the actual distribution (a handful of personal machines) |
| **A purchased certificate** | annual fee + hardware token or signing service | removes the "unknown publisher" identity problem; reputation still has to build | worth pricing only if the app is given to someone else |
| **Store distribution** | packaging + review + model change | no warning at all | poor fit; revisit only if the project's audience changes |

**The decision today is: unresolved, and deliberately deferred.** The recall hook is concrete —
**this becomes urgent the first time a build is given to somebody who is not the owner**, or the
first time the click-through friction is annoying enough to be worth money. Until then, the
truthful statement in any release note is *"unsigned; Windows will warn."*

Note the interaction with §3.2: **packaged deployment generally requires signing**, so the
packaged-versus-unpackaged decision and this one are the same decision wearing two hats. Decide them
together, in one ADR.

---

## 8. The release checklist **[D]**

```
[ ] Closeout gate green: coord audit · audit --since origin/main · map --check · test · build
[ ] manual-validation.md §5 "always" rows run (S1, S5, S6) — results recorded, skips named
[ ] Conditional scenarios for whatever this release touched
[ ] Product version decided; settings schema version bumped ONLY if the shape changed
[ ] If the schema changed structurally: migration step written, and its test OBSERVED FAILING first
[ ] Release build produced; artifact carries version, commit, SDK, machine, hash (§3.2)
[ ] Previous release's artifact retained for rollback (§6)
[ ] Manifest written: version, artifact, hash, minimumFrom, notes (§4.1)
[ ] Installed over the PREVIOUS release on a real machine — not a clean install
[ ] Running version verified after restart by READING it, not by assuming the installer's exit code
[ ] Settings from the previous version confirmed intact, item by item (S6)
[ ] Release record written (§9) and linked from docs/audit-log.md
[ ] docs/NEXT.md updated; anything learned added to README.md Pitfalls
```

---

## 9. Recording a release **[D]**

```markdown
## Release <version> — <YYYY-MM-DD>

Commit:     <sha>
Built on:   <machine>, SDK <version>, <packaged|unpackaged>, <signed|unsigned>
Settings:   schema <n> (<unchanged | additive | structural + migration step>)
Upgraded from: <previous version>  on  <machine(s)>

Gate:       coord audit <n> error · coord test <n>/<n> (Linux) <n>/<n> (Windows)
Scenarios:  S1 <result> · S5 <result> · S6 <result> · <others>  — skips and why
Observed:   <what actually happened, including surprises that did not fail anything>
Rollback:   <not needed | performed, and what it cost>
```

It lives in [docs/audit-log.md](../audit-log.md) alongside the audit entries — one chronological
record of what happened to this repository, rather than two that drift.

---

## 10. Status, and what closes it

Nothing here has been executed. The concrete conditions that let this document drop its
**designed-not-built** framing, in order:

1. **A build exists at all.** Blocked on the first compile ([NEXT.md](../NEXT.md) Active focus).
2. **The seam exists** — packaging identity, version comparison as tested Core logic, and an
   install-over path that preserves settings. That is P1.
3. **The pipe works end to end** — package, deliver, install over an existing install, with a
   structural settings change exercised by a test observed failing without its migration. That is P5,
   and it is the phase gate ([COORDINATOR §8](../COORDINATOR.md)).
4. **S6 passes on a real machine**, over a real previous release.
5. **The signing decision is made**, together with packaged-versus-unpackaged, in one ADR (§7).

**The trip-wire that promotes all of this to urgent:** the first install on a **second machine** —
one the developer is not sitting at. At that moment **TD-6** goes from latent to active regardless of
what else is in flight, because from then on this runbook is the only way any fix reaches that
install.

---

## See also

- [COORDINATOR.md §4, §8](../COORDINATOR.md) — the update channel as a platform service, and the P5 gate.
- [MODULE_SPEC.md §5](../MODULE_SPEC.md) — settings discipline and the settings-migration contract.
- [manual-validation.md](manual-validation.md) — **S6**, the acceptance scenario for this whole path.
- [dev-setup.md](dev-setup.md) — producing a build in the first place; the deployment questions in §3.3.
- [OPERATING_MODEL.md §3, §7](../OPERATING_MODEL.md) — why this is in the build-now set, and the
  evidence standard the checklist enforces.
- [TECH_DEBT.md](../TECH_DEBT.md) — **TD-6** (channel designed, unbuilt), **TD-10** (deployment shape
  unmeasured).
