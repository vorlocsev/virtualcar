# B3A304 — Original BaseData.VehicleProfile: string keys and global NULL profile

Status: **Draft / offline regression**, 2026-11-18. Builds on B3A303 / Draft PR #367.

## Direct original evidence vs synthetic assumptions

An owner-local **read-only** SQL export of original VIDA 2014D
previously documented `BaseData.dbo.VehicleProfile` profile
`id=0c00c8af80205920`, `FolderLevel=0`, and nullable/empty
`fkVehicleModel`, `fkModelYear`, `fkEngine`, `fkTransmission` etc.
The join to original `DiagSwdlRepository.ScriptProfileMap` and the
`GetValidProfilesForSelected` FolderLevel=0 UNION was also examined.
Source: owner research `docs/research/vida-owner-readvin-global-profile-confirmed-2026-11-10.md`.

Do not confuse that 16-hex *BaseData* key with the numeric
`CarCom.T161_Profile.id` values 163119/163120/163191.
The original BaseData source may have a case-sensitive column name
requiring further owner-local schema confirmation; this fix targets
the already documented original **value shape**.

## Reproduced failures in earlier Drafts

Original-shaped local fixture (no database connection) produced:

- B3A301: `ProfileEvidenceError: invalid VehicleProfile key or folder level`
  because `_validate_profiles` required `type(Id) is int`.
- B3A302: `OfflineEvidenceError: invalid source profile key`
  because `_profiles` also required integer Id.
- B3A301 additionally rejected full table captures containing the
  *legitimate global FolderLevel=0* row with
  `fkVehicleModel=NULL`.

These failures arose despite B3A301 20/20 and B3A302 20/20
previous synthetic checks, which used invented numeric profile IDs
that did **not** reflect the original BaseData record format.

## Fix, deliberately minimal

1. Preserve exact original 16-character hexadecimal string
   `VehicleProfile.Id` (including leading zeroes and case).
   Do not convert to integer and **do not use CarCom numeric IDs**.
   Reject malformed/boolean/decimal identifiers rather than silently
   reinterpret key domains.
2. B3A301 accepts SQL NULL in `fkVehicleModel`. For a
   FolderLevel=0 row with all profile dimension FKs NULL,
   report `global_level0_profile_candidates_in_capture`
   **separately** from model-specific compatible candidates.
   Set `global_readvin_script_selection_verified=false`.
3. B3A302 accepts such global rows in the raw export but does
   not treat them as satisfying the open-source decoder's exact
   model/year/engine/transmission second filter.
4. All prior evidence limits remain: no claim of original runtime
   script selection, accepted VIN, ECU identification, or validated
   source SQL snapshot.

## Exact touched files

- `emulator/tools/vida_vin_vehicle_profile.py`
- `emulator/tests/test_vida_vin_vehicle_profile.py`
- `emulator/tools/vida_vin_public_disambiguation.py`
- `emulator/tests/test_vida_vin_public_disambiguation.py`

No original VIDA DLL, SQL or record was modified; all tests use
synthetic profile rows. The one public owner-confirmed literal global
profile key in regression tests is deliberately preserved unaltered
as documented; original private VINs/logs remain absent.

## Local verification

Focused synthetic B3A301 + B3A302 tests: **51/51 PASS**.
Together with unchanged B3A303 tests: **73/73 PASS**.
Python `compileall`: **PASS**.

Git blobs of locally tested corrected files:
- B3A301 tool: `6cd86fd6cddc696061e96eed629564624c2997e2`
- B3A301 test: `17204b54aaa877753dbd3ab1332cfbc3a18b964b`
- B3A302 tool: `10ab0bbe66055d0f72f6c9112cf2bca27593ea26`
- B3A302 test: `c01e1757b45d0921a9ba2c1546b9d65e2301eb2b`

Tests run in isolated local Python against no live VIDA DB or adapter.
**Exact-head CI, original BaseData export on this head, original GUI,
ReadVin, ECU-ID, T111/T122, physical J2534: NOT RUN/NOT ATTESTED**.

## Next proof gate

Use the unchanged read-only original catalog tool from Draft #317 to
capture real `BaseData.VehicleProfile` column names/types and the
specific target VIN's `VINDecodeModel` and `VINDecodeVariant` rows.
Confirm original session Partner Group, and compare owner-local
manual VIN versus virtual J2534 GUI outputs from B3A303.
No SQL UPDATE, DLL replacement or J2534-1 bypass of original VIDA
should be used as a proxy for acceptance.

This PR is stacked on B3A303 Draft #367: earlier Draft branches
#365/#366 are not mutated directly, and the fix is **not yet
integrated into development**. Rebase/stack resolution and retest
are required before any merge.
