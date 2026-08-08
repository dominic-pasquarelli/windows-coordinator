// -------------------------------------------------------------------------------------------------
// WARNING — NEVER COMPILED. Authored 2026-08-08 in an environment with no .NET SDK. Not one line of
// C# in this repository has been through a compiler, an analyzer, or a test runner. Treat every
// signature in this file as a proposal to be verified by the first build, not as working code.
// See docs/NEXT.md (Active focus) and TD-1 in docs/TECH_DEBT.md.
// -------------------------------------------------------------------------------------------------

namespace Coordinator.Platform;

/// <summary>
/// A settings document that knows which schema version it is, and how to move an older one
/// forward.
/// </summary>
/// <remarks>
/// <para>
/// Settings are the source of truth and they have to survive an update, because the alternative —
/// a user losing their zone layouts because a field moved — is the kind of thing that gets an
/// application uninstalled. Two rules make that survivable, and they are stated on this interface
/// because this is where they are enforced:
/// </para>
/// <para>
/// <b>Additive by default.</b> A new field must be readable with a safe default, so a settings
/// document written by yesterday's build still loads in today's. Adding a field is compatible in
/// both directions and costs nothing, which is why it is the default move rather than the
/// exceptional one — and why it does not need a version bump.
/// </para>
/// <para>
/// <b>Structural changes are explicit.</b> Anything that is not a new-field-with-a-default — a
/// field renamed, a shape flattened, a list turned into a dictionary — bumps
/// <see cref="SchemaVersion"/> and is handled in <see cref="Migrate"/>. And per this project's
/// evidence standard: write the migration test first, watch it fail without the migration, then
/// add the migration. A migration guard that has never been observed to fail is a comment.
/// </para>
/// <para>
/// A reset is only ever explicit. Nothing on this interface, and nothing in the store below, is
/// permitted to discard a user's settings as a recovery strategy for a document it could not
/// understand.
/// </para>
/// </remarks>
public interface IVersionedSettings
{
    /// <summary>
    /// The schema version this shape represents — the version the module's current code writes.
    /// Bumped only for a structural change, never for an added field.
    /// </summary>
    int SchemaVersion { get; }

    /// <summary>
    /// Move a document that was persisted under an older schema forward to this one.
    /// </summary>
    /// <param name="loadedSchemaVersion">
    /// The version stamped on the document that was read from disk. Always lower than
    /// <see cref="SchemaVersion"/> when the store calls this; the store does not call it otherwise.
    /// </param>
    /// <returns>
    /// The migrated document. Returning the same instance is correct when nothing structural
    /// changed between the two versions.
    /// </returns>
    /// <remarks>
    /// <para>
    /// Must be pure and fast. It runs during load, before the module is enabled, on the path every
    /// start-up takes. No input, no I/O, no clock.
    /// </para>
    /// <para>
    /// <b>Known wart, recorded rather than hidden:</b> this returns the interface, so
    /// <see cref="ISettingsStore"/> has to cast the result back to the concrete settings type. A
    /// self-referential generic interface would type it properly and would also make every module's
    /// settings declaration noticeably harder to read. The trade is deliberately unresolved until a
    /// compiler and a real second module can weigh in — see the platform README's
    /// "Where to resume".
    /// </para>
    /// </remarks>
    IVersionedSettings Migrate(int loadedSchemaVersion);
}

/// <summary>
/// Typed load and save of one module's settings. A module never touches a file path, a serializer,
/// or a backup — it asks for its settings and it gets them.
/// </summary>
/// <remarks>
/// <para>
/// The store handed to a module is scoped to that module: it cannot read or write another module's
/// settings, because "just reading its settings" is the first crack in module isolation and the
/// hardest to see once it has spread.
/// </para>
/// <para>
/// Both operations are asynchronous because both touch the disk, and the disk is never touched from
/// a hook callback or the UI thread. Loading happens once during start-up; saving happens when
/// settings change. Neither belongs anywhere near a dispatch path.
/// </para>
/// </remarks>
public interface ISettingsStore
{
    /// <summary>
    /// Read this module's settings, migrating them forward if the stored document is older.
    /// </summary>
    /// <typeparam name="T">The module's settings type.</typeparam>
    /// <param name="defaults">
    /// The document to return when nothing has been stored yet. Supplied by the caller rather than
    /// constructed by the store, so that a settings type is free to be a record with required
    /// values and no parameterless constructor — and so that "what a fresh install looks like" is
    /// written in the module, where it can be read, rather than inferred by the platform.
    /// </param>
    /// <param name="cancellationToken">Cancels the read.</param>
    /// <returns>
    /// The stored settings, migrated to the current schema version; or <paramref name="defaults"/>
    /// when there is nothing stored.
    /// </returns>
    /// <remarks>
    /// A document that exists but cannot be understood is a fault to be reported, not a reason to
    /// silently substitute defaults: overwriting a user's configuration because a parser was
    /// unhappy is data loss wearing the costume of resilience.
    /// </remarks>
    ValueTask<T> LoadAsync<T>(T defaults, CancellationToken cancellationToken)
        where T : class, IVersionedSettings;

    /// <summary>
    /// Persist this module's settings.
    /// </summary>
    /// <typeparam name="T">The module's settings type.</typeparam>
    /// <param name="settings">The document to write. Stamped with its schema version.</param>
    /// <param name="cancellationToken">Cancels the write.</param>
    /// <remarks>
    /// A save is the module's second enable: this is the moment to re-resolve anything expensive
    /// that the new values invalidate — recompiled bindings, recomputed geometry, reallocated
    /// buffers — so that the dispatch path stays pre-resolved and cheap.
    /// </remarks>
    ValueTask SaveAsync<T>(T settings, CancellationToken cancellationToken)
        where T : class, IVersionedSettings;
}
