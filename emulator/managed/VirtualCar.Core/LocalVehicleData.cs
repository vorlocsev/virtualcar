using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace VirtualCar.Core;

public sealed record LocalConfigurationRow(int Offset, string Name, string Value, bool Locked);
public sealed record LocalVehicleProfile(BuiltInVehicle Vehicle, IReadOnlyList<LocalConfigurationRow> Rows)
{
    public ManagedEquipmentPreview? Editor { get; init; }
    public EquipmentReferences? References { get; init; }
    public string NativeSha { get; init; } = "";
    public string ManifestSha { get; init; } = "";
}

public static class LocalVehicleData
{
    public const string Id = "xc90-v8-2009";
    // Same immutable reviewed candidate as VC059.1, not a new OEM claim.
    public const string PinnedProfile = "c6d8b7b36382bce1fdbc7cf1a639175ae1c64137782904420059cec1be537f88";
    private static readonly HashSet<int> Locked = [2,3,4,8,9,10,12,16,28,33,36,123];

    public static string Folder(string root)
    {
        if (!Path.IsPathFullyQualified(root)) throw new InvalidDataException();
        return Path.Combine(root, "vehicle-data", Id);
    }

    private static byte[] Read(string path, int cap) => VehicleStatePackages.ReadFile(path, cap);

    public enum Availability { Missing, Ready, Invalid }

    public static bool SameSnapshot(Availability previous, LocalVehicleProfile? oldProfile,
        Availability current, LocalVehicleProfile? newProfile)
    {
        if (previous != current) return false;
        if (current != Availability.Ready)
            return (current is Availability.Missing or Availability.Invalid) &&
                oldProfile is null && newProfile is null;
        return oldProfile is not null && newProfile is not null &&
            AcceptanceReportReader.IsHash(oldProfile.ManifestSha, 64) &&
            oldProfile.ManifestSha.Equals(newProfile.ManifestSha, StringComparison.OrdinalIgnoreCase);
    }

    public static Availability Probe(string root, out LocalVehicleProfile? profile)
    {
        profile = null;
        try
        {
            string folder = Folder(root);
            try { _ = File.GetAttributes(folder); }
            catch (FileNotFoundException) { return Availability.Missing; }
            catch (DirectoryNotFoundException) { return Availability.Missing; }
            profile = Load(root);
            return Availability.Ready;
        }
        catch (Exception ex) when (ex is InvalidDataException or IOException or UnauthorizedAccessException or
            System.Security.SecurityException or JsonException or InvalidOperationException or
            ArgumentException or FormatException or OverflowException or KeyNotFoundException)
        {
            return Availability.Invalid;
        }
    }

    // Identity is read only from the Vehicle section, not an unrelated ECU
    // or diagnostic fixture. The actual owner profile must still match its pin.
    public static string ReadVehicleVin(byte[] bytes)
    {
        if (bytes.Length is < 1 or > 1024 * 1024 || bytes.Any(b => b == 0 || b > 127))
            throw new InvalidDataException();
        bool vehicle = false, seen = false;
        string? vin = null, year = null;
        foreach (string raw in Encoding.ASCII.GetString(bytes).Split('\n'))
        {
            string line = raw.Trim();
            if (line.Length == 0 || line.StartsWith(';') || line.StartsWith('#')) continue;
            if (line.StartsWith('['))
            {
                if (!line.EndsWith(']') || line.IndexOf(']') != line.Length - 1) throw new InvalidDataException();
                vehicle = line[1..^1].Trim().Equals("Vehicle", StringComparison.OrdinalIgnoreCase);
                if (vehicle && seen) throw new InvalidDataException();
                if (vehicle) seen = true;
                continue;
            }
            if (!vehicle) continue;
            int eq = line.IndexOf('=');
            if (eq < 1) continue;
            string key = line[..eq].Trim(), value = line[(eq+1)..].Trim();
            if (key.Equals("VIN", StringComparison.OrdinalIgnoreCase))
            {
                if (vin is not null) throw new InvalidDataException();
                vin = value;
            }
            if (key.Equals("ModelYear", StringComparison.OrdinalIgnoreCase))
            {
                if (year is not null) throw new InvalidDataException();
                year = value;
            }
        }
        if (vin is null || !Regex.IsMatch(vin, @"\A[A-HJ-NPR-Z0-9]{17}\z") || vin[9] != '9' || year != "2009")
            throw new InvalidDataException();
        return vin;
    }

    public static byte[] ReadProfile(string root)
    {
        byte[] bytes = Read(Path.Combine(Folder(root), "virtualcar.ini"), 1024 * 1024);
        if (!NativeEcmScenarioApply.Digest(bytes).Equals(PinnedProfile, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        return bytes;
    }

    private static string Hash(JsonElement node, string key)
    {
        string? value = node.GetProperty(key).GetString();
        if (!AcceptanceReportReader.IsHash(value, 64)) throw new InvalidDataException();
        return value!.ToLowerInvariant();
    }
    private static void Keys(JsonElement node, params string[] expected)
    {
        var actual = node.EnumerateObject().Select(p => p.Name).ToArray();
        if (actual.Length != expected.Length || !actual.ToHashSet(StringComparer.Ordinal).SetEquals(expected))
            throw new InvalidDataException();
    }

    // The built-in package is an independent consistency anchor, not a signature.
    public static void ValidateNativeBinding(string root, string expected)
    {
        if (!AcceptanceReportReader.IsHash(expected, 64)) throw new InvalidDataException();
        string reference = BuiltInVehicles.PackageLibrary(root, "p2");
        string dir = Path.GetDirectoryName(reference)!;
        if (!BuiltInVehicles.MatchesProfile("p2", Read(Path.Combine(dir, "virtualcar.ini"), 1024 * 1024)))
            throw new InvalidDataException();
        string declared = Encoding.ASCII.GetString(Read(Path.Combine(dir, "candidate.sha256"), 128)).Trim();
        if (!declared.Equals(expected, StringComparison.OrdinalIgnoreCase) ||
            !NativeEcmScenarioApply.Digest(Read(reference, 64 * 1024 * 1024)).Equals(expected, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
    }

    public static void ValidateInventory(string dir, string schema)
    {
        var expected = new HashSet<string>(StringComparer.Ordinal)
        {
            "local-profile.json", "virtualcar.ini", "VirtualCarJ2534.dll",
            "candidate.sha256", "configuration.json"
        };
        switch (schema)
        {
            case "vc094d2-local-profile-v3":
                expected.Add("configuration-references.json");
                goto case "vc094d-local-profile-v2";
            case "vc094d-local-profile-v2":
                expected.Add("configuration-options.json");
                break;
            case "vc094b-local-profile-v1":
                break;
            default:
                throw new InvalidDataException();
        }
        if (!Path.IsPathFullyQualified(dir)) throw new InvalidDataException();
        for (DirectoryInfo? parent = new(dir); parent is not null; parent = parent.Parent)
            if ((parent.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException();
        foreach (var item in new DirectoryInfo(dir).EnumerateFileSystemInfos())
            if ((item.Attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0 ||
                !expected.Remove(item.Name)) throw new InvalidDataException();
        if (expected.Count != 0) throw new InvalidDataException();
    }

    public static LocalVehicleProfile Load(string root)
    {
        string dir = Folder(root);
        string marker = Path.Combine(dir, "local-profile.json");
        byte[] manifestBytes = Read(marker, 4096);
        using var manifest = JsonDocument.Parse(manifestBytes);
        var m = manifest.RootElement;
        string? schema = m.GetProperty("schema").GetString();
        bool referencesIncluded = schema == "vc094d2-local-profile-v3";
        bool editable = referencesIncluded || schema == "vc094d-local-profile-v2";
        if (referencesIncluded) Keys(m, "schema", "profile_sha256", "native_sha256", "catalog_sha256", "options_sha256", "references_sha256");
        else if (editable) Keys(m, "schema", "profile_sha256", "native_sha256", "catalog_sha256", "options_sha256");
        else Keys(m, "schema", "profile_sha256", "native_sha256", "catalog_sha256");
        if ((!editable && schema != "vc094b-local-profile-v1") || Hash(m, "profile_sha256") != PinnedProfile)
            throw new InvalidDataException();
        ValidateInventory(dir, schema!);
        string native = Hash(m, "native_sha256");
        ValidateNativeBinding(root, native);
        if (!Encoding.ASCII.GetString(Read(Path.Combine(dir, "candidate.sha256"), 128)).Trim().Equals(native, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        byte[] profile = ReadProfile(root);
        if (NativeEcuInventory.Inspect(profile).Count != 8) throw new InvalidDataException();
        string vin = ReadVehicleVin(profile);
        byte[] library = Read(Path.Combine(dir, "VirtualCarJ2534.dll"), 64 * 1024 * 1024);
        if (!NativeEcmScenarioApply.Digest(library).Equals(native, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        byte[] catalog = Read(Path.Combine(dir, "configuration.json"), 1024 * 1024);
        if (!NativeEcmScenarioApply.Digest(catalog).Equals(Hash(m, "catalog_sha256"), StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        var rows = ParseCatalog(catalog);
        ManagedEquipmentPreview? editor = null;
        if (editable)
        {
            byte[] options = Read(Path.Combine(dir, "configuration-options.json"), 4 * 1024 * 1024);
            if (!NativeEcmScenarioApply.Digest(options).Equals(Hash(m, "options_sha256"), StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException();
            editor = new ManagedEquipmentPreview(ManagedEquipmentPreview.ExtractBlock(profile), options);
            if (editor.Preview(new Dictionary<int, string>()).Status != "pass") throw new InvalidDataException();
        }
        EquipmentReferences? references = null;
        if (referencesIncluded)
        {
            byte[] rawReferences = Read(Path.Combine(dir, "configuration-references.json"), 65536);
            if (!NativeEcmScenarioApply.Digest(rawReferences).Equals(Hash(m, "references_sha256"), StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException();
            references = new EquipmentReferences(rawReferences);
            references.VerifyAll(editor!, profile);
        }
        ValidateInventory(dir, schema!);
        if (!Read(marker, 4096).AsSpan().SequenceEqual(manifestBytes)) throw new InvalidDataException();
        return new(new BuiltInVehicle(Id, "Volvo XC90 V8 · 2009", "Volvo XC90 V8 · 2009",
            "Owner-local reviewed simulator profile. Original VIDA acceptance remains separate.",
            "Проверенный локальный профиль эмулятора. Фактическая приёмка VIDA проверяется отдельно.",
            vin, false), rows) { Editor = editor, References = references, NativeSha = native,
                ManifestSha = NativeEcmScenarioApply.Digest(manifestBytes) };
    }

    public static IReadOnlyList<LocalConfigurationRow> ParseCatalog(byte[] bytes)
    {
        if (bytes.Length is < 1 or > 1024 * 1024) throw new InvalidDataException();
        using var doc = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 8 });
        var root = doc.RootElement;
        Keys(root, "schema", "rows");
        if (root.GetProperty("schema").GetString() != "vc094b-cem-baseline-v1") throw new InvalidDataException();
        var rows = new List<LocalConfigurationRow>();
        var seen = new HashSet<int>();
        foreach (var item in root.GetProperty("rows").EnumerateArray())
        {
            Keys(item, "offset", "name", "value", "locked");
            int offset = item.GetProperty("offset").GetInt32();
            string name = item.GetProperty("name").GetString() ?? throw new InvalidDataException();
            string value = item.GetProperty("value").GetString() ?? throw new InvalidDataException();
            bool locked = item.GetProperty("locked").GetBoolean();
            if (offset < 0 || offset >= 130 || offset is 0 or 1 or 7 || !seen.Add(offset) ||
                locked != Locked.Contains(offset) || name.Length is < 1 or > 512 || value.Length > 1024)
                throw new InvalidDataException();
            rows.Add(new(offset, name, value, locked));
        }
        if (rows.Count != 127) throw new InvalidDataException();
        return rows.OrderBy(r => r.Offset).ToList().AsReadOnly();
    }
}
