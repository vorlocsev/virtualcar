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
        ("VC094B 08 reject unpinned simulator profile", () => Run(Test08))
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
}
