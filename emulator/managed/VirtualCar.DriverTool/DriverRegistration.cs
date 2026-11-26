using Microsoft.Win32;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;

namespace VirtualCar.DriverTool;

internal static class DriverRegistration
{
    internal const string Parent = @"SOFTWARE\PassThruSupport.04.04";
    internal const string Provider = "J2534 Lab Adapter";
    private const string Vendor = "J2534 Lab";
    private const string Name = Provider;
    // Historical identity is recognized only to allow explicit removal.
    private const string LegacyProvider = "SectorV Virtual Car";
    private const string LegacyVendor = "SectorV Virtual Lab";
    private const string LegacyName = "SectorV Virtual Car (J2534)";
    private static readonly string[] Names =
        ["Vendor", "Name", "FunctionLibrary", "ConfigApplication", "CAN", "ISO15765", "MessageVersion"];

    internal enum State { Absent, Registered, LegacyRegistered, Conflict, Unavailable }
    internal sealed record Info(State Status, string? Library);

    // Validate a local, explicitly chosen x86 DLL without loading it.
    internal static string Fingerprint(string path)
    {
        if (!Path.IsPathFullyQualified(path) || path.StartsWith(@"\\", StringComparison.Ordinal) ||
            !string.Equals(Path.GetFileName(path), "VirtualCarJ2534.dll", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        string full = Path.GetFullPath(path);
        if (new DriveInfo(Path.GetPathRoot(full)!).DriveType != DriveType.Fixed)
            throw new InvalidDataException();
        for (FileSystemInfo? item = new FileInfo(full); item is not null;
            item = item is FileInfo file ? file.Directory : ((DirectoryInfo)item).Parent)
            if ((item.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException();
        using var stream = File.Open(full, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (stream.Length < 256 || stream.Length > 64L * 1024 * 1024) throw new InvalidDataException();
        using (var pe = new PEReader(stream, PEStreamOptions.LeaveOpen))
        {
            var headers = pe.PEHeaders;
            var optional = headers.PEHeader;
            if (headers.CoffHeader.Machine != Machine.I386 ||
                optional is null || optional.Magic != PEMagic.PE32 ||
                (headers.CoffHeader.Characteristics & Characteristics.Dll) == 0 ||
                optional.ExportTableDirectory.Size < 40)
                throw new InvalidDataException();
        }
        stream.Position = 0;
        return Convert.ToHexString(SHA256.HashData(stream));
    }

    private static object? Value(RegistryKey key, string name) =>
        key.GetValue(name, null, RegistryValueOptions.DoNotExpandEnvironmentNames);

    private static bool Owned(RegistryKey key, bool legacy = false) =>
        key.SubKeyCount == 0 &&
        new HashSet<string>(key.GetValueNames(), StringComparer.OrdinalIgnoreCase).SetEquals(Names) &&
        Equals(Value(key, "Vendor"), legacy ? LegacyVendor : Vendor) &&
        Equals(Value(key, "Name"), legacy ? LegacyName : Name) &&
        Value(key, "FunctionLibrary") is string library &&
        Path.IsPathFullyQualified(library) &&
        string.Equals(Path.GetFileName(library), "VirtualCarJ2534.dll", StringComparison.OrdinalIgnoreCase) &&
        key.GetValueKind("FunctionLibrary") == RegistryValueKind.String &&
        Equals(Value(key, "ConfigApplication"), "") &&
        Equals(Value(key, "CAN"), 1) && Equals(Value(key, "ISO15765"), 1) &&
        Equals(Value(key, "MessageVersion"), 0x0404);

    internal static Info Read()
    {
        try
        {
            using var root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry32);
            using var key = root.OpenSubKey(Parent + @"\" + Provider);
            using var legacy = root.OpenSubKey(Parent + @"\" + LegacyProvider);
            if (key is not null && legacy is not null) return new(State.Conflict, null);
            if (key is not null)
                return Owned(key) ? new(State.Registered, (string?)Value(key, "FunctionLibrary")) : new(State.Conflict, null);
            if (legacy is not null)
                return Owned(legacy, legacy: true) ? new(State.LegacyRegistered, (string?)Value(legacy, "FunctionLibrary")) : new(State.Conflict, null);
            return new(State.Absent, null);
        }
        catch (Exception) { return new(State.Unavailable, null); }
    }

    // Caller must have explicitly requested elevation and confirmed the exact path/hash.
    internal static void Install(string path, string expectedSha256)
    {
        path = Path.GetFullPath(path);
        if (expectedSha256.Length != 64 ||
            !string.Equals(Fingerprint(path), expectedSha256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        using var root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry32);
        using var parent = root.CreateSubKey(Parent);
        using (var legacy = parent.OpenSubKey(LegacyProvider))
            if (legacy is not null) throw new InvalidOperationException("Remove the previous registration first.");
        using (var existing = parent.OpenSubKey(Provider))
        {
            if (existing is not null)
            {
                if (Owned(existing) && string.Equals((string?)Value(existing, "FunctionLibrary"),
                    path, StringComparison.OrdinalIgnoreCase)) return;
                throw new InvalidOperationException("Existing registration must be reviewed and removed first.");
            }
        }
        // Serialize our own mutations; do not run concurrent external installers.
        try
        {
            using var key = parent.CreateSubKey(Provider);
            key.SetValue("Vendor", Vendor, RegistryValueKind.String);
            key.SetValue("Name", Name, RegistryValueKind.String);
            key.SetValue("FunctionLibrary", path, RegistryValueKind.String);
            key.SetValue("ConfigApplication", "", RegistryValueKind.String);
            key.SetValue("CAN", 1, RegistryValueKind.DWord);
            key.SetValue("ISO15765", 1, RegistryValueKind.DWord);
            key.SetValue("MessageVersion", 0x0404, RegistryValueKind.DWord);
            key.Flush();
            if (!Owned(key)) throw new IOException();
        }
        catch
        {
            // Do not delete a possibly changed/partial registration automatically.
            // A conflict is reported and further mutations are blocked for review.
            throw;
        }
    }

    internal static void Remove(string expectedPath, bool canonicalOnly = false, string? expectedSha256 = null)
    {
        if (canonicalOnly && (expectedSha256 is null || expectedSha256.Length != 64 ||
            !string.Equals(Fingerprint(expectedPath), expectedSha256, StringComparison.OrdinalIgnoreCase)))
            throw new InvalidDataException();
        using var root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry32);
        using var parent = root.OpenSubKey(Parent, writable: true);
        if (parent is null) return;
        string target;
        using (var key = parent.OpenSubKey(Provider))
        using (var legacy = parent.OpenSubKey(LegacyProvider))
        {
            if (key is not null && legacy is not null) throw new InvalidOperationException("Conflicting registrations.");
            var selected = key ?? legacy;
            if (selected is null) return;
            bool isLegacy = key is null;
            if (canonicalOnly && isLegacy) throw new InvalidOperationException("Legacy registration is outside the canonical acceptance scope.");
            if (!Owned(selected, isLegacy) || !string.Equals((string?)Value(selected, "FunctionLibrary"),
                expectedPath, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Registration changed or is not recognized.");
            target = isLegacy ? LegacyProvider : Provider;
        }
        // Never recursive, never delete the parent or files on disk.
        parent.DeleteSubKey(target, throwOnMissingSubKey: false);
    }
}
