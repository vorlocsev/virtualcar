using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class NativeEcmScenarioChecks
{
    private const string Baseline = "[B3A309_EcmLiveDataLab]\nEnabled=1\n";
    private const string Ready = Baseline +
        "[B3A314_EcmExtendedLiveLab]\nEnabled=1\n[B3A267_CurrentDataLab]\nEnabled=1\n" +
        "[B3A319_BatterySyncLab]\nEnabled=1\n[B3A320_RemVoltageSyncLab]\nEnabled=1\n" +
        "[B3A324_SupplyVoltageSyncLab]\nEnabled=1\n[Diagnostics]\nEnableGGDCemLab=1\n";
    private static EcmScenarioPlan Inspect(string text, EcmScenario? selection = null) =>
        NativeEcmScenarioPlan.Inspect(Encoding.ASCII.GetBytes(text), selection);
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC079 default gates remain off", () => Check(() =>
        {
            var p = Inspect("[Vehicle]\nBatteryMv=12500\n");
            Require(!p.CanApply && p.Selection == EcmScenario.Stationary);
        })),
        ("VC079 five static states", () => Check(() =>
        {
            for (int i = 0; i < 5; i++)
            {
                var p = Inspect(Baseline + "[B3A316_EcmScenarioLab]\nEnabled=1\nState=" + i + "\n");
                Require(p.Selection == (EcmScenario)i && p.CanApply && p.IniPatch.Contains("State=" + i + "\r\n"));
            }
        })),
        ("VC079 disabled scenario defaults to zero", () => Check(() =>
            Require(Inspect(Baseline + "[B3A316_EcmScenarioLab]\nEnabled=0\nState=4\n").Selection == EcmScenario.Stationary))),
        ("VC079 dynamic requires every gate", () => Check(() =>
        {
            Require(Inspect(Ready, EcmScenario.Dynamic).CanApply);
            foreach (string section in new[] { "B3A309_EcmLiveDataLab", "B3A314_EcmExtendedLiveLab",
                "B3A267_CurrentDataLab", "B3A319_BatterySyncLab", "B3A320_RemVoltageSyncLab",
                "B3A324_SupplyVoltageSyncLab" })
                Require(!Inspect(Ready.Replace("[" + section + "]\nEnabled=1", "[" + section + "]\nEnabled=0"), EcmScenario.Dynamic).CanApply);
            Require(!Inspect(Ready.Replace("EnableGGDCemLab=1", "EnableGGDCemLab=0"), EcmScenario.Dynamic).CanApply);
        })),
        ("VC079 dynamic precedence only with prerequisites", () => Check(() =>
        {
            const string setting = "[B3A329_DynamicEcmLab]\nEnabled=1\n[B3A316_EcmScenarioLab]\nEnabled=1\nState=4\n";
            Require(Inspect(Ready + setting).Selection == EcmScenario.Dynamic);
            Require(Inspect(Baseline + setting).Selection == EcmScenario.WarmIdle);
        })),
        ("VC079 patch restricted to two sections", () => Check(() =>
        {
            var p = Inspect(Ready + "[Vehicle]\nVIN=PRIVATE_TEST\n", EcmScenario.Dynamic);
            Require(p.IniPatch == "[B3A316_EcmScenarioLab]\r\nEnabled=1\r\nState=0\r\n\r\n[B3A329_DynamicEcmLab]\r\nEnabled=1\r\n");
        })),
        ("VC079 ambiguous configuration rejected", () => Check(() =>
        {
            foreach (string input in new[] { Baseline + Baseline,
                Baseline + "Enabled=0\n", "[B3A309_EcmLiveDataLab]\nEnabled=\"1\"\n",
                "[B3A316_EcmScenarioLab]\nState=5\n", "[broken\n" })
            {
                try { Inspect(input); }
                catch (InvalidDataException) { continue; }
                throw new InvalidOperationException("Ambiguous profile accepted.");
            }
        })),
        ("VC079 bounded input and invalid selector", () => Check(() =>
        {
            try { NativeEcmScenarioPlan.Inspect(new byte[1024 * 1024 + 1]); throw new Exception(); }
            catch (InvalidDataException) { }
            try { Inspect(Baseline, (EcmScenario)99); throw new Exception(); }
            catch (ArgumentOutOfRangeException) { }
        }))
    ];
    private static Task Check(Action test) { test(); return Task.CompletedTask; }
    private static void Require(bool condition) { if (!condition) throw new InvalidOperationException(); }
}
