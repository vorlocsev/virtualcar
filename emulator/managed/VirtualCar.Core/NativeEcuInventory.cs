using System.Globalization;
using System.Text;

namespace VirtualCar.Core;

public enum EcuRouteState { Configured, DefaultsUsed, Invalid, DuplicateRequest, FunctionalRequest }

public sealed record NativeEcuSlot(int Index, uint? RequestId, uint? ResponseId, uint? ExpectedBaud,
    string? PartNumber, string? Software, EcuRouteState State);

/// <summary>Bounded static inventory of native ECU0..ECU31 settings. Not discovery.</summary>
public static class NativeEcuInventory
{
    private static readonly string[] Fields = ["RequestId", "ResponseId", "ExpectedBaud", "PartNumber", "Software"];

    public static IReadOnlyList<NativeEcuSlot> Inspect(ReadOnlySpan<byte> bytes)
    {
        if (bytes.Length is < 1 or > 1024 * 1024 || bytes.Contains((byte)0) ||
            bytes.StartsWith(new byte[] { 0xEF, 0xBB, 0xBF }))
            throw new InvalidDataException("Unsupported profile encoding or size.");
        var sections = new Dictionary<string, Dictionary<string, string>>(StringComparer.OrdinalIgnoreCase);
        Dictionary<string, string>? current = null;
        string section = "";
        foreach (string raw in Encoding.Latin1.GetString(bytes).Split('\n'))
        {
            string line = raw.Trim();
            if (line.Length == 0 || line.StartsWith(';') || line.StartsWith('#')) continue;
            if (line.StartsWith('['))
            {
                if (!line.EndsWith(']') || line.Length < 3 || line.IndexOf(']') != line.Length - 1)
                    throw new InvalidDataException("Ambiguous section.");
                section = line[1..^1].Trim();
                current = null;
                bool relevant = section.Equals("Vehicle", StringComparison.OrdinalIgnoreCase) ||
                    Enumerable.Range(0, 32).Any(i => section.Equals("ECU" + i, StringComparison.OrdinalIgnoreCase));
                if (!relevant) continue;
                current = new(StringComparer.OrdinalIgnoreCase);
                if (!sections.TryAdd(section, current)) throw new InvalidDataException("Duplicate ECU section.");
                continue;
            }
            if (current is null) continue;
            int eq = line.IndexOf('=');
            if (eq < 1) continue;
            string key = line[..eq].Trim();
            bool wanted = section.Equals("Vehicle", StringComparison.OrdinalIgnoreCase)
                ? key.Equals("ECUCount", StringComparison.OrdinalIgnoreCase)
                : Fields.Contains(key, StringComparer.OrdinalIgnoreCase);
            if (!wanted) continue;
            if (!current.TryAdd(key, line[(eq + 1)..].Trim()))
                throw new InvalidDataException("Duplicate ECU setting.");
        }

        string? Get(string name, string key) =>
            sections.TryGetValue(name, out var values) && values.TryGetValue(key, out var value) ? value : null;
        string? countText = Get("Vehicle", "ECUCount");
        if (countText is not null && (!Number(countText, false, out uint countValue) || countValue is < 1 or > 32))
            throw new InvalidDataException("Unsupported ECUCount; native fallback is not inferred.");
        int count = countText is null ? 2 : (int)Parse(countText, false)!.Value;
        var slots = new List<NativeEcuSlot>(count);
        for (int i = 0; i < count; i++)
        {
            string name = "ECU" + i;
            string? request = Get(name, "RequestId"), response = Get(name, "ResponseId"),
                baud = Get(name, "ExpectedBaud"), part = Get(name, "PartNumber"), software = Get(name, "Software");
            uint? req = request is null && i < 8 ? (i == 1 ? 0x726u : 0x7E0u) : Parse(request, true);
            uint? resp = response is null && i < 8 ? (i == 1 ? 0x72Eu : 0x7E8u) : Parse(response, true);
            uint? rate = baud is null ? 0u : Parse(baud, false);
            bool invalid = req is null || resp is null || rate is null || req > 0x1FFFFFFFu ||
                resp > 0x1FFFFFFFu || rate == uint.MaxValue || req == resp ||
                (req <= 0x7FFu) != (resp <= 0x7FFu);
            var state = invalid ? EcuRouteState.Invalid : req == 0x7DFu ? EcuRouteState.FunctionalRequest :
                request is null || response is null || baud is null || part is null || software is null
                    ? EcuRouteState.DefaultsUsed : EcuRouteState.Configured;
            slots.Add(new(i, req, resp, rate, Display(part), Display(software), state));
        }
        // Any duplicate request identifier is flagged conservatively, even across bitrates.
        var duplicates = slots.Where(x => x.RequestId.HasValue && x.State is EcuRouteState.Configured or EcuRouteState.DefaultsUsed)
            .GroupBy(x => x.RequestId).Where(g => g.Count() > 1).Select(g => g.Key).ToHashSet();
        return slots.Select(s => duplicates.Contains(s.RequestId) &&
            s.State is EcuRouteState.Configured or EcuRouteState.DefaultsUsed
                ? s with { State = EcuRouteState.DuplicateRequest } : s).ToArray();
    }

    // Preserve local ASCII identity text only when it fits the native 48-byte buffer.
    // Null means missing or not faithfully representable, not an identified ECU.
    private static string? Display(string? value) =>
        value is not null && value.Length is > 0 and <= 47 &&
        value.All(c => c is >= ' ' and <= '~' && c != '"') ? value : null;

    private static uint? Parse(string? value, bool hex) =>
        value is not null && Number(value, hex, out uint number) ? number : null;

    private static bool Number(string value, bool hex, out uint number)
    {
        if (value.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            value = value[2..];
            hex = true;
        }
        return uint.TryParse(value, hex ? NumberStyles.AllowHexSpecifier : NumberStyles.None,
            CultureInfo.InvariantCulture, out number);
    }
}
