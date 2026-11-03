# VDASH: offline static analysis with REA

**Scope:** private, local, read-only inspection of `Frontend.Client.Core.dll`
from a legitimately obtained VDASH build. Nothing in this workflow programs,
unlocks, or changes a vehicle, and no VDASH binary or decompiled source belongs
in the Virtual Car repository.

## Why this tool

The saved VDASH 2.5.115.79 IL excerpt establishes two calls from
`VddModel.Detect` (MethodDef `0x0600132B`) to MethodSpec
`0x2B000002` at IL offsets `0x0124` and `0x0423`, followed by calls to
MethodDef `0x06001359` at `0x0129` and `0x0428`. The MethodSpec
instantiation signature is `0A 01 0E`, i.e. a single `System.String`
generic type argument. This **does not** identify the underlying generic
method, the predicate's meaning, or the runtime branch taken.

REA from [morluto/rea](https://github.com/morluto/rea) implements
`inspect_managed_artifact` and `inspect_managed_members` for PE/CLI
metadata, including `call_edges` with `caller_token`, `il_offset`,
`target_token`, `target_kind`, `target_name`, and
`target_declaring_type`. REA documents MethodSpec target name resolution,
but it can report unresolved or partial evidence. REA is **not** guaranteed
to deobfuscate the client. See the vendor's
[managed-code analysis specification](https://github.com/morluto/rea/blob/main/docs/managed-code-analysis.md).

## Windows: local, private inspection

Use a supported Node.js version according to the REA package's own
`engines` field (at the reviewed v6.8.0 repository snapshot,
`^22.23.4 || ^24.22.1 || >=26.12.1`). Installation is **optional**
and must be approved by the operator. No installation occurs in Virtual Car CI.
If using the setup wizard, review its configuration changes before approving.

Example PowerShell session; **replace the DLL path with your local copy**:

```powershell
npm install --global rea-agents@6.8.0
rea --help

$private = Join-Path $env:USERPROFILE 'VDASH-REA-private'
New-Item -ItemType Directory -Force -Path $private | Out-Null
$dll = 'C:\path\to\Frontend.Client.Core.dll'
rea inspect-managed-artifact $dll --json |
    Out-File -FilePath (Join-Path $private 'artifact-private.json') -Encoding utf8

# Keep the complete output PRIVATE. No --detail summary: that option returns
# a reduced observation and requires an evidence bundle destination.
rea inspect-managed-members $dll --json |
    Out-File -FilePath (Join-Path $private 'members-private.json') -Encoding utf8

py -3 .\tools\audit_rea_vdash_evidence.py `
    (Join-Path $private 'members-private.json') `
    --output (Join-Path $private 'rea-vdash-sanitized.json')
```

Run the last command from the `emulator` directory. It refuses to overwrite
existing output. **Do not** commit, paste or share the two `*-private.json`
files. They may contain all decoded methods, IL strings, local file paths,
binary digests and other proprietary data. If full inspection hits REA's
resource limit, inspect the exact `types[].full_name` returned by REA and
rerun `rea inspect-managed-members $dll --type Namespace.TypeName --json`.
A selected-type report need not cover the other required tokens; an unexamined
token is **unknown, not absent**.

### Read full names locally, never in the sanitized report

With the *private* complete member result only:

```powershell
$raw = Get-Content -Raw (Join-Path $private 'members-private.json') |
    ConvertFrom-Json
$raw.normalized_result.call_edges |
    Where-Object { $_.caller_token -eq '0x0600132b' -and
                   $_.target_token -eq '0x2b000002' } |
    Select-Object il_offset,target_kind,target_name,target_declaring_type
```

This table stays on the operator's machine. A `target_name` can remain null.
The stable `0x2B000002` token is **module/build-scoped** and must not be
transferred blindly to a different VDASH build. In a selected inspection,
some call edges may not be present at all. A matching name does not reveal
whether the opaque predicate is equality, error acceptance, server gating,
or another behavior.

## Allowlisted output and interpretation

`audit_rea_vdash_evidence.py` accepts a full REA JSON response that contains
`normalized_result`. It verifies that metadata identifies module
`Frontend.Client.Core.dll`, the build-local token scope and matching
artifact digest/MVID (where supplied). Its output includes **only**:

- Assembly identity **attestation flags** and REA coverage state, never
  original digest, MVID or path.
- Two callsite groups with observed count, exact IL offset checks, and whether
  REA populated one consistent method name and declaring type, not the names.
- Three independent structural links under `structural_edges`, each with
  observed count and a strict one-site IL-offset match:
  `Detect` (`0x0600132B`) `newobj 0x060011BB` at `IL_017F`
  (`DetectResult` constructor); the same caller `newobj 0x0600126D`
  at `IL_0268` (`Ecus` constructor); and
  `VddCommand.Execute` (`0x0600115D`) `call 0x06001160` at `IL_025E`
  (`ParseData`). These are grounded in the earlier **private static IL
  excerpt** for VDASH 2.5.115.79, not in a currently available original DLL.
  No raw IL or recovered method names are copied into the exported JSON.
- Inspection status (`present`, `partial`, `absent`, `malformed` or
  `not_inspected`) for six explicitly selected MethodDef tokens:
  `Execute` `0x0600115D`, `Detect` `0x0600132B`, predicate
  `0x06001359`, `ParseData` `0x06001160`, `DetectResult`
  constructor `0x060011BB`, and `Ecus` constructor `0x0600126D`.

**Interpretation of structural edges.** `newobj` in an obfuscated,
control-flow-flattened method is a callsite anchor only. Its presence cannot
prove object creation succeeded or that its source basic block is reachable.
Likewise, `Execute → ParseData` is an observed static callsite, **not**
proof that command data was accepted, `DetectResult` is populated or an ECU
list appears in VDASH. An absent edge in a selected or partial REA inspection
is `not observed`, not proof the instruction is absent from the DLL. These
tokens and offsets are meaningful only when matched to the **same exact
assembly build** as the saved IL excerpt. The available excerpt lacks a
verified original binary SHA, so the tool reports exact local matches without
automatically certifying version correspondence.

### Completeness gates for real REA runs

REA's published `managedMemberInspectionSchema` distinguishes the
assembly-wide coverage state from two **independent bounds**:

- `selection.type_names`: an explicit `--type` selection. Missing
  `Execute` or `ParseData` in that subset is **not** evidence that the
  corresponding MethodDef does not exist in the assembly. REA's current
  full-inventory schema represents no selection as an explicit
  `selection: null`. If this field is **omitted** by a historical or
  transformed report, `declaring_types=unreported`, never `all_types`.
- `method_rows.offset/count/total`: examined zero-based MethodDef rows
  **before** declaring-type filtering. If this is absent (historical reports)
  or names only a subset, the new `inspection_scope.method_rows` reports
  `unreported` or `page_only`, not `all_rows`.
- `coverage.state`: `partial` or `unavailable` does not establish
  complete source inventory even with all rows selected.

The exported `inspection_scope.all_members_examined` is `true`
**only** for a REA record that simultaneously attests complete coverage,
no declaring-type selection and the entire MethodDef row interval. This
describes reported **static inspection scope**, not an independently
verified match to the private VDASH 2.5.115.79 build, runtime reachability,
or successful ECU enumeration. An exact callsite from a partial report
remains an exact observation of the rows **returned**, not proof that the
complete graph has been decoded.

A second callsite gate now distinguishes an **edge row match**
(`exact_expected_sites` or `exact_expected_site`) from a **decoded caller
corroboration** (`decoded_caller_corroborated`). The latter is true only
when the same exact caller's local CIL decode is attested complete and the
expected call edge matches exactly. This does **not** prove that the
control-flow-flattened branch can be reached, that `ParseData` completed,
that `DetectResult.Ecus` was accepted, or that the recovered older IL
belongs to the same DLL build. A selected/paged report can show call edges
without a usable decoded caller, and will then report `false`.

The `method_bodies[].cil_decode` field is separate from REA's body
`status`. It returns `complete_decode_attested` only if the source
reports `status=present`, complete matching instruction counts,
`truncated_instructions=0`, an available 64-hex-digit normalized CIL
digest, and no issue. An omitted decode field yields `unreported`,
and an inconsistent/truncated/incomplete decode yields
`partial_or_unavailable`. The digest itself is **never exported**.
`complete_decode_attested` is a property of local static decoding,
not evidence that the method executed or produced usable
`DetectResult`/`Ecus`.

Eight additional **synthetic** tests validate full-vs-selected/paged
scope, missing historical row metadata, complete-versus-truncated CIL,
rejection of malformed counters and selections, and sanitization of
private type names/digests.

The checker limits input size and method/edge rows, rejects malformed method
tokens, mismatched identity and incomplete JSON structure, and refuses to
overwrite an output file. Its tests contain **synthetic** REA-shaped records
only; no proprietary VDASH data has been tested with REA in GitHub CI.

**Next genuine evidence gate:** once a real local REA observation exists,
confirm whether the methods are actually present and their type signatures
are readable, separately inspect the local implementation bodies and
reconstruct the `VddCommand.ResultData` → `DetectResult` → `Ecus`
path. Static method data cannot prove VDASH accepted the virtual ECU. Do not
fabricate CEM A3/A6/B9F0/B9FB/FC responses or infer normal-mode success.

## Recovered ParseData inventory: evidence available without the original DLL

A separate, private user-supplied `VDASH_Recovered_Methods_Inventory.json`
can be inspected **without** requiring REA or an original DLL. This inventory
reports details that earlier callsite-only research did not capture:

| Recovered method token | Inventory summary (VDASH 2.5.115.79) |
|---|---|
| `0x0600132B` (Detect) | 1746 IL bytes; 511 decoded opcodes; 0 decoder issues; two `MethodSpec 0x2B000002` calls and two `0x06001359` calls |
| `0x0600115D` (Execute) | 1073 IL bytes; 311 decoded opcodes; 0 issues; one direct `0x06001160` call |
| `0x06001160` (ParseData) | 550 IL bytes; **171 decoded opcodes; 0 issues**; four `get_ResultData`, two `RaiseEvent`, one `set_DataHash`; one call each to `<ParseData>b__88_0` and `<ParseData>b__1` |

These statements are **inventory metadata claims from the local recovered
archive**, not a newly decompiled body, execution proof, or confirmation of
successful CEM identification. A decoder reporting zero issues still does
not prove the obfuscated control-flow interpretation.

Run the new privacy-preserving offline inventory check from `emulator`,
leaving the full inventory in a private directory:

```powershell
py -3 .\tools\audit_recovered_inventory.py `
  (Join-Path $private 'VDASH_Recovered_Methods_Inventory.json') `
  --output (Join-Path $private 'recovered-inventory-summary.json')
```

If the actual original **or** reconstructed DLL subsequently becomes
available and REA has produced its full private member JSON, use a *new*
output path and opt into material hash matching:

```powershell
py -3 .\tools\audit_recovered_inventory.py `
  (Join-Path $private 'VDASH_Recovered_Methods_Inventory.json') `
  --rea-members (Join-Path $private 'members-private.json') `
  --output (Join-Path $private 'inventory-reconciled-summary.json')
```

The inventory records source ZIP and per-module source/recovered SHA-256,
which are **not published** by either script. A matching REA artifact digest
is reported as `matched_original_material` or
`matched_recovered_material`; a mismatch fails closed. A match against
the *original encrypted* DLL does **not** attest that MethodDef tokens in
the normalized recovered DLL have the same alignment, and a match against
the recovered DLL is not runtime acceptance evidence. This hash evidence
is recorded provenance asserted by the original inventory file, not an
independent new verification of the absent DLL. Do not paste private
raw JSON, archive hashes, original IL, paths or VIN into GitHub.

The dedicated inventory audit uses only known technical tokens and numeric
call counts. It never exports user-supplied method names, source paths,
digests, literal values or raw code. Eight synthetic tests cover the
observed G2 shape, original/recovered hash paths, mismatch rejection,
unknown methods, duplicate/malformed counters, sanitization and CLI
overwrite safety.

## Provenance

Implementation checks are based on REA's published
`docs/managed-code-analysis.md`,
`src/dotnet/ManagedMemberRows.ts` (`ManagedCallEdge` projection) and
`src/domain/managed/managedArtifact.ts` (the normalized member data schema)
as reviewed on 2026-11-03. REA is not vendored, downloaded, invoked or required
by the Virtual Car Windows x86 build. See
[`VDASH_IL_STATIC_AUDIT.md`](VDASH_IL_STATIC_AUDIT.md) for preceding, independently
recovered IL evidence.
