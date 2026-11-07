# VIDA 2015A: VIN versus X40 identity result and ECU inventory boundaries

**2026-11-07, original-source static analysis only.**
This note extends the verified `ScriptType.ReadVin=4` selection and
categorical script-run evidence. It does **not** reconstruct the
proprietary `ReadVin` XML, assert an ECU reply or certify a
MY2009 XC90 V8.

## Original binaries (private, SHA-256 verified)

- `AppServices.VehicleAccess.DLL`:
  `3bcaac2ce2dbe0b986a1c8588bbe3d75fe579bb41bb1eada759ccdb7214545a0`
- `BizServices.Scripting.DLL`:
  `d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028`

The original DLLs remain off GitHub. The research only checks
bounded CLR MethodDef instructions/call names and known field
accesses. It does not execute or redistribute the modules.

## What the original implementation actually does

| Source method | Verified static behavior | Not proven |
| --- | --- | --- |
| `VehicleIdentityOutput.AddVIN` (MethodDef `0x0600037D`) | Assigns the supplied string to the identity field | That the string is a valid 17-character VIN; no format check occurs in this method |
| `VehicleIdentityOutput.SetX40Serial` (`0x0600037E`) | Sets `IsX40=true` and assigns the supplied X40 serial to **the same identity field** | That the target vehicle is X40 or that any specific script calls this branch |
| `VehicleIdentityOutput.GetIdentity` (`0x0600037F`) | Returns the shared stored identity | That the value came from a CEM response |
| `VehicleIdentityOutput.get_IsX40` (`0x06000380`) | Reads a separate boolean flag | That its value corresponds to actual transport evidence |
| `VehicleAccess.IdentifyVehicle` (`0x060000ED`) | Temporarily selects `VehicleProfile.Empty`, executes `RunIdentifyVehicleScript`, obtains identity and X40 flag, constructs `VehicleIdentity`, and restores the prior profile via the method's cleanup path | That this path succeeded in an actual MY2009 session |
| `VehicleIdentity..ctor` (`0x06000104`) | For non-null input, trims **trailing carriage return and line feed** and preserves the caller-supplied identity-is-VIN flag | That any other character or semantic VIN validation occurs here |

**Order matters:** `SetX40Serial` overwrites any identity string
previously stored by `AddVIN`. Conversely, `AddVIN` does **not**
reset the `IsX40` flag. The code should not be simplified to
"the last AddVIN call proves a VIN" without observing the actual
script path and flag. It is an important distinction between
**identity string present**, **identity type**, and **VIN accepted**.

In `VehicleAccess.IdentifyVehicle`, a null identity after the
script produces a `VinException` construction path. The
`VehicleIdentity` constructor is supplied a boolean equivalent to
`not IsX40`; the boolean is therefore separate from the returned
identity characters. The static branch does not demonstrate any
positive CEM response, VIN checksum validation or automotive
communications.

The original assembly contains **mock-oriented test methods** named
`OkVinTest`, `ThrowsExceptionWhenVinCannotBeReadFromVehicle`,
`NoVinX40Test`, and `VehicleIdentityWithCrLfTest`.
Their code sets up artificial `VehicleIdentityOutput` values and
checks results. Their *presence* is useful confirmation of intended
branches, **not evidence that a real DiCE/VIDA session passed**.

## ECU readout is a separate stage with three distinct categories

Original `ScriptOutputConverter` in
`AppServices.VehicleAccess.DLL` distinguishes:

- `GetAliveEcus`: obtains results from
  `EcuIdentificationOutput.GetAliveEcus`, consults CarCom for
  a matching ECU variant and constructs ECU information.
- `GetNotAliveEcus`: processes a **different source collection**
  and can consult a **default ECU variant** from CarCom.
  A default row in the VIDA database is not a received
  positive ECU identification.
- `GetNotPresentEcus`: derives information from
  `MecuReadoutOutput.GetNotInConfigEcus`.
  A module absent from a profile/configuration is **not** identical
  to a physically present ECU that failed to answer.

The names of the original getters and the distinct call paths
are confirmed. The real 2015A database profile and the target
model-year ECU list are **not** confirmed. No positive ECU
response, hardware state or actual vehicle is implied.

## Eight completed independent source-only checks

The following checks were executed *locally* against the two
unmodified original DLLs, with **8/8 PASS**:

1. Both source DLL SHA-256 values equal the exact pinned hashes.
2. `AddVIN` writes the shared identity field.
3. `SetX40Serial` writes the X40 flag and overwrites the same field.
4. Identity and X40 getters read distinct fields.
5. `VehicleAccess.IdentifyVehicle` invokes the identity script
   and reads both output fields before constructing a result.
6. Null-identity exception path and relevant original mock test
   method names exist.
7. The result boolean is derived from `not IsX40`;
   the constructor performs only CR/LF trimming.
8. Script output conversion has three independent ECU collection
   paths, including a default-CarCom fallback for not-alive ECU.

These are **offline static checks**, not tests that execute the
original VIDA code or a current project Windows/VMware CI run.
No proprietary IL body, original test strings, VIN or ECU data
has been committed.

## Practical diagnostic consequence

For the Virtual Car P0 reader and any future independent VIDA
trace, **keep these states separate**:

```text
ReadVin GetScript lookup
    -> script fetched
    -> script run
    -> VehicleIdentityOutput: string present / null
    -> identity type: VIN / X40 serial / unknown
    -> resolver accepted vehicle: confirmed / denied / unknown
    -> ECU identification run
    -> ECU class: alive / not-alive / not-in-configuration / unknown
```

A `ReadVin` event triple, a B9FB `delivered` J2534
frame, a non-null X40 serial or an ECU expected in CarCom **must not**
promote `vin_accepted` or `ecu_identification_accepted` to true.

For a real authorized VIDA2015A observation, the missing gates are
still the returned `GetScript(ReadVin=4)` XML and its execution,
normal-mode/ignition predicate, effective DiCE/connection routing,
and private same-run client confirmation. The older public
VIDA2014D S40 fallback log and partial ReadVinComponent XML
are context, **not** target MY2009 proof:
[existing research](vida-readvin-2014d-public-fallback-chronology.md).

Do not add synthetic A3/E3, PIN/security challenge, ECU coding,
firmware writes, a J2534 driver or a published Virtual Car build.
