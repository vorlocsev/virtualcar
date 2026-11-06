using System.Buffers.Binary;

namespace VirtualCar.Service;

/// <summary>
/// Strict, versioned, local-only M5 preflight envelope. No ECU/CAN commands
/// or scenario administration are permitted on this data endpoint.
/// </summary>
public static class PipeFrameCodec
{
    public const ushort Version = 1;
    public const int HeaderLength = 28;
    public const int MaximumPayload = 256;
    public const ushort Hello = 1;
    public const ushort KeepAlive = 2;
    public const ushort Goodbye = 3;
    public const ushort Ack = 4;
    private static ReadOnlySpan<byte> Magic => "VCLB"u8;

    public static async Task WriteAsync(Stream stream, PipeFrame frame, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(stream);
        ArgumentNullException.ThrowIfNull(frame);
        ArgumentNullException.ThrowIfNull(frame.Payload);
        if (frame.Payload.Length > MaximumPayload || !Supported(frame.Kind))
            throw new InvalidDataException("Unsupported or oversized laboratory frame.");

        byte[] header = new byte[HeaderLength];
        Magic.CopyTo(header);
        BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(4), Version);
        BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(6), frame.Kind);
        BinaryPrimitives.WriteInt32LittleEndian(header.AsSpan(8), frame.Payload.Length);
        BinaryPrimitives.WriteUInt64LittleEndian(header.AsSpan(12), frame.SessionId);
        BinaryPrimitives.WriteUInt64LittleEndian(header.AsSpan(20), frame.Generation);
        await stream.WriteAsync(header, cancellationToken).ConfigureAwait(false);
        if (frame.Payload.Length != 0)
            await stream.WriteAsync(frame.Payload, cancellationToken).ConfigureAwait(false);
        await stream.FlushAsync(cancellationToken).ConfigureAwait(false);
    }

    public static async Task<PipeFrame?> ReadAsync(Stream stream, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(stream);
        byte[] header = new byte[HeaderLength];
        int received = await stream.ReadAsync(header, cancellationToken).ConfigureAwait(false);
        if (received == 0) return null;
        if (received < HeaderLength)
            await stream.ReadExactlyAsync(header.AsMemory(received), cancellationToken).ConfigureAwait(false);

        if (!header.AsSpan(0, 4).SequenceEqual(Magic) ||
            BinaryPrimitives.ReadUInt16LittleEndian(header.AsSpan(4)) != Version)
            throw new InvalidDataException("Invalid laboratory frame version.");

        ushort kind = BinaryPrimitives.ReadUInt16LittleEndian(header.AsSpan(6));
        int length = BinaryPrimitives.ReadInt32LittleEndian(header.AsSpan(8));
        if (!Supported(kind) || length is < 0 or > MaximumPayload)
            throw new InvalidDataException("Invalid laboratory frame kind or length.");

        byte[] body = new byte[length];
        if (length != 0)
            await stream.ReadExactlyAsync(body, cancellationToken).ConfigureAwait(false);
        return new PipeFrame(kind,
            BinaryPrimitives.ReadUInt64LittleEndian(header.AsSpan(12)),
            BinaryPrimitives.ReadUInt64LittleEndian(header.AsSpan(20)), body);
    }

    private static bool Supported(ushort kind) =>
        kind is Hello or KeepAlive or Goodbye or Ack;
}

public sealed record PipeFrame(ushort Kind, ulong SessionId, ulong Generation, byte[] Payload);
