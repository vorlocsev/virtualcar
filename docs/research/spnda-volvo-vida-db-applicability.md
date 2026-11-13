# Study of spnda/volvo_vida_db for Virtual Car

Reviewed: 2026-11-13. Source: https://github.com/spnda/volvo_vida_db (main). Target: Virtual Car `development`, Volvo P2 / XC90 V8 MY2009, isolated read-only diagnostic research.

**Status: source-based research and an offline candidate check, not an original VIDA ReadVin result.** The repository analyzes VIDA **2014D** SQL Server databases and selected decompiled VIDA diagnostic classes. This is not an ECU capture from the target car, not a substitute for a selected private VIDA installation's actual GetScript/CarCom lookup, and not evidence of an accepted VIN or detected ECU.

## Relevant implementation evidence

| Source and implementation | Source-backed finding | Decision for Virtual Car |
| --- | --- | --- |
| [`scripts/vin_decoder.py`](https://github.com/spnda/volvo_vida_db/blob/main/scripts/vin_decoder.py) | Uses `VINDecodeModel`, `VINDecodeVariant` and `VehicleProfile` to resolve model, model year, partner, engine, transmission and applicable profiles. Its platform table maps model CID **275** to P2. Defaults to European partner and can cache decoded records as Python pickle. | Treat vehicle profiles as evidence-specific database selections, not universal VIN parsing. Do not copy fixed VINs or load untrusted pickle; private vehicle identity stays local. CID 275 belongs to the upstream lookup table, not proof the current synthetic B9FB was accepted. |
| [`scripts/carcom.py`](https://github.com/spnda/volvo_vida_db/blob/main/scripts/carcom.py) `get_vehicle_ecus` | `T161_Profile` / `T160_DefaultEcuVariant` link to `T100_EcuVariant`, `T101_Ecu`, `T102_EcuType` and `T121_Config`. Configuration joins `T122_Protocol` and `T123_Bus` and includes addresses, bus rates and gateway. These are **default assumed variants**, before actual vehicle identification. | Build an ECU topology evidence chain only when profile+variant+configuration come from the same locally verified VIDA source. Do not treat default ECU rows as successful identification or populate synthetic ECU replies automatically. |
| `carcom.py` `get_hw_settings`, `get_ecu_config_values` | `T136_InitHw_Profile` maps profile-specific hardware settings via `T130/T131/T132`; `T121` references initialization and timing entries. More specific profiles can override less specific settings. | Compare configured bus/baud/timing against original selected VIDA profile and locally observed J2534 operations. Never hard-code 250k/500k or keep-alive based only on a general database dump. |
| `carcom.py` `EcuBlocks` | `T144_BlockChild` forms a hierarchy of `T141_Block` and `T150_BlockValue`; identifier types include `REID`, `REOFF`, `BLOFF`, `ADDR` and `RTOFF`. The parameter bit offset is MSB-first after identifier bytes; As/Ppe labels and scaling can differ. | Use for a future *read-only* parameter decoder with explicit ECU variant/provenance. Do not assume the As and Ppe scalings match. `RTOFF` is routine control (not suitable as a read-only probe). |
| `carcom.py` `get_ecu_services` and [`sql/extract_services.ps1`](https://github.com/spnda/volvo_vida_db/blob/main/sql/extract_services.ps1) | `T110` associates ECU variants with `T111_Service`; service XML definitions are separately extracted from `T111_Service.definition`. | Determine the original `ReadVin.ServiceId` / `Identifier` / service mode from the matching private database, not by matching lexical `F114` or `B9FB` text in script XML alone. |
| [`sql/extract_scripts.ps1`](https://github.com/spnda/volvo_vida_db/blob/main/sql/extract_scripts.ps1) | `ScriptContent.XmlDataCompressed` is extracted as ZIP and expanded to XML, with script metadata in associated tables. Source script uses a large binary query size. | Reuse Virtual Car's existing bounded, read-only original-VIDA SQL/ZIP tools. Do **not** run upstream's broad exports against the private installation or publish its scripts. |
| [`scripts/d2.py`](https://github.com/spnda/volvo_vida_db/blob/main/scripts/d2.py) | Documents 29-bit tester request CAN ID `0x000FFFFE`, D2 `C8/8F/08../48..` fragmentation, positive service = requested service + `0x40`, `7F` negative and `7E` general responses. It describes a VIDA 2014D J2534 RX pass filter with mask/pattern `0x00000001` (odd 29-bit IDs) and an `D8 00 ...` 4-second diagnostic keep-alive. | Existing D2 fixture parsing remains separate from ISO-TP. Add **offline odd-CAN-ID candidate classification**, preserving existing replay and filter policy. Do **not** automatically emit `D8`, accept all odd CAN IDs, or change the emulator's network/ECU configuration solely from this source. |

The upstream's listed command `carcom.py ecus <VIN>` returns **potential** ECUs for selected profiles. Its `carcom.py params` definitions refer to specific ECU variants and must not be promoted into a universal CEM map.

## Added offline compatibility observation

In `emulator/tools/audit_p2_b9fb_shape.py`, `vida2014d_d2_rx_filter_candidate` is a **new additive categorical field**:

- `odd_extended_id_candidate`: CAN-ID integer exceeds 11-bit width and has bit 0 set; matches the **described** numeric odd-ID filter.
- `even_extended_id_mask_mismatch`: CAN-ID integer exceeds 11-bit width and bit 0 is clear; the described filter would exclude it.
- `width_unknown_without_j2534_flags`: ID integer fits in 11 bits, but the actual standard/extended frame form is unknowable from the numeric value alone.
- `not_evaluated`: the D2 frame sequence/route was invalid, or the ID is invalid.

`j2534_rx_29bit_flags_verified` is **always false** for this text-log importer: it cannot establish the installed filter, CAN_29BIT_ID flags, original client process, baud, actual ECU provenance, or VIN acceptance. It emits neither CAN ID nor payload. The classifier is an aid to interpreting an owner-local captured response, never a new acceptance gate. A **candidate** is not a PASS.

Eight new synthetic tests cover both filter polarities, width ambiguity, mixed IDs, corrupt order, negative reply, alternate target and privacy. No C source, real VIN, response payload or 2014D private SQL rows were imported.

## Exact separation of acceptance

1. *Database identification*: same original VIDA version and profile record are selected, with documented `T160/T161` chain.
2. *CarCom service selection*: `T111` ID, mode, `T122` protocol, `T123` bus, `T121` config and `ReadVin.ServiceId` match the selected installed scripts.
3. *J2534 behavior*: actual client `PassThruConnect`, filter installation, channel/baud and 29-bit flags captured in the relevant process/session.
4. *CEM transport*: source-specific B9FB response frames loaded, routed and delivered; audit indicates frame validity only.
5. *VIDA application*: actual ReadVin result and first subsequent ECU-identification request are observed; neither source review nor an odd RX ID proves this.

A previous owner-side VIDA run found B9FB TX requests but no delivered RX. The filter candidate cannot explain **absent** responses; first load the opt-in synthetic B9FB fixture in the isolated guest, then inspect exact RX delivery and actual filter state. Keep the synthetic profile explicitly labelled.

## Licensing, safety and provenance

No top-level `LICENSE` file was retrievable via the repository content API during this review and `pyproject.toml` has no explicit license declaration. This does **not** establish any permission to copy code. No upstream code, SQL credentials, proprietary VIDА XML, raw traces or VINs are included here. Upstream's README states SQL credentials are embedded in its export scripts: never copy, run or redistribute those defaults. Use Virtual Car's existing owner-only bounded metadata readers for the original installed database.

Reviewed blob IDs: [README](https://github.com/spnda/volvo_vida_db/blob/main/README.md) `2e8c7b6857521f3de468b5e24724a12b0549d6dd`; [d2.py](https://github.com/spnda/volvo_vida_db/blob/main/scripts/d2.py) `e029c34798af8e1353d73fb07dd8d19ae4dde03f`; [carcom.py](https://github.com/spnda/volvo_vida_db/blob/main/scripts/carcom.py) `dbacd38a59096a03288a99f23c58ac7f98f520b9`; [vin_decoder.py](https://github.com/spnda/volvo_vida_db/blob/main/scripts/vin_decoder.py) `5e2ccee5e0dbaa417a7b0d20006b253844dc45aa`; [extract_services.ps1](https://github.com/spnda/volvo_vida_db/blob/main/sql/extract_services.ps1) `ddf9d5ad5cc52a92083beab4a7ad3b922e6a467c`.

**Unverified:** original XC90 V8 MY2009 CEM response, actual VIDA 2014D/2015A filter and timing for owner's guest, exact selected GetScript + service lookup, physical DiCE, accepted VIN and detected ECU.
