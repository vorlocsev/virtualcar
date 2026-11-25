using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class NativeEcmRestoreChecks
{
    private const string Source = "[B3A309_EcmLiveDataLab]\nEnabled=1\n[Vehicle]\nVIN=PRIVATE_TEST\n";
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC081 exact restore and recovery backup", () => WithProfile((path, original, applied) =>
        {
            byte[] active = File.ReadAllBytes(path);
            var restored = Restore(path, applied.BackupPath!);
            Require(restored.Changed && File.ReadAllBytes(path).SequenceEqual(original));
            Require(File.ReadAllBytes(restored.BackupPath!).SequenceEqual(active));
            Require(File.ReadAllBytes(applied.BackupPath!).SequenceEqual(original));
        })),
        ("VC081 undo restore", () => WithProfile((path, original, applied) =>
        {
            byte[] active = File.ReadAllBytes(path);
            var restored = Restore(path, applied.BackupPath!);
            Restore(path, restored.BackupPath!);
            Require(File.ReadAllBytes(path).SequenceEqual(active));
        })),
        ("VC081 unrelated changes refuse restoration", () => WithProfile((path, original, applied) =>
        {
            File.AppendAllText(path, "\n[Unrelated]\nKey=changed\n");
            byte[] active = File.ReadAllBytes(path);
            Expect<InvalidOperationException>(() => Restore(path, applied.BackupPath!));
            Require(File.ReadAllBytes(path).SequenceEqual(active));
            Require(Directory.GetFiles(Path.GetDirectoryName(path)!).Length == 2);
        })),
        ("VC081 stale active digest refuses restore", () => WithProfile((path, original, applied) =>
        {
            byte[] active = File.ReadAllBytes(path);
            Expect<InvalidOperationException>(() => NativeEcmScenarioApply.Restore(path, applied.BackupPath!,
                new string('0', 64), NativeEcmScenarioApply.Digest(original)));
            Require(File.ReadAllBytes(path).SequenceEqual(active));
        })),
        ("VC081 stale backup digest refuses restore", () => WithProfile((path, original, applied) =>
        {
            byte[] active = File.ReadAllBytes(path);
            Expect<InvalidOperationException>(() => NativeEcmScenarioApply.Restore(path, applied.BackupPath!,
                NativeEcmScenarioApply.Digest(active), new string('0', 64)));
            Require(File.ReadAllBytes(path).SequenceEqual(active));
        })),
        ("VC081 arbitrary filename refused", () => WithProfile((path, original, applied) =>
        {
            string other = Path.Combine(Path.GetDirectoryName(path)!, "other.bak");
            File.WriteAllBytes(other, original);
            Expect<InvalidDataException>(() => NativeEcmScenarioApply.ReadBackup(path, other));
        })),
        ("VC081 backup outside profile folder refused", () => WithProfile((path, original, applied) =>
        {
            string folder = Path.Combine(Path.GetDirectoryName(path)!, "other");
            Directory.CreateDirectory(folder);
            string other = Path.Combine(folder, Path.GetFileName(applied.BackupPath!));
            File.WriteAllBytes(other, original);
            Expect<InvalidDataException>(() => NativeEcmScenarioApply.ReadBackup(path, other));
        })),
        ("VC081 identical restore creates no backup", () => WithProfile((path, original, applied) =>
        {
            Restore(path, applied.BackupPath!);
            int count = Directory.GetFiles(Path.GetDirectoryName(path)!).Length;
            var result = Restore(path, applied.BackupPath!);
            Require(!result.Changed && result.BackupPath is null);
            Require(Directory.GetFiles(Path.GetDirectoryName(path)!).Length == count);
        }))
    ];
    private static NativeScenarioApplyResult Restore(string path, string backup) =>
        NativeEcmScenarioApply.Restore(path, backup,
            NativeEcmScenarioApply.Digest(NativeEcmScenarioApply.ReadProfile(path)),
            NativeEcmScenarioApply.Digest(NativeEcmScenarioApply.ReadBackup(path, backup)));

    private static Task WithProfile(Action<string, byte[], NativeScenarioApplyResult> action)
    {
        string dir = Path.Combine(Path.GetTempPath(), "VC081-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        try
        {
            string path = Path.Combine(dir, "virtualcar.ini");
            byte[] before = Encoding.ASCII.GetBytes(Source);
            File.WriteAllBytes(path, before);
            var result = NativeEcmScenarioApply.Apply(path, NativeEcmScenarioApply.Digest(before), EcmScenario.WarmIdle);
            action(path, before, result);
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
