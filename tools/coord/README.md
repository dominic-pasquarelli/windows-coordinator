---
title: coord — the developer entry point
tier: tool
status: living
updated: 2026-08-08
audited: 2026-08-08
module: coord
related:
  - docs/AUDIT.md
  - docs/DOC_SPEC.md
  - docs/MODULE_SPEC.md
  - docs/OPERATING_MODEL.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
  - docs/recipes/add-a-module.md
  - docs/runbooks/dev-setup.md
  - docs/runbooks/manual-validation.md
  - tools/doc-audit/README.md
---

# `coord` — the single developer entry point

> Everything you do to this repository, behind one command: build it, test it, run it, check the
> documentation, scaffold a module, and find out what this machine can actually do. Its whole job is
> to delete the question *which command, which project, which nuance* — because the answer to that
> question changes with the machine you are sitting at, and having to re-derive it is exactly the
> friction that makes a project you left six months ago feel unapproachable.
>
> **One sentence:** `coord <thing>` is always the right command, `coord doctor` always tells you the
> truth about the machine, and the two subcommands that matter most today — `audit` and `map` — work
> on a machine with no .NET SDK at all.

The tool lives in `tools/coord/coord.py`. The launchers at the repository root (`coord` on POSIX,
`coord.cmd` on Windows) resolve it relative to their own location, so it works from anywhere.

---

## Quick start

```sh
./coord doctor            # ALWAYS first on a new machine — what is installed, what is missing
./coord audit             # the documentation + modularity gate (works with no .NET)
./coord map --check       # is the generated documentation index current?

./coord build             # dotnet build            — needs the SDK
./coord test              # dotnet test, Core suites — needs the SDK, runs on any OS
./coord run               # launch the Shell host    — needs the SDK, Windows only

./coord new-module zones  # scaffold a module
```

On Windows drop the `./` — `coord doctor`, `coord audit`, and so on.

No install, no virtual environment, no pip. Stdlib-only Python 3.11+. **If you find yourself
creating a virtual environment for this repository, something has gone wrong** — either the tooling
grew a dependency it should not have, or you are in the wrong repo.

---

## The guarantee that matters most: `audit` and `map` need no .NET

**`coord audit` and `coord map` never touch the .NET path.** Not "degrade gracefully without it" —
they do not look for it, do not call it, and cannot be affected by its absence. They are thin Python
wrappers over the stdlib checker in `tools/doc-audit/`.

This is not a nicety, it is the reason anything in this repository has ever been checked. The
project was authored in a Linux container with Python and Node and **no .NET SDK**. Not one line of
C# here has been through a compiler ([TD-1](../../docs/TECH_DEBT.md)). The documentation gate is the
only automated evidence this project currently possesses, so it was built to run in the worst-case
environment on purpose, and it does.

The practical consequence: **a documentation-only machine is a first-class way to work here.** You
can read, write, restructure, audit and map the entire project from a Chromebook. The full split of
what each path can and cannot do is in [dev-setup.md](../../docs/runbooks/dev-setup.md).

---

## Commands

| Command | What it does | Needs .NET? |
|---|---|---|
| `coord doctor` | Reports the toolchain honestly and says what this machine can do. | no |
| `coord audit` | Documentation + modularity drift check. `--quiet`, `--format json`, `--no-fail`, `--accuracy`, `--since REF`. | no |
| `coord map` | Regenerates the documentation index. `--check` verifies it is current. | no |
| `coord new-module <name>` | Scaffolds a module: README, docs, Core and Shell projects, tests project. Fills in around a docs-only module; never overwrites an existing file. | no |
| `coord test [NAME…]` | Runs the Core test suites over any discovered test project. `--filter`, `-c`. | **yes** |
| `coord build` | Compiles the C#. `--project`, `--core-only`, `-c`. | **yes** |
| `coord run` | Launches the Shell host. **Windows only.** | **yes** |
| `--dry-run` (global) | Prints what would run, or what would be created, without doing it. | — |

### `coord doctor`

Run it first on any machine, every time, and **read the output rather than skimming it**. Its whole
job is to turn the state of the toolchain from an assumption into a fact:

```text
Windows Coordinator — coord doctor

  python        3.11.15                     ok (3.11+)
  git           found                       /usr/bin/git
  platform      linux                       posix · /home/user/windows-coordinator

  dotnet SDK    not found                   MISSING — coord build / test / run are unavailable
  workloads     (skipped — no SDK)
  solution      not found                   expected — no .sln exists yet (TD-2)
  projects      3 under src/
  test projects 0 under tests/              expected until a module exists
  modules       none                        expected — no module has been created
  doc audit     present                     tools/doc-audit/audit.py
  doc map       present                     tools/doc-audit/genmap.py
```

It then prints what you *can* do here, what you *cannot*, and a note for each finding that has a
fix. Three of those findings deserve their explanation up front, because each one looks like a
failure and is not:

- **No .NET SDK** is a supported state, not an error. `doctor` exits zero on it.
- **No solution file** is deliberate. A `.sln` carries per-project GUIDs that could not be generated
  or verified where this repository was authored, and a file that looks authoritative but has never
  been parsed by anything is worse than an absent one ([TD-2](../../docs/TECH_DEBT.md)). Generating
  it is the first task in [NEXT.md](../../docs/NEXT.md).
- **A runtime-only `dotnet`** is reported distinctly from a missing one. That case is a genuine
  trap: the CLI is present and answers, so everything looks fine, and then every build fails for an
  unrelated-sounding reason.

`doctor` exits non-zero only for genuinely blocking problems — today that means a Python older than
3.11, or the doc-audit tooling missing from the checkout.

**If `doctor` is ever wrong about a machine, fix `doctor` before trusting anything downstream.** A
diagnostic that cannot be wrong carries no information; that is failure shape 1 in
[OPERATING_MODEL §7](../../docs/OPERATING_MODEL.md), sitting at the entry point of the whole
workflow.

### `coord audit`

The mechanical half of the audit protocol — frontmatter, links, `related:` targets, code references,
map freshness, ADR sequence, and the modularity boundary check. The judgement half (the six lenses)
is a human or LLM pass driven by [AUDIT.md](../../docs/AUDIT.md).

```sh
./coord audit                      # full report; exits non-zero on any ERROR
./coord audit --quiet              # summary and ERRORs only
./coord audit --format json        # machine-readable, for a hook or CI
./coord audit --no-fail            # report without gating — useful mid-edit
./coord audit --accuracy           # sweep for docs whose `audited` flag has gone stale
./coord audit --since origin/main  # closeout: changed docs must bump `updated`
```

`--since` is the branch-closeout mode described in [DOC_SPEC §6](../../docs/DOC_SPEC.md). Run it
before you consider a piece of work finished.

### `coord map`

Regenerates the documentation index, grouped tier → module. Generation is deterministic — a pure
function of the doc set, with no timestamps — which is what makes `--check` a meaningful gate rather
than a source of spurious diffs.

```sh
./coord map           # regenerate
./coord map --check   # exit non-zero if the index is stale (the CI shape)
```

### `coord new-module <name>`

Scaffolds a module and tells you what to do next. Names are lowercase, alphanumeric, hyphen
separated, and **plain and descriptive rather than codenames** — `zones`, `chrono`,
`window-restore` (ADR 0009). The name becomes the module's **permanent id**, referenced by settings
files and key bindings on machines you are not looking at, so the tool validates it and refuses
anything else.

```sh
./coord new-module zones
./coord --dry-run new-module zones   # see exactly what would be created
```

**A module may already exist as documentation, and that is normal here.**
[MODULE_SPEC](../../docs/MODULE_SPEC.md) says to write the spec before the code, and Zones was
designed in full while the module host that would load it did not exist. So when
`src/modules/<name>/` is already there but holds **no project file**, the scaffolder fills the code
in around it and reports which files it kept:

```text
> src/modules/zones exists and holds documentation only — adding the code projects around it,
  leaving every existing file untouched.
> kept existing src/modules/zones/README.md
> kept existing src/modules/zones/docs/ARCHITECTURE.md
```

It **never overwrites a file that already exists**, and it still refuses outright when a `.csproj`
is present — clobbering real code is the thing worth refusing, not clobbering an empty directory.
Both behaviours are covered by `tools/coord/tests/test_scaffold.py`, including a test that the
refusal still fires.

What it lays down:

```text
src/modules/zones/
├── README.md                         front door — capabilities, done-vs-TODO,
│                                     and a "Where to resume" section
├── Coordinator.Zones.Core/           net9.0 — ALL decision logic, no Windows types
│   ├── Coordinator.Zones.Core.csproj
│   ├── ZonesModule.cs
│   ├── ZonesCapabilities.cs
│   ├── ZonesTriggers.cs
│   └── ZonesSettings.cs
├── Coordinator.Zones.Shell/          net9.0-windows — thin adapter (delete if unused)
│   └── Coordinator.Zones.Shell.csproj
└── docs/
    ├── ARCHITECTURE.md
    └── NEXT.md

tests/
└── Coordinator.Zones.Core.Tests/     runs on any OS
    └── Coordinator.Zones.Core.Tests.csproj
```

Three deliberate properties of the scaffold:

- **It refuses to overwrite an existing module.** A scaffold that can silently clobber work is a
  scaffold nobody can trust, so re-running it on an existing name is an error you have to resolve
  yourself.
- **The `.cs` files are honest placeholders, not generated code.** Each carries the contract it is
  meant to satisfy as a comment and no implementation. A generated stub referencing types nobody has
  ever compiled would look like progress and be worse than a blank file.
- **Core and Shell are separate projects from the first commit.** That is the one part of the shape
  that is expensive to fix later: a single project with a Windows target defeats the boundary check
  silently, and the boundary check is the modularity teeth.
- **The `.Core` / `.Shell` suffix is on the directory and the assembly, never on the namespace.**
  `Coordinator.Zones.Core` and `Coordinator.Zones.Shell` are two project names over one namespace,
  `Coordinator.Zones` — so moving a type across the line is not a namespace change. The platform and
  pillar projects follow the same rule (`Coordinator.Platform.Core`, `Coordinator.Conduit.Core`,
  `Coordinator.Atlas.Core`), which is what makes the pair predictable from the module id alone.

The walkthrough that follows the scaffold is [add-a-module.md](../../docs/recipes/add-a-module.md);
the contract it must satisfy is [MODULE_SPEC.md](../../docs/MODULE_SPEC.md).

### `coord test`, `coord build`, `coord run`

```sh
./coord test                     # every discovered Core test project
./coord test zones               # only test projects whose name matches
./coord test --filter Category=Layout
./coord build                    # the whole solution
./coord build --core-only        # only the portable projects — the useful mode off Windows
./coord run                      # launch the Shell host (Windows only)
```

`--core-only` exists because on Linux or macOS the Windows-targeted projects cannot build at all
([TD-4](../../docs/TECH_DEBT.md)). That is the [Core/Shell split](../../docs/COORDINATOR.md) working
as designed, not a broken checkout, and building just the portable half is the productive thing to
do there.

`coord run` refuses immediately on a non-Windows machine with an explanation, rather than producing
a confusing restore error several seconds later. The Shell is the thin Windows adapter; there is no
cross-platform build of it and there is not meant to be (ADR 0003).

---

## What each command licenses you to claim

This table is the project's evidence standard in miniature, and it is the reason the tool exists in
the shape it does. The full statement is [OPERATING_MODEL §7](../../docs/OPERATING_MODEL.md).

| Command | Proves | Does **not** prove |
|---|---|---|
| `coord audit` | frontmatter, links, references, boundaries and ADR sequence are mechanically consistent | that any doc is *true* — that is the accuracy pass and the six lenses |
| `coord map --check` | the documentation index matches the doc set | anything about content |
| `coord build` | the C# compiles | that anything behaves |
| `coord test` | **Core logic** — geometry, schedule arithmetic, arbitration decisions, settings migration | window placement, hotkey capture, DPI behavior, the tray, the UI |
| `coord run` | the process starts on this machine | any specific behavior |
| a [manual-validation](../../docs/runbooks/manual-validation.md) scenario | what a human observed, on a named machine, on a date | anything not written down |

**A green `coord test` is never a claim about the desktop.** The Core/Shell split is what makes the
tests portable, and the same split is what makes them narrow.

### Failing loudly is a feature

Every command that cannot do its job exits non-zero with a message naming what is missing and how to
fix it. None of them prints anything that reads like success:

- `coord build` / `coord test` / `coord run` with no SDK → exit 2, with the install command.
- `coord build` with no solution → exit 2, with the `dotnet new sln` line and a pointer to NEXT.md.
- **`coord test` with zero discovered test projects → exit 2, not a pass.** A test run containing
  nothing would report success, and a check that cannot fail is worse than no check at all.
- `coord audit` / `coord map` with the checker missing → exit 2 with a plain explanation, not a
  Python traceback.

| Exit code | Meaning |
|---|---|
| `0` | the work happened and succeeded |
| `1` | the work ran and failed (a failing build, a failing suite, a stale map, an ERROR-level audit finding) |
| `2` | the work could not be attempted — missing tool, missing target, bad usage |

---

## Why Python, for a .NET project

It is a fair question, and the answer is bootstrapping. The tool's first job on any machine is
`coord doctor` — *is the toolchain here at all?* — and a tool written in the toolchain it is
checking cannot answer that. A .NET global tool would need the SDK to tell you the SDK is missing.

Everything else follows from the same root. Python is already present on essentially every
development machine; stdlib-only means there is nothing to install before the thing that tells you
what to install; and it is the reason the documentation gate survives an environment with no .NET at
all — which is not a hypothetical here, it is the environment the entire project was written in.

The cost is real and worth naming: two languages in one repository, and no compiler checking the
tool. It is accepted deliberately, and recorded in ADR 0010.

## Why `coord` and not `wc`

`wc` is the POSIX word-count command. A repository-local `wc` on `PATH` — or a shell alias, or muscle
memory in the wrong direction — is a collision with a decades-old tool that would produce confusing
behavior in both directions, on the exact machines where this project is developed. `coord` is four
characters, unambiguous, and reads as what it is. Also ADR 0010.

## Adding a subcommand

The tool is one file with a deliberately flat shape, so adding a command is three edits and no
plumbing:

1. **Write `cmd_<name>(args) -> int`.** Return an exit code; never swallow a failure. Use `die()`
   for anything that means the work cannot be attempted, `run_cmd()` for subprocesses.
2. **Register it in `build_parser()`** with `sub.add_parser(...)` and `set_defaults(func=cmd_<name>)`.
3. **Document it here**, in the command table and, if it is not self-evident, its own section.

Three house rules, each of which is load-bearing rather than stylistic:

- **Anything that shells out to `dotnet` must call `require_dotnet()` first**, and must never be
  reachable from `audit`, `map`, or `new-module`. The no-SDK guarantee is a property of the code
  path, not an intention, and it stays true only if nobody quietly crosses that line.
- **A command that cannot do its job exits non-zero and says why.** If you catch yourself writing a
  fallback that lets a command finish "successfully" without the outcome occurring, that is the
  failure shape the whole project is organized against.
- **Honor `--dry-run`.** A command that mutates anything — files, or the world through a subprocess
  — must be inspectable before it runs.

Keep it stdlib. A dependency here would break the property that makes the tool useful.

## Known unverified surface

**The `dotnet`-invoking subcommands have never executed their `dotnet` path — not once**
([TD-7](../../docs/TECH_DEBT.md)). No SDK existed where this was written, so the argument
construction, working-directory handling, exit-code propagation and error reporting of `coord test`,
`coord build` and `coord run` are unverified code sitting in the one tool every future session
reaches for first.

The first session on a Windows machine should therefore **deliberately break a build and confirm
that `coord build` exits non-zero and says so**, before trusting a green result from it. Verify the
failure path before the success path — a wrapper that mis-reports a failed build as a pass would be
a check that cannot fail, at the entry point of the entire workflow.

What *has* actually been executed, on Linux with Python 3.11 and no .NET: `doctor`, `--help`,
`map --check`, `audit`, `new-module` (including its dry-run, its name validation and its
overwrite refusal), and the refusal paths of `build`, `test` and `run`.
