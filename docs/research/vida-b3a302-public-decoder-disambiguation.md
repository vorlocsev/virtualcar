# B3A302: public VIN decoding ambiguity audit (offline)

Date: 2026-11-18. Draft, stacked on B3A301 / PR #365.

## Exact examined source

Public independent implementation: [spnda/volvo_vida_db VIN decoder](https://github.com/spnda/volvo_vida_db/blob/main/scripts/vin_decoder.py), Git blob SHA
`5e2ccee5e0dbaa417a7b0d20006b253844dc45aa`.

The open-source `Vehicle.get_vehicle_profiles()` applies nullable
wildcards to general model/year/Partner Group/engine/transmission/body
profile constraints. The separate `decode_vin()` routine instead:
1. Builds a DISTINCT cross product from `components c1, components c2`,
   taking engine from c1 and transmission from c2.
2. If *any* component has non-NULL transmission, its NULL-transmission
   fallback is suppressed globally.
3. If more than one distinct combination remains, requires a matching
   `VehicleProfile` model/year and an exact engine/transmission pair,
   OR accepts a NULL combined transmission with a matching model/year.
4. If only one distinct candidate exists, skips the second profile
   filter entirely.

There is **no model/year/Partner Group equality predicate joining c1
and c2** in the inspected public implementation. This can create
cross-key engine/transmission combinations. This is NOT proof that
Volvo's original VIDA contains the same logic or a defect.

Important limitation: upstream B3A300 already projected out
`fkBodyStyle` and source-row identity. Consequently B3A302 is a
bounded **approximation of the published algorithm**, not an
equivalent rerun of the original VIDA decoder or even the complete
public DuckDB code.

## Files

- `emulator/tools/vida_vin_public_disambiguation.py`: consumes an
  owner-local B3A300 JSON candidates report and original
  `BaseData.dbo.VehicleProfile` table JSON produced read-only by the
  existing separate Draft PR #317 tools. No SQL server connection,
  arbitrary code loading, diagnostic traffic, original vendor DLL
  execution, SQL UPDATE, or Registry operations.
- `emulator/tests/test_vida_vin_public_disambiguation.py`:
  20 synthetic-only tests for source cross-products, exact-match
  filters, global NULL transmission semantics, cross-key warnings,
  capture scopes, and fail-closed file behavior.

## Owner-local use (only after original tables have been captured)

Run in the checkout containing this Draft, using new output filename:

```powershell
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
$candidates = Join-Path $private 'B3A300-vin-model-variant-001.json'
$profiles = Join-Path $private 'BaseData-VehicleProfile-original-001.json'
$output = Join-Path $private 'B3A302-public-disambiguation-001.json'
py -3 emulator/tools/vida_vin_public_disambiguation.py --candidates $candidates --profiles $profiles --output $output
if ($LASTEXITCODE -ne 0) { throw 'B3A302: invalid or unavailable owner-local input' }
```

All original values are preserved **owner-private** in the input
captures and output report, not anonymized and not uploaded. A filtered
table subset cannot prove absence of other matches.

## Interpreting output without false acceptance

- `source_cross_key_pair_count` counts cross-source combinations
  that used different model/year/Partner Group values.
- `only_cross_key_origin_observed` flags combinations with no
  same-key source for their engine/transmission pairing.
- `public_profile_filter_triggered` distinguishes bypass from
  the second exact engine/transmission filter.
- `public_branch_in_available_inputs` is ONLY a branch prediction
  over existing capture rows; it is not a true VIN decoder result.
- `source_same_snapshot_verified=false`: separate captures do not
  attest a single SQL transaction.
- `body_style_discarded_upstream=true`: exact source equivalence
  cannot be established.
- `public_decoder_equivalence_verified=false`,
  `original_vida_decoder_runtime_verified=false`,
  `readvin_gui_acceptance_verified=false`,
  `ecu_identification_verified=false`: remain untested.

Separate evidence still needed: original owner BaseData,
actual selected Partner Group, manual VIN vs J2534 GUI A/B,
original ResponseHandler/AddVIN behavior, ECU-ID/T111/T122.

## Verified locally

Python unittest from standard emulator/tests layout: **20/20 PASS**;
Python compileall: **PASS**. Same source hashes:
- tool: `f2557d1c0ca5a6a0b3a075a819418fe9c3b6d386`
- tests: `dfbb625c1af96a22bf338e2e4c7b680bf11cc7dd`

Exact-head owner VMware CI **not run**. No original VIDA, SQL,
CEM, ECU, J2534, Registry32, Dvinholm, installation, merge or release
changed during this stage.
