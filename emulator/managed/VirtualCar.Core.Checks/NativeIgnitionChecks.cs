using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class NativeIgnitionChecks
{
    private const string Ggd = "[Diagnostics]\r\nEnableGGDCemLab=1\r\n";
    private const string Flag = "[B3A157_IgnitionLab]\r\nEnabled=1\r\nA45FRawByte=07\r\n";
    private static byte[] B(string s) => Encoding.Latin1.GetBytes(s);
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC082 default baseline", () => Check(() =>
        {
            var p = NativeIgnitionPlan.Inspect(B(Ggd));
            Require(p.CanApply && p.ExpectedRaw == "04");
        })),
        ("VC082 exact candidate", () => Check(() =>
        {
            var p = NativeIgnitionPlan.Inspect(B(Ggd + Flag));
            Require(p.CanApply && p.ExpectedRaw == "07");
        })),
        ("VC082 GGD prerequisite", () => Check(() =>
        {
            Require(!NativeIgnitionPlan.Inspect(B(Flag)).CanApply);
            Expect<InvalidOperationException>(() => NativeIgnitionPlan.Build(B(Flag), NativeIgnitionSelection.Baseline));
        })),
        ("VC082 unsupported raw and duplicate refuse", () => Check(() =>
        {
            foreach (string bad in new[] { Flag.Replace("07", "08"), Flag + Flag,
                Flag.Replace("A45FRawByte=07", ""), Flag + "Enabled=0\r\n" })
                Expect<InvalidDataException>(() => NativeIgnitionPlan.Inspect(B(Ggd + bad)));
        })),
        ("VC082 scoped byte change and baseline restore", () => Check(() =>
        {
            string source = Ggd + Flag + "[Vehicle]\r\nVIN=PRIVATE_TEST\r\n; café\r\n";
            byte[] edited = NativeIgnitionPlan.Build(B(source), NativeIgnitionSelection.Baseline);
            Require(Encoding.Latin1.GetString(edited) == source.Replace("Enabled=1", "Enabled=0"));
            Require(NativeIgnitionPlan.Build(edited, NativeIgnitionSelection.PositionIICandidate).SequenceEqual(B(source)));
        })),
        ("VC082 inserts only required keys", () => Check(() =>
        {
            byte[] after = NativeIgnitionPlan.Build(B(Ggd), NativeIgnitionSelection.PositionIICandidate);
            Require(after.SequenceEqual(B(Ggd + Flag)));
        })),
        ("VC082 stale digest blocks write", () => WithProfile((path, before) =>
        {
            Expect<InvalidOperationException>(() => NativeIgnitionPlan.Apply(path, new string('0', 64),
                NativeIgnitionSelection.PositionIICandidate));
            Require(File.ReadAllBytes(path).SequenceEqual(before));
        })),
        ("VC082 exact backup and guarded undo", () => WithProfile((path, before) =>
        {
            var applied = NativeIgnitionPlan.Apply(path, NativeEcmScenarioApply.Digest(before),
                NativeIgnitionSelection.PositionIICandidate);
            Require(applied.Changed && File.ReadAllBytes(applied.BackupPath!).SequenceEqual(before));
            var result = NativeEcmScenarioApply.Restore(path, applied.BackupPath!,
                applied.Sha256, NativeEcmScenarioApply.Digest(before));
            Require(result.Changed && File.ReadAllBytes(path).SequenceEqual(before));
        }))
    ];
    private static Task Check(Action a) { a(); return Task.CompletedTask; }
    private static Task WithProfile(Action<string, byte[]> a)
    {
        string dir = Path.Combine(Path.GetTempPath(), "VC082-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            string path = Path.Combine(dir, "virtualcar.ini");
            byte[] before = B(Ggd);
            File.WriteAllBytes(path, before);
            a(path, before);
            return Task.CompletedTask;
        }
        finally { Directory.Delete(dir, recursive: true); }
    }
    private static void Expect<T>(Action a) where T : Exception
    {
        try { a(); } catch (T) { return; }
        throw new InvalidOperationException("Expected " + typeof(T).Name);
    }
    private static void Require(bool value) { if (!value) throw new InvalidOperationException(); }
}
