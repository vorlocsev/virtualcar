using System.Buffers.Binary;
using System.IO.Pipes;
using System.Security.Cryptography;
using VirtualCar.Core;
using VirtualCar.Service;

namespace VirtualCar.Service.Checks;

internal static class Program
{
    private static readonly byte[] LaunchSecret = Enumerable.Range(0, 32)
        .Select(i => (byte)(i * 7 + 3)).ToArray(); // Synthetic test only.

    private static async Task<int> Main(string[] args)
    {
        if (!OperatingSystem.IsWindows())
        {
            Console.Error.WriteLine("M5A integration checks must execute on Windows.");
            return 1;
        }
        // Cross-language M5B test mode. The secret is a synthetic CI fixture only.
        // "no-session" intentionally leaves the coordinator without an active scenario,
        // so a wrong-PID client must be rejected before it can authenticate.
        if ((args.Length == 3 || args.Length == 4) &&
            args[0] == "--serve-once" &&
            args[2] is "session" or "no-session" or "read-session" or "read-held" &&
            (args[2] != "read-held" || args.Length == 4) &&
            (args[2] == "read-held" || args.Length == 3))
        {
            string pipeName = args[1];
            if (string.IsNullOrEmpty(pipeName) || pipeName.Length > 80 ||
                !pipeName.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '-'))
                return 2;

            var runtime = new StubRuntime();
            bool selected = args[2] != "no-session";
            await using var core = await CoreAsync(
                selected: selected, runtime: runtime,
                readFixture: args[2] is "read-session" or "read-held");
            Func<CancellationToken, Task>? barrier = null;
            if (args[2] == "read-held")
            {
                string marker = args[3];
                if (!Path.IsPathFullyQualified(marker) ||
                    !Path.GetFileName(marker).EndsWith(".ready",
                        StringComparison.OrdinalIgnoreCase))
                    return 2;
                barrier = async token =>
                {
                    // Mark this read accepted only after VCRD identity,
                    // session, route and sealed fixture validation.
                    await File.WriteAllTextAsync(marker, "accepted", token);
                    await Task.Delay(TimeSpan.FromSeconds(6), token);
                };
            }
            await Host(core, pipeName, TimeSpan.FromSeconds(10), barrier)
                .ServeOnceAsync();

            int expectedPreparations = selected ? 1 : 0;
            if (runtime.PrepareCount != expectedPreparations)
            {
                Console.Error.WriteLine("Unexpected synthetic scenario preparation count.");
                return 3;
            }

            // Reset is a deliberate leak detector: it fails if GOODBYE or peer
            // disconnect left an authenticated core session active.
            if (selected)
                await core.ResetAsync();
            else
                Require(!await core.HasSelectedScenarioAsync(),
                    "Wrong-PID preflight unexpectedly activated a scenario.");
            return 0;
        }
        if (args.Length != 0)
        {
            Console.Error.WriteLine("Usage: VirtualCar.Service.Checks [--serve-once <pipe-name> <session|no-session|read-session> | --serve-once <pipe-name> read-held <absolute-ready-marker>]");
            return 2;
        }

        (string, Func<Task>)[] checks =
        [
            ("01 Authenticated HELLO and bounded keepalive", Test01),
            ("02 Missing verified synthetic scenario refuses open", Test02),
            ("03 Wrong 256-bit launch secret is rejected", Test03),
            ("04 Bad magic and protocol version are rejected", Test04),
            ("05 Oversize, negative length and truncated frames", Test05),
            ("06 Stale session generation fails closed", Test06),
            ("07 Forged session and unrecognized command are rejected", Test07),
            ("08 Disconnect and reconnect invalidate previous token", Test08),
            ("09 Idle accept deadline releases listener", Test09),
            ("10 Authenticated VCRD F187/F190 reads from sealed scenario", Test10),
            ("11 Read request with wrong Host process identity is rejected", Test11),
            ("12 Read request with unapproved CAN route is rejected", Test12),
            ("13 Read SecurityAccess and arbitrary service denied", Test13),
            ("14 Unknown DID and invalid VCRD kind denied", Test14),
            ("15 Replayed read operation rejected after positive reply", Test15),
            ("16 Unsealed or malformed VCRF fixture denied", Test16),
            ("17 Invalid VCRD reserved bytes and truncation denied", Test17)
        ];
        int passed = 0;
        foreach (var (label, check) in checks)
        {
            try
            {
                await check();
                Console.WriteLine("PASS " + label);
                passed++;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("FAIL " + label + " (" + ex.GetType().Name + ")");
            }
        }
        Console.WriteLine($"VirtualCar.Service Windows local IPC preflight: {passed}/{checks.Length}");
        return passed == checks.Length ? 0 : 1;
    }

    private static void Require(bool result, string message)
    {
        if (!result) throw new InvalidOperationException(message);
    }

    private static async Task<ScenarioCoordinator> CoreAsync(
        bool selected = true, StubRuntime? runtime = null, bool readFixture = false)
    {
        var core = new ScenarioCoordinator(
            new StubCatalog(readFixture), runtime ?? new StubRuntime());
        if (selected) await core.SelectAsync("ipc-synthetic", 1);
        return core;
    }

    private static LocalLabPipeHost Host(
        ScenarioCoordinator core, string? name = null, TimeSpan? deadline = null,
        Func<CancellationToken, Task>? barrier = null) =>
        new(name ?? "vcm5-" + Guid.NewGuid().ToString("N"), core, LaunchSecret,
            deadline ?? TimeSpan.FromSeconds(3), barrier);

    private static async Task<NamedPipeClientStream> ConnectAsync(string name)
    {
        var pipe = new NamedPipeClientStream(".", name, PipeDirection.InOut,
            PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
        try
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            await pipe.ConnectAsync(timeout.Token);
            return pipe;
        }
        catch
        {
            await pipe.DisposeAsync();
            throw;
        }
    }

    private static async Task<PipeFrame> HelloAsync(Stream client, byte[]? secret = null)
    {
        await PipeFrameCodec.WriteAsync(client,
            new PipeFrame(PipeFrameCodec.Hello, 0, 0, secret ?? LaunchSecret));
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(4));
        PipeFrame? response = await PipeFrameCodec.ReadAsync(client, timeout.Token);
        Require(response?.Kind == PipeFrameCodec.Ack &&
            response.SessionId != 0 && response.Generation != 0 &&
            response.Payload.Length == 0, "Authentication did not create a real core session");
        return response!;
    }

    private static async Task ExpectClosedAsync(Stream client)
    {
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(4));
        try
        {
            PipeFrame? unexpected = await PipeFrameCodec.ReadAsync(client, timeout.Token);
            Require(unexpected is null, "Unexpected positive laboratory IPC response");
        }
        catch (IOException) { /* Windows reports a closed peer as broken pipe. */ }
    }

    private static async Task RunClosedAsync(
        Func<NamedPipeClientStream, Task> clientAction,
        bool selected = true, bool readFixture = false)
    {
        await using var core = await CoreAsync(selected, readFixture: readFixture);
        LocalLabPipeHost host = Host(core);
        Task serving = host.ServeOnceAsync();
        await using (var client = await ConnectAsync(host.PipeName))
            await clientAction(client);
        await serving.WaitAsync(TimeSpan.FromSeconds(5));
        if (selected)
            await core.ResetAsync(); // Proves the IPC session was closed.
        else
            Require(!await core.HasSelectedScenarioAsync(), "Unselected scenario activated");
    }

    private static async Task Test01()
    {
        await RunClosedAsync(async client =>
        {
            PipeFrame authenticated = await HelloAsync(client);
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.KeepAlive, authenticated.SessionId,
                    authenticated.Generation, []));
            PipeFrame? reply = await PipeFrameCodec.ReadAsync(client);
            Require(reply?.Kind == PipeFrameCodec.Ack &&
                reply.SessionId == authenticated.SessionId &&
                reply.Generation == authenticated.Generation, "Keepalive was not session-bound");
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.Goodbye, authenticated.SessionId,
                    authenticated.Generation, []));
            await ExpectClosedAsync(client);
        });
    }

    private static async Task Test02() => await RunClosedAsync(async client =>
    {
        await PipeFrameCodec.WriteAsync(client,
            new PipeFrame(PipeFrameCodec.Hello, 0, 0, LaunchSecret));
        await ExpectClosedAsync(client);
    }, selected: false);

    private static async Task Test03()
    {
        await RunClosedAsync(async client =>
        {
            byte[] wrong = LaunchSecret.ToArray();
            wrong[^1] ^= 0x80;
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.Hello, 0, 0, wrong));
            await ExpectClosedAsync(client);
        });
        await RunClosedAsync(async client =>
        {
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.Hello, 0, 1, LaunchSecret));
            await ExpectClosedAsync(client);
        });
    }

    private static async Task SendRawAsync(Stream client, Action<byte[]> mutate, int? truncate = null)
    {
        using var buffer = new MemoryStream();
        await PipeFrameCodec.WriteAsync(buffer,
            new PipeFrame(PipeFrameCodec.Hello, 0, 0, LaunchSecret));
        byte[] raw = buffer.ToArray();
        mutate(raw);
        if (truncate is int length) raw = raw[..length];
        // The server may reject and close immediately after reading the
        // 28-byte invalid header, before Windows has accepted the remaining
        // bytes. A broken-pipe write is an expected fail-closed result here,
        // but the caller must independently verify that no ACK is returned.
        try { await client.WriteAsync(raw); }
        catch (IOException) { /* The hostile frame was rejected early. */ }
    }

    private static async Task Test04()
    {
        await RunClosedAsync(async client =>
        {
            await SendRawAsync(client, b => b[0] = (byte)'X');
            await ExpectClosedAsync(client);
        });
        await RunClosedAsync(async client =>
        {
            await SendRawAsync(client, b => BinaryPrimitives.WriteUInt16LittleEndian(
                b.AsSpan(4), PipeFrameCodec.Version + 1));
            await ExpectClosedAsync(client);
        });
    }

    private static async Task Test05()
    {
        await RunClosedAsync(async client =>
        {
            await SendRawAsync(client, b => BinaryPrimitives.WriteInt32LittleEndian(
                b.AsSpan(8), PipeFrameCodec.MaximumPayload + 1));
            await ExpectClosedAsync(client);
        });
        await RunClosedAsync(async client =>
        {
            await SendRawAsync(client, b => BinaryPrimitives.WriteInt32LittleEndian(
                b.AsSpan(8), -1));
            await ExpectClosedAsync(client);
        });
        // Incomplete header: the reader must never treat it as a HELLO.
        await RunClosedAsync(async client =>
        {
            await SendRawAsync(client, _ => { }, truncate: 8);
        });
        // After successful authentication, disconnect before the declared
        // body is complete. The server must release the core session, not
        // return an ACK for the partial keepalive.
        await RunClosedAsync(async client =>
        {
            PipeFrame authenticated = await HelloAsync(client);
            using var buffer = new MemoryStream();
            await PipeFrameCodec.WriteAsync(buffer,
                new PipeFrame(PipeFrameCodec.KeepAlive, authenticated.SessionId,
                    authenticated.Generation, []));
            byte[] incomplete = buffer.ToArray();
            BinaryPrimitives.WriteInt32LittleEndian(incomplete.AsSpan(8), 4);
            await client.WriteAsync(incomplete);
            await client.WriteAsync(new byte[] { 0x11 }); // Only 1 of 4 bytes.
            // RunClosedAsync disposes the client here; the server must fail closed.
        });
    }

    private static async Task Test06() => await RunClosedAsync(async client =>
    {
        PipeFrame authenticated = await HelloAsync(client);
        await PipeFrameCodec.WriteAsync(client,
            new PipeFrame(PipeFrameCodec.KeepAlive, authenticated.SessionId,
                authenticated.Generation + 1, []));
        await ExpectClosedAsync(client);
    });

    private static async Task Test07()
    {
        await RunClosedAsync(async client =>
        {
            PipeFrame authenticated = await HelloAsync(client);
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.KeepAlive, authenticated.SessionId + 1,
                    authenticated.Generation, []));
            await ExpectClosedAsync(client);
        });
        await RunClosedAsync(async client =>
        {
            await HelloAsync(client);
            byte[] raw = new byte[PipeFrameCodec.HeaderLength];
            "VCLB"u8.CopyTo(raw);
            BinaryPrimitives.WriteUInt16LittleEndian(raw.AsSpan(4), PipeFrameCodec.Version);
            BinaryPrimitives.WriteUInt16LittleEndian(raw.AsSpan(6), 99);
            try { await client.WriteAsync(raw); }
            catch (IOException) { /* Deliberate unsupported command rejected early. */ }
            await ExpectClosedAsync(client);
        });
    }

    private static async Task Test08()
    {
        await using var core = await CoreAsync();
        string pipeName = "vcm5-" + Guid.NewGuid().ToString("N");
        var host = Host(core, pipeName);
        Task firstServing = host.ServeOnceAsync();
        PipeFrame first;
        await using (var client = await ConnectAsync(pipeName))
        {
            first = await HelloAsync(client);
            bool rejectedSecondListener = false;
            try { await host.ServeOnceAsync(); }
            catch (InvalidOperationException) { rejectedSecondListener = true; }
            Require(rejectedSecondListener,
                "Concurrent listener start was not rejected");
        } // Abrupt disconnect, no GOODBYE.
        await firstServing.WaitAsync(TimeSpan.FromSeconds(5));
        await core.ResetAsync(); // Must have no leaked session.
        Task secondServing = host.ServeOnceAsync();
        await using (var client = await ConnectAsync(pipeName))
        {
            PipeFrame second = await HelloAsync(client);
            Require(second.SessionId != first.SessionId && second.Generation != first.Generation,
                "Reconnect reused stale session identity");
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.Goodbye, second.SessionId, second.Generation, []));
        }
        await secondServing.WaitAsync(TimeSpan.FromSeconds(5));
        await core.ResetAsync();
    }

    private static async Task Test09()
    {
        await using var core = await CoreAsync();
        var host = Host(core, deadline: TimeSpan.FromMilliseconds(250));

        // No client connects: both one-shot accepts must expire and release
        // the listener guard rather than leaving ServeOnceAsync pending.
        await host.ServeOnceAsync().WaitAsync(TimeSpan.FromSeconds(3));
        await host.ServeOnceAsync().WaitAsync(TimeSpan.FromSeconds(3));

        SessionToken token = await core.OpenSessionAsync();
        await core.CloseSessionAsync(token);
        await core.ResetAsync();
    }

    // Invented data only. VCRF v1 route 0x7e0->0x7e8, three sorted
    // DIDs and small synthetic response bytes, SHA256-sealed by the catalog.
    private static byte[] ReadFixtureBytes() =>
    [
        (byte)'V', (byte)'C', (byte)'R', (byte)'F',
        1, 0, 0xe0, 0x07, 0, 0, 0xe8, 0x07, 0, 0, 3,
        0xf1, 0x87, 2, (byte)'A', (byte)'B',
        0xf1, 0x89, 1, (byte)'C',
        0xf1, 0x90, 3, (byte)'L', (byte)'A', (byte)'B'
    ];

    private static VcrdEnvelope ReadRequest(
        PipeFrame session, ulong operation = 1, ushort did = 0xF187,
        uint requestId = 0x7e0, uint responseId = 0x7e8,
        bool extended = false)
    {
        return new VcrdEnvelope(
            VcrdCodec.ReadRequest, operation, session.SessionId,
            session.Generation, (uint)Environment.ProcessId,
            VcrdCodec.CurrentHostCreationTime(), requestId, responseId,
            extended, [0x22, (byte)(did >> 8), (byte)did]);
    }

    private static async Task SendReadRawAsync(
        Stream client, PipeFrame session, byte[] bytes)
    {
        await PipeFrameCodec.WriteAsync(client,
            new PipeFrame(PipeFrameCodec.ReadRequest, session.SessionId,
                session.Generation, bytes));
    }

    private static async Task<VcrdEnvelope> ReadResultAsync(
        Stream client, PipeFrame session, VcrdEnvelope request)
    {
        await SendReadRawAsync(client, session, VcrdCodec.Encode(request));
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
        PipeFrame? response = await PipeFrameCodec.ReadAsync(client, timeout.Token);
        Require(response is not null &&
            response.Kind == PipeFrameCodec.ReadReply &&
            response.SessionId == session.SessionId &&
            response.Generation == session.Generation,
            "Uncorrelated or missing outer VCLB read response.");
        Require(VcrdCodec.TryDecode(response!.Payload, out VcrdEnvelope? decoded) &&
            decoded is not null &&
            decoded.Kind == VcrdCodec.ReadResponse &&
            decoded.OperationId == request.OperationId &&
            decoded.SessionId == session.SessionId &&
            decoded.Generation == session.Generation &&
            decoded.ServerPid == request.ServerPid &&
            decoded.Created100Ns == request.Created100Ns &&
            decoded.RequestCanId == request.RequestCanId &&
            decoded.ResponseCanId == request.ResponseCanId &&
            decoded.Extended == request.Extended,
            "Uncorrelated or malformed VCRD positive read response.");
        return decoded!;
    }

    private static async Task Test10()
    {
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            VcrdEnvelope first = await ReadResultAsync(
                client, token, ReadRequest(token, 1, 0xF187));
            Require(first.Payload.SequenceEqual(new byte[]
                { 0x62, 0xf1, 0x87, (byte)'A', (byte)'B' }),
                "F187 fixture is not identical to immutable canonical scenario.");
            VcrdEnvelope second = await ReadResultAsync(
                client, token, ReadRequest(token, 2, 0xF190));
            Require(second.Payload.SequenceEqual(new byte[]
                { 0x62, 0xf1, 0x90, (byte)'L', (byte)'A', (byte)'B' }),
                "F190 fixture bytes were not scenario derived.");
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.KeepAlive,
                    token.SessionId, token.Generation, []));
            PipeFrame? ack = await PipeFrameCodec.ReadAsync(client);
            Require(ack?.Kind == PipeFrameCodec.Ack, "Read broke authenticated keepalive.");
            await PipeFrameCodec.WriteAsync(client,
                new PipeFrame(PipeFrameCodec.Goodbye,
                    token.SessionId, token.Generation, []));
            await ExpectClosedAsync(client);
        }, readFixture: true);
    }

    private static async Task Test11() =>
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            VcrdEnvelope wrong = ReadRequest(token) with
            {
                Created100Ns = VcrdCodec.CurrentHostCreationTime() + 1
            };
            await SendReadRawAsync(client, token, VcrdCodec.Encode(wrong));
            await ExpectClosedAsync(client);
        }, readFixture: true);

    private static async Task Test12() =>
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            await SendReadRawAsync(client, token,
                VcrdCodec.Encode(ReadRequest(token, requestId: 0x7e1)));
            await ExpectClosedAsync(client);
        }, readFixture: true);

    private static async Task Test13() =>
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            byte[] wire = VcrdCodec.Encode(ReadRequest(token));
            wire[VcrdCodec.HeaderLength] = 0x27; // SecurityAccess, not read.
            await SendReadRawAsync(client, token, wire);
            await ExpectClosedAsync(client);
        }, readFixture: true);

    private static async Task Test14()
    {
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            byte[] wire = VcrdCodec.Encode(ReadRequest(token));
            wire[VcrdCodec.HeaderLength + 2] = 0x91; // Unknown DID.
            await SendReadRawAsync(client, token, wire);
            await ExpectClosedAsync(client);
        }, readFixture: true);
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            byte[] wire = VcrdCodec.Encode(ReadRequest(token));
            BinaryPrimitives.WriteUInt16LittleEndian(wire.AsSpan(6), 99);
            await SendReadRawAsync(client, token, wire);
            await ExpectClosedAsync(client);
        }, readFixture: true);
    }

    private static async Task Test15() =>
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            VcrdEnvelope req = ReadRequest(token);
            _ = await ReadResultAsync(client, token, req);
            await SendReadRawAsync(client, token, VcrdCodec.Encode(req));
            await ExpectClosedAsync(client);
        }, readFixture: true);

    private static async Task Test16()
    {
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            await SendReadRawAsync(client, token,
                VcrdCodec.Encode(ReadRequest(token)));
            await ExpectClosedAsync(client);
        }); // selected old scenario, not a VCRF response map

        byte[] malformed = ReadFixtureBytes();
        byte[] withTrailing = [.. malformed, 0xff];
        ScenarioSnapshot candidate = ScenarioSnapshot.VerifySynthetic(
            new ScenarioCandidate("ipc-synthetic", 1,
                ScenarioProvenance.Synthetic, true, withTrailing,
                Convert.ToHexString(SHA256.HashData(withTrailing))));
        Require(SyntheticReadFixture.Find(
                candidate, 0x7e0, 0x7e8, false, 0xF187) is null,
            "VCRF parser accepted a trailing record outside sealed framing.");

        malformed[17] = 62; // first entry claims oversized response data
        candidate = ScenarioSnapshot.VerifySynthetic(
            new ScenarioCandidate("ipc-synthetic", 1,
                ScenarioProvenance.Synthetic, true, malformed,
                Convert.ToHexString(SHA256.HashData(malformed))));
        Require(SyntheticReadFixture.Find(
                candidate, 0x7e0, 0x7e8, false, 0xF187) is null,
            "VCRF parser accepted an oversized entry.");
    }

    private static async Task Test17()
    {
        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            byte[] wire = VcrdCodec.Encode(ReadRequest(token));
            wire[56] = 1; // Reserved field is mandatory zero.
            await SendReadRawAsync(client, token, wire);
            await ExpectClosedAsync(client);
        }, readFixture: true);

        await RunClosedAsync(async client =>
        {
            PipeFrame token = await HelloAsync(client);
            byte[] wire = VcrdCodec.Encode(ReadRequest(token));
            await SendReadRawAsync(client, token, wire[..^1]);
            await ExpectClosedAsync(client);
        }, readFixture: true);
    }

    private sealed class StubCatalog(bool readFixture = false) : IScenarioCatalog
    {
        public Task<ScenarioCandidate?> LoadAsync(string id, long revision, CancellationToken ct)
        {
            ct.ThrowIfCancellationRequested();
            byte[] bytes = readFixture
                ? ReadFixtureBytes()
                : [0x22, 0xF1, 0x87]; // Old M5A scenario, NOT a VCRF response map.
            return Task.FromResult<ScenarioCandidate?>(new ScenarioCandidate(
                "ipc-synthetic", 1, ScenarioProvenance.Synthetic, true,
                bytes, Convert.ToHexString(SHA256.HashData(bytes))));
        }
    }

    private sealed class StubRuntime : IScenarioRuntime
    {
        public int PrepareCount { get; private set; }

        public Task PrepareAsync(ScenarioSnapshot snapshot, CancellationToken ct)
        {
            PrepareCount++;
            return Task.CompletedTask;
        }

        public Task StopAsync(CancellationToken ct) => Task.CompletedTask;
    }
}
