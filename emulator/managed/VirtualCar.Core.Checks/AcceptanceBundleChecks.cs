using System.Text;
using System.Text.Json;
using System.Security.Cryptography;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class AcceptanceBundleChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC093 01 import historical six-file partial bundle", () => Run(Test01)),
        ("VC093 02 reject runtime success claims", () => Run(Test02)),
        ("VC093 03 reject contradictory checkpoint progress", () => Run(Test03)),
        ("VC093 04 compare individual report bytes with bundle", () => Run(Test04)),
        ("VC093 05 preserve scope and missing environment claims", () => Run(Test05)),
        ("VC093 06 catalog and integrity role consistency", () => Run(Test06)),
        ("VC093 07 export exact UTF8 summary without overwrite", () => Run(Test07)),
        ("VC093 08 reject unsafe export destinations", () => Run(Test08))
    ];
    private static Task Run(Action test) { test(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
    private static void Reject(Action action)
    {
        try { action(); }
        catch (InvalidDataException) { return; }
        catch (JsonException) { return; }
        catch (IOException) { return; }
        throw new InvalidOperationException("Expected rejection");
    }

    private static string H(char c, int n = 64) => new(c, n);
    private static Dictionary<string, object> Data()
    {
        var result = new Dictionary<string, object>
        {
            ["schema"] = "vc092-evidence-bundle-report-v1",
            ["source_sha"] = H('a', 40),
            ["native_sha256"] = H('b'),
            ["manifest_sha256"] = H('c'),
            ["scope"] = "owner_reviewed",
            ["overall"] = "runtime_acceptance_not_verified",
            ["registration_checkpoints"] = 2,
            ["registration_checkpoints_expected"] = 5,
            ["owner_claims"] = new Dictionary<string, bool>
            {
                ["disposable_vm_snapshot"] = false, ["owner_mutation_permission"] = false,
                ["not_persistent_runner"] = false, ["physical_adapter_disconnected"] = false, ["same_session_reviewed"] = false
            },
            ["gates"] = new Dictionary<string, string>
            {
                ["environment"] = "blocked_or_synthetic", ["native_preflight"] = "reported_preflight_consistent",
                ["registration"] = "partial_checkpoints", ["binding"] = "not_tested",
                ["readvin"] = "review_required", ["ecu"] = "review_required", ["catalog"] = "not_supplied",
                ["file_integrity"] = "supplied_digests_match"
            },
            ["evidence_sha256_by_role"] = new Dictionary<string, string>
            {
                ["native_preflight"] = H('d'), ["native_dll"] = H('b'),
                ["registration_Baseline"] = H('e'), ["registration_InstallCancelled"] = H('f'),
                ["readvin"] = H('1'), ["ecu"] = H('2')
            },
            ["catalog_sample"] = new { status = "not_supplied", sampled_rows = 0, matching_references = 0, unmatched_references = 0, null_references = 0 }
        };
        foreach (string key in new[] { "same_runtime_session_verified", "vm_snapshot_verified",
            "registry_mutation_authorized_by_tool", "registration_install_remove_verified",
            "original_vida_provider_selection_verified", "loaded_module_identity_verified",
            "original_vida_readvin_verified", "original_vida_ecu_identification_verified",
            "original_catalog_coverage_verified", "physical_j2534_verified", "release_ready" })
            result[key] = false;
        return result;
    }
    private static AcceptanceReport Parse(Dictionary<string, object> data) =>
        AcceptanceReportReader.Parse(JsonSerializer.SerializeToUtf8Bytes(data));
    private static Dictionary<string, string> Gates(Dictionary<string, object> data) => (Dictionary<string, string>)data["gates"];
    private static Dictionary<string, string> Evidence(Dictionary<string, object> data) => (Dictionary<string, string>)data["evidence_sha256_by_role"];

    private static void Test01()
    {
        var bytes = JsonSerializer.SerializeToUtf8Bytes(Data());
        var report = AcceptanceReportReader.Parse(bytes);
        var bundle = report.Bundle ?? throw new InvalidOperationException();
        Require(report.Stage == "VC092" && report.Observation == AcceptanceObservation.Review);
        Require(bundle.Checkpoints == 2 && bundle.Gates.Count == 8 && bundle.Evidence.Count == 6);
        Require(report.CompareSource(H('a', 40)) == AcceptanceSourceMatch.Matches &&
            report.CompareSource(H('b', 40)) == AcceptanceSourceMatch.Differs);
        Require(report.ReportSha == Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
    }
    private static void Test02()
    {
        var data = Data(); data["release_ready"] = true; Reject(() => Parse(data));
        data = Data(); data["original_vida_readvin_verified"] = true; Reject(() => Parse(data));
        data = Data(); data["overall"] = "pass"; Reject(() => Parse(data));
    }
    private static void Test03()
    {
        var data = Data(); data["registration_checkpoints"] = 5; Reject(() => Parse(data));
        data = Data(); Evidence(data).Remove("registration_InstallCancelled");
        Evidence(data)["registration_Installed"] = H('f'); Reject(() => Parse(data));
        Gates(data)["registration"] = "checkpoint_gap"; Require(Parse(data).Bundle?.Checkpoints == 2);
        data = Data(); Gates(data)["registration"] = "reported_checkpoints_consistent"; Reject(() => Parse(data));
    }
    private static void Test04()
    {
        var bundle = Parse(Data()).Bundle!;
        var one = new AcceptanceReport("VC090B/Baseline", "test", AcceptanceObservation.Observed,
            null, null, H('e'), null, null, "checkpoint_only");
        Require(bundle.CompareReport(one) == "matches");
        Require(bundle.CompareReport(one with { ReportSha = H('9') }) == "differs");
        Require(bundle.CompareReport(one with { Stage = "VC090C" }) == "not_in_bundle");
        Require(BundleSummary.RoleForStage("VC092") is null);
    }
    private static void Test05()
    {
        var data = Data();
        Require(Parse(data).Bundle?.MissingClaims.Count == 5);
        Gates(data)["environment"] = "owner_claims_only"; Reject(() => Parse(data));
        var claims = (Dictionary<string, bool>)data["owner_claims"];
        foreach (string key in claims.Keys.ToArray()) claims[key] = true;
        Require(Parse(data).Bundle?.MissingClaims.Count == 0);
        data["scope"] = "synthetic"; Reject(() => Parse(data));
    }
    private static void Test06()
    {
        var data = Data(); Evidence(data)["native_dll"] = H('0'); Reject(() => Parse(data));
        data = Data(); Gates(data)["file_integrity"] = "no_evidence_files"; Reject(() => Parse(data));
        data = Data(); Evidence(data)["binding"] = H('0'); Reject(() => Parse(data));
        data = Data(); Gates(data)["catalog"] = "sample_all_references_matched"; Reject(() => Parse(data));
        data = Data(); Evidence(data)["catalog"] = H('3'); Gates(data)["catalog"] = "sample_all_references_matched";
        data["catalog_sample"] = new { status = "sample_all_references_matched", sampled_rows = 10,
            matching_references = 10, unmatched_references = 0, null_references = 0 };
        Require(Parse(data).Bundle?.CatalogMatched == 10);
    }
    private static void Test07()
    {
        string dir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N")); Directory.CreateDirectory(dir);
        try
        {
            string path = Path.Combine(dir, "summary.txt");
            string summary = "VC092 · Приёмка не подтверждена";
            AcceptanceSummaryExport.WriteNew(path, summary);
            Require(File.ReadAllBytes(path).SequenceEqual(Encoding.UTF8.GetBytes(summary)));
            Reject(() => AcceptanceSummaryExport.WriteNew(path, "changed"));
            Require(File.ReadAllText(path) == summary);
        }
        finally { Directory.Delete(dir, true); }
    }
    private static void Test08()
    {
        Reject(() => AcceptanceSummaryExport.WriteNew("relative.txt", "summary"));
        string dir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N")); Directory.CreateDirectory(dir);
        try
        {
            Reject(() => AcceptanceSummaryExport.WriteNew(Path.Combine(dir, "report.json"), "summary"));
            Reject(() => AcceptanceSummaryExport.WriteNew(Path.Combine(dir, "large.txt"), new string('x', AcceptanceSummaryExport.MaxBytes + 1)));
            File.WriteAllText(Path.Combine(dir, ".git"), "gitdir: synthetic");
            Reject(() => AcceptanceSummaryExport.WriteNew(Path.Combine(dir, "repo.txt"), "summary"));
            Require(!File.Exists(Path.Combine(dir, "repo.txt")));
            File.Delete(Path.Combine(dir, ".git"));
            File.WriteAllText(Path.Combine(dir, "build-manifest.json"), "{}");
            Reject(() => AcceptanceSummaryExport.WriteNew(Path.Combine(dir, "build.txt"), "summary"));
        }
        finally { Directory.Delete(dir, true); }
    }
}
