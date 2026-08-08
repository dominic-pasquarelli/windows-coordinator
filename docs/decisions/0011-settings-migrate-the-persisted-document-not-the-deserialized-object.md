# ADR 0011 — Settings migrations run on the persisted document, not the deserialized object

Date: 2026-08-08
Status: Accepted · Amends [ADR 0007](0007-settings-schema-additive-versioned-migrated.md)

## Context

[ADR 0007](0007-settings-schema-additive-versioned-migrated.md) settled the settings contract:
additive by default, versioned, and **structural changes handled by an explicit migration step**. It
named the cases a migration exists for — *a field renamed, a shape flattened, a list turned into a
dictionary* — and the mechanism it specified was a method on the settings type itself:

```csharp
IVersionedSettings Migrate(int loadedSchemaVersion);
```

That mechanism cannot perform any of the cases it was written for, and the reason is not subtle once
seen. `Migrate` receives an instance of the **current** settings type. To produce that instance, the
deserializer has already read the stored document and discarded every property the current type has
no home for. A field that was renamed in v2 no longer exists as a member, so its v1 value was dropped
before `Migrate` was called. A list that became a dictionary failed to bind and left a default.

So the API could only ever perform the migrations that need no migrating — additive changes, which
ADR 0007 correctly says require no version bump at all. For everything else it would run, return
successfully, and silently produce a document with the user's data missing. The failure mode is the
exact one ADR 0007 opens by ruling out: *"a user losing their zone layouts because a field moved."*

Found in review of PR #1, before any of it was implemented or compiled. Nothing shipped with this
defect; what shipped was a contract that promised something its own signature forbade.

## Decision

**Migrations operate on the persisted JSON document, one version step at a time, before
deserialization.**

1. `IVersionedSettings` keeps only `int SchemaVersion` — the version the current code writes. It no
   longer declares a migration method.
2. A structural change ships an **`ISettingsMigration`**: `int FromVersion` and
   `JsonObject Migrate(JsonObject document)`, producing the document at `FromVersion + 1`. The old
   data is all still present, because nothing has bound it to a type yet.
3. **`SettingsMigrator.MigrateToCurrent(document, currentVersion, migrations)`** walks the chain from
   the document's stamped version up to the current one, applying exactly one step per version. The
   store deserializes only after the chain completes.
4. The **runner stamps the new version**, not the migration — so an author who forgets cannot produce
   a document that lies about its own shape, or an unterminating loop.
5. Refusals, all of them faults rather than recoveries:
   - a document from a **newer** schema is refused, because loading it and saving afterwards would
     write an older shape over newer settings — a silent downgrade;
   - a **malformed** document (no version, a non-integer version, a version below 1) is refused,
     because substituting defaults means the next save overwrites a file that may have been one typo
     from recoverable;
   - a **broken chain** (a missing `FromVersion`, or two steps claiming the same one) is refused.

The schema version lives in a reserved `schemaVersion` property on every persisted document.

## Consequences

- **The migrations ADR 0007 promised are now possible.** A rename moves a value between property
  names; a collection reshape rewrites an array into objects. Both are tested
  (`tests/Coordinator.Platform.Core.Tests/SettingsMigrationTests.cs`), and both are tests that could
  not have been written against the old signature.
- **A migration is testable without a settings type, a file, or a disk** — it is a function from
  `JsonObject` to `JsonObject`. That is the Core/Shell split ([ADR 0003](0003-the-core-shell-split.md))
  applied to persistence.
- **The settings type describes the current shape only.** History lives in the migration chain, where
  it can be read in order. Previously the type would have accumulated compatibility members for
  fields it no longer had, which is how a settings class becomes unreadable.
- **Cost: migrations are stringly-typed.** A migration manipulates property names as strings, so a
  typo is a runtime failure rather than a compile error. This is the accepted price of operating
  before binding, and it is why every migration ships with a test that asserts the value survived —
  the test is what turns the string into a checked claim.
- **Cost: `ISettingsStore.LoadAsync` gained a parameter.** The caller passes its migration chain.
  An empty chain is correct for a module that has never made a structural change, which is every
  module today.
- `schemaVersion` is now reserved: a settings type must not declare a field that serializes to it.

## Alternatives considered

- **Keep `Migrate` on the settings type and additionally retain the raw document** (e.g. hand the
  type both its bound self and a `JsonObject` of the original). Rejected: it offers two sources of
  truth for the same values and leaves the author to work out which one is authoritative for a given
  field — a decision that is easy to get wrong and impossible to see in review.
- **Version-specific DTOs** (`SettingsV1`, `SettingsV2`, …, with a mapper per step). Genuinely
  type-safe, and the strongest alternative. Rejected for now on cost: every structural change would
  add a full type plus a mapper, permanently, and the project has zero modules and zero shipped
  schema versions. The seam does not foreclose it — a migration step is already a function per
  version, so a step may deserialize into a version-specific DTO internally the day one is worth
  writing. Revisit when a module reaches its third structural version, or when a stringly-typed
  migration first ships a typo that a test did not catch.
- **Do nothing until a real migration is needed.** Rejected: this is the retrofit-expensive class
  named in [OPERATING_MODEL §3](../OPERATING_MODEL.md). The mechanism has to be right *before* the
  first document is written on a user's machine, because by the time a migration is needed, the
  documents that need it already exist.
- **Migrate on load failure only** (try to bind; migrate if it throws). Rejected: binding does not
  fail on a renamed field, it silently succeeds with a default. The failure this design exists to
  prevent produces no exception to trigger on.
