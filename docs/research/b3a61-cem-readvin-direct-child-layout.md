# B3A61 — CEM ReadVin: exact direct-child field layout from original CarCom

**Evidence:** owner-local read-only SQL SELECT; source research only. The original CSV and source VIDA database stay outside Git. No OEM CAN capture, actual J2534 reply, ECU configuration or VIDA GUI acceptance is established.

## Input and structural validation

- Owner-local file: `CEM-ReadVin-DirectChildren.csv`.
- Exact raw-file SHA-256: `54c5bfcb9060695179f60ac86d8fdbd56723af6dd87791eff72ad5cac235ee91`.
- **572 rows, 13 root groups**. Each group is keyed by exact `(VariantId, RootBlockId)`; child IDs within each group are unique.
- All child offsets and lengths are whole bytes (given in bits in `T141_Block`). For **all 13 groups**, each child occupies a positive interval fully inside its root; **no child interval overlaps**. Unmapped bytes are reported below; they are NOT automatically padding, newline, a checksum, or available replacement bytes.
- Source lineage: `T144_BlockChild` direct children of the 13 previously verified top-level roots, `T141_Block` metadata and `T143_BlockDataType`. `T150_BlockValue` original response values are not present.

## Exact source field coverage

| Variant | Root BlockId | Service/block | Root bytes | Direct children | Described bytes | Unmapped bytes |
|---|---:|---|---:|---:|---:|---:|
| **230** | 109632 | D2 B9 F0 ECU identification | 15 | 2 | 15 | 0 |
| **230** | 109650 | D2 B9 FB Vehicle Information | **86** | **10** | **72** | **14** |
| **230** | 109661 | D2 B9 FC Vehicle Configuration | **76** | **71** | **71** | **5** |
| **2160** | 4686268 | D2 B9 F0 ECU identification | 15 | 2 | 15 | 0 |
| **2160** | 4687470 | D2 B9 FB Vehicle Information | **166** | **16** | **142** | **24** |
| **2160** | 4686717 | D2 B9 FC Vehicle Configuration | **130** | **127** | **127** | **3** |
| **821** | 2049125 | GGD REID F106 Vehicle Configuration | **186** | **186** | **186** | **0** |
| **821** | 2049307 | GGD REID F110 database reference | 24 | 1 | 24 | 0 |
| **821** | 2049313 | GGD REID F114 Vehicle Information | **255** | **12** | **222** | **33** |
| **821** | 2049431 | GGD REID F190 VIN | **24** | **1** | **24** | **0** |
| **529** | 293867 | GGD REID F106 Vehicle Configuration | **130** | **127** | **127** | **3** |
| **529** | 293990 | GGD REID F110 database reference | 24 | 1 | 24 | 0 |
| **529** | 293992 | GGD REID F114 Vehicle Information | **166** | **16** | **140** | **26** |

All byte counts above are **CarCom schema lengths** (bits divided by eight), not a proof of wire payload or J2534 DataSize.

## VIN position verified across four Vehicle Information roots

| Variant | Protocol/block | VIN ChildBlockId | Byte offset | Length | DataType |
|---|---|---:|---:|---:|---|
| **230**, original ReadVin script | D2 B9 FB | **109654** | **11** | **17** | `Ascii` |
| **2160**, XC90 profile default | D2 B9 FB | **4687570** | **11** | **17** | `Ascii` |
| **821**, original ReadVin script | GGD REID F114 | **2049317** | **11** | **17** | `Ascii` |
| **529**, XC90 profile default | GGD REID F114 | **293996** | **11** | **17** | `Ascii` |

**Decisive finding:** all four Vehicle Information roots describe **the same 17-byte ASCII VIN window at bytes 11–27 inclusive**, despite root lengths 86/166/255/166. D2 variants 230 and 2160 have **exactly identical first ten direct children** by original name, byte offset, byte length and datatype: Data length, Car Config Doc No, Car Config Issue No, VIN, FYON, Type (PNR-3), Chassis, Factory code, Structure week and Package Identity. These ten fields finish at byte **85** in both variants.

This is a **schema compatibility of the common prefix**, not proof that a physical CEM returned matching bytes, or that the original VIDA parser accepted this synthetic VIN.

## Unmapped byte ranges and variant-specific fields

### D2 B9 FB

- **230 / 86 bytes:** ten fields, 72 described bytes; **seven two-byte gaps**: `9–10, 28–29, 39–40, 44–45, 52–53, 56–57, 64–65`. Package Identity occupies bytes `66–85`; no additional direct child follows.
- **2160 / 166 bytes:** the same ten-field layout plus six additional direct fields: unnamed 40-byte ASCII at `88–127`, Marketing code `128–129`, Interior code `132–135`, Exterior color code `138–142`, S-message `145–149`, and Service information `152–165`. Twelve two-byte gaps total, **24 unmapped bytes**. The extra records do not establish the meaning of the gaps.

**Historical synthetic 88-byte B9FB:** It is **two bytes longer** than the 230 root; even though these ten described fields all fit within 86 bytes, the extra bytes are not identified by this CSV as transport framing, terminator, or a validated OEM trailing field. Do not trim, pad, or promote that fixture to a genuine CEM reply.

### GGD REID F114

- **821 / 255 bytes:** first ten direct fields have the same *offsets, lengths and types* as D2 230's Vehicle Information layout (field name spellings/case differ). Then `Reserved` at **88–109** (22 bytes, `Hex`), **unmapped 110–126** (17 bytes), and `Brand speific` [source spelling] at **127–254** (128 bytes, `Hex`). Eight 2-byte gaps in earlier positions (including `86–87`) plus that 17-byte gap = **33 unmapped bytes**. The 17-byte gap **is not the VIN**: the named VIN is at bytes 11–27.
- **529 / 166 bytes:** first ten common fields, then 38-byte ASCII at `88–125`, Marketing code `128–129`, Interior code `132–135`, Exterior color code `138–142`, S-message `145–149`, Service information `152–165`. Total **26 unmapped bytes**, compared with D2 2160's 24. This is a distinct 166-byte field map, not proof of identical payload semantics.

### D2 B9 FC and GGD F106

- **230 D2 B9 FC / 76 bytes:** 71 one-byte `Unsigned` children; gaps at **0–1, 7, 40, 72**, totaling 5 bytes. Data begins at byte 2; there is no asserted checksum or header structure in this source.
- **2160 D2 B9 FC** and **529 GGD F106**: each has 127 one-byte `Unsigned` children in a 130-byte root; unmapped bytes **0, 1, 7**. Their positions/datatypes match, though some names and enumerated meanings differ.
- **821 GGD F106 / 186 bytes:** 186 contiguous one-byte `Unsigned` children, with `Number of bytes` at byte 0 and `Checksum` at byte 1. This 186-byte layout is **not interchangeable** with the 130-byte F106 schema or the 76-byte B9 FC schema.

### D2 B9 F0, GGD F110 and F190

- **230/2160 B9 F0:** two fields have identical field labels, offsets, lengths and datatypes: `ECU Complete Part Number` at bytes 0–7 (8 B, `BCD+Ascii`), `ECU Diagnostic Software number` at 8–14 (7 B, `BCD+Ascii`). Different root and child BlockIds remain variant-specific; the **actual ECU reply** is unknown.
- **821/529 F110:** each maps to a single 24-byte `Ascii` direct child.
- **821 F190:** has a **single 24-byte `Ascii` child** called `Vehicle Identification Number`. It is **not a 17-byte direct child**, unlike F114; the file does not say whether 24 bytes include padding, other metadata, or a format-specific record. Do not expose a 24-byte VIN or infer the exact 17-character extraction rule.

## Implications for original VIDA acceptance

Earlier B3A55 owner-local window: 60 native TX / **0 RX enqueued / 0 RX delivered**, D2 `0x40` B9 F0 and B9 FB no-fixture and P3 CEM F114 no-fixture. This CSV **clarifies what the original CarCom decoder describes**, not what the VirtualCar adapter sent; it does not resolve whether script ECUVariant 230/821 or default profile variant 2160/529 was selected. The PS DLL loaded in an `iexplore.exe` module snapshot at one instant, but there is still no same-process `Active INI:` and end-to-end RX/GUI acceptance proof.

**Next source/transport gate:** inspect original Script/ResponseHandler VIN extraction expectations (especially script variant 821 F114 vs F190 and 230 B9 FB), and verify native D2 13-frame payload assembly and J2534 delivered RX in a controlled owner-local window. Do not populate unknown gap bytes with guessed CRLF; do not change installed DLL, `virtualcar.ini`, Registry32, OEM database or any ECU configuration.

**Acceptance:** ReadVin, CEM/ECM identification, T111/T122, physical J2534 all **NOT VERIFIED**. No new positive ECU reply or runtime/CI claim in this analysis.
