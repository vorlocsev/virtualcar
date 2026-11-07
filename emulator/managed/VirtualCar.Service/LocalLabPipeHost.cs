using System.IO.Pipes;
using System.Security.Cryptography;
using VirtualCar.Core;

namespace VirtualCar.Service;

/// <summary>
/// One-client Windows Named Pipe preflight for the private laboratory.
/// OS current-user isolation plus a separate 256-bit launch secret are required.
/// The launch secret must be provisioned out-of-band by a future trusted launcher.
/// Only sealed synthetic identification reads are allowed by M5D-2a.
/// No raw CAN, physical J2534, arbitrary ECU request or programming.
/// </summary>
public sealed class LocalLabPipeHost
{
    private readonly ScenarioCoordinator _coordinator;
    private readonly byte[] _secret;
    private readonly TimeSpan _ioDeadline;
    // Test-only deterministic barrier. Production builds never supply this.
    // Only invoked after authenticated, verified synthetic fixture read.
    private readonly Func<CancellationToken, Task>? _syntheticReadBarrier;
    private int _serving;

    public LocalLabPipeHost(
        string pipeName,
        ScenarioCoordinator coordinator,
        byte[] launchSecret,
        TimeSpan? ioDeadline = null,
        Func<CancellationToken, Task>? syntheticReadBarrier = null)
    {
        if (string.IsNullOrEmpty(pipeName) || pipeName.Length > 80 ||
            !pipeName.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '-'))
            throw new ArgumentException("Invalid private laboratory pipe name.", nameof(pipeName));
        ArgumentNullException.ThrowIfNull(coordinator);
        ArgumentNullException.ThrowIfNull(launchSecret);
        if (launchSecret.Length != 32)
            throw new ArgumentException("A 256-bit launch secret is required.", nameof(launchSecret));
        TimeSpan deadline = ioDeadline ?? TimeSpan.FromSeconds(5);
        if (deadline < TimeSpan.FromMilliseconds(100) || deadline > TimeSpan.FromMinutes(1))
            throw new ArgumentOutOfRangeException(nameof(ioDeadline));

        PipeName = pipeName;
        _coordinator = coordinator;
        _secret = launchSecret.ToArray();
        _ioDeadline = deadline;
        _syntheticReadBarrier = syntheticReadBarrier;
    }

    public string PipeName { get; }

    /// <summary>
    /// Exactly one connection. No network socket or named pipe registry changes.
    /// Each new connection must authenticate and receive a new core session.
    /// </summary>
    public async Task ServeOnceAsync(CancellationToken cancellationToken = default)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("M5 local pipe host requires Windows.");

        // Only one active listener may own this private pipe host at a time.
        // Reset the guard even if creating the OS pipe itself fails.
        if (Interlocked.CompareExchange(ref _serving, 1, 0) != 0)
            throw new InvalidOperationException("A laboratory IPC listener is already running.");
        try
        {
            using var server = new NamedPipeServerStream(
                PipeName, PipeDirection.InOut, 1, PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
            SessionToken? session = null;
            try
            {
                await WaitForConnectionWithDeadlineAsync(server, cancellationToken)
                    .ConfigureAwait(false);
                PipeFrame? hello = await ReadWithDeadlineAsync(server, cancellationToken)
                    .ConfigureAwait(false);
                if (hello is null || hello.Kind != PipeFrameCodec.Hello ||
                    hello.SessionId != 0 || hello.Generation != 0 ||
                    hello.Payload.Length != _secret.Length ||
                    !CryptographicOperations.FixedTimeEquals(hello.Payload, _secret))
                    return;

                // Only an independently verified synthetic scenario permits
                // the creation of a laboratory core session.
                session = await _coordinator.OpenSessionAsync(cancellationToken)
                    .ConfigureAwait(false);
                await WriteWithDeadlineAsync(server,
                    new PipeFrame(PipeFrameCodec.Ack, session.Value.Id,
                        session.Value.Generation, []),
                    cancellationToken).ConfigureAwait(false);

                // Every read request is correlated monotonically inside
                // this one authenticated connection. A restarted Host has
                // a new process-creation identity and reauthenticates.
                ulong lastReadOperationId = 0;
                ulong serverCreated = VcrdCodec.CurrentHostCreationTime();
                while (!cancellationToken.IsCancellationRequested)
                {
                    PipeFrame? frame = await ReadWithDeadlineAsync(server, cancellationToken)
                        .ConfigureAwait(false);
                    if (frame is null) return;
                    if (frame.SessionId != session.Value.Id ||
                        frame.Generation != session.Value.Generation)
                        return;
                    await _coordinator.ValidateSessionAsync(session.Value, cancellationToken)
                        .ConfigureAwait(false);

                    if (frame.Kind is PipeFrameCodec.KeepAlive or PipeFrameCodec.Goodbye)
                    {
                        if (frame.Payload.Length != 0) return;
                        if (frame.Kind == PipeFrameCodec.Goodbye) return;
                        await WriteWithDeadlineAsync(server,
                            new PipeFrame(PipeFrameCodec.Ack, session.Value.Id,
                                session.Value.Generation, []),
                            cancellationToken).ConfigureAwait(false);
                        continue;
                    }

                    // Only a 63-byte VCRD read request is accepted, never a
                    // raw CAN frame or a generic caller-provided response.
                    if (frame.Kind != PipeFrameCodec.ReadRequest ||
                        frame.Payload.Length != VcrdCodec.HeaderLength + 3 ||
                        !VcrdCodec.TryDecode(frame.Payload, out VcrdEnvelope? request) ||
                        request is null ||
                        request.Kind != VcrdCodec.ReadRequest ||
                        request.SessionId != session.Value.Id ||
                        request.Generation != session.Value.Generation ||
                        request.ServerPid != (uint)Environment.ProcessId ||
                        request.Created100Ns != serverCreated ||
                        request.OperationId <= lastReadOperationId)
                        return;

                    // The coordinator validates that the *current* session
                    // still owns an immutable, verified synthetic scenario.
                    // Missing or malformed VCRF fixtures fail CLOSED.
                    ushort did = System.Buffers.Binary.BinaryPrimitives
                        .ReadUInt16BigEndian(request.Payload.AsSpan(1, 2));
                    byte[]? synthetic = await _coordinator.ReadSyntheticAsync(
                        session.Value, request.RequestCanId, request.ResponseCanId,
                        request.Extended, did, cancellationToken).ConfigureAwait(false);
                    if (synthetic is null || synthetic.Length is < 1 or > 61)
                        return;

                    // A restricted, test-supplied barrier makes it possible
                    // to kill or cancel an ALREADY accepted read, not merely
                    // a waiting HELLO. Production Host has no barrier.
                    if (_syntheticReadBarrier is not null)
                    {
                        using var hold = CancellationTokenSource.CreateLinkedTokenSource(
                            cancellationToken);
                        hold.CancelAfter(_ioDeadline);
                        await _syntheticReadBarrier(hold.Token).ConfigureAwait(false);
                    }

                    lastReadOperationId = request.OperationId;
                    byte[] positive = new byte[3 + synthetic.Length];
                    positive[0] = 0x62;
                    positive[1] = request.Payload[1];
                    positive[2] = request.Payload[2];
                    synthetic.CopyTo(positive, 3);
                    byte[] encoded = VcrdCodec.Encode(request with
                    {
                        Kind = VcrdCodec.ReadResponse,
                        Payload = positive
                    });
                    await WriteWithDeadlineAsync(server,
                        new PipeFrame(PipeFrameCodec.ReadReply, session.Value.Id,
                            session.Value.Generation, encoded),
                        cancellationToken).ConfigureAwait(false);
                }
            }
            catch (Exception ex) when (ex is InvalidDataException or EndOfStreamException
                or IOException or InvalidOperationException ||
                ex is OperationCanceledException && !cancellationToken.IsCancellationRequested)
            {
                // Protocol failure, timeout and broken peer all fail closed.
                // Do not log credentials or peer-controlled message bytes.
            }
            finally
            {
                if (session is SessionToken token)
                {
                    try
                    {
                        await _coordinator.CloseSessionAsync(token, CancellationToken.None)
                            .ConfigureAwait(false);
                    }
                    catch (InvalidOperationException)
                    {
                        // Core reset/shutdown may already have invalidated it.
                    }
                }
            }
        }
        finally
        {
            Volatile.Write(ref _serving, 0);
        }
    }

    private async Task WaitForConnectionWithDeadlineAsync(
        NamedPipeServerStream server, CancellationToken cancellationToken)
    {
        // An idle one-shot listener must not hold a host operation open forever.
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(_ioDeadline);
        await server.WaitForConnectionAsync(timeout.Token).ConfigureAwait(false);
    }

    private async Task WriteWithDeadlineAsync(
        Stream stream, PipeFrame frame, CancellationToken cancellationToken)
    {
        // A stalled client must not hold a validated synthetic session open
        // indefinitely while the server is trying to send an ACK.
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(_ioDeadline);
        await PipeFrameCodec.WriteAsync(stream, frame, timeout.Token).ConfigureAwait(false);
    }

    private async Task<PipeFrame?> ReadWithDeadlineAsync(
        Stream stream, CancellationToken cancellationToken)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(_ioDeadline);
        return await PipeFrameCodec.ReadAsync(stream, timeout.Token).ConfigureAwait(false);
    }
}
