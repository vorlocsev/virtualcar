# B3A311 — CarCom XC90 V8 MY2009: P2 Restyling / CEM / D2 / GGD

Date: 2026-11-18. Stacked on B3A310 / Draft PR #374. Read-only evidence only.

## Confirmed prior owner findings

Prior offline CarCom research recorded 43 exact XC90 V8 MY2009 profile candidates, nine default ECU rows across two profiles and two candidate CEM variants. The 43 exact profiles had zero direct T136 InitHw links; one more general XC90 MY2009 profile had InitHw with seven populated values. Source: docs/research/vida-offline-inithw-profile-coverage.md and docs/research/vida-offline-carcom-schema-preflight.md. Original profile inheritance, alive ECU and VIDA runtime selection are NOT confirmed.

XC90 V8 MY2009 = P2-Restyling as a model-year catalog hint, not a CEM variant. H/L hardware and D2/GGD diagnostics remain independent of platform phase. Default CarCom variant is not an observed live ECU.

## Implemented

Source: emulator/tools/audit_vida_xc90_cem_candidates.py

Seven allowlisted original CarCom tables are joined from an owner-private immutable SQLite export:
- T161_Profile to find separately supplied exact and general profile identifiers.
- T160_DefaultEcuVariant → T100_EcuVariant → T101_Ecu to count direct default ECU candidates and specifically those with original ECU identifier CEM.
- T120_Config_EcuVariant → T121_Config → T122_Protocol to count matching CEM config rows with D2, GGD and other protocols, and count NULL busRate. Does not output the actual rate.

Input files must exist independently of this tool: exactly 43 original CarCom.T161_Profile.identifier values in an exact-profile text file, and 1–8 separate general comparison profile identifiers in another. No guessed or hardcoded original IDs. The owner must establish input selection provenance independently.

Read-only protection: source-export identity and tables/columns/counts checked; original tables and exporter metadata must be ordinary SQLite tables; physical table mapping unambiguous; values bound in SQL parameters; bounded joins; SQLite mode=ro&immutable=1 and query_only=ON; WAL/SHM/journal sidecars rejected; exclusive output path outside checkout. Missing or corrupt relationships fail closed.

## Windows PowerShell invocation inside owner VMware checkout

Command (one line, from reviewed exact-head checkout; the private files must already exist):

    $py=(Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
    $private='E:\VirtualCar\VIDA-private'
    & $py '.\emulator\tools\audit_vida_xc90_cem_candidates.py' --folder "$private" --exact-profiles "$private\p0-exact-43-private.txt" --general-profiles "$private\p0-general-private.txt" --output "$private\p0-cem-candidates-001-aggregate.json"
    if ($LASTEXITCODE -ne 0) { throw 'Offline CEM candidate audit failed' }

The resulting JSON contains grouped integer counts only: profiles with direct defaults, CEM vs other default variant rows, CEM variants without configs, D2/GGD/other CEM config rows, and NULL busRate rows. No owner ProfileId/VariantId/ConfigId, VIN, actual baud, physical addresses, CAN IDs, original XML/SQL or input path is exported. Even counts should be reviewed before publication.

Always false: owner_profile_selection_provenance_verified, original_sql_server_fk_semantics_verified, actual_selected_vida_profile_verified, profile_parentage_or_effective_inithw_verified, cem_hardware_h_l_verified, client_ecu_alive_verified, original_vida_readvin_accepted, response_fixture_selection_approved.

The vehicle_catalog_hint XC90/B8444S/MY2009/P2-Restyling is **not** source-proven CarCom profile membership; input identifiers are owner-provided.

## Actually executed

Local isolated Linux Python 3.13.5, synthetic data only: 8/8 unittest PASS and compileall PASS. Original SQLite and VIDA were not used. GitHub blob SHA of the two new Python files was verified equal to the locally executed source and tests.

Synthetic fixture: 43 exact profiles, one general comparator, two CEM defaults, one ECM default, two D2 config rows, one GGD config row, one nullable busRate. These numbers are test fixtures, not new claims about original VIDA.

NOT RUN: original owner CarCom export, Windows Python, exact-head CI, x86 native J2534, original VIDA GUI ReadVin/T111/T122, physical ECU. No registry/provider installation, SQL mutation, SecurityAccess, PIN, firmware changes, merge or release.

Next: owner-local original aggregate, then join outcome with original VIDA runtime evidence. No D2/GGD or CEM H/L response may be enabled from this summary.
