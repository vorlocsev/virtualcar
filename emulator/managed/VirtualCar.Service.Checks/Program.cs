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
            Console.Error.WriteLine("M5A/M5B integration checks must execute on Windows.");
            return 1;
        }

        // Cross-language test mode: host one already-approved synthetic
        // scenario for a native C++ x86/x64 client. The fixed secret is
        // test-only and is never used by a production launcher.
        if (args.Length == 2 && args[0] == "--serve-once")
        {
            string pipeName = args[1];
            if (string.IsNullOrEmpty(pipeName) || pipeName.Length > 80 ||
                !pipeName.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '-'))
                return 2;
            await using var core = await CoreAsync();
            await Host(core, pipeName).ServeOnceAsync();
            return 0;
        }
        if (args.Length != 0)
        {
            Console.Error.WriteLine("Usage: VirtualCar.Service.Checks [--serve-once <pipe-name>]");
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
            ("08 Disconnect and reconnect invalidate previous token", Test08)
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

    private static async Task<ScenarioCoordinator> CoreAsync(bool selected = true)
    {
        var core = new ScenarioCoordinator(new StubCatalog(), new StubRuntime());
        if (selected) await core.SelectAsync("ipc-synthetic", 1);
        return core;
    }

    private static LocalLabPipeHost Host(ScenarioCoordinator core, string? name = null) =>
        new(name ?? "vcm5-" + Guid.NewGuid().ToString("N"), core, LaunchSecret,
            TimeSpan.FromSeconds(3));

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
        Func<NamedPipeClientStream, Task> clientAction, bool selected = true)
    {
        await using var core = await CoreAsync(selected);
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

    private sealed class StubCatalog : IScenarioCatalog
    {
        public Task<ScenarioCandidate?> LoadAsync(string id, long revision, CancellationToken ct)
        {
            ct.ThrowIfCancellationRequested();
            byte[] bytes = [0x22, 0xF1, 0x87]; // Invented read-only synthetic fixture.
            return Task.FromResult<ScenarioCandidate?>(new ScenarioCandidate(
                "ipc-synthetic", 1, ScenarioProvenance.Synthetic, true,
                bytes, Convert.ToHexString(SHA256.HashData(bytes))));
        }
    }

    private sealed class StubRuntime : IScenarioRuntime
    {
        public Task PrepareAsync(ScenarioSnapshot snapshot, CancellationToken ct) =>
            Task.CompletedTask;
        public Task StopAsync(CancellationToken ct) => Task.CompletedTask;
    }
}
