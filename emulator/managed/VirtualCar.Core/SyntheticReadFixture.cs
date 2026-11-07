using System.Buffers.Binary;

namespace VirtualCar.Core;

/// <summary>
/// Parses small sealed synthetic VCRF fixtures. This is NOT a general
/// ECU database or a diagnostic protocol. Its caller must have validated
/// the active coordinator session and the immutable ScenarioSnapshot.
/// </summary>
public static class SyntheticReadFixture
{
    private const int HeaderSize = 15;
    private const int MaximumFixtureSize = 256;
    private const int MaximumEntries = 3;

    public static byte[]? Find(
        ScenarioSnapshot snapshot, uint requestCanId, uint responseCanId,
        bool extended, ushort did)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ReadOnlySpan<byte> bytes = snapshot.CanonicalBytes;
        if (bytes.Length < HeaderSize + 4 || bytes.Length > MaximumFixtureSize ||
            !bytes[..4].SequenceEqual("VCRF"u8) ||
            bytes[4] != 1 || bytes[5] > 1 ||
            !ValidRoute(requestCanId, responseCanId, extended) ||
            bytes[5] != (extended ? 1 : 0) ||
            BinaryPrimitives.ReadUInt32LittleEndian(bytes[6..10]) != requestCanId ||
            BinaryPrimitives.ReadUInt32LittleEndian(bytes[10..14]) != responseCanId ||
            bytes[14] is < 1 or > MaximumEntries)
            return null;

        int count = bytes[14];
        int offset = HeaderSize;
        ushort previous = 0;
        byte[]? found = null;
        for (int i = 0; i < count; ++i)
        {
            if (bytes.Length - offset < 3) return null;
            ushort entryDid = BinaryPrimitives.ReadUInt16BigEndian(bytes.Slice(offset, 2));
            int length = bytes[offset + 2];
            offset += 3;

            // Ordered unique allowlisted DID records are mandatory. Validate
            // the ENTIRE fixture before returning a match, including suffixes.
            if (!AllowedDid(entryDid) || entryDid <= previous ||
                length is < 1 or > 61 || bytes.Length - offset < length)
                return null;
            if (entryDid == did)
                found = bytes.Slice(offset, length).ToArray();
            offset += length;
            previous = entryDid;
        }
        return offset == bytes.Length ? found : null;
    }

    public static bool AllowedDid(ushort did) =>
        did is 0xF187 or 0xF189 or 0xF190;

    private static bool ValidRoute(uint request, uint response, bool extended)
    {
        uint maxId = extended ? 0x1FFFFFFFu : 0x7FFu;
        return request <= maxId && response <= maxId && request != response;
    }
}
