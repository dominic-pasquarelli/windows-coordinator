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
/// settings-only. A <see cref="CapabilityKind.Reading"/> is never bindable, and the constructor
/// refuses that combination rather than trusting every caller to remember it.
/// </param>
public sealed record Capability(
    CapabilityId Id,
    CapabilityKind Kind,
    string Label,
    bool Bindable = true)
{
    /// <summary>
    /// What kind of value this holds. <b>Get-only on purpose</b> — see <see cref="Bindable"/>.
    /// </summary>
    public CapabilityKind Kind { get; } = Kind;

    /// <summary>
    /// Whether this capability may be a binding target. Validated at construction against
    /// <see cref="Kind"/>, and <b>get-only on purpose</b>.
    /// </summary>
    /// <remarks>
    /// <para>
    /// A <see cref="CapabilityKind.Reading"/> reports a value the module observes; there is nothing
    /// for a chord to invoke, so binding one is meaningless rather than merely unusual. The rule
    /// used to live only in this doc-comment while the parameter defaulted to
    /// <see langword="true"/> — so the shortest possible declaration,
    /// <c>new Capability(id, CapabilityKind.Reading, "…")</c>, produced exactly the state the
    /// comment forbade. An invariant stated in prose beside a default that violates it is not an
    /// invariant.
    /// </para>
    /// <para>
    /// <b>Why <see cref="Kind"/> and this property are get-only rather than <c>init</c>.</b> A
    /// validating initializer alone would not be enough: a record's <c>with</c> expression runs the
    /// compiler-generated copy constructor, which assigns fields directly and does <i>not</i> re-run
    /// property initializers. <c>capability with { Kind = CapabilityKind.Reading }</c> would
    /// therefore copy <c>Bindable = true</c> straight past the check and reconstruct the illegal
    /// state the primary constructor just refused. Making both members get-only removes that path at
    /// compile time — the constructor becomes the only way to choose this pair, and the constructor
    /// validates. Changing a capability's kind is not an edit anyway; it is a different capability.
    /// </para>
    /// <para>
    /// This throws rather than silently coercing to <see langword="false"/>. A quiet correction
    /// would hide a real modelling mistake — the author meant a different kind, or a different
    /// binding — and this project's evidence standard is specifically about not letting a wrong
    /// belief pass as success.
    /// </para>
    /// </remarks>
    /// <exception cref="ArgumentException">
    /// The kind is <see cref="CapabilityKind.Reading"/> and the capability was declared bindable.
    /// </exception>
    public bool Bindable { get; } = Kind is CapabilityKind.Reading && Bindable
        ? throw new ArgumentException(
            $"capability '{Id.Value}' is a {nameof(CapabilityKind.Reading)}, which is never " +
            "bindable — a reading reports a value, so there is nothing for a binding to invoke. " +
            $"Pass {nameof(Bindable)}: false, or use a different {nameof(CapabilityKind)}.",
            nameof(Bindable))
        : Bindable;

    /// <summary>
    /// Human-facing text. Never load-bearing; rename at will — but never blank, because the label is
    /// what a person sees in the settings surface and in a binding-conflict report, and a blank one
    /// makes the conflict unreadable.
    /// </summary>
    /// <exception cref="ArgumentException">The label is null, empty, or whitespace.</exception>
    public string Label { get; } = string.IsNullOrWhiteSpace(Label)
        ? throw new ArgumentException(
            $"capability '{Id.Value}' has a blank label.", nameof(Label))
        : Label;
}
