# Stage 48 | VIDA 2015A ScriptContent: private XML/ZIP lexical triage

This step continues Stage 47 (docs/research/vida-identity-ecu-boundary-il.md)
and the read-only P2 CEM investigation in Issue #4.

## Source-established storage route

Original VIDA 2015A installation logs supplied by the user say the
DiagSwdlRepository database was attached. This proves only installation
activity, not SQL availability or the exact script used by a vehicle.

Two public reverse-engineering projects describe VIDA diagnostic scripts
as XML compressed in ZIP in database
DiagSwdlRepository.dbo.ScriptContent.XmlDataCompressed:

- https://github.com/spnda/volvo_vida_db/blob/main/sql/extract_scripts.ps1
  (metadata tables Script, ScriptCarFunction, ScriptProfileMap, ScriptType,
  ScriptVariant, and ScriptContent by language);
- https://github.com/Tigo2000/Volvo-VIDA/blob/main/scripts/Export-ScriptsToXML.ps1
  (reads ScriptProfileMap, then ScriptContent for a selected profile).

Those projects target VIDA 2014D. Their SQL storage layout has not been
independently verified against every table in the user's 2015A installation.

Stage 47 verified from five original VIDA 2015A .NET DLLs that
RunIdentifyVehicleScript returns VehicleIdentityOutput through a script engine,
and AddVIN/SetX40Serial populate separate identity states. The actual script
SQL/XML content, B9FB dependency, branching, and ECU-profile rules were NOT
recovered. Diagnostic B9FB transport is not an identity success claim.

## New read-only tool

emulator/tools/audit_vida_script_archives.py scans up to 256 locally exported
plain XML files or corresponding one-entry ZIPs without executing VIDA,
connecting to SQL Server or extracting onto disk. It reports only counts for
lexical presence of B9FB/B9F0/B9FC, AddVIN, SetX40Serial and co-occurrence
within the same script file.

The tool excludes XML comments and rejects DTD/ENTITY, symlinks, malformed XML,
unsafe ZIP members, overlarge files and ZIP expansion above 100:1. It never
outputs raw XML, VIN, original script IDs, source paths, binary fragments or
candidate filenames. Report creation is exclusive (never overwrite).
Do not commit/share input files, SQL exports, VIN, credentials or original DLLs.

Example when a private authorized export already exists:

    python emulator/tools/audit_vida_script_archives.py PRIVATE-VIDA-SCRIPTS --output SAFE-vida-script-summary.json

Reports are explicitly lexical-only. Even if B9FB and AddVIN appear in
the same file, this does NOT prove the runtime selected that script, that
the code paths are reachable, or that B9FB becomes a valid VIN. Actual
script metadata and IL evidence must be examined before replay.

## Eight evidence gates

1. Original 2015A XML from an authorized installation is available.
2. Script version/profile mapping in SQL verified for that installation.
3. Runtime identity script selected, not guessed from text.
4. B9FB -> AddVIN/SetX40Serial shown as a reachable control-flow branch.
5. VIN validation and ProfileFromVin/ResolveVin checked separately.
6. ECU identification script and reply checked separately from VIN.
7. No private XML/SQL credentials/VIN/PIN/traces committed to GitHub.
8. Actual VIDA/SectorV acceptance remains unknown until live authorized testing.

Eight local synthetic groups: emulator/tests/test_audit_vida_script_archives.py.
Research tools/tests/docs only; no J2534 DLL changes, no CEM fixture,
VIN substitution, Security Access, ECU programming, or release.
