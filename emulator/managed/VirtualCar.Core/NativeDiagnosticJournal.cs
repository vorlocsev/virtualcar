namespace VirtualCar.Core;

public enum DiagnosticKind { Request, Positive, Negative, Indication, Unclassified }

public sealed record DiagnosticEntry(NativeTraceRow Trace, DiagnosticKind Kind, byte? Service,
    ushort? Did, byte? Nrc);

public sealed record DiagnosticSummary(int Requests, int Positive, int Negative,
    int Indications, int Unclassified);

/// <summary>Independent diagnostic message classification, never request/response correlation.</summary>
public static class NativeDiagnosticJournal
{
    private static bool Supported(byte sid) => sid is 0x09 or 0x10 or 0x11 or 0x14 or 0x19
        or 0x22 or 0x27 or 0x2E or 0x31 or 0x34 or 0x36 or 0x37 or 0x3E;

    public static DiagnosticEntry Classify(NativeTraceRow row)
    {
        var unknown = new DiagnosticEntry(row, DiagnosticKind.Unclassified, null, null, null);
        if (row.Protocol != 6 || row.Channel is null || row.Flags is not uint flags ||
            row.CanId is not uint id || id > 0x1FFFFFFFu ||
            ((flags & 0x100u) == 0 && id > 0x7FFu)) return unknown;
        bool tx = row.Direction == NativeTraceDirection.Tx;
        if (!tx && (flags & 2u) != 0)
            return row.DataHex.Length == 0 && (flags & ~0x102u) == 0
                ? unknown with { Kind = DiagnosticKind.Indication } : unknown;
        if ((flags & ~(tx ? 0x140u : 0x100u)) != 0 || row.PossibleTruncation) return unknown;
        string[] tokens = row.DataHex.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (tokens.Length is < 1 or > 48) return unknown;
        byte[] data = new byte[tokens.Length];
        for (int i = 0; i < tokens.Length; i++)
            if (tokens[i].Length != 2 || !byte.TryParse(tokens[i],
                System.Globalization.NumberStyles.AllowHexSpecifier,
                System.Globalization.CultureInfo.InvariantCulture, out data[i])) return unknown;

        byte sid = data[0];
        if (tx)
        {
            if (!Supported(sid)) return unknown;
            // Only a single DID request is decoded; multi-DID and malformed requests stay raw.
            if (sid == 0x22)
                return data.Length == 3 ? new(row, DiagnosticKind.Request, sid, Did(data), null) : unknown;
            if (sid == 0x09 && (data.Length != 2 || data[1] != 0x02)) return unknown;
            if (sid is 0x10 or 0x3E && data.Length != 2) return unknown;
            return new(row, DiagnosticKind.Request, sid, null, null);
        }
        if (sid == 0x7F)
            return data.Length == 3 && Supported(data[1])
                ? new(row, DiagnosticKind.Negative, data[1], null, data[2]) : unknown;
        if (sid == 0x62)
            return data.Length >= 4 ? new(row, DiagnosticKind.Positive, 0x22, Did(data), null) : unknown;
        if (sid == 0x49)
            return data.Length == 20 && data[1] == 2 && data[2] == 1
                ? new(row, DiagnosticKind.Positive, 0x09, null, null) : unknown;
        if (sid == 0x50 && data.Length == 6) return new(row, DiagnosticKind.Positive, 0x10, null, null);
        if (sid == 0x59 && data.Length >= 3 && data[1] is 2 or 4 or 6)
            return new(row, DiagnosticKind.Positive, 0x19, null, null);
        if (sid == 0x7E && data.Length == 2) return new(row, DiagnosticKind.Positive, 0x3E, null, null);
        return unknown;
    }

    private static ushort Did(byte[] bytes) => (ushort)((bytes[1] << 8) | bytes[2]);

    public static DiagnosticSummary Summarize(IEnumerable<DiagnosticEntry> entries)
    {
        int requests = 0, positive = 0, negative = 0, indications = 0, unknown = 0;
        foreach (var item in entries)
            switch (item.Kind)
            {
                case DiagnosticKind.Request: requests++; break;
                case DiagnosticKind.Positive: positive++; break;
                case DiagnosticKind.Negative: negative++; break;
                case DiagnosticKind.Indication: indications++; break;
                default: unknown++; break;
            }
        return new(requests, positive, negative, indications, unknown);
    }
}
