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

using Coordinator.Platform;

namespace Coordinator.Conduit;

/// <summary>
/// One delivered wake-up: a declared intent fired, and here is the capability it addresses.
/// </summary>
/// <remarks>
/// <para>
/// Notice what is <b>not</b> here: no key code, no window handle, no timer reference, no mechanism
/// of any kind. That absence is the pillar's entire purpose. A module's handler receives its own
/// capability id and can be written, and tested, by someone who has never thought about input.
/// </para>
/// <para>
/// A window-event dispatch carries no window either, deliberately: an event says the desktop
/// changed, and what the desktop now <i>is</i> comes from a single coherent snapshot taken by the
/// other pillar. Two sources of desktop truth is the thing that pillar exists to prevent.
/// </para>
/// </remarks>
/// <param name="Intent">Which declared intent fired.</param>
/// <param name="Capability">The capability to act on — the module's own id, from its declaration.</param>
/// <param name="MonotonicStamp">
/// When the originating event was observed, in ticks from a <b>monotonic</b> source — not the wall
/// clock, which jumps backwards and forwards on clock sync, time-zone transitions, and a user
/// setting the time. The value is meaningful only when compared against another reading of the same
/// source, and a handler that wants to know how stale its wake-up is computes that itself, at the
/// moment it actually matters.
/// </param>
public sealed record TriggerEvent(
    TriggerIntentId Intent,
    CapabilityId Capability,
    long MonotonicStamp);

/// <summary>
/// What the fabric calls when a declared intent fires.
/// </summary>
/// <param name="triggerEvent">The wake-up.</param>
/// <param name="cancellationToken">
/// Cancelled when the module is being disabled or the host is shutting down. A handler that ignores
/// it is a handler that delays shutdown.
/// </param>
/// <remarks>
/// <para>
/// <b>This never runs on an input hook thread.</b> While a low-level input hook callback is
/// running, the keystroke it is inspecting has not yet been delivered to the application the user
/// is typing into — so a handler that blocks there does not slow this application down, it stalls
/// every application on the machine. Worse, the system applies a timeout to such hooks and silently
/// removes one that exceeds it: the punishment for being slow is that input stops working, with no
/// exception and no log entry.
/// </para>
/// <para>
/// The containment property that buys back is worth stating plainly: because dispatch happens on a
/// worker, a module that does something slow in a handler makes <i>itself</i> sluggish and cannot
/// make the desktop sluggish. That is the deal. It does not license blocking on the network or on
/// slow disk here — the user is still waiting — but the blast radius is bounded to the module.
/// </para>
/// <para>
/// <b>A handler is never re-entered for the same intent.</b> Dispatch is serialised per intent: if
/// a trigger fires while its handler is still running, the second event is coalesced or dropped,
/// not delivered concurrently. Re-entrancy in a hotkey handler is a bug factory, and it is far
/// cheaper to forbid it once in the fabric than to document it in every module.
/// </para>
/// <para>
/// Asynchronous because the natural response to most triggers is asynchronous, and because a
/// synchronous signature would quietly invite blocking on the dispatch worker.
/// </para>
/// </remarks>
public delegate ValueTask TriggerDispatchHandler(
    TriggerEvent triggerEvent,
    CancellationToken cancellationToken);
