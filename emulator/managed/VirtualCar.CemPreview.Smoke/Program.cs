using System.Security.Cryptography;
using VirtualCar.Core;

namespace VirtualCar.CemPreview.Smoke;

// Explicit owner-local acceptance only. Never used by automatic CI.
// No private data, paths, values, hashes or exception messages are printed.
internal static class Program
{
    private static readonly string[] Inputs =
    [
        "VC041-529.private.json",
        "VC0586-candidate.private.ini",
        "VC0586-vida-acceptance.private.json",
        "VC0586-catalog-coverage.private.json",
        "VC056-result.private.json",
        "VC0591-configuration-store.private.json",
        "VC046-XC90-V8-20261125-085427.private.json"
    ];

    private static void Require(bool ok)
    {
        if (!ok) throw new InvalidDataException("Smoke assertion failed.");
    }

    private static async Task Reject<T>(Func<Task> operation) where T : Exception
    {
        try { await operation(); }
        catch (T) { return; }
        throw new InvalidOperationException("Expected rejection.");
    }

    private static string[] Fingerprint(string directory) =>
        Inputs.Select(name =>
        {
            using var stream = File.OpenRead(Path.Combine(directory, name));
            return Convert.ToHexString(SHA256.HashData(stream));
        }).ToArray();

    private static async Task<int> Main(string[] args)
    {
        if (args.Length != 3 || args.Any(p => !Path.IsPathFullyQualified(p)))
        {
            Console.Error.WriteLine("Usage: <absolute-python-exe> <absolute-vc071_view.py> <absolute-private-data-directory>");
            return 2;
        }

        int passed = 0;
        string[]? before = null;
        string step = "preflight";
        bool unchanged = false;
        try
        {
            var transport = new CemPreviewProcessTransport(args[0], args[1], args[2]);
            var client = new CemPreviewClient(transport);
            var view = new CemPreviewViewModel(client);
            before = Fingerprint(args[2]);

            step = "01 real baseline";
            await view.RefreshAsync([]);
            var baseline = view.Snapshot ?? throw new InvalidDataException();
            Require(!view.IsBusy && baseline.Rows.Count == 127 &&
                baseline.Rows.Count(r => r.Locked) == 12 &&
                baseline.Rows.All(r => !r.Changed) &&
                baseline.LabOnly && !baseline.CanExport);
            Pass();

            step = "02 repeated baseline";
            var repeat = await client.PreviewAsync([]);
            Require(repeat.AuditSha256 == baseline.AuditSha256 &&
                repeat.Status == baseline.Status &&
                repeat.Rows.Select(r => (r.Offset, r.Name, r.BaselineCode, r.BaselineText))
                    .SequenceEqual(baseline.Rows.Select(r => (r.Offset, r.Name, r.BaselineCode, r.BaselineText))));
            Pass();

            step = "03 selectable edit";
            var choice = baseline.Rows.Where(r => !r.Locked)
                .SelectMany(r => r.Options.Where(o => o.Selectable && o.Code != r.BaselineCode)
                    .Select(o => (Row: r, Option: o))).First();
            var edit = new CemEdit(choice.Row.Offset, choice.Option.Code);
            var edited = await client.PreviewAsync([edit]);
            var changed = edited.Rows.Single(r => r.Changed);
            Require(changed.Offset == edit.Offset && changed.SelectedCode == edit.Code &&
                changed.SelectedText == choice.Option.Text &&
                edited.AuditSha256 != baseline.AuditSha256 &&
                edited.LabOnly && !edited.CanExport);
            Pass();

            step = "04 audit determinism";
            var editedAgain = await client.PreviewAsync([edit]);
            Require(editedAgain.AuditSha256 == edited.AuditSha256 &&
                editedAgain.Status == edited.Status &&
                editedAgain.Errors.SequenceEqual(edited.Errors) &&
                editedAgain.Warnings.SequenceEqual(edited.Warnings) &&
                editedAgain.TopologyReviewRequired == edited.TopologyReviewRequired);
            Pass();

            step = "05 locked edit rejected";
            var locked = baseline.Rows.First(r => r.Locked);
            await Reject<InvalidDataException>(() => client.PreviewAsync([new(locked.Offset, "01")]));
            Pass();

            step = "06 malformed request rejected by real process";
            await Reject<InvalidDataException>(() => transport.PreviewAsync("{"u8.ToArray(), CancellationToken.None));
            Pass();

            step = "07 cancelled refresh clears snapshot";
            using (var cancel = new CancellationTokenSource())
            {
                cancel.Cancel();
                await Reject<OperationCanceledException>(() => view.RefreshAsync([], cancel.Token));
                Require(view.Snapshot is null && !view.IsBusy);
            }
            Pass();
        }
        catch (Exception)
        {
            Console.Error.WriteLine("FAIL " + step);
        }
        finally
        {
            if (before is not null)
            {
                try { unchanged = before.SequenceEqual(Fingerprint(args[2])); }
                catch (Exception) { unchanged = false; }
            }
            if (unchanged) { step = "08 seven input files unchanged"; Pass(); }
            else Console.Error.WriteLine("FAIL 08 input integrity not established");
        }

        Console.WriteLine($"VC073 owner-local smoke: {passed}/8");
        return passed == 8 ? 0 : 1;

        void Pass()
        {
            passed++;
            Console.WriteLine("PASS " + step);
        }
    }
}
