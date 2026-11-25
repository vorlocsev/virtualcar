using Microsoft.Win32;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;

namespace VirtualCar.DriverTool;

internal static class DriverRegistration
{
    internal const string Parent = @"SOFTWARE\PassThruSupport.04.04";
    internal const string Provider = "SectorV Virtual Car";
    private const string Vendor = "SectorV Virtual Lab";
    private const string Name = "SectorV Virtual Car (J2534)";
    private static readonly string[] Names =
        ["Vendor", "Name", "FunctionLibrary", "ConfigApplication", "CAN", "ISO15765", "MessageVersion"];

    internal enum State { Absent, Registered, Conflict, Unavailable }
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
            if (headers.CoffHeader.Machine != Machine.I386 ||
                headers.PEHeader?.Magic != PEMagic.PE32 ||
                (headers.CoffHeader.Characteristics & Characteristics.Dll) == 0 ||
                headers.PEHeader.ExportTableDirectory.Size < 40)
                throw new InvalidDataException();
        }
        stream.Position = 0;
        return Convert.ToHexString(SHA256.HashData(stream));
    }

    private static object? Value(RegistryKey key, string name) =>
        key.GetValue(name, null, RegistryValueOptions.DoNotExpandEnvironmentNames);

    private static bool Owned(RegistryKey key) =>
        key.SubKeyCount == 0 &&
        new HashSet<string>(key.GetValueNames(), StringComparer.OrdinalIgnoreCase).SetEquals(Names) &&
        Equals(Value(key, "Vendor"), Vendor) && Equals(Value(key, "Name"), Name) &&
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
            if (key is null) return new(State.Absent, null);
            return Owned(key) ? new(State.Registered, (string?)Value(key, "FunctionLibrary")) : new(State.Conflict, null);
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

    internal static void Remove(string expectedPath)
    {
        using var root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry32);
        using var parent = root.OpenSubKey(Parent, writable: true);
        if (parent is null) return;
        using (var key = parent.OpenSubKey(Provider))
        {
            if (key is null) return;
            if (!Owned(key) || !string.Equals((string?)Value(key, "FunctionLibrary"),
                expectedPath, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Registration changed or is not recognized.");
        }
        // Never recursive, never delete the parent or files on disk.
        parent.DeleteSubKey(Provider, throwOnMissingSubKey: false);
    }
}
