namespace VirtualCar.Core;

public sealed record VehicleStateChoice(NativeIgnitionSelection? Ignition, EcmScenario? Engine)
{
    public static VehicleStateChoice Original { get; } = new(null, null);
    public bool IsOriginal => Ignition is null && Engine is null;
    public string Key => "i" + (Ignition is null ? "base" : ((int)Ignition.Value).ToString(System.Globalization.CultureInfo.InvariantCulture)) +
        "-e" + (Engine is null ? "base" : ((int)Engine.Value).ToString(System.Globalization.CultureInfo.InvariantCulture));
}

/// <summary>Build immutable per-state simulator copies. No registry, client or ECU access.</summary>
public static class VehicleStatePackages
{
    public static IReadOnlyList<NativeIgnitionSelection?> Ignitions(byte[] baseline) =>
        NativeIgnitionPlan.Inspect(baseline).CanApply
            ? Array.AsReadOnly(new NativeIgnitionSelection?[] { null, NativeIgnitionSelection.Baseline, NativeIgnitionSelection.PositionIICandidate })
            : Array.AsReadOnly(new NativeIgnitionSelection?[] { null });

    public static IReadOnlyList<EcmScenario?> Engines(byte[] baseline) =>
        Array.AsReadOnly(new EcmScenario?[] { null }.Concat(Enum.GetValues<EcmScenario>()
            .Where(s => NativeEcmScenarioPlan.Inspect(baseline, s).CanApply).Select(s => (EcmScenario?)s)).ToArray());

    public static byte[] Build(byte[] baseline, VehicleStateChoice choice)
    {
        if (!Ignitions(baseline).Contains(choice.Ignition) || !Engines(baseline).Contains(choice.Engine))
            throw new InvalidOperationException("State not supported by profile.");
        byte[] result = baseline.ToArray();
        if (choice.Ignition is { } ignition) result = NativeIgnitionPlan.Build(result, ignition);
        if (choice.Engine is { } engine) result = NativeEcmScenarioApply.Build(result, engine);
        // The existing transformations alter only their own named scenario sections.
        if (choice.Ignition is { } i && NativeIgnitionPlan.Inspect(result).Configured != i ||
            choice.Engine is { } e && NativeEcmScenarioPlan.Inspect(result).Selection != e)
            throw new InvalidDataException("State verification failed.");
        return result;
    }

    public static string Folder(string root, VehicleStateChoice choice)
    {
        if (!Path.IsPathFullyQualified(root) ||
            choice.Ignition is { } i && !Enum.IsDefined(i) ||
            choice.Engine is { } e && !Enum.IsDefined(e)) throw new InvalidDataException();
        return choice.IsOriginal ? LocalVehicleData.Folder(root) :
            Path.Combine(Path.GetFullPath(root), "vehicle-data", "xc90-v8-2009-states", choice.Key);
    }

    public static byte[] ReadFile(string path, int cap)
    {
        if (!Path.IsPathFullyQualified(path)) throw new InvalidDataException();
        if (OperatingSystem.IsWindows() &&
            (path.StartsWith(@"\\", StringComparison.Ordinal) || new DriveInfo(Path.GetPathRoot(path)!).DriveType != DriveType.Fixed))
            throw new InvalidDataException();
        for (FileSystemInfo? item = new FileInfo(path); item is not null;
            item = item is FileInfo file ? file.Directory : ((DirectoryInfo)item).Parent)
            if ((item.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException();
        using var stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (stream.Length is < 1 || stream.Length > cap) throw new InvalidDataException();
        byte[] bytes = new byte[(int)stream.Length];
        stream.ReadExactly(bytes);
        if (stream.ReadByte() != -1) throw new InvalidDataException();
        return bytes;
    }

    public static bool Matches(string root, VehicleStateChoice choice, byte[] baseline, string nativeSha)
    {
        try
        {
            string dir = Folder(root, choice);
            byte[] expected = Build(baseline, choice);
            byte[] profile = ReadFile(Path.Combine(dir, "virtualcar.ini"), 1024 * 1024);
            byte[] dll = ReadFile(Path.Combine(dir, "VirtualCarJ2534.dll"), 64 * 1024 * 1024);
            return profile.AsSpan().SequenceEqual(expected) &&
                NativeEcmScenarioApply.Digest(dll).Equals(nativeSha, StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception) { return false; }
    }

    // Caller explicitly confirms all diagnostic clients closed and checks registration absent.
    // A deterministic target never gets overwritten; invalid existing copies are rejected.
    public static void Prepare(string root, VehicleStateChoice choice, byte[] baseline, string nativeSha)
    {
        if (choice.IsOriginal || !AcceptanceReportReader.IsHash(nativeSha, 64)) throw new InvalidDataException();
        string source = LocalVehicleData.Folder(root);
        byte[] original = ReadFile(Path.Combine(source, "virtualcar.ini"), 1024 * 1024);
        if (!original.AsSpan().SequenceEqual(baseline)) throw new InvalidDataException();
        byte[] dll = ReadFile(Path.Combine(source, "VirtualCarJ2534.dll"), 64 * 1024 * 1024);
        if (!NativeEcmScenarioApply.Digest(dll).Equals(nativeSha, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        byte[] profile = Build(original, choice);
        string target = Folder(root, choice);
        if (!BuiltInVehicles.IsNativePathSupported(Path.Combine(target, "VirtualCarJ2534.dll")))
            throw new InvalidDataException();
        if (Directory.Exists(target))
        {
            if (!Matches(root, choice, baseline, nativeSha)) throw new InvalidDataException();
            return;
        }
        string parent = Path.GetDirectoryName(target)!;
        for (DirectoryInfo? dir = new DirectoryInfo(Path.GetDirectoryName(parent)!); dir is not null; dir = dir.Parent)
            if ((dir.Attributes & FileAttributes.ReparsePoint) != 0 || Directory.Exists(Path.Combine(dir.FullName, ".git")) || File.Exists(Path.Combine(dir.FullName, ".git")))
                throw new InvalidDataException();
        // Source ancestry was checked on read. The state directory is a sibling under vehicle-data.
        if (Directory.Exists(parent) && (File.GetAttributes(parent) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException();
        Directory.CreateDirectory(parent);
        string temp = Path.Combine(parent, ".prepare-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temp);
        try
        {
            Write(Path.Combine(temp, "virtualcar.ini"), profile);
            Write(Path.Combine(temp, "VirtualCarJ2534.dll"), dll);
            if (!ReadFile(Path.Combine(source, "virtualcar.ini"), 1024 * 1024).AsSpan().SequenceEqual(original) ||
                !ReadFile(Path.Combine(source, "VirtualCarJ2534.dll"), 64 * 1024 * 1024).AsSpan().SequenceEqual(dll))
                throw new InvalidDataException("Source changed during preparation.");
            Directory.Move(temp, target);
            if (!Matches(root, choice, baseline, nativeSha)) throw new IOException("Prepared state verification failed.");
        }
        finally
        {
            if (Directory.Exists(temp) && (File.GetAttributes(temp) & FileAttributes.ReparsePoint) == 0)
            {
                // Delete only our known temporary files, never recursively traverse a replaced path.
                foreach (string name in new[] { "virtualcar.ini", "VirtualCarJ2534.dll" })
                    File.Delete(Path.Combine(temp, name));
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
