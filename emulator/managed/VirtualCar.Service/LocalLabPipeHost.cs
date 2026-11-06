using System.IO.Pipes;
using System.Security.Cryptography;
using VirtualCar.Core;

namespace VirtualCar.Service;

/// <summary>
/// One-client Windows Named Pipe preflight for the private laboratory.
/// OS current-user isolation plus a separate 256-bit launch secret are required.
/// The launch secret must be provisioned out-of-band by a future trusted launcher.
/// NO CAN/ECU request can be executed through this host.
/// </summary>
public sealed class LocalLabPipeHost
{
    private readonly ScenarioCoordinator _coordinator;
    private readonly byte[] _secret;
    private readonly TimeSpan _ioDeadline;
    private int _serving;

    public LocalLabPipeHost(
        string pipeName,
        ScenarioCoordinator coordinator,
        byte[] launchSecret,
        TimeSpan? ioDeadline = null)
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

        // The host is a single-instance preflight endpoint. Concurrent start
        // attempts must fail deterministically instead of competing for
        // the same named pipe path or silently opening extra instances.
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
                await server.WaitForConnectionAsync(cancellationToken).ConfigureAwait(false);
            PipeFrame? hello = await ReadWithDeadlineAsync(server, cancellationToken).ConfigureAwait(false);
            if (hello is null || hello.Kind != PipeFrameCodec.Hello ||
                hello.SessionId != 0 || hello.Generation != 0 ||
                hello.Payload.Length != _secret.Length ||
                !CryptographicOperations.FixedTimeEquals(hello.Payload, _secret))
                return;

            // The only way to reach an authenticated session is through an
            // independently verified and activated synthetic Core scenario.
            session = await _coordinator.OpenSessionAsync(cancellationToken).ConfigureAwait(false);
            await WriteWithDeadlineAsync(server,
                new PipeFrame(PipeFrameCodec.Ack, session.Value.Id, session.Value.Generation, []),
                cancellationToken).ConfigureAwait(false);

            while (!cancellationToken.IsCancellationRequested)
            {
                PipeFrame? frame = await ReadWithDeadlineAsync(server, cancellationToken)
                    .ConfigureAwait(false);
                if (frame is null) return;
                if (frame.SessionId != session.Value.Id ||
                    frame.Generation != session.Value.Generation ||
                    frame.Payload.Length != 0 ||
                    frame.Kind is not (PipeFrameCodec.KeepAlive or PipeFrameCodec.Goodbye))
                    return;
                await _coordinator.ValidateSessionAsync(session.Value, cancellationToken)
                    .ConfigureAwait(false);
                if (frame.Kind == PipeFrameCodec.Goodbye) return;
                await WriteWithDeadlineAsync(server,
                    new PipeFrame(PipeFrameCodec.Ack, session.Value.Id, session.Value.Generation, []),
                    cancellationToken).ConfigureAwait(false);
            }
        }
        catch (Exception ex) when (ex is InvalidDataException or EndOfStreamException
            or IOException or InvalidOperationException ||
            ex is OperationCanceledException && !cancellationToken.IsCancellationRequested)
        {
            // Unexpected protocol and broken connections always fail closed.
            // Do not log secrets, message bytes or client-controlled details.
        }
            finally
            {
                if (session is SessionToken token)
                {
                    try { await _coordinator.CloseSessionAsync(token, CancellationToken.None).ConfigureAwait(false); }
                    catch (InvalidOperationException) { /* Reset/shutdown already invalidated it. */ }
                }
            }
        }
        finally
        {
            Volatile.Write(ref _serving, 0);
        }
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
