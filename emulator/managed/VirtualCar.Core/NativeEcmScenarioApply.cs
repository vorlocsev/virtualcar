using System.Security.Cryptography;
using System.Text;

namespace VirtualCar.Core;

public sealed record NativeScenarioApplyResult(bool Changed, string? BackupPath, string Sha256);

/// <summary>Scoped INI update. No DLL loading, registry mutation or client control.</summary>
public static class NativeEcmScenarioApply
{
    private const int MaxBytes = 1024 * 1024;
    private const string StaticSection = "B3A316_EcmScenarioLab";
    private const string DynamicSection = "B3A329_DynamicEcmLab";

    public static byte[] Build(ReadOnlySpan<byte> original, EcmScenario selection)
    {
        if (!NativeEcmScenarioPlan.Inspect(original, selection).CanApply)
            throw new InvalidOperationException("Required gates missing.");
        string text = Encoding.Latin1.GetString(original);
        // Restrict edits to ordinary LF/CRLF files. Other text bytes are preserved.
        if (text.Replace("\r\n", "\n").Contains('\r'))
            throw new InvalidDataException("Unsupported line endings.");
        string newline = text.Contains("\r\n") ? "\r\n" : "\n";
        var lines = text.Split('\n').ToList();
        bool dynamic = selection == EcmScenario.Dynamic;
        UpdateSection(lines, StaticSection, new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["Enabled"] = "1",
            ["State"] = dynamic ? "0" : ((int)selection).ToString(System.Globalization.CultureInfo.InvariantCulture)
        }, newline);
        UpdateSection(lines, DynamicSection, new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["Enabled"] = dynamic ? "1" : "0"
        }, newline);
        byte[] result = Encoding.Latin1.GetBytes(string.Join("\n", lines));
        var verified = NativeEcmScenarioPlan.Inspect(result);
        if (verified.Selection != selection || !verified.CanApply)
            throw new InvalidDataException("Candidate verification failed.");
        return result;
    }

    internal static void UpdateSection(List<string> lines, string section,
        Dictionary<string, string> missing, string newline)
    {
        int start = -1, end = lines.Count;
        for (int i = 0; i < lines.Count; i++)
        {
            string line = lines[i].Trim();
            if (!line.StartsWith('[')) continue;
            if (start >= 0) { end = i; break; }
            if (string.Equals(line, "[" + section + "]", StringComparison.OrdinalIgnoreCase))
                start = i;
            else if (line.EndsWith(']') &&
                string.Equals(line[1..^1].Trim(), section, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Noncanonical target section.");
        }
        string ending = newline == "\r\n" ? "\r" : "";
        if (start < 0)
        {
            // Preserve original bytes, adding a separator only when needed.
            if (lines[^1].Length == 0) lines.RemoveAt(lines.Count - 1);
            else if (!lines[^1].EndsWith('\r') && ending.Length > 0) lines[^1] += ending;
            lines.Add("[" + section + "]" + ending);
            foreach (var pair in missing) lines.Add(pair.Key + "=" + pair.Value + ending);
            lines.Add("");
            return;
        }

        for (int i = start + 1; i < end; i++)
        {
            string raw = lines[i];
            string trimmed = raw.Trim();
            if (trimmed.Length == 0 || trimmed.StartsWith(';') || trimmed.StartsWith('#')) continue;
            int eq = raw.IndexOf('=');
            if (eq < 1) continue;
            string key = raw[..eq].Trim();
            if (!missing.TryGetValue(key, out string? value)) continue;
            int at = eq + 1;
            while (at < raw.Length && raw[at] is ' ' or '\t') at++;
            int length = key.Equals("A45FRawByte", StringComparison.OrdinalIgnoreCase) ? 2 : 1;
            if (at + length > raw.Length ||
                (length == 2 ? raw.Substring(at, length) != "07" : raw[at] is < '0' or > '4') ||
                raw[(at + length)..].Any(c => c is not (' ' or '\t' or '\r')))
                throw new InvalidDataException("Ambiguous target value.");
            lines[i] = raw[..at] + value + raw[(at + length)..];
            missing.Remove(key);
        }
        if (missing.Count == 0) return;
        // A final empty element denotes an existing terminal newline.
        if (end == lines.Count && lines[^1].Length == 0) end--;
        if (end == lines.Count && ending.Length > 0 && !lines[^1].EndsWith('\r'))
            lines[^1] += ending;
        foreach (var pair in missing)
            lines.Insert(end++, pair.Key + "=" + pair.Value + ending);
        if (end == lines.Count) lines.Add("");
    }

    private static string ValidatePath(string path)
    {
        if (!Path.IsPathFullyQualified(path) ||
            !string.Equals(Path.GetFileName(path), "virtualcar.ini", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Explicit profile path required.");
        return ValidateLocalFile(path);
    }

    private static string ValidateLocalFile(string path)
    {
        string full = Path.GetFullPath(path);
        if (OperatingSystem.IsWindows() &&
            (full.StartsWith(@"\\", StringComparison.Ordinal) ||
             new DriveInfo(Path.GetPathRoot(full)!).DriveType != DriveType.Fixed))
            throw new InvalidDataException("Local fixed drive required.");
        for (FileSystemInfo? item = new FileInfo(full); item is not null;
            item = item is FileInfo file ? file.Directory : ((DirectoryInfo)item).Parent)
            if ((item.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Reparse point not allowed.");
        return full;
    }

    public static byte[] ReadProfile(string path)
    {
        using var stream = File.Open(ValidatePath(path), FileMode.Open, FileAccess.Read, FileShare.Read);
        return ReadBounded(stream);
    }

    // Only exact VC080/VC081/VC082 backups beside the selected profile are accepted.
    private static string ValidateBackup(string profile, string backup)
    {
        if (!Path.IsPathFullyQualified(backup)) throw new InvalidDataException("Absolute backup path required.");
        string full = ValidateLocalFile(backup);
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (!string.Equals(Path.GetDirectoryName(profile), Path.GetDirectoryName(full), comparison))
            throw new InvalidDataException("Backup must be beside the profile.");
        string name = Path.GetFileName(full);
        const string prefix = "virtualcar.vc08";
        if (name.Length != prefix.Length + 2 + 32 + 4 ||
            !name.StartsWith(prefix, StringComparison.Ordinal) ||
            name[prefix.Length] is not ('0' or '1' or '2') || name[prefix.Length + 1] != '-' ||
            !name.EndsWith(".bak", StringComparison.Ordinal) ||
            !Guid.TryParseExact(name.Substring(prefix.Length + 2, 32), "N", out _))
            throw new InvalidDataException("Unrecognized backup name.");
        return full;
    }

    public static byte[] ReadBackup(string path, string backup)
    {
        string profile = ValidatePath(path);
        using var stream = File.Open(ValidateBackup(profile, backup), FileMode.Open, FileAccess.Read, FileShare.Read);
        byte[] bytes = ReadBounded(stream);
        NativeEcmScenarioPlan.Inspect(bytes);
        return bytes;
    }

    private static byte[] ReadBounded(Stream stream)
    {
        byte[] bytes = new byte[MaxBytes + 1];
        int count = stream.ReadAtLeast(bytes, bytes.Length, throwIfEndOfStream: false);
        if (count is < 1 or > MaxBytes) throw new InvalidDataException("Profile size rejected.");
        return bytes[..count];
    }

    public static string Digest(ReadOnlySpan<byte> bytes) => Convert.ToHexString(SHA256.HashData(bytes));

    /// <summary>Caller confirms all diagnostic clients and external editors are closed.
    /// Same-directory replace with backup; not a lock against unrelated rename operations.</summary>
    public static NativeScenarioApplyResult Apply(string path, string expectedSha256, EcmScenario selection)
    {
        return Replace(path, expectedSha256, before => Build(before, selection), "vc080");
    }

    // Restore only a verified ancestor produced by a scoped scenario edit.
    // Full-byte equality against one of the six forward transformations proves
    // that unrelated configuration was not changed since this backup.
    public static NativeScenarioApplyResult Restore(string path, string backup,
        string expectedCurrentSha256, string expectedBackupSha256)
    {
        string full = ValidatePath(path);
        string source = ValidateBackup(full, backup);
        using var input = File.Open(source, FileMode.Open, FileAccess.Read, FileShare.Read);
        byte[] original = ReadBounded(input);
        NativeEcmScenarioPlan.Inspect(original);
        if (!string.Equals(Digest(original), expectedBackupSha256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Backup changed since inspection.");
        return Replace(full, expectedCurrentSha256, current =>
        {
            if (current.AsSpan().SequenceEqual(original)) return original;
            foreach (var scenario in Enum.GetValues<EcmScenario>())
            {
                try
                {
                    if (Build(original, scenario).AsSpan().SequenceEqual(current)) return original;
                }
                catch (InvalidOperationException) { }
                catch (InvalidDataException) { }
            }
            // Also allow undoing a previous restore (reverse transformation).
            foreach (var scenario in Enum.GetValues<EcmScenario>())
            {
                try
                {
                    if (Build(current, scenario).AsSpan().SequenceEqual(original)) return original;
                }
                catch (InvalidOperationException) { }
                catch (InvalidDataException) { }
            }
            foreach (var ignition in Enum.GetValues<NativeIgnitionSelection>())
            {
                try
                {
                    if (NativeIgnitionPlan.Build(original, ignition).AsSpan().SequenceEqual(current)) return original;
                }
                catch (InvalidOperationException) { }
                catch (InvalidDataException) { }
                try
                {
                    if (NativeIgnitionPlan.Build(current, ignition).AsSpan().SequenceEqual(original)) return original;
                }
                catch (InvalidOperationException) { }
                catch (InvalidDataException) { }
            }
            throw new InvalidOperationException("Backup is not a verified scenario-only relative of this profile.");
        }, "vc081");
    }

    internal static NativeScenarioApplyResult Replace(string path, string expectedSha256,
        Func<byte[], byte[]> transform, string tag)
    {
        string full = ValidatePath(path);
        string directory = Path.GetDirectoryName(full)!;
        string suffix = Guid.NewGuid().ToString("N");
        string temp = Path.Combine(directory, "." + tag + "-" + suffix + ".tmp");
        string backup = Path.Combine(directory, "virtualcar." + tag + "-" + suffix + ".bak");
        bool created = false;
        try
        {
            // Deny new writers on Windows while permitting the required rename.
            using var original = File.Open(full, FileMode.Open, FileAccess.Read, FileShare.Read | FileShare.Delete);
            byte[] before = ReadBounded(original);
            if (!string.Equals(Digest(before), expectedSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Profile changed since inspection.");
            byte[] after = transform(before);
            string digest = Digest(after);
            if (before.AsSpan().SequenceEqual(after))
                return new(false, null, digest);
            using (var output = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                created = true;
                output.Write(after);
                output.Flush(flushToDisk: true);
            }
            if (File.Exists(backup)) throw new IOException("Backup collision.");
            // Recheck the path, not just the already-open source handle.
            if (!string.Equals(Digest(ReadProfile(full)), expectedSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Profile changed before replacement.");
            File.Replace(temp, full, backup);
            if (Digest(ReadProfile(full)) != digest ||
                !ReadBackup(full, backup).AsSpan().SequenceEqual(before))
                throw new IOException("Replacement verification failed. Preserve the backup for review.");
            return new(true, backup, digest);
        }
        finally
        {
            if (created && File.Exists(temp)) File.Delete(temp);
        }
    }
}
