using System.Text.Json.Nodes;
using Coordinator.Platform;
using Xunit;

namespace Coordinator.Platform.Tests;

/// <summary>
/// The settings migration chain.
///
/// Why these tests carry more weight than their size suggests: migration runs on every start-up,
/// against a document the user cannot re-create, and its failure mode is silent. A migration that
/// quietly drops a field does not throw, does not log, and does not look wrong — the user simply
/// finds their layouts gone after an update, with nothing anywhere to explain it.
///
/// The first two tests are the ones that motivated the whole redesign. Migration used to run on the
/// already-deserialized settings object, where a renamed field's old value has ALREADY been
/// discarded by the deserializer — so the two changes migration exists for were exactly the two it
/// could not perform. Both are now expressed against the raw document, where the old data is still
/// there.
/// </summary>
public sealed class SettingsMigrationTests
{
    private static JsonObject Parse(string json) => JsonNode.Parse(json)!.AsObject();

    private sealed class DelegateMigration(int fromVersion, Func<JsonObject, JsonObject> migrate)
        : ISettingsMigration
    {
        public int FromVersion { get; } = fromVersion;

        public JsonObject Migrate(JsonObject document) => migrate(document);
    }

    // --- the two migrations the old design could not perform ---------------------------------

    /// <summary>A field was renamed. The user's value must survive under the new name.</summary>
    [Fact]
    public void PreservesAValueAcrossAFieldRename()
    {
        JsonObject stored = Parse("""
            { "schemaVersion": 1, "snapTolerance": 12, "showOverlay": true }
            """);

        DelegateMigration rename = new(1, document =>
        {
            JsonNode? old = document["snapTolerance"];
            document.Remove("snapTolerance");
            document["snapToleranceDip"] = old?.DeepClone();
            return document;
        });

        JsonObject migrated = SettingsMigrator.MigrateToCurrent(stored, 2, [rename]);

        Assert.Equal(2, SettingsMigrator.ReadSchemaVersion(migrated));
        Assert.Null(migrated["snapTolerance"]);
        Assert.Equal(12, migrated["snapToleranceDip"]!.GetValue<int>());

        // The untouched field is still untouched — a migration must not be a rewrite.
        Assert.True(migrated["showOverlay"]!.GetValue<bool>());
    }

    /// <summary>A collection changed shape: a list of names became a list of objects.</summary>
    [Fact]
    public void MigratesACollectionShapeWithoutLosingEntries()
    {
        JsonObject stored = Parse("""
            { "schemaVersion": 1, "layouts": ["columns", "grid", "focus"] }
            """);

        DelegateMigration reshape = new(1, document =>
        {
            JsonArray names = document["layouts"]!.AsArray();
            JsonArray reshaped = [];
            foreach (JsonNode? name in names)
            {
                reshaped.Add(new JsonObject
                {
                    ["id"] = name!.GetValue<string>(),
                    ["enabled"] = true,
                });
            }

            document["layouts"] = reshaped;
            return document;
        });

        JsonObject migrated = SettingsMigrator.MigrateToCurrent(stored, 2, [reshape]);

        JsonArray layouts = migrated["layouts"]!.AsArray();
        Assert.Equal(3, layouts.Count);
        Assert.Equal("columns", layouts[0]!["id"]!.GetValue<string>());
        Assert.Equal("focus", layouts[2]!["id"]!.GetValue<string>());
        Assert.True(layouts[1]!["enabled"]!.GetValue<bool>());
    }

    // --- refusals: the cases where loading would destroy data ---------------------------------

    /// <summary>
    /// A document from a NEWER build. Loading it means interpreting fields this build has never
    /// seen; saving afterwards writes the older shape back over the user's newer settings. That is
    /// a silent downgrade, so the only safe answer is to refuse.
    /// </summary>
    [Fact]
    public void RefusesADocumentFromAFutureSchema()
    {
        JsonObject stored = Parse("""{ "schemaVersion": 9, "anything": 1 }""");

        SettingsMigrationException error = Assert.Throws<SettingsMigrationException>(
            () => SettingsMigrator.MigrateToCurrent(stored, 2, []));

        Assert.Contains("9", error.Message, StringComparison.Ordinal);
        Assert.Contains("newer version", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// A malformed document is a fault to report, never a reason to substitute defaults. Silently
    /// starting from defaults means the next save overwrites a file that might have been one typo
    /// away from recoverable — data loss wearing the costume of resilience.
    /// </summary>
    [Theory]
    [InlineData("""{ "snapTolerance": 12 }""")]
    [InlineData("""{ "schemaVersion": "two", "snapTolerance": 12 }""")]
    [InlineData("""{ "schemaVersion": null, "snapTolerance": 12 }""")]
    [InlineData("""{ "schemaVersion": 0 }""")]
    public void RefusesAMalformedDocumentRatherThanSubstitutingDefaults(string json)
    {
        JsonObject stored = Parse(json);
        Assert.Throws<SettingsMigrationException>(
            () => SettingsMigrator.MigrateToCurrent(stored, 2, []));
    }

    // --- the chain -----------------------------------------------------------------------------

    [Fact]
    public void AppliesEveryStepInOrderAcrossSeveralVersions()
    {
        JsonObject stored = Parse("""{ "schemaVersion": 1, "trail": "" }""");

        List<ISettingsMigration> chain =
        [
            new DelegateMigration(2, d => { d["trail"] = d["trail"]!.GetValue<string>() + "b"; return d; }),
            new DelegateMigration(1, d => { d["trail"] = d["trail"]!.GetValue<string>() + "a"; return d; }),
        ];

        JsonObject migrated = SettingsMigrator.MigrateToCurrent(stored, 3, chain);

        // Declaration order is irrelevant; FromVersion decides. "ab", never "ba".
        Assert.Equal("ab", migrated["trail"]!.GetValue<string>());
        Assert.Equal(3, SettingsMigrator.ReadSchemaVersion(migrated));
    }

    [Fact]
    public void RefusesWhenAStepInTheChainIsMissing()
    {
        JsonObject stored = Parse("""{ "schemaVersion": 1 }""");
        List<ISettingsMigration> chain = [new DelegateMigration(1, d => d)];

        SettingsMigrationException error = Assert.Throws<SettingsMigrationException>(
            () => SettingsMigrator.MigrateToCurrent(stored, 3, chain));

        Assert.Contains("FromVersion 2", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void RefusesTwoMigrationsClaimingTheSameFromVersion()
    {
        JsonObject stored = Parse("""{ "schemaVersion": 1 }""");
        List<ISettingsMigration> ambiguous =
        [
            new DelegateMigration(1, d => d),
            new DelegateMigration(1, d => d),
        ];

        Assert.Throws<SettingsMigrationException>(
            () => SettingsMigrator.MigrateToCurrent(stored, 2, ambiguous));
    }

    /// <summary>
    /// The runner stamps the version, not the migration — so a migration author who forgets cannot
    /// produce a document that lies about its own shape, or an infinite loop.
    /// </summary>
    [Fact]
    public void StampsTheNewVersionEvenWhenTheMigrationDoesNot()
    {
        JsonObject stored = Parse("""{ "schemaVersion": 1 }""");
        DelegateMigration forgetful = new(1, d => d);

        JsonObject migrated = SettingsMigrator.MigrateToCurrent(stored, 2, [forgetful]);

        Assert.Equal(2, SettingsMigrator.ReadSchemaVersion(migrated));
    }

    [Fact]
    public void ReturnsACurrentDocumentUntouchedAndNeedsNoMigrations()
    {
        JsonObject stored = Parse("""{ "schemaVersion": 2, "value": 5 }""");

        JsonObject result = SettingsMigrator.MigrateToCurrent(stored, 2, []);

        Assert.Same(stored, result);
        Assert.Equal(5, result["value"]!.GetValue<int>());
    }
}
