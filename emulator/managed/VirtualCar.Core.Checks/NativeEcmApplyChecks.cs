using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class NativeEcmApplyChecks
{
    private const string Base = "[B3A309_EcmLiveDataLab]\r\nEnabled=1\r\n";
    private const string Static = "[B3A316_EcmScenarioLab]\r\nEnabled=1\r\nState=0\r\n";
    private const string Dynamic = "[B3A329_DynamicEcmLab]\r\nEnabled=0\r\n";
    private static byte[] Bytes(string text) => Encoding.Latin1.GetBytes(text);
    private static string Text(byte[] bytes) => Encoding.Latin1.GetString(bytes);
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC080 only target digits change", () => Check(() =>
        {
            string source = Base + "[Vehicle]\r\nVIN=PRIVATE_TEST\r\n; café\r\n" +
                "[B3A316_EcmScenarioLab]\r\nEnabled = 0  \r\nState=0\r\nUnknown=keep\r\n" + Dynamic;
            Require(Text(NativeEcmScenarioApply.Build(Bytes(source), EcmScenario.WarmIdle)) ==
                source.Replace("Enabled = 0  ", "Enabled = 1  ").Replace("State=0", "State=4"));
        })),
        ("VC080 inserts missing sections without changing prefix", () => Check(() =>
        {
            string source = Base + "[Other]\r\nKeep=1";
            var result = NativeEcmScenarioApply.Build(Bytes(source), EcmScenario.Cranking);
            Require(Text(result).StartsWith(source + "\r\n", StringComparison.Ordinal));
            Require(NativeEcmScenarioPlan.Inspect(result).Selection == EcmScenario.Cranking);
        })),
        ("VC080 fills missing keys in LF section", () => Check(() =>
        {
            string source = "[B3A309_EcmLiveDataLab]\nEnabled=1\n[B3A316_EcmScenarioLab]\n;keep\n[Other]\nX=1\n";
            string result = Text(NativeEcmScenarioApply.Build(Bytes(source), EcmScenario.ColdIdle));
            Require(result.Contains(";keep\nEnabled=1\nState=2\n[Other]\nX=1\n") && !result.Contains('\r'));
        })),
        ("VC080 missing gates refuse modification", () => Check(() =>
        {
            Expect<InvalidOperationException>(() => NativeEcmScenarioApply.Build(Bytes("[Other]\nX=1"), EcmScenario.WarmIdle));
            Expect<InvalidOperationException>(() => NativeEcmScenarioApply.Build(Bytes(Base), EcmScenario.Dynamic));
        })),
        ("VC080 malformed section and duplicate reject", () => Check(() =>
        {
            Expect<InvalidDataException>(() => NativeEcmScenarioApply.Build(Bytes(Base + Static + Static), EcmScenario.WarmIdle));
            Expect<InvalidDataException>(() => NativeEcmScenarioApply.Build(Bytes(Base + "[ B3A316_EcmScenarioLab ]\nEnabled=1\nState=0\n"), EcmScenario.WarmIdle));
        })),
        ("VC080 exact backup and verified replacement", () => WithFile((path, before) =>
        {
            var result = NativeEcmScenarioApply.Apply(path, NativeEcmScenarioApply.Digest(before), EcmScenario.WarmIdle);
            Require(result.Changed && result.BackupPath is not null);
            Require(File.ReadAllBytes(result.BackupPath!).AsSpan().SequenceEqual(before));
            Require(NativeEcmScenarioApply.Digest(File.ReadAllBytes(path)) == result.Sha256);
            Require(NativeEcmScenarioPlan.Inspect(File.ReadAllBytes(path)).Selection == EcmScenario.WarmIdle);
            Require(Directory.GetFiles(Path.GetDirectoryName(path)!).Length == 2);
        })),
        ("VC080 stale digest prevents any write", () => WithFile((path, before) =>
        {
            Expect<InvalidOperationException>(() => NativeEcmScenarioApply.Apply(path, new string('0', 64), EcmScenario.WarmIdle));
            Require(File.ReadAllBytes(path).AsSpan().SequenceEqual(before));
            Require(Directory.GetFiles(Path.GetDirectoryName(path)!).Length == 1);
        })),
        ("VC080 no-op creates no backup", () => WithFile((path, before) =>
        {
            var result = NativeEcmScenarioApply.Apply(path, NativeEcmScenarioApply.Digest(before), EcmScenario.Stationary);
            Require(!result.Changed && result.BackupPath is null && File.ReadAllBytes(path).AsSpan().SequenceEqual(before));
            Require(Directory.GetFiles(Path.GetDirectoryName(path)!).Length == 1);
        }))
    ];
    private static Task Check(Action action) { action(); return Task.CompletedTask; }
    private static Task WithFile(Action<string, byte[]> action)
    {
        string dir = Path.Combine(Path.GetTempPath(), "VC080-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            string path = Path.Combine(dir, "virtualcar.ini");
            byte[] before = Bytes(Base + Static + Dynamic);
            File.WriteAllBytes(path, before);
            action(path, before);
            return Task.CompletedTask;
        }
        finally { Directory.Delete(dir, recursive: true); }
    }
    private static void Expect<T>(Action action) where T : Exception
    {
        try { action(); }
        catch (T) { return; }
        throw new InvalidOperationException("Expected " + typeof(T).Name);
    }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
}
