#!/usr/bin/env python3
"""coord — the single developer entry point for Windows Coordinator.

One command surface for everything you do to this repository: build it, test it, run it, check the
documentation, and scaffold a new module. Its whole job is to remove the friction the owner kept
hitting — *which command, which project, which nuance* — so that "what do I run?" has exactly one
answer and that answer is the same on Windows and on Linux.

Two properties are deliberate and load-bearing:

1. **`coord audit` and `coord map` never touch the .NET path.** They are pure Python wrappers over
   `tools/doc-audit/`, so the documentation gate works on a machine with no SDK at all. That is not
   hypothetical: this repository was authored in a Linux container with Python and Node and **no
   .NET SDK**, and the doc gate is the only check that has ever actually run here.

2. **A command that cannot do its job fails loudly.** Missing `dotnet`, missing solution, zero test
   projects — each exits non-zero with a message naming what is missing and how to fix it. Nothing
   prints anything that reads like success unless the work happened. That is the project's evidence
   standard (docs/OPERATING_MODEL.md §7) applied to its own tooling: a successful `coord` command
   must mean the claimed outcome occurred.

Stdlib only, Python 3.11+. No pip install, no virtual environment. If you find yourself creating one
for this repository, something has gone wrong.

Honesty note carried in the code because it is easy to forget, updated 2026-08-08 after the first
CI run at 7aef6ff:

  * `coord test` HAS executed its dotnet path — GitHub Actions ran it on Ubuntu, where it discovered
    both Core test projects, ran each individually, and reported 45 passing tests.
  * `coord build` and `coord run` still have **not** executed their dotnet path. CI builds projects
    with `dotnet build` directly rather than through this tool, and nothing has ever launched the
    Shell (there is no Shell project). Their argument construction and exit-code propagation on the
    SUCCESS path remain unverified (TD-7).
  * The FAILURE path of all three is verified: with no SDK present each exits 2 with a message that
    names what is missing, which was checked by hand in the authoring container.

The first Windows session should still deliberately break a build and confirm `coord build` exits
non-zero and says so, before trusting its success path.

Usage:
  coord test [NAME ...] [--filter EXPR] [-c CONFIG]
  coord build [--project PATH] [--core-only] [-c CONFIG]
  coord run [--project PATH] [-c CONFIG]
  coord audit [--since REF] [--accuracy] [--format json] [--quiet] [--no-fail]
  coord map [--check]
  coord new-module <name>
  coord doctor
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

MIN_PY = (3, 11)
if sys.version_info < MIN_PY:  # pragma: no cover - the interpreter that runs this may be old
    sys.stderr.write(
        f"coord: needs Python {MIN_PY[0]}.{MIN_PY[1]}+, you have {sys.version.split()[0]}.\n"
        "The tooling is stdlib-only and targets 3.11+ deliberately (docs/runbooks/dev-setup.md).\n")
    raise SystemExit(2)

# --- paths -------------------------------------------------------------------------------------
TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent.parent                 # tools/coord/ -> repo root
DOC_AUDIT_DIR = REPO_ROOT / "tools" / "doc-audit"
AUDIT_SCRIPT = DOC_AUDIT_DIR / "audit.py"
GENMAP_SCRIPT = DOC_AUDIT_DIR / "genmap.py"
SRC_DIR = REPO_ROOT / "src"
MODULES_DIR = SRC_DIR / "modules"
SHELL_DIR = SRC_DIR / "shell"
TESTS_DIR = REPO_ROOT / "tests"

MODULE_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

# Exit codes, so callers (and CI) can tell the two failure kinds apart.
EXIT_OK = 0
EXIT_FAILED = 1        # the work ran and failed
EXIT_UNAVAILABLE = 2   # the work could not be attempted — missing tool, missing target, bad usage

# --- output ------------------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _USE_COLOR else s


def info(msg: str) -> None:
    print(f"{_c('36', '>')} {msg}")


def ok(msg: str) -> None:
    print(f"{_c('32', 'ok')} {msg}")


def warn(msg: str) -> None:
    print(f"{_c('33', '!')} {msg}", file=sys.stderr)


def die(msg: str, code: int = EXIT_UNAVAILABLE) -> "None":
    """Fail loudly. Every caller of this is a place where continuing would produce a result that
    reads like success without the outcome having occurred."""
    print(f"{_c('31', 'error')} {msg}", file=sys.stderr)
    sys.exit(code)


def _make_stdio_utf8() -> None:
    """Windows' legacy console defaults to cp1252, which cannot encode the characters this tool
    prints (→ · ✓). A bare print then dies with UnicodeEncodeError — and it would die in the error
    path, which is the worst possible place for a crash. errors='replace' degrades to readable text
    instead. No-op where reconfigure is unavailable."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def run_cmd(cmd: list[str], *, cwd: Path | None = None, dry: bool = False) -> int:
    """Run a subprocess, echoing it first. Returns its exit code — never swallows a failure."""
    printable = " ".join(cmd)
    if dry:
        print(f"(dry-run) {printable}")
        return EXIT_OK
    info(printable)
    try:
        return subprocess.run(cmd, cwd=str(cwd or REPO_ROOT)).returncode
    except FileNotFoundError:
        die(f"could not execute {cmd[0]!r} — it is not on PATH.")
        return EXIT_UNAVAILABLE  # unreachable; keeps type-checkers happy


# --- the .NET toolchain (only the dotnet-shaped subcommands may call these) ---------------------
def find_dotnet() -> str | None:
    """Locate the .NET CLI. On PATH first, then the well-known per-OS install locations, because a
    Windows install occasionally lands outside the PATH of a shell that was already open."""
    onpath = shutil.which("dotnet")
    if onpath:
        return onpath
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "dotnet" / "dotnet.exe",
        Path.home() / ".dotnet" / "dotnet.exe",
        Path.home() / ".dotnet" / "dotnet",
        Path("/usr/share/dotnet/dotnet"),
        Path("/usr/lib/dotnet/dotnet"),
        Path("/usr/local/share/dotnet/dotnet"),
    ]
    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except OSError:
            continue
    return None


def dotnet_sdks(dotnet: str) -> list[str]:
    """The installed SDK versions, or [] — including the runtime-only case, where `dotnet` exists
    and answers but lists no SDKs. That case is a real trap: the command works, so it looks fine,
    and then every build fails with something unrelated-sounding."""
    try:
        p = subprocess.run([dotnet, "--list-sdks"], capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    if p.returncode != 0:
        return []
    return [ln.split(" ", 1)[0] for ln in p.stdout.splitlines() if ln.strip()]


DOTNET_MISSING_HELP = (
    "the .NET SDK is not installed on this machine (looked on PATH and in the standard install "
    "locations).\n"
    "         This subcommand shells out to `dotnet` and cannot do its job without it.\n"
    "         Fix:  winget install Microsoft.DotNet.SDK.9      (Windows)\n"
    "               https://dotnet.microsoft.com/download      (other platforms)\n"
    "         Then: coord doctor\n"
    "         Working without an SDK is expected and supported — `coord audit` and `coord map` are\n"
    "         pure Python and run here today. See docs/runbooks/dev-setup.md."
)


def require_dotnet() -> str:
    dotnet = find_dotnet()
    if not dotnet:
        die(DOTNET_MISSING_HELP)
    sdks = dotnet_sdks(dotnet)  # type: ignore[arg-type]
    if not sdks:
        die(f"found the .NET CLI at {dotnet}, but it lists no SDKs — this is a **runtime-only** "
            "install.\n"
            "         Building and testing need the SDK. Run `dotnet --info` and read the *SDKs* "
            "list.\n"
            "         Fix:  winget install Microsoft.DotNet.SDK.9")
    return dotnet  # type: ignore[return-value]


# --- repository discovery ----------------------------------------------------------------------
def find_solution() -> Path | None:
    """The solution file, if one exists. It does not today: a hand-written .sln carries per-project
    GUIDs that could not be generated or verified in the authoring container, so generating it on a
    Windows machine is the first task in docs/NEXT.md (TD-2)."""
    for pattern in ("*.sln", "*.slnx"):
        hits = sorted(REPO_ROOT.glob(pattern))
        if hits:
            return hits[0]
    return None


NO_SOLUTION_HELP = (
    "there is no solution file in this repository, so `dotnet` has nothing to point at.\n"
    "         This is a known, deliberate state, not a corrupt checkout: a .sln carries per-project\n"
    "         GUIDs that could not be verified where this repository was authored (TD-2).\n"
    "         Fix, on a Windows machine with the SDK:\n"
    "             dotnet new sln --name Coordinator\n"
    "             dotnet sln add <each project under src/ and tests/>\n"
    "         docs/NEXT.md owns that task and the expectations around it — read it first."
)


def find_projects(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.csproj") if "obj" not in p.parts and "bin" not in p.parts)


def find_test_projects() -> list[Path]:
    return find_projects(TESTS_DIR)


def targets_windows(proj: Path) -> bool:
    """True if a project file names a Windows target framework. Text inspection, not evaluation —
    the same shape the boundary check uses, for the same reason: nothing here has ever been through
    MSBuild, so the file's text is the only fact available."""
    try:
        text = proj.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "-windows" in text


def find_shell_project() -> Path | None:
    projects = find_projects(SHELL_DIR)
    if not projects:
        return None
    for p in projects:
        if p.stem.lower() in ("coordinator.shell", "coordinator.shell.app"):
            return p
    return projects[0]


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


# --- commands: the .NET side -------------------------------------------------------------------
def cmd_test(args) -> int:
    """Run the Core test suites. These are plain net9.0 projects and run on any operating system —
    that is the payoff of the Core/Shell split (ADR 0003).

    What a green run licenses you to claim is narrow and worth re-reading: Core logic — geometry,
    schedule arithmetic, arbitration decisions, settings migration. It says nothing whatsoever about
    window placement, hotkey capture, DPI behavior, the tray, or the UI. Those live in
    docs/runbooks/manual-validation.md and are checked by a human, on a named machine, on a date.
    """
    dotnet = require_dotnet()
    projects = find_test_projects()
    names = list(getattr(args, "name", None) or [])
    if names:
        wanted = [n.lower() for n in names]
        projects = [p for p in projects if any(w in p.stem.lower() for w in wanted)]
        if not projects:
            die(f"no test project under tests/ matches {', '.join(names)}. "
                f"Known: {', '.join(p.stem for p in find_test_projects()) or '(none)'}")

    if not projects:
        die("found no test projects under tests/ — so there is nothing to run, and a 'pass' here\n"
            "         would be a check that cannot fail.\n"
            "         Either no module has been created yet (expected today — no module exists), or\n"
            "         your test project is not under tests/. Add one with `coord new-module <name>`,\n"
            "         or see docs/MODULE_SPEC.md §6.")

    extra: list[str] = []
    if getattr(args, "filter", None):
        extra += ["--filter", args.filter]
    extra += ["-c", args.configuration]

    # ALWAYS run the discovered test projects individually — never `dotnet test <solution>`, even
    # when a solution exists.
    #
    # The solution is the whole product: once the Shell adapters land it contains
    # `net9.0-windows10.0.19041.0` projects, and handing it to `dotnet test` would drag those into
    # the run. On the Linux CI runner that fails outright; on a Windows machine it quietly widens
    # what a green `coord test` means, which is worse — the entire value of this command is that it
    # is a claim about PORTABLE Core logic and nothing else (ADR 0003).
    #
    # Discovery under tests/ is therefore the definition of the Core-test set, and it stays
    # independent of whatever the solution accumulates. Reported by review 2026-08-08.
    failures: list[str] = []
    for proj in projects:
        info(f"testing {rel(proj)}")
        rc = run_cmd([dotnet, "test", str(proj), *extra], dry=args.dry_run)
        if rc != EXIT_OK:
            failures.append(rel(proj))
    if failures:
        warn(f"{len(failures)} of {len(projects)} test project(s) FAILED: {', '.join(failures)}")
        return EXIT_FAILED
    if not args.dry_run:
        ok(f"{len(projects)} test project(s) passed — Core logic only "
           "(see docs/runbooks/manual-validation.md for everything this does not cover).")
    return EXIT_OK


def cmd_build(args) -> int:
    """Compile the C#. Nothing more: a green build proves the code compiles and proves nothing about
    behavior.

    On a non-Windows machine the Windows-targeted projects cannot build at all (TD-4) — that is the
    split working as designed, not a broken checkout. `--core-only` builds just the portable
    projects, which is the useful thing to do on Linux or macOS.
    """
    dotnet = require_dotnet()
    extra = ["-c", args.configuration]

    if getattr(args, "project", None):
        proj = Path(args.project)
        if not proj.is_absolute():
            proj = REPO_ROOT / proj
        if not proj.exists():
            die(f"no such project: {args.project}")
        return _build_targets(dotnet, [proj], extra, args)

    if getattr(args, "core_only", False):
        projects = [p for p in find_projects(SRC_DIR) + find_test_projects()
                    if not targets_windows(p)]
        if not projects:
            die("found no portable (non-Windows-targeted) projects under src/ or tests/ to build.")
        info(f"building {len(projects)} portable project(s) — Windows-targeted projects skipped")
        return _build_targets(dotnet, projects, extra, args)

    sln = find_solution()
    if not sln:
        die(NO_SOLUTION_HELP)
    if sys.platform != "win32":
        warn("building the whole solution off Windows: any net9.0-windows project in it will fail "
             "to restore (TD-4). Use `coord build --core-only` for the portable projects.")
    info(f"building {rel(sln)}")
    rc = run_cmd([dotnet, "build", str(sln), *extra], dry=args.dry_run)
    if rc != EXIT_OK:
        warn(f"dotnet build failed (exit {rc}) — nothing was produced.")
    return rc


def _build_targets(dotnet: str, projects: list[Path], extra: list[str], args) -> int:
    failures: list[str] = []
    for proj in projects:
        rc = run_cmd([dotnet, "build", str(proj), *extra], dry=args.dry_run)
        if rc != EXIT_OK:
            failures.append(rel(proj))
    if failures:
        warn(f"{len(failures)} of {len(projects)} project(s) FAILED to build: {', '.join(failures)}")
        return EXIT_FAILED
    if not args.dry_run:
        ok(f"{len(projects)} project(s) compiled — this proves compilation, nothing else.")
    return EXIT_OK


def cmd_run(args) -> int:
    """Launch the Shell host — the tray-resident WinUI app.

    Windows-only, and not apologetically so: the Shell is the thin Windows adapter over portable
    Core logic (ADR 0003). There is no cross-platform build of it and there is not meant to be. On
    any other OS this refuses immediately rather than producing a confusing MSBuild error.
    """
    if sys.platform != "win32":
        die("`coord run` launches the WinUI Shell host, which only exists on Windows.\n"
            f"         This machine reports platform '{sys.platform}'.\n"
            "         That is the Core/Shell split working as designed (ADR 0003), not a missing\n"
            "         feature: the Windows adapter has no portable build.\n"
            "         What you CAN do here: `coord test` (Core logic), `coord audit`, `coord map`.\n"
            "         Anything about placement, hotkeys, DPI or the tray needs a real Windows\n"
            "         desktop and docs/runbooks/manual-validation.md.")
    dotnet = require_dotnet()
    proj = Path(args.project) if getattr(args, "project", None) else find_shell_project()
    if proj is not None and not proj.is_absolute():
        proj = REPO_ROOT / proj
    if proj is None or not proj.exists():
        die("could not find a Shell project to run under src/shell/.\n"
            "         The WinUI host has not been created yet — there is no Shell project to run.\n"
            "         The Core projects compile (CI, 7aef6ff), but nothing here has a UI or a\n"
            "         process. See src/shell/README.md and docs/NEXT.md.\n"
            "         Point at one explicitly with `coord run --project <path.csproj>`.")
    info(f"launching {rel(proj)}")
    rc = run_cmd([dotnet, "run", "--project", str(proj), "-c", args.configuration],
                 dry=args.dry_run)
    if rc != EXIT_OK:
        warn(f"the app exited non-zero ({rc}).")
    return rc


# --- commands: the pure-Python side (NO dotnet anywhere below this line) ------------------------
def _require_doc_tool(script: Path, what: str) -> None:
    """The doc tooling is the only gate that works without an SDK, so its absence is reported as a
    plain missing file rather than as a traceback from a failed exec."""
    if not script.exists():
        die(f"the {what} is not present at {rel(script)}.\n"
            "         `coord audit` and `coord map` wrap the stdlib checker in tools/doc-audit/.\n"
            "         If this is a fresh or partial checkout, that directory did not come with it —\n"
            "         restore it from git. See docs/AUDIT.md and tools/doc-audit/README.md.")


def cmd_audit(args) -> int:
    """Run the mechanical drift checker: frontmatter, links, `related:` targets, code references,
    map freshness, ADR sequence, and the modularity boundary check.

    Deliberately pure Python and deliberately independent of the .NET toolchain — it is the gate
    that works on a machine with no SDK, which is the only reason anything in this repository has
    ever been checked. The judgement half of the audit (the six lenses) is docs/AUDIT.md.
    """
    _require_doc_tool(AUDIT_SCRIPT, "documentation audit script")
    cmd = [sys.executable, str(AUDIT_SCRIPT)]
    if getattr(args, "quiet", False):
        cmd.append("--quiet")
    if getattr(args, "format", None):
        cmd += ["--format", args.format]
    if getattr(args, "no_fail", False):
        cmd.append("--no-fail")
    if getattr(args, "accuracy", False):
        cmd.append("--accuracy")
    if getattr(args, "since", None):
        cmd += ["--since", args.since]
    if args.dry_run:
        print("(dry-run) " + " ".join(cmd))
        return EXIT_OK
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def cmd_map(args) -> int:
    """Regenerate docs/MAP.md, the traversable documentation index, or `--check` that it is current.

    Generation is deterministic — a pure function of the doc set, with no timestamps — so `--check`
    is a meaningful gate rather than a source of spurious diffs (docs/DOC_SPEC.md §5).
    """
    _require_doc_tool(GENMAP_SCRIPT, "documentation map generator")
    cmd = [sys.executable, str(GENMAP_SCRIPT)]
    if getattr(args, "check", False):
        cmd.append("--check")
    if args.dry_run:
        print("(dry-run) " + " ".join(cmd))
        return EXIT_OK
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


# --- commands: scaffolding ---------------------------------------------------------------------
def pascal(name: str) -> str:
    """zones -> Zones · window-restore -> WindowRestore. The module id stays lowercase forever; the
    PascalCase form is only ever a C# identifier."""
    return "".join(part.capitalize() for part in name.split("-") if part)


def _module_readme(name: str, cls: str, today: str) -> str:
    return f"""---
title: {cls} (module)
tier: module
status: living
updated: {today}
module: {name}
related:
  - docs/MODULE_SPEC.md
  - docs/recipes/add-a-module.md
  - docs/NEXT.md
---

# {cls}

> **What this module does — replace this line with one honest sentence.** Not what it will do
> eventually; what it does today.
>
> **One sentence:** scaffolded on {today} by `coord new-module {name}` and not yet implemented.

## Status

Nothing here has been compiled or run. Replace this table as reality changes — a stale status table
is the most invisible kind of drift there is (docs/AUDIT.md, Lens A).

| | State |
|---|---|
| Core logic | **TODO** — scaffold only |
| Core tests | **TODO** |
| Shell adapter | **TODO** |
| Capabilities declared | **TODO** |
| Trigger intents declared | **TODO** |
| Settings + migration | **TODO** |
| Validation scenario in the manual-validation runbook | **TODO** |

## Capabilities

List every capability this module publishes, with its **permanent id**. Ids are referenced by
settings files and user bindings on machines you are not looking at: add freely, never rename, never
reuse. Labels are free; ids are forever.

| Capability id | Kind | What it controls |
|---|---|---|
| `{name}.example` | (Action / Setting / Reading) | — |

## Trigger intents

What this module asks Conduit to wake it for, and what it does when an intent is **refused** — a
refusal is a normal outcome, not an error, and the module must stay useful without it.

| Intent id | Kind | Behavior if refused |
|---|---|---|
| `{name}.example.chord` | (chord / window event / schedule / tray) | — |

## Where to resume

**This section is the point of the whole file.** Name a *specific next action*, not a topic. The
difference between "continue work on layouts" and "`LayoutMath.Resolve` handles one monitor; the
multi-monitor path is stubbed at the work-area union — decide whether a zone may span monitors
before writing it" is an evening of re-derivation, every single time you come back.

Right now the honest anchor is:

> Nothing is implemented. Start at step 2 of the add-a-module recipe — write the Core logic and its
> tests before any Windows code exists — and delete this paragraph when it stops being true.

Read next: [MODULE_SPEC.md](../../../docs/MODULE_SPEC.md) for the contract, and
[add-a-module.md](../../../docs/recipes/add-a-module.md) for the walkthrough.
"""


def _module_architecture(name: str, cls: str, today: str) -> str:
    return f"""---
title: {cls} — internal architecture
tier: module
status: living
updated: {today}
module: {name}
related:
  - docs/MODULE_SPEC.md
  - src/modules/{name}/README.md
---

# {cls} — internal architecture

> How this module is built on the inside: its decomposition, the shape of its state, and the
> non-obvious choices. Brief is fine — three honest paragraphs beat an empty template.
>
> **One sentence:** placeholder written by the scaffold; replace it with the real design.

## The decomposition

What lives in Core, what lives in the Shell adapter, and why the line falls where it does. The rule
is not stylistic: every decision left in the adapter is a decision no test will ever see.

## State

What this module holds between dispatches, what is derived, and what is recomputed. Anything
expensive belongs at load or settings-save, never in a hook callback or a drag loop — *resolve once,
execute cheap*.

## Non-obvious choices

Anything a reader would otherwise re-litigate. If a choice has real trade-offs, it belongs in the
unified decision log at `docs/decisions/` rather than here, and this section links to it.
"""


def _module_next(name: str, cls: str, today: str) -> str:
    return f"""---
title: {cls} — NEXT
tier: module
status: living
updated: {today}
module: {name}
related:
  - docs/NEXT.md
  - src/modules/{name}/README.md
---

# {cls} — NEXT

> The task-granular resume anchor for this module. The README's "Where to resume" says where you
> are; this page says what to do next, in order.
>
> **One sentence:** scaffolded {today}; nothing implemented.

## Active

1. Write the pure Core logic this module exists for, and its tests, before any Windows code exists.
2. Declare capabilities and trigger intents with permanent ids.
3. Add a validation scenario to `docs/runbooks/manual-validation.md`.

## Parked

Nothing yet. When you defer something, give it a recall hook here or it cannot resurface.
"""


CORE_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">

  <!-- Core: portable decision logic. net9.0 with NO Windows dependency, so it builds and unit-tests
       on any operating system (ADR 0003). Nothing Windows-shaped may enter this project: no
       platform-invoke attributes, no Windows or WinUI namespaces, no reference to a Shell project.
       The boundary check reads those as text and fails the gate.
       Shared properties (nullable, LangVersion, warnings-as-errors) come from Directory.Build.props.
       NOTE: this template's output is checked by tools/coord/tests/test_scaffold.py, which
       scaffolds a module and asserts every ProjectReference it emits resolves. It has not been
       compiled — no scaffolded module has ever been built. -->

  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
  </PropertyGroup>

  <ItemGroup>
    <ProjectReference Include="..\\..\\..\\platform\\Coordinator.Platform.Core\\Coordinator.Platform.Core.csproj" />
  </ItemGroup>

</Project>
"""


SHELL_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">

  <!-- Shell adapter: the thin Windows surface. Collect facts, hand them to Core, carry out Core's
       answer — it decides nothing. If you are writing an `if` here that is not a null check or a
       Win32 error check, that decision belongs in Core.
       DELETE THIS PROJECT if the module needs no Windows surface of its own; plenty of useful
       behavior does not, and an empty project is a claim.
       Add the Windows App SDK package reference only when this module actually renders its own UI —
       the generic settings page comes free from declared capabilities.
       NOTE: this template's output is checked by tools/coord/tests/test_scaffold.py, which
       scaffolds a module and asserts every ProjectReference it emits resolves. It has not been
       compiled — no scaffolded module has ever been built. -->

  <PropertyGroup>
    <TargetFramework>net9.0-windows10.0.19041.0</TargetFramework>
    <SupportedOSPlatformVersion>10.0.17763.0</SupportedOSPlatformVersion>
  </PropertyGroup>

  <ItemGroup>
    <ProjectReference Include="..\\Coordinator.{cls}.Core\\Coordinator.{cls}.Core.csproj" />
  </ItemGroup>

</Project>
"""


TESTS_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">

  <!-- Core tests: portable, run on any operating system, and the only automated evidence this
       project has. A green run proves Core logic — geometry, schedules, arbitration decisions,
       settings migration — and proves nothing about window placement, hotkeys, DPI or the UI.
       NOTE: the test framework below is the scaffold's default and has NEVER been restored. The
       choice is not yet recorded in an ADR; if you change it, change the scaffold too and record
       the decision. Package versions are unverified. -->

  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <IsPackable>false</IsPackable>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.11.1" />
    <PackageReference Include="xunit" Version="2.9.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\\..\\src\\modules\\{name}\\Coordinator.{cls}.Core\\Coordinator.{cls}.Core.csproj" />
  </ItemGroup>

</Project>
"""


def _cs_placeholder(cls: str, name: str, kind: str, body: str) -> str:
    wrapped = "\n".join(f"// {line}" for line in textwrap.wrap(body, width=94))
    return f"""// {cls}{kind} — SCAFFOLD PLACEHOLDER, intentionally empty of code.
//
// This file exists so the module's shape is right from the first commit; it deliberately contains
// no implementation, because a generated stub that references types nobody has compiled is worse
// than an honest blank. Nothing in this repository has ever been through a C# compiler.
//
{wrapped}
//
// Contract: docs/MODULE_SPEC.md · Walkthrough: docs/recipes/add-a-module.md
// Module id: "{name}" — permanent. Capability and trigger ids are permanent too.

namespace Coordinator.{cls};
"""


def cmd_new_module(args) -> int:
    """Scaffold a module: one directory, the two projects, the tests project, and the docs.

    Why a scaffold rather than copying a sibling: the two things that are expensive to fix later are
    both structural. Core and Shell must be separate *projects* (a single project with a Windows
    target defeats the boundary check silently), and the docs must exist before there is anything to
    document, or they never get written at all.
    """
    name = args.name
    if not MODULE_NAME_RE.match(name):
        die(f"invalid module name {name!r}.\n"
            "         Module names are lowercase, alphanumeric, hyphen-separated: `zones`,\n"
            "         `chrono`, `window-restore`. They are plain and descriptive, not codenames\n"
            "         (ADR 0009), and the name becomes the module's PERMANENT id — settings files\n"
            "         and user bindings on other people's machines reference it.")
    cls = pascal(name)
    today = date.today().isoformat()

    mod_dir = MODULES_DIR / name
    core_dir = mod_dir / f"Coordinator.{cls}.Core"
    shell_dir = mod_dir / f"Coordinator.{cls}.Shell"
    docs_dir = mod_dir / "docs"
    test_dir = TESTS_DIR / f"Coordinator.{cls}.Core.Tests"

    # A module in this project starts as a DESIGN before it starts as code — docs/MODULE_SPEC.md
    # says to write the spec first, and Zones was specified in full while the module host that would
    # load it did not exist. So a directory holding only documentation is not "an existing module"
    # to be protected from; it is the normal state of a module the day before its first line of C#.
    #
    # The thing actually worth refusing is clobbering CODE. Refuse when any project file exists;
    # otherwise fill in the missing pieces and leave every existing file untouched.
    existing_projects = sorted(mod_dir.rglob("*.csproj")) if mod_dir.exists() else []
    if existing_projects:
        die(f"{rel(mod_dir)} already contains {len(existing_projects)} project file(s) — refusing "
            "to overwrite an existing module.\n"
            f"         First: {rel(existing_projects[0])}\n"
            "         If you meant to start over, move or delete it yourself; a scaffold that can\n"
            "         silently clobber work is a scaffold nobody can trust.")
    if test_dir.exists() and any(test_dir.rglob("*.csproj")):
        die(f"{rel(test_dir)} already contains a project file — refusing to overwrite it.")
    if mod_dir.exists():
        info(f"{rel(mod_dir)} exists and holds documentation only — adding the code projects "
             "around it, leaving every existing file untouched.")

    files: dict[Path, str] = {
        mod_dir / "README.md": _module_readme(name, cls, today),
        docs_dir / "ARCHITECTURE.md": _module_architecture(name, cls, today),
        docs_dir / "NEXT.md": _module_next(name, cls, today),
        core_dir / f"Coordinator.{cls}.Core.csproj": CORE_CSPROJ,
        core_dir / f"{cls}Module.cs": _cs_placeholder(
            cls, name, "Module",
            "Implements IModule: Identity, Capabilities, TriggerIntents, and the lifecycle "
            "(Initialize / Enable / Handle / Apply / Disable). Everything it needs arrives through "
            "IModuleContext — no statics, no service locator, no ambient globals."),
        core_dir / f"{cls}Capabilities.cs": _cs_placeholder(
            cls, name, "Capabilities",
            "Capability ids as constants, each with a ValueSpec carrying its real bounds. One "
            "declaration drives the settings form, load-time validation, and any future binding "
            "surface. Ids are permanent: add freely, never rename, never reuse."),
        core_dir / f"{cls}Triggers.cs": _cs_placeholder(
            cls, name, "Triggers",
            "Trigger intents declared for Conduit. This module never names an input mechanism and "
            "never installs a hook. A declaration is a request; the answer may be a refusal, and "
            "the module must remain useful when refused."),
        core_dir / f"{cls}Settings.cs": _cs_placeholder(
            cls, name, "Settings",
            "The versioned settings record. Every field has a default so old settings still load "
            "(additive by default); structural changes get an explicit Migrate() plus a test that "
            "fails without it. A reset is only ever explicit."),
        shell_dir / f"Coordinator.{cls}.Shell.csproj": SHELL_CSPROJ.replace("{cls}", cls),
        test_dir / f"Coordinator.{cls}.Core.Tests.csproj":
            TESTS_CSPROJ.replace("{cls}", cls).replace("{name}", name),
    }

    # Never overwrite a file that is already there. The guard above establishes that no CODE exists;
    # this establishes that a hand-written README or ARCHITECTURE.md survives contact with the
    # scaffolder. A generator that silently replaces prose someone wrote is worse than one that
    # refuses outright, because the loss is invisible until you look for it.
    skipped = [p for p in files if p.exists()]
    to_write = {p: c for p, c in files.items() if not p.exists()}

    if args.dry_run:
        print(f"(dry-run) would create {len(to_write)} file(s) under {rel(mod_dir)} and {rel(test_dir)}:")
        for path in to_write:
            print(f"          {rel(path)}")
        for path in skipped:
            print(f"          (kept, already exists) {rel(path)}")
        return EXIT_OK

    for path, content in to_write.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    for path in skipped:
        info(f"kept existing {rel(path)}")

    print()
    ok(f"scaffolded module '{name}' ({cls})")
    print(f"""
  src/modules/{name}/
  ├── README.md                              front door — capabilities, done-vs-TODO,
  │                                          and a "Where to resume" section
  ├── Coordinator.{cls}.Core/{" " * max(0, 24 - len(cls))} net9.0 — ALL decision logic, no Windows types
  │   ├── Coordinator.{cls}.Core.csproj
  │   ├── {cls}Module.cs
  │   ├── {cls}Capabilities.cs
  │   ├── {cls}Triggers.cs
  │   └── {cls}Settings.cs
  ├── Coordinator.{cls}.Shell/{" " * max(0, 23 - len(cls))} net9.0-windows — thin adapter (delete if unused)
  │   └── Coordinator.{cls}.Shell.csproj
  └── docs/
      ├── ARCHITECTURE.md
      └── NEXT.md

  tests/
  └── Coordinator.{cls}.Core.Tests/{" " * max(0, 18 - len(cls))} runs on any OS
      └── Coordinator.{cls}.Core.Tests.csproj
""")
    print("""Next steps — the walkthrough is docs/recipes/add-a-module.md, the contract is
docs/MODULE_SPEC.md:

  1. Write the Core logic and its tests FIRST, before any Windows code exists. That ordering is the
     recipe's one hard rule: once a Windows project can be launched, "run it and look" becomes the
     cheapest check, and from then on you cannot tell a wrong calculation from a wrong adapter.
  2. Declare capabilities and trigger intents with permanent ids.
  3. Register the module with the host, and add the test project to the solution — a test project
     nobody runs is a check that cannot fail.
  4. Add a row to the module table in README.md, at its REAL state.
  5. Add a validation scenario to docs/runbooks/manual-validation.md.
  6. Fill in "Where to resume" in the module README before you stop. Not at the end — now.

Then run:  coord test  ·  coord audit  ·  coord map --check
""")
    warn("the .csproj files just written have never been restored or built — no C# in this "
         "repository has been through a compiler.")
    return EXIT_OK


# --- commands: doctor --------------------------------------------------------------------------
def _row(label: str, value: str, note: str = "") -> None:
    print(f"  {label:<14}{value:<34}{note}")


def cmd_doctor(args) -> int:
    """Report what this machine actually has, honestly, and say what that lets you do.

    This is the one command whose output should be read rather than skimmed, because everything
    downstream assumes it. A diagnostic that cannot be wrong carries no information — so if `doctor`
    is wrong about the machine, fix `doctor` before trusting anything else.

    Exit code: non-zero only for genuinely blocking problems. A missing .NET SDK is NOT blocking —
    it is the documented state of a documentation-only machine, and the doc gate works without it.
    """
    print("Windows Coordinator — coord doctor\n")

    blocking: list[str] = []
    notes: list[str] = []

    # --- the machine ---------------------------------------------------------------------------
    py = sys.version.split()[0]
    py_ok = sys.version_info >= MIN_PY
    _row("python", py, "ok (3.11+)" if py_ok else "TOO OLD — the tooling requires 3.11+")
    if not py_ok:
        blocking.append("Python is older than 3.11 — the stdlib tooling will not run.")

    git = shutil.which("git")
    _row("git", "found" if git else "not found",
         git or "MISSING — install git")
    if not git:
        notes.append("git is missing: `coord audit --since <ref>` cannot diff, so closeout mode is "
                     "unavailable.")

    _row("platform", f"{sys.platform}", f"{os.name} · {REPO_ROOT}")

    print()

    # --- the .NET toolchain --------------------------------------------------------------------
    dotnet = find_dotnet()
    if not dotnet:
        _row("dotnet SDK", "not found",
             _c("33", "MISSING — coord build / test / run are unavailable"))
        _row("workloads", "(skipped — no SDK)", "")
        notes.append(
            "No .NET SDK on this machine. That is a supported state, not an error: `coord audit` "
            "and `coord map` are pure Python and work here.\n"
            "    To get the rest: winget install Microsoft.DotNet.SDK.9  (Windows), or "
            "https://dotnet.microsoft.com/download.")
    else:
        sdks = dotnet_sdks(dotnet)
        if not sdks:
            _row("dotnet SDK", "runtime only",
                 _c("33", "the CLI is present but lists NO SDKs"))
            notes.append(
                f"`dotnet` at {dotnet} is a RUNTIME-only install — it answers, which makes it look "
                "fine, and then every build fails for an unrelated-sounding reason.\n"
                "    Run `dotnet --info` and read the *SDKs* list. Fix: install "
                "Microsoft.DotNet.SDK.9.")
        else:
            _row("dotnet SDK", ", ".join(sdks[-3:]), f"ok · {dotnet}")
            has9 = any(v.startswith("9.") for v in sdks)
            if not has9:
                notes.append("No 9.x SDK found. The projects target net9.0 (ADR 0002); an older SDK "
                             "will not build them.")
            wl = _workloads(dotnet)
            _row("workloads", wl or "(none reported)",
                 "informational — WinUI 3 ships as a NuGet package, no workload expected")

    # --- the repository ------------------------------------------------------------------------
    sln = find_solution()
    if sln:
        _row("solution", rel(sln), "ok")
    else:
        _row("solution", "not found",
             "expected — no .sln exists yet (TD-2); docs/NEXT.md step 1 generates it")
        notes.append(
            "No solution file. This is a KNOWN STATE, deliberately, not a broken checkout: a .sln "
            "carries per-project GUIDs that could not be verified where this repository was "
            "authored.\n"
            "    Fix, on Windows with the SDK:  dotnet new sln --name Coordinator   then "
            "`dotnet sln add` each project under src/ and tests/. Read docs/NEXT.md first — it owns "
            "that task.")

    src_projects = find_projects(SRC_DIR)
    test_projects = find_test_projects()
    _row("projects", f"{len(src_projects)} under src/",
         "none yet" if not src_projects else "")
    _row("test projects", f"{len(test_projects)} under tests/",
         "expected until a module exists" if not test_projects else "")
    if not test_projects:
        notes.append("Zero test projects: `coord test` will refuse rather than report a pass, "
                     "because a run with nothing in it is a check that cannot fail.")

    modules = ([p.name for p in sorted(MODULES_DIR.iterdir()) if p.is_dir()]
               if MODULES_DIR.is_dir() else [])
    _row("modules", ", ".join(modules) if modules else "none",
         "expected — no module has been created (`coord new-module <name>`)" if not modules else "")

    # --- the doc tooling (the gate that works today) --------------------------------------------
    audit_ok = AUDIT_SCRIPT.exists()
    genmap_ok = GENMAP_SCRIPT.exists()
    _row("doc audit", "present" if audit_ok else "NOT FOUND",
         rel(AUDIT_SCRIPT) if audit_ok else _c("31", f"expected at {rel(AUDIT_SCRIPT)}"))
    _row("doc map", "present" if genmap_ok else "NOT FOUND",
         rel(GENMAP_SCRIPT) if genmap_ok else _c("31", f"expected at {rel(GENMAP_SCRIPT)}"))
    if not (audit_ok and genmap_ok):
        blocking.append(
            "The doc-audit tooling is missing from tools/doc-audit/. It is the only gate that works "
            "without a .NET SDK, so without it this checkout has no automated check at all. Restore "
            "it from git.")

    # --- the verdict ----------------------------------------------------------------------------
    print()
    print("What you can do on this machine:")
    can = []
    if audit_ok and genmap_ok and py_ok:
        can += ["coord audit", "coord map", "coord new-module"]
    if dotnet and dotnet_sdks(dotnet):
        can += ["coord build", "coord test"]
        if sys.platform == "win32":
            can.append("coord run")
    print("  " + (", ".join(can) if can else "(nothing — see the blocking problems below)"))

    cannot = []
    if not (dotnet and dotnet_sdks(dotnet)):
        cannot.append("coord build / coord test / coord run — no .NET SDK")
    elif sys.platform != "win32":
        cannot.append("coord run — not Windows")
    cannot.append("anything about window placement, hotkeys, DPI, the tray or the UI — those are "
                  "checked by a human on a real desktop (docs/runbooks/manual-validation.md)")
    print("What you cannot:")
    for c in cannot:
        print(f"  - {c}")

    if notes:
        print("\nNotes:")
        for n in notes:
            print(f"  - {n}")

    if blocking:
        print()
        for b in blocking:
            warn(b)
        return EXIT_FAILED

    print()
    ok("no blocking problems.")
    return EXIT_OK


def _workloads(dotnet: str) -> str:
    try:
        p = subprocess.run([dotnet, "workload", "list"], capture_output=True, text=True, timeout=60)
    except Exception:
        return ""
    if p.returncode != 0:
        return ""
    ids = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith(("Installed Workload", "Id", "-", "Use `dotnet")):
            continue
        ids.append(line.split()[0])
    return ", ".join(ids)


# --- arg parsing -------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="coord",
        description="Windows Coordinator — the single developer entry point.",
        epilog="`coord audit` and `coord map` are pure Python and need no .NET SDK. "
               "`coord doctor` tells you what this machine can actually do.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="print what would run (or be created) without doing it")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("test", help="run the Core test suites (dotnet test) — any OS")
    t.add_argument("name", nargs="*", help="optional test-project name filter(s)")
    t.add_argument("--filter", help="passed through to `dotnet test --filter`")
    t.add_argument("-c", "--configuration", default="Debug", help="build configuration (Debug)")
    t.set_defaults(func=cmd_test)

    b = sub.add_parser("build", help="compile the C# (dotnet build)")
    b.add_argument("--project", help="build one project instead of the solution")
    b.add_argument("--core-only", action="store_true",
                   help="build only portable (non-Windows-targeted) projects — the useful mode off "
                        "Windows")
    b.add_argument("-c", "--configuration", default="Debug", help="build configuration (Debug)")
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("run", help="launch the Shell host — Windows only")
    r.add_argument("--project", help="run a specific project instead of the discovered Shell host")
    r.add_argument("-c", "--configuration", default="Debug", help="build configuration (Debug)")
    r.set_defaults(func=cmd_run)

    au = sub.add_parser("audit", help="documentation + modularity drift check (no .NET needed)")
    au.add_argument("--quiet", action="store_true", help="summary and ERRORs only")
    au.add_argument("--format", choices=["text", "json"], help="output format")
    au.add_argument("--no-fail", action="store_true", help="always exit 0 (report only)")
    au.add_argument("--accuracy", action="store_true",
                    help="accuracy sweep: docs whose `audited` flag has gone stale")
    au.add_argument("--since", metavar="REF",
                    help="closeout mode vs REF (e.g. origin/main) — changed docs must bump "
                         "`updated`")
    au.set_defaults(func=cmd_audit)

    mp = sub.add_parser("map", help="regenerate docs/MAP.md, the doc index (no .NET needed)")
    mp.add_argument("--check", action="store_true", help="exit non-zero if the index is stale")
    mp.set_defaults(func=cmd_map)

    nm = sub.add_parser("new-module", help="scaffold a module (README + docs + Core/Shell + tests)")
    nm.add_argument("name", help="lowercase, hyphen-separated, plain and descriptive (e.g. zones)")
    nm.set_defaults(func=cmd_new_module)

    d = sub.add_parser("doctor", help="report the toolchain honestly — run this first on a new "
                                      "machine")
    d.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    _make_stdio_utf8()
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        warn("interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
