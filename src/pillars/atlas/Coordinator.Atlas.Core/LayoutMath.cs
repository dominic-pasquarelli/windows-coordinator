// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
//
// This file is the concrete proof of the Core/Shell split: it is ordinary arithmetic over values,
// with no desktop anywhere in it, so it runs and is unit-tested on any operating system. It is also
// the first thing in this repository that will ever be tested — see the Atlas README.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Atlas;

/// <summary>Why a template could not be resolved against a work area.</summary>
/// <remarks>
/// Refusing loudly matters more here than it looks. The alternative to a refusal is a zero-width or
/// negative rectangle escaping into a placement call, which does not throw — it just puts a window
/// somewhere nonsensical, on somebody else's monitor arrangement, with no error anywhere.
/// </remarks>
public enum LayoutRefusalReason
{
    /// <summary>The template declares no cells, so there is nothing to resolve.</summary>
    TemplateEmpty,

    /// <summary>A cell's fractions are outside 0.0 to 1.0, or inverted.</summary>
    CellOutOfRange,

    /// <summary>The work area is zero-sized or inverted.</summary>
    WorkAreaEmpty,

    /// <summary>
    /// The work area is real but too small for this template once padding and gaps are taken out —
    /// at least one zone would have no pixels left.
    /// </summary>
    WorkAreaTooSmall,
}

/// <summary>
/// The outcome of resolving a template: rectangles, or a reason there are none.
/// </summary>
/// <remarks>
/// A result type rather than an exception because "this template does not fit this monitor" is an
/// ordinary, expected situation on a small display, not an exceptional one — and because a caller
/// that has to handle a value is a caller that cannot forget to.
/// </remarks>
public abstract record LayoutResult
{
    /// <summary>The template resolved. Here are the zones.</summary>
    /// <param name="ZoneSet">The resolved zone set.</param>
    public sealed record Resolved(ZoneSet ZoneSet) : LayoutResult;

    /// <summary>The template did not resolve, and here is why in terms a person can act on.</summary>
    /// <param name="Reason">The category of refusal.</param>
    /// <param name="Detail">
    /// The specifics — which cell, what size, what was left after padding. Written for a human
    /// reading a log or a settings surface at the moment their layout did not appear.
    /// </param>
    public sealed record Refused(LayoutRefusalReason Reason, string Detail) : LayoutResult;
}

/// <summary>
/// Turns a layout template and a work area into zone rectangles. Pure arithmetic: no desktop, no
/// I/O, no clock, no ambient state.
/// </summary>
public static class LayoutMath
{
    /// <summary>
    /// Resolve a template against one monitor's work area.
    /// </summary>
    /// <param name="template">The template to resolve.</param>
    /// <param name="workArea">
    /// The monitor's work area — the monitor rectangle minus the taskbar and any application bars —
    /// in <see cref="CoordinateSpace.PhysicalVirtualScreen"/>. Not the monitor's full bounds:
    /// resolving against those puts a zone underneath the taskbar.
    /// </param>
    /// <param name="topologyGeneration">
    /// The desktop topology generation this is being computed at, carried into the result so a
    /// consumer can tell later whether the geometry is still meaningful. Required rather than
    /// defaulted: a silent zero would be a value that is always accepted and never true, which is
    /// exactly the check-that-cannot-fail this project's evidence standard names first.
    /// </param>
    /// <returns>
    /// <see cref="LayoutResult.Resolved"/> with the zone set, or <see cref="LayoutResult.Refused"/>
    /// with a reason.
    /// </returns>
    /// <remarks>
    /// <para>
    /// <b>The algorithm, and why it is this one.</b> Every edge is computed by mapping its fraction
    /// through one rounding step against the padded work area — never by computing each zone's width
    /// independently and laying zones end to end. The difference is invisible in code review and
    /// obvious on screen: independent rounding accumulates, leaving a one-pixel seam between some
    /// pairs of zones and a one-pixel overlap between others depending on the work area's width. The
    /// user perceives that as a hairline of wallpaper between two snapped windows, which is precisely
    /// the small wrongness that makes a tool feel cheap.
    /// </para>
    /// <para>
    /// Because the same fraction against the same padded work area always maps to the same pixel,
    /// two cells that share a boundary fraction get the identical edge — exactly, at every width.
    /// That is the property to write the first test against, and to watch fail against a naive
    /// per-zone-width implementation before trusting it.
    /// </para>
    /// <para>
    /// Rounding is away from zero rather than the platform default of to-even, because to-even makes
    /// the result depend on the parity of a number nobody is thinking about, and geometry bugs are
    /// hard enough to reason about without that.
    /// </para>
    /// <para>
    /// Negative coordinates are handled by construction: the mapping is relative to the work area's
    /// own origin, so a monitor arranged left of the primary one resolves correctly with no special
    /// case and nothing clamped.
    /// </para>
    /// </remarks>
    public static LayoutResult Resolve(LayoutTemplate template, Rect workArea, int topologyGeneration)
    {
        if (template.Cells.Count == 0)
        {
            return new LayoutResult.Refused(
                LayoutRefusalReason.TemplateEmpty,
                $"template '{template.Id}' declares no cells");
        }

        if (workArea.IsEmpty)
        {
            return new LayoutResult.Refused(
                LayoutRefusalReason.WorkAreaEmpty,
                $"work area is {workArea.Width} by {workArea.Height}");
        }

        int padding = Math.Max(0, template.Padding);
        int gap = Math.Max(0, template.Gap);
        int halfGap = gap / 2;

        Rect inner = new(
            workArea.Left + padding,
            workArea.Top + padding,
            workArea.Right - padding,
            workArea.Bottom - padding);

        if (inner.IsEmpty)
        {
            return new LayoutResult.Refused(
                LayoutRefusalReason.WorkAreaTooSmall,
                $"padding of {padding} leaves {inner.Width} by {inner.Height}");
        }

        var zones = new List<ZoneRect>(template.Cells.Count);

        for (int index = 0; index < template.Cells.Count; index++)
        {
            LayoutCell cell = template.Cells[index];

            if (!IsWellFormed(cell))
            {
                return new LayoutResult.Refused(
                    LayoutRefusalReason.CellOutOfRange,
                    $"cell '{cell.Id}' has fractions " +
                    $"({cell.Left}, {cell.Top}) to ({cell.Right}, {cell.Bottom}); each must be " +
                    "within 0.0 to 1.0 with right greater than left and bottom greater than top");
            }

            // One rounding step per edge, against the padded work area. Shared fractions therefore
            // produce shared edges exactly — see the remarks above.
            int left = MapFraction(cell.Left, inner.Left, inner.Width);
            int right = MapFraction(cell.Right, inner.Left, inner.Width);
            int top = MapFraction(cell.Top, inner.Top, inner.Height);
            int bottom = MapFraction(cell.Bottom, inner.Top, inner.Height);

            // Gaps are inset on INTERIOR edges only, so neighbours end up exactly `gap` apart while
            // the outside of the layout stays flush with the padded work area. Insetting all four
            // edges instead would make the outer margin depend on the gap, which is a different
            // (and undeclared) visual rule.
            if (left > inner.Left)
            {
                left += halfGap;
            }

            if (top > inner.Top)
            {
                top += halfGap;
            }

            if (right < inner.Right)
            {
                right -= halfGap;
            }

            if (bottom < inner.Bottom)
            {
                bottom -= halfGap;
            }

            Rect bounds = new(left, top, right, bottom);

            if (bounds.IsEmpty)
            {
                return new LayoutResult.Refused(
                    LayoutRefusalReason.WorkAreaTooSmall,
                    $"zone '{cell.Id}' resolves to {bounds.Width} by {bounds.Height} in a work " +
                    $"area of {workArea.Width} by {workArea.Height} with padding {padding} and " +
                    $"gap {gap}");
            }

            zones.Add(new ZoneRect(cell.Id, index, bounds, CoordinateSpace.PhysicalVirtualScreen));
        }

        return new LayoutResult.Resolved(
            new ZoneSet(template, workArea, topologyGeneration, zones));
    }

    /// <summary>
    /// Which zone contains a point — the hit test a drag runs against pre-computed geometry.
    /// </summary>
    /// <param name="zoneSet">The resolved zones.</param>
    /// <param name="x">X coordinate, in the zone set's space.</param>
    /// <param name="y">Y coordinate, in the zone set's space.</param>
    /// <returns>The first zone covering the point, or null if none does.</returns>
    /// <remarks>
    /// <para>
    /// Comparison arithmetic, deliberately. This is what a drag calls on every mouse move, so the
    /// expensive work — reading the desktop, resolving the template — has to have happened once,
    /// when the drag started. Re-reading the desktop per mouse move is a full enumeration on the
    /// interaction path, and it is the specific mistake this design exists to prevent.
    /// </para>
    /// <para>
    /// "First" matters when zones overlap, which the layout model permits: template order decides,
    /// and template order is the author's declared intent.
    /// </para>
    /// </remarks>
    public static ZoneRect? HitTest(ZoneSet zoneSet, int x, int y) =>
        zoneSet.Zones.FirstOrDefault(z => z.Bounds.Contains(x, y));

    /// <summary>
    /// Map a fraction of an extent to an absolute coordinate, with exactly one rounding step.
    /// </summary>
    /// <param name="fraction">The fraction, from 0.0 to 1.0.</param>
    /// <param name="origin">The absolute coordinate the extent starts at. May be negative.</param>
    /// <param name="extent">The extent's size in pixels. Positive.</param>
    /// <returns>The absolute coordinate.</returns>
    private static int MapFraction(double fraction, int origin, int extent) =>
        origin + (int)Math.Round(fraction * extent, MidpointRounding.AwayFromZero);

    /// <summary>
    /// Is a cell's geometry usable — inside the unit square, and not inverted or empty?
    /// </summary>
    /// <param name="cell">The cell to check.</param>
    /// <returns>True if it can be resolved.</returns>
    private static bool IsWellFormed(LayoutCell cell) =>
        cell.Left >= 0.0
        && cell.Top >= 0.0
        && cell.Right <= 1.0
        && cell.Bottom <= 1.0
        && cell.Right > cell.Left
        && cell.Bottom > cell.Top;
}
