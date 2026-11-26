using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class BuiltInVehicleChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC094A 01 three distinct built-in profiles", () => Run(Test01)),
        ("VC094A 02 P2 baseline remains silent for unknown D2", () => Run(Test02)),
        ("VC094A 03 generic synthetic inventory", () => Run(Test03)),
        ("VC094A 04 historical demonstration is explicitly labelled", () => Run(Test04)),
        ("VC094A 05 embedded data returned as independent copy", () => Run(Test05)),
        ("VC094A 06 exact package profile identity", () => Run(Test06)),
        ("VC094A 07 reject unknown and traversal profile IDs", () => Run(Test07)),
        ("VC094A 08 separate native package paths", () => Run(Test08))
    ];
    private static Task Run(Action action) { action(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
    private static string Text(string id) => Encoding.Latin1.GetString(BuiltInVehicles.ReadProfile(id));
    private static void Reject(Action action)
    {
        try { action(); }
        catch (ArgumentException) { return; }
        catch (InvalidDataException) { return; }
        throw new InvalidOperationException("Expected rejection");
    }
    private static void Test01()
    {
        Require(BuiltInVehicles.All.Count == 3 && BuiltInVehicles.All.Select(p => p.Id).Distinct().Count() == 3);
        Require(BuiltInVehicles.All.Select(p => BuiltInVehicles.ProfileSha(p.Id)).Distinct().Count() == 3);
        Require(BuiltInVehicles.All.All(p => p.Vin == "YV1CZ0002A0000001"));
    }
    private static void Test02()
    {
        string text = Text("p2");
        Require(text.Contains("StrictRouting = 1") && text.Split("B9FBFrameCount=0").Length == 3);
        Require(!text.Contains("B9FBFrame0 ="));
    }
    private static void Test03()
    {
        var slots = NativeEcuInventory.Inspect(BuiltInVehicles.ReadProfile("obd"));
        Require(slots.Count == 2 && slots[0].RequestId == 0x7e0 && slots[1].RequestId == 0x726);
    }
    private static void Test04()
    {
        var profile = BuiltInVehicles.All.Single(p => p.HistoricalDemo);
        Require(profile.Id == "p2-vin-demo" && profile.DescriptionEn.Contains("not a verified XC90 V8"));
        Require(Text(profile.Id).Contains("historical_public_2005_fixture_with_replaced_VIN") &&
            Text(profile.Id).Contains("B9FBFrameCount = 13"));
    }
    private static void Test05()
    {
        byte[] a = BuiltInVehicles.ReadProfile("p2");
        byte[] b = BuiltInVehicles.ReadProfile("p2");
        a[0] ^= 0xff;
        Require(!a.SequenceEqual(b) && b.SequenceEqual(BuiltInVehicles.ReadProfile("p2")));
    }
    private static void Test06()
    {
        byte[] bytes = BuiltInVehicles.ReadProfile("p2");
        Require(BuiltInVehicles.MatchesProfile("p2", bytes));
        Require(!BuiltInVehicles.MatchesProfile("obd", bytes));
        bytes[^1] ^= 1;
        Require(!BuiltInVehicles.MatchesProfile("p2", bytes));
    }
    private static void Test07()
    {
        foreach (string id in new[] { "", "../p2", "P2", "private" })
        {
            Reject(() => BuiltInVehicles.ReadProfile(id));
            Reject(() => BuiltInVehicles.PackageLibrary(Path.GetTempPath(), id));
        }
        Reject(() => BuiltInVehicles.PackageLibrary("relative", "p2"));
    }
    private static void Test08()
    {
        string root = Path.GetFullPath(Path.Combine(Path.GetTempPath(), "VC094"));
        var paths = BuiltInVehicles.All.Select(p => BuiltInVehicles.PackageLibrary(root, p.Id)).ToArray();
        Require(paths.Distinct().Count() == 3);
        Require(paths.All(p => Path.GetFileName(p) == "VirtualCarJ2534.dll"));
        Require(!BuiltInVehicles.IsNativePathSupported("relative"));
        Require(!BuiltInVehicles.IsNativePathSupported(Path.Combine(root, "машина")));
        Require(!BuiltInVehicles.IsNativePathSupported(Path.Combine(root, new string('a', 250))));
    }
}
