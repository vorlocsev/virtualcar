# B3A58 — Original VIDA CarCom: CEM D2 2160 and ECM Denso CV8 GGD 1489

**Date:** 2026-11-21. **Evidence class:** `OWNER_LOCAL_SOURCE_RESEARCH`, not an actual ECU response or original VIDA acceptance. Input: three owner-local **read-only SELECT** exports. The original files stay outside GitHub.

## Export provenance

| Owner-local file | Rows | Exact file SHA-256 |
|---|---:|---|
| `XC90-2009-CarCom-NextSchema.csv` | 90 | `317d1c13a4849f26273eefd05038d07da3c2c033e08893c52173f82220a344a7` |
| `XC90-2009-2160-1489-Services.csv` | 103 | `2477755f55fe29be5b46dad00b854fa3f44c9ccc6963ea265ceabdb18ad72e09` |
| `XC90-2009-2160-1489-BlockTree.csv` | 48,695 | `c8dc63533fa1746c8b3bc9568f54a4ba4ac195a15c326c4002c36a2c774072af` |

The recursive block tree was joined to `T150_BlockValue`, so **one block may yield many rows** for alternate `CompareValue`s and may appear under different parents. The row count is not an ECU count, request count, or number of independent blocks. Count unique `(VariantId, BlockId)` for block identity, `(VariantId, ParentBlockId, BlockId)` for distinct edges.

## Variant-specific service catalog

| Metric | CEM D2 2160 / `31296075 AA` | ECM Denso CV8 GGD 1489 / `30670321 AA` |
|---|---:|---:|
| `T110_Service_EcuVariant` entries | **54** | **49** |
| Non-empty `T111_Service.definition` rendered as `System.Byte[]` in the CSV | 15 | 31 |
| Blank `definition` cells in CSV | 39 | 18 |
| Root blocks in recursive CSV (unique BlockId) | 518 | 1,335 |
| Unique BlockId over all depths | 1,621 | 12,045 |
| Root `BLOFF` | 42 | 0 |
| Root `REID` | 236 | 986 |

**Important:** In this CSV, `definition` is the literal `.NET System.Byte[]` string — **not XML and not decoded request bytes**. The underlying SQL column is `image`; recovering the byte content requires a separate SELECT that emits `DefinitionHex`, with owner-private raw output. Prior service XML evidence in other documents must not be attributed to the current CSV.

Service catalog by application opcode:

- **2160 D2:** `A0, A1, A3, A6, AC, AE, AF, B1, B2, B4, B8, B9`. The `B9` mapping uses **ServiceId 2 / Read Data Block By Offset**. `A6 01` uses **ServiceId 4**. Multiple entries for `AE` and `B4` are service variants, not separate physical modules.
- **1489 GGD:** `10, 11, 14, 19, 22, 23, 27, 2A, 2C, 2E, 2F, 31, 34, 35, 36, 37, 3E, 85`. `22` uses **ServiceId 100 / Read Data By Identifier**. Services that can write, reset, unlock or program are **out of scope** for a read-only emulator.

## CEM D2 2160: actual BLOFF roots in owner's block-tree export

| Identifier in `T150_BlockValue.CompareValue` | BlockId | Root block name | Root length (bits) | Bytes | Unique direct PARAM children |
|---|---:|---|---:|---:|---:|
| `0xF0` | `4686268` | ECU identification | 120 | **15** | 2 |
| `0xFB` | `4687470` | Vehicle Information Section | 1,328 | **166** | 16 |
| `0xFC` | `4686717` | Vehicle Configuration Parameters | 1,040 | **130** | 127 |

### B9 F0 (15 bytes)

| Byte offset | Length | Direct PARAM | Type |
|---:|---:|---|---|
| 0 | 8 | `4687514` ECU Complete Part Number | `BCD+Ascii` |
| 8 | 7 | `4687148` ECU Diagnostic Software number | `BCD+Ascii` |

Both direct PARAM rows show `Scaling=x`; this is a catalog decoding rule, **not** evidence of the ECU's actual part-number bytes.

### B9 FB (166 bytes)

`T141_Block.offset` and `length` values are **bits**; byte offsets below are derived by dividing by eight. **VIN** is a 17-byte ASCII PARAM at **byte offset 11**, `BlockId=4687570`. Further fields include configuration document number (byte 1, 5 bytes, BCD), issue number (byte 6, 3 bytes, ASCII), chassis (byte 46, 6 bytes, ASCII), and service information (byte 152, 14 bytes, ASCII).

16 distinct child PARAM definitions cover **142/166 bytes**. The **24 missing bytes** are 12 two-byte gaps, at offsets:
`9–10, 28–29, 39–40, 44–45, 52–53, 56–57, 64–65, 86–87, 130–131, 136–137, 143–144, 150–151`.

The unnamed D2 2160 field at **byte 88** is **40 bytes** (`BlockId=4686540`, ASCII), reaching byte 127 inclusive. Other GGD variants have a different description for this interval. Neither the gaps nor field encoding beyond the declared datatype may be filled with invented OEM data.

### B9 FC (130 bytes)

Direct child PARAM count = **127**. Every listed child occupies eight bits. Their byte positions are **2–129 except byte 7**, leaving **bytes 0, 1, and 7 unspecified**. Sample enumerated catalog fields:

| Byte offset | PARAM | `BlockId` | Distinct nonempty enum codes |
|---:|---|---:|---:|
| 2 | 001-AC Vehicle main type | 4687206 | 5 |
| 3 | 002-C1 Steering position | 4687557 | 3 |
| 8 | 007-DF Gear box type | 4686060 | 3 |
| 9 | 008-DB Gear box | 4686529 | 22 |
| 10 | 009-AE Vehicle sub type | 4686923 | 17 |
| 12 | 011-AJ Power train | 4686174 | 3 |
| 16 | 015-CB Engine dynamics/STC | 4686275 | 8 |
| 36 | 035-CF Engine | 4686832 | 39 |
| 114 | 113-MU Service interval | 4686409 | 33 |
| 123 | 122-YB Year Designation Letter | 4687055 | 21 |

The positions 127, 128 and 129 have unnamed one-byte PARAMs (`5664058`, `5664059`, `5664060`). Enum dictionaries describe **allowed codes**, not values read from the owner's physical car or a verified ISO-TP response.

## ECM Denso CV8 GGD 1489: read-only identifier candidates

ECM variant 1489's root `REID` records include:

| DID | BlockId | Catalog name | Length | Child datatype |
|---|---:|---|---:|---|
| `0xF110` | 3229612 | On-line Diagnostic Database Reference Number | 24 bytes | ASCII |
| `0xF18C` | 3230495 | ECU Serial No | 16 bytes | ASCII |
| `0xF188` | 3237115 | Vehicle Manufacturer ECU Software number | 24 bytes | ASCII |
| `0xF191` | 3233087 | Vehicle Manufacturer ECU Hardware No | 24 bytes | ASCII |
| `0xF194` | 3229449 | ECU Software No | 24 bytes | ASCII |
| **`0xF190`** | **3238346** | **Vehicle Identification Number** | **17 bytes** | **ASCII** |

The `22` service exists for this exact ECM variant. These REID codes are **catalog-defined data identifiers**, not proven original VIDA requests in this owner's run. The present export has **no ECM 1489 root REID `F114` or `F106`**, and no ECM `BLOFF` roots. Do not transpose the CEM GGD `22 F114` route or the D2 `B9 FB` format onto this ECM.

## Relation to the B3A55 owner-local window and prior ReadVin research

The owner-observed B3A55 recent window had **60 native app TX, zero RX queued/delivered**, with missing D2 `B9 F0` for 19 **different target logical addresses**, and missing `B9 FB` for **target `0x40`**. CarCom profile 163120 independently lists CEM D2 Variant 2160 as `physicalAddress=40` / `commAddress=40` on Low speed CAN; this is a **consistent addressing candidate**, not a proof of a real CEM response. The other 18 B9F0 targets are **not identified** by the seven default-variant rows of this vehicle profile. Do not synthesize replies on their behalf.

**Critical runtime-vs-profile distinction:** previous owner-source ReadVin XML/IL research in [Draft #317](https://github.com/vorlocsev/virtualcar/pull/317) traced **hard-coded diagnostic script variant identifiers** for CEM GGD `30728270 AA` (variant 821) and CEM D2 `09469693  A` (variant 230), which differ from the XC90 profile's **default CEM variants 529 and 2160**. The present exports do **not** establish how VIDA chooses between the script variants and default ECUVariant, nor whether the new 2160/529 block tree is the effective runtime decoder. Compare actual script lookup and `T120/T121` configurations before claiming a direct causal ReadVin fix.

The ECM's available `22 F190` record should not be confused with the original ReadVin script's CEM `22 F114` branch. A parser definition alone does not prove that VIDA invoked that DID during the owner's J2534 session.

## Next gate, without changing the installed PS provider

1. Read-only comparison of original ReadVin script variants **230/821** against default CEM variants **2160/529** (exact variant identifiers, service links, config rows, priority and D2 `B9 F0/FB` / GGD `F114` layout).
2. Capture a fresh same-process `Active INI:` and matched TX/RX markers; preserve the exact current PS DLL SHA, Registry32 and fixture.
3. Only after source and transport agreement, write a **separate opt-in lab fixture** using authentic source-backed bytes or explicitly labelled synthetic data, **not** a fabricated 166-byte OEM response.
4. Keep original VIDA ReadVin, ECU identification, T111/T122 and physical J2534 **NOT VERIFIED**.

No original SQL database, raw CSV, binary vendor service XML, VIN or PIN was committed in this research note. No Windows/VMware runtime or GitHub CI was executed for this stage.
