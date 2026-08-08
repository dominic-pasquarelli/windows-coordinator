// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Atlas;

/// <summary>
/// Which coordinate space a rectangle's numbers are in.
/// </summary>
/// <remarks>
/// <para>
/// Mixing coordinate spaces is <i>the</i> classic window-placement bug, and it is silent: no
/// exception, no error, just a window off by a scale factor or an offset, on one person's monitor
/// arrangement and nobody else's. The defence is that the space is part of the type rather than
/// part of somebody's memory, and that conversion happens exactly once, at the boundary where the
/// operating system's numbers arrive.
/// </para>
/// <para>
/// Two facts about this that catch people, recorded here because this enum is where they are
/// relevant: coordinates on a secondary display are routinely <b>negative</b> — the virtual-screen
/// origin is the top-left of the <i>primary</i> monitor, so a display arranged to its left starts
/// at a negative X, and any code that clamps to non-negative is broken on the first right-to-left
/// setup. And the scale factor is <b>per monitor</b>, not per machine: a 150% laptop panel beside a
/// 100% external display is the ordinary case, so any conversion has to name whose scale factor it
/// used.
/// </para>
/// </remarks>
public enum CoordinateSpace
{
    /// <summary>
    /// Physical device pixels, measured from the virtual-screen origin (the primary monitor's
    /// top-left). This is the space Atlas normalises everything to, and the space every rectangle
    /// in this project speaks unless its own documentation says otherwise.
    /// </summary>
    PhysicalVirtualScreen,

    /// <summary>
    /// Physical device pixels measured from one monitor's own top-left corner. Occasionally the
    /// natural space to think in; never the space anything is stored in.
    /// </summary>
    PhysicalMonitorLocal,

    /// <summary>
    /// Effective pixels (device-independent units, one ninety-sixth of an inch), which is what a
    /// UI framework's layout speaks. Core should not hold one of these without also holding the
    /// scale factor that produced it; conversion belongs at the Windows boundary.
    /// </summary>
    Effective,
}

/// <summary>
/// An axis-aligned rectangle in integer pixels.
/// </summary>
/// <remarks>
/// <para>
/// <b>Half-open by definition: the rectangle covers Left up to but not including Right, and Top up
/// to but not including Bottom.</b> That is not a detail, it is the property that makes two
/// adjacent zones share an exact edge with neither a one-pixel seam nor a one-pixel overlap — the
/// hairline of wallpaper between two snapped windows that makes a tool feel cheap. Every
/// containment and adjacency question in this project is answered under this convention, so it is
/// stated once, here, and relied on everywhere.
/// </para>
/// <para>
/// The space these numbers are in is <see cref="CoordinateSpace.PhysicalVirtualScreen"/> unless the
/// type carrying the rectangle says otherwise — which means <b>negative coordinates are normal</b>
/// and correct. Nothing here clamps.
/// </para>
/// </remarks>
/// <param name="Left">Left edge, inclusive.</param>
/// <param name="Top">Top edge, inclusive.</param>
/// <param name="Right">Right edge, exclusive.</param>
/// <param name="Bottom">Bottom edge, exclusive.</param>
public readonly record struct Rect(int Left, int Top, int Right, int Bottom)
{
    /// <summary>Width in pixels. Negative if the rectangle is inverted; see <see cref="IsEmpty"/>.</summary>
    public int Width => Right - Left;

    /// <summary>Height in pixels. Negative if the rectangle is inverted; see <see cref="IsEmpty"/>.</summary>
    public int Height => Bottom - Top;

    /// <summary>
    /// True when this rectangle covers no pixels — zero-sized or inverted. Both cases are treated
    /// the same way on purpose: an inverted rectangle is always a bug upstream, and letting one
    /// through into a placement call turns a detectable mistake into a window in a nonsensical
    /// position.
    /// </summary>
    public bool IsEmpty => Right <= Left || Bottom <= Top;

    /// <summary>
    /// Does this rectangle cover the given point, under the half-open convention?
    /// </summary>
    /// <param name="x">X coordinate, same space as this rectangle.</param>
    /// <param name="y">Y coordinate, same space as this rectangle.</param>
    /// <returns>True if the point is inside.</returns>
    public bool Contains(int x, int y) => x >= Left && x < Right && y >= Top && y < Bottom;

    /// <summary>
    /// Build a rectangle from an origin and a size, rather than from two corners.
    /// </summary>
    /// <param name="left">Left edge.</param>
    /// <param name="top">Top edge.</param>
    /// <param name="width">Width in pixels.</param>
    /// <param name="height">Height in pixels.</param>
    /// <returns>The rectangle.</returns>
    /// <remarks>
    /// Exists because the operating system reports geometry both ways and the conversion is exactly
    /// the sort of two-line arithmetic that gets written slightly differently in four places.
    /// </remarks>
    public static Rect FromSize(int left, int top, int width, int height) =>
        new(left, top, left + width, top + height);
}
