# ADR 0002 — C# / .NET 9 and WinUI 3 as the stack

Date: 2026-08-08
Status: Accepted

## Context

Windows Coordinator is a tray-resident host that manipulates other applications' windows, registers
global hotkeys, listens to system-wide window events, and presents a settings surface. Four
requirements shape the stack choice, and they pull in different directions.

**Deep Win32 interop is unavoidable.** Everything the product does — moving a window, owning a chord,
knowing when a drag started, reading a monitor's work area — is a Win32 call. A stack that makes
interop awkward makes the whole product awkward.

**"Stock Windows feel" is a product requirement, not a preference.** The reference point is PowerToys:
a settings window that looks like part of the operating system rather than an add-on. A toolbox whose
own UI feels foreign undermines the thing it is for. This is the requirement that eliminates most
candidates.

**It must be resumable after months.** [OPERATING_MODEL.md](../OPERATING_MODEL.md) treats context
re-acquisition as the cost the whole architecture exists to eliminate. A stack the owner uses rarely
imposes that cost on every single burst of work, permanently.

**It sits resident all day.** Idle memory, idle CPU, and startup cost are real for a process that is
always running, and a utility that makes the machine worse has failed regardless of its features.

The choice had to be made before any UI could be written, and it was made in an environment with **no
.NET SDK present** — so it is a decision taken on reputation and prior experience, with nothing
measured. That is recorded honestly below rather than glossed.

## Decision

**C# on .NET 9. WinUI 3 via the Windows App SDK for the Shell. Core libraries target `net9.0` and
reference neither.**

Concretely: every Core project targets `net9.0` and is forbidden from referencing Windows types at all
([ADR 0003](0003-the-core-shell-split.md)); every Windows-facing project targets
`net9.0-windows10.0.19041.0`; the settings and dashboard surface is WinUI 3; interop is P/Invoke,
generated where practical rather than hand-declared. Shared MSBuild properties (nullable enabled,
warnings as errors, a pinned language version) live in `Directory.Build.props` so the settings are one
decision rather than one per project.

The reasoning, briefly. C# gives first-class, thoroughly documented Win32 interop without leaving the
managed world, so the awkward part of the product is awkward in a well-trodden way. It is the stack
the owner will still be fluent in after a nine-month gap, which is worth more here than any
performance argument. The tooling that comes free — a test runner, nullable reference types,
analyzers — is what makes the Core half of [ADR 0003](0003-the-core-shell-split.md) genuinely
testable rather than theoretically testable. And WinUI 3 *is* what current Windows UI is built from,
so stock feel is inherited rather than reconstructed; PowerToys building its settings app on the same
substrate means the parity target and the implementation share a foundation.

## Consequences

**WinUI 3 pins development and validation to Windows, and this cost is larger than it first sounds.**
Anything targeting `net9.0-windows10.0.19041.0` cannot be built on Linux at all — not built, not
tested, not analyzed. Continuous integration can therefore cover the Core projects and nothing else,
which means **the automated gate covers the half of the codebase that was already easiest to verify
and none of the half where the risk lives** ([TD-4](../TECH_DEBT.md)). The mitigation is structural
rather than procedural: the Core/Shell split deliberately pushes everything decidable into the half
that CI can reach, so the uncovered half is reduced to adapters thin enough for a human to check by
reading. The residual danger is forgetting the gap exists and reading a green badge as coverage.

**The bootstrap could not compile a single line.** No .NET SDK existed in the environment where this
repository was authored, so this stack decision, the project files, and every contract interface are
text that has never reached a compiler ([TD-1](../TECH_DEBT.md)). Nothing here has been shown to
build, and the correct phrasing everywhere in this repository is *not compiled*.

**Every fiddly part of this specific stack is unmeasured.** WinUI 3 does not provide a notification
area icon, so a tray-resident app needs a Win32 path for the one thing it is most defined by.
Unpackaged deployment, the Windows App SDK runtime bootstrapper dependency, per-monitor DPI awareness
in the settings window, and cold start for a resident process are all areas where this stack is known
to be temperamental, and none has been tried here. [TD-10](../TECH_DEBT.md) carries them with a
trigger: a minimal spike during P1 — a tray icon plus one settings window, unpackaged — that records
what deployment actually required.

**A managed runtime costs more resident footprint than a native one.** For an all-day process that is
a real cost and it has never been measured; [TD-11](../TECH_DEBT.md) exists so that any future claim
that the toolbox is lightweight is falsifiable rather than rhetorical.

**The delivery channel inherits a prerequisite.** If the App SDK bootstrapper makes "copy the folder
and run it" impossible, that constrains
[ADR 0008](0008-the-update-delivery-channel-is-built-now.md)'s mechanism, and the P1 spike must report
it explicitly rather than discovering it during a release.

**What would make this decision be revisited**, stated now so a future session does not have to
invent the criteria:

- The P1 spike finds tray behavior or unpackaged deployment genuinely hostile — TD-10's trigger in
  [TECH_DEBT.md](../TECH_DEBT.md). That reopens **the UI framework**, with WPF as the fallback; it
  does not reopen the language, and it costs only the Shell adapters.
- Measured idle footprint or hook-callback latency makes the toolbox worse than the annoyances it
  removes (TD-11). That reopens **the runtime**, which is a much larger conversation.
- Neither reopens the Core projects. That containment is the entire point of the split, and it is why
  a stack decision taken with zero measurements is an acceptable risk rather than a reckless one.

## Alternatives considered

**WPF.** The closest call by a wide margin, and it wins on several axes that matter here: no Windows
App SDK dependency, no runtime bootstrapper, a mature and well-understood tray story, simpler
deployment, and — honestly — a *more* testable UI layer, since its MVVM tooling and ecosystem are
deeper than WinUI 3's. Rejected on the one requirement that is not negotiable: its visual language is
a decade old, and a settings window that looks like 2015 fails the stock-Windows-feel goal at exactly
the surface the user judges the product by. The consolation is that the split makes this reversible —
if [TD-10](../TECH_DEBT.md)'s spike goes badly, moving to WPF rewrites the Shell and touches no Core
logic at all.

**Rust with the `windows` crates.** Genuinely attractive on the resident-process axis: a much smaller
footprint, no runtime prerequisite, and single-binary delivery that would make
[ADR 0008](0008-the-update-delivery-channel-is-built-now.md) substantially simpler. Rejected on the UI
story, which is the product's front door — there is no native-feeling Windows UI path, so the settings
surface would be a web view (which inverts the footprint advantage and the stock-feel requirement at
once) or a hand-rolled Win32 UI (which is a large amount of the least interesting work in the
project). The resumability test compounds it: an evenings project returned to after eight months in a
language used less often is a worse bet than a heavier runtime in a familiar one.

**C++ with Win32 directly** — the shape most PowerToys modules actually take. Best interop and best
footprint, worst fit for a single developer working in evening-sized pieces, and it would make the
Core half *harder* to test rather than easier, since the tooling that makes host testing cheap would
have to be assembled by hand.

**Electron or another web-UI shell.** Rejected outright: it fails the footprint requirement and the
stock-feel requirement simultaneously, which is a rare achievement for a stack whose main selling
point is developer convenience.

**Windows Forms.** Not seriously considered for the product surface, though worth recording that it
remains the pragmatic answer for a throwaway diagnostic window, and using it that way would not
violate anything here.
