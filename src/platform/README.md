---
title: Platform core — code front door
tier: platform
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - docs/COORDINATOR.md
  - docs/MODULE_SPEC.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
  - src/shell/README.md
---

# Platform core — the module membrane

> **The contract every module implements and consumes.** Module identity, the lifecycle the host
> supervises, the capability declarations that make everything controllable a named typed target,
> and the versioned settings that have to survive an update. Domain-agnostic by construction: true
> with zero modules loaded and true with ten.
>
> **One sentence:** this directory holds the small set of types a module talks to and nothing else —
> the architecture around them is [docs/COORDINATOR.md](../../docs/COORDINATOR.md), the obligations
> they place on a module are [docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md). It **compiles and is
> tested**; it **does** nothing yet.

## Status: contract types compile, and the settings/capability logic is tested

The C# here was authored without a local .NET SDK, so **CI was its first reader**. It compiles:
GitHub Actions at `7aef6ff` (2026-08-08) — Ubuntu and Windows, 0 warnings under `TreatWarningsAsErrors` — and `Coordinator.Platform.Core.Tests` passes **20 tests** covering the settings migration
chain and the capability invariants.

Nothing here has been compiled on a developer machine (**TD-1** in
[docs/TECH_DEBT.md](../../docs/TECH_DEBT.md)), and nothing here *does* anything: there is no module
host, no registry, no settings store implementation, and no process. "Compiles" and "the Core tests
pass" are the claims available. Not "works".

| | State |
|---|---|
| Architecture spine ([docs/COORDINATOR.md](../../docs/COORDINATOR.md)) | **done** |
| Module contract ([docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md)) | **done** — and unvalidated by any implementation (**TD-5**) |
| `src/platform/Coordinator.Platform.Core/` — the contract types | **compiles** (CI `7aef6ff`) |
| Module host, registry, lifecycle supervision | **TODO** — not started |
| Settings store implementation | **TODO** — the interface exists; nothing implements it |
| Update / delivery channel seam | **TODO** — planned for P1 (**TD-6**) |
| Logging and diagnostics | **TODO** — not started |
| Windows adapter for the platform | **TODO** — not created; see below |
| Core tests | **20 passing** — `tests/Coordinator.Platform.Core.Tests` (migration chain, capability invariants) |

## What is here

Five files, one namespace, no dependencies on anything outside the .NET base library.

| File | What it fixes |
|---|---|
| `ModuleManifest.cs` | Who a module permanently is. One field that can never change (the id), three that can change freely (display name, version, description). |
| `IModule.cs` | The lifecycle the host supervises: manifest, declared capabilities, initialise, enable, disable, dispose. |
| `IModuleContext.cs` | The **only** route from a module to the platform. No statics, no service locator, no ambient globals — which is what makes a module testable with a context of fakes. |
| `Capability.cs` | The stable id, the typed kind, and the declaration record. The id discipline is stated here because this is where it is enforced. |
| `Settings.cs` | Versioned settings, the `ISettingsMigration` chain that runs on the persisted document (ADR 0011), and the store that loads and saves them. |

**Every one of these was kept smaller than the specification describes**, on purpose. The
capability declaration has no value specification (no minimum, maximum, step, or option list);
`IModule` has no trigger-intent list, no dispatch handler, and no capability setter;
`IModuleContext` exposes settings and identity and nothing else. Each of those is real, intended,
and described in [docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md) — and each would have to be
invented from nothing right now, because the consumers that would push back on the shape (a
settings surface, a validator, a live pillar, a real module) do not exist. Guessing a shape and
being wrong is a breaking change; adding a member later is an additive one. Every omission is
recorded in the file that would have carried it, with the reason.

## Intended layout

The platform follows the same Core/Shell split as every module and pillar
([docs/COORDINATOR.md §3](../../docs/COORDINATOR.md)), and today only the Core half exists:

```text
src/platform/
├── README.md                          ← you are here
└── Coordinator.Platform.Core/         net9.0 · zero Windows dependencies · testable on any OS
    ├── Coordinator.Platform.Core.csproj
    ├── ModuleManifest.cs
    ├── IModule.cs
    ├── IModuleContext.cs
    ├── Capability.cs
    └── Settings.cs
```

The **project and assembly** carry the `.Core` suffix so they pair with the Windows adapter
described below; the **namespace** is plain `Coordinator.Platform`, because a consumer should not
have to name which half of the split a type came from.

**The Windows adapter is documented but not created in this pass.** The platform's Windows-facing
half — where the settings file actually lives, the process-level per-monitor DPI declaration, the
tray host, the update installer — needs a `net9.0-windows` project, and the natural home for most of
it is the WinUI host in [`src/shell/`](../shell/README.md). Which parts belong to a platform
adapter and which belong to the Shell is genuinely undecided, and deciding it without a compiler or
a running process would be a guess dressed as a decision.

The `boundary` check in [`tools/doc-audit/audit.py`](../../tools/doc-audit/audit.py) classifies a
project as Core from its declared target framework, so the absence of a `-windows` suffix in
`Coordinator.Platform.Core.csproj` is load-bearing rather than cosmetic: it is what makes a P/Invoke
or a Windows namespace appearing in this directory an ERROR-level finding.

## The three rules this directory exists to enforce

1. **A module reaches the platform only through the context.** If it is not on `IModuleContext`, a
   module does not get it. That is what makes a module testable in isolation — there is nothing else
   to reach.
2. **Ids are permanent; labels are free.** A module id, a capability id, and a trigger intent id are
   each chosen once and never renamed or reused. Saved settings and user-assigned bindings reference
   them as strings on machines nobody is looking at, so a rename is a silently broken feature and a
   reuse points somebody's existing binding at a different behaviour.
3. **Settings are additive by default.** A new field is read with a default, so yesterday's settings
   still load. Structural changes bump the schema version and ship an `ISettingsMigration`, with a test
   written first and observed failing before the migration is added. A reset is only ever explicit.

## Read order

1. [docs/COORDINATOR.md](../../docs/COORDINATOR.md) — the platform architecture: host, core,
   pillars, modules, the Core/Shell split, the principle list, the roadmap and its gates.
2. [docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md) — the module contract, which is the consumer
   side of every type in this directory.
3. [docs/CONDUIT.md](../../docs/CONDUIT.md) and [docs/ATLAS.md](../../docs/ATLAS.md) — the two
   pillars a module builds on alongside this contract.
4. [../../CLAUDE.md](../../CLAUDE.md) and [docs/NEXT.md](../../docs/NEXT.md) — standing orientation
   and what to do right now.

## Decisions that shaped this directory

ADRs live in the unified log at [`docs/decisions/`](../../docs/decisions/) — one chronological
project record, never split per area. The four that govern the code here:

- **ADR 0003 — the Core/Shell split.** Why this project targets `net9.0` and contains no Windows.
- **ADR 0004 — Module is the modular unit.** Why the membrane is shaped around a module rather than
  around a plugin or a service.
- **ADR 0007 — settings schema: additive by default, versioned, migrated.** Why `Settings.cs` looks
  the way it does.
- **ADR 0008 — the update / delivery channel is built now.** Why module identity and settings
  migration are in the build-now set at all, when nothing ships yet.

## Where to resume

**Not blocked.** These types compile and 20 tests exercise the settings and capability logic
(CI `7aef6ff`). What is missing is an implementation, not a verdict from a compiler.

The first action here is the one the contract cannot be judged without:

> Write the **module host** — load, start, stop, unload, with a module that throws on load isolated
> so the host and the other modules survive (principle 12). It is the first thing that will *use*
> `IModule` and `IModuleContext` rather than merely declare them, and it is what turns the three
> open questions below from taste into evidence.

Three known open questions follow, in order. Each is already written into the file that carries it,
so the code and this list cannot drift apart:

1. **`ModuleManifest` versus `ModuleIdentity`.** [docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md)
   §2.1 names the type `ModuleIdentity` and exposes it as `IModule.Identity`; the code here calls it
   `ModuleManifest` and exposes it as `IModule.Manifest`. The compiler cannot help here — both
   names compile fine; only one of them is what the spec promises a module author. Pick one, in the
   same session, and correct the loser.
2. **~~The `Migrate()` return type.~~ Settled 2026-08-08 by
   [ADR 0011](../../docs/decisions/0011-settings-migrate-the-persisted-document-not-the-deserialized-object.md).**
   The awkward return type is gone because the method is gone: migrating the *deserialized* object
   could never perform the renames and reshapes migrations exist for, since the deserializer has
   already discarded whatever the current type has no home for. Migrations now run on the persisted
   `JsonObject` before binding, via `ISettingsMigration` and `SettingsMigrator`. What is left to do
   here is not a decision but an implementation: there is no `ISettingsStore` implementation yet, so
   nothing actually reads a file, chains the migrations and deserializes the result.
3. **Which way the platform and the pillars depend on each other.** Today the pillars reference this
   project and it references neither of them, which keeps the graph acyclic — but
   [docs/MODULE_SPEC.md](../../docs/MODULE_SPEC.md) describes a context exposing desktop truth and
   trigger registrations, which would invert that. An accessor here, a separate context assembly, or
   the pillars reaching a module some other way: it is a real decision and it deserves an ADR rather
   than whichever answer the compiler makes easiest.

Only after the platform Core compiles should the module host and the settings store be written —
and the settings store starts with a migration test that fails without the migration, because a
guard nobody has watched fail is decoration.
