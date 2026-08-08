// -------------------------------------------------------------------------------------------------
// Settings — versioned, additive by default, migrated on a representation that still holds the old
// data. See docs/decisions/0007-settings-schema-additive-versioned-migrated.md.
// -------------------------------------------------------------------------------------------------

using System.Text.Json.Nodes;

namespace Coordinator.Platform;

/// <summary>
/// A settings document that knows which schema version the current code writes.
/// </summary>
/// <remarks>
/// <para>
/// Settings are the source of truth and they have to survive an update, because the alternative —
/// a user losing their zone layouts because a field moved — is the kind of thing that gets an
/// application uninstalled.
/// </para>
/// <para>
/// <b>Additive by default.</b> A new field must be readable with a safe default, so a document
/// written by yesterday's build still loads in today's. Adding a field is compatible in both
/// directions and costs nothing, which is why it is the default move and why it does not bump
/// <see cref="SchemaVersion"/>.
/// </para>
/// <para>
/// <b>Structural changes are explicit.</b> Anything that is not a new-field-with-a-default — a
/// field renamed, a shape flattened, a list turned into a dictionary — bumps
/// <see cref="SchemaVersion"/> and ships an <see cref="ISettingsMigration"/> for the step.
/// </para>
/// <para>
/// A reset is only ever explicit. Nothing here is permitted to discard a user's settings as a
/// recovery strategy for a document it could not understand.
/// </para>
/// </remarks>
public interface IVersionedSettings
{
    /// <summary>
    /// The schema version this shape represents — the version the module's current code writes.
    /// Bumped only for a structural change, never for an added field. Starts at 1.
    /// </summary>
    int SchemaVersion { get; }
}

/// <summary>
/// A settings document could not be read or moved forward. Never thrown to mean "there is nothing
/// stored yet" — that case returns the caller's defaults and is not an error.
/// </summary>
public sealed class SettingsMigrationException : Exception
{
    /// <summary>Create the exception with a message.</summary>
    /// <param name="message">What went wrong, in terms someone can act on.</param>
    public SettingsMigrationException(string message) : base(message)
    {
    }

    /// <summary>Create the exception with a message and the underlying cause.</summary>
    /// <param name="message">What went wrong.</param>
    /// <param name="innerException">The underlying failure.</param>
    public SettingsMigrationException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

/// <summary>
/// One structural step, moving a persisted document from <see cref="FromVersion"/> to
/// <see cref="FromVersion"/> + 1.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why this operates on JSON rather than on the settings type.</b> A migration exists precisely
/// for the changes the current type can no longer express: a renamed field, a list that became a
/// dictionary, a shape that was flattened. By the time a document has been deserialized into the
/// current type, the deserializer has already dropped every property the current type has no home
/// for — so the old value the migration needs to preserve is gone before the migration runs. An
/// API that migrated the deserialized object could therefore only ever perform the migrations that
/// do not need migrating.
/// </para>
/// <para>
/// Working on the raw document instead keeps the old data present and movable, and it keeps the
/// settings type clean: the type describes the current shape only, and history lives in the
/// migration chain where it can be read in order and tested step by step.
/// </para>
/// <para>
/// Must be pure and fast. Migrations run during load, before the module is enabled, on the path
/// every start-up takes. No I/O, no clock, no input.
/// </para>
/// </remarks>
public interface ISettingsMigration
{
    /// <summary>
    /// The version this step reads. It produces <c>FromVersion + 1</c>.
    /// </summary>
    int FromVersion { get; }

    /// <summary>
    /// Move the document one version forward.
    /// </summary>
    /// <param name="document">
    /// The document as persisted at <see cref="FromVersion"/>. Every property that was written is
    /// present, including ones the current settings type no longer declares.
    /// </param>
    /// <returns>
    /// The document at <c>FromVersion + 1</c>. May be the same instance, mutated. The caller stamps
    /// the new version number, so a migration cannot forget to.
    /// </returns>
    JsonObject Migrate(JsonObject document);
}

/// <summary>
/// Runs the migration chain over a persisted settings document. Pure: no I/O, no ambient state.
/// </summary>
public static class SettingsMigrator
{
    /// <summary>
    /// The property every persisted settings document carries. Reserved — a settings type must not
    /// declare a field that serializes to this name.
    /// </summary>
    public const string VersionPropertyName = "schemaVersion";

    /// <summary>
    /// Read the schema version stamped on a document.
    /// </summary>
    /// <param name="document">The parsed document.</param>
    /// <returns>The stamped version.</returns>
    /// <exception cref="SettingsMigrationException">
    /// The version is missing, is not an integer, or is below 1. Each is a malformed document, and
    /// a malformed document is a fault to report — never a reason to silently substitute defaults,
    /// which is data loss wearing the costume of resilience.
    /// </exception>
    public static int ReadSchemaVersion(JsonObject document)
    {
        ArgumentNullException.ThrowIfNull(document);

        if (!document.TryGetPropertyValue(VersionPropertyName, out JsonNode? node) || node is null)
        {
            throw new SettingsMigrationException(
                $"the settings document has no `{VersionPropertyName}` property, so there is no way " +
                "to know which schema wrote it. Refusing to guess — a wrong guess silently discards " +
                "settings. Repair the document or delete it deliberately.");
        }

        if (node is not JsonValue value || !value.TryGetValue(out int version))
        {
            throw new SettingsMigrationException(
                $"the settings document's `{VersionPropertyName}` is `{node.ToJsonString()}`, which " +
                "is not an integer.");
        }

        if (version < 1)
        {
            throw new SettingsMigrationException(
                $"the settings document declares `{VersionPropertyName}` {version}; versions start " +
                "at 1.");
        }

        return version;
    }

    /// <summary>
    /// Move a persisted document forward to <paramref name="currentVersion"/>, one step at a time.
    /// </summary>
    /// <param name="document">The document as read from storage.</param>
    /// <param name="currentVersion">The version the running code writes.</param>
    /// <param name="migrations">
    /// The available steps, in any order. Exactly one must declare each <c>FromVersion</c> between
    /// the document's version and <paramref name="currentVersion"/>.
    /// </param>
    /// <returns>
    /// The document at <paramref name="currentVersion"/>, ready to deserialize. Returned unchanged
    /// when it is already current.
    /// </returns>
    /// <exception cref="SettingsMigrationException">
    /// The document is malformed; its version is newer than this build understands; a step in the
    /// chain is missing; or two steps declare the same <c>FromVersion</c>.
    /// </exception>
    public static JsonObject MigrateToCurrent(
        JsonObject document,
        int currentVersion,
        IEnumerable<ISettingsMigration> migrations)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(migrations);
        ArgumentOutOfRangeException.ThrowIfLessThan(currentVersion, 1);

        int version = ReadSchemaVersion(document);

        // A document from a NEWER build. Loading it would mean interpreting fields written by code
        // this build has never seen, and saving afterwards would write the older shape back over
        // the user's newer settings — a silent downgrade that destroys data. Refuse instead: the
        // honest outcome is "this profile was written by a newer version", not a quiet reset.
        if (version > currentVersion)
        {
            throw new SettingsMigrationException(
                $"the settings document is schema version {version}, but this build understands at " +
                $"most {currentVersion}. It was written by a newer version of Windows Coordinator. " +
                "Refusing to load it, because loading and re-saving would overwrite newer settings " +
                "with an older shape.");
        }

        if (version == currentVersion)
        {
            return document;
        }

        Dictionary<int, ISettingsMigration> byFromVersion = [];
        foreach (ISettingsMigration migration in migrations)
        {
            if (migration is null)
            {
                throw new SettingsMigrationException("the migration set contains a null entry.");
            }

            if (!byFromVersion.TryAdd(migration.FromVersion, migration))
            {
                throw new SettingsMigrationException(
                    $"two migrations both declare FromVersion {migration.FromVersion}; the chain " +
                    "would be ambiguous.");
            }
        }

        JsonObject current = document;
        while (version < currentVersion)
        {
            if (!byFromVersion.TryGetValue(version, out ISettingsMigration? step))
            {
                throw new SettingsMigrationException(
                    $"no migration declares FromVersion {version}, so the chain from {version} to " +
                    $"{currentVersion} is broken. Every structural version bump must ship its step.");
            }

            JsonObject next = step.Migrate(current)
                ?? throw new SettingsMigrationException(
                    $"the migration from version {version} returned null.");

            // The runner stamps the version, not the migration — so a migration author cannot
            // forget to, and a forgotten stamp cannot turn into an infinite loop or a document
            // that lies about its own shape.
            next[VersionPropertyName] = JsonValue.Create(version + 1);

            current = next;
            version++;
        }

        return current;
    }
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
    /// Read this module's settings, migrating the stored document forward if it is older.
    /// </summary>
    /// <typeparam name="T">The module's settings type.</typeparam>
    /// <param name="defaults">
    /// The document to return when nothing has been stored yet. Supplied by the caller rather than
    /// constructed by the store, so a settings type is free to be a record with required values and
    /// no parameterless constructor — and so "what a fresh install looks like" is written in the
    /// module, where it can be read.
    /// </param>
    /// <param name="migrations">
    /// The module's migration chain — one step per structural version bump it has ever made. Empty
    /// is correct for a module that has never made one.
    /// </param>
    /// <param name="cancellationToken">Cancels the read.</param>
    /// <returns>
    /// The stored settings, migrated to <c>defaults.SchemaVersion</c>; or <paramref name="defaults"/>
    /// when there is nothing stored.
    /// </returns>
    /// <exception cref="SettingsMigrationException">
    /// A document exists but is malformed, is newer than this build, or cannot be migrated. A
    /// document that exists and cannot be understood is a fault to report, not a reason to silently
    /// substitute defaults.
    /// </exception>
    ValueTask<T> LoadAsync<T>(
        T defaults,
        IReadOnlyList<ISettingsMigration> migrations,
        CancellationToken cancellationToken)
        where T : class, IVersionedSettings;

    /// <summary>
    /// Persist this module's settings, stamped with <see cref="IVersionedSettings.SchemaVersion"/>.
    /// </summary>
    /// <typeparam name="T">The module's settings type.</typeparam>
    /// <param name="settings">The document to write.</param>
    /// <param name="cancellationToken">Cancels the write.</param>
    /// <remarks>
    /// A save is the module's second enable: this is the moment to re-resolve anything expensive
    /// that the new values invalidate — recompiled bindings, recomputed geometry, reallocated
    /// buffers — so the dispatch path stays pre-resolved and cheap.
    /// </remarks>
    ValueTask SaveAsync<T>(T settings, CancellationToken cancellationToken)
        where T : class, IVersionedSettings;
}
