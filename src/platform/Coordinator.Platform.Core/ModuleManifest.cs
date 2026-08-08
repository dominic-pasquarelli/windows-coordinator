// -------------------------------------------------------------------------------------------------
// COMPILES. First observed 2026-08-08 at commit 7aef6ff: GitHub Actions built every project on
// Ubuntu (0 warnings, under TreatWarningsAsErrors) and on Windows, and the Core suites passed —
// 45 tests, 0 failed. Authored without a local SDK, so the compiler was the first reader.
//
// That is a statement about COMPILATION and, where tests cover it, about pure logic. It is not a
// statement about behaviour: no window has been placed, no hotkey registered, no monitor
// enumerated, no tray icon shown, and no Shell adapter exists. Those come only from
// docs/runbooks/manual-validation.md, performed by a human on a real Windows desktop.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Platform;

/// <summary>
/// A module's identity as the platform records it: who this module permanently is, and how it
/// should be described to a human.
/// </summary>
/// <remarks>
/// <para>
/// The manifest separates the one field that can never change from the three that can change
/// freely. That separation is the whole reason the type exists, and it is the same discipline
/// applied to capability ids (see <see cref="CapabilityId"/>).
/// </para>
/// <para>
/// The manifest is declared by the module and read by the host, the settings store, and the update
/// channel. It is a value: constructing one has no side effects and does no work.
/// </para>
/// </remarks>
/// <param name="Id">
/// The permanent module id — lowercase, plain, descriptive, chosen once and never changed
/// ("zones", "chrono"). This is the key under which settings are stored, the prefix of every
/// capability id the module publishes, and the name the trigger arbiter reports when this module
/// wins a contested binding. Renaming it silently orphans a user's saved settings and bindings on
/// a machine nobody is looking at, which is the worst class of failure available here: no
/// exception, no log line, just a feature that quietly stops doing what it did yesterday.
/// Independent of assembly name, file path, and display name, so all three stay free to change.
/// </param>
/// <param name="DisplayName">
/// The human-facing name, shown in the tray menu and the settings surface. Rename it whenever a
/// better word turns up; nothing keys on it.
/// </param>
/// <param name="Version">
/// The module's version as text. Note that a module does not ship independently — it travels inside
/// the host's update payload (ADR 0008) — so this is descriptive, useful in a diagnostic or a fault
/// report, and it is not a dependency-resolution input. Comparison semantics are deliberately
/// undecided: nothing compares two of these yet, and inventing an ordering with no consumer is the
/// speculative work the operating model forbids.
/// </param>
/// <param name="Description">
/// One sentence a user would recognise: what this module does. Shown beside the module in the
/// Shell. Free to change.
/// </param>
public sealed record ModuleManifest(
    string Id,
    string DisplayName,
    string Version,
    string Description);
