using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class CemPreviewChecks
{
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC072 baseline 127 rows and locked fields", Baseline),
        ("VC072 valid edit, request and audit binding", Edit),
        ("VC072 blocked and topology review preserved", Audit),
        ("VC072 invalid edits never invoke transport", InvalidEdits),
        ("VC072 malformed or oversized response rejected", InvalidResponse),
        ("VC072 stale or inconsistent response rejected", StaleResponse),
        ("VC072 single-flight and clearing stale view", ViewState),
        ("VC072 cancellation and local path preflight", Cancel)
    ];

    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException("Preview check failed."); }
    private static async Task Fails<T>(Func<Task> f) where T : Exception
    {
        try { await f(); } catch (T) { return; }
        throw new InvalidOperationException("Expected " + typeof(T).Name);
    }

    private static JsonObject Fixture(bool edit = false, string status = "pass", bool topology = false)
    {
        int[] locked = [2,3,4,8,9,10,12,16,28,33,36,123];
        var rows = Enumerable.Range(0,130).Where(i => i is not (0 or 1 or 7)).Select(i =>
        {
            bool changed = edit && i == 65;
            bool isLocked = locked.Contains(i);
            return new
            {
                offset = i, name = "Synthetic field " + i, locked = isLocked,
                baseline_code = "01", baseline_text = "Synthetic  baseline",
                selected_code = changed ? "02" : "01",
                selected_text = changed ? "New value" : "Synthetic  baseline", changed,
                options = new[] { new { code = "02", as_text = "New value", selectable = !isLocked } }
            };
        }).ToArray();
        var edits = edit ? new[] { new { offset = 65, new_code = "02" } } : [];
        return JsonSerializer.SerializeToNode(new
        {
            schema = CemPreviewClient.Schema, rows,
            draft = new { edits },
            audit = new
            {
                status, topology_review_required = topology,
                policy = new
                {
                    errors = status == "blocked" ? new[] { "SYNTHETIC_ERROR" } : [],
                    warnings = status == "review" && !topology ? new[] { "SYNTHETIC_WARNING" } : []
                }
            },
            audit_sha256 = new string('a', 64), can_export = false, lab_only = true,
            vida_verified = false, oem_verified = false, physical_j2534_verified = false
        })!.AsObject();
    }
    private static byte[] Bytes(JsonNode n) => Encoding.UTF8.GetBytes(n.ToJsonString());

    private sealed class Fake : ICemPreviewTransport
    {
        public byte[] Reply = Bytes(Fixture());
        public byte[]? Last;
        public int Calls;
        public Func<CancellationToken, Task<byte[]>>? Handler;
        public Task<byte[]> PreviewAsync(byte[] request, CancellationToken token)
        {
            Calls++; Last = request;
            return Handler is null ? Task.FromResult(Reply) : Handler(token);
        }
    }

    private static async Task Baseline()
    {
        var f = new Fake();
        var r = await new CemPreviewClient(f).PreviewAsync([]);
        Require(r.Rows.Count == 127 && r.Rows.Count(x => x.Locked) == 12 && r.Rows.All(x => !x.Changed));
        Require(r.Rows[0].BaselineText == "Synthetic  baseline" && !r.CanExport && r.LabOnly);
    }

    private static async Task Edit()
    {
        var f = new Fake { Reply = Bytes(Fixture(edit: true)) };
        var r = await new CemPreviewClient(f).PreviewAsync([new(65,"02")]);
        Require(r.Rows.Single(x => x.Changed).SelectedCode == "02" && r.AuditSha256 == new string('a',64));
        using var req = JsonDocument.Parse(f.Last!);
        Require(req.RootElement.GetProperty("schema").GetString() == CemPreviewClient.Schema
            && req.RootElement.GetProperty("edits")[0].GetProperty("offset").GetInt32() == 65
            && req.RootElement.GetProperty("edits")[0].GetProperty("code").GetString() == "02");
    }

    private static async Task Audit()
    {
        var f = new Fake { Reply = Bytes(Fixture(status: "blocked")) };
        var c = new CemPreviewClient(f);
        Require((await c.PreviewAsync([])).Errors.Count == 1);
        f.Reply = Bytes(Fixture(status: "review", topology: true));
        Require((await c.PreviewAsync([])).TopologyReviewRequired);
        f.Reply = Bytes(Fixture(status: "review"));
        Require((await c.PreviewAsync([])).Warnings.Count == 1);
    }

    private static async Task InvalidEdits()
    {
        var f = new Fake();
        var c = new CemPreviewClient(f);
        foreach (CemEdit[] edits in new CemEdit[][] { [new(2,"02")], [new(0,"02")], [new(65,"ff")],
            [new(65,"FF")], [new(65,"02"),new(65,"03")] })
            await Fails<InvalidDataException>(() => c.PreviewAsync(edits));
        Require(f.Calls == 0);
    }

    private static async Task InvalidResponse()
    {
        var f = new Fake();
        var c = new CemPreviewClient(f);
        foreach (var bytes in new[] { Array.Empty<byte>(), new byte[CemPreviewClient.MaxResponseBytes+1],
            Encoding.UTF8.GetBytes("{"), Encoding.UTF8.GetBytes("{\"schema\":\"x\",\"schema\":\"y\"}") })
        {
            f.Reply = bytes;
            await Fails<InvalidDataException>(() => c.PreviewAsync([]));
        }
        var n = Fixture(); n["can_export"] = true; f.Reply = Bytes(n);
        await Fails<InvalidDataException>(() => c.PreviewAsync([]));
    }

    private static async Task StaleResponse()
    {
        var f = new Fake();
        var c = new CemPreviewClient(f);
        await Fails<InvalidDataException>(() => c.PreviewAsync([new(65,"02")]));
        var n = Fixture(); n["rows"]!.AsArray().RemoveAt(0); f.Reply = Bytes(n);
        await Fails<InvalidDataException>(() => c.PreviewAsync([]));
        n = Fixture(); n["audit"]!["status"] = "blocked"; f.Reply = Bytes(n);
        await Fails<InvalidDataException>(() => c.PreviewAsync([]));
    }

    private static async Task ViewState()
    {
        var f = new Fake();
        var v = new CemPreviewViewModel(new CemPreviewClient(f));
        await v.RefreshAsync([]);
        Require(v.Snapshot is not null && !v.IsBusy);
        var pending = new TaskCompletionSource<byte[]>(TaskCreationOptions.RunContinuationsAsynchronously);
        f.Handler = _ => pending.Task;
        var refresh = v.RefreshAsync([]);
        Require(v.IsBusy && v.Snapshot is null);
        await Fails<InvalidOperationException>(() => v.RefreshAsync([]));
        pending.SetResult([0]);
        await Fails<InvalidDataException>(() => refresh);
        Require(!v.IsBusy && v.Snapshot is null);
    }

    private static async Task Cancel()
    {
        var f = new Fake();
        var v = new CemPreviewViewModel(new CemPreviewClient(f));
        await v.RefreshAsync([]);
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        await Fails<OperationCanceledException>(() => v.RefreshAsync([], cts.Token));
        Require(v.Snapshot is null && !v.IsBusy && f.Calls == 1);
        await Fails<ArgumentException>(() => Task.Run(() => new CemPreviewProcessTransport("python", "vc071_view.py", ".")));
    }
}
