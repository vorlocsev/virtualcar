# VIDA P0: first-ReadVin EMPTYPROFILE selection and J2534 evidence boundary

Date: 2026-11-08. Research-only, read-only. No new ECU responses,
fake VIN or updates to the Virtual Car emulator.

## Independent source evidence

1. The owner's **original** `BizServices.ScriptRepository.DLL` has
   SHA-256 `f046b5fa3c8d3487fc05aa1140ac3c4ef1880eef5251c8c46b1c3d73f45a6bca`.
   Independently tested six bounded static CLR metadata/IL checks:
   **6/6 PASS**; no original assembly executed. The original
   `ScriptProvider.GetFromDb` (MethodDef `0x0600001E`) issues
   stored procedure `GetScript` with **five exact parameter
   names**: `@scriptType`, `@profileList`, `@scriptId`,
   `@languageCode`, `@ecuType`. It can use
   `IsScriptOnDisk` as an alternative. `GetZippedScriptXml`
   (`0x0600001F`) reads SQL binary, decompresses and parses XML.
   Existence of an extracted `ScriptContent` ZIP does not
   establish which variant `GetScript` returned at runtime.
2. Public repository
   https://github.com/spnda/volvo_vida_db
   at original reviewed commit `e2f8ee165e373360d7f7fd0e80298f68c25bc07e`:
   `sql/extract_scripts.ps1` exports `ScriptContent` for
   language 15 and metadata from `Script`, `ScriptType`,
   `ScriptProfileMap`, `ScriptVariant`; its `filter_scripts.py`
   filters using VIN-dependent profile joins. This is **not**
   a runtime emulation of `GetScript` nor confirmation of
   the bootstrap ReadVin profile.
3. Independent **published third-party** VIDA 2014D log:
   https://www.motor-talk.de/forum/obdii-volvo-vida-dice-t3858075.html?page=180
   The displayed session selects **ReadVin with
   `Profile: 'EMPTYPROFILE,'`, `EcuType: '-1'`** before
   identifying the car, and fetches script
   `VCC-225200-1 1.8`, titled "Read VIN first readout
   (Odometer Value) (No immo check)". The log shows
   attempts on CAN ID `0x726` with request `22 F1 14`
   and D2 requests `CB 40 B9 FB 00 00 00 00` and
   `CB 50 B9 FB 00 00 00 00` on CAN ID `0x000FFFFE`.
   Adapter echo/TRANSMITTED FRAME indication is **not**
   ECU reply; the published attempts end in
   `ERR_BUFFER_EMPTY`, **not successful VIN identification**.
   That specific example is for a different vehicle,
   **not an XC90 V8 MY2009 confirmation**.
4. Independent public observations in
   https://jan-jansen.readthedocs.io/en/latest/vin.html
   describe the ReadVin bootstrap and `22 F1 14`.
   This does not resolve the user's actual script
   or VIN acceptance.

## Consequence for the emulator

The **first** ReadVin attempt need not have a VIN-specific
vehicle profile. Therefore using XC90 V8 profile matching as
a prerequisite for startup script selection is not proven
correct; first distinguish `EMPTYPROFILE` bootstrap from
later VIN/profile-dependent identification.

The existing Virtual Car source recognizes the exact
`0x000FFFFE` D2 `CB 40/50 B9 FB` request envelopes
but emits a B9FB reply only when a verified fixture is
configured. Its P3 `22 F1 14` probing path also cannot
supply an accepted VIN without valid source evidence.
Do not synthesize D2 `F9 FB` or UDS `62 F1 14`
payloads based solely on a TX log or an XML method name.

## Private-log classifier

`emulator/tools/audit_vida_readvin_bootstrap_trace.py`
accepts one owner-authorized **local** plain text VIDA log.
It is bounded and outputs only categorical counters. It
keeps `Starting new logsession` boundaries, recognizes
the published `ReadVin/EMPTYPROFILE` selection, observed
`VehComm` requests and J2534 **TX** shapes, distinguishes
short RX-direction echo from possible positive RX prefixes,
and counts `ERR_BUFFER_EMPTY`. It never includes any
VIN, node identifier, raw CAN data, original line, file name,
path, authentication data or original XML in the JSON.

Important: this tool is NOT a complete J2534 protocol
decoder. Log lines may be interleaved, and a positive-looking
prefix is not a validated ECU reply or an accepted VIN.
The tool deliberately fixes runtime ECU, VIN, GetScript SQL
selection and replay approval flags to **false**.

Example offline command:
`py -3 emulator/tools/audit_vida_readvin_bootstrap_trace.py C:\VIDA-private\VIDA.log --output C:\VIDA-private\bootstrap.redacted.json`

**12/12 local synthetic Python regressions PASS**.
Test input is entirely synthetic; no third-party source log,
private car log, real VIN or copyrighted DLL is committed.
Git blob SHA1 of locally tested source:
`eb20ab563584a3ad570dd40b1bd8cb342d7f542f`;
tests: `aef6bcbfb92c92412fe7b8e175056429731240a8`.

## Unresolved evidence and next steps

- Obtain selected original private `ReadVin` XML **and** the
  corresponding `GetScript` metadata for the **same** owner
  VIDA installation. Do not treat `VCC-225200-1` as a
  database `fkScript` without a verified mapping.
- Confirm the exact `ReadVin.Result → ResultGet.InValue →
  AddVIN` script path and service identifiers from original
  data, not a synthesized test XML.
- Require same-session actual ECU reply and independent
  client VIN acceptance evidence before enabling any
  emulator reply. The published external session reports
  failures, not a usable B9FB response fixture.
- Do not publish database passwords or SQL export
  configurations from third-party repositories.
- Owner-only Windows VMware workflow has not run on
  this research commit. Keep PR Draft; no runtime or
  release changes.

## Why literal B9FB may be absent in one ReadVin XML

A second set of original-source static tests was executed against the
owner's same SHA-pinned `BizServices.Scripting.DLL`:
**4/4 MethodDef path assertions PASS**, without executing the binary:

- `ReadVinComponent.PropertySetup` (0x06000424) registers
  `CanHiSpeedValue`, `UseRelay`, `BusId`, `Identifier`,
  `Mode` and `EcuVariant` properties. It inherits further
  `VehCommBase` properties, including `ServiceId`.
- `ReadVinComponent.Execute` (0x06000426) reads
  `CanHiSpeedValue` and `UseRelay`, sets up the communication
  provider, adds `Identifier` as a service parameter,
  calls `SetupTester`, then `VehCommBase.executeService`.
- `VehCommBase.setupVehComm` (0x0600041D) reads `ServiceId`,
  chooses communication context through `Mode` and
  `CreateFromEcuVariant`/`CreateFromEcuType`/
  `CreateFromEcuAddress`.
- `VehCommBase.executeService` (0x06000420) calls the provider's
  service `Execute`, stores a response object with
  `set_Result`, then dispatches status-dependent delegates.

This gives a code-grounded explanation for a critical analysis
pitfall: **the script's literal XML need not contain the full
CAN request `B9 FB`**. Service selection plus `Identifier`
are interpreted by the diagnostic provider. One original
redacted XML summary happened to contain lexical `F114`
but not `B9FB`. That difference is not evidence that its
runtime cannot issue `B9FB`, nor proof that it does.

The next missing source is therefore the **exact**
`ReadVin` script's **`ServiceId`, `Mode`, `Identifier`
declarations and property handlers**, reconciled with the
`T111_Service` definition and selected ECU configuration
from the *same* VIDA installation. The public `spnda`
exporter can extract those tables, but this research PR
does not have the owner's private selected ReadVin ZIP or
SQL procedure result and cannot claim their values.

No inferred `F9 FB` or `62 F1 14` positive payload
will be enabled in the emulator from this static evidence.

## Original ServiceId → CarCom service catalog: next static evidence gate (2026-11-08)

Original **SHA-verified owner DLLs** were inspected via a local
read-only CLR metadata/IL reader, *never executed*:

- `BizServices.Scripting.DLL` SHA256
  `d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028`.
  `VehCommBase.setupVehComm` MethodDef `0x0600041D`
  reads the script node's `ServiceId` and chooses the
  provider context by `EcuVariant`, `EcuType`, or
  `EcuAddress`. `ReadVinComponent.Execute`
  `0x06000426` adds `Identifier` as a service parameter,
  then calls the diagnostic service's `Execute`.
- `BizServices.CarCom.VehicleServices.DLL` SHA256
  `1735d8ac20d63a20afe13742ea5156cce5a5328392bd3e44d9ec3cd8ae0dbd07`.
  `SPService.GetService` `0x06000073` calls
  stored procedure **`service_GetService`**, passing
  **`@service`**; reads `service`, `mode`, `name`,
  `description`, and binary `definition` fields,
  then constructs `<service>` XML. A distinct
  `SPService.getServiceFromFile` `0x06000070`
  can read a local **`VehicleServices.xml`** catalog.
- **7/7 local SHA256 and MethodDef feature gates passed**
  on both original DLLs.
- Independently checked public `spnda/volvo_vida_db`
  `sql/extract_services.ps1`: exports the
  `carcom.T111_Service` **`id`** column and
  `service/mode` metadata as CSV, with definitions
  stored in separate extracted XML files. This is a
  convenient local reference schema, but its SQL
  implementation of **`service_GetService`** was
  not reviewed here.

Created a **new standalone private-source classifier**, distributed
only as a user-visible ZIP in this research conversation, *not
committed as executable source in this PR yet*. It accepts
one private selected ReadVin XML ZIP and the same-installation
`T111_Service.csv`, and counts direct `ServiceId` Int
declarations, candidate T111 ID matches, dynamic/duplicate
declarations and any enabled `propertyhandler` setters
into `ReadVin.ServiceId` or `Identifier`. It emits
**only categorical counters and fixed false runtime flags**:
no literal numeric ServiceId, Identifier values, VIN,
ECU addresses, source XML or row text. The offline tool
was locally verified **10/10 synthetic unit tests PASS**.
The ZIP is byte-checked, contains source/tests/README/SHA256
and has SHA256
`aa18692a9cbf2e9857ddd23997221781902aba7898419e100b8eb2d65f487066`.

**Crucial limitation:** an XML `ServiceId=23` matched to
a T111 row `id=23` is *only* a static catalog candidate;
it does NOT establish the actual service selected at runtime,
its `service/mode` wire payload, the ECU configuration,
GetScript selection, a CEM response, VIN acceptance or a
suitable emulator replay fixture. Both original private
selected ReadVin XML and owner T111 CSV are **not available**
to this new checker here; no actual match reported.

No emulator/J2534/CEM changes; the PR remains Draft and
exact-head Windows CI has not executed.

## Public literal ReadVin property example, not the owner's selected script

An independently accessible public technical write-up
https://jan-jansen.readthedocs.io/en/latest/vin.html
quotes a `Components.ReadVinComponent` XML node from
its own observed first-readout script. It reports these
**source-declared properties** (not an owner-car trace):

- `ServiceId`: `class="Int"`, literal value `100`.
- `Identifier`: `class="String"`, literal value `F114`.
- `Mode`: `class="String"`, literal value `EcuVariant`.
- `CanHiSpeedValue`: `500000` and `BusId`: `1`,
  which are script configuration declarations, not
  validated target XC90 V8 communication.

The external site also reproduces the published
`ReadVin/EMPTYPROFILE` first-readout selection. The
`ServiceId=100` example provides a **real public XML
shape** for our safe static catalog join, NOT proof that
`T111_Service.id=100` exists in the owner's installation
or what its `service/mode/definition` bytes are. The
`Identifier=F114` string is **not** a complete 0x22 or
0xB9 CAN request; the selected CarCom service and
ECU communication context are required.

For comparison, the owner's locally available
`VIDA.log.txt`, `server.log.txt` and
`db_attach_log.txt` were searched *privately* for
`ReadVin`, `GetScript` and `service_GetService`:
**zero matching lines** in these three already-supplied
startup/database-install logs. The new bootstrap
analyzer yielded **0 tracked sessions** on
`VIDA.log.txt`. This is a limitation of the available
log sample and does **not** prove VIDA never started
ReadVin, nor that a vehicle failed identification.
No raw log text, names, paths or credentials are
uploaded here.

Before any claim of real target CEM behavior, the same
owner-selected `ReadVin` XML and `T111_Service.csv`,
plus its corresponding `extracted_services/<id>.xml`,
must be matched with actual GetScript selection and
same-session ECU RX. An absent service row or a
`VehicleServices.xml` fallback likewise changes
interpretation. No synthetic F114/B9FB response is
authorized by this static metadata evidence.
