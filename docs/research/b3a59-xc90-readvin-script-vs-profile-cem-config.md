# B3A59 — CarCom CEM routing: ReadVin script variants 230/821 vs XC90 profile 2160/529

**Evidence date:** 2026-11-21. **Class:** original-owner read-only SQL export `SOURCE_RESEARCH / OWNER_LOCAL`; not ECU hardware evidence, a measured J2534 transaction, or successful original VIDA ReadVin.

## Exact owner-local export

- File: `CEM-ReadVin-230-821-2160-529-Configs.csv` (private/local; not committed).
- Rows: **6**; unique variants: **4**.
- SHA-256 (raw CSV bytes): `17c5536beaebba285658098071cd3636fcbc8b17cf483451e9b07d70f8f030c1`.
- Source join: `T100_EcuVariant` → `T101_Ecu` → `T120_Config_EcuVariant` → `T121_Config` → `T122_Protocol`, `T123_Bus`.
- Queries use SELECT only. Raw `NULL`/empty values and literal `000` have distinct meanings and are preserved.

## Exact six configuration rows

| Variant | Part number (CarCom) | ConfigId | Priority | Protocol | Bus | Physical | Functional | Comm | canAddress | canIdTX | canIdRX | canIdFunc | busRate | size |
|---|---|---:|---:|---|---|---|---|---|---|---|---|---|---:|---:|
| **230** | `09469693  A` | **240** | **1** | D2 | Low speed | `40` | `C0` | `40` | `FFFFE` | NULL | NULL | NULL | NULL | 29 |
| **230** | `09469693  A` | **241** | **2** | D2 | High s 1 | `D0` | `50` | `50` | `FFFFE` | NULL | NULL | NULL | NULL | 29 |
| **2160** | `31296075 AA` | **1824** | **1** | D2 | High s 1 | `D0` | `50` | `50` | `FFFFE` | NULL | NULL | NULL | NULL | 29 |
| **2160** | `31296075 AA` | **1825** | **2** | D2 | Low speed | `40` | `C0` | `40` | `FFFFE` | `000` | `000` | `000` | NULL | 29 |
| **821** | `30728270 AA` | **611** | **1** | GGD | High s 1 | `00` | `00` | `52` | `0` | **`72E`** | **`726`** | **`7DF`** | 500000 | **11** |
| **529** | `30682825  A` | **541** | **1** | GGD | High s 1 | `50` | `33` | `50` | **`18DA50F1`** | `000` | `000` | `000` | 500000 | **29** |

Both D2 variants have no specified `busRate` in the exported `T121_Config` rows. Do not insert a nominal HS/LS speed into this field or claim that these six rows prove wire timing. Distinguish source literal `000` from SQL NULL; `000` must not be interpreted as a verified arbitration address.

## Finding A — D2 has opposite priority, but the same two logical routes

- Script variant **230**: low-speed physical/comm `40` **priority 1**, high-speed physical `D0`/comm `50` **priority 2**.
- XC90 profile default variant **2160**: high-speed physical `D0`/comm `50` **priority 1**, low-speed physical/comm `40` **priority 2**.
- Thus bus/address choices match as a **set**, but priority order does **not**. This is a **catalog preference**, not runtime evidence that a particular priority is always chosen by `ReadVinComponent`.

Relation to owner B3A55: one D2 B9F0 and one D2 B9FB to logical target `0x40` were classified on a CAN 125000 route, among 19 distinct B9F0 targets (18 other addresses). This fits **both** D2 candidates' low-speed config. In the script variant 230 it is priority 1; in profile variant 2160 it is priority 2. No same-session variant/ConfigId selection evidence is provided.

## Finding B — GGD is not an interchangeable CAN route

- Script variant **821**: ConfigId 611 / **11-bit** addressSize, `canIdTX=72E`, `canIdRX=726`, `canIdFunc=7DF`, `canAddress=0`, `commAddress=52`, 500000.
- XC90 default variant **529**: ConfigId 541 / **29-bit** addressSize, `canAddress=18DA50F1`, `canIdTX/RX/Func=000`, `physicalAddress=50`, `commAddress=50`, 500000.
- `canIdTX` / `canIdRX` are preserved exactly as **database column labels**. This research does **not** assign adapter TX/RX wire direction to them without consulting the original `GetEcuInitFromConfigId` consumer.
- The current B3A55 `P3 0x18DA50F1` requests are **consistent** with Variant 529's `canAddress` and do not by themselves demonstrate Variant 821's 11-bit route. A client might invoke separate scripts/channels; process category alone is not variant attribution.

## Critical distinction: original ReadVin XML vs vehicle profile defaults

Earlier original-owner static VIDA XML/IL analysis in [Draft PR #317](https://github.com/vorlocsev/virtualcar/pull/317) identified hard-coded ReadVin script ECU variant identifiers `09469693  A` (230, D2) and `30728270 AA` (821, GGD), alongside additional fallbacks. Profile `T161_Profile.id=163120` / `T160_DefaultEcuVariant` references CEM variants `2160` and `529`. **Neither this export nor the previous block trees prove how the runtime selects a default/profile ECUVariant relative to an explicit script ECUVariant**.

Especially, the original script may use variant 230's B9 service/blocks rather than the already exported variant 2160 tree. Do **not** copy D2 2160's B9 FB 166-byte payload definition into variant 230 without the next source comparison; similarly do **not** transpose CEM GGD variant 529's F114/F106 record definitions to variant 821.

## Bounded next verification (SELECT only)

Compare:
1. `T110_Service_EcuVariant` + `T111_Service` links for all **230/821/2160/529**, especially D2 `B9`, `A6`, `A3`, GGD `22`.
2. Their exact `T144_BlockChild` top-level BLOFF `F0/FB/FC` and REID `F114/F106/F110` root `BlockId`, `length` and type, without assuming inherited content.
3. Original `GetEcuInitFromConfigId` consumer wire direction and same-run native `Active INI:` plus `TX → RX enqueue → RX delivered` markers.

Only once the script-selected **variant, config and response format** are established should a separately isolated synthetic fixture be designed. Do not change production or installed PS DLL, installed `virtualcar.ini`, registry or original VIDA; no programming/security operations.

**Acceptance remains NOT VERIFIED:** original VIDA ReadVin (GUI), CEM/ECM identification, T111/T122, physical J2534. No live tests, CI, merge or release performed in this source-review step.
