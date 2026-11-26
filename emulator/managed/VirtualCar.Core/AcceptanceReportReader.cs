using System.Security.Cryptography;
using System.Text.Json;

namespace VirtualCar.Core;

public enum AcceptanceObservation { ReportedPass, ReportedFail, Review, NotTested, Observed }
public enum AcceptanceSourceMatch { Matches, Differs, NotDeclared, NotCompared }

public sealed record AcceptanceReport(string Stage, string Schema, AcceptanceObservation Observation,
    string? SourceSha, string? NativeSha, string ReportSha, int? Passed, int? Total, string Detail)
{
    public AcceptanceSourceMatch CompareSource(string? expected)
    {
        if (SourceSha is null) return AcceptanceSourceMatch.NotDeclared;
        if (string.IsNullOrEmpty(expected)) return AcceptanceSourceMatch.NotCompared;
        return SourceSha.Equals(expected, StringComparison.OrdinalIgnoreCase)
            ? AcceptanceSourceMatch.Matches : AcceptanceSourceMatch.Differs;
    }
}

/// <summary>Imports bounded local report claims, never runtime attestation.</summary>
public static class AcceptanceReportReader
{
    public const int MaxBytes = 256 * 1024;

    public static bool IsHash(string? value, int length) =>
        value is not null && value.Length == length && value.All(Uri.IsHexDigit);

    public static AcceptanceReport ReadFile(string path)
    {
        if (!Path.IsPathFullyQualified(path) || !Path.GetExtension(path).Equals(".json", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        string full = Path.GetFullPath(path);
        if (OperatingSystem.IsWindows() && (full.StartsWith(@"\\", StringComparison.Ordinal) ||
            new DriveInfo(Path.GetPathRoot(full)!).DriveType != DriveType.Fixed))
            throw new InvalidDataException();
        for (FileSystemInfo? item = new FileInfo(full); item is not null;
            item = item is FileInfo file ? file.Directory : ((DirectoryInfo)item).Parent)
            if ((item.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException();
        using var stream = File.Open(full, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (stream.Length is < 1 or > MaxBytes) throw new InvalidDataException();
        byte[] bytes = new byte[(int)stream.Length];
        stream.ReadExactly(bytes);
        if (stream.ReadByte() != -1) throw new InvalidDataException();
        return Parse(bytes);
    }

    public static AcceptanceReport Parse(ReadOnlyMemory<byte> bytes)
    {
        if (bytes.Length is < 1 or > MaxBytes) throw new InvalidDataException();
        string digest = Convert.ToHexString(SHA256.HashData(bytes.Span)).ToLowerInvariant();
        if (bytes.Span.StartsWith(new byte[] { 0xef, 0xbb, 0xbf })) bytes = bytes[3..];
        using var doc = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 24 });
        var root = doc.RootElement;
        CheckTree(root);
        bool hasSchema = root.TryGetProperty("schema", out _);
        bool hasVersion = root.TryGetProperty("schema_version", out _);
        if (hasSchema == hasVersion) throw new InvalidDataException();
        string schema = Str(root, hasSchema ? "schema" : "schema_version");
        return schema switch
        {
            "vc090-native-preflight-v1" => Native(root, schema, digest),
            "vc090b-registration-checkpoint-v1" => Registration(root, schema, digest),
            "vc090c-explicit-vida-binding-v1" => Binding(root, schema, digest),
            "vc090d-native-readvin-evidence-v1" => Identity(root, schema, digest),
            "vc090e-ecu-identification-evidence-v1" => Ecu(root, schema, digest),
            _ => throw new InvalidDataException()
        };
    }

    private static void CheckTree(JsonElement node)
    {
        if (node.ValueKind == JsonValueKind.Object)
        {
            var keys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var p in node.EnumerateObject())
            {
                if (!keys.Add(p.Name)) throw new InvalidDataException();
                CheckTree(p.Value);
            }
        }
        else if (node.ValueKind == JsonValueKind.Array)
            foreach (var item in node.EnumerateArray()) CheckTree(item);
    }

    private static JsonElement Field(JsonElement root, string key) =>
        root.ValueKind == JsonValueKind.Object && root.TryGetProperty(key, out var value)
            ? value : throw new InvalidDataException();
    private static string Str(JsonElement root, string key) =>
        Field(root, key).ValueKind == JsonValueKind.String
            ? Field(root, key).GetString()! : throw new InvalidDataException();
    private static string Choice(JsonElement root, string key, params string[] allowed)
    {
        string value = Str(root, key);
        return allowed.Contains(value, StringComparer.Ordinal) ? value : throw new InvalidDataException();
    }
    private static string Hash(JsonElement root, string key, int length)
    {
        string hash = Str(root, key);
        return IsHash(hash, length) ? hash.ToLowerInvariant() : throw new InvalidDataException();
    }
    private static bool Bool(JsonElement root, string key) => Field(root, key).ValueKind switch
    {
        JsonValueKind.True => true, JsonValueKind.False => false, _ => throw new InvalidDataException()
    };
    private static void Unverified(JsonElement root, params string[] fields)
    {
        foreach (string key in fields) if (Bool(root, key)) throw new InvalidDataException();
    }
    private static int Count(JsonElement root, string key, int max = 250000) =>
        Field(root, key).ValueKind == JsonValueKind.Number &&
        Field(root, key).TryGetInt32(out int n) && n >= 0 && n <= max
            ? n : throw new InvalidDataException();

    private static AcceptanceReport Native(JsonElement root, string schema, string digest)
    {
        string source = Hash(root, "source_sha", 40);
        string native = Hash(root, "native_dll_sha256", 64);
        string state = Choice(root, "status", "pass", "fail");
        string[] keys = ["source_and_managed_inventory", "fresh_native_build", "x86_export_contract",
            "native_silence_and_evidence", "synthetic_identity_replay", "can_ms_lifecycle",
            "registry32_preflight", "final_integrity"];
        var gates = Field(root, "gates");
        if (gates.ValueKind != JsonValueKind.Object || gates.EnumerateObject().Count() != keys.Length)
            throw new InvalidDataException();
        string[] values = keys.Select(k => Choice(gates, k, "pass", "fail", "not_tested")).ToArray();
        int passed = values.Count(v => v == "pass");
        if ((state == "pass") != (passed == keys.Length)) throw new InvalidDataException();
        foreach (string name in new[] { "registration_install_remove", "vida_provider_selection",
            "vida_loaded_module_identity", "vida_readvin", "vida_t111", "vida_t122", "physical_j2534" })
            Choice(root, name, "not_tested");
        return new("VC090A", schema, state == "pass" ? AcceptanceObservation.ReportedPass : AcceptanceObservation.ReportedFail,
            source, native, digest, passed, keys.Length, "native_preflight");
    }

    private static AcceptanceReport Registration(JsonElement root, string schema, string digest)
    {
        string phase = Choice(root, "phase", "Baseline", "InstallCancelled", "Installed", "RemoveCancelled", "Restored");
        bool present = Bool(root, "canonical_present");
        if (present != (phase is "Installed" or "RemoveCancelled")) throw new InvalidDataException();
        Choice(root, "ui_actions", "owner_confirmation_required");
        Choice(root, "vida", "not_tested");
        Choice(root, "physical_j2534", "not_tested");
        foreach (string name in new[] { "registry32_other", "registry64" })
        {
            var view = Field(root, name);
            Hash(view, "digest", 64);
            Count(view, "other_provider_count");
        }
        return new("VC090B/" + phase, schema, AcceptanceObservation.Observed,
            Hash(root, "source_sha", 40), Hash(root, "native_sha256", 64), digest, null, null, "checkpoint_only");
    }

    private static AcceptanceReport Binding(JsonElement root, string schema, string digest)
    {
        Unverified(root, "selected_pid_is_authenticated_original_vida", "selected_process_is_authenticated_original_vida",
            "loaded_binary_memory_matches_disk_verified", "active_vida_diagnostic_config_loaded_verified",
            "effective_diagnostic_connection_mode_verified", "original_vida_script_selection_verified",
            "original_vida_j2534_tx_rx_verified", "original_vida_vin_accepted_verified",
            "ecu_identity_accepted_verified", "provider_selection_in_vida_gui_verified",
            "registry_install_remove_verified", "physical_adapter_examined");
        string gate = Choice(root, "candidate_binding_gate", "snapshot_changed_or_unverifiable",
            "selected_provider_unavailable", "historical_or_different_binary", "binary_equivalence_unverified",
            "process_identity_unverified", "module_binding_unverified", "candidate_path_and_disk_bytes_observed");
        bool match = gate == "candidate_path_and_disk_bytes_observed";
        if (match && (!Bool(root, "selected_provider_snapshot_stable") ||
            !Bool(root, "reference_fingerprint_verified") ||
            !Bool(root, "registered_dll_module_path_seen_in_name_matched_process") ||
            Str(root, "installed_vs_reference_dll") != "exact_bytes_at_snapshot"))
            throw new InvalidDataException();
        return new("VC090C", schema, match ? AcceptanceObservation.Observed : AcceptanceObservation.Review,
            null, null, digest, null, null, gate);
    }

    private static AcceptanceReport Identity(JsonElement root, string schema, string digest)
    {
        Unverified(root, "original_vida_process_authenticated", "loaded_module_identity_verified",
            "readvin_script_execution_verified", "original_vida_vin_accepted_verified",
            "ecu_identity_accepted_verified", "physical_j2534_verified");
        string gate = Choice(root, "native_evidence_gate", "incomplete_or_ambiguous_native_evidence",
            "no_positive_identity_delivery_observed", "delivered_identity_differs", "matching_lab_identity_delivery_observed");
        var counts = Field(root, "counts");
        int b = Count(counts, "b9fb_positive"), f = Count(counts, "f190_positive");
        int be = Count(counts, "b9fb_vin_equal"), fe = Count(counts, "f190_vin_equal");
        if (b != be + Count(counts, "b9fb_vin_different") ||
            f != fe + Count(counts, "f190_vin_different")) throw new InvalidDataException();
        bool match = gate == "matching_lab_identity_delivery_observed";
        if (match && (!Bool(root, "single_closed_logger_session") || b + f == 0 || be + fe != b + f))
            throw new InvalidDataException();
        return new("VC090D", schema, match ? AcceptanceObservation.Observed : AcceptanceObservation.Review,
            null, null, digest, be + fe, b + f, gate);
    }

    private static AcceptanceReport Ecu(JsonElement root, string schema, string digest)
    {
        Unverified(root, "catalog_and_readout_same_run_verified", "selected_vehicle_profile_verified",
            "original_vida_client_authenticated", "actual_j2534_identification_exchange_verified",
            "original_vida_readvin_accepted", "original_vida_ecu_identification_accepted", "physical_j2534_verified");
        string gate = Choice(root, "readout_reconciliation_gate", "no_module_observations",
            "same_run_not_reported", "reported_discrepancies_require_review",
            "reported_evidence_incomplete", "reported_categories_consistent_only");
        int modules = Count(root, "module_count", 256);
        var states = Field(root, "readout_counts");
        if (new[] { "alive", "not_alive", "not_present", "not_observed" }
            .Sum(k => Count(states, k, 256)) != modules) throw new InvalidDataException();
        bool consistent = gate == "reported_categories_consistent_only";
        if (consistent && (modules == 0 || !Bool(root, "same_run_reported"))) throw new InvalidDataException();
        return new("VC090E", schema, consistent ? AcceptanceObservation.Observed : AcceptanceObservation.Review,
            null, null, digest, null, null, gate);
    }
}
