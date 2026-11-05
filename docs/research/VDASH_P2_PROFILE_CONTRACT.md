# VDASH P2 profile contract: offline read-only configuration audit

Date: 2026-11-03. Scope: Virtual Car synthetic configuration and reproducible
unit tests in Draft PR #39, without VMware or physical J2534 testing.

## The exact source-state distinction

Two checked-in sample INI profiles are **not equivalent**:

| File | Verified static facts | Boundary |
| --- | --- | --- |
| emulator/virtualcar-vdash-lab.ini | Has ECUCount=2, OBD 0x7E0/0x7E8 and P3 0x726/0x72E routes. D2_40 and D2_50 both declare B9FBFrameCount=0. | A mixed P2/P3 synthetic laboratory profile, not an authentic XC90 P2 V8 MY2009 CEM. |
| emulator/virtualcar-p2.ini | Has ECUCount=1, P2.StrictRouting=1, generic OBD route and no P3 0x726/0x72E route. D2 B9FB, B9F0 and B9FC sections declare 0 frames. | A strict P2 read-only testing scaffold, not a complete recognized CEM fixture. |

No B9FB frame is newly supplied or invented. A count of zero is evidence of a configured empty fixture **only**, not proof VDASH asked for that service. Zero cannot be used as proof of a disabled hardware ECU, a lost CAN response, or a failed VIN.

## New bounded audit

The new program emulator/tools/audit_vdash_profile_contract.py reads **only** a local INI text file and emits a JSON report consisting of:
- declared ECUCount and number/contiguity of indexed ECU sections;
- configured P2.StrictRouting flag, if present;
- existence of exact P3 0x726/0x72E and generic OBD 0x7E0/0x7E8 routes;
- for each target 40/50 and service B9FB/B9F0/B9FC: unreported, zero_declared or nonzero_unverified;
- one bounded research-focus label, all verification flags false.

It never returns an original VIN, ECU PartNumber, private hexadecimal frame, file path, keys, arbitrary string or raw J2534 data.

Possible labels:
- mixed_p2_p3_lab_configuration: both P3 route and a declared D2 count in one profile; warns about evidence scope, not a proven collision.
- strict_p2_no_d2_read_fixtures: strict routing but none of the six relevant D2 service-target pairs declares a nonzero frame count.
- strict_p2_with_p3_route_unverified: a P3 route appears despite P2 strict mode; no runtime failure is asserted.
- declared_d2_frames_need_source_validation: at least one nonzero declared count; bytes, vehicle, and source provenance remain unchecked.
- ecu_count_mismatch: ECUCount differs from a contiguous zero-based sequence of indexed ECU sections.
- configuration_only_no_acceptance_evidence: no stronger statement supported.

Use locally, from repository root:

~~~powershell
py -3 .\emulator\tools\audit_vdash_profile_contract.py .\emulator\virtualcar-vdash-lab.ini --output "$env:TEMP\vc-vdash-lab-profile-audit.json"
py -3 .\emulator\tools\audit_vdash_profile_contract.py .\emulator\virtualcar-p2.ini --output "$env:TEMP\vc-p2-profile-audit.json"
~~~

Outputs must not already exist. The audit refuses malformed counts, duplicate INI properties, invalid CAN IDs, and zero-count sections with an explicit FrameN entry. Nothing is written to the source configuration file.

## Relation to VDASH IL evidence

VDASH portable 2.5.115.79 static research has located VddModel.Detect,
DetectResult.Units, loader-related source sites, Model_DetectDone's indexed
InitializeUnits call, and four module-specific RefreshAvailability callsites.
It has **not** recovered the target bodies or proven that VDASH 2.0 and
2.5.115.79 follow the same recognition path. A missing authentic P2 D2
fixture is one limitation of the emulator test profile, but not the proven
reason for empty ECU UI, failed J2534 connection, or any model-year mismatch.

Eight synthetic test groups cover the two repository sample configurations,
missing D2 evidence, declared but unauthenticated frames, mixed strict P2/P3
routes, invalid inputs, ECU-count mismatch and privacy-safe CLI output.

**CI policy:** VMware LAB is skipped on this research PR. Ordinary Windows x86
compilation, Python/C/Go synthetic tests and native route checks remain active.
No real VDASH, actual Volvo hardware, programming, PIN or release is involved.
