// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Conduit;

/// <summary>
/// Why a trigger intent was not granted.
/// </summary>
/// <remarks>
/// Every reason here is something a person can be told. That is the test a new member has to pass:
/// if the honest rendering of a refusal is "it did not work", the reason is not specific enough to
/// exist.
/// </remarks>
public enum RefusalReason
{
    /// <summary>
    /// Another module already holds this, and won the arbitration. The winner is named in the
    /// refusal so the settings surface can say who, rather than making the user guess.
    /// </summary>
    AlreadyHeldByAnotherModule,

    /// <summary>
    /// Something outside this application holds it — another program, or the operating system.
    /// This is the arbitration layer above ours and it is the stronger authority.
    /// </summary>
    HeldOutsideThisApplication,

    /// <summary>
    /// The system reserves it and will never yield it. Refusing at registration turns a permanent
    /// mystery into a message.
    /// </summary>
    ReservedBySystem,

    /// <summary>
    /// The declaration itself is invalid — a global chord with no modifier (it would swallow a bare
    /// keystroke from every application on the machine), a chord with no key, a non-positive
    /// interval.
    /// </summary>
    Malformed,

    /// <summary>The user turned this binding off. A refusal, not a failure.</summary>
    DisabledByUser,

    /// <summary>A bounded table is full. Rare, and better named than mistaken for one of the above.</summary>
    ResourceExhausted,
}

/// <summary>
/// The answer to a registration request. There is no method that installs a trigger; there is a
/// method that tells you what happened.
/// </summary>
/// <remarks>
/// <para>
/// <b>This shape is the most important thing in the pillar.</b> Registration is a request, and the
/// answer is a value the caller has to look at. The failure mode being designed out is the one
/// where a module believes it holds a chord it does not hold — a feature that is installed,
/// enabled, documented, and silently does nothing, which the user cannot distinguish from their own
/// misunderstanding.
/// </para>
/// <para>
/// <b>A refusal is never a silent no-op.</b> It is returned to the module, recorded against it in
/// the registry, and surfaced next to the binding that lost, naming the winner.
/// </para>
/// <para>
/// <b>A refusal is not fatal either.</b> A module whose intent was refused keeps running with
/// reduced function and says so. Only the module knows whether one refused chord makes it useless,
/// so only the module gets to decide.
/// </para>
/// <para>
/// <b>Arbitration is deterministic across restarts.</b> Reserved system combinations are refused
/// outright; an explicit user binding always beats a module default; and module defaults are
/// ordered by permanent module id — never by load order or discovery order. A chord that works on
/// Tuesday and not on Wednesday is unfalsifiable and unreportable, which makes it worse than one
/// that never works at all.
/// </para>
/// <para>
/// <b>Not modelled yet: the lease.</b> docs/CONDUIT.md §4 specifies that a grant is revocable — the
/// user rebinds, a session change forces re-registration, and re-registration can fail differently
/// the second time — so a real grant carries state and notifies its holder when that state changes.
/// A revocation mechanism with nothing to revoke and nobody to notify would be shape invented from
/// nothing, so <see cref="Granted"/> is a plain acknowledgement today. It is expected to grow, and
/// growing it is an additive change.
/// </para>
/// </remarks>
public abstract record TriggerRegistration
{
    /// <summary>The intent is registered and may fire.</summary>
    /// <param name="Intent">Which intent was granted.</param>
    public sealed record Granted(TriggerIntentId Intent) : TriggerRegistration;

    /// <summary>The intent will not fire, and here is the reason a person can be told.</summary>
    /// <param name="Intent">Which intent was refused.</param>
    /// <param name="Reason">Why.</param>
    /// <param name="HeldByModuleId">
    /// The permanent id of the module that won, when <paramref name="Reason"/> is
    /// <see cref="RefusalReason.AlreadyHeldByAnotherModule"/>; otherwise null. It is the module id
    /// rather than a display name because the display name is free to change and this value ends up
    /// in logs and settings surfaces that have to keep meaning the same thing.
    /// </param>
    public sealed record Refused(
        TriggerIntentId Intent,
        RefusalReason Reason,
        string? HeldByModuleId) : TriggerRegistration;
}
