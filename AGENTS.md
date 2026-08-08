# AGENTS.md

This project's agent/LLM instructions live in **[CLAUDE.md](CLAUDE.md)** — read it first, in full.

Then:

1. [docs/NEXT.md](docs/NEXT.md) — the always-current "what to do now" tree. Start with the
   **Active focus** line; if it carries a `RESUME AFTER DETOUR` anchor, start there instead.
2. [docs/ONBOARDING.md](docs/ONBOARDING.md) — cold-start setup and the read order.
3. [docs/COORDINATOR.md](docs/COORDINATOR.md) — the platform architecture (the contract).
4. [docs/MODULE_SPEC.md](docs/MODULE_SPEC.md) — the module contract, when creating or resuming a
   module.

**What this is:** Windows Coordinator, a tray-resident Windows productivity toolbox in the spirit of
PowerToys. The modular unit is a **Module**; two pillars — [Conduit](docs/CONDUIT.md) (input &
trigger fabric) and [Atlas](docs/ATLAS.md) (desktop spatial truth) — are the only ways a module
touches input or the desktop. Every module and pillar is split **Core** (`net9.0`, zero Windows
dependencies, unit-tested anywhere) / **Shell adapter** (Windows-only, thin, validated by hand).

**Read this before you claim anything:** the Python tooling (`coord`, the doc audit) is executed
and verified. **The C# compiles and the Core suites pass** — GitHub Actions at `7aef6ff`
(2026-08-08), Ubuntu and Windows, 0 warnings, 45 tests, 0 failed. **But no module exists, there is
no Shell adapter, and nothing has ever run on Windows** — no hotkey, no window, no tray icon, no UI.
"Compiles" and "the Core tests pass" are checkable claims; **never** say "works". Full statement:
CLAUDE.md → "Current honesty boundary".

Key rules (full list in CLAUDE.md): match the architecture or flag it — propose an ADR rather than
quietly working around a principle; keep `docs/NEXT.md` current, especially before stopping; leave
every module resumable (the shelving contract — [MODULE_SPEC §7](docs/MODULE_SPEC.md)); each phase
ends compiling with the app still working; host-test the pure logic via `coord test`; never commit
secrets. **Documentation is load-bearing** — this project is worked in bursts, and a phase isn't
done until a cold reader could resume from the docs alone.

**Audit protocol:** before a phase ends or a module is shelved, run `coord audit` (mechanical
code↔doc drift plus the modularity **boundary** check, which reads `using` directives, namespaces,
`[DllImport]` attributes and `ProjectReference` elements as text — so it needs no compiler and runs
on a machine with no .NET SDK) and walk the six lenses (alignment · modularity · resumability · fidelity ·
recall/lifecycle · connectivity/forward-compat), then log it in
[docs/audit-log.md](docs/audit-log.md). ERROR-level drift blocks a phase. Invoke the full pass with
the `/audit` skill; the rarer two-blind-passes sweep is `/deep-audit`; everything in one sitting is
`/comprehensive-audit`. Full protocol: [docs/AUDIT.md](docs/AUDIT.md).

**Documentation spec:** docs follow their code — tiers `platform` · `pillar` · `module` · `tool` ·
`meta`. **One concern, one canonical home** — cross-link, never restate. Every canonical doc carries
frontmatter; **bump `updated` whenever you edit it**, and **set `audited: <today>` whenever you
re-read a doc against the code and confirm it is still true** (an accuracy flag, distinct from
`updated`). The audit flags docs stale beyond 7 days or 15 commits since `audited`, so stamp
`audited` on docs you verify in passing. Closing out a branch = `coord audit --since origin/main`.
Traverse from the generated [docs/MAP.md](docs/MAP.md) (`coord map`). A whole-project save point is
the `/freeze` skill, which writes [docs/freezes/](docs/freezes/README.md). Full spec:
[docs/DOC_SPEC.md](docs/DOC_SPEC.md).

**Snapshot protocol:** if the user says `SNAPSHOT:` / `IDEA:` (or clearly wants to capture a stray
thought), append it verbatim to [docs/INBOX.md](docs/INBOX.md) **first**, then assess it — if it is
small and safe enough to finish in the same reply, offer to just do it (progress beats paperwork);
otherwise propose where it should land and confirm before editing. Steer both ways: offer
park-or-think-through once when the user drifts into a future tangent, and offer to **promote** a
parked idea to active work when the conversation about it has clearly become the real work. A
think-through drops a resume anchor into `docs/NEXT.md` **before** diving in and clears it on the
way back — the anchor is the contract. Full protocol: CLAUDE.md → "Snapshot intake & steering".

**Evidence standard:** a successful command must mean the claimed outcome actually occurred. The
three failure shapes to watch for are *a check that cannot fail*, *a claim stronger than its
evidence*, and *an error found after the expensive step*; the operational rule is **when you add a
guard, prove it fails without the fix**. Concretely here: a green `coord test` proves **Core logic
only** — it is never a claim about window placement, hotkey capture, DPI behavior, or the UI. Those
come only from [docs/runbooks/manual-validation.md](docs/runbooks/manual-validation.md), performed
on a real Windows desktop, with the result written down. Full statement:
[OPERATING_MODEL §7](docs/OPERATING_MODEL.md).

**Flush before compaction:** when context fills toward ~90%, don't wait for the auto-summary — sweep
`docs/NEXT.md` and every doc the session touched, record any decision that isn't written down
anywhere, run `coord audit`, and commit. A post-compaction reader must resume from current docs, not
from a lossy summary.
