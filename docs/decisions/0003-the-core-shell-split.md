# ADR 0003 — The Core/Shell split — Windows-free logic, thin Windows adapter

Date: 2026-08-08
Status: Accepted

## Context

Everything this product does is, at the bottom, a Win32 call. Moving a window is a Win32 call; owning
a hotkey chord is a Win32 call; knowing a monitor's work area, a window's bounds, or that a drag just
started are all Win32 calls. The path of least resistance is to write the logic where the calls are —
compute the target rectangle right next to `SetWindowPos`, decide which zone was hit right inside the
hook callback, migrate settings in the same class that reads the file.

That arrangement has one property that quietly determines everything else: **nothing can be verified
except by a human sitting at a Windows desktop watching the screen.** And it is precisely the hard
parts that get trapped behind that boundary. Zone rectangles derived from a work area across mixed DPI
scaling; deciding which of two modules owns a chord; schedule arithmetic across a daylight-saving
transition and a machine that was asleep; migrating a settings file three versions old. Every one of
those is pure computation with subtle edge cases, and every one of them would be reachable only
through the UI.

Two facts about this project make that unacceptable rather than merely unfortunate. First, the work
happens in bursts separated by months, and an unverifiable codebase after a gap is one you must
re-validate by hand before you dare change anything — the exact context-re-acquisition cost that
[OPERATING_MODEL.md](../OPERATING_MODEL.md) says the architecture exists to eliminate. Second, this
project's evidence standard forbids a claim stronger than its evidence, and a system where the only
evidence class is "I watched it work once" makes that standard impossible to honor honestly.

## Decision

**Every module and every pillar is two projects.**

| | **Core** | **Shell adapter** |
|---|---|---|
| Target framework | `net9.0` | `net9.0-windows10.0.19041.0` |
| Windows dependencies | **zero** | all of them |
| Contains | decision logic, geometry, state machines, scheduling, settings shapes, capability declarations | P/Invoke, window handles, hook plumbing, WinUI pages |
| Runs on | any OS — a Linux CI runner, a container, a Mac | Windows only |
| Verified by | unit tests (`coord test`) | [runbooks/manual-validation.md](../runbooks/manual-validation.md) |
| Size goal | as large as it needs to be | **as thin as physically possible** |

Three rules make the split real rather than aspirational.

**The Shell adapter decides nothing.** Its job is to collect facts, hand them to Core, and carry out
Core's answer. The only branches permitted in an adapter are null checks and Win32 error checks;
anything else is a decision, and decisions live in Core. This is what keeps the untestable half small
enough that reading it is a credible substitute for testing it.

**Core never sees a Windows type.** Not an `HWND`, not a `RECT`, not an `IntPtr` standing in for
either. [Atlas](../ATLAS.md) exposes an opaque `WindowRef` precisely so that "which window" can cross
the boundary without dragging Windows into Core. The mapping between Core's types and whatever Win32
hands back lives on the Shell side of the line, by construction.

**The boundary is machine-checked, not trusted.** The `boundary` check in `tools/doc-audit/audit.py`
is an ERROR-severity gate: it reads `using` directives, `[DllImport]` attributes, namespace references
and `ProjectReference` elements across `.cs` and `.csproj` files, and it fails when a Core project
reaches for Windows — or when a module reaches for another module, or the platform reaches into a
module. [TD-3](../TECH_DEBT.md) is honest about the limits of a text-based check: it is defeated by
reflection, by a fully-qualified type name written inline, and by a package that transitively drags
Windows types in. A green boundary result is evidence, not proof.

## Consequences

**This is what makes the rest of the apparatus mean anything**, and that is worth being explicit
about, because the split otherwise reads as taste. Lens A of the [audit](../AUDIT.md) asks whether
every documented claim is still true — answerable only where behavior can be asserted. A test suite is
*possible* because there is a half that can be tested. Continuous integration is possible at all only
because half the tree is meant to build on Linux. And the evidence standard's second failure shape — a claim
stronger than its evidence — stops being a matter of judgement each time and becomes a structural
fact: the boundary between "proven by a test" and "validated by a human" is a project reference you
can see.

**The costs are real and are paid on every unit.**

*Two projects per unit.* A module is never one folder, and creating one is never one command's worth
of typing. `coord new-module` exists partly so that the ceremony is not a reason to leave an idea
uncreated.

*A mapping layer at the boundary.* `RECT` becomes a Core rectangle; `HWND` becomes a `WindowRef`; a
hook callback becomes a Core event. That is real code with real bugs, sitting on the side of the line
that has no tests. It is a genuine transfer of risk, not an elimination of it — the bet is that
mechanical translation fails more visibly and less subtly than geometry does.

*The standing temptation to "just P/Invoke here."* One `GetWindowRect` inside a Core project, because
the alternative is threading a value through Atlas for a case that seems obvious. **This is how the
design dies** — not by a decision to abandon it, but by five individually reasonable exceptions after
which the split exists only in the documentation. The boundary check exists specifically to catch
that first exception, and [TD-3](../TECH_DEBT.md) records what it cannot see. When a Core project
someday has a *legitimate* need for a Windows type, the correct response is an ADR and a considered
exception, not a quiet `using`.

*A permanent obligation about phrasing.* A green `coord test` proves Core logic and proves **nothing**
about window placement, hotkey capture, DPI behavior, tray lifecycle, or anything a user can see. The
split is what makes host testing possible; being precise forever after about which half a green run
covers is its price, and any sentence in this repository that blurs it is a defect in the
documentation rather than a shortcut.

*None of this is verified.* Nothing has been compiled ([TD-1](../TECH_DEBT.md)), so the split as
described is a design and not an observed property of a codebase. The first real build is expected to
surface places where the boundary is harder to hold than it reads.

## Alternatives considered

**One project per unit, with interfaces for Windows services and mocks in tests.** The conventional
answer, and it achieves the same testability *when it is followed*. Rejected because it relies
entirely on discipline, and discipline is exactly what a project resumed after eight months does not
have. The difference is enforceability: a project reference is checkable by a script, while "we always
put Win32 behind an interface" is checkable only by a review that will not happen on a solo project.
Given a choice between a rule a machine enforces and a rule a person remembers, this project takes the
machine every time.

**Test everything on Windows through UI automation.** Rejected on three counts: it is slow and flaky
enough that a failing run gets re-run rather than investigated (a check that cannot fail, by
attrition); it needs a Windows runner, which the CI story does not have ([TD-4](../TECH_DEBT.md)); and
it would not run in the environment where thinking actually happens. It also gives up the property
that matters most day to day — being able to check a geometry change in two seconds while the idea is
still in your head.

**Skip Core entirely and accept manual validation as the only evidence class.** This is the honest
description of most personal Windows utilities, and it is genuinely cheaper on day one. Rejected
because it makes every change after a long gap a leap of faith, and because it would make the project's
own evidence standard unsatisfiable — there would be no claim about behavior that anything but a
human's memory could support.

**Apply the split to modules only, letting the pillars stay monolithic.** Superficially appealing,
since the pillars are the layer closest to Win32 and would seem to benefit least. Rejected because it
exempts exactly the wrong code: the pillars hold the hardest pure logic in the system — zone geometry
resolved against a work area at a given scale factor, trigger arbitration, schedule arithmetic — and
that logic is far more likely to be subtly wrong than any module's. [CONDUIT.md](../CONDUIT.md) and
[ATLAS.md](../ATLAS.md) both describe Core-side contracts for this reason.

**Put the split at a source-file convention instead of a project boundary** (`*.Core.cs` files, one
assembly). Rejected: it cannot be enforced by the compiler at all — a "Core" file can reference
anything its assembly references — so it provides the diagram without the guarantee.
