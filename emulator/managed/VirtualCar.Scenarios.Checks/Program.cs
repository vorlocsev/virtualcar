using System.Security.Cryptography;
using Microsoft.Data.Sqlite;
using VirtualCar.Core;
using VirtualCar.Scenarios;
using VirtualCar.Storage;

namespace VirtualCar.Scenarios.Checks;

/// <summary>Eight offline SQLite-to-C# compiler gates. No J2534, Volvo
/// B9FB, donor data, physical adapter or real vehicle is used.</summary>
internal static class Program
{
    private static readonly byte[] GoodRequest = [0x22, 0xF1, 0x87];
    private static readonly byte[] GoodReply = [0x62, 0xF1, 0x87, 0x01];

    private static async Task<int> Main()
    {
        (string Name, Func<Task> Check)[] checks =
        [
            ("01 Preview never approves; sealed hash enables compilation", Test01),
            ("02 Determinism independent of SQLite row insertion order", Test02),
            ("03 Missing or wrong request material is rejected", Test03),
            ("04 Research-only and unapproved replies fail closed", Test04),
            ("05 Security service and mismatched positive reply rejected", Test05),
            ("06 11-bit IDs and ambiguous ECU routes rejected", Test06),
            ("07 Post-seal tampering invalidates materialized checksum", Test07),
            ("08 Cancellation and C# coordinator generation integration", Test08)
        ];
        int success = 0;
        foreach ((string name, Func<Task> check) in checks)
        {
            try
            {
                await check();
                Console.WriteLine("PASS " + name);
                success++;
            }
            catch (Exception e)
            {
                Console.Error.WriteLine("FAIL " + name + " (" + e.GetType().Name + ")");
            }
        }
        Console.WriteLine($"VirtualCar.Scenarios M2: {success}/{checks.Length}");
        return success == checks.Length ? 0 : 1;
    }

    private static void Require(bool valid, string reason)
    {
        if (!valid) throw new InvalidOperationException(reason);
    }

    private static async Task RejectAsync<T>(Func<Task> action) where T : Exception
    {
        try { await action(); }
        catch (T) { return; }
        throw new InvalidOperationException("Expected " + typeof(T).Name);
    }

    private static async Task Test01()
    {
        await using var lab = await Laboratory.CreateAsync();
        ScenarioPreview preview = await lab.Compiler.PreviewDraftAsync("scenario-1", 1);
        Require(preview.ResponseCount == 1 && !preview.RuntimeApproved &&
                !preview.SnapshotBytesVerified && preview.Sha256.Length == 64,
                "Draft was incorrectly approved");
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await lab.Compiler.CompileVerifiedAsync("scenario-1", 1);
        });
        await lab.SealAsync(preview.Sha256);
        ScenarioCandidate candidate = await lab.Compiler.CompileVerifiedAsync("scenario-1", 1);
        Require(candidate.ApprovedReadOnly &&
                candidate.Provenance == ScenarioProvenance.Synthetic &&
                candidate.CanonicalBytes.Length > 16 &&
                candidate.CanonicalBytes.AsSpan(0, 7).SequenceEqual("VCSNAP1"u8) &&
                candidate.Sha256 == preview.Sha256 &&
                candidate.Sha256 == Convert.ToHexString(
                    SHA256.HashData(candidate.CanonicalBytes)).ToLowerInvariant(),
                "Verified canonical snapshot did not match expected bytes");
    }

    private static async Task Test02()
    {
        await using var a = await Laboratory.CreateAsync(twoFixtures: true);
        await using var b = await Laboratory.CreateAsync(twoFixtures: true, reverseOrder: true);
        string a1 = (await a.Compiler.PreviewDraftAsync("scenario-1", 1)).Sha256;
        string a2 = (await a.Compiler.PreviewDraftAsync("scenario-1", 1)).Sha256;
        string b1 = (await b.Compiler.PreviewDraftAsync("scenario-1", 1)).Sha256;
        Require(a1 == a2 && a1 == b1, "Non-deterministic materialization");
        await a.SealAsync(a1);
        await b.SealAsync(b1);
        var left = await a.Compiler.CompileVerifiedAsync("scenario-1", 1);
        var right = await b.Compiler.CompileVerifiedAsync("scenario-1", 1);
        Require(left.CanonicalBytes.SequenceEqual(right.CanonicalBytes),
            "Insertion order modified bytes");
    }

    private static async Task Test03()
    {
        await using var lab = await Laboratory.CreateAsync();
        string hash = Hash(GoodRequest);
        lab.Manifest.Bytes.Remove(hash);
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await lab.Compiler.PreviewDraftAsync("scenario-1", 1);
        });
        lab.Manifest.Bytes[hash] = [0x22, 0xF1, 0x88];
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await lab.Compiler.PreviewDraftAsync("scenario-1", 1);
        });
    }

    private static async Task Test04()
    {
        await using var lab = await Laboratory.CreateAsync();
        await lab.ExecuteAsync("UPDATE vehicle_profiles SET provenance='research_only';");
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await lab.Compiler.PreviewDraftAsync("scenario-1", 1);
        });
        await lab.ExecuteAsync("UPDATE vehicle_profiles SET provenance='synthetic';");
        await lab.ExecuteAsync("UPDATE response_fixtures SET lab_approval='draft';");
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await lab.Compiler.PreviewDraftAsync("scenario-1", 1);
        });
        // The SQL CHECK forbids a captured_private fixture holding inline
        // synthetic bytes. Neither compiler nor DB should accept this.
        await RejectAsync<SqliteException>(() =>
            lab.ExecuteAsync("UPDATE response_fixtures SET provenance='captured_private';"));
    }

    private static async Task Test05()
    {
        await using var lab = await Laboratory.CreateAsync(
            firstRequest: [0x27, 0xF1, 0x87],
            firstReply: [0x67, 0xF1, 0x87, 0x01]);
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await lab.Compiler.PreviewDraftAsync("scenario-1", 1);
        });
        await using var wrong = await Laboratory.CreateAsync(
            firstReply: [0x62, 0xF1, 0x88, 0x01]);
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await wrong.Compiler.PreviewDraftAsync("scenario-1", 1);
        });
    }

    private static async Task Test06()
    {
        await using var invalidId = await Laboratory.CreateAsync();
        await invalidId.ExecuteAsync("UPDATE ecu_nodes SET request_can_id=2048 WHERE id='ecu-1';");
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await invalidId.Compiler.PreviewDraftAsync("scenario-1", 1);
        });

        await using var conflicting = await Laboratory.CreateAsync();
        await conflicting.ExecuteAsync("""
            INSERT INTO ecu_nodes VALUES('ecu-2','bus-1','Other ECU','iso15765',2016,2025,1);
            """);
        byte[] req2 = [0x22, 0xF1, 0x88];
        conflicting.Manifest.Bytes[Hash(req2)] = req2;
        await conflicting.AddFixtureAsync("fixture-2", "ecu-2", req2,
            [0x62, 0xF1, 0x88, 0x02]);
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await conflicting.Compiler.PreviewDraftAsync("scenario-1", 1);
        });
    }

    private static async Task Test07()
    {
        await using var lab = await Laboratory.CreateAsync();
        string digest = (await lab.Compiler.PreviewDraftAsync("scenario-1", 1)).Sha256;
        await lab.SealAsync(digest);
        _ = await lab.Compiler.CompileVerifiedAsync("scenario-1", 1);
        // The v1 schema guards fixture bindings, but ECU rows remain mutable.
        // Full-payload rehash is the critical protection against that gap.
        await lab.ExecuteAsync("UPDATE ecu_nodes SET request_can_id=2017 WHERE id='ecu-1';");
        await RejectAsync<ScenarioCompilationException>(async () =>
        {
            await lab.Compiler.CompileVerifiedAsync("scenario-1", 1);
        });
        await RejectAsync<SqliteException>(() =>
            lab.ExecuteAsync("UPDATE response_fixtures SET lab_approval='draft';"));
    }

    private static async Task Test08()
    {
        await using var lab = await Laboratory.CreateAsync();
        using var cancel = new CancellationTokenSource();
        cancel.Cancel();
        await RejectAsync<OperationCanceledException>(async () =>
        {
            await lab.Compiler.PreviewDraftAsync("scenario-1", 1, cancel.Token);
        });
        string digest = (await lab.Compiler.PreviewDraftAsync("scenario-1", 1)).Sha256;
        await lab.SealAsync(digest);

        var runtime = new NoopSyntheticRuntime();
        var coordinator = new ScenarioCoordinator(
            new VerifiedScenarioCatalog(lab.Compiler), runtime);
        await coordinator.SelectAsync("scenario-1", 1);
        SessionToken token = await coordinator.OpenSessionAsync();
        await coordinator.ValidateSessionAsync(token);
        await RejectAsync<InvalidOperationException>(async () =>
        {
            await coordinator.ResetAsync();
        });
        await coordinator.CloseSessionAsync(token);
        await coordinator.ResetAsync();
        await RejectAsync<InvalidOperationException>(async () =>
        {
            await coordinator.ValidateSessionAsync(token);
        });
        Require(runtime.PrepareCount == 2, "Coordinator failed to prepare verified snapshot");
        await coordinator.ShutdownAsync();
    }

    private static string Hash(byte[] bytes) =>
        Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    private sealed class Manifest : ISyntheticRequestManifest
    {
        public Dictionary<string, byte[]> Bytes { get; } = new(StringComparer.Ordinal);

        public Task<byte[]?> ResolveAsync(string requestSha256, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return Task.FromResult(Bytes.TryGetValue(requestSha256, out byte[]? bytes)
                ? bytes.ToArray() : null);
        }
    }

    private sealed class NoopSyntheticRuntime : IScenarioRuntime
    {
        public int PrepareCount { get; private set; }
        public Task PrepareAsync(ScenarioSnapshot snapshot, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Require(snapshot.ApprovedReadOnly && snapshot.CanonicalBytes.Length > 0,
                "Invalid candidate reached the synthetic runtime");
            PrepareCount++;
            return Task.CompletedTask;
        }

        public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    }

    private sealed class Laboratory : IAsyncDisposable
    {
        private readonly string _folder;
        private readonly string _path;
        private readonly LabCatalog _catalog;

        public Manifest Manifest { get; } = new();
        public ScenarioCompiler Compiler { get; }

        private Laboratory(string folder, LabCatalog catalog)
        {
            _folder = folder;
            _path = Path.Combine(folder, "lab.db");
            _catalog = catalog;
            Compiler = new ScenarioCompiler(_catalog, Manifest);
        }

        public static async Task<Laboratory> CreateAsync(
            bool twoFixtures = false, bool reverseOrder = false,
            byte[]? firstRequest = null, byte[]? firstReply = null)
        {
            string folder = Path.Combine(Path.GetTempPath(),
                "virtualcar-m2-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            try
            {
                LabCatalog catalog = await LabCatalog.CreateAsync(Path.Combine(folder, "lab.db"));
                var lab = new Laboratory(folder, catalog);
                await lab.SeedAsync(twoFixtures, reverseOrder,
                    firstRequest ?? GoodRequest, firstReply ?? GoodReply);
                return lab;
            }
            catch
            {
                try { Directory.Delete(folder, true); }
                catch (IOException) { }
                throw;
            }
        }

        private async Task SeedAsync(bool two, bool reverse, byte[] first, byte[] reply)
        {
            await ExecuteAsync("""
                INSERT INTO vehicle_profiles VALUES('vehicle-1','Synthetic car','GENERIC',2009,
                                                   'synthetic','2026-11-06T00:00:00Z');
                INSERT INTO can_buses VALUES('bus-1','vehicle-1','HS',500000,'11bit');
                INSERT INTO ecu_nodes VALUES('ecu-1','bus-1','ECM','iso15765',2016,2024,1);
                INSERT INTO scenarios VALUES('scenario-1','Synthetic lab scenario','vehicle-1',
                                            '2026-11-06T00:00:00Z');
                INSERT INTO scenario_revisions VALUES('revision-1','scenario-1',1,0,NULL,
                                                      '2026-11-06T00:00:00Z');
                """);

            var fixtures = new List<(string Id, string Ecu, byte[] Request, byte[] Reply)>
            {
                ("fixture-1", "ecu-1", first, reply)
            };
            if (two) fixtures.Add(("fixture-2", "ecu-1",
                [0x22, 0xF1, 0x88], [0x62, 0xF1, 0x88, 0x02]));
            if (reverse) fixtures.Reverse();
            foreach (var f in fixtures)
            {
                Manifest.Bytes[Hash(f.Request)] = f.Request.ToArray();
                await AddFixtureAsync(f.Id, f.Ecu, f.Request, f.Reply);
            }
        }

        public async Task AddFixtureAsync(string id, string ecu,
            byte[] request, byte[] reply)
        {
            await using var con = new SqliteConnection(
                new SqliteConnectionStringBuilder
                {
                    DataSource = _path,
                    Mode = SqliteOpenMode.ReadWrite,
                    Pooling = false
                }.ToString());
            await con.OpenAsync();
            using (var fk = con.CreateCommand())
            {
                fk.CommandText = "PRAGMA foreign_keys=ON;";
                await fk.ExecuteNonQueryAsync();
            }
            using var tx = con.BeginTransaction();
            using (var insert = con.CreateCommand())
            {
                insert.Transaction = tx;
                insert.CommandText = """
                    INSERT INTO response_fixtures
                      (id,ecu_id,request_sha256,provenance,lab_approval,synthetic_reply,
                       private_artifact_id)
                    VALUES($id,$ecu,$hash,'synthetic','approved_for_readonly_lab',$reply,NULL);
                    """;
                insert.Parameters.AddWithValue("$id", id);
                insert.Parameters.AddWithValue("$ecu", ecu);
                insert.Parameters.AddWithValue("$hash", Hash(request));
                insert.Parameters.AddWithValue("$reply", reply);
                await insert.ExecuteNonQueryAsync();
            }
            using (var binding = con.CreateCommand())
            {
                binding.Transaction = tx;
                binding.CommandText = """
                    INSERT INTO scenario_bindings VALUES('revision-1',$fixture,1);
                    """;
                binding.Parameters.AddWithValue("$fixture", id);
                await binding.ExecuteNonQueryAsync();
            }
            tx.Commit();
        }

        public async Task SealAsync(string digest)
        {
            await using var con = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = _path, Pooling = false }.ToString());
            await con.OpenAsync();
            using var command = con.CreateCommand();
            command.CommandText = """
                UPDATE scenario_revisions SET sealed=1,snapshot_sha256=$digest
                WHERE id='revision-1' AND sealed=0;
                """;
            command.Parameters.AddWithValue("$digest", digest);
            Require(await command.ExecuteNonQueryAsync() == 1, "Could not seal scenario");
        }

        public async Task ExecuteAsync(string sql)
        {
            await using var con = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = _path, Pooling = false }.ToString());
            await con.OpenAsync();
            using var command = con.CreateCommand();
            command.CommandText = sql;
            await command.ExecuteNonQueryAsync();
        }

        public async ValueTask DisposeAsync()
        {
            await _catalog.DisposeAsync();
            try { Directory.Delete(_folder, true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
