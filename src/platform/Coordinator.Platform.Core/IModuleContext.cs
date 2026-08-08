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
/// Everything a module is given by the platform, handed to it once at initialisation.
/// </summary>
/// <remarks>
/// <para>
/// <b>This is the only way a module reaches the platform.</b> There is no service locator, no
/// static accessor, and no ambient global. If something is not on this interface, a module does not
/// get it — which is what makes a module testable in isolation: a test constructs a context of
/// fakes and the module cannot tell the difference, because there is nothing else for it to reach.
/// </para>
/// <para>
/// <b>What is deliberately not here yet, and why.</b> docs/MODULE_SPEC.md describes a richer
/// context: a scoped logger, a desktop-truth accessor, an injected clock, and the record of what
/// the trigger fabric granted or refused. Every one of those is intended. None is declared here,
/// because each would require a type that does not exist yet, and declaring an accessor whose
/// return type is invented on the spot fixes a shape before anything has pushed back on it.
/// </para>
/// <para>
/// There is also a real design question underneath, and it is better named than papered over: the
/// dependency direction between the platform and the pillars is not settled. Today the pillars
/// reference this project (for <see cref="CapabilityId"/>) and this project references neither of
/// them, which keeps the graph acyclic and keeps this assembly free of anything a module might not
/// use. Exposing a desktop-truth accessor here would invert that. Resolving it — an accessor here,
/// a separate context assembly, or the pillars handed to a module some other way — is a first-build
/// task, recorded in the platform README's "Where to resume".
/// </para>
/// </remarks>
public interface IModuleContext
{
    /// <summary>
    /// This module's own identity, as the host recorded it. Handed back so a module never has to
    /// hold a second copy of its own id and never has to reconstruct one.
    /// </summary>
    ModuleManifest Manifest { get; }

    /// <summary>
    /// This module's settings, and only this module's. See <see cref="ISettingsStore"/>.
    /// </summary>
    ISettingsStore Settings { get; }
}
