// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Atlas;

/// <summary>
/// One cell of a layout, expressed as fractions of the work area rather than pixels.
/// </summary>
/// <remarks>
/// <para>
/// Fractions, not pixels, because a layout has to mean the same thing on a 1080p panel and an
/// ultrawide, and because the same template has to resolve correctly against every monitor in a
/// mixed arrangement. A "left half" is 0.0 to 0.5 everywhere; what that is in pixels is a question
/// only the work area can answer.
/// </para>
/// <para>
/// Fractions are absolute positions within the work area, not sizes laid end to end — so the
/// familiar question of whether a template's fractions "add up to one" does not arise. What does
/// arise, and is deliberately <b>not</b> checked: nothing here prevents two cells overlapping or
/// leaves of the work area being uncovered. Both are legitimate layouts, so refusing them would be
/// inventing a rule; if a template author wants a check, that is a template-authoring feature and
/// belongs where templates are authored.
/// </para>
/// </remarks>
/// <param name="Id">
/// A stable id for this cell within its template. Ends up in saved settings when a user assigns a
/// window to a zone, so it is subject to the same never-rename discipline as every other id here.
/// </param>
/// <param name="Left">Left edge as a fraction of work-area width, from 0.0 to 1.0.</param>
/// <param name="Top">Top edge as a fraction of work-area height, from 0.0 to 1.0.</param>
/// <param name="Right">Right edge as a fraction, strictly greater than <paramref name="Left"/>.</param>
/// <param name="Bottom">Bottom edge as a fraction, strictly greater than <paramref name="Top"/>.</param>
public sealed record LayoutCell(
    string Id,
    double Left,
    double Top,
    double Right,
    double Bottom);

/// <summary>
/// A named arrangement of cells, resolvable against any work area.
/// </summary>
/// <remarks>
/// A template contains no pixels, no monitor, and no desktop — which is what makes resolving one
/// pure arithmetic and therefore testable anywhere.
/// </remarks>
/// <param name="Id">Stable id, referenced by settings. Never renamed.</param>
/// <param name="Name">Human-facing name. Free to change.</param>
/// <param name="Cells">The cells, in the order zones should be numbered.</param>
/// <param name="Padding">
/// Pixels removed from every edge of the work area before any cell is resolved. Applied first so
/// that padding never lands unevenly on the last zone.
/// </param>
/// <param name="Gap">
/// Pixels of separation between adjacent zones, in the resolved result. Applied as half a gap
/// inset on each interior edge, so two neighbours are exactly <c>Gap</c> apart while the outer
/// edges of the layout stay flush with the padded work area. An odd gap loses a pixel to integer
/// division, which is deliberate and preferable to a rounding rule that makes some pairs of zones
/// closer than others.
/// </param>
public sealed record LayoutTemplate(
    string Id,
    string Name,
    IReadOnlyList<LayoutCell> Cells,
    int Padding = 0,
    int Gap = 0);

/// <summary>
/// One resolved zone: a real rectangle, in a named coordinate space.
/// </summary>
/// <param name="ZoneId">The originating cell's stable id.</param>
/// <param name="Index">The zone's position in the template's cell order, from zero.</param>
/// <param name="Bounds">The resolved rectangle.</param>
/// <param name="Space">
/// Which space <paramref name="Bounds"/> is in. Carried explicitly rather than assumed, because a
/// rectangle whose space is ambiguous is the raw material of every window-placement bug.
/// </param>
public sealed record ZoneRect(
    string ZoneId,
    int Index,
    Rect Bounds,
    CoordinateSpace Space);

/// <summary>
/// A template resolved against one monitor's work area: the zone rectangles, plus enough context to
/// know whether they are still valid.
/// </summary>
/// <remarks>
/// The template and work area are kept alongside the zones so that a consumer holding a zone set
/// can answer "where did these numbers come from" without a second lookup — and so that the
/// generation check below has something to compare against.
/// </remarks>
/// <param name="Template">The template these zones came from.</param>
/// <param name="WorkArea">The work area they were resolved against, before padding.</param>
/// <param name="TopologyGeneration">
/// The desktop topology generation current when this was computed. <b>A zone set must not be
/// applied at a later generation than the one it was computed at</b> — recompute instead. A layout
/// derived from a work area that no longer exists is not approximately right, it is arbitrary, and
/// carrying the generation is what turns that from an invisible mistake into a comparison.
/// </param>
/// <param name="Zones">The resolved rectangles, in template order.</param>
public sealed record ZoneSet(
    LayoutTemplate Template,
    Rect WorkArea,
    int TopologyGeneration,
    IReadOnlyList<ZoneRect> Zones);
