using System.Text;
using System.Text.Json;

namespace VirtualCar.Core;

public sealed record BundleGate(string Key, string State);
public sealed record BundleEvidence(string Role, string Sha256);
public sealed record BundleSummary(string Scope, string ManifestSha, int Checkpoints,
    IReadOnlyList<BundleGate> Gates, IReadOnlyList<BundleEvidence> Evidence,
    int CatalogMatched, int CatalogSampled, IReadOnlyList<string> MissingClaims)
{
    public static string? RoleForStage(string stage) => stage switch
    {
        "VC090A" => "native_preflight", "VC090C" => "binding",
        "VC090D" => "readvin", "VC090E" => "ecu",
        _ when stage.StartsWith("VC090B/", StringComparison.Ordinal) => "registration_" + stage[7..],
        _ => null
    };

    public string CompareReport(AcceptanceReport report)
    {
        string? role = RoleForStage(report.Stage);
        var entry = Evidence.FirstOrDefault(e => e.Role == role);
        return entry is null ? "not_in_bundle" :
            entry.Sha256.Equals(report.ReportSha, StringComparison.OrdinalIgnoreCase) ? "matches" : "differs";
    }
}

public static partial class AcceptanceReportReader
{
    private static readonly string[] BundlePhases = ["Baseline", "InstallCancelled", "Installed", "RemoveCancelled", "Restored"];
    private static readonly string[] BundleClaims = ["disposable_vm_snapshot", "owner_mutation_permission",
        "not_persistent_runner", "physical_adapter_disconnected", "same_session_reviewed"];
    private static readonly string[] RuntimeFlags = ["same_runtime_session_verified", "vm_snapshot_verified",
        "registry_mutation_authorized_by_tool", "registration_install_remove_verified",
        "original_vida_provider_selection_verified", "loaded_module_identity_verified",
        "original_vida_readvin_verified", "original_vida_ecu_identification_verified",
        "original_catalog_coverage_verified", "physical_j2534_verified", "release_ready"];

    private static void ExactKeys(JsonElement obj, IEnumerable<string> keys)
    {
        if (obj.ValueKind != JsonValueKind.Object ||
            !obj.EnumerateObject().Select(p => p.Name).ToHashSet(StringComparer.Ordinal).SetEquals(keys))
            throw new InvalidDataException();
    }

    private static AcceptanceReport Bundle(JsonElement root, string schema, string digest)
    {
        Unverified(root, RuntimeFlags);
        Choice(root, "overall", "runtime_acceptance_not_verified");
        string source = Hash(root, "source_sha", 40), dll = Hash(root, "native_sha256", 64);
        string scope = Choice(root, "scope", "synthetic", "owner_reviewed");
        string manifest = Hash(root, "manifest_sha256", 64);
        var evidence = Field(root, "evidence_sha256_by_role");
        var roles = new HashSet<string>(new[] { "native_preflight", "native_dll", "binding", "readvin", "ecu", "catalog" }
            .Concat(BundlePhases.Select(p => "registration_" + p)), StringComparer.Ordinal);
        if (evidence.ValueKind != JsonValueKind.Object) throw new InvalidDataException();
        var entries = new List<BundleEvidence>();
        foreach (var property in evidence.EnumerateObject())
        {
            if (!roles.Contains(property.Name)) throw new InvalidDataException();
            entries.Add(new(property.Name, Hash(evidence, property.Name, 64)));
        }
        bool Has(string role) => entries.Any(e => e.Role == role);
        var claims = Field(root, "owner_claims");
        ExactKeys(claims, BundleClaims);
        string[] missing = BundleClaims.Where(k => !Bool(claims, k)).ToArray();
        var gates = Field(root, "gates");
        ExactKeys(gates, ["environment", "native_preflight", "registration", "binding", "readvin", "ecu", "catalog", "file_integrity"]);
        var rows = new List<BundleGate>();
        string Add(string key, params string[] states)
        {
            string value = Choice(gates, key, states);
            rows.Add(new(key, value));
            return value;
        }
        string env = Add("environment", "owner_claims_only", "blocked_or_synthetic");
        if ((env == "owner_claims_only") != (scope == "owner_reviewed" && missing.Length == 0))
            throw new InvalidDataException();
        string native = Add("native_preflight", "not_tested", "source_mismatch", "reported_failure",
            "candidate_mismatch", "candidate_file_missing", "reported_preflight_consistent");
        if ((native == "not_tested") == Has("native_preflight") ||
            (native == "reported_preflight_consistent" && (!Has("native_dll") ||
                entries.Single(e => e.Role == "native_dll").Sha256 != dll)) ||
            (native == "candidate_file_missing" && Has("native_dll"))) throw new InvalidDataException();
        string reg = Add("registration", "not_tested", "candidate_mismatch", "registry_snapshot_mismatch",
            "checkpoint_gap", "partial_checkpoints", "reported_checkpoints_consistent");
        int count = Count(root, "registration_checkpoints", 5);
        if (Count(root, "registration_checkpoints_expected", 5) != 5) throw new InvalidDataException();
        var included = BundlePhases.Where(p => Has("registration_" + p)).ToArray();
        bool prefix = included.SequenceEqual(BundlePhases.Take(included.Length));
        if (count > included.Length ||
            (reg == "not_tested" && (included.Length != 0 || count != 0)) ||
            (reg == "partial_checkpoints" && (!prefix || count != included.Length || count is < 1 or > 4)) ||
            (reg == "reported_checkpoints_consistent" && (count != 5 || included.Length != 5)) ||
            (reg == "checkpoint_gap" && (prefix || count != included.Length)) ||
            ((reg is "candidate_mismatch" or "registry_snapshot_mismatch") && count >= included.Length))
            throw new InvalidDataException();
        foreach (string key in new[] { "binding", "readvin", "ecu" })
        {
            string value = Add(key, "not_tested", "review_required", "unbound_report_observation");
            if ((value == "not_tested") == Has(key)) throw new InvalidDataException();
        }
        string coverage = Add("catalog", "not_supplied", "empty_sample", "unmatched_references_observed",
            "null_references_observed", "sample_all_references_matched");
        var sample = Field(root, "catalog_sample");
        ExactKeys(sample, ["status", "sampled_rows", "matching_references", "unmatched_references", "null_references"]);
        int n = Count(sample, "sampled_rows", 1000), matched = Count(sample, "matching_references", 1000);
        int missed = Count(sample, "unmatched_references", 1000), nulls = Count(sample, "null_references", 1000);
        if ((!Has("catalog") && n != 0) || n != matched + missed + nulls || Str(sample, "status") != coverage ||
            coverage != (!Has("catalog") && n == 0 ? "not_supplied" : n == 0 ? "empty_sample" :
                missed > 0 ? "unmatched_references_observed" : nulls > 0 ? "null_references_observed" : "sample_all_references_matched"))
            throw new InvalidDataException();
        if ((Add("file_integrity", "supplied_digests_match", "no_evidence_files") == "no_evidence_files") != (entries.Count == 0))
            throw new InvalidDataException();
        var bundle = new BundleSummary(scope, manifest, count, rows.AsReadOnly(), entries.AsReadOnly(), matched, n,
            Array.AsReadOnly(missing));
        return new("VC092", schema, AcceptanceObservation.Review, source, dll, digest, count, 5,
            "runtime_acceptance_not_verified") { Bundle = bundle };
    }
}

/// <summary>Explicit new external text file only; never exports raw imported JSON.</summary>
public static class AcceptanceSummaryExport
{
    public const int MaxBytes = 128 * 1024;
    public static void WriteNew(string path, string summary)
    {
        if (!Path.IsPathFullyQualified(path) || !Path.GetExtension(path).Equals(".txt", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException();
        string full = Path.GetFullPath(path);
        if (OperatingSystem.IsWindows() && Path.GetFileName(full).Contains(':')) throw new InvalidDataException();
        if (OperatingSystem.IsWindows() && (full.StartsWith(@"\\", StringComparison.Ordinal) ||
            new DriveInfo(Path.GetPathRoot(full)!).DriveType != DriveType.Fixed)) throw new InvalidDataException();
        for (DirectoryInfo? dir = new FileInfo(full).Directory; dir is not null; dir = dir.Parent)
            if ((dir.Attributes & FileAttributes.ReparsePoint) != 0 || Directory.Exists(Path.Combine(dir.FullName, ".git")) ||
                File.Exists(Path.Combine(dir.FullName, ".git")) || File.Exists(Path.Combine(dir.FullName, "build-manifest.json")))
                throw new InvalidDataException();
        byte[] bytes = new UTF8Encoding(false, true).GetBytes(summary);
        if (bytes.Length is < 1 or > MaxBytes) throw new InvalidDataException();
        using var stream = File.Open(full, FileMode.CreateNew, FileAccess.Write, FileShare.None);
        stream.Write(bytes);
    }
}
