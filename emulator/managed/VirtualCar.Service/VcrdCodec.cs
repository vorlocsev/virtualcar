using System.Buffers.Binary;
using System.Diagnostics;
using VirtualCar.Core;

namespace VirtualCar.Service;

/// <summary>
/// Proposed M5D VCRD v1 read-only envelope; transported only inside an
/// authenticated VCLB current-user pipe session. Not a J2534 frame.
/// </summary>
public static class VcrdCodec
{
    public const ushort Version = 1;
    public const ushort ReadRequest = 1;
    public const ushort ReadResponse = 2;
    public const int HeaderLength = 60;
    public const int MaximumPayload = 64;
    public const int MaximumWireLength = HeaderLength + MaximumPayload;

    public static ulong CurrentHostCreationTime()
    {
        using Process process = Process.GetCurrentProcess();
        return checked((ulong)process.StartTime.ToFileTimeUtc());
    }

    public static byte[] Encode(VcrdEnvelope frame)
    {
        ArgumentNullException.ThrowIfNull(frame);
        if (!Valid(frame)) throw new InvalidDataException("Invalid synthetic read envelope.");

        byte[] result = new byte[HeaderLength + frame.Payload.Length];
        "VCRD"u8.CopyTo(result);
        BinaryPrimitives.WriteUInt16LittleEndian(result.AsSpan(4), Version);
        BinaryPrimitives.WriteUInt16LittleEndian(result.AsSpan(6), frame.Kind);
        BinaryPrimitives.WriteUInt16LittleEndian(result.AsSpan(8),
            checked((ushort)frame.Payload.Length));
        BinaryPrimitives.WriteUInt16LittleEndian(result.AsSpan(10),
            frame.Extended ? (ushort)1 : (ushort)0);
        BinaryPrimitives.WriteUInt64LittleEndian(result.AsSpan(12), frame.OperationId);
        BinaryPrimitives.WriteUInt64LittleEndian(result.AsSpan(20), frame.SessionId);
        BinaryPrimitives.WriteUInt64LittleEndian(result.AsSpan(28), frame.Generation);
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(36), frame.ServerPid);
        BinaryPrimitives.WriteUInt64LittleEndian(result.AsSpan(40), frame.Created100Ns);
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(48), frame.RequestCanId);
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(52), frame.ResponseCanId);
        // Reserved bytes 56..59 remain zero.
        frame.Payload.CopyTo(result, HeaderLength);
        return result;
    }

    public static bool TryDecode(ReadOnlySpan<byte> wire, out VcrdEnvelope? result)
    {
        result = null;
        if (wire.Length is < HeaderLength or > MaximumWireLength ||
            !wire[..4].SequenceEqual("VCRD"u8) ||
            BinaryPrimitives.ReadUInt16LittleEndian(wire[4..]) != Version ||
            BinaryPrimitives.ReadUInt32LittleEndian(wire[56..]) != 0)
            return false;
        ushort length = BinaryPrimitives.ReadUInt16LittleEndian(wire[8..]);
        ushort flags = BinaryPrimitives.ReadUInt16LittleEndian(wire[10..]);
        if (flags > 1 || length > MaximumPayload ||
            wire.Length != HeaderLength + length)
            return false;
        var frame = new VcrdEnvelope(
            BinaryPrimitives.ReadUInt16LittleEndian(wire[6..]),
            BinaryPrimitives.ReadUInt64LittleEndian(wire[12..]),
            BinaryPrimitives.ReadUInt64LittleEndian(wire[20..]),
            BinaryPrimitives.ReadUInt64LittleEndian(wire[28..]),
            BinaryPrimitives.ReadUInt32LittleEndian(wire[36..]),
            BinaryPrimitives.ReadUInt64LittleEndian(wire[40..]),
            BinaryPrimitives.ReadUInt32LittleEndian(wire[48..]),
            BinaryPrimitives.ReadUInt32LittleEndian(wire[52..]),
            flags == 1, wire[HeaderLength..].ToArray());
        if (!Valid(frame)) return false;
        result = frame;
        return true;
    }

    private static bool Valid(VcrdEnvelope f)
    {
        if (f.Payload is null || f.Payload.Length > MaximumPayload ||
            f.OperationId == 0 || f.SessionId == 0 || f.Generation == 0 ||
            f.ServerPid == 0 || f.Created100Ns == 0 ||
            f.RequestCanId == f.ResponseCanId)
            return false;
        uint max = f.Extended ? 0x1FFFFFFFu : 0x7FFu;
        if (f.RequestCanId > max || f.ResponseCanId > max)
            return false;
        if (f.Kind == ReadRequest)
            return f.Payload.Length == 3 && f.Payload[0] == 0x22 &&
                SyntheticReadFixture.AllowedDid(BinaryPrimitives.ReadUInt16BigEndian(
                    f.Payload.AsSpan(1)));
        if (f.Kind == ReadResponse)
            return f.Payload.Length is >= 4 and <= MaximumPayload &&
                f.Payload[0] == 0x62 &&
                SyntheticReadFixture.AllowedDid(BinaryPrimitives.ReadUInt16BigEndian(
                    f.Payload.AsSpan(1)));
        return false;
    }
}

public sealed record VcrdEnvelope(
    ushort Kind, ulong OperationId, ulong SessionId, ulong Generation,
    uint ServerPid, ulong Created100Ns,
    uint RequestCanId, uint ResponseCanId, bool Extended, byte[] Payload);
