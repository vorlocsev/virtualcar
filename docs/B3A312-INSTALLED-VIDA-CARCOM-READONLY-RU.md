# B3A312 — подключение к установленной VIDA (read-only)

Windows PowerShell 5.1 adapter: emulator/tools/connect_installed_vida_carcom.ps1

## Purpose

The owner previously installed VIDA under E:\vida, with local SQL Server instance .\VIDA and database CarCom. This new adapter uses local Windows Integrated Security, and checks the installed folder, server, CarCom database and seven original source tables/columns. It does not modify the installation, install drivers, change Registry32, execute stored procedures or generate ECU responses.

Mode Probe checks local connectivity and exact schema metadata. It does not read user profiles:

    powershell.exe -NoProfile -File .\emulator\tools\connect_installed_vida_carcom.ps1 -Mode Probe -VidaRoot 'E:\vida' -ServerInstance '.\VIDA'

The successful result is a small JSON with status=connected, CarCom, and seven_expected_tables_present. A failure emits a bounded JSON object to stderr with `status=failed`, a fixed phase (`preflight`, `connection`, `database`, `schema`, `private_input`, `aggregation`, or `report`), and an exception class; the script exits with code 2. It does not emit SQL strings, original profile identifiers, connection strings, or original data. A `Probe` success does not prove the `Analyze` phase, actual VIDA profile selection, or ReadVin acceptance.

Mode Analyze performs SELECT-only aggregation over original owner-selected profiles:

    powershell.exe -NoProfile -File .\emulator\tools\connect_installed_vida_carcom.ps1 -Mode Analyze -VidaRoot 'E:\vida' -ServerInstance '.\VIDA' -ExactProfiles 'E:\VirtualCar\VIDA-private\p0-exact-43-private.txt' -GeneralProfiles 'E:\VirtualCar\VIDA-private\p0-general-private.txt' -Output 'E:\VirtualCar\VIDA-private\p0-live-cem-001.json'

The two original private input files MUST already exist. The first contains exactly 43 previously selected CarCom.T161_Profile.identifier strings for XC90 V8 MY2009; the second contains 1-8 distinct general comparison profile identifiers. They must come from original VIDA owner-local selections. The tool does not invent or automatically pick these rows. If files are absent or selections are ambiguous/overlap, it fails.

SQL joins:
T161_Profile -> T160_DefaultEcuVariant -> T100_EcuVariant -> T101_Ecu -> T120_Config_EcuVariant -> T121_Config -> T122_Protocol.

The JSON report contains only grouped counts (direct CEM default variants vs other ECU, CEM D2 vs GGD vs other configurations, NULL busRate rows). It does not output source profile IDs, VariantIDs, real busRate values, VIN, CAN identifiers, SQL source, local paths, credentials or private ECU responses.

Safety:
- Local SQL instance only; no remote SQL hosts or SQL authentication.
- Metadata validated from sys.tables/sys.columns before data SELECT.
- Input identifiers bound with SQL @value, not interpolated in SQL.
- Bounded direct-link queries, unique-ID checks, readonly SQL queries.
- Global fail-closed work budget: at most 4096 SQL SELECT operations and 120 seconds checked before each query, with a separate 15-second per-command timeout. Exceeding the budget raises a sanitized aggregation failure; no report is written. This is a bounded sequential audit, not a consistent SQL snapshot.
- SQL connection ApplicationIntent=ReadOnly is only a hint, not database permission enforcement; script itself performs only SELECT. Prefer SELECT-only SQL account.
- No UPDATE, DELETE, INSERT, EXEC, ALTER, database configuration, J2534, security, PIN or ECU programming.
- New report FileMode.CreateNew; refuse outputs inside the original VIDA root, repo or over original input files.
- Also refuse a missing report parent directory and any NTFS reparse point (junction or symlink) in its ancestor chain. `GetFullPath` lexical normalization alone does not resolve those aliases. This guard is designed to prevent report writes redirected through a link into VIDA or the repository; it does not establish sandboxing against an actively changing filesystem.
- No consistent SQL Server snapshot guarantee: multiple separate SELECTs. No change to server SNAPSHOT isolation.

Original source may differ in columns, permissions or SQL instance. Schema mismatch is a stop condition, not permission to edit originals.

Vehicle classification remains independent: XC90 V8 MY2009 = P2-Restyling (P2 platform), CEM-H/L unknown, D2/GGD source variants distinct. Default ECU does not prove the real device is present. No replay fixtures auto-enabled.

## Validation boundary

The connector and its schema/SQL static guards are reviewed in GitHub, but local Windows PowerShell 5.1 and the original installed VIDA are not accessible from this chat. Probe and Analyze have NOT executed on the owner's Windows system. Exact-head CI, original VIDA ReadVin/ECU-ID/T111/T122 and physical CEM NOT TESTED. No merge or release.
