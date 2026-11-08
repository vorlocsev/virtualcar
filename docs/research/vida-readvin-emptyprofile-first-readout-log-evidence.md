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
