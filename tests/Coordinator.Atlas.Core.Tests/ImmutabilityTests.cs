using Coordinator.Atlas;
using Xunit;

namespace Coordinator.Atlas.Tests;

/// <summary>
/// The coherent-snapshot guarantee, tested as behaviour rather than asserted in a doc-comment.
///
/// The defect these pin: <c>IReadOnlyList&lt;T&gt;</c> says only that <i>this reference</i> offers
/// no mutators. It says nothing about the underlying object. A caller that builds a
/// <c>List&lt;T&gt;</c>, hands it to a snapshot and keeps its own reference can still mutate it
/// afterwards, and every holder of that "snapshot" observes the change — which turns the one type
/// whose entire job is to be a fixed instant into a shared mutable cache with a reassuring name.
///
/// Each test therefore mutates the ORIGINAL list after construction and asserts the constructed
/// value did not move. Every one of them fails if the defensive copy is removed.
/// </summary>
public sealed class ImmutabilityTests
{
    private static LayoutCell Cell(string id) => new(id, 0.0, 0.0, 1.0, 1.0);

    private static MonitorInfo Monitor(string id) =>
        new(new MonitorId(id), new Rect(0, 0, 1920, 1080), new Rect(0, 0, 1920, 1040), 1.0, true);

    private static WindowInfo Window(long handle) =>
        new(new WindowRef(handle), new Rect(0, 0, 800, 600), new Rect(0, 0, 800, 600),
            WindowState.Normal, new MonitorId("m1"));

    [Fact]
    public void LayoutTemplateDoesNotSeeLaterMutationOfTheCallersList()
    {
        List<LayoutCell> callersCells = [Cell("a"), Cell("b")];
        LayoutTemplate template = new("t", "Template", callersCells);

        callersCells.Add(Cell("smuggled"));
        callersCells[0] = Cell("replaced");

        Assert.Equal(2, template.Cells.Count);
        Assert.Equal("a", template.Cells[0].Id);
        Assert.Equal("b", template.Cells[1].Id);
    }

    [Fact]
    public void LayoutTemplateDoesNotSeeTheCallersListBeingCleared()
    {
        List<LayoutCell> callersCells = [Cell("a"), Cell("b")];
        LayoutTemplate template = new("t", "Template", callersCells);

        callersCells.Clear();

        Assert.Equal(2, template.Cells.Count);
    }

    [Fact]
    public void ZoneSetDoesNotSeeLaterMutationOfTheCallersList()
    {
        List<ZoneRect> callersZones =
        [
            new ZoneRect("z0", 0, new Rect(0, 0, 500, 800), CoordinateSpace.PhysicalVirtualScreen),
        ];

        ZoneSet zoneSet = new(
            new LayoutTemplate("t", "Template", [Cell("a")]),
            new Rect(0, 0, 1000, 800),
            TopologyGeneration: 1,
            callersZones);

        callersZones.Add(
            new ZoneRect("smuggled", 1, new Rect(0, 0, 10, 10), CoordinateSpace.PhysicalVirtualScreen));

        Assert.Single(zoneSet.Zones);
        Assert.Equal("z0", zoneSet.Zones[0].ZoneId);
    }

    /// <summary>
    /// The one that would actually hurt: a zone set is handed to a drag loop that hit-tests it on
    /// every mouse move. Geometry that changes underneath that loop puts a window somewhere nobody
    /// chose, and it does so intermittently.
    /// </summary>
    [Fact]
    public void AResolvedZoneSetIsUnaffectedByMutatingTheTemplateSourceList()
    {
        List<LayoutCell> callersCells = [Cell("only")];
        LayoutTemplate template = new("t", "Template", callersCells);

        LayoutResult result = LayoutMath.Resolve(template, new Rect(0, 0, 1000, 800), 1);
        ZoneSet zones = Assert.IsType<LayoutResult.Resolved>(result).ZoneSet;

        callersCells.Add(Cell("added-after-resolution"));

        Assert.Single(zones.Zones);
        Assert.Single(zones.Template.Cells);
    }

    [Fact]
    public void DesktopSnapshotDoesNotSeeLaterMutationOfTheCallersLists()
    {
        List<MonitorInfo> callersMonitors = [Monitor("m1")];
        List<WindowInfo> callersWindows = [Window(1)];

        DesktopSnapshot snapshot = new(callersMonitors, callersWindows, CapturedAtTicks: 100,
                                       TopologyGeneration: 3);

        callersMonitors.Add(Monitor("m2"));
        callersWindows.Clear();

        Assert.Single(snapshot.Monitors);
        Assert.Equal("m1", snapshot.Monitors[0].Id.Value);
        Assert.Single(snapshot.Windows);
    }

    [Fact]
    public void DesktopSnapshotRejectsNullCollections()
    {
        Assert.Throws<ArgumentNullException>(() =>
            new DesktopSnapshot(null!, [], CapturedAtTicks: 0, TopologyGeneration: 0));
        Assert.Throws<ArgumentNullException>(() =>
            new DesktopSnapshot([], null!, CapturedAtTicks: 0, TopologyGeneration: 0));
    }
}
