// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Atlas;

/// <summary>
/// A monitor's identity, stable for as long as the display arrangement is. Opaque: nothing outside
/// the Windows adapter may assume anything about its contents.
/// </summary>
/// <param name="Value">The id text, assigned by whatever enumerated the display.</param>
public readonly record struct MonitorId(string Value);

/// <summary>
/// A reference to a top-level window, opaque and comparable.
/// </summary>
/// <remarks>
/// <para>
/// Opaque on purpose: Core never sees a real window handle, never mentions the platform's handle
/// type, and cannot accidentally do anything to a window. Only the Windows adapter knows how to
/// turn one of these back into something the operating system will act on.
/// </para>
/// <para>
/// Comparable so a module can hold one across snapshots and ask "is this still the window I meant".
/// Note that it can go stale — the window may have closed between a snapshot being taken and
/// anything being done about it, and that is an ordinary expected outcome rather than an error.
/// </para>
/// </remarks>
/// <param name="Value">The opaque value. Meaningful only to the Windows adapter that produced it.</param>
public readonly record struct WindowRef(long Value);

/// <summary>How a window is currently displayed.</summary>
public enum WindowState
{
    /// <summary>Ordinary restored window with real geometry.</summary>
    Normal,

    /// <summary>Minimised. Its reported geometry is not where a user would say it is.</summary>
    Minimized,

    /// <summary>Maximised. Must generally be restored before it can be positioned.</summary>
    Maximized,
}

/// <summary>
/// One monitor, as it was at the instant the snapshot was taken.
/// </summary>
/// <param name="Id">The monitor's identity within this arrangement.</param>
/// <param name="Bounds">
/// The whole monitor, in <see cref="CoordinateSpace.PhysicalVirtualScreen"/>. Negative coordinates
/// are normal for any display arranged left of or above the primary one.
/// </param>
/// <param name="WorkArea">
/// The usable part — the monitor minus the taskbar and any registered application bars, in the same
/// space. <b>This is not the same rectangle as <paramref name="Bounds"/></b> and confusing the two
/// puts a window underneath the taskbar. Layout is always computed against the work area.
/// </param>
/// <param name="ScaleFactor">
/// This monitor's scaling as a multiplier, computed as its DPI divided by ninety-six: 1.0 at 100%,
/// 1.5 at 150%. Per monitor, never per machine — a mixed arrangement is the ordinary case, and any
/// conversion between physical and effective pixels has to use the scale factor of the monitor the
/// window is actually on, not the primary's.
/// </param>
/// <param name="IsPrimary">Whether this is the primary monitor, which defines the virtual-screen origin.</param>
public sealed record MonitorInfo(
    MonitorId Id,
    Rect Bounds,
    Rect WorkArea,
    double ScaleFactor,
    bool IsPrimary);

/// <summary>
/// One window, as it was at the instant the snapshot was taken.
/// </summary>
/// <remarks>
/// <b>Two rectangles, and it is not redundancy.</b> On modern Windows the geometry a window reports
/// includes an invisible resize border — a few pixels of transparent frame outside what the user can
/// see. Position a window flush to a monitor edge using that rectangle and it appears to overhang;
/// align two windows edge to edge and they appear to overlap. Layout therefore reasons about
/// <paramref name="VisibleBounds"/>, and placement compensates by the difference between the two.
/// The difference varies by window, by state, and by Windows version, so it is measured rather than
/// assumed constant. This is the concrete mechanism behind "the window is twenty pixels off".
/// </remarks>
/// <param name="Window">The opaque reference to this window.</param>
/// <param name="Bounds">
/// The geometry rectangle the platform reports and a placement call accepts, in
/// <see cref="CoordinateSpace.PhysicalVirtualScreen"/>. Includes the invisible frame.
/// </param>
/// <param name="VisibleBounds">
/// The rectangle a human perceives, in the same space. What layout and alignment should use.
/// </param>
/// <param name="State">Normal, minimised, or maximised.</param>
/// <param name="Monitor">
/// The monitor that owns this window. For a window straddling two, the rule is "the monitor with
/// the largest intersection" — decided once, here, because it is exactly the sort of thing that
/// otherwise gets reimplemented three times slightly differently.
/// </param>
public sealed record WindowInfo(
    WindowRef Window,
    Rect Bounds,
    Rect VisibleBounds,
    WindowState State,
    MonitorId Monitor);

/// <summary>
/// Everything about the desktop, all true at the same instant. The unit of reading.
/// </summary>
/// <remarks>
/// <para>
/// <b>A module reads one snapshot; it does not issue queries.</b> The desktop changes while you are
/// reading it — a window crosses a monitor boundary, a laptop is undocked, a projector is plugged
/// in, the taskbar auto-hides. Code that asks "which monitor is this window on?" and then "what is
/// that monitor's work area?" as two separate calls can get an answer pair that never coexisted, at
/// which point the arithmetic is perfect and the result is wrong. Nobody can debug that: it is
/// intermittent, it has no exception and no log line, and its trigger is a human hand.
/// </para>
/// <para>
/// So the lookups on this type are lookups <i>inside the value</i>. Nothing can change between two
/// of them, because there is nothing to change: a snapshot is immutable, re-readable, and has no
/// refresh.
/// </para>
/// <para>
/// <b>Stamped, but not self-aging.</b> There is deliberately no age property here, and Atlas never
/// tells a consumer how old a snapshot is. An age computed by the producer is a claim about a moment
/// that has already passed by the time anyone reads it, and it becomes more wrong the longer the
/// value is held. Freshness is computed by the reader, from its own monotonic clock, at the moment
/// it actually matters — which also lets a drag overlay and a placement operation hold different,
/// equally valid thresholds without Atlas guessing for either of them.
/// </para>
/// </remarks>
/// <param name="Monitors">Every monitor in the arrangement.</param>
/// <param name="Windows">
/// Every window a user would say is open. That predicate is a real decision, not a detail: a naive
/// enumeration returns hundreds of things nobody has ever seen — tool windows, owned dialogs,
/// zero-size helpers, message-only windows, and cloaked windows, which are how an application on
/// another virtual desktop stays enumerable while not being on screen at all. The filtering is pure
/// logic over flags the Windows adapter collects, so it is one shared answer, testable against a
/// table of cases, rather than something two modules get subtly and differently wrong.
/// </param>
/// <param name="CapturedAtTicks">
/// When this snapshot was taken, in ticks from a <b>monotonic</b> source. Never wall-clock time:
/// system time jumps on clock sync, on time-zone transitions, and whenever someone sets the clock,
/// and a freshness check against a jumping clock can decide that a snapshot taken one second ago is
/// an hour old.
/// </param>
/// <param name="TopologyGeneration">
/// Bumped whenever the <i>shape</i> of the desktop changes — a monitor added or removed, a
/// resolution or scale factor changed, a work area resized by the taskbar. The rule that makes it
/// worth carrying: <b>geometry computed against generation N must not be applied at generation
/// N+1</b>; it must be recomputed. A zone set derived from a work area that no longer exists is not
/// approximately right, it is arbitrary — and comparing one integer makes that mistake detectable
/// instead of invisible.
/// </param>
public sealed record DesktopSnapshot(
    IReadOnlyList<MonitorInfo> Monitors,
    IReadOnlyList<WindowInfo> Windows,
    long CapturedAtTicks,
    int TopologyGeneration)
{
    /// <summary>
    /// The primary monitor, or null if this snapshot contains none — which should be impossible on
    /// a real desktop and is therefore worth surfacing rather than assuming away.
    /// </summary>
    public MonitorInfo? Primary => Monitors.FirstOrDefault(m => m.IsPrimary);

    /// <summary>
    /// Find a monitor by id, within this snapshot.
    /// </summary>
    /// <param name="id">The monitor to find.</param>
    /// <returns>The monitor, or null if this snapshot does not contain it.</returns>
    public MonitorInfo? FindMonitor(MonitorId id) => Monitors.FirstOrDefault(m => m.Id == id);

    /// <summary>
    /// Find a window by reference, within this snapshot.
    /// </summary>
    /// <param name="window">The window to find.</param>
    /// <returns>The window, or null if it is not in this snapshot.</returns>
    public WindowInfo? FindWindow(WindowRef window) =>
        Windows.FirstOrDefault(w => w.Window == window);

    /// <summary>
    /// The monitor a window is on.
    /// </summary>
    /// <param name="window">The window.</param>
    /// <returns>Its monitor, or null if either the window or its monitor is absent here.</returns>
    /// <remarks>
    /// This is a pure lookup inside the snapshot, not a fresh question to the operating system —
    /// which is the entire reason the snapshot type exists. Two calls against the same snapshot can
    /// never disagree.
    /// </remarks>
    public MonitorInfo? MonitorOf(WindowRef window)
    {
        WindowInfo? info = FindWindow(window);
        return info is null ? null : FindMonitor(info.Monitor);
    }
}
