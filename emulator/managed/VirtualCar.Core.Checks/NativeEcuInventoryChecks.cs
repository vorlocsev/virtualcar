using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class NativeEcuInventoryChecks
{
    private static IReadOnlyList<NativeEcuSlot> Read(string ini) => NativeEcuInventory.Inspect(Encoding.Latin1.GetBytes(ini));
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC083 native defaults marked", () => Check(() =>
        {
            var slots = Read("[Vehicle]\nVIN=PRIVATE_TEST\n");
            Require(slots.Count == 2 && slots[0].RequestId == 0x7E0 && slots[1].ResponseId == 0x72E);
            Require(slots.All(x => x.State == EcuRouteState.DefaultsUsed && x.PartNumber is null));
        })),
        ("VC083 configured route and identity text", () => Check(() =>
        {
            var s = Read("[Vehicle]\nECUCount=1\n[ECU0]\nRequestId=18DA50F1\nResponseId=18DAF150\nExpectedBaud=500000\nPartNumber=LAB\nSoftware=TEST\n").Single();
            Require(s.State == EcuRouteState.Configured && s.RequestId == 0x18DA50F1 && s.ExpectedBaud == 500000 && s.PartNumber == "LAB");
        })),
        ("VC083 32 slot bound and extended missing routes", () => Check(() =>
        {
            var slots = Read("[Vehicle]\nECUCount=32\n[ECU31]\nRequestId=18DA50F1\nResponseId=18DAF150\n");
            Require(slots.Count == 32 && slots[8].State == EcuRouteState.Invalid && slots[31].RequestId == 0x18DA50F1);
        })),
        ("VC083 duplicate requests flagged", () => Check(() =>
        {
            var slots = Read("[Vehicle]\nECUCount=3\n");
            Require(slots[0].State == EcuRouteState.DuplicateRequest && slots[2].State == EcuRouteState.DuplicateRequest);
        })),
        ("VC083 malformed route and overflow not inferred", () => Check(() =>
        {
            foreach (string id in new[] { "bogus", "FFFFFFFFF", "20000000" })
                Require(Read("[Vehicle]\nECUCount=1\n[ECU0]\nRequestId=" + id + "\n").Single().State == EcuRouteState.Invalid);
            Require(Read("[Vehicle]\nECUCount=1\n[ECU0]\nExpectedBaud=bad\n").Single().State == EcuRouteState.Invalid);
        })),
        ("VC083 functional address marked separately", () => Check(() =>
            Require(Read("[Vehicle]\nECUCount=1\n[ECU0]\nRequestId=7DF\n").Single().State == EcuRouteState.FunctionalRequest))),
        ("VC083 duplicate settings and invalid count rejected", () => Check(() =>
        {
            foreach (string s in new[] { "[Vehicle]\nECUCount=33", "[Vehicle]\nECUCount=0", "[Vehicle]\nECUCount=2\necuCount=1",
                "[ECU0]\nRequestId=7E0\n[ecu0]\nResponseId=7E8" })
                Expect(() => Read(s));
        })),
        ("VC083 bounded input and nonrepresentable text", () => Check(() =>
        {
            Expect(() => NativeEcuInventory.Inspect(new byte[1024 * 1024 + 1]));
            var s = Read("[Vehicle]\nECUCount=1\n[ECU0]\nPartNumber=" + new string('X', 48) + "\nSoftware=\"quoted\"").Single();
            Require(s.PartNumber is null && s.Software is null);
        }))
    ];
    private static Task Check(Action a) { a(); return Task.CompletedTask; }
    private static void Expect(Action a)
    {
        try { a(); } catch (InvalidDataException) { return; }
        throw new InvalidOperationException("Expected invalid profile.");
    }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
}
