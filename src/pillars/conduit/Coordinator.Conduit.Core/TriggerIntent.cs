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
/// The permanent id of one trigger intent a module declares. Same discipline as a capability id:
/// chosen once, never renamed, never reused — a user's rebound chord is stored against it.
/// </summary>
/// <param name="Value">The id text. Lowercase, dotted, permanent.</param>
public readonly record struct TriggerIntentId(string Value);

/// <summary>
/// A declaration of what a module wants to be woken for. Never how.
/// </summary>
/// <remarks>
/// <para>
/// <b>A module never names an input mechanism.</b> It does not register a hotkey, install a hook,
/// own a timer, or subscribe to a window-event source. It declares an intent, and whether that is
/// satisfied by a kernel-arbitrated registration, a low-level hook, a window-event source or a
/// timer wheel is decided entirely inside this pillar — and can change later without a single
/// module changing with it.
/// </para>
/// <para>
/// The reason this is a pillar rather than a helper is that arbitration cannot be retrofitted.
/// Once two modules each hold their own registration, "who has this chord?" has no answer to give,
/// the loser cannot be told it lost, and the user sees a feature that is installed, enabled,
/// documented, and silently does nothing. So the indirection is mandatory from the first release
/// or it is never available at all.
/// </para>
/// <para>
/// Every intent carries the <see cref="CapabilityId"/> it will dispatch to, which is the whole
/// payoff of the indirection: what arrives at a module is its own capability id, never a key code,
/// so the binding is data the user owns rather than code the module owns.
/// </para>
/// <para>
/// <b>Four kinds are modelled here; docs/CONDUIT.md §3 specifies five.</b> The input gesture — the
/// drag-with-modifier recogniser that Zones will eventually need — is not declared, because a
/// recogniser specification with no recogniser and no consumer is a shape invented from nothing.
/// It is specified, it is expected, and it lands when the module that needs it does.
/// </para>
/// </remarks>
/// <param name="Id">The intent's permanent id.</param>
/// <param name="Capability">
/// The capability this intent fires. Belongs to the declaring module; the fabric never invents one.
/// </param>
public abstract record TriggerIntent(TriggerIntentId Id, CapabilityId Capability);

/// <summary>
/// "Wake me on this key combination."
/// </summary>
/// <param name="Id">The intent's permanent id.</param>
/// <param name="Capability">The capability the chord fires.</param>
/// <param name="DefaultChord">
/// <para>
/// The chord the module suggests, as text — "Ctrl+Alt+Space". A <b>default</b>, not a claim: user
/// settings may replace it, and the module's code neither knows nor cares which chord it ended up
/// with.
/// </para>
/// <para>
/// It is text rather than a parsed structure because the chord grammar — parsing, normalising,
/// comparing two spellings of the same combination, refusing a global chord with no modifier — is
/// Conduit Core work that has not been written. Parsing belongs at registration, where a bad chord
/// becomes a refusal with a reason rather than an exception in a module.
/// </para>
/// </param>
public sealed record HotkeyIntent(
    TriggerIntentId Id,
    CapabilityId Capability,
    string DefaultChord)
    : TriggerIntent(Id, Capability);

/// <summary>
/// The desktop transitions a module can ask to hear about.
/// </summary>
/// <remarks>
/// A mask, not a subscription list, because these are combined far more often than they are used
/// alone.
/// </remarks>
[Flags]
public enum WindowEventKinds
{
    /// <summary>Nothing.</summary>
    None = 0,

    /// <summary>A top-level window appeared.</summary>
    Created = 1 << 0,

    /// <summary>A top-level window went away.</summary>
    Destroyed = 1 << 1,

    /// <summary>The foreground window changed.</summary>
    FocusChanged = 1 << 2,

    /// <summary>A move or resize began. Always paired with <see cref="MoveSizeEnded"/>.</summary>
    MoveSizeStarted = 1 << 3,

    /// <summary>A move or resize finished, including when it was cancelled.</summary>
    MoveSizeEnded = 1 << 4,

    /// <summary>A window moved. High frequency during a drag; coalesced without apology.</summary>
    Moved = 1 << 5,

    /// <summary>A window was minimised.</summary>
    Minimized = 1 << 6,

    /// <summary>A window was restored from minimised or maximised.</summary>
    Restored = 1 << 7,
}

/// <summary>
/// "Wake me when the desktop changes in one of these ways."
/// </summary>
/// <remarks>
/// <para>
/// <b>What this delivers is a hint, not a log.</b> The guarantee is deliberately weak: "something
/// changed, it is worth reading the desktop again". Events are coalesced and rate-limited, and the
/// stream is explicitly not complete or ordered. A complete guaranteed stream would need unbounded
/// buffering fed from a thread that must never block, and those two requirements cannot both be
/// met — so the guarantee that would have to be broken is declared absent up front instead of
/// discovered later.
/// </para>
/// <para>
/// One exception is load-bearing: <see cref="WindowEventKinds.MoveSizeStarted"/> and
/// <see cref="WindowEventKinds.MoveSizeEnded"/> are delivered as a pair. A drag-to-snap module puts
/// an overlay on the screen at start and takes it down at end; a dropped end event leaves that
/// overlay on the user's desktop forever, which is not a bug in a feature, it is the toolbox making
/// the machine worse.
/// </para>
/// </remarks>
/// <param name="Id">The intent's permanent id.</param>
/// <param name="Capability">The capability these events dispatch to.</param>
/// <param name="Mask">Which transitions to hear about.</param>
public sealed record WindowEventIntent(
    TriggerIntentId Id,
    CapabilityId Capability,
    WindowEventKinds Mask)
    : TriggerIntent(Id, Capability);

/// <summary>
/// How a repeating schedule measures its next fire.
/// </summary>
public enum ScheduleDrift
{
    /// <summary>
    /// The n-th fire is at start plus n intervals, so a late fire does not push its successors.
    /// What a pomodoro wants: twelve intervals later, it should still line up with the clock.
    /// </summary>
    FixedRate,

    /// <summary>
    /// The next fire is measured from the end of the previous handler. What a polling loop wants.
    /// Getting this backwards is invisible for an hour and obvious after eight.
    /// </summary>
    FixedDelay,
}

/// <summary>
/// What to do about fires that were missed because the machine was asleep or the process was not
/// running.
/// </summary>
/// <remarks>
/// There is no correct universal answer here — only a declared one. That is why it is a required
/// part of the declaration rather than a default buried in the fabric.
/// </remarks>
public enum MissedFirePolicy
{
    /// <summary>Pretend they did not happen and resume from now.</summary>
    Skip,

    /// <summary>Fire once, immediately, however many were missed.</summary>
    FireOnce,

    /// <summary>Fire each missed occurrence, up to a bound the fabric imposes.</summary>
    FireAll,
}

/// <summary>
/// "Wake me every so often."
/// </summary>
/// <remarks>
/// <para>
/// Interval schedules run on a <b>monotonic</b> clock, never the wall clock. A twenty-five minute
/// timer must not become eighty-five minutes because the system clock jumped an hour for a
/// time-zone transition or a clock sync.
/// </para>
/// <para>
/// docs/CONDUIT.md §3.3 specifies two further shapes — a wall-clock time of day, and a one-shot at
/// an instant — that are not modelled here. A wall-clock schedule has to define what it does on the
/// day a local time happens twice and the day it does not happen at all, and that is a decision
/// worth making with a real consumer and a real test rather than in advance.
/// </para>
/// </remarks>
/// <param name="Id">The intent's permanent id.</param>
/// <param name="Capability">The capability each fire dispatches to.</param>
/// <param name="Interval">The gap between fires. Must be positive; a non-positive interval is a
/// malformed declaration and is refused at registration rather than becoming a busy loop.</param>
/// <param name="Drift">How the next fire is measured.</param>
/// <param name="MissedFire">What to do about fires missed while asleep or not running.</param>
public sealed record ScheduleIntent(
    TriggerIntentId Id,
    CapabilityId Capability,
    TimeSpan Interval,
    ScheduleDrift Drift,
    MissedFirePolicy MissedFire)
    : TriggerIntent(Id, Capability);

/// <summary>
/// "Put an item in the tray menu, and wake me when it is chosen."
/// </summary>
/// <remarks>
/// There is one tray icon and one tray menu, owned by the host. Modules contribute items to it;
/// they do not each get an icon. A toolbox that installs six tray icons has stopped being one
/// thing. Items are declared, not drawn.
/// </remarks>
/// <param name="Id">The intent's permanent id.</param>
/// <param name="Capability">The capability the menu item invokes.</param>
/// <param name="Label">The menu text, grouped under the declaring module's name.</param>
public sealed record TrayActionIntent(
    TriggerIntentId Id,
    CapabilityId Capability,
    string Label)
    : TriggerIntent(Id, Capability);
