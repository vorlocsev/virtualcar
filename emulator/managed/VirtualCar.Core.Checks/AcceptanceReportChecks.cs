using System.Security.Cryptography;
using System.Text.Json;
using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class AcceptanceReportChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC091 01 native preflight claim and exact fingerprints", () => Run(Test01)),
        ("VC091 02 native failure and contradictory claims", () => Run(Test02)),
        ("VC091 03 registration checkpoints are observations only", () => Run(Test03)),
        ("VC091 04 binding observation cannot authenticate VIDA", () => Run(Test04)),
        ("VC091 05 native identity is not ReadVin acceptance", () => Run(Test05)),
        ("VC091 06 ECU reconciliation is not runtime acceptance", () => Run(Test06)),
        ("VC091 07 bounded and duplicate JSON rejection", () => Run(Test07)),
        ("VC091 08 local snapshot integrity and source mismatch", () => Run(Test08))
    ];
    private static Task Run(Action test) { test(); return Task.CompletedTask; }
    private static void Require(bool value) { if (!value) throw new InvalidOperationException(); }
    private static void Reject(Action action)
    {
        try { action(); }
        catch (InvalidDataException) { return; }
        catch (JsonException) { return; }
        throw new InvalidOperationException("Expected invalid report.");
    }
    private static string Head => new('a', 40);
    private static string Dll => new('b', 64);
    private static AcceptanceReport Parse(Dictionary<string, object> data) =>
        AcceptanceReportReader.Parse(JsonSerializer.SerializeToUtf8Bytes(data));
    private static Dictionary<string, object> Base(string schema, params string[] flags)
    {
        var data = new Dictionary<string, object> { ["schema"] = schema };
        foreach (string flag in flags) data[flag] = false;
        return data;
    }
    private static Dictionary<string, object> Native()
    {
        var data = Base("vc090-native-preflight-v1");
        data["source_sha"] = Head; data["native_dll_sha256"] = Dll; data["native_dll_bytes"] = 109568;
        data["status"] = "pass"; data["failed_stage"] = "";
        data["gates"] = new[] { "source_and_managed_inventory", "fresh_native_build", "x86_export_contract",
            "native_silence_and_evidence", "synthetic_identity_replay", "can_ms_lifecycle",
            "registry32_preflight", "final_integrity" }.ToDictionary(k => k, _ => "pass");
        foreach (string key in new[] { "registration_install_remove", "vida_provider_selection",
            "vida_loaded_module_identity", "vida_readvin", "vida_t111", "vida_t122", "physical_j2534" })
            data[key] = "not_tested";
        return data;
    }
    private static void Test01()
    {
        var bytes = JsonSerializer.SerializeToUtf8Bytes(Native());
        var report = AcceptanceReportReader.Parse(bytes);
        Require(report.Observation == AcceptanceObservation.ReportedPass && report.Passed == 8 && report.Total == 8);
        Require(report.SourceSha == Head && report.NativeSha == Dll && report.CompareSource(Head.ToUpperInvariant()) == AcceptanceSourceMatch.Matches);
        Require(report.ReportSha == Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
    }
    private static void Test02()
    {
        var data = Native();
        var gates = (Dictionary<string, string>)data["gates"];
        gates["fresh_native_build"] = "fail";
        foreach (string key in gates.Keys.ToArray()) if (key != "fresh_native_build" && key != "source_and_managed_inventory") gates[key] = "not_tested";
        Reject(() => Parse(data));
        data["status"] = "fail"; data["failed_stage"] = "fresh_native_build";
        data["native_dll_sha256"] = ""; data["native_dll_bytes"] = 0;
        var report = Parse(data);
        Require(report.Observation == AcceptanceObservation.ReportedFail && report.NativeSha is null && report.Passed == 1);
        data["vida_readvin"] = "pass"; Reject(() => Parse(data));
    }
    private static void Test03()
    {
        var data = Base("vc090b-registration-checkpoint-v1");
        data["source_sha"] = Head; data["native_sha256"] = Dll;
        data["phase"] = "Restored"; data["canonical_present"] = false;
        data["ui_actions"] = "owner_confirmation_required";
        data["vida"] = data["physical_j2534"] = "not_tested";
        data["registry32_other"] = data["registry64"] = new { digest = Dll, other_provider_count = 69 };
        var report = Parse(data);
        Require(report.Stage == "VC090B/Restored" && report.Observation == AcceptanceObservation.Observed);
        data["canonical_present"] = true; Reject(() => Parse(data));
    }
    private static void Test04()
    {
        var data = Base("vc090c-explicit-vida-binding-v1", "selected_pid_is_authenticated_original_vida",
            "selected_process_is_authenticated_original_vida", "loaded_binary_memory_matches_disk_verified",
            "active_vida_diagnostic_config_loaded_verified", "effective_diagnostic_connection_mode_verified",
            "original_vida_script_selection_verified", "original_vida_j2534_tx_rx_verified",
            "original_vida_vin_accepted_verified", "ecu_identity_accepted_verified", "provider_selection_in_vida_gui_verified",
            "registry_install_remove_verified", "physical_adapter_examined");
        data["schema_version"] = data["schema"]; data.Remove("schema");
        data["candidate_binding_gate"] = "candidate_path_and_disk_bytes_observed";
        data["selected_provider_snapshot_stable"] = data["reference_fingerprint_verified"] =
            data["registered_dll_module_path_seen_in_name_matched_process"] = true;
        data["installed_vs_reference_dll"] = "exact_bytes_at_snapshot";
        data["reference_dll_pe32"] = "x86_pe32_header";
        data["selected_private_pid_starttime_snapshot_stability"] = "same_pid_process_starttime_after_snapshot";
        var report = Parse(data);
        Require(report.Observation == AcceptanceObservation.Observed && report.CompareSource(Head) == AcceptanceSourceMatch.NotDeclared);
        data["original_vida_vin_accepted_verified"] = true; Reject(() => Parse(data));
    }
    private static void Test05()
    {
        var data = Base("vc090d-native-readvin-evidence-v1", "original_vida_process_authenticated",
            "loaded_module_identity_verified", "readvin_script_execution_verified", "original_vida_vin_accepted_verified",
            "ecu_identity_accepted_verified", "physical_j2534_verified");
        data["native_evidence_gate"] = "incomplete_or_ambiguous_native_evidence";
        var counts = new Dictionary<string, int> { ["b9fb_positive"] = 1, ["f190_positive"] = 1,
            ["b9fb_vin_equal"] = 1, ["f190_vin_equal"] = 1, ["b9fb_vin_different"] = 0, ["f190_vin_different"] = 0 };
        data["counts"] = counts;
        Require(Parse(data).Observation == AcceptanceObservation.Review);
        counts["b9fb_vin_equal"] = 2; Reject(() => Parse(data));
    }
    private static void Test06()
    {
        var data = Base("vc090e-ecu-identification-evidence-v1", "catalog_and_readout_same_run_verified",
            "selected_vehicle_profile_verified", "original_vida_client_authenticated", "actual_j2534_identification_exchange_verified",
            "original_vida_readvin_accepted", "original_vida_ecu_identification_accepted", "physical_j2534_verified");
        data["readout_reconciliation_gate"] = "reported_categories_consistent_only";
        data["same_run_reported"] = true; data["module_count"] = 2;
        data["evidence_source"] = "synthetic";
        data["catalog_reference_coverage"] = new { status = "sample_all_references_matched", sampled_rows = 10,
            matching_references = 10, unmatched_references = 0, null_references = 0 };
        data["readout_counts"] = new { alive = 1, not_alive = 1, not_present = 0, not_observed = 0 };
        data["discrepancies"] = new { test = 0 }; data["evidence_gaps"] = new { test = 0 };
        Require(Parse(data).Observation == AcceptanceObservation.Observed);
        data["evidence_gaps"] = new { test = 1 }; Reject(() => Parse(data));
        data["module_count"] = 3; Reject(() => Parse(data));
    }
    private static void Test07()
    {
        Reject(() => AcceptanceReportReader.Parse(new byte[AcceptanceReportReader.MaxBytes + 1]));
        foreach (string json in new[] { "[]", "{\"schema\":\"unknown\"}", "{\"schema\":\"x\",\"Schema\":\"y\"}", "{\"schema\":\"x\",\"nested\":{\"a\":1,\"a\":2}}" })
            Reject(() => AcceptanceReportReader.Parse(Encoding.UTF8.GetBytes(json)));
    }
    private static void Test08()
    {
        string path = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N") + ".json");
        byte[] bytes = [0xef, 0xbb, 0xbf, ..JsonSerializer.SerializeToUtf8Bytes(Native())];
        File.WriteAllBytes(path, bytes);
        try
        {
            var report = AcceptanceReportReader.ReadFile(path);
            Require(report.CompareSource(new string('c', 40)) == AcceptanceSourceMatch.Differs);
            Require(report.CompareSource(null) == AcceptanceSourceMatch.NotCompared);
            Require(File.ReadAllBytes(path).SequenceEqual(bytes));
            Require(report.ReportSha == Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
            Reject(() => AcceptanceReportReader.ReadFile("relative.json"));
        }
        finally { File.Delete(path); }
    }
}
