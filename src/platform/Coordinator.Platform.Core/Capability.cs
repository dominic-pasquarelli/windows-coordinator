// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Platform;

/// <summary>
/// The permanent address of one controllable thing a module exposes: "zones.snap-current",
/// "chrono.pomodoro.minutes".
/// </summary>
/// <remarks>
/// <para>
/// <b>A capability id is a permanent contract. It must never be renamed and never be reused.</b>
/// Saved settings and user-assigned hotkey bindings reference these ids as strings, on machines
/// nobody is looking at. A renamed id is a binding that silently stops working. A reused id is
/// worse: it points somebody's existing binding at a different behaviour, which looks like the
/// application doing something bizarre of its own accord.
/// </para>
/// <para>
/// The rule that follows from that: add new capabilities freely, never break an existing one, and
/// when a capability genuinely dies, leave its id retired and unclaimed rather than recycling it.
/// Labels are free to change; ids are not. Convention is
/// <c>moduleid.thing</c> or <c>moduleid.thing.parameter</c>, all lowercase.
/// </para>
/// <para>
/// It is a wrapper around a string rather than a bare string so that a display label, a module id
/// and a capability id cannot be passed to each other's parameters by accident — the ids are the
/// currency of the whole system and the compiler may as well count it.
/// </para>
/// </remarks>
/// <param name="Value">The id text. Lowercase, dotted, permanent.</param>
public readonly record struct CapabilityId(string Value);

/// <summary>
/// What kind of value a capability holds — the typed half of "every capability is a named, typed
/// binding target".
/// </summary>
/// <remarks>
/// This is a presentational and validation category, not a .NET type. It tells a settings surface
/// what control to render, tells a binding surface what it is allowed to send, and tells the module
/// host what a request is claiming to be — without any of them knowing what the module does.
/// </remarks>
public enum CapabilityKind
{
    /// <summary>Fire-and-forget: do the thing. Carries no value. The natural hotkey target.</summary>
    Action,

    /// <summary>On or off.</summary>
    Toggle,

    /// <summary>A number. Bounds belong with the declaration; see the note on the value spec.</summary>
    Number,

    /// <summary>One of a fixed set of options.</summary>
    Choice,

    /// <summary>Free text.</summary>
    Text,

    /// <summary>
    /// Read-only state the module publishes — the current layout, the time remaining. A write to a
    /// reading must be refused rather than quietly ignored. Readings exist so a module can surface
    /// state to the settings UI without inventing a private side channel to do it.
    /// </summary>
    Reading,
}

/// <summary>
/// One capability a module publishes: a stable id, a typed kind, and a human label.
/// </summary>
/// <remarks>
/// <para>
/// <b>Deliberately absent: the value specification.</b> docs/MODULE_SPEC.md describes a
/// <c>ValueSpec</c> carrying a number's minimum, maximum and step, a choice's options and their
/// labels, and a toggle's default — the declaration that would let a settings form render itself
/// and let the settings store validate a loaded value. It is not written here because nothing
/// consumes it yet: there is no settings surface, no validator, and no binding surface. Building a
/// bounds-and-options type against zero consumers is exactly the speculative abstraction
/// docs/OPERATING_MODEL.md rules out, and the shape it should take will be obvious the moment the
/// first real consumer exists and guesswork the moment before. Adding it later is an additive
/// change to this record; guessing it now and being wrong is a breaking one.
/// </para>
/// <para>
/// Reconciling that omission with MODULE_SPEC's sketch is a named task for the first session with
/// a compiler — see the platform README's "Where to resume".
/// </para>
/// </remarks>
/// <param name="Id">The permanent address. See <see cref="CapabilityId"/>.</param>
/// <param name="Kind">What kind of value this holds.</param>
/// <param name="Label">
/// Human-facing text for the settings surface and for the arbiter's "Zones — Snap current window"
/// style reporting. Never load-bearing; rename at will.
/// </param>
/// <param name="Bindable">
/// Whether this capability may be the target of a hotkey or other trigger binding, or is
/// settings-only. A <see cref="CapabilityKind.Reading"/> is never bindable.
/// </param>
public sealed record Capability(
    CapabilityId Id,
    CapabilityKind Kind,
    string Label,
    bool Bindable = true);
