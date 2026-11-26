using System.Text.Json;

namespace VirtualCar.Core;

// Reference digests are produced by the original offline compiler during owner-local packaging.
// They are consistency evidence, not publisher signatures or runtime acceptance.
public sealed class EquipmentReferences
{
    private readonly Dictionary<(int, string), string> _cases = new();
    public int Count => _cases.Count;
    public IReadOnlyList<EquipmentVariant> Variants => _cases.OrderBy(p => p.Key.Item1)
        .ThenBy(p => p.Key.Item2, StringComparer.Ordinal)
        .Select(p => new EquipmentVariant(p.Key.Item1, p.Key.Item2, p.Value)).ToArray();

    public byte[] CompileVariant(ManagedEquipmentPreview editor, byte[] baseline, EquipmentVariant variant)
    {
        if (!_cases.TryGetValue((variant.Offset, variant.Code), out string? sha) || sha != variant.ProfileSha)
            throw new InvalidDataException("Unknown equipment variant.");
        return Compile(editor, baseline, new Dictionary<int, string> { [variant.Offset] = variant.Code });
    }
    public EquipmentReferences(byte[] bytes)
    {
        if (bytes.Length is < 1 or > 65536) throw new InvalidDataException();
        using var doc = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 6 });
        var root = doc.RootElement;
        Keys(root, "schema", "cases");
        if (root.GetProperty("schema").GetString() != "vc094d2-single-edit-references-v1")
            throw new InvalidDataException();
        foreach (var item in root.GetProperty("cases").EnumerateArray())
        {
            Keys(item, "offset", "code", "ini_sha256");
            int offset = item.GetProperty("offset").GetInt32();
            string code = item.GetProperty("code").GetString() ?? "";
            string? sha = item.GetProperty("ini_sha256").GetString();
            if (offset is < 2 or >= 130 || offset == 7 || code.Length != 2 ||
                !code.All(c => c is >= '0' and <= '9' or >= 'A' and <= 'F') || code == "FF" ||
                !AcceptanceReportReader.IsHash(sha, 64) || !_cases.TryAdd((offset, code), sha!.ToLowerInvariant()) ||
                _cases.Count > 256) throw new InvalidDataException();
        }
    }
    private static void Keys(JsonElement node, params string[] keys)
    {
        var names = node.EnumerateObject().Select(x => x.Name).ToArray();
        if (names.Length != keys.Length || !names.ToHashSet(StringComparer.Ordinal).SetEquals(keys))
            throw new InvalidDataException();
    }
    public bool Supports(IReadOnlyDictionary<int, string> edits) =>
        edits.Count == 1 && _cases.ContainsKey((edits.First().Key, edits.First().Value));

    public byte[] Compile(ManagedEquipmentPreview editor, byte[] baseline, IReadOnlyDictionary<int, string> edits)
    {
        if (!Supports(edits)) throw new InvalidOperationException("No independent reference for this draft.");
        var edit = edits.Single();
        byte[] result = editor.CompileReviewed(baseline, edits);
        if (!NativeEcmScenarioApply.Digest(result).Equals(_cases[(edit.Key, edit.Value)], StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Managed compiler differs from reference.");
        return result;
    }

    public void VerifyAll(ManagedEquipmentPreview editor, byte[] baseline)
    {
        foreach (var item in _cases.Keys)
            Compile(editor, baseline, new Dictionary<int, string> { [item.Item1] = item.Item2 });
    }

    // Deliberately outside registered provider directories. A prepared copy is
    // not active, not registered and cannot silently replace the baseline.
    public string Prepare(string root, ManagedEquipmentPreview editor, byte[] baseline,
        IReadOnlyDictionary<int, string> edits)
    {
        byte[] result = Compile(editor, baseline, edits);
        string source = Path.Combine(LocalVehicleData.Folder(root), "virtualcar.ini");
        if (!VehicleStatePackages.ReadFile(source, 1024 * 1024).SequenceEqual(baseline))
            throw new InvalidDataException("Baseline changed.");
        string parent = Path.Combine(Path.GetFullPath(root), "vehicle-data");
        for (DirectoryInfo? dir = new(parent); dir is not null; dir = dir.Parent)
            if ((dir.Attributes & FileAttributes.ReparsePoint) != 0 ||
                Directory.Exists(Path.Combine(dir.FullName, ".git")) || File.Exists(Path.Combine(dir.FullName, ".git")))
                throw new InvalidDataException();
        string folder = Path.Combine(parent, "equipment-drafts");
        if (Directory.Exists(folder) && (File.GetAttributes(folder) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException();
        Directory.CreateDirectory(folder);
        string path = Path.Combine(folder, NativeEcmScenarioApply.Digest(result).ToLowerInvariant() + ".ini");
        if (File.Exists(path))
        {
            if (!VehicleStatePackages.ReadFile(path, 1024 * 1024).SequenceEqual(result)) throw new InvalidDataException();
            return path;
        }
        using (var stream = File.Open(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        {
            stream.Write(result);
            stream.Flush(flushToDisk: true);
        }
        if (!VehicleStatePackages.ReadFile(path, 1024 * 1024).SequenceEqual(result)) throw new IOException();
        return path;
    }
}
