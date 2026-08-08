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



class DesignFirstScaffoldTests(unittest.TestCase):
    """A module starts as a design before it starts as code.

    docs/MODULE_SPEC.md says to write the spec first, and Zones was specified in full before the
    module host that would load it existed. So `coord new-module` has to be able to fill in the code
    around a directory that already holds documentation — while never touching a file a human wrote,
    and while still refusing to clobber real code.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        _copy_repo(self.repo)
        self.addCleanup(self._tmp.cleanup)

    def test_fills_in_code_around_a_docs_only_module_without_touching_the_docs(self) -> None:
        mod = self.repo / "src" / "modules" / "designfirst"
        (mod / "docs").mkdir(parents=True)
        readme = mod / "README.md"
        arch = mod / "docs" / "ARCHITECTURE.md"
        readme.write_text("hand-written front door\n", encoding="utf-8")
        arch.write_text("hand-written design\n", encoding="utf-8")

        result = _run_new_module(self.repo, "designfirst")
        self.assertEqual(result.returncode, 0,
                         f"refused a docs-only module\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        # The code arrived...
        self.assertTrue((mod / "Coordinator.Designfirst.Core"
                             / "Coordinator.Designfirst.Core.csproj").exists())
        # ...and the prose is byte-for-byte what it was.
        self.assertEqual(readme.read_text(encoding="utf-8"), "hand-written front door\n")
        self.assertEqual(arch.read_text(encoding="utf-8"), "hand-written design\n")

    def test_still_refuses_when_real_code_exists(self) -> None:
        """The guard that actually matters must not have been weakened into uselessness."""
        first = _run_new_module(self.repo, "hascode")
        self.assertEqual(first.returncode, 0, first.stderr)
        second = _run_new_module(self.repo, "hascode")
        self.assertNotEqual(second.returncode, 0,
                            "scaffolded over a module that already had project files")
        combined = (second.stdout + second.stderr).lower()
        self.assertIn("not documentation", combined)
        self.assertIn(".csproj", combined, "the refusal should name what it found")


class OrphanCodeGuardTests(unittest.TestCase):
    """"Documentation only" must be an allow-list, not "contains no .csproj".

    The first version of the design-first guard tested for the absence of a project file, so a
    directory holding orphan .cs or .xaml was accepted — and the tool then printed "holds
    documentation only" while scaffolding around real work. A guard whose predicate is broader than
    its claim passes for reasons its own message does not admit. Reported in review of PR #2.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        _copy_repo(self.repo)
        self.addCleanup(self._tmp.cleanup)

    def _expect_refusal(self, name: str, path: Path, body: str = "// orphan\n") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        result = _run_new_module(self.repo, name)
        self.assertNotEqual(
            result.returncode, 0,
            f"scaffolded around orphan code at {path.relative_to(self.repo)}\n{result.stdout}")
        self.assertNotIn("documentation only", result.stdout,
                         "claimed the directory was documentation only while it held code")
        self.assertEqual(body, path.read_text(encoding="utf-8"), "the orphan file was modified")

    def test_refuses_orphan_cs_in_the_module_directory(self) -> None:
        self._expect_refusal("orphancs",
                             self.repo / "src" / "modules" / "orphancs" / "Half.cs")

    def test_refuses_orphan_xaml_nested_in_the_module_directory(self) -> None:
        self._expect_refusal("orphanxaml",
                             self.repo / "src" / "modules" / "orphanxaml" / "ui" / "Page.xaml",
                             "<Page/>\n")

    def test_refuses_orphan_code_in_the_TEST_directory(self) -> None:
        """The tests directory is a separate tree and was unguarded in the first version."""
        self._expect_refusal("orphantests",
                             self.repo / "tests" / "Coordinator.Orphantests.Core.Tests" / "Old.cs")

    def test_refuses_a_stray_non_doc_file_under_docs(self) -> None:
        self._expect_refusal("orphandocs",
                             self.repo / "src" / "modules" / "orphandocs" / "docs" / "notes.txt",
                             "notes\n")

    def test_still_accepts_the_real_documentation_only_shape(self) -> None:
        """Guard the guard: the allow-list must not have been tightened into uselessness."""
        mod = self.repo / "src" / "modules" / "docsonly"
        (mod / "docs").mkdir(parents=True)
        (mod / "README.md").write_text("front door\n", encoding="utf-8")
        (mod / "docs" / "ARCHITECTURE.md").write_text("design\n", encoding="utf-8")
        (mod / "docs" / "diagram.svg").write_text("<svg/>\n", encoding="utf-8")
        result = _run_new_module(self.repo, "docsonly")
        self.assertEqual(result.returncode, 0,
                         f"refused a genuinely docs-only module\n{result.stdout}\n{result.stderr}")
        self.assertEqual((mod / "README.md").read_text(encoding="utf-8"), "front door\n")

if __name__ == "__main__":
    unittest.main()
