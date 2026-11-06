# Stage 47 | VIDA 2015A script identity and ECU identification boundaries

Read-only static IL research from the user's original VIDA directory:
`ai/VirtualCar/Distributions/VIDA/jboss/standalone/deployments/VidaEar.ear/VidaWeb.war/Diagnostics/`.
**No executable was run**, and no original DLL, personal VIN, original test payload or proprietary
car configuration data is checked into this repository.

## Verified original-binary hashes and methods

| DLL | SHA-256 |
|---|---|
| `AppServices.VehicleAccess.DLL` | `3bcaac2ce2dbe0b986a1c8588bbe3d75fe579bb41bb1eada759ccdb7214545a0` |
| `AppServices.Scripting.DLL` | `c5f092eddceac8b9eb583fb9a54536d482402a64797bd3597fd0cc6b387f3b7f` |
| `BizServices.Scripting.DLL` | `d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028` |
| `BizServices.VehicleResolver.DLL` | `31d107b0ca13ae22a2c2f3893c76d38550ac3ce160648d07888866ddafe46720` |
| `BizServices.CarCom.VehicleServices.DLL` | `1735d8ac20d63a20afe13742ea5156cce5a5328392bd3e44d9ec3cd8ae0dbd07` |

### Identity stage in the actual VIDA IL

1. `AppServices.VehicleAccess.DLL` MethodDef `0x060000ED`, `VehicleAccess.IdentifyVehicle`:
   temporarily selects an empty `VehicleProfile`, calls `IRunScriptService.RunIdentifyVehicleScript`,
   calls `VehicleIdentityOutput.GetIdentity`; null/empty branches to `VinException`. A returned
   identity is wrapped in `VehicleIdentity` with `IsIdentityVin = !Get_IsX40`.
2. `AppServices.Scripting.DLL` MethodDef `0x06000071`, `RunScriptService.RunIdentifyVehicleScript`:
   gets a script engine without a selected ECU context (the IL supplies constant `4`),
   invokes `IScriptEngine.RunScript` and `GetOutput`, casts to `VehicleIdentityOutput`.
   **This method alone does not identify the script's SQL/XML contents or prove a B9FB request.**
3. `BizServices.Scripting.DLL` MethodDefs `0x0600037D`/`0x0600037E`/`0x0600037F`:
   `VehicleIdentityOutput.AddVIN` stores a value; `SetX40Serial` stores a value and sets
   `IsX40` true; `GetIdentity` retrieves the stored value. These methods do not
   validate the VIN or year. `Get_IsX40` returns its separate flag.
4. `AppServices.VehicleAccess.DLL` MethodDef `0x06000104`, `VehicleIdentity..ctor`:
   creates a two-character trim set (`0x0A`, `0x0D`) and uses `String.TrimEnd`.
   The original NUnit `VehicleIdentityWithCrLfTest` (MethodDef `0x060000B5`)
   verifies the ending CRLF is removed. **The trim does not prove any other field is valid.**
5. `BizServices.VehicleResolver.DLL` MethodDefs `0x06000015`, `0x06000017`,
   `0x06000019`: `ResolveVin` first invokes `VinValidator.IsValidVIN`;
   another overload invokes a database stored procedure and maps data into
   vehicle/profile objects. `ProfileFromVin` uses `ResolveVin`,
   `CreateVehicleProfile` and an empty-profile fallback. The examined
   `VehicleAccess.IdentifyVehicle` method **does not call `ResolveVin` directly**.
6. `AppServices.VehicleAccess.DLL` MethodDef `0x060000E7`,
   `PerformEcuIdentification`: selects ECU-identification scripts via
   `ScriptObjectProvider.GetEcuIdentificationScript`, independently of the
   `IdentifyVehicle` entry-point's returned `VehicleIdentity` object.
7. `BizServices.Scripting.DLL` MethodDef `0x060002F5`,
   `MecuReadoutOutput.AddVehicleInfoParam` collects a named parameter and
   display value. It does not define a universal B9FB field schema.

## Why this matters for Virtual Car

The confirmed code path is *script output -> identity object*; a separately
observed J2534 B9FB transport success is not enough to prove that the
script produced an identity. The real SQL/XML script, its exact B9FB/B9F0
dependencies, client timings and parser conditions have not been recovered
in this stage. An `IsIdentityVin` property alone is not `VinValidator`
approval, a valid profile, ECU reachability, or SectorV normal-mode acceptance.

### Reproducible privacy-safe audit

`emulator/tools/audit_vida_identity_boundary.py` consumes a strictly
allowlisted **manually curated categorical JSON** for a single lab client run.
It does not parse raw logs or receive VIN. Example:

~~~json
{ "schema_version": "virtualcar-vida-identity-boundary-v1",
  "application": "VIDA2015A",
  "run_scope": "same_client_run",
  "evidence_source": "human_reviewed_lab_summary",
  "stages": { "b9fb_transport": "complete",
              "identify_script": "not_observed",
              "vin_resolver": "not_observed",
              "ecu_identification": "not_observed" },
  "is_x40": null }
~~~

~~~bash
python emulator/tools/audit_vida_identity_boundary.py SAFE-example.json --output NEW-report.json
~~~

The output is a status-only observation, **not a verified client run**.
No identity, payload, host path, identifier hash or source data is emitted.
Eight synthetic regression groups check transport-only, missing identity
exception path, identity with/without X40 flag, independent VIN resolver,
independent ECU response, rejection of raw/foreign data, no-overwrite CLI.

## Offline evidence and limits

An independent local static verifier checked **8/8 IL invariants** against
these precise original SHA-256 binaries; report JSON remains local and
is not shipped with DLLs or identifying constants.

**Not established:** the actual SQL/XML `RunIdentifyVehicleScript` for
XC90 V8 MY2009, a literal B9FB->identity mapping, VIN checksum,
application B9FB CRC, normal-mode acceptance, a correct CEM A3/E3 response,
or physical DiCE/VIDA/SectorV success. All replay remains disallowed;
Virtual Car release publication remains disallowed.

Related: [Stage46 VIDA B9FB matcher](p2-vida-b9fb-matcher-il.md),
[Stage45 SectorV normal-mode evidence](sectorv-normal-mode-gate-evidence.md),
[Issue #4](https://github.com/vorlocsev/virtualcar/issues/4).
