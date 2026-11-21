# B3A57 — XC90 2009 B8444S: exact CarCom profile ECU/configuration map

**Evidence class:** owner-local, read-only VIDA CarCom SQL export. This document records the selected profile's catalog/default-variant and configuration rows. It is not a live vehicle scan, not proof that every listed module is physically installed, and not proof of an ECU response or VIDA acceptance.

## Source identity

| Field | Exact value |
|---|---|
| Database | `CarCom` |
| Profile table | `T161_Profile` |
| Profile ID | `163120` |
| Profile title | `XC90 2009 B8444S` |
| Profile identifier | `0b00c8af83f1a29b` |
| Owner export | `XC90-2009-ECU-map.csv` |
| Unique ECU variants | 7 |
| Configuration rows | 8 |

The CEM D2 variant has two configuration rows, which explains eight rows for seven unique variants.

## Exact ECUVariant and configuration rows

| ECU | ECUVariantId | Part number | Protocol | Version | ConfigId | Bus | Physical | Functional | canAddress | commAddress | busRate |
|---|---:|---|---|---:|---:|---|---|---|---|---|---:|
| BCM | 416 | `30667559 AA` | GGD | 2 | 428 | High s 1 | `01` | `33` | `18DA01F1` | `01` | 500000 |
| CEM | 2160 | `31296075 AA` | D2 | 7 | 1824 | High s 1 | `D0` | `50` | `FFFFE` | `50` | NULL |
| CEM | 2160 | `31296075 AA` | D2 | 7 | 1825 | Low speed | `40` | `C0` | `FFFFE` | `40` | NULL |
| CEM | 529 | `30682825  A` | GGD | 2 | 541 | High s 1 | `50` | `33` | `18DA50F1` | `50` | 500000 |
| CPM | 3066 | `30710664 AC` | D2 | 7 | 2754 | Low speed | `8F` | `0F` | `FFFFE` | `0F` | NULL |
| ECM Denso CV8 | 1489 | `30670321 AA` | GGD | 2 | 1255 | High s 1 | `10` | `33` | `FFFFE` | `10` | 500000 |
| HCM | 1614 | `30782609 AA` | GGD | 2 | 1346 | High s 1 | `76` | `33` | `0` | `76` | 500000 |
| SAS | 573 | `30710733 AC` | GGD | 2 | 585 | High s 1 | `32` | `33` | `18DA32F1` | `32` | 500000 |

The table preserves the original `BusName`, `physicalAddress`, `functionalAddress`, `canAddress`, `commAddress` and `busRate` values. `NULL` means the exported CarCom configuration row had no value; it must not be silently filled from a generic protocol assumption.

### Additional raw routing fields

- BCM / Config 428: `canIdTX=000`, `canIdRX=000`, `canIdFunc=000`, `canIdUUDT=NULL`, `addressSize=29`, `Gateway=NULL`.
- CEM D2 / Config 1824: all four `canId*` fields NULL; `addressSize=29`, `Gateway=NULL`.
- CEM D2 / Config 1825: `canIdTX=000`, `canIdRX=000`, `canIdFunc=000`, `canIdUUDT=NULL`; `addressSize=29`, `Gateway=NULL`.
- CEM GGD / Config 541: `canIdTX=000`, `canIdRX=000`, `canIdFunc=000`, `canIdUUDT=NULL`; `addressSize=29`, `Gateway=NULL`.
- CPM / Config 2754: all four `canId*` fields NULL; `addressSize=NULL`, `Gateway=NULL`.
- ECM Denso CV8 / Config 1255: `canIdTX=000`, `canIdRX=000`, `canIdFunc=000`, `canIdUUDT=NULL`; `addressSize=29`, `Gateway=NULL`.
- HCM / Config 1346: `canIdTX=000`, `canIdRX=000`, `canIdFunc=000`, `canIdUUDT=NULL`; `addressSize=29`, `Gateway=NULL`.
- SAS / Config 585: `canIdTX=000`, `canIdRX=000`, `canIdFunc=000`, `canIdUUDT=NULL`; `addressSize=29`, `Gateway=NULL`.

## Corrections to earlier hypotheses

1. **The profile catalog contains two CEM diagnostic variants, not proof of two physical CEMs.** CEM D2 v7 / `31296075 AA` (Variant 2160) and CEM GGD v2 / `30682825  A` (Variant 529) are both associated with this VIDA profile. Their presence must be interpreted as diagnostic/profile alternatives until a live session establishes which path VIDA selects.
2. **The exact profile export does not contain CEM P/N `30786890`.** That number may exist in other model-year or service-replacement contexts, but it is not the CEM part number in these rows.
3. **The detailed block tree previously extracted for Variant 529 belongs to GGD v2.** It must not be treated as the D2 v7 block map for Variant 2160.
4. **The detailed service list previously extracted for Variant 3018 / `31327407 AA` is a different ECUVariant.** Its A6/AE/B9 definitions cannot be copied to Variant 2160 without querying Variant 2160's own CarCom rows.
5. **The ECM row is GGD v2 / Variant 1489 / `30670321 AA`, physical and communication address `10`, functional address `33`.** This profile row does not support the earlier proposed ECM logical address `7A`. A live response address still requires a trace.
6. **D2 CEM has separate HS and LS config rows.** Config 1824 uses `physicalAddress=D0`, `commAddress=50`; Config 1825 uses `physicalAddress=40`, `commAddress=40`. The low-speed `40` row is consistent with the separately observed B3A55 D2 requests on the 125-kbit/s route, but the `T121_Config.busRate` field itself is NULL in this export. The 500/125-kbit/s values must be sourced from the relevant initialization/timing configuration, not invented here.

## Consequences for Virtual Car

- Keep D2 v7 and GGD v2 as separate protocol handlers and fixture namespaces.
- Do not synthesize a CEM D2 response from the Variant 529 GGD block tree.
- Do not reuse Variant 3018's A6 or AE service definition as Variant 2160's definition.
- Before changing `virtualcar.ini`, obtain Variant 2160's own service definitions, D2 block tree and timing/configuration rows; separately inspect Variant 1489's GGD services and block metadata.
- Preserve the exact address fields independently. In particular, do not equate `physicalAddress`, `functionalAddress`, `commAddress`, `canAddress` and `canIdTX/RX` without source-level protocol evidence.

## Acceptance boundaries

The export proves profile/catalog metadata only. It does **not** prove:
- which CEM variant is selected in the current original VIDA runtime;
- that all seven variants are physically present;
- any positive B9F0/B9FB/A6/AE response;
- original VIDA ReadVin acceptance or ECU identification;
- T111/T122 acceptance or physical J2534 operation.

No ECU response fixture, installed DLL, registry entry, original VIDA database, or vehicle configuration was modified by this research note.
