using System.Text.Json;
using System.Text.Json.Serialization;

namespace VirtualCar.Core;

public sealed record CemEdit(
    [property: JsonPropertyName("offset")] int Offset,
    [property: JsonPropertyName("code")] string Code);
public sealed record CemOption(string Code, string? Text, bool Selectable);
public sealed record CemRow(int Offset, string Name, string BaselineCode, string BaselineText,
    string SelectedCode, string SelectedText, bool Locked, bool Changed, IReadOnlyList<CemOption> Options);
public sealed record CemPreview(IReadOnlyList<CemRow> Rows, string Status, string AuditSha256,
    IReadOnlyList<string> Errors, IReadOnlyList<string> Warnings, bool TopologyReviewRequired)
{
    public bool CanExport => false;
    public bool LabOnly => true;
}

public interface ICemPreviewTransport
{
    Task<byte[]> PreviewAsync(byte[] request, CancellationToken cancellationToken);
}

public sealed class CemPreviewClient(ICemPreviewTransport transport)
{
    public const string Schema = "vc071-ui-preview-v1";
    public const int MaxResponseBytes = 4 * 1024 * 1024;
    private static readonly int[] Offsets = Enumerable.Range(0, 130)
        .Where(i => i is not (0 or 1 or 7)).ToArray();
    private static readonly HashSet<int> Locked = [2,3,4,8,9,10,12,16,28,33,36,123];

    private static InvalidDataException Invalid() => new("Invalid CEM preview contract.");
    private static void Require(bool condition) { if (!condition) throw Invalid(); }
    private static bool Hex(string? s, int length) => s is not null && s.Length == length &&
        s.All(c => c is >= '0' and <= '9' or >= 'A' and <= 'F');
    private static string Str(JsonElement e, string key) => e.GetProperty(key).GetString() ?? throw Invalid();

    public async Task<CemPreview> PreviewAsync(IEnumerable<CemEdit> edits, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(edits);
        var requested = new Dictionary<int, string>();
        foreach (var edit in edits)
        {
            Require(edit is not null && Offsets.Contains(edit.Offset) && !Locked.Contains(edit.Offset)
                && Hex(edit.Code, 2) && edit.Code != "FF" && requested.TryAdd(edit.Offset, edit.Code));
        }
        var request = JsonSerializer.SerializeToUtf8Bytes(new
        {
            schema = Schema,
            edits = requested.OrderBy(x => x.Key).Select(x => new CemEdit(x.Key, x.Value)).ToArray()
        });
        Require(request.Length <= 32768);
        cancellationToken.ThrowIfCancellationRequested();
        var bytes = await transport.PreviewAsync(request, cancellationToken).ConfigureAwait(false);
        cancellationToken.ThrowIfCancellationRequested();
        return Parse(bytes, requested);
    }

    private static void UniqueKeys(JsonElement e)
    {
        if (e.ValueKind == JsonValueKind.Object)
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in e.EnumerateObject())
            {
                Require(seen.Add(p.Name));
                UniqueKeys(p.Value);
            }
        }
        else if (e.ValueKind == JsonValueKind.Array)
            foreach (var item in e.EnumerateArray()) UniqueKeys(item);
    }

    private static IReadOnlyList<string> Strings(JsonElement e) =>
        Array.AsReadOnly(e.EnumerateArray().Select(x => x.GetString() ?? throw Invalid()).ToArray());

    private static CemPreview Parse(byte[] bytes, Dictionary<int, string> requested)
    {
        try
        {
            Require(bytes is not null && bytes.Length is > 0 and <= MaxResponseBytes);
            using var doc = JsonDocument.Parse(bytes!, new JsonDocumentOptions { MaxDepth = 48 });
            var root = doc.RootElement;
            UniqueKeys(root);
            Require(Str(root, "schema") == Schema && root.GetProperty("lab_only").GetBoolean()
                && !root.GetProperty("can_export").GetBoolean()
                && !root.GetProperty("vida_verified").GetBoolean()
                && !root.GetProperty("oem_verified").GetBoolean()
                && !root.GetProperty("physical_j2534_verified").GetBoolean());
            var hash = Str(root, "audit_sha256");
            Require(hash.Length == 64 && hash.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f'));
            var audit = root.GetProperty("audit");
            var status = Str(audit, "status");
            Require(status is "pass" or "review" or "blocked");
            var policy = audit.GetProperty("policy");
            var errors = Strings(policy.GetProperty("errors"));
            var warnings = Strings(policy.GetProperty("warnings"));
            var topology = audit.GetProperty("topology_review_required").GetBoolean();
            Require(status == (errors.Count > 0 ? "blocked" : warnings.Count > 0 || topology ? "review" : "pass"));

            var rows = new List<CemRow>();
            var seen = new HashSet<int>();
            foreach (var row in root.GetProperty("rows").EnumerateArray())
            {
                int offset = row.GetProperty("offset").GetInt32();
                Require(Offsets.Contains(offset) && seen.Add(offset));
                var baseline = Str(row, "baseline_code");
                var selected = Str(row, "selected_code");
                var oldText = Str(row, "baseline_text");
                var newText = Str(row, "selected_text");
                var locked = row.GetProperty("locked").GetBoolean();
                var changed = row.GetProperty("changed").GetBoolean();
                bool hasEdit = requested.TryGetValue(offset, out string? expected);
                Require(Hex(baseline, 2) && Hex(selected, 2) && locked == Locked.Contains(offset)
                    && changed == hasEdit && selected == (hasEdit ? expected : baseline)
                    && (!hasEdit ? newText == oldText : selected != baseline));
                var options = new List<CemOption>();
                foreach (var opt in row.GetProperty("options").EnumerateArray())
                {
                    var code = Str(opt, "code");
                    var selectable = opt.GetProperty("selectable").GetBoolean();
                    Require(Hex(code, 2) && (!selectable || (!locked && code != "FF")));
                    options.Add(new CemOption(code, opt.GetProperty("as_text").GetString(), selectable));
                }
                if (hasEdit)
                    Require(options.Count(x => x.Code == selected && x.Selectable && x.Text == newText) == 1);
                rows.Add(new CemRow(offset, Str(row, "name"), baseline, oldText, selected, newText,
                    locked, changed, options.AsReadOnly()));
            }
            Require(seen.SetEquals(Offsets));
            var draftEdits = root.GetProperty("draft").GetProperty("edits").EnumerateArray();
            var echoed = new Dictionary<int, string>();
            foreach (var e in draftEdits)
                Require(echoed.TryAdd(e.GetProperty("offset").GetInt32(), Str(e, "new_code")));
            Require(echoed.Count == requested.Count && requested.All(x => echoed.TryGetValue(x.Key, out var code) && code == x.Value));
            return new CemPreview(rows.OrderBy(r => r.Offset).ToList().AsReadOnly(), status, hash,
                errors, warnings, topology);
        }
        catch (Exception ex) when (ex is JsonException or KeyNotFoundException or FormatException or InvalidOperationException or ArgumentException)
        {
            throw Invalid();
        }
    }
}

/// <summary>Single-flight preview state. Failed or cancelled operations never retain a stale preview.</summary>
public sealed class CemPreviewViewModel(CemPreviewClient client)
{
    private int _busy;
    public bool IsBusy => Volatile.Read(ref _busy) != 0;
    public CemPreview? Snapshot { get; private set; }
    public async Task RefreshAsync(IEnumerable<CemEdit> edits, CancellationToken cancellationToken = default)
    {
        if (Interlocked.CompareExchange(ref _busy, 1, 0) != 0)
            throw new InvalidOperationException("CEM preview already in progress.");
        Snapshot = null;
        try
        {
            Snapshot = await client.PreviewAsync(edits, cancellationToken);
        }
        finally { Volatile.Write(ref _busy, 0); }
    }
}
