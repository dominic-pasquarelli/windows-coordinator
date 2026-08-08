# ADR 0008 — The update / delivery channel is built now

Date: 2026-08-08
Status: Accepted

## Context

[OPERATING_MODEL.md](../OPERATING_MODEL.md) draws a hard line between what gets built now and what
gets deferred to a clean, empty seam plus a recall hook. The test is narrow and mechanical: *is this
painful to graft onto an installation already running on a machine you are not sitting at?* Almost
nothing passes. Four things do — the update / delivery channel, module identity, settings migration,
and trigger arbitration — and everything else is deliberately left unbuilt, because building on
speculation is the failure mode that principle exists to prevent.

Of those four, the delivery channel is the keystone, and the reason is structural rather than a matter
of degree. **It is the pipe every other deferred thing has to travel through.** Module identity
matters because update manifests and settings reference it; settings migration matters because a new
version has to read an old file — but a migration only ever runs if the new version arrives, and a
stable id is only useful across versions if there are versions. Without a delivery path, the copy of
the app on a given machine is frozen at whatever was put there, and "we can add that later" becomes a
sentence the architecture cannot honor for that install.

That is easy to dismiss for a personal tool on one machine, where "update" means rebuilding in place.
It stops being dismissible at the exact moment the tool becomes worth having on a second machine —
which, for a utility the owner uses every day, is the natural end state rather than an edge case.

## Decision

**Build the seam now, in P1, before any module needs it. Build the working path in P5.**

Built in P1, as part of the platform core rather than as a feature:

- a **packaging identity and a version the application can compare**, so the app can tell whether the
  thing being installed is newer than the thing installed;
- an **install-over-existing path that preserves the settings directory**, so an update is not a
  reinstall — with [ADR 0007](0007-settings-schema-additive-versioned-migrated.md)'s migration running
  on the first load afterwards;
- **module identity stable across versions**, so bindings and settings written by the old version
  still resolve in the new one;
- **the host owns delivery for every module.** There is no per-module updater and no per-module
  version; a module ships inside the host's payload, which follows directly from compile-time
  modularity ([ADR 0004](0004-module-is-the-modular-unit-and-the-adr-log-stays-unified.md)).

Deferred to P5, explicitly: producing the package, delivering it, and installing it over a previous
install, with a settings migration proven end to end.

### Honest status — decided, not built

**Nothing here exists.** No package has been produced. No install has ever been performed. No version
has ever been compared. The seam described above is a plan in [NEXT.md](../NEXT.md), not a mechanism,
and — as with everything else in this repository — none of the surrounding code has ever been compiled
([TD-1](../TECH_DEBT.md)). [TD-6](../TECH_DEBT.md) carries the gap.

This ADR is therefore a decision about **priority and ownership**, not a record of work completed. It
is written now because the specific failure it prevents is a failure of sequencing, and sequencing
decisions are only useful before the sequence runs.

**The recorded trigger: the first install on a second machine.** At that moment TD-6 turns from latent
to active and P5 is promoted to the Active focus regardless of what else is in flight — because that
is the moment a copy of the app exists that the developer cannot fix by rebuilding, and the cost stops
being hypothetical. The trigger is written into the debt register rather than left to judgement,
precisely because in the moment it fires there will be something more interesting to work on.

## Consequences

**P1 grows a task that produces nothing a user can see.** Packaging identity and an install-over path
demo as nothing at all. This is exactly the kind of work that gets postponed by a developer working in
evening-sized pieces, which is why it is simultaneously an ADR, a roadmap gate
([COORDINATOR.md §8](../COORDINATOR.md)), a NEXT item, and a debt row with a trigger. Four records for
one task is not redundancy here; it is the countermeasure to the specific way this task dies.

**The stack decision feeds into the mechanism.** If the Windows App SDK's runtime bootstrapper makes
"copy the folder and run it" impossible, the delivery mechanism inherits a prerequisite, and that has
to be discovered by the P1 spike rather than during a release
([ADR 0002](0002-csharp-dotnet9-and-winui3-as-the-stack.md), [TD-10](../TECH_DEBT.md)).

**Module identity becomes a precondition rather than a nicety.** It was already in the build-now set on
its own merits; this decision makes it load-bearing for delivery too, which is worth knowing before
someone proposes deriving a module's id from its assembly name or its folder.

**The seam must not quietly become an auto-updater.** What is decided here is a *delivery path* — the
ability to install a new version over an old one without losing the user's settings. A background
service that checks for updates, a notification surface, staged rollouts, delta packages: all of that
is additive, none of it passes the build-now test, and building it now would be exactly the
speculative generality the operating model forbids. If the seam starts growing in that direction
before P5, that growth is drift and an audit should catch it.

**Settings and delivery are coupled by design, and the coupling has to be tested together.** P5's gate
is not "an installer ran"; it is that a settings file written by the previous version loads in the new
one, with a structural change exercised by a test that fails without its migration. An update path
verified without that check has verified the easy half.

## Alternatives considered

**Defer entirely until a second machine actually exists.** The most reasonable-sounding option, and it
is what the build-now discipline is specifically designed to resist. Rejected on timing: the moment
the need appears is the moment the developer is least willing to stop and build infrastructure, and
the work is *larger* then, because it has to be retrofitted around whatever packaging assumptions have
accumulated. Deferring does not defer the cost — it defers the notice and raises the price.

**Manual copy forever, on the grounds that this is a personal tool.** Worth stating honestly: this is a
defensible position for a single machine and it costs nothing. It fails the moment the tool is worth
having on a laptop as well as a desktop, and it fails silently, because the second machine simply ends
up running an old version nobody remembers deploying. The named modules in [vision.md](../vision.md)
are all things the owner would want everywhere, so the single-machine assumption has an expiry date
even if it has no expiry date on the calendar.

**Adopt an off-the-shelf updater now** — a packaging-and-update framework, or the platform's own
packaged-app update mechanism. **Not rejected; deferred as the likely implementation.** This ADR
decides that the seam exists, when it is built, and that the host owns it. *Which* mechanism fills it
is a P5 choice, and the strong prior is that it should be an existing tool rather than something
hand-rolled, since an update mechanism is precisely the kind of code whose failures are discovered on
someone else's machine. Recording that here so P5 does not open by re-deciding a question this ADR has
already answered.

**Per-module updates — a plugin-store shape where modules version and ship independently.** Rejected
on two counts. It multiplies the delivery surface by the module count, so every module carries a share
of the hardest infrastructure in the project. And it contradicts compile-time modularity: modules here
are compiled participants in one host, not drop-in binaries
([ADR 0004](0004-module-is-the-modular-unit-and-the-adr-log-stays-unified.md)). The extensibility it
buys has no consumer — there is one developer and no third-party authors.

**Build the full P5 path now rather than only the seam.** Rejected as the mirror-image error. The
build-now test admits the *seam* because the seam is what is expensive to retrofit; the working path
is ordinary work that can be done when there is something worth delivering. Building a release
pipeline before there is a release is speculative generality wearing the costume of diligence.
