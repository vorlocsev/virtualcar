using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class NativeDiagnosticJournalChecks
{
    private static NativeTraceRow Row(string data, bool tx = true, uint? protocol = 6,
        uint? flags = 0, uint? id = 0x7E0, bool truncated = false) =>
        new(1, "fixture.exe", tx ? NativeTraceDirection.Tx : NativeTraceDirection.Rx,
            1, protocol, flags, 500000, 1, id, data, truncated);
    private static DiagnosticEntry Decode(string data, bool tx = true) =>
        NativeDiagnosticJournal.Classify(Row(data, tx));
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC085 single DID request and response", () => Check(() =>
        {
            var req = Decode("22 F1 90");
            var rx = Decode("62 F1 90 41", false);
            Require(req.Kind == DiagnosticKind.Request && req.Service == 0x22 && req.Did == 0xF190);
            Require(rx.Kind == DiagnosticKind.Positive && rx.Service == 0x22 && rx.Did == 0xF190);
        })),
        ("VC085 NRC and response pending", () => Check(() =>
        {
            foreach (string code in new[] { "11", "31", "33", "78" })
            {
                var e = Decode("7F 22 " + code, false);
                Require(e.Kind == DiagnosticKind.Negative && e.Service == 0x22 && e.Did is null &&
                    e.Nrc == Convert.ToByte(code, 16));
            }
        })),
        ("VC085 non-DID supported services", () => Check(() =>
        {
            Require(Decode("19 02 FF").Service == 0x19);
            Require(Decode("59 02 20", false).Kind == DiagnosticKind.Positive);
            Require(Decode("10 03").Kind == DiagnosticKind.Request);
            Require(Decode("50 03 00 32 01 F4", false).Kind == DiagnosticKind.Positive);
            Require(Decode("3E 80").Kind == DiagnosticKind.Request);
            Require(Decode("7E 00", false).Kind == DiagnosticKind.Positive);
            Require(Decode("09 02").Service == 9);
            Require(Decode("49 02 01 " + string.Join(" ", Enumerable.Repeat("41", 17)), false).Kind == DiagnosticKind.Positive);
        })),
        ("VC085 CAN and absent context remain unknown", () => Check(() =>
        {
            foreach (var r in new[] { Row("22 F1 90", protocol: 5), Row("22 F1 90", protocol: null),
                Row("22 F1 90", flags: null), Row("22 F1 90", id: null), Row("22 F1 90", id: 0x18DA50F1) })
                Require(NativeDiagnosticJournal.Classify(r).Kind == DiagnosticKind.Unclassified);
            Require(NativeDiagnosticJournal.Classify(Row("22 F1 90", flags: 0x140, id: 0x18DA50F1)).Did == 0xF190);
        })),
        ("VC085 start indication not positive response", () => Check(() =>
        {
            Require(NativeDiagnosticJournal.Classify(Row("", false, flags: 2)).Kind == DiagnosticKind.Indication);
            Require(NativeDiagnosticJournal.Classify(Row("62 F1 90 41", false, flags: 2)).Kind == DiagnosticKind.Unclassified);
            Require(NativeDiagnosticJournal.Classify(Row("62 F1 90 41", false, flags: 1)).Kind == DiagnosticKind.Unclassified);
        })),
        ("VC085 malformed, truncated and unsupported data", () => Check(() =>
        {
            foreach (string data in new[] { "22", "22 F1", "22 F1 90 F1 87", "22 GG 90", "CB 46 B9 FB" })
                Require(Decode(data).Kind == DiagnosticKind.Unclassified);
            foreach (string data in new[] { "62 F1 90", "7F 22", "7F 22 31 00", "67 01 42" })
                Require(Decode(data, false).Kind == DiagnosticKind.Unclassified);
            Require(NativeDiagnosticJournal.Classify(Row("62 F1 90 41", false, truncated: true)).Kind == DiagnosticKind.Unclassified);
        })),
        ("VC085 protected service request is observation only", () => Check(() =>
        {
            Require(Decode("27 01").Kind == DiagnosticKind.Request);
            Require(Decode("7F 27 33", false).Nrc == 0x33);
            Require(Decode("67 01", false).Kind == DiagnosticKind.Unclassified);
        })),
        ("VC085 independent snapshot counts no pairing", () => Check(() =>
        {
            var s = NativeDiagnosticJournal.Summarize(new[] { Decode("22 F1 90"),
                Decode("62 F1 87 41", false), Decode("7F 22 78", false),
                NativeDiagnosticJournal.Classify(Row("", false, flags: 2)), Decode("FF") });
            Require(s == new DiagnosticSummary(1, 1, 1, 1, 1));
        }))
    ];
    private static Task Check(Action a) { a(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
}
