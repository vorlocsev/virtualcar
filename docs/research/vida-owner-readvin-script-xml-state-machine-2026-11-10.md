# Owner-confirmed original VIDA ReadVin XML and static fallback graph (2026-11-10)

## Evidence and exact ID

Owner-supplied private \`VIDA-ReadVIN-original-script-content.zip\` contains
**25 entries**: 17 exact original compressed script binaries, seven CSV/SQL
supporting files and README. Outer archive CRC and all 17 per-binary
SHA-256 values validated against owner-local manifest. Every binary is a
valid embedded PKZIP with one XML entry, original filename
\`0900c8af8184c004\`. Original full SQL, original XML and binary payloads
**remain owner-private** and are **not committed** to this repository.

Only **one unique ScriptId** is present:
\`0900c8af8184c004\`, original display text
\`Read VIN first readout (Odometer Value) (No immo check)\`,
XML \`docno="VCC-225200"\`, \`type="ReadVin"\`,
profile \`0c00c8af80205920\`. There are 17 language rows
(\`sv-SE\`, \`ja-JP\`, \`de-DE\`, \`es-ES\`, \`fi-FI\`, \`fr-FR\`,
\`it-IT\`, \`ko-KR\`, \`nl-NL\`, \`pt-PT\`, \`ru-RU\`, \`th-TH\`,
\`zh-TW\`, \`tr-TR\`, \`en-US\`, \`en-GB\`, \`zh-CN\`).
Each decompressed XML is 17,964 bytes; after removing language
metadata, all 17 have **identical 14 nodes, node property values and
27 eventhandler edges** (same static graph).

**Two independent ID namespaces:** original managed enum
\`ValueObjects.ScriptType.ReadVin=4\`; original SQL table
\`DiagSwdlRepository.dbo.ScriptType\` has **id 7,
Description='ReadVin'**. \`ScriptProvider\` passes textual
\`ScriptType.ToString()\` to SQL \`GetScript\`; it does not send 4
as the SQL PK. Do not conflate them.

## Source-grounded static diagnostic graph

\`Start.OnStart\` → \`EuCD\`:
- \`Components.ReadVinComponent\` with \`ServiceId=100\`,
  \`Identifier=F114\`, \`BusId=1\`, \`UseRelay=0\`,
  \`CanHiSpeedValue=500000\`, original
  \`EcuVariant="30728270 AA"\`.
- Catalog association (previous original CarCom evidence):
  \`ServiceId=100\` is GGD \`22\` (Read Data By Identifier).
- On positive response → \`GetEUCDVin\` → \`Output.AddVIN\`.
- On no response, negative response or no contact →
  \`NO_RELAY40B9FB\`.

D2 fallback in XML, with all three failure events
(\`OnNoResponse\`, \`OnNegativeResponse\`, \`OnNoContact\`)
connected between successive fallback stages:

| XML node | Service/identifier | BusId | Speed | Relay | Exact EcuVariant |
|---|---|---:|---:|---:|---|
| NO_RELAY40B9FB | D2 B9 / FB | 0 | 250000 | 0 | \`09469693  A\` |
| NO_RELAY50B9FB | D2 B9 / FB | 1 | 500000 | 0 | \`08666792  F\` |
| WITHRELAY40B9FB | D2 B9 / FB | 0 | 250000 | 1 | \`09469693  A\` |
| WITHRELAY50B9FB | D2 B9 / FB | 1 | 250000 | 1 | \`9451570\` |
| WITHRELAY51B9F0 | D2 B9 / F0 | 3 | 250000 | 1 | \`30887708  A\` |
| WITHRELAY_CI_Odo | D2 A5 01 / 32 | 3 | 250000 | 1 | \`30887707  C\` |

Original \`NO_RELAY40B9FB\` also specifies
\`EcuAddress=64\`. Positive responses from the first four
D2 B9/FB nodes invoke \`ResultVIN.Execute\` →
\`Output.AddVIN\`. \`WITHRELAY51B9F0.OnPositiveResponse\`
or \`OnNoContact\` starts \`WITHRELAY_CI_Odo\`;
a positive result there invokes \`ResultX40\` →
\`Output.SetX40Serial\`.
Not every final node has an explicit timeout/negative-response
handler; do **not** invent missing fallback edges.

Original response extractor graph:
- \`ResultVIN\`: \`Parameters\` → original key **59790**
  → \`value\`, then \`AddVIN\`.
- \`GetEUCDVin\`: \`Records\` → original key **61716**
  (XML title \`FB - Vehicle information section\`) →
  \`Parameters\` → original key **59790** (\`VIN\`) →
  \`value\`, then \`AddVIN\`.
- \`ResultX40\`: property \`raw\` → \`SetX40Serial\`.

This is **positive original evidence of B9 FB in a VIDA
ReadVin script** (previously unproven). It also proves that
the first static XML branch is **GGD 22 F114, not 22 F190**.
The script contains **no 22 F190 request**.

## Profile selection remains a critical unresolved prerequisite

\`ScriptProfileMap\` in the owner export has exactly one
mapping: \`ScriptId=0900c8af8184c004\` →
\`fkProfile=0c00c8af80205920\`. An exact
\`fkProfile='EMPTYPROFILE'\` lookup returned **zero rows**.

This does not imply the script cannot be selected. The original
owner-provided SQL \`GetValidProfilesForSelected\` function
explicitly **UNIONs every \`BaseData..VehicleProfile\` row
with \`FolderLevel=0\`** into valid profiles. Thus, if
\`0c00c8af80205920\` is a global level-0 profile, the
\`GetScript\` profile-list branch can select it even when
input is literal \`EMPTYPROFILE\`. The level of that exact
original BaseData profile has **not been queried**, and the
actual SQL runtime invocation has **not been observed**.
Do not mark selected script as runtime-confirmed.

The seven XML \`EcuVariant\` strings have **zero direct matches**
(after trimming SQL padding) against the 29 exact
\`T160_DefaultEcuVariant\` identifiers from the previously
captured XC90 2009 profiles \`163119\`, \`163120\`, \`163191\`.
This is an original generic/pre-profile selection script;
do **not** substitute the XC90-specific CEM variant IDs
without runtime or component-implementation proof.

\`CanHiSpeedValue\` and \`BusId\` are original script
component properties, **not** verified J2534 arbitration
IDs or observed channel configurations. Do not mix the
250000/500000 XML values with the separate J2534-2
125000-bps CAN-MS eligibility test or profile InitHw.

## Next gates (remain NOT TESTED unless independently verified)

1. Read-only SELECT BaseData \`VehicleProfile\` for
   \`0c00c8af80205920\`: verify \`FolderLevel\`.
   Do not execute owner SQL stored procedures or UDFs.
2. Inspect \`Components.ReadVinComponent\` managed IL to
   confirm on-wire addressing, BusId, relay, ECU variant
   selection, request framing, and the semantics of events.
3. Implement separate deterministic **synthetic** fixture
   tests for source-graph edges and \`Parameters[59790]\` /
   \`Records[61716]\` extraction. Synthetic tests are
   **not** original VIDA acceptance.
4. Validate original VIDA inside VMware with virtual J2534
   after its J2534-2 CAN_MS channel probing; require actual
   traces and VIN equality, not catalog evidence.
5. Physical J2534, original VIDA runtime ReadVin and
   exact-head CI are not evidenced here.

No original vendor source XML, SQL records, or binary assets
were uploaded to GitHub, and no merge/release occurred.
