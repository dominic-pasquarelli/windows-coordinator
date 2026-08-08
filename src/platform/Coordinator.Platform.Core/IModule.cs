// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Platform;

/// <summary>
/// The lifecycle every module implements. One behaviour, declared and supervised by the host.
/// </summary>
/// <remarks>
/// <para>
/// The order is fixed and the host guarantees it: construct, initialise, enable, ... disable,
/// dispose. A module is never asked to do anything before <see cref="EnableAsync"/> has returned or
/// after <see cref="DisableAsync"/> has been called, and the host is responsible for making that
/// true even when another module misbehaves.
/// </para>
/// <para>
/// <b>Where the work goes.</b> Construction is cheap — no I/O, no throwing, nothing that delays
/// start-up for every other module. <see cref="InitializeAsync"/> is where expensive setup belongs:
/// settings are already loaded, and blocking on the disk here costs a moment at start-up rather
/// than a stutter at the worst possible time. Everything after that should be pre-resolved and
/// cheap. This is "resolve once, execute cheap", and on this platform it is not a performance
/// nicety: the paths that run later sit on the desktop's critical path, where slowness is felt
/// machine-wide rather than in one application.
/// </para>
/// <para>
/// <b>Degradation is a contract, not a courtesy.</b> A module that fails must not take down the
/// host or any other module. Concretely: <see cref="DisableAsync"/> must be safe to call after a
/// failed <see cref="EnableAsync"/>, and it must not throw — it is the path the host uses to clean
/// up after something has already gone wrong, and a throw there turns one broken module into a
/// broken tray icon.
/// </para>
/// <para>
/// <b>Deliberately minimal.</b> docs/MODULE_SPEC.md also describes trigger-intent declarations, a
/// dispatch handler, and a single capability setter. None of those is declared here: the trigger
/// types live in the Conduit pillar and nothing yet dispatches anything, so putting the members on
/// this interface now would fix their shapes before the first consumer has ever pushed back. What
/// is here is the part every module needs regardless of how those questions resolve.
/// </para>
/// </remarks>
public interface IModule : IAsyncDisposable
{
    /// <summary>
    /// This module's permanent identity and human description. Must be a constant of the module —
    /// the same value on every construction, never computed from a path, an assembly name, or the
    /// environment.
    /// </summary>
    ModuleManifest Manifest { get; }

    /// <summary>
    /// Everything this module exposes for settings, for the settings surface, and for binding.
    /// </summary>
    /// <remarks>
    /// Declared, not discovered: the host reads this list rather than reflecting over the type, so
    /// what a module publishes is a decision written in one place and readable in one place. If a
    /// user could plausibly want to change it or bind a key to it, it belongs in this list — that
    /// is how settings, the Shell, and any future binding surface find it without knowing anything
    /// about what the module does. The ids in it are permanent; see <see cref="CapabilityId"/>.
    /// </remarks>
    IReadOnlyList<Capability> Capabilities { get; }

    /// <summary>
    /// Real setup. Settings are loaded by the time this runs, and no trigger can fire until it
    /// returns.
    /// </summary>
    /// <param name="context">
    /// The platform, and the only route to it. See <see cref="IModuleContext"/>.
    /// </param>
    /// <param name="cancellationToken">Cancels a slow start-up.</param>
    /// <remarks>I/O is allowed here. This is the place for it.</remarks>
    ValueTask InitializeAsync(IModuleContext context, CancellationToken cancellationToken);

    /// <summary>
    /// Begin responding. After this returns the module is live and may be called at any time.
    /// </summary>
    /// <param name="cancellationToken">Cancels the transition.</param>
    ValueTask EnableAsync(CancellationToken cancellationToken);

    /// <summary>
    /// Stop responding, and release anything held while enabled.
    /// </summary>
    /// <param name="cancellationToken">
    /// Bounds the shutdown. Note that the host may proceed anyway: a module that will not stop
    /// promptly is not permitted to hold up the process.
    /// </param>
    /// <remarks>
    /// Must complete promptly, must be safe to call after a failed enable, must be safe to call
    /// twice, and must not throw.
    /// </remarks>
    ValueTask DisableAsync(CancellationToken cancellationToken);

    // Disposal is `IAsyncDisposable`, inherited above, and the host calls it after DisableAsync.
    // It is last-resort cleanup for unmanaged or long-lived resources — not a second disable, and
    // not somewhere to do work that mattered.
}
