using Coordinator.Atlas;
using Xunit;

namespace Coordinator.Atlas.Tests;

/// <summary>
/// The zone arithmetic. Pure values in, pure values out — no desktop anywhere in this file, which
/// is the property that lets it run on a Linux CI runner.
/// </summary>
public sealed class LayoutMathTests
{
    private const int Generation = 7;

    private static LayoutTemplate Columns(int count, int padding = 0, int gap = 0)
    {
        List<LayoutCell> cells = [];
        for (int i = 0; i < count; i++)
        {
            cells.Add(new LayoutCell($"c{i}", (double)i / count, 0.0, (double)(i + 1) / count, 1.0));
        }

        return new LayoutTemplate($"cols{count}", $"{count} columns", cells, padding, gap);
    }

    private static ZoneSet Resolved(LayoutTemplate template, Rect workArea)
    {
        LayoutResult result = LayoutMath.Resolve(template, workArea, Generation);
        LayoutResult.Resolved resolved = Assert.IsType<LayoutResult.Resolved>(result);
        return resolved.ZoneSet;
    }

    // --- the seam property ------------------------------------------------------------------

    /// <summary>
    /// Adjacent zones must share an edge EXACTLY, at every width — no one-pixel seam of wallpaper
    /// between two snapped windows, and no one-pixel overlap.
    ///
    /// This is the property LayoutMath's remarks single out as the first thing to test, and it is
    /// the property a naive implementation breaks: computing each zone's width independently and
    /// laying the zones end to end accumulates rounding error, so the seams land differently
    /// depending on the work area's width. Mapping every edge through one rounding step against the
    /// same padded area cannot do that, because the same fraction always maps to the same pixel.
    ///
    /// The width range is swept rather than sampled because the failure is width-dependent: a
    /// single convenient width (say 1920, divisible by 3) would pass against the naive
    /// implementation too, and a test that passes against the bug it exists to catch is decoration.
    /// </summary>
    [Theory]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(5)]
    public void AdjacentZonesShareAnExactEdgeAtEveryWidth(int columns)
    {
        LayoutTemplate template = Columns(columns);

        for (int width = 101; width <= 400; width++)
        {
            Rect workArea = new(0, 0, width, 900);
            ZoneSet zones = Resolved(template, workArea);

            Assert.Equal(columns, zones.Zones.Count);
            Assert.Equal(workArea.Left, zones.Zones[0].Bounds.Left);
            Assert.Equal(workArea.Right, zones.Zones[^1].Bounds.Right);

            for (int i = 0; i < columns - 1; i++)
            {
                Assert.Equal(zones.Zones[i].Bounds.Right, zones.Zones[i + 1].Bounds.Left);
            }
        }
    }

    /// <summary>
    /// Guard the guard: prove the sweep above would actually catch the naive implementation, rather
    /// than trusting that it would. Independently-rounded widths laid end to end do NOT tile a
    /// 100-pixel area in three, so at least one width in the sweep is a real discriminator.
    /// </summary>
    [Fact]
    public void IndependentlyRoundedWidthsWouldNotTileTheArea()
    {
        const int width = 100;
        const int columns = 3;

        int naiveTotal = 0;
        for (int i = 0; i < columns; i++)
        {
            naiveTotal += (int)Math.Round((double)width / columns, MidpointRounding.AwayFromZero);
        }

        Assert.NotEqual(width, naiveTotal);

        ZoneSet zones = Resolved(Columns(columns), new Rect(0, 0, width, 900));
        int actualTotal = zones.Zones.Sum(z => z.Bounds.Width);
        Assert.Equal(width, actualTotal);
    }

    // --- coordinate handling ----------------------------------------------------------------

    /// <summary>
    /// A monitor arranged to the LEFT of the primary has negative coordinates. Resolution is
    /// relative to the work area's own origin, so this needs no special case — and if someone ever
    /// "fixes" it by clamping to zero, every zone on that monitor lands on the wrong screen.
    /// </summary>
    [Fact]
    public void ResolvesAgainstAMonitorWithNegativeCoordinates()
    {
        Rect workArea = new(-1920, -200, 0, 880);
        ZoneSet zones = Resolved(Columns(2), workArea);

        Assert.Equal(-1920, zones.Zones[0].Bounds.Left);
        Assert.Equal(0, zones.Zones[^1].Bounds.Right);
        Assert.Equal(zones.Zones[0].Bounds.Right, zones.Zones[1].Bounds.Left);
        Assert.All(zones.Zones, z => Assert.False(z.Bounds.IsEmpty));
    }

    /// <summary>
    /// Padding insets the whole layout; the gap is inset on INTERIOR edges only, so the outside of
    /// the layout stays flush with the padded area while neighbours sit apart.
    /// </summary>
    [Fact]
    public void GapAppliesToInteriorEdgesOnlyAndPaddingToTheOutside()
    {
        const int padding = 10;
        const int gap = 8;
        Rect workArea = new(0, 0, 1000, 800);
        ZoneSet zones = Resolved(Columns(2, padding, gap), workArea);

        Assert.Equal(workArea.Left + padding, zones.Zones[0].Bounds.Left);
        Assert.Equal(workArea.Right - padding, zones.Zones[1].Bounds.Right);
        Assert.Equal(workArea.Top + padding, zones.Zones[0].Bounds.Top);
        Assert.Equal(workArea.Bottom - padding, zones.Zones[0].Bounds.Bottom);

        int separation = zones.Zones[1].Bounds.Left - zones.Zones[0].Bounds.Right;
        Assert.Equal(gap / 2 * 2, separation);
    }

    [Fact]
    public void CarriesTheTopologyGenerationItWasComputedAt()
    {
        ZoneSet zones = Resolved(Columns(2), new Rect(0, 0, 800, 600));
        Assert.Equal(Generation, zones.TopologyGeneration);
    }

    // --- refusals ----------------------------------------------------------------------------

    /// <summary>
    /// Every refusal is a value, not an exception, and every refusal names a reason. The
    /// alternative — a zero-width or negative rectangle escaping into a placement call — does not
    /// throw; it just puts a window somewhere nonsensical with no error anywhere.
    /// </summary>
    [Fact]
    public void RefusesAnEmptyTemplate()
    {
        LayoutTemplate empty = new("none", "No cells", []);
        LayoutResult.Refused refused =
            Assert.IsType<LayoutResult.Refused>(LayoutMath.Resolve(empty, new Rect(0, 0, 800, 600), 1));
        Assert.Equal(LayoutRefusalReason.TemplateEmpty, refused.Reason);
        Assert.False(string.IsNullOrWhiteSpace(refused.Detail));
    }

    [Theory]
    [InlineData(0, 0, 0, 0)]
    [InlineData(100, 100, 100, 200)]
    [InlineData(100, 100, 50, 200)]
    public void RefusesAnEmptyOrInvertedWorkArea(int left, int top, int right, int bottom)
    {
        LayoutResult.Refused refused = Assert.IsType<LayoutResult.Refused>(
            LayoutMath.Resolve(Columns(2), new Rect(left, top, right, bottom), 1));
        Assert.Equal(LayoutRefusalReason.WorkAreaEmpty, refused.Reason);
    }

    [Theory]
    [InlineData(-0.1, 0.0, 0.5, 1.0)]
    [InlineData(0.0, 0.0, 1.1, 1.0)]
    [InlineData(0.6, 0.0, 0.4, 1.0)]
    [InlineData(0.0, 0.5, 1.0, 0.5)]
    public void RefusesACellOutsideTheUnitSquareOrInverted(
        double left, double top, double right, double bottom)
    {
        LayoutTemplate template = new("bad", "Bad cell", [new LayoutCell("c", left, top, right, bottom)]);
        LayoutResult.Refused refused = Assert.IsType<LayoutResult.Refused>(
            LayoutMath.Resolve(template, new Rect(0, 0, 800, 600), 1));
        Assert.Equal(LayoutRefusalReason.CellOutOfRange, refused.Reason);
        Assert.Contains("c", refused.Detail, StringComparison.Ordinal);
    }

    [Fact]
    public void RefusesWhenPaddingLeavesNothing()
    {
        LayoutResult.Refused refused = Assert.IsType<LayoutResult.Refused>(
            LayoutMath.Resolve(Columns(2, padding: 200), new Rect(0, 0, 300, 300), 1));
        Assert.Equal(LayoutRefusalReason.WorkAreaTooSmall, refused.Reason);
    }

    // --- hit testing --------------------------------------------------------------------------

    [Fact]
    public void HitTestFindsTheZoneContainingThePoint()
    {
        ZoneSet zones = Resolved(Columns(2), new Rect(0, 0, 1000, 800));

        ZoneRect? left = LayoutMath.HitTest(zones, 10, 10);
        ZoneRect? right = LayoutMath.HitTest(zones, 990, 790);

        Assert.NotNull(left);
        Assert.NotNull(right);
        Assert.Equal("c0", left!.ZoneId);
        Assert.Equal("c1", right!.ZoneId);
    }

    [Fact]
    public void HitTestReturnsNullOutsideEveryZone()
    {
        ZoneSet zones = Resolved(Columns(2), new Rect(0, 0, 1000, 800));
        Assert.Null(LayoutMath.HitTest(zones, -1, 400));
        Assert.Null(LayoutMath.HitTest(zones, 1000, 400));
        Assert.Null(LayoutMath.HitTest(zones, 500, 800));
    }

    /// <summary>
    /// Overlapping zones are permitted, and template order decides — because template order is the
    /// author's declared intent, and "whichever we happen to enumerate first" is not.
    /// </summary>
    [Fact]
    public void HitTestPrefersTheEarlierZoneWhenZonesOverlap()
    {
        LayoutTemplate overlapping = new("ov", "Overlapping",
        [
            new LayoutCell("under", 0.0, 0.0, 1.0, 1.0),
            new LayoutCell("over", 0.0, 0.0, 0.5, 1.0),
        ]);

        ZoneSet zones = Resolved(overlapping, new Rect(0, 0, 1000, 800));
        ZoneRect? hit = LayoutMath.HitTest(zones, 100, 100);

        Assert.NotNull(hit);
        Assert.Equal("under", hit!.ZoneId);
    }
}
