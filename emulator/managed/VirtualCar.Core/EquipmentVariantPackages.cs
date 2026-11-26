namespace VirtualCar.Core;

public sealed record EquipmentVariant(int Offset, string Code, string ProfileSha);

/// <summary>Prepared emulator-only variant. The original provider and profile are never overwritten.</summary>
public static class EquipmentVariantPackages
{
    public static string Folder(string root, EquipmentVariant variant)
    {
        if (!Path.IsPathFullyQualified(root) || variant.Offset is < 2 or >= 130 || variant.Offset == 7 ||
            variant.Code.Length != 2 || variant.Code == "FF" ||
            !variant.Code.All(c => c is >= '0' and <= '9' or >= 'A' and <= 'F') ||
            !AcceptanceReportReader.IsHash(variant.ProfileSha, 64)) throw new InvalidDataException();
        return Path.Combine(Path.GetFullPath(root), "vehicle-data", "equipment-variants",
            variant.Offset.ToString("D3", System.Globalization.CultureInfo.InvariantCulture) + "-" + variant.Code);
    }

    public static string Library(string root, EquipmentVariant variant) =>
        Path.Combine(Folder(root, variant), "VirtualCarJ2534.dll");

    private static byte[] Baseline(string root) =>
        VehicleStatePackages.ReadFile(Path.Combine(LocalVehicleData.Folder(root), "virtualcar.ini"), 1024 * 1024);

    private static byte[] Native(string root) =>
        VehicleStatePackages.ReadFile(Path.Combine(LocalVehicleData.Folder(root), "VirtualCarJ2534.dll"), 64 * 1024 * 1024);

    private static bool SameDigest(byte[] bytes, string sha) =>
        NativeEcmScenarioApply.Digest(bytes).Equals(sha, StringComparison.OrdinalIgnoreCase);

    public static bool Matches(string root, ManagedEquipmentPreview editor, EquipmentReferences references,
        byte[] baseline, string nativeSha, EquipmentVariant variant)
    {
        try
        {
            if (!AcceptanceReportReader.IsHash(nativeSha, 64) || !Baseline(root).SequenceEqual(baseline) ||
                !SameDigest(Native(root), nativeSha) ||
                !BuiltInVehicles.IsNativePathSupported(Library(root, variant))) return false;
            byte[] expected = references.CompileVariant(editor, baseline, variant);
            return VehicleStatePackages.ReadFile(Path.Combine(Folder(root, variant), "virtualcar.ini"), 1024 * 1024)
                    .SequenceEqual(expected) &&
                SameDigest(VehicleStatePackages.ReadFile(Library(root, variant), 64 * 1024 * 1024), nativeSha);
        }
        catch (Exception) { return false; }
    }

    public static void Prepare(string root, ManagedEquipmentPreview editor, EquipmentReferences references,
        byte[] baseline, string nativeSha, EquipmentVariant variant)
    {
        if (!AcceptanceReportReader.IsHash(nativeSha, 64)) throw new InvalidDataException();
        byte[] expected = references.CompileVariant(editor, baseline, variant);
        byte[] dll = Native(root);
        if (!Baseline(root).SequenceEqual(baseline) || !SameDigest(dll, nativeSha)) throw new InvalidDataException();
        string target = Folder(root, variant);
        if (!BuiltInVehicles.IsNativePathSupported(Library(root, variant))) throw new InvalidDataException();
        string parent = Path.GetDirectoryName(target)!;
        for (DirectoryInfo? dir = new(Path.GetDirectoryName(parent)!); dir is not null; dir = dir.Parent)
            if ((dir.Attributes & FileAttributes.ReparsePoint) != 0 ||
                File.Exists(Path.Combine(dir.FullName, ".git")) || Directory.Exists(Path.Combine(dir.FullName, ".git")))
                throw new InvalidDataException();
        if (Directory.Exists(parent) && (File.GetAttributes(parent) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException();
        if (Directory.Exists(target))
        {
            if (!Matches(root, editor, references, baseline, nativeSha, variant)) throw new InvalidDataException();
            return;
        }
        // A detached independently checked draft must already exist.
        string detached = Path.Combine(Path.GetFullPath(root), "vehicle-data", "equipment-drafts",
            variant.ProfileSha + ".ini");
        if (!VehicleStatePackages.ReadFile(detached, 1024 * 1024).SequenceEqual(expected)) throw new InvalidDataException();
        Directory.CreateDirectory(parent);
        string temp = Path.Combine(parent, ".prepare-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temp);
        try
        {
            Write(Path.Combine(temp, "virtualcar.ini"), expected);
            Write(Path.Combine(temp, "VirtualCarJ2534.dll"), dll);
            if (!Baseline(root).SequenceEqual(baseline) || !Native(root).SequenceEqual(dll) ||
                !VehicleStatePackages.ReadFile(detached, 1024 * 1024).SequenceEqual(expected))
                throw new InvalidDataException("Source changed.");
            Directory.Move(temp, target);
            if (!Matches(root, editor, references, baseline, nativeSha, variant)) throw new IOException();
        }
        finally
        {
            if (Directory.Exists(temp) && (File.GetAttributes(temp) & FileAttributes.ReparsePoint) == 0)
            {
                File.Delete(Path.Combine(temp, "virtualcar.ini"));
                File.Delete(Path.Combine(temp, "VirtualCarJ2534.dll"));
                Directory.Delete(temp);
            }
        }
    }

    private static void Write(string path, byte[] bytes)
    {
        using var stream = File.Open(path, FileMode.CreateNew, FileAccess.Write, FileShare.None);
        stream.Write(bytes);
        stream.Flush(flushToDisk: true);
    }
}
