using Coordinator.Platform;
using Xunit;

namespace Coordinator.Platform.Tests;

/// <summary>
/// The one invariant <see cref="Capability"/> has: a <see cref="CapabilityKind.Reading"/> is never
/// bindable.
///
/// It used to be stated only in a doc-comment, three lines above a parameter that defaulted to
/// <c>Bindable = true</c> — so the shortest declaration anyone would naturally write produced
/// exactly the state the comment forbade. These tests exist so the rule is enforced by the type
/// rather than by whoever remembers to read the comment.
/// </summary>
public sealed class CapabilityTests
{
    private static CapabilityId Id(string value) => new(value);

    [Fact]
    public void RefusesABindableReading()
    {
        // The natural, shortest declaration — the one that used to silently produce an illegal
        // capability by taking the default.
        ArgumentException error = Assert.Throws<ArgumentException>(
            () => new Capability(Id("zones.activeLayout"), CapabilityKind.Reading, "Active layout"));

        Assert.Contains("Reading", error.Message, StringComparison.Ordinal);
        Assert.Contains("zones.activeLayout", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void RefusesABindableReadingDeclaredExplicitly()
    {
        Assert.Throws<ArgumentException>(
            () => new Capability(Id("zones.activeLayout"), CapabilityKind.Reading, "Active layout",
                                 Bindable: true));
    }

    [Fact]
    public void AcceptsAReadingThatIsNotBindable()
    {
        Capability reading = new(Id("zones.activeLayout"), CapabilityKind.Reading, "Active layout",
                                 Bindable: false);

        Assert.False(reading.Bindable);
        Assert.Equal(CapabilityKind.Reading, reading.Kind);
    }

    [Fact]
    public void AnActionIsBindableByDefault()
    {
        Capability action = new(Id("zones.snapCurrent"), CapabilityKind.Action, "Snap current window");

        Assert.True(action.Bindable);
    }

    [Fact]
    public void AcceptsASettingsOnlyAction()
    {
        Capability action = new(Id("zones.reload"), CapabilityKind.Action, "Reload layouts",
                                Bindable: false);

        Assert.False(action.Bindable);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void RefusesABlankLabel(string label)
    {
        Assert.Throws<ArgumentException>(
            () => new Capability(Id("zones.snapCurrent"), CapabilityKind.Action, label));
    }

    /// <summary>
    /// <c>Kind</c> and <c>Bindable</c> are get-only, so <c>with { Kind = … }</c> and
    /// <c>with { Bindable = … }</c> do not compile. That is deliberate and is the reason there is no
    /// runtime test for them: a record's <c>with</c> runs the copy constructor, which assigns fields
    /// directly and never re-runs a validating initializer — so an <c>init</c> accessor here would
    /// have let <c>with</c> rebuild the exact illegal state the constructor refuses. The remaining
    /// members stay copyable, which this test pins.
    /// </summary>
    [Fact]
    public void RemainsCopyableOnMembersThatCarryNoInvariant()
    {
        Capability original = new(Id("zones.snapCurrent"), CapabilityKind.Action, "Snap current window");
        Capability renamed = original with { Id = Id("zones.snapFocused") };

        Assert.Equal("zones.snapFocused", renamed.Id.Value);
        Assert.Equal(original.Kind, renamed.Kind);
        Assert.Equal(original.Bindable, renamed.Bindable);
    }
}
