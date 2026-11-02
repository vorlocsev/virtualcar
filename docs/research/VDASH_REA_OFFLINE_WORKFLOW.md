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
npm install --global rea-agents
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
- Inspection status (`present`, `partial`, `absent`, `malformed` or
  `not_inspected`) for five explicitly selected MethodDef tokens:
  `Detect` `0x0600132B`, predicate `0x06001359`, `ParseData`
  `0x06001160`, `DetectResult` constructor `0x060011BB`, and
  `Ecus` constructor `0x0600126D`.

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

## Provenance

Implementation checks are based on REA's published
`docs/managed-code-analysis.md`,
`src/dotnet/ManagedMemberRows.ts` (`ManagedCallEdge` projection) and
`src/domain/managed/managedArtifact.ts` (the normalized member data schema)
as reviewed on 2026-11-03. REA is not vendored, downloaded, invoked or required
by the Virtual Car Windows x86 build. See
[`VDASH_IL_STATIC_AUDIT.md`](VDASH_IL_STATIC_AUDIT.md) for preceding, independently
recovered IL evidence.
