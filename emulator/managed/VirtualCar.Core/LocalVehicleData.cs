using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace VirtualCar.Core;

public sealed record LocalConfigurationRow(int Offset, string Name, string Value, bool Locked);
public sealed record LocalVehicleProfile(BuiltInVehicle Vehicle, IReadOnlyList<LocalConfigurationRow> Rows)
{
    public ManagedEquipmentPreview? Editor { get; init; }
    public EquipmentReferences? References { get; init; }
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

    private static byte[] Read(string path, int cap)
    {
        for (FileSystemInfo? item = new FileInfo(path); item is not null;
            item = item is FileInfo f ? f.Directory : ((DirectoryInfo)item).Parent)
            if ((item.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException();
        using var file = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (file.Length < 1 || file.Length > cap) throw new InvalidDataException();
        byte[] bytes = new byte[(int)file.Length];
        file.ReadExactly(bytes);
        if (file.ReadByte() != -1) throw new InvalidDataException();
        return bytes;
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

    public static LocalVehicleProfile Load(string root)
    {
        string dir = Folder(root);
        using var manifest = JsonDocument.Parse(Read(Path.Combine(dir, "local-profile.json"), 4096));
        var m = manifest.RootElement;
        string? schema = m.GetProperty("schema").GetString();
        bool referencesIncluded = schema == "vc094d2-local-profile-v3";
        bool editable = referencesIncluded || schema == "vc094d-local-profile-v2";
        if (referencesIncluded) Keys(m, "schema", "profile_sha256", "native_sha256", "catalog_sha256", "options_sha256", "references_sha256");
        else if (editable) Keys(m, "schema", "profile_sha256", "native_sha256", "catalog_sha256", "options_sha256");
        else Keys(m, "schema", "profile_sha256", "native_sha256", "catalog_sha256");
        if ((!editable && schema != "vc094b-local-profile-v1") || Hash(m, "profile_sha256") != PinnedProfile)
            throw new InvalidDataException();
        string native = Hash(m, "native_sha256");
        if (!Encoding.ASCII.GetString(Read(Path.Combine(dir, "candidate.sha256"), 128)).Trim().Equals(native, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        byte[] profile = ReadProfile(root);
        if (NativeEcuInventory.Inspect(profile).Count != 8) throw new InvalidDataException();
        string text = Encoding.ASCII.GetString(profile);
        var vins = Regex.Matches(text, @"(?m)^VIN\s*=\s*([A-HJ-NPR-Z0-9]{17})[ \t]*\r?$");
        if (vins.Count != 1 || vins[0].Groups[1].Value[9] != '9') throw new InvalidDataException();
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
        return new(new BuiltInVehicle(Id, "Volvo XC90 V8 · 2009", "Volvo XC90 V8 · 2009",
            "Owner-local reviewed simulator profile. Original VIDA acceptance remains separate.",
            "Проверенный локальный профиль эмулятора. Фактическая приёмка VIDA проверяется отдельно.",
            vins[0].Groups[1].Value, false), rows) { Editor = editor, References = references };
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
