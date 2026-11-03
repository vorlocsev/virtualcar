# VDASH 2.5.115.79: runtime anti-tamper fingerprint and read-only verification gate

**Status:** source-grounded static REA finding, **not** successful decryption or successful vehicle identification. Date: 2026-11-03. Private inputs: original user-supplied VDASH `portable.zip`, read-only REA results `metadata_probe_20261103_051302.zip`, and a historical recovered-method inventory matched to the same original binaries by SHA-256. None of those files or memory contents is committed.

## Six-assembly cross-check

Each row below comes from a real private REA **member** report after a reversible *metadata stream-count-only* normalization on a **nonexecuted copy**. It records MethodDef rows with nonzero RVA, the two intact fat-CIL bodies, and the historical encrypted-body recovery count. For six independently enumerated modules, `nonzero_rva - 2 == historical_recovered_count` **exactly**.

| Module | MethodDef | Nonzero RVA | Intact fat CIL | Previously reported recovered bodies | Equal |
|---|---:|---:|---:|---:|:---:|
| Client.Core.dll | 2,563 | 2,557 | 2 | 2,555 | Yes |
| Core.dll | 17,001 | 16,559 | 2 | 16,557 | Yes |
| Frontend.Client.Core.dll | 8,546 | 8,274 | 2 | 8,272 | Yes |
| Frontend.Core.dll | 810 | 726 | 2 | 724 | Yes |
| Vdash.Frontend.exe | 124 | 122 | 2 | 120 | Yes |
| Vdash.Monitor.exe | 480 | 478 | 2 | 476 | Yes |

`Frontend.exe` **cannot** be used as a seventh instance of this comparison: REA's probe exhausted the metadata representation budget and returned zero selected methods, while the historical recovered inventory reports 27,082 encrypted bodies. Zero selected methods is **not** zero actual methods.

In all six modules, the only intact fat-CIL MethodDefs are `<Module>..cctor` (`0x06000001`) and an obfuscated method `0x0600000D`. The remainder with nonzero RVAs is largely undecodable. REA labels a small fraction of these opaque-section bytes `body.status=present` with **tiny** headers, but very short random opcode-looking fragments are not reliable evidence of executable method bodies. Only the two intact **fat** method bodies have been independently verified as consistent shared loader candidates.

## Specific static evidence for a loader

The following *each* holds in all six recovered REA member reports:

1. `<Module>..cctor` begins with `IL_0000 call 0x0600000D`.
2. `0x0600000D` returns `void`, has a fully parsed fat CIL body, and calls `GetTypeFromHandle`, `Module.FullyQualifiedName`, and `Marshal.GetHINSTANCE`.
3. `0x0600000D` calls `0x0600000C`, a P/Invoke MethodDef with no RVA and the decoded signature `bool(native-int, u4, u4, u4&)`, matching the parameter shape of Windows `VirtualProtect`. The actual import name has **not** been independently attested.
4. The larger module initializer calls `Marshal.Copy`, `MethodBase.Invoke`, `Environment.FailFast`, and creates/starts a background thread. Obfuscated branches do not prove when each call runs.
5. The protected assemblies have a nonstandard first PE section containing most protected method RVAs; the two legitimate fat bodies are in a separate `.text` section.

The overall shape closely **resembles ConfuserEx-style Normal anti-tamper**, which scans PE sections, changes protection on an encrypted region and restores method IL during module initialization. See the archived original reference implementation: https://github.com/yck1509/ConfuserEx/blob/master/Confuser.Runtime/AntiTamper.Normal.cs and the separate open-source unpacker research https://github.com/XenocodeRCE/ConfuserEx-Unpacker/blob/master/ConfuserEx%20Dynamic%20Unpacker/Protections/AntiTamper.cs. Similarity is **not** proof of the exact protector, variant, derivation key, successful runtime decryption, or authorized decompilation.

## G2 next gate: observe only whether loaded code changes

A private, operator-side Windows PowerShell read-only probe compares 64 **code** bytes in the running **original** `Frontend.Client.Core.dll` image against the corresponding file bytes at seven source-grounded method RVAs:

- two plaintext loader candidates `0x06000001`, `0x0600000D`;
- `0x0600117A`, `0x0600117B`, `ParseData 0x06001160`;
- `VddModel.Detect 0x0600132B`, and predicate `0x06001359`.

The probe first verifies the exact original DLL SHA-256, uses `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION`, and **does not** inject code, call any VDASH methods, launch VDASH, write into the target, or persist memory bytes. Its only output is a small private JSON containing `changed_vs_disk` and a *candidate* tiny/fat CIL header class for each sample. It must run on the **original** application image, never the metadata-probe normalized DLL copies. VMware snapshot and no physical J2534 recommended.

**Interpretation:**
- `changed_vs_disk=true` plus newly plausible CIL headers at several targets would **support** in-memory modification after module initialization, not prove full method recovery.
- Unchanged bytes **do not disprove** anti-tamper, e.g. if the CLR has not initialized the module or it uses JIT-time replacement.
- Actual decoded instruction bodies, logical condition checks and client acceptance of a virtual CEM remain **unverified**. Next analysis should be driven by a new concrete observation instead of more synthetic test count.

## Separation of concerns

This document is research-only and does not alter CAN, J2534, CEM synthetic replies, Virtual Car Stable/Development or release publication. Physical J2534 and a real VDASH vehicle-identification session remain untested.
