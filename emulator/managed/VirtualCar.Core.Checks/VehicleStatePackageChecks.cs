using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class VehicleStatePackageChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC094C 01 unsupported profile offers original only", () => Run(Test01)),
        ("VC094C 02 ignition requires existing GGD gate", () => Run(Test02)),
        ("VC094C 03 engine scenarios require existing ECM gate", () => Run(Test03)),
        ("VC094C 04 dynamic scenario requires all prerequisites", () => Run(Test04)),
        ("VC094C 05 scoped combined profile preserves original", () => Run(Test05)),
        ("VC094C 06 deterministic distinct paths", () => Run(Test06)),
        ("VC094C 07 prepare and reuse immutable state copy", () => Run(Test07)),
        ("VC094C 08 reject changed copy and source", () => Run(Test08))
    ];
    private static Task Run(Action action) { action(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
    private static void Reject(Action action)
    {
        try { action(); }
        catch (InvalidDataException) { return; }
        catch (InvalidOperationException) { return; }
        throw new Exception("Expected rejection.");
    }
    private const string OriginalText = "[Vehicle]\r\nVIN=LAB-ONLY\r\nECUCount=1\r\n";
    private const string Ggd = "[Diagnostics]\r\nEnableGGDCemLab=1\r\n";
    private const string Ecm = "[B3A309_EcmLiveDataLab]\r\nEnabled=1\r\n";
    private static byte[] B(string text) => Encoding.Latin1.GetBytes(text);
    private static VehicleStateChoice Combined => new(NativeIgnitionSelection.PositionIICandidate, EcmScenario.WarmIdle);
    private static byte[] Baseline => B(OriginalText + Ggd + Ecm);

    private static void Test01()
    {
        var bytes = B(OriginalText);
        Require(VehicleStatePackages.Ignitions(bytes).Count == 1 && VehicleStatePackages.Engines(bytes).Count == 1);
        Require(VehicleStatePackages.Build(bytes, VehicleStateChoice.Original).SequenceEqual(bytes));
        Reject(() => VehicleStatePackages.Build(bytes, Combined));
    }
    private static void Test02()
    {
        byte[] bytes = B(OriginalText + Ggd);
        Require(VehicleStatePackages.Ignitions(bytes).Count == 3);
        var result = VehicleStatePackages.Build(bytes, new(NativeIgnitionSelection.PositionIICandidate, null));
        Require(NativeIgnitionPlan.Inspect(result).Configured == NativeIgnitionSelection.PositionIICandidate);
        Require(VehicleStatePackages.Engines(bytes).Count == 1);
    }
    private static void Test03()
    {
        var bytes = B(OriginalText + Ecm);
        var options = VehicleStatePackages.Engines(bytes);
        Require(options.Count == 6 && options.Contains(EcmScenario.WarmIdle) && !options.Contains(EcmScenario.Dynamic));
        Reject(() => VehicleStatePackages.Build(bytes, new(null, EcmScenario.Dynamic)));
    }
    private static void Test04()
    {
        string text = OriginalText + Ggd + Ecm + string.Concat(new[]
        {
            "B3A314_EcmExtendedLiveLab", "B3A267_CurrentDataLab", "B3A319_BatterySyncLab",
            "B3A320_RemVoltageSyncLab", "B3A324_SupplyVoltageSyncLab"
        }.Select(s => "[" + s + "]\r\nEnabled=1\r\n"));
        var bytes = B(text);
        Require(VehicleStatePackages.Engines(bytes).Count == 7);
        var result = VehicleStatePackages.Build(bytes, new(null, EcmScenario.Dynamic));
        Require(NativeEcmScenarioPlan.Inspect(result).Selection == EcmScenario.Dynamic);
    }
    private static void Test05()
    {
        byte[] before = Baseline;
        byte[] after = VehicleStatePackages.Build(before, Combined);
        Require(before.SequenceEqual(Baseline));
        Require(after.SequenceEqual(NativeEcmScenarioApply.Build(
            NativeIgnitionPlan.Build(before, NativeIgnitionSelection.PositionIICandidate), EcmScenario.WarmIdle)));
        Require(Encoding.Latin1.GetString(after).StartsWith(OriginalText, StringComparison.Ordinal));
        Require(NativeIgnitionPlan.Inspect(after).Configured == NativeIgnitionSelection.PositionIICandidate);
        Require(NativeEcmScenarioPlan.Inspect(after).Selection == EcmScenario.WarmIdle);
    }
    private static void Test06()
    {
        string root = Path.GetTempPath();
        Require(VehicleStatePackages.Folder(root, VehicleStateChoice.Original) == LocalVehicleData.Folder(root));
        Require(VehicleStatePackages.Folder(root, Combined) != VehicleStatePackages.Folder(root, new(null, EcmScenario.WarmIdle)));
        Require(Path.GetFileName(VehicleStatePackages.Folder(root, Combined)) == "i1-e4");
        Reject(() => VehicleStatePackages.Folder(root, new((NativeIgnitionSelection)99, null)));
    }
    private static void WithPackage(Action<string, byte[], byte[], string> action)
    {
        string root = Path.Combine(Path.GetTempPath(), "VC094C-" + Guid.NewGuid().ToString("N"));
        string folder = LocalVehicleData.Folder(root); Directory.CreateDirectory(folder);
        byte[] before = Baseline, dll = "synthetic test bytes, never load"u8.ToArray();
        File.WriteAllBytes(Path.Combine(folder, "virtualcar.ini"), before);
        File.WriteAllBytes(Path.Combine(folder, "VirtualCarJ2534.dll"), dll);
        try { action(root, before, dll, NativeEcmScenarioApply.Digest(dll)); }
        finally { Directory.Delete(root, true); }
    }
    private static void Test07() => WithPackage((root, baseline, dll, sha) =>
    {
        Require(!VehicleStatePackages.Matches(root, Combined, baseline, sha));
        VehicleStatePackages.Prepare(root, Combined, baseline, sha);
        Require(VehicleStatePackages.Matches(root, Combined, baseline, sha));
        string folder = VehicleStatePackages.Folder(root, Combined);
        var before = File.ReadAllBytes(Path.Combine(folder, "virtualcar.ini"));
        VehicleStatePackages.Prepare(root, Combined, baseline, sha);
        Require(before.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "virtualcar.ini"))));
        Require(File.ReadAllBytes(Path.Combine(LocalVehicleData.Folder(root), "virtualcar.ini")).SequenceEqual(baseline));
        Require(File.ReadAllBytes(Path.Combine(LocalVehicleData.Folder(root), "VirtualCarJ2534.dll")).SequenceEqual(dll));
    });
    private static void Test08() => WithPackage((root, baseline, dll, sha) =>
    {
        Reject(() => VehicleStatePackages.Prepare(root, Combined, baseline, new string('0', 64)));
        VehicleStatePackages.Prepare(root, Combined, baseline, sha);
        string path = Path.Combine(VehicleStatePackages.Folder(root, Combined), "virtualcar.ini");
        File.AppendAllText(path, ";changed");
        byte[] changed = File.ReadAllBytes(path);
        Require(!VehicleStatePackages.Matches(root, Combined, baseline, sha));
        Reject(() => VehicleStatePackages.Prepare(root, Combined, baseline, sha));
        Require(changed.SequenceEqual(File.ReadAllBytes(path)));
        File.AppendAllText(Path.Combine(LocalVehicleData.Folder(root), "virtualcar.ini"), ";changed");
        Reject(() => VehicleStatePackages.Prepare(root, new(null, EcmScenario.ColdIdle), baseline, sha));
    });
}
