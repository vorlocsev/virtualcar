using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class NativeCanTraceChecks
{
    private const string A = "[PID=00000001 client.exe] ";
    private const string B = "[PID=00000002 client.exe] ";
    private const string Tx = "TX context channel/protocol/flags/baud/time-us (BE) 00 00 00 01 00 00 00 05 00 00 01 00 00 07 A1 20 FF FF FF FF ";
    private const string Rx = "RX context channel/protocol/status/baud/time-us (BE) 00 00 00 02 00 00 00 06 00 00 00 00 00 01 E8 48 00 00 00 01 ";
    private const string Request = "TX (app request) 18 DA 50 F1 22 F1 90 ";
    private const string Reply = "PassThruReadMsgs -> delivered 18 DA F1 50 62 F1 90 ";
    private static NativeTraceSnapshot Parse(string text, bool tail = false) =>
        NativeCanTrace.Parse(Encoding.Latin1.GetBytes(text), tail);
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC084 context and address decoding", () => Check(() =>
        {
            var row = Parse(A + Tx + "\r\n" + A + Request + "\r\n").Rows.Single();
            Require(row.Direction == NativeTraceDirection.Tx && row.Channel == 1 && row.Protocol == 5 &&
                row.Baud == 500000 && row.Flags == 256 && row.TimeUs == uint.MaxValue &&
                row.CanId == 0x18DA50F1 && row.DataHex == "22 F1 90");
        })),
        ("VC084 interleaved clients never share context", () => Check(() =>
        {
            var rows = Parse(A + Tx + "\n" + B + Rx + "\n" + A + Request + "\n" + B + Reply + "\n").Rows;
            Require(rows.Count == 2 && rows[0].Pid == 1 && rows[0].Channel == 1 &&
                rows[1].Pid == 2 && rows[1].Channel == 2 && rows[1].Baud == 125000);
        })),
        ("VC084 stale wrong-direction and missing context", () => Check(() =>
        {
            var rows = Parse(A + Tx + "\n" + A + "unrelated\n" + A + Request + "\n" +
                A + Tx + "\n" + A + Reply + "\n" + A + Request + "\n").Rows;
            Require(rows.Count == 3 && rows.All(x => x.Channel is null && x.CanId is null));
            Require(rows[0].DataHex.StartsWith("18 DA 50 F1", StringComparison.Ordinal));
        })),
        ("VC084 no duplicate queued RX or malformed payload", () => Check(() =>
        {
            var rows = Parse(A + "RX (simulated) 18 DA F1 50 62\n" + A +
                "RX START_OF_MESSAGE (ISO15765) 18 DA F1 50\n" + A +
                "TX (app request) 00 GG 00 00\n" + A + Reply + "\n").Rows;
            Require(rows.Count == 1 && rows[0].Direction == NativeTraceDirection.Rx);
        })),
        ("VC084 partial head and tail excluded", () => Check(() =>
        {
            var rows = Parse(A + Request + "\n" + A + Reply + "\n" + A + Request, true);
            Require(rows.TailOnly && rows.Rows.Count == 1 && rows.Rows[0].Direction == NativeTraceDirection.Rx);
        })),
        ("VC084 possible native truncation", () => Check(() =>
        {
            string data = string.Join(" ", Enumerable.Repeat("00", 52));
            Require(Parse(A + "TX (app request) " + data + "\n").Rows.Single().PossibleTruncation);
            Require(Parse(A + "TX (app request) " + data + " 00\n").Rows.Count == 0);
        })),
        ("VC084 bounded newest rows", () => Check(() =>
        {
            string log = string.Concat(Enumerable.Repeat(A + Request + "\n", 501)) + B + Reply + "\n";
            var rows = Parse(log).Rows;
            Require(rows.Count == NativeCanTrace.MaxRows && rows[^1].Pid == 2);
        })),
        ("VC084 bounded shared file snapshot", () => Check(() =>
        {
            string dir = Path.Combine(Path.GetTempPath(), "VC084-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            try
            {
                string path = Path.Combine(dir, "fixture.log");
                File.WriteAllText(path, new string('x', NativeCanTrace.MaxBytes) + "\n" + A + Tx + "\n" + A + Request + "\n");
                var snapshot = NativeCanTrace.ReadFile(path);
                Require(snapshot.TailOnly && snapshot.Rows.Single().CanId == 0x18DA50F1);
            }
            finally { Directory.Delete(dir, recursive: true); }
        }))
    ];
    private static Task Check(Action test) { test(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
}
