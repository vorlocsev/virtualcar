using System.Text;

namespace VirtualCar.Core;

public enum EcmScenario { Stationary = 0, Cranking = 1, ColdIdle = 2, Warming = 3, WarmIdle = 4, Dynamic = 5 }

public sealed record EcmScenarioPlan(EcmScenario Selection, bool BaselineEnabled, bool DynamicReady, string IniPatch)
{
    public bool CanApply => BaselineEnabled && (Selection != EcmScenario.Dynamic || DynamicReady);
}

/// <summary>Read-only inspection and INI patch preview for legacy native ECM gates.
/// No native DLL loading, registry changes, profile writes or simulated live state.</summary>
public static class NativeEcmScenarioPlan
{
    private const int MaximumBytes = 1024 * 1024;
    private const string Scenario = "B3A316_EcmScenarioLab";
    private const string Dynamic = "B3A329_DynamicEcmLab";
    private static readonly string[] DynamicGates =
    [
        "B3A309_EcmLiveDataLab", "B3A314_EcmExtendedLiveLab", "B3A267_CurrentDataLab",
        "B3A319_BatterySyncLab", "B3A320_RemVoltageSyncLab", "B3A324_SupplyVoltageSyncLab"
    ];

    // Fail closed on ambiguous relevant entries; preserve the native exact "1" semantics
    // for simple, unquoted INI values. Reject non-ASCII relevant values and duplicate sections.
    private static Dictionary<string, string> Read(ReadOnlySpan<byte> bytes)
    {
        if (bytes.Length is < 1 or > MaximumBytes || bytes.Contains((byte)0) ||
            bytes.StartsWith(new byte[] { 0xEF, 0xBB, 0xBF }))
            throw new InvalidDataException("Unsupported profile encoding or size.");
        var sections = new HashSet<string>(DynamicGates, StringComparer.OrdinalIgnoreCase)
            { Scenario, Dynamic, "Diagnostics" };
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        string section = "";
        foreach (string raw in Encoding.Latin1.GetString(bytes).Split('\n'))
        {
            string line = raw.Trim();
            if (line.Length == 0 || line.StartsWith(';') || line.StartsWith('#')) continue;
            if (line.StartsWith('['))
            {
                int end = line.IndexOf(']');
                if (end < 2 || line[(end + 1)..].Trim().Length != 0)
                    throw new InvalidDataException("Ambiguous section.");
                section = line[1..end].Trim();
                if (sections.Contains(section) && !seen.Add(section))
                    throw new InvalidDataException("Duplicate scenario section.");
                continue;
            }
            if (!sections.Contains(section)) continue;
            int equals = line.IndexOf('=');
            if (equals < 1) continue;
            string key = line[..equals].Trim();
            bool relevant = section.Equals("Diagnostics", StringComparison.OrdinalIgnoreCase)
                ? key.Equals("EnableGGDCemLab", StringComparison.OrdinalIgnoreCase)
                : key.Equals("Enabled", StringComparison.OrdinalIgnoreCase) ||
                    (section.Equals(Scenario, StringComparison.OrdinalIgnoreCase) &&
                     key.Equals("State", StringComparison.OrdinalIgnoreCase));
            if (!relevant) continue;
            string value = line[(equals + 1)..].Trim();
            if (value.Length != 1 || value[0] is < '0' or > '4' ||
                (!key.Equals("State", StringComparison.OrdinalIgnoreCase) && value is not ("0" or "1")) ||
                !values.TryAdd(section + "/" + key, value))
                throw new InvalidDataException("Ambiguous scenario value.");
        }
        return values;
    }

    internal static bool GgdEnabled(ReadOnlySpan<byte> bytes) =>
        Read(bytes).TryGetValue("Diagnostics/EnableGGDCemLab", out string? value) && value == "1";

    public static EcmScenarioPlan Inspect(ReadOnlySpan<byte> bytes, EcmScenario? selection = null)
    {
        var values = Read(bytes);
        bool On(string section, string key = "Enabled") =>
            values.TryGetValue(section + "/" + key, out string? value) && value == "1";
        bool baseline = On(DynamicGates[0]);
        bool ready = DynamicGates.All(s => On(s)) && On("Diagnostics", "EnableGGDCemLab");
        EcmScenario current = On(Dynamic) && ready ? EcmScenario.Dynamic :
            On(Scenario) && values.TryGetValue(Scenario + "/State", out string? state)
                ? (EcmScenario)(state[0] - '0') : EcmScenario.Stationary;
        EcmScenario chosen = selection ?? current;
        if (!Enum.IsDefined(chosen)) throw new ArgumentOutOfRangeException(nameof(selection));
        // These are the only settings this feature proposes. No prerequisite is auto-enabled.
        bool dynamic = chosen == EcmScenario.Dynamic;
        string patch = $"[{Scenario}]\r\nEnabled=1\r\nState={(dynamic ? 0 : (int)chosen)}\r\n\r\n" +
            $"[{Dynamic}]\r\nEnabled={(dynamic ? 1 : 0)}\r\n";
        return new(chosen, baseline, ready, patch);
    }
}
