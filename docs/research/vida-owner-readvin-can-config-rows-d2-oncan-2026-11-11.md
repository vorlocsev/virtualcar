# VIDA owner original ReadVin T121 CAN configurations and D2onCAN request layout

**Owner evidence** \`VIDA-ReadVIN-CAN-Config-Rows.zip\` (7 files); ZIP integrity passed, all **6/6** CSV and JSON lengths/SHA256 match owner manifest. The export is original owner VIDA 2014D \`CarCom\` data, with **no anonymization**, collected by read-only SQL SELECTs. Neither original SQL records nor vendor DLLs/full IL are committed to this repository. A separate, already owner-provided \`VehCom2.DLL\` was statically inspected; nothing was executed.

## Original direct variant → config facts

Seven rows, six distinct original \`T100_EcuVariant\` IDs. Original string values shown exactly where relevant (including double spaces):

| Original ECU variant ID / identifier | \`T121_Config.id\` | priority | Protocol / net | Config node address \`commAddress\` | \`physicalAddress\` | \`canAddress\` | CanIdTX / CanIdRX / CanIdFunc |
|---|---:|---:|---|---|---|---|---|
| 70 / \`08666792  F\` (PJB) | 74 | 1 | D2 / CAN | \`50\` | \`D0\` | \`FFFFE\` | NULL / NULL / NULL |
| 230 / \`09469693  A\` (CEM) | 240 | **1** | D2 / CAN | \`40\` | \`40\` | \`FFFFE\` | NULL / NULL / NULL |
| 230 / \`09469693  A\` (CEM) | 241 | **2** | D2 / CAN | \`50\` | \`D0\` | \`FFFFE\` | NULL / NULL / NULL |
| 692 / \`30887707  C\` (CI) | 704 | 1 | D2 / **K** | \`51\` | \`51\` | \`FFFFE\` | NULL / NULL / NULL |
| 693 / \`30887708  A\` (CI) | 705 | 1 | D2 / **K** | \`51\` | \`51\` | \`FFFFE\` | NULL / NULL / NULL |
| 714 / \`9451570\` (CDM) | 726 | 1 | D2 / CAN | \`50\` | \`D0\` | \`FFFFE\` | NULL / NULL / NULL |
| 821 / \`30728270 AA\` (CEM GGD) | 611 | 1 | GGD / CAN | \`52\` | \`00\` | \`0\` | **\`72E\` / \`726\` / \`7DF\`** |

Original CEM GGD config 611 also has \`busRate=500000\`, \`addressSize='11'\`; six D2 rows have SQL \`busRate=NULL\`, \`addressSize='29'\`, and all seven rows have \`CanIdUUDT=NULL\`. **Do not cast original SQL NULL to zero or infer a 29-bit CAN bus from D2/K row addressSize.**

All 7 source rows have **\`fkT121_Config_Gateway=NULL\`**, and the directly linked gateway-row query returned **0 rows**. This does **not** rule out other forms of gateway behavior. The original \`T120\` links have count 1 for IDs 70, 692, 693, 714, 821, and count 2 for CEM D2 ID 230. Priority order is source metadata, **not** measured actual choice by the runtime.

## Original J2534 D2onCAN implementation (static managed IL)

From previously user-provided \`VehCom2.DLL\`:
- \`J2534.Diagnostics.DiagAppConnection.Send_D2onCan\` (MethodDef #525) prefixes one byte of \`EcuAddress\` to diagnostic request bytes, unless the argument is a \`CanIdAddress\` or \`SubNodeAddress\`; it calls \`ID2Application.Send\`. \`EcuAddress.op_Implicit\` (#1159) returns its stored byte.
- \`J2534.Diagnostics.D2onCanApplication.Connect\` (#429) opens J2534 channel with \`ProtocolID=5\` (\`CAN_PS\`), flags **256**, configured baud rate.
- \`D2onCanApplication.Send\` (#431) embeds a **4-byte static CAN-ID prefix**, verified by extracting original managed FieldRVA #116, Field #987, exact bytes **\`00 0F FF FE\`** = arbitration ID **\`0x000FFFFE\`**. The source procedure for D2-on-CAN does not obtain this ID from \`CanIdTX\` SQL fields. \`PASSTHRU_MSG\` uses \`TxFlags=256\`, \`DataSize=12\`, 4-byte identifier then 8-byte data.
- For **one D2-on-CAN frame**, format byte is **\`0xC8 | (request-length & 7)\`**, followed by logical address + application bytes, padded to 8 CAN data bytes. Longer payloads use D2-specific multi-frame codes, **not necessarily ISO-TP standard framing**.
- \`D2ResponseInterpreter\` (#456-466) checks the ECU address; for a positive response, checks service \`requestService + 0x40\`, plus the requested block offset for service \`B9\`. Actual incoming J2534 frame/byte values not recorded.

**Conditional derived synthetic test vector** when CEM D2 variant 230 resolves to config 240 and sends original ReadVin application payload \`B9 FB\`:

\`\`\`text
ProtocolID=5 (CAN_PS), TxFlags=0x100, DataSize=12
CAN ID:   0x000FFFFE
CAN Data: CB 40 B9 FB 00 00 00 00
PASSTHRU_MSG.Data:
          00 0F FF FE CB 40 B9 FB 00 00 00 00
\`\`\`

The source of \`40\` is original \`commAddress='40'\` for config 240, **not** the ReadVin XML's \`EcuAddress=64\` field (Mode is EcuVariant). \`CarComRepository.GetEcuConfig\` parses original \`commAddress\` as NodeAddress, then the service provider builds the ECU address object. The alternate config 241 has \`commAddress='50'\` and \`physicalAddress='D0'\`; **do not assume D0 is the D2 request's logical address**. Exact selected config, branch, speed and runtime message need separate verification.

Initial GGD \`EuCD\` source request remains \`22 F1 14\`; config 611 source names say \`CanIdTX=72E, CanIdRX=726, CanIdFunc=7DF\` and 500 kbit/s. Do not flip source TX/RX labels based on generic conventions, or claim a recorded on-wire J2534 send from these rows alone.

## Priorities / incomplete acceptance gates

1. Add isolated **synthetic** fixtures for GGD \`22 F1 14\` and conditional D2 CAN request vector, plus negative and wrong ECU/offset response rejection; do not label tests as actual VIDA acceptance.
2. Prove runtime config choice and J2534 D2-on-CAN baud + addressing (including CEM config 240 vs 241) from original VIDA trace in VMware.
3. Prove 125 kbps J2534-2 CAN-MS capability channel open/close, despite VIN request itself starting with 500 kbit/s GGD.
4. Treat CI D2/K branches separately from CAN; do not send them as CAN data.
5. Capture original VIDA accepted VIN equality and exact-head CI; physical J2534 remains not tested.

**No release, merge or proprietary asset publication.** A successful catalog/IL lookup is not equivalent to runtime acceptance.
