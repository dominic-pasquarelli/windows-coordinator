---
title: Runbook — dev setup (zero to productive)
tier: meta
status: living
updated: 2026-08-08
audited: 2026-08-08
related:
  - CLAUDE.md
  - docs/ONBOARDING.md
  - docs/COORDINATOR.md
  - docs/NEXT.md
  - docs/TECH_DEBT.md
  - docs/OPERATING_MODEL.md
  - docs/runbooks/manual-validation.md
  - docs/runbooks/release-and-update.md
  - tools/coord/README.md
---

# Runbook — dev setup (zero to productive)

> How to take a machine from nothing to being able to work on this project. There are **two setup
> paths and they are very different sizes**: the documentation and tooling path needs Python and git
> and takes minutes on any operating system; the full build path needs Windows, the .NET 9 SDK, and
> the Windows App SDK.
>
> **One sentence:** if you are here to write docs, run the audit, or reason about Core logic, you
> need Python 3.11+ and git and nothing else — and that is a deliberate property of the
> architecture, not a convenience.
>
> **⚠ These steps have never been executed end to end.** They are derived from the documented
> requirements of the chosen toolchain, written in a Linux container with **no .NET SDK**. Nobody
> has yet installed this stack and watched anything compile. Treat every command below as a first
> draft. **Correcting it on first contact is a real deliverable** — fix what is wrong here, bump
> `updated`, and note anything surprising in the root [README.md](../../README.md) Pitfalls list.
> The orientation-level summary of the same material is [ONBOARDING §6–§7](../ONBOARDING.md); this
> runbook owns the detail and the troubleshooting.

---

## 1. Which path do you need?

| You want to… | You need | OS | Verified? |
|---|---|---|---|
| Write or audit documentation; run `coord audit` / `coord map`; read and reason about Core logic | **Python 3.11+**, **git** | any — Linux, macOS, Windows | **yes** — this is how the repository was authored |
| Build and unit-test **Core** projects (`net9.0`, zero Windows dependencies) | + **.NET 9 SDK** | any | no — never attempted |
| Build the **Shell adapters** and the WinUI host; run the app; validate anything a user can see | + **Windows 11**, **Windows App SDK / WinUI 3** | Windows only | no — never attempted |

The first row is not a consolation prize. The [Core/Shell split](../COORDINATOR.md) exists precisely
so that the thinking part of this project is portable, and today the documentation gate is **the only
gate this repository has ever passed**. A machine with no .NET on it can do a large share of the
useful work here.

---

## 2. The docs-only path (any OS, ~5 minutes)

```sh
git clone <this repo> && cd windows-coordinator
python3 --version          # need 3.11 or newer
./coord audit              # the documentation + boundary gate
./coord map --check        # is the generated doc index in sync?
```

On Windows, substitute `coord.cmd` for `./coord` everywhere in this document.

**There is nothing to install and nothing to bootstrap.** `tools/coord/coord.py`,
`tools/doc-audit/audit.py` and `tools/doc-audit/genmap.py` are **stdlib-only Python 3.11+** — no
`pip install`, no virtual environment, no lockfile, no vendored dependencies. That constraint was
chosen so that the first thing a cold session does cannot fail on a package manager, and it is
recorded in ADR 0010.

Three things work on this path, and they are worth knowing about before you decide you need the full
stack:

- **`coord audit`** is the ERROR gate that blocks a phase — broken links, missing frontmatter, ADR
  sequence gaps, and the **boundary** check that reads `using` directives, `[DllImport]` attributes
  and `ProjectReference` elements as text. That last one is a genuine modularity check on C# source
  without a compiler anywhere near it (its limits are **TD-3** in [TECH_DEBT.md](../TECH_DEBT.md)).
- **`coord map`** regenerates [MAP.md](../MAP.md), the traversable doc index.
- **`coord doctor`** tells you what the machine actually has. It is written to report a missing .NET
  SDK clearly rather than failing obscurely — it was written in exactly that situation.

What you **cannot** do on this path: `coord build`, `coord test`, `coord run`, and every claim that
depends on them. Say "not compiled"; do not round up.

---

## 3. The full path (Windows)

### 3.1 Windows 11

The Shell adapters target `net9.0-windows10.0.19041.0` and the design assumes modern behavior —
per-monitor-DPI-aware v2, current tray semantics, WinUI 3 Mica surfaces. Windows 10 at 19041 or later
is the nominal floor implied by the target framework, but **nothing has been tested on Windows 10**
and this project's target is Windows 11. If you get this working on Windows 10, that is a finding
worth writing down here.

### 3.2 The .NET 9 SDK

```powershell
winget install Microsoft.DotNet.SDK.9
dotnet --info                      # confirm an SDK in the 9.x band is listed
```

`dotnet --info` is the check that matters: it lists **installed SDKs** and **installed runtimes**
separately, and a machine with only the runtime will happily run `dotnet` and refuse to build. If you
already had .NET installed for something else, read the SDK list rather than the version banner.

### 3.3 The Windows App SDK / WinUI 3 workload

Two routes, and the choice is genuinely open because neither has been exercised here.

**Route A — Visual Studio 2022.** Install with the **.NET desktop development** workload and the
**Windows application development** workload (the latter is the one that brings the Windows App SDK
and the WinUI 3 project templates). This is the better-trodden path and gives you the XAML designer,
the hot-reload loop, and working project templates.

```powershell
winget install Microsoft.VisualStudio.2022.Community
# then add the two workloads via the Visual Studio Installer
```

**Route B — CLI only.** The Windows App SDK is delivered to a project as the `Microsoft.WindowsAppSDK`
NuGet package, restored from the project file, so in principle `dotnet build` is enough once the
project files reference it. **Whether a WinUI 3 project builds cleanly with the CLI alone, with no
Visual Studio components installed, is unverified here** and is one of the first questions this
project will answer in practice. If Route B works, say so here; if it needs a specific component,
name it here.

Two deployment facts that will matter the first time the app actually launches, both currently
**unmeasured** (**TD-10** in [TECH_DEBT.md](../TECH_DEBT.md)):

- An **unpackaged** WinUI 3 app needs the Windows App SDK runtime present on the machine, unless the
  app is built self-contained. Which of those two this project chooses is a real decision with a real
  cost, and it interacts directly with the delivery channel in
  [release-and-update.md](release-and-update.md).
- **Packaged versus unpackaged** changes tray behavior, install layout, update mechanics, and where
  settings land. Do not treat it as a build flag; it is an architectural choice that deserves an ADR
  when it is made.

### 3.4 Python 3.11+

Needed for `coord` itself, even on the full path — `coord` is the entry point that wraps `dotnet`.

```powershell
winget install Python.Python.3.12
python --version
```

Stdlib only. If you find yourself creating a virtual environment for this repository, something has
gone wrong — either the tooling grew a dependency it should not have, or you are in the wrong repo.

### 3.5 git

```powershell
winget install Git.Git
```

**Line endings:** this repository is authored on Linux and built on Windows. If you see whole files
appearing as modified with no visible change, that is a CRLF/LF normalization issue, not a real diff.
Decide it once (a `.gitattributes` entry or a `core.autocrlf` setting) and record the decision here —
it is exactly the kind of small friction that costs an evening if it is rediscovered every time.

---

## 4. First run

```sh
git clone <this repo> && cd windows-coordinator

./coord doctor       # ALWAYS first — what is installed, what is missing
./coord audit        # the gate that works today
./coord map --check
```

**`coord doctor` before anything else, every time on a new machine.** Its whole job is to make the
state of the toolchain a fact rather than an assumption, and it is the one command whose output you
should read rather than skim. The expected shape of its report:

```text
# ILLUSTRATIVE — the exact wording is whatever tools/coord/coord.py actually prints.
Python      3.12.x            ok
git         2.4x.x            ok
dotnet SDK  not found         MISSING — coord build / test / run are unavailable
workloads   (skipped — no SDK)
solution    not found         expected: no .sln exists yet (TD-2)
```

If `doctor` is wrong about the machine, **fix `doctor` before trusting anything downstream.** A
diagnostic that cannot be wrong carries no information — that is failure shape 1 in
[OPERATING_MODEL §7](../OPERATING_MODEL.md), sitting at the entry point of the whole workflow.
The `dotnet`-invoking subcommands of `coord` have never executed their `dotnet` path even once
(**TD-7**), so the first Windows session should deliberately break a build and confirm that
`coord build` exits non-zero and says so. **Verify the failure path before trusting the success path.**

---

## 5. There is no solution file yet

`dotnet build` at the repository root has nothing to point at: the repository contains project files
and no `.sln`. That is deliberate — a hand-written solution file carries per-project GUIDs that could
not be generated or verified in the authoring container, and a file that looks authoritative and has
never been parsed by anything is worse than an absent one (**TD-2**).

Generating it is **step 2 of the Active focus** in [NEXT.md](../NEXT.md), which owns the full
sequence and the expectations around it. The setup-shaped part is one line:

```powershell
dotnet new sln --name Coordinator
# then: dotnet sln add <each project under src/ and tests/>
```

Read [NEXT.md](../NEXT.md) before you run it. The point of that task is not the file; it is the first
checkable statement this codebase has ever produced, and it should be done as a session, not as a
detour.

---

## 6. Build, test, run

Once an SDK exists and the solution has been generated:

```sh
./coord build        # dotnet build
./coord test         # dotnet test over the Core test projects
./coord run          # launch the Shell app — Windows only
```

**What each one licenses you to claim:**

| Command | Proves | Does **not** prove |
|---|---|---|
| `coord build` | the C# compiles | that anything behaves |
| `coord test` | **Core logic** — geometry, scheduling, arbitration decisions, settings migration | window placement, hotkey capture, DPI behavior, the tray, the UI |
| `coord run` | the process starts on this machine | any specific behavior — that is what the next line is for |
| [manual-validation.md](manual-validation.md) | what a human actually observed, on a named machine, on a date | anything not written down |

That table is the project's evidence standard in miniature. The full statement, its three recurring
failure shapes, and the "prove the guard fails without the fix" rule are in
[OPERATING_MODEL §7](../OPERATING_MODEL.md).

---

## 7. Troubleshooting

Everything in this section is **predicted**, not observed. When you hit one of these for real, replace
the prediction with what actually happened and what actually fixed it — that is the difference between
a runbook and a guess.

| Symptom | Likely cause | What to try |
|---|---|---|
| `./coord: Permission denied` | the launcher lost its executable bit on clone | `chmod +x coord`, or invoke `python3 tools/coord/coord.py <cmd>` directly |
| `coord` runs but reports a Python syntax error | Python older than 3.11 is first on PATH | `python3 --version`; the tooling targets 3.11+ and uses modern syntax deliberately |
| `coord audit` reports ERRORs on a fresh clone | genuine drift, or a doc referencing a path that does not exist yet | read the finding; `code-ref` at ERROR is strict on purpose ([AUDIT §8](../AUDIT.md)) |
| `coord doctor` says no SDK but `dotnet` works | only the **runtime** is installed, not the SDK | `dotnet --info` and read the *SDKs* list; install `Microsoft.DotNet.SDK.9` |
| `coord build` fails with "no project or solution found" | the `.sln` has not been generated | §5 above, then [NEXT.md](../NEXT.md) |
| `coord test` reports zero test projects | the same missing solution, or the test projects are not referenced by it | `dotnet sln list`; add the projects under `tests/` |
| A Windows-targeted project will not restore on Linux/macOS | expected — `net9.0-windows10.0.19041.0` cannot build off Windows | build only the Core projects there; this is the split working as designed (**TD-4**) |
| The app builds but will not launch | the Windows App SDK runtime is missing, or packaged/unpackaged deployment is mismatched | §3.3; record what it actually needed — this is **TD-10**'s whole point |
| Windows warns before running your own freshly built binary | SmartScreen on an unsigned local build | expected today; the signing problem is genuinely unsolved — see [release-and-update.md §7](release-and-update.md) |
| Path-length errors during build or restore | deep `obj/` paths under a long clone path | clone nearer the drive root, or enable long paths |
| Every file shows as modified with no visible change | CRLF/LF normalization | §3.5 — decide it once and write the decision down here |

---

## 8. What you do not need

Say no to these until something forces the issue, and if something does force it, write down what:

- **A package manager for the tooling.** `coord` and the doc-audit checker are stdlib-only on purpose.
- **A virtual environment.** Same reason.
- **Node.** Nothing in this repository builds a web asset. If that changes, it needs an ADR first.
- **A container or VM for the docs work.** The docs-only path (§2) runs anywhere.
- **A Windows CI runner.** CI covers the Core projects only, and that gap is named and accepted
  (**TD-4**). Do not price a runner in the abstract — price it against a specific regression that
  escaped.

---

## 9. Before you stop

Whatever you learned setting this machine up is the most perishable knowledge in the project, and it
is knowledge nobody else has yet.

1. **Correct this document** to say what actually had to be done — including the steps that were
   unnecessary. Bump `updated`, and `audited` if you re-read the rest and it held.
2. **Correct [ONBOARDING §6](../ONBOARDING.md)** if the prerequisite table there is now wrong.
3. **Add a Pitfalls entry** to the root [README.md](../../README.md) for anything that cost you more
   than a few minutes and would cost the next person the same.
4. **Record the toolchain state** in [NEXT.md](../NEXT.md) — the machine, the SDK version, the date,
   and the honest outcome, including a failure. A recorded failure is worth more to the next session
   than a vague "in progress."

---

## See also

- [ONBOARDING.md](../ONBOARDING.md) — cold-start orientation; §6–§7 summarize this runbook.
- [tools/coord/README.md](../../tools/coord/README.md) — what each `coord` subcommand actually does.
- [manual-validation.md](manual-validation.md) — the only source of a claim about the desktop.
- [release-and-update.md](release-and-update.md) — how a build reaches a machine.
- [COORDINATOR.md §3](../COORDINATOR.md) — why Core builds anywhere and the Shell does not.
- [TECH_DEBT.md](../TECH_DEBT.md) — **TD-1** (nothing compiled), **TD-2** (no solution), **TD-7**
  (`coord`'s `dotnet` path unexercised), **TD-10** (the UI stack is unmeasured).
