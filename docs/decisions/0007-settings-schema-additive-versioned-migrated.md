# ADR 0007 — Settings schema — additive by default, versioned, migrated

Date: 2026-08-08
Status: Accepted

## Context

A user's settings file is the one artifact in this system that the developer cannot regenerate. The
binaries can be rebuilt. The layout templates ship with the app. But the zone layout somebody spent an
evening tuning across three monitors, and the hotkey bindings that have been in their fingers for a
year, exist in exactly one place — a file on a machine the developer will never see, written by a
version of the app that may be arbitrarily old.

That file has to survive every future update, and the update will be performed by someone who is not
watching for problems. If it goes wrong, the developer does not see the failure, cannot inspect the
file, and receives a report that says "it forgot my layouts."

So the schema rules have to be chosen before the first release rather than discovered after it, and
they have to be chosen so that the *common* case — adding a field — is free. A discipline that taxes
the routine change is a discipline that gets routed around, and the way it gets routed around is by
someone quietly deciding that this particular change probably will not matter.

## Decision

**Settings are versioned; schema change is additive by default; structural change requires an explicit
migration; a reset is only ever explicit.** Six rules, stated precisely because the precision is the
decision.

**1. Every settings record carries a `Version`.** One integer, bumped only by rule 3.

**2. Additive change is the default and needs no migration.** A new field must be *read with a safe
default*, so a file written before that field existed still loads and the absent value is simply the
default. Adding a field is not a schema change requiring ceremony — it is the normal case, and it is
deliberately made free.

**3. A structural change requires an explicit `Migrate()` step and a version bump.** Structural means:
renaming a field, changing its type, changing the units or the meaning of an existing value, splitting
one field into two, merging two into one, or changing the shape of a collection. Migrations are pure
functions from the previous shape to the next, applied **in sequence** so that a file several versions
old is brought forward one step at a time rather than by a single function that has to know every
history.

**4. Unknown fields are preserved, not discarded**, wherever the serializer permits. A file written by
a newer version and read by an older one must not lose the newer version's data at the next save. This
matters in two ordinary situations — a downgrade after a bad update, and the same settings synced
between two machines running different versions — and in both, silent field-dropping looks exactly
like corruption.

**5. A reset is only ever explicit and user-initiated.** There is no code path that decides settings
"looked wrong" and starts fresh. A settings file that fails to load is reported, copied aside intact,
and the app starts on defaults **without overwriting the original**. The user keeps the artifact even
when the app cannot read it.

**6. Every migration step is host-tested, and the test fails without the migration.** A fixture of the
old shape, an assertion about the new one, and — per the operational rule in
[OPERATING_MODEL.md](../OPERATING_MODEL.md) — a demonstration that removing the migration turns the
test red. A migration test that would pass without the migration is a check that cannot fail, sitting
in front of the one artifact that cannot be recovered.

### Why this matters more for a desktop app than it looks

The rule reads like ordinary schema hygiene. The reason it is a non-negotiable principle here is that
the failure is *invisible and indistinguishable from data loss*.

**A settings file the new version silently discards is data loss.** The fact that it happened through
a defaulting read rather than a `File.Delete` is a distinction only the developer can perceive. From
the user's side, the update ate their configuration. And the trust cost of that is asymmetric: it is
paid once and remembered at every subsequent update, which turns "update available" into a decision
rather than a click. For a personal productivity tool whose entire value proposition is that it makes
the machine feel better, an update that makes the machine feel worse is close to fatal.

**The second-order effect is what makes deferral safe everywhere else.** The build-now analysis in
[OPERATING_MODEL.md](../OPERATING_MODEL.md) concludes that most machinery is free to defer — leave a
clean seam, drop a recall hook, build nothing. That conclusion *depends on this rule*: a feature
deferred today can add its fields tomorrow and an old settings file will still load. If additive
change were not free, every deferred feature would carry a latent migration debt, and the
retrofit-expensive set would have to be much larger than four items. So the additive rule is not only
a settings policy — it is the mechanism that keeps the build-now set small.

## Consequences

**Schema shape is constrained on purpose.** Prefer flat, independently meaningful fields over shapes
whose meaning depends on their neighbors, because the latter forces a structural migration for what
should have been additive. A list whose *position* carries meaning, or a field interpreted differently
depending on another field's value, converts every future extension into ceremony. Lens F of the
[audit](../AUDIT.md) checks for exactly this — whether what has been built forecloses what is planned.

**Migration code is permanent.** Steps are never deleted, because an install can be arbitrarily old.
That means a growing body of code that is dead more than 99% of the time and must nevertheless be
correct, which is precisely why rule 6 requires it to be host-tested rather than eyeballed.

**Identifiers referenced by settings are permanent contracts.** Module ids and capability ids
([MODULE_SPEC.md](../MODULE_SPEC.md)) are written into settings and hotkey bindings, so renaming one is
a structural migration under rule 3, not a rename. Display labels are free to change; ids are not.

**Load-time cost grows slightly with version distance**, since a very old file walks several
migrations. Irrelevant at this scale, and worth stating so nobody optimizes it.

**None of this exists.** The settings store is P1 work in [NEXT.md](../NEXT.md); the end-to-end proof —
an update installed over a previous install, with a structural change exercised by a test that fails
without its migration — is P5's gate ([COORDINATOR.md §8](../COORDINATOR.md)). Nothing has been
compiled ([TD-1](../TECH_DEBT.md)), no settings file has ever been written, and no migration has ever
been run.

## Alternatives considered

**No versioning — load whatever parses and tolerate the rest.** Rejected: it works right up to the
first structural change, at which point there is no way to distinguish an old file from a corrupt one,
and therefore no correct behavior available. The version stamp costs one integer and is the only thing
that makes the difference knowable.

**Version, but reset on mismatch.** This is very common in personal utilities, precisely because it is
easy and it makes the failure go away from the developer's point of view. Rejected outright: it is the
data-loss path with a version number attached, and it converts an inconvenience for the developer into
an irreversible loss for the user.

**Migrate on write rather than on read.** Rejected on two grounds. A settings file is read far more
often than it is written, so most sessions would run against an unmigrated shape. And a crash between
load and first save leaves a file in the old shape while the running app has already applied the new
version's assumptions in memory — a state neither version's code was written for.

**A schemaless bag of string key/value pairs.** Superficially the most future-proof option, since
nothing can fail to load. Rejected because it moves every failure from load time to use time: nothing
is validated, nothing can be checked against a module's declared value specifications, and a typo in a
key produces a silently defaulted value at the moment of use rather than an error at the moment of
load. It trades a loud, early, fixable failure for a quiet, late, unattributable one.

**Store settings in the registry.** Rejected for recoverability rather than performance: a file can be
backed up, inspected, diffed, copied between machines, and restored by a user with no tools. Giving up
"just copy the file back" removes the one recovery path that makes an update failure survivable
without the developer's involvement.

**Keep a full version history of settings files** (write a new file per version, never overwrite).
Attractive, and not rejected on principle — it is simply larger than what rule 5's copy-aside behavior
buys, and it can be added later as an additive change. Recorded here so a future session recognizes it
as an available extension rather than a contradiction.
