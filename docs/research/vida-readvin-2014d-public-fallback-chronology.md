# VIDA ReadVin: SQL row-selection semantics and published D2 fallback chronology

**Scope:** read-only XC90 V8 MY2009 Virtual Car research. The original
VIDA 2015A DLL source and an independently published **2014D** log
provide different kinds of evidence. Neither is a complete successful
2015A/MY2009 vehicle session.

## Original VIDA 2015A: first SQL XML returned, not all candidates

Original `BizServices.ScriptRepository.DLL` SHA-256:
`f046b5fa3c8d3487fc05aa1140ac3c4ef1880eef5251c8c46b1c3d73f45a6bca`.
Eight *local source-only* checks of actual managed IL **8/8 PASS**:

1. Original SHA-256 verified.
2. `RunIdentifyVehicleScript` uses `ScriptType.ReadVin = 4` and a
   no-ECU-context script engine.
3. Five-argument `ScriptProvider.GetScript` calls
   `GetOneScriptFromDb`.
4. `GetOneScriptFromDb` calls `GetFromDb`, checks array length
   and returns **the first array element** when nonempty.
5. If `GetFromDb` returns an empty array, the wrapper returns null.
6. `GetFromDb` uses `StoredProcedureHelper`,
   `SqlDataReaderWrapper.HasRows` and `Read`.
7. It can aggregate XML results into an `ArrayList` and call
   `ToArray`. A no-rows branch can instead throw
   `ScriptMissingException`; this differs from an empty result
   propagated through the wrapper.
8. `GetZippedScriptXml` reads SQL binary, decompresses through
   `ZIP.DecompressString`, and passes the result to
   `XmlDocument.LoadXml`.

This is **static call/branch evidence**. The stored procedure's SQL
definition, ordering, selected row and actual XML content remain
unknown. An aggregate count of all `ReadVin` script records is
therefore insufficient to prove which XML VIDA selects. The program
was not executed and no original bytes, credentials, script IDs,
VIN, response payloads or private logs enter the repository.

## Independently observed VIDA 2014D log, 2025-12-04

Public source: [Matthews Volvo Site, VIDA / VXDIAG discussion, page 2](https://www.matthewsvolvosite.com/forums/viewtopic.php?start=10&t=102268).
The publisher describes a **2003 S40** and a VXDIAG VCX NANO, not
the target XC90 V8 MY2009. The actual log identifies VIDA **2014D**.

The following is **metadata-only chronology** from that published
read-only diagnostic attempt. No original CAN payloads, ECU serials,
VINs or tool serials are reproduced.

| Stage | Independently observed source outcome |
| --- | --- |
| Script lookup | `DiagSwdlRepository / GetScript`, `Type=ReadVin`, `Profile=EMPTYPROFILE`; subsequent `Fetched script` and `Running script` in the same log thread |
| Script version | Public trace gives `VCC-225200-1` version `1.8`; this is an external 2014D log observation, **not** a verified 2015A selection |
| First diagnostic probe | ISO15765/500000, P3-style CEM request `22F114` to `0x726`; only a TX indication is visible, followed by `ERR_BUFFER_EMPTY` |
| D2 fallback 1 | `B9FB`, target `0x40`, CAN_PS/125000, failed read; client reports it is trying the next ECU configuration |
| D2 fallback 2 | `B9FB`, target `0x50`, CAN/250000, failed read |
| D2 fallback 3 | `B9FB`, target `0x50`, CAN/500000, failed read |
| Additional candidates | Public log includes further attempts with channels, a relay opener and distinct protocol/rate settings; this is an observed branch list, **not** proof of required transport for another model |

References to public log areas:
[script lookup and P3 probe](https://www.matthewsvolvosite.com/forums/viewtopic.php?start=10&t=102268),
[125k target-40 and 250k target-50](https://www.matthewsvolvosite.com/forums/viewtopic.php?p=672174).

### Public ReadVinComponent XML excerpt: independent F114 corroboration

A separate public [VIN research note by Jan Jansen](https://jan-jansen.readthedocs.io/en/latest/vin.html)
displays a **partial, third-party-extracted XML node**, not a complete
verified 2015A ReadVin script or an OEM-backed XC90 MY2009 artifact.
Its `Components.ReadVinComponent` has categorical settings
`Identifier=F114`, `CanHiSpeedValue=500000`, `BusId=1`,
`UseRelay=0`, `Mode=EcuVariant` and `ServiceId=100`.
The researcher also documents the J2534 0x726 / `22F114`
request associated with this branch.

This is **stronger than a prose guess** for the published
F114 pathway: a script *fragment* contains the identifier and
communications settings consistent with the public VIDA 2014D log.
It remains unverified which exact VIDA version, installed script
checksum, model profile and reachable control-flow branch produced
the original excerpt. Crucially, the excerpt contains **no proof of
the B9FB fallback branch or the client accepting VIN**. The
original owner's VIDA 2015A XML and database are not available
as runnable sources. Do not reconstruct missing XML branches
or manufacture a response from the fragment.

The same public trace explicitly labels `ReadVinScriptThread`
for the J2534 writes. **This is stronger than separate reports from
different client sessions:** it establishes that those logged probes
occurred during the named script thread. It does **not** recover XML
control flow, accepted VIN, normal ignition/mode predicate, or any
authentic positive CEM reply.

Important distinctions:

- `0x40` and `0x50` are D2 target bytes, not an HS/LS bus
  mapping by themselves. A given target has multiple candidate
  bus/protocol configurations in this trace.
- Source `PassThruConnect` protocol `0x8004` denotes an
  observed J2534-2 pin-switching CAN_PS request, not proof that a
  plain J2534 CAN connection in Virtual Car behaves identically.
- `ERR_BUFFER_EMPTY` is **not** an ECU negative response, a
  complete B9FB RX, or a successful VIN decode.
- The public S40 fallback sequence must **not** be hardcoded
  as a universal XC90 MY2009 script sequence, nor used to
  fabricate a positive ECU reply or change the emulator's routing.
- `VCC-225200-1 1.8` is a public 2014D script label;
  identical names do not establish matching 2015A SQL content
  or checksum. No exact XML export was supplied.

This provides a concrete external check on the previous open-source
2014D research and the original 2015A IL findings
([stage 47](vida-identity-ecu-boundary-il.md),
[stage 50](vida-script-selection-stage50.md),
[2015A GetScript catalog audit](vida-2015a-getscript-sql-catalog-gate.md)).

## Added categorical source audit

Extend existing `emulator/tools/audit_vida_script_selection.py`,
not the actual diagnostic/transport implementation:

- Recognize exactly `Type='ReadVin'` as a separate script
  category, distinct from `VehCommSpecification`.
- Count a source-logged `GetScript → Fetched → Running`
  triple only when the script ID is equal on the **same log
  thread** within the existing 30-second window.
- Count an explicit `Profile: 'EMPTYPROFILE,'` literal
  separately, **only** when it appears on the ReadVin lookup.
  A mention elsewhere does not establish the selected profile.
- Preserve the existing flags `script_selected_for_identify_vehicle_verified=false`,
  `b9fb_to_vin_mapping_verified=false`,
  `xc90_v8_my2009_verified=false` and
  `replay_approved=false`.
- Output only counts and fixed booleans. No script IDs, VIN,
  profile keys, raw log lines, timestamps, names or SQL contents.

Eight additional synthetic regression groups (#09-#16 in
`test_audit_vida_script_selection.py`): exact ReadVin triple,
literal EMPTYPROFILE, non-ReadVin not promoted, misleading title
text rejected, mismatched IDs, cross-thread/deadline rejection,
request-only/foreign B9FB not acceptance, and no-leak/exclusive
CLI reporting. Previous eight groups remain.

**Expected** Python suite after this work: **292 tests**
(284 previously verified at exact PR #148 SHA + 8).
This is NOT a claim that feature CI already passed.

## Next real acquisition

1. Read-only SQL metadata on the owner's active VIDA2015A
   `GetScript` using the merged
   `Inspect-VidaGetScriptSchema.ps1`.
2. Verify the selected ReadVin script identifier/version in a
   **real authorized 2015A log**, without uploading its literal
   identifier, XML, VIN or private trace.
3. Capture whether 2015A tries P3 before D2 and which bus,
   bitrate, protocol and target each D2 candidate actually uses.
4. Keep successful B9FB transport, script output, VIN resolver,
   normal mode and ECU identification as **independent gates**.
5. Do not publish virtualcar binaries, use security access,
   program/coding ECU, or add synthetic E3/E6 responses.

No physical DiCE/vehicle test was performed here. Public log
is a **different model and software version** and is not a
replayable XC90 V8 MY2009 ECU fixture.
