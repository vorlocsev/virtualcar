# B3A60 — Original VIDA CarCom: ReadVin CEM root-block sizes differ from XC90 default profile

**Source date:** 2026-11-21. **Evidence class:** `OWNER_LOCAL_SOURCE_RESEARCH`; read-only SQL `SELECT` export, not a diagnostic response, J2534 RX proof, or original VIDA ReadVin acceptance.

## Exact input and methodology

Source: owner-provided `CEM-ReadVin-Block-Comparison.csv` exported from original `CarCom` on an isolated VMware installation.

- **13** SQL rows, UTF-8 CSV with BOM; exact raw-file SHA-256: `804dbec99e546f2f3e6e0f35abaa64a831e37854f3cdf7a827505839a55bf6ce`.
- Selected `T144_BlockChild` *top-level* rows where `fkT141_Block_Parent=1`; `T150_BlockValue.CompareValue` is the identifier, `T141_Block.length` is in bits.
- Every returned `LengthBits` divides exactly by 8. All `OffsetBits=0` and `DataTypeId=50` **for these roots**. These are catalog structure definitions, not the number of bytes delivered by `PassThruReadMsgs`.
- Profile-default variant IDs: **2160** (D2), **529** (GGD); original ReadVin-script variants from prior owner-private XML/source investigation: **230** (D2), **821** (GGD). Script selection at runtime remains unverified.

## D2 root comparison — all three block IDs are variant-specific

| BLOFF | ReadVin variant 230, `09469693  A` | Profile variant 2160, `31296075 AA` | Length difference (2160 minus 230) |
|---|---|---|---:|
| `0xF0` | BlockId **109632**, 120 bits = **15 B** | BlockId **4686268**, 120 bits = **15 B** | 0 B |
| `0xFB` | BlockId **109650**, 688 bits = **86 B** | BlockId **4687470**, 1,328 bits = **166 B** | **+80 B** |
| `0xFC` | BlockId **109661**, 608 bits = **76 B** | BlockId **4686717**, 1,040 bits = **130 B** | **+54 B** |

**B9 F0** lengths match, but BlockIds differ; do not conclude that the 15 bytes or fields match without direct-child comparison. **B9 FB** and **B9 FC** lengths are substantially different, so a 166-byte 2160 B9FB structure is **not proven compatible** with the script variant 230's 86-byte root.

The existing CEM50 adapter's synthetic, historical **88-byte** B9FB fixture is **not identical** to variant 230's 86-byte root. A two-byte difference **might** be framing or an alternative schema, but nothing in this export proves that; **do not strip two bytes, pad, or transplant the fixture** to force a pass.

## GGD root comparison

| REID | ReadVin variant 821, `30728270 AA` | Profile variant 529, `30682825  A` | Length difference (529 minus 821) |
|---|---|---|---:|
| `0xF106` | BlockId **2049125**, 1,488 bits = **186 B** | BlockId **293867**, 1,040 bits = **130 B** | **−56 B** |
| `0xF110` | BlockId **2049307**, 192 bits = **24 B** | BlockId **293990**, 192 bits = **24 B** | 0 B |
| `0xF114` | BlockId **2049313**, 2,040 bits = **255 B** | BlockId **293992**, 1,328 bits = **166 B** | **−89 B** |
| `0xF190` | BlockId **2049431**, 192 bits = **24 B** | **No matching top-level root in the filtered export** | N/A |

GGD `F114` is **255 B** in the original ReadVin variant 821 and **166 B** in profile variant 529. The `F190` 24-byte root exists in variant 821 but no matching *top-level* root was returned for 529 by this query; that cannot prove global nonexistence of an F190 parameter/service in variant 529. A catalog name of **Vehicle Identification Number** does not mean its full 24-byte block equals exactly 17 ASCII VIN bytes. Inspect the direct child fields and offsets.

## Impact on the current B3A55 / J2534 gate

Previously observed B3A55 window: 60 application TX, zero RX enqueued and zero RX delivered, D2 B9F0 to 19 distinct target logical addresses and B9FB to `0x40` with explicit no-fixture, plus GGD/UDS CEM F114 no-fixture and other unmatched requests.

- Catalog routing *supports candidate mapping*, not actual VIDA-selected ECUVariant.
- The effective original ReadVin script is a critical confounder. **Do not use variant 2160 / 529 lengths as if they were the 230 / 821 decoding contracts**, especially the 86 vs 166-byte D2 Vehicle Info and 255 vs 166-byte GGD Vehicle Info roots.
- Even the matching B9 F0 length **does not establish** the actual 15-byte CEM reply, fields, checksum, multi-frame protocol, or VIN acceptance.
- Keep `ReadVin`, ECU identification, T111, T122 and physical J2534 **NOT VERIFIED**. A catalog-only size comparison cannot authorize a simulated *OEM* reply.

## Exact next read-only SQL gate

Extract `T144_BlockChild` *direct children* of the 13 identified roots by their **verified BlockId**, and output child `BlockId`, `name`, `offset`, `length`, `fkT143_BlockDataType`. Compare whether root payloads begin with a length/header, where an actual 17-byte VIN field is located in **variant 230 B9 FB** and **variant 821 F114/F190**, and whether the identical-sized B9 F0 / F110 roots share direct-child layout.

Do not query full raw `T150_BlockValue` enumerations until needed: the prior recursive tree inflated to tens of thousands of rows. A bounded direct-child query is sufficient for this stage.

**Scope:** only source catalog work; no new J2534 response, fixture/INI mutation, SQL writes, original VIDA runtime or CI/workflow actions, release or merge. Raw source CSV stays owner-local.
