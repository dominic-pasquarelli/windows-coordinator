# ADR 0010 — `coord` as the single developer entry point

Date: 2026-08-08
Status: Accepted

## Context

The recurring developer workflow for this project is: build, test, run the app, check the
documentation for drift, regenerate the documentation index, scaffold a new module, and — first of
all, after a long gap — find out whether the machine you are sitting at can do any of those things.

Left alone, that becomes a set of remembered `dotnet` invocations with their flags, plus a couple of
Python scripts invoked by path, plus a README paragraph that describes both and drifts from both. For
a project explicitly designed to be resumed cold after months, the very first command a returning
session types is the one that must not be stale — because it is the command that establishes whether
anything here still works.

There is also a hard constraint that this bootstrap discovered by living inside it, and it is the most
important input to this decision.

**The documentation tooling must run with no .NET installed.** This repository was authored in a Linux
container with Python 3.11 and Node and **no .NET SDK whatsoever**. Every check that actually ran
during the bootstrap — frontmatter validation, link resolution, `related:` resolution, the map
regeneration and its drift check, the ADR sequence check, the modularity boundary scan — ran because
those checks are stdlib Python operating on text. Had the checker been an MSBuild target, a
`dotnet tool`, or a Roslyn analyzer, **the entire documentation system would have shipped completely
unverified**, and this project's own evidence standard would have been violated in its first commit.
That is not a hypothetical justification constructed after the fact; it is the case the design was
built for, and it is the case that occurred.

## Decision

**`coord` is the single developer entry point**: `tools/coord/coord.py`, stdlib-only Python 3.11+,
launched by a `coord` shell wrapper on POSIX and a `coord.cmd` wrapper on Windows.

| Subcommand | Does | Needs .NET |
|---|---|---|
| `coord test` | runs the Core test projects | yes |
| `coord build` | builds the solution | yes |
| `coord run` | launches the Shell app (Windows only) | yes |
| `coord audit [--since REF] [--accuracy] [--format json]` | wraps `tools/doc-audit/audit.py` | **no** |
| `coord map [--check]` | wraps `tools/doc-audit/genmap.py` | **no** |
| `coord new-module <name>` | scaffolds a module from the template | **no** |
| `coord doctor` | reports the toolchain state honestly | **no** |

Three properties of the tool are decisions rather than implementation details.

**`coord audit` and `coord map` must work with no .NET installed.** This is a standing constraint on
the documentation pipeline, not a happy accident of the current implementation. Nothing in the doc
tooling may acquire a toolchain dependency, because documentation health has to be checkable in every
environment the project is ever worked on — including a container, a CI job that has restored nothing,
and a machine whose SDK is the thing being diagnosed.

**`coord doctor` must detect and clearly report a missing .NET SDK** — the exact state of the
container this repository was written in — and say so in a sentence, rather than failing obscurely
somewhere inside a `dotnet` invocation. A returning session's first question is "what is missing
here," and a tool that answers it with a stack trace costs an hour to the person least equipped to
spend one.

**Subcommands that shell out propagate exit codes faithfully.** A wrapper that reports success for a
failed build is the first failure shape from [OPERATING_MODEL.md](../OPERATING_MODEL.md) — a check
that cannot fail — installed at the entry point of the entire workflow, where every subsequent belief
depends on it. [TD-7](../TECH_DEBT.md) records that this path has **never executed**, and requires
that the *failure* path be verified before the success path is trusted: deliberately break the build,
and confirm `coord build` exits non-zero and says why.

### Why Python drives a .NET project

The instinct is to write the tooling in the project's own language — a `dotnet tool`, or MSBuild
targets that hang off the build. Three reasons not to, in increasing order of importance.

**No bootstrap step.** Python 3.11 is present on the machines this project is developed and audited
on, so the tooling runs from a clean clone with nothing installed and nothing restored. A `dotnet
tool` needs a restore, which needs an SDK — which is the very thing the tool might be reporting the
absence of.

**The documentation tooling must not depend on the code toolchain.** The bootstrap case above is the
proof, and the principle generalizes: a broken or missing SDK should never make the documentation
uncheckable, because that is exactly backwards — the documentation is what you fall back on when the
code is not working.

**Stdlib-only means it does not rot.** No package feed, no lockfile, no transitive dependency that
becomes unmaintained during a nine-month gap. A tool that still runs unchanged after that gap is worth
considerably more to this project than a tool that is idiomatic, and the operating model's
resume-fidelity argument applies to tooling at least as strongly as it applies to prose.

### Why `coord`, not `wc`

`wc` is the POSIX word-count command. It is present in every Linux and macOS shell, and in every Git
Bash and WSL environment on a Windows machine — which is to say, in the environments this project is
partly developed in. Shadowing it would mean that a stray `wc -l somefile` typed inside this
repository runs either the project tool or the real one depending on `PATH` order, producing a wrong
answer with no error. That is a twenty-minute confusion that recurs forever, bought in exchange for
saving three keystrokes.

`coord` is short, unambiguous, pronounceable, and matches the product name, so the entry point does
not have to be remembered as a separate fact from the project itself.

## Consequences

**Two languages live in this repository.** Accepted, because they occupy disjoint layers with no
overlap: Python never ships to a user and never touches product behavior; C# never runs an audit. The
cost is that a contributor needs both, and [ONBOARDING.md](../ONBOARDING.md) says so.

**`coord` is the highest-leverage code in the project by a wide margin.** It is the first thing every
session touches and the thing every claim about build or test status flows through, so its own failure
modes matter more than most product code's. That is why TD-7 demands the failure path be exercised
explicitly rather than inferred from a successful run.

**The wrapper must stay thin.** Argument passthrough to `dotnet` (test filters, configuration,
verbosity) will be wanted quickly, and the temptation will be to grow opinions about each. The tool's
job is to remove the tax of remembering commands, not to become a build system — a `coord` that starts
making build decisions is a second, undocumented build configuration.

**Everything that shells out to `dotnet` is unexecuted code today.** `coord test`, `coord build` and
`coord run` have never run their `dotnet` path even once, because no SDK was present
([TD-1](../TECH_DEBT.md), [TD-7](../TECH_DEBT.md)). Their argument construction, working-directory
handling, exit-code propagation and error reporting are all unverified. The pure-Python subcommands
were actually executed during the bootstrap, and their results are real; the distinction between those
two statements is exactly the distinction this project's evidence standard exists to preserve.

## Alternatives considered

**Raw `dotnet` plus a README listing the commands.** Rejected on drift. The commands and the README
diverge, and a cold reader's very first action — the one that has to succeed to establish any
confidence at all — becomes a copy-paste of a possibly-stale line. It also leaves the documentation
tooling with no home, so it would be invoked by path and forgotten.

**A `dotnet tool` or MSBuild targets.** The idiomatic choice, and the one that would have made this
repository unverifiable: with the doc checker behind the SDK, nothing in the bootstrap could have been
checked at all. Rejected on the decoupling argument above. Worth noting that the *code-facing* half of
the tooling could reasonably live there someday — a Roslyn-based boundary analyzer is exactly the
pay-down [TD-3](../TECH_DEBT.md) describes — but it would be an addition alongside the text checks,
never a replacement for their independence.

**Shell scripts, `.sh` and `.cmd` in pairs.** Rejected on duplication: two implementations of every
command, drifting quietly, with the difference only discovered on whichever platform is used less. And
the real logic — parsing frontmatter, resolving links across a tree, scanning source text for boundary
violations — is not shell-shaped in any case.

**A task runner: `make`, `just`, Nuke, or Cake.** `make` and `just` add an install step and are
second-class citizens on Windows, which is the primary development platform for a Windows utility.
Nuke and Cake are .NET-based, which reintroduces precisely the toolchain dependency this decision
exists to eliminate. Rejected on both counts.

**Node, since it is also present in the authoring environment.** Rejected: it would need a manifest
file and an installed dependency tree, which is a bootstrap step and a rot surface, and it
offers nothing over Python's standard library for text processing and subprocess management. Its
presence here is incidental, and the tooling should not depend on an incidental fact.
