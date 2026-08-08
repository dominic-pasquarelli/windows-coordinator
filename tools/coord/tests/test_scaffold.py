#!/usr/bin/env python3
"""Scaffold tests for `coord new-module`.

Why this file exists, stated plainly because the answer is a real defect and not a hypothetical:
`coord new-module` WRITES `.csproj` files, and a generated file is code. On 2026-08-08 the three
Core projects were renamed to carry a `.Core` suffix; the rename fixed the one hand-written
`ProjectReference` in the repository and missed the one the scaffold emits. Every module created
from then on would have been born referencing `Coordinator.Platform/Coordinator.Platform.csproj`,
a path that no longer existed. Two audits and four adversarial verifiers passed it, because nothing
had ever *run* the generator and looked at what came out.

So: create a module in a throwaway copy of the repository and assert that every reference the
generator produced resolves to a file that exists. Stdlib `unittest`, no dependencies, runs
anywhere Python 3.11+ does — including a machine with no .NET SDK.

    python3 -m unittest discover -s tools/coord/tests -v
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_REFERENCE_RE = re.compile(r'<ProjectReference[^>]*\sInclude="([^"]+)"')

# Directories that must not be copied into the throwaway checkout: version control, caches, and
# build output. Copying .git would make each test run clone the entire history for no benefit.
SKIP = {".git", "__pycache__", "bin", "obj", ".venv", "node_modules", ".pytest_cache"}


def _copy_repo(dest: Path) -> None:
    shutil.copytree(REPO_ROOT, dest, ignore=shutil.ignore_patterns(*SKIP), dirs_exist_ok=True)


def _run_new_module(repo: Path, name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "tools" / "coord" / "coord.py"), "new-module", name],
        capture_output=True, text=True, cwd=repo, check=False)


def _project_references(csproj: Path) -> list[str]:
    return PROJECT_REFERENCE_RE.findall(csproj.read_text(encoding="utf-8"))


class ScaffoldTests(unittest.TestCase):
    """`coord new-module` must produce a module whose references resolve."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        _copy_repo(self.repo)
        self.addCleanup(self._tmp.cleanup)

    def test_every_generated_project_reference_resolves(self) -> None:
        """The regression that motivated this file: a reference to a project that is not there."""
        result = _run_new_module(self.repo, "scaffoldprobe")
        self.assertEqual(result.returncode, 0,
                         f"new-module failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        generated = sorted((self.repo / "src" / "modules" / "scaffoldprobe").rglob("*.csproj"))
        generated += sorted((self.repo / "tests").rglob("*scaffoldprobe*/*.csproj"))
        self.assertTrue(generated, "new-module produced no .csproj files at all")

        checked = 0
        for csproj in generated:
            refs = _project_references(csproj)
            for inc in refs:
                # MSBuild accepts backslashes on every platform; normalise before hitting the disk.
                target = (csproj.parent / inc.replace("\\", "/")).resolve()
                self.assertTrue(
                    target.exists(),
                    f"{csproj.relative_to(self.repo)} references a project that does not exist:\n"
                    f"  Include = {inc}\n  resolved = {target}\n"
                    "A generated file is code. Fix the template in tools/coord/coord.py.")
                checked += 1

        # Guard the guard: if the generator ever stops emitting references, this test would pass
        # vacuously while checking nothing. A module Core project references the platform, so zero
        # is always wrong.
        self.assertGreater(checked, 0,
                           "no ProjectReference elements were found in the generated projects — "
                           "this test would have passed without checking anything")

    def test_generated_projects_are_discovered_by_the_audit(self) -> None:
        """The scaffold's output must satisfy the same boundary and reference checks as hand code."""
        result = _run_new_module(self.repo, "auditprobe")
        self.assertEqual(result.returncode, 0, result.stderr)

        audit = subprocess.run(
            [sys.executable, str(self.repo / "tools" / "doc-audit" / "audit.py"), "--format", "json"],
            capture_output=True, text=True, cwd=self.repo, check=False)

        import json
        findings = json.loads(audit.stdout)["findings"]
        offenders = [f for f in findings
                     if f["check"] in {"projectref", "boundary"} and f["severity"] == "error"]
        self.assertEqual(offenders, [],
                         "a freshly scaffolded module fails the repository's own checks:\n"
                         + "\n".join(f"  {f['check']} {f['file']}: {f['message']}" for f in offenders))

    def test_refuses_to_overwrite_an_existing_module(self) -> None:
        """Scaffolding over a module would destroy work; refusing is the whole behaviour."""
        first = _run_new_module(self.repo, "twice")
        self.assertEqual(first.returncode, 0, first.stderr)
        second = _run_new_module(self.repo, "twice")
        self.assertNotEqual(second.returncode, 0,
                            "new-module overwrote an existing module instead of refusing")

    def test_rejects_an_invalid_module_name(self) -> None:
        """Validation happens before anything is written, not after."""
        for bad in ["Zones Extra", "../escape", "UPPER", ""]:
            with self.subTest(name=bad):
                result = _run_new_module(self.repo, bad)
                self.assertNotEqual(result.returncode, 0,
                                    f"new-module accepted the invalid name {bad!r}")


if __name__ == "__main__":
    unittest.main()
