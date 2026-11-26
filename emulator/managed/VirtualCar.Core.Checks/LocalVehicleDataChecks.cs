using System.Text.Json;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class LocalVehicleDataChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC094B 01 full baseline equipment catalog", () => Run(Test01)),
        ("VC094B 02 preserve original labels", () => Run(Test02)),
        ("VC094B 03 reject incomplete or duplicate fields", () => Run(Test03)),
        ("VC094B 04 reject identity lock changes", () => Run(Test04)),
        ("VC094B 05 reject unknown schema and extra keys", () => Run(Test05)),
        ("VC094B 06 bound data size", () => Run(Test06)),
        ("VC094B 07 missing local package is not a vehicle", () => Run(Test07)),
        ("VC094B 08 reject unpinned simulator profile", () => Run(Test08)),
        ("VC095C 01 missing package is distinct from invalid", () => Run(Test09)),
        ("VC095C 02 incomplete local package rejected", () => Run(Test10)),
        ("VC095C 03 malformed local manifest rejected", () => Run(Test11)),
        ("VC095C 04 vehicle VIN scoped to Vehicle", () => Run(Test12)),
        ("VC095C 05 reject missing or duplicate vehicle identity", () => Run(Test13)),
        ("VC095C 06 reject wrong year and VIN syntax", () => Run(Test14)),
        ("VC095C 07 reject duplicate Vehicle section", () => Run(Test15)),
        ("VC095C 08 reject invalid identity encoding and oversized bytes", () => Run(Test16)),
        ("VC095H 01 native reference matches", () => Run(Test17)),
        ("VC095H 02 reject different native hash", () => Run(Test18)),
        ("VC095H 03 reject changed reference DLL", () => Run(Test19)),
        ("VC095H 04 reject changed reference INI", () => Run(Test20)),
        ("VC095H 05 reject missing or invalid reference marker", () => Run(Test21)),
        ("VC095H 06 exact inventory for all supported schemas", () => Run(Test22)),
        ("VC095H 07 reject incomplete inventory", () => Run(Test23)),
        ("VC095H 08 reject extra, pending or directory entries", () => Run(Test24))
    ];
    private static Task Run(Action action) { action(); return Task.CompletedTask; }
    private static void Require(bool value) { if (!value) throw new InvalidOperationException(); }
    private static void Reject(Action action)
    {
        try { action(); }
        catch (InvalidDataException) { return; }
        catch (IOException) { return; }
        catch (JsonException) { return; }
        throw new InvalidOperationException("Expected rejection");
    }
    private static Dictionary<string, object>[] Rows()
    {
        int[] locked = [2,3,4,8,9,10,12,16,28,33,36,123];
        return Enumerable.Range(0,130).Where(i => i is not (0 or 1 or 7))
            .Select(i => new Dictionary<string, object> { ["offset"] = i, ["name"] = "Original " + i,
                ["value"] = "Оригинальное значение", ["locked"] = locked.Contains(i) }).ToArray();
    }
    private static byte[] Encode(object rows, string schema = "vc094b-cem-baseline-v1") =>
        JsonSerializer.SerializeToUtf8Bytes(new { schema, rows });
    private static void Test01()
    {
        var rows = LocalVehicleData.ParseCatalog(Encode(Rows()));
        Require(rows.Count == 127 && rows.Count(r => r.Locked) == 12 && rows[0].Offset == 2);
    }
    private static void Test02()
    {
        var rows = LocalVehicleData.ParseCatalog(Encode(Rows()));
        Require(rows[0].Name == "Original 2" && rows[0].Value == "Оригинальное значение");
    }
    private static void Test03()
    {
        var rows = Rows(); Reject(() => LocalVehicleData.ParseCatalog(Encode(rows.Take(126))));
        rows[1]["offset"] = 2; Reject(() => LocalVehicleData.ParseCatalog(Encode(rows)));
    }
    private static void Test04()
    {
        var rows = Rows(); rows[0]["locked"] = false; Reject(() => LocalVehicleData.ParseCatalog(Encode(rows)));
    }
    private static void Test05()
    {
        Reject(() => LocalVehicleData.ParseCatalog(Encode(Rows(), "unknown")));
        var rows = Rows(); rows[0]["raw"] = "extra"; Reject(() => LocalVehicleData.ParseCatalog(Encode(rows)));
    }
    private static void Test06()
    {
        Reject(() => LocalVehicleData.ParseCatalog(new byte[1024 * 1024 + 1]));
        var rows = Rows(); rows[0]["name"] = new string('x',513); Reject(() => LocalVehicleData.ParseCatalog(Encode(rows)));
    }
    private static void Test07()
    {
        string root = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Reject(() => LocalVehicleData.Load(root));
    }
    private static void Test08()
    {
        string root = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        string folder = LocalVehicleData.Folder(root); Directory.CreateDirectory(folder);
        try
        {
            File.WriteAllBytes(Path.Combine(folder, "virtualcar.ini"), BuiltInVehicles.ReadProfile("p2"));
            Reject(() => LocalVehicleData.ReadProfile(root));
        }
        finally { Directory.Delete(root, true); }
    }

    private const string SyntheticVin = "YV1CZ000290000001";
    private static byte[] Ini(string text) => System.Text.Encoding.ASCII.GetBytes(text);
    private static string Identity => "[Vehicle]\r\nVIN=" + SyntheticVin + "\r\nModelYear=2009\r\n";
    private static void WithFolder(Action<string,string> check)
    {
        string root = Path.Combine(Path.GetTempPath(), "VC095C-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try { check(root, LocalVehicleData.Folder(root)); }
        finally { Directory.Delete(root, true); }
    }
    private static void Test09() => WithFolder((root, folder) =>
    {
        Require(LocalVehicleData.Probe(root, out var profile) == LocalVehicleData.Availability.Missing && profile is null);
        Directory.CreateDirectory(Path.GetDirectoryName(folder)!);
        File.WriteAllText(folder, "not a directory");
        Require(LocalVehicleData.Probe(root, out profile) == LocalVehicleData.Availability.Invalid && profile is null);
    });
    private static void Test10() => WithFolder((root, folder) =>
    {
        Directory.CreateDirectory(folder);
        Require(LocalVehicleData.Probe(root, out var profile) == LocalVehicleData.Availability.Invalid && profile is null);
    });
    private static void Test11() => WithFolder((root, folder) =>
    {
        Directory.CreateDirectory(folder);
        string file = Path.Combine(folder,"local-profile.json");
        foreach (string bad in new[] { "{", "[]", "{}", "{\"schema\":null}", "{\"schema\":\"unknown\"}" })
        {
            File.WriteAllText(file,bad);
            Require(LocalVehicleData.Probe(root,out var profile) == LocalVehicleData.Availability.Invalid && profile is null);
            Require(File.ReadAllText(file)==bad);
        }
    });
    private static void Test12()
    {
        Require(LocalVehicleData.ReadVehicleVin(Ini("[ECU0]\nVIN=UNRELATED\n" + Identity + "[ECU1]\nVIN=OTHER\n")) == SyntheticVin);
        Require(LocalVehicleData.ReadVehicleVin(Ini("[vehicle]\n vin = " + SyntheticVin + "\n modelyear = 2009\n")) == SyntheticVin);
    }
    private static void Test13()
    {
        foreach (string bad in new[] { "[ECU0]\nVIN="+SyntheticVin+"\nModelYear=2009\n",
            Identity+"vin="+SyntheticVin+"\n",Identity+"ModelYear=2009\n",
            "[Vehicle]\nVIN="+SyntheticVin+"\n", "[Vehicle]\nModelYear=2009\n" })
            Reject(()=>LocalVehicleData.ReadVehicleVin(Ini(bad)));
    }
    private static void Test14()
    {
        foreach (string bad in new[] { Identity.Replace("2009","2010"), Identity.Replace(SyntheticVin,"YV1CZ0002A0000001"),
            Identity.Replace(SyntheticVin,"YV1CZ000I90000001"), Identity.Replace(SyntheticVin,"short") })
            Reject(()=>LocalVehicleData.ReadVehicleVin(Ini(bad)));
    }
    private static void Test15() => Reject(()=>LocalVehicleData.ReadVehicleVin(Ini(Identity+Identity)));
    private static void Test16()
    {
        Reject(()=>LocalVehicleData.ReadVehicleVin(new byte[1024*1024+1]));
        Reject(()=>LocalVehicleData.ReadVehicleVin(Ini(Identity+"\0")));
        Reject(()=>LocalVehicleData.ReadVehicleVin(Ini(Identity).Concat(new byte[]{0xff}).ToArray()));
    }

    private static void WithNativeReference(Action<string,string,string> check) => WithFolder((root, _) =>
    {
        string dll = BuiltInVehicles.PackageLibrary(root, "p2");
        string dir = Path.GetDirectoryName(dll)!;
        Directory.CreateDirectory(dir);
        byte[] bytes = [1,2,3,4];
        string sha = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(bytes));
        File.WriteAllBytes(dll, bytes);
        File.WriteAllBytes(Path.Combine(dir, "virtualcar.ini"), BuiltInVehicles.ReadProfile("p2"));
        File.WriteAllText(Path.Combine(dir, "candidate.sha256"), sha);
        check(root, dir, sha);
    });
    private static void Test17() => WithNativeReference((root, dir, sha) =>
    {
        LocalVehicleData.ValidateNativeBinding(root, sha.ToLowerInvariant());
    });
    private static void Test18() => WithNativeReference((root, dir, sha) =>
    {
        Reject(() => LocalVehicleData.ValidateNativeBinding(root, new string('0', 64)));
    });
    private static void Test19() => WithNativeReference((root, dir, sha) =>
    {
        File.WriteAllBytes(Path.Combine(dir, "VirtualCarJ2534.dll"), [4,3,2,1]);
        Reject(() => LocalVehicleData.ValidateNativeBinding(root, sha));
    });
    private static void Test20() => WithNativeReference((root, dir, sha) =>
    {
        File.AppendAllText(Path.Combine(dir, "virtualcar.ini"), "; changed");
        Reject(() => LocalVehicleData.ValidateNativeBinding(root, sha));
    });
    private static void Test21() => WithNativeReference((root, dir, sha) =>
    {
        string marker = Path.Combine(dir, "candidate.sha256");
        File.WriteAllText(marker, "invalid");
        Reject(() => LocalVehicleData.ValidateNativeBinding(root, sha));
        File.Delete(marker);
        Reject(() => LocalVehicleData.ValidateNativeBinding(root, sha));
    });
    private static void AddInventory(string folder, params string[] extras)
    {
        Directory.CreateDirectory(folder);
        foreach (string file in new[] { "local-profile.json", "virtualcar.ini", "VirtualCarJ2534.dll",
                     "candidate.sha256", "configuration.json" }.Concat(extras))
            File.WriteAllText(Path.Combine(folder, file), "synthetic");
    }
    private static void Test22() => WithFolder((root, folder) =>
    {
        AddInventory(folder);
        LocalVehicleData.ValidateInventory(folder, "vc094b-local-profile-v1");
        File.WriteAllText(Path.Combine(folder, "configuration-options.json"), "synthetic");
        LocalVehicleData.ValidateInventory(folder, "vc094d-local-profile-v2");
        File.WriteAllText(Path.Combine(folder, "configuration-references.json"), "synthetic");
        LocalVehicleData.ValidateInventory(folder, "vc094d2-local-profile-v3");
    });
    private static void Test23() => WithFolder((root, folder) =>
    {
        AddInventory(folder, "configuration-options.json");
        Reject(() => LocalVehicleData.ValidateInventory(folder, "vc094d2-local-profile-v3"));
        File.Delete(Path.Combine(folder, "virtualcar.ini"));
        Reject(() => LocalVehicleData.ValidateInventory(folder, "vc094d-local-profile-v2"));
    });
    private static void Test24() => WithFolder((root, folder) =>
    {
        AddInventory(folder, "configuration-options.json", "configuration-references.json");
        const string schema = "vc094d2-local-profile-v3";
        foreach (string extra in new[] { ".local-profile.json.pending", "unknown.txt" })
        {
            string path = Path.Combine(folder, extra);
            File.WriteAllText(path, "preserve");
            Reject(() => LocalVehicleData.ValidateInventory(folder, schema));
            Require(File.ReadAllText(path) == "preserve");
            File.Delete(path);
        }
        string nested = Path.Combine(folder, "configuration.json");
        File.Delete(nested);
        Directory.CreateDirectory(nested);
        Reject(() => LocalVehicleData.ValidateInventory(folder, schema));
    });
}
