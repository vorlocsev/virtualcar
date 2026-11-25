using System.Text;

namespace VirtualCar.Core;

public enum NativeIgnitionSelection { Baseline, PositionIICandidate }

public sealed record NativeIgnitionState(bool GgdEnabled, NativeIgnitionSelection Configured)
{
    public bool CanApply => GgdEnabled;
    public string ExpectedRaw => Configured == NativeIgnitionSelection.PositionIICandidate ? "07" : "04";
}

/// <summary>Existing B3A157 A45F laboratory candidate only; not physical ignition control.</summary>
public static class NativeIgnitionPlan
{
    private const string Section = "B3A157_IgnitionLab";

    public static NativeIgnitionState Inspect(ReadOnlySpan<byte> bytes)
    {
        bool ggd = NativeEcmScenarioPlan.GgdEnabled(bytes);
        bool seen = false, active = false;
        string? enabled = null, rawByte = null;
        foreach (string raw in Encoding.Latin1.GetString(bytes).Split('\n'))
        {
            string line = raw.Trim();
            if (line.Length == 0 || line.StartsWith(';') || line.StartsWith('#')) continue;
            if (line.StartsWith('['))
            {
                active = string.Equals(line, "[" + Section + "]", StringComparison.OrdinalIgnoreCase);
                if (!active && line.EndsWith(']') &&
                    string.Equals(line[1..^1].Trim(), Section, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Noncanonical ignition section.");
                if (active)
                {
                    if (seen) throw new InvalidDataException("Duplicate ignition section.");
                    seen = true;
                }
                continue;
            }
            if (!active) continue;
            int eq = line.IndexOf('=');
            if (eq < 1) continue;
            string key = line[..eq].Trim(), value = line[(eq + 1)..].Trim();
            if (key.Equals("Enabled", StringComparison.OrdinalIgnoreCase))
            {
                if (enabled is not null || value is not ("0" or "1"))
                    throw new InvalidDataException("Ambiguous ignition enable flag.");
                enabled = value;
            }
            else if (key.Equals("A45FRawByte", StringComparison.OrdinalIgnoreCase))
            {
                if (rawByte is not null || value != "07")
                    throw new InvalidDataException("Unsupported ignition candidate byte.");
                rawByte = value;
            }
        }
        if (enabled == "1" && rawByte != "07")
            throw new InvalidDataException("Enabled candidate requires literal 07.");
        return new(ggd, enabled == "1" ? NativeIgnitionSelection.PositionIICandidate : NativeIgnitionSelection.Baseline);
    }

    public static byte[] Build(ReadOnlySpan<byte> original, NativeIgnitionSelection selection)
    {
        if (!Enum.IsDefined(selection)) throw new ArgumentOutOfRangeException(nameof(selection));
        if (!Inspect(original).CanApply) throw new InvalidOperationException("GGD CEM lab flag required.");
        string text = Encoding.Latin1.GetString(original);
        if (text.Replace("\r\n", "\n").Contains('\r'))
            throw new InvalidDataException("Unsupported line endings.");
        string newline = text.Contains("\r\n") ? "\r\n" : "\n";
        var lines = text.Split('\n').ToList();
        NativeEcmScenarioApply.UpdateSection(lines, Section,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Enabled"] = selection == NativeIgnitionSelection.PositionIICandidate ? "1" : "0",
                ["A45FRawByte"] = "07"
            }, newline);
        byte[] result = Encoding.Latin1.GetBytes(string.Join("\n", lines));
        var verified = Inspect(result);
        if (!verified.CanApply || verified.Configured != selection)
            throw new InvalidDataException("Ignition candidate verification failed.");
        return result;
    }

    public static NativeScenarioApplyResult Apply(string path, string expectedSha256, NativeIgnitionSelection selection) =>
        NativeEcmScenarioApply.Replace(path, expectedSha256, before => Build(before, selection), "vc082");
}
