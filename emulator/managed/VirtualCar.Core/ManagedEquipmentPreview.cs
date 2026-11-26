using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace VirtualCar.Core;

public sealed record EquipmentOption(string Code, string Text);
public sealed record EquipmentChoices(int Offset, string BaselineCode, IReadOnlyList<EquipmentOption> Choices);
public sealed record EquipmentPreview(IReadOnlyList<string> Errors, IReadOnlyList<string> Warnings,
    bool TopologyReview, int ChangedCount)
{
    public string Status => Errors.Count > 0 ? "blocked" : Warnings.Count > 0 || TopologyReview ? "review" : "pass";
}

// Managed preview of VC059.2/.3/.4 lab rules, not OEM dependency validation.
// No export, activation, or vehicle I/O in this stage.
public sealed class ManagedEquipmentPreview
{
    private static readonly HashSet<int> Locked = [2,3,4,8,9,10,12,16,28,33,36,123];
    private static readonly HashSet<int> Equipment = [13,15,20,21,23,25,43,45,46,55,64,67,73,76,79,81,85,90,91,105,106,107,110,113,118,120,122,124,125,127,128,129];
    private static readonly string[] Bad = ["", "Undefined value", "Parameter error", "Faulty value"];
    private readonly byte[] _baseline;
    private readonly IReadOnlyDictionary<int, EquipmentChoices> _options;
    public IReadOnlyDictionary<int, EquipmentChoices> Options => _options;

    public static byte[] ExtractBlock(byte[] ini)
    {
        var matches = Regex.Matches(Encoding.Latin1.GetString(ini),
            @"(?m)^\[VC054_F106Lab\]\r?\nBlockHex=([0-9a-f]{284})\r?\nLayout=donor-142\r?\nEnabled=1\r?$");
        if (matches.Count != 1) throw new InvalidDataException();
        return Convert.FromHexString(matches[0].Groups[1].Value);
    }

    private static void Keys(JsonElement node, params string[] keys)
    {
        var actual = node.EnumerateObject().Select(x => x.Name).ToArray();
        if (actual.Length != keys.Length || !actual.ToHashSet(StringComparer.Ordinal).SetEquals(keys))
            throw new InvalidDataException();
    }
    private static bool Code(string? value) => value is { Length: 2 } &&
        value.All(c => c is >= '0' and <= '9' or >= 'A' and <= 'F');

    public ManagedEquipmentPreview(byte[] baseline, byte[] options)
    {
        if (baseline.Length != 142 || baseline[0] != 0x8c || baseline[1] != baseline.Skip(2).Sum(b => (int)b) % 256 ||
            options.Length is < 1 or > 4 * 1024 * 1024) throw new InvalidDataException();
        _baseline = baseline.ToArray();
        using var doc = JsonDocument.Parse(options, new JsonDocumentOptions { MaxDepth = 8 });
        var root = doc.RootElement;
        Keys(root, "schema", "rows");
        if (root.GetProperty("schema").GetString() != "vc094d-cem-options-v1") throw new InvalidDataException();
        var rows = new Dictionary<int, EquipmentChoices>();
        foreach (var row in root.GetProperty("rows").EnumerateArray())
        {
            Keys(row, "offset", "baseline_code", "choices");
            int offset = row.GetProperty("offset").GetInt32();
            string code = row.GetProperty("baseline_code").GetString() ?? throw new InvalidDataException();
            if (offset is < 2 or >= 130 || offset == 7 || code != _baseline[offset].ToString("X2", CultureInfo.InvariantCulture))
                throw new InvalidDataException();
            var choices = new List<EquipmentOption>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var item in row.GetProperty("choices").EnumerateArray())
            {
                Keys(item, "code", "text");
                string? choice = item.GetProperty("code").GetString();
                string? text = item.GetProperty("text").GetString();
                if (!Code(choice) || choice == "FF" || choice == code || Locked.Contains(offset) ||
                    text is null || text.Length > 1024 || Bad.Contains(text) || !seen.Add(choice!))
                    throw new InvalidDataException();
                choices.Add(new(choice!, text));
            }
            if (!rows.TryAdd(offset, new(offset, code, choices.AsReadOnly()))) throw new InvalidDataException();
        }
        if (rows.Count != 127) throw new InvalidDataException();
        _options = new System.Collections.ObjectModel.ReadOnlyDictionary<int, EquipmentChoices>(rows);
    }

    public EquipmentPreview Preview(IReadOnlyDictionary<int, string> edits)
    {
        byte[] b = _baseline.ToArray();
        foreach (var (offset, code) in edits)
        {
            if (!_options.TryGetValue(offset, out var row) || Locked.Contains(offset) ||
                !row.Choices.Any(c => c.Code == code)) throw new InvalidDataException();
            b[offset] = byte.Parse(code, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        }
        b[1] = (byte)(b.Skip(2).Sum(x => (int)x) % 256);
        var errors = new List<string>();
        var warnings = new List<string>();
        void E(string id, bool condition) { if (condition) errors.Add(id); }
        void W(string id, bool condition) { if (condition) warnings.Add(id); }
        E("PETROL_HEATER", b[33] == 1 && b[23] is 3 or 4 or 5);
        E("AUTO_STARTBLOCK", b[8] == 2 && b[71] == 2);
        E("AC_HEATER_ONLY", b[20] == 2 && b[21] == 1);
        E("AC_REAR", b[20] == 1 && b[105] == 2);
        E("AC_CLIMATE", b[20] == 1 && b[21] is 2 or 5 or 6 or 7 or 9);
        W("AQS_FILTER", (b[21] == 6) != (b[75] == 4));
        E("PARK_AEM", b[64] is 2 or 5 && b[76] == 1);
        E("AIRBAG_SWITCH", b[73] == 1 && b[113] == 2);
        E("OWS_CAL", b[91] is 1 or 5 && b[116] != 1);
        E("TPMS_LOAD", (b[79] == 1) != (b[112] == 0x22));
        E("XENON_ADJUST", b[81] is 0x11 or 0x12 && b[55] != 3);
        W("ALARM_OPTIONS", b[46] is 1 or 4 &&
            (b[47] != 1 || b[48] == 1 || b[49] == 2 || b[50] == 2 || b[51] != 1 || b[77] == 2 || b[83] == 2));
        W("HEATER_CALL", b[23] == 1 && b[25] == 1 && b[84] != 1);
        W("RTI_CONTROL", b[85] is not (1 or 2 or 3 or 8) && b[43] == 1);
        W("AUDIO_AMP", b[45] == 1 && b[67] != 1);
        W("AUDIO_SYSTEM", b[45] == 0x59 && b[107] == 1);
        return new(errors.AsReadOnly(), warnings.AsReadOnly(), edits.Keys.Any(Equipment.Contains), edits.Count);
    }
}
