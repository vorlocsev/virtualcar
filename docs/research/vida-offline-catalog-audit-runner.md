# VIDA offline SQLite catalog audit on owner VMware Runner

## Confirmed prerequisites, 2026-11-08

The owner has already copied all 9 VIDA SQLite databases and 9 matching
manifest files to E:\VirtualCar\VIDA-private on the existing Windows
VirtualCar VMware runner. Their local validator v0.2 reported:

- \`source_count=9\`, \`verified_table_total=269\`,
  \`verified_row_total=59846862\`
- \`all_sha256_verified=true\`, \`all_integrity_ok=true\`
- Windows runner service \`actions.runner.vorlocsev-virtualcar.VirtualCar-CI-WIN\`
  is Running with Auto start mode.

This is a verified **offline file copy** only. It does not imply runtime
VIN acceptance in SectorV/VDASH, executable SQL stored procedure support,
or an atomic cross-database SQL Server export snapshot.

## Goal

Run **owner-only**, **manual** GitHub Actions workflow
\`.github/workflows/vida-offline-catalog-audit.yml\` on \`main\`. Unlike
the earlier validation workflow, this additional workflow:

1. Retrieves only the reviewed auditor and synthetic tests from a
   specific immutable source SHA, with no persisted GitHub credentials.
2. Runs synthetic privacy/structural regression tests.
3. Revalidates the owner-local 9 SQLite copies using the already-installed
   offline v0.2 validator. Does not copy or publish them.
4. Runs the audited Python script over only the following exporter catalog
   tables: \`_vida_meta\`, \`_vida_tables\`, \`_vida_columns\`,
   \`_vida_indexes\`, \`_vida_foreign_keys\`, \`_vida_modules\`.

The Python script uses SQLite \`mode=ro&immutable=1\` and
\`PRAGMA query_only=ON\`; there are no user-table record reads or writes.
It counts schema roles, binary column types, foreign-key/index metadata,
and literal token matches in module names/bodies. Matched module
definitions remain in private process memory. The JSON contains only
fixed category labels, vetted column hints and aggregate counts, not
SQL source code, VIN values, XML, ZIP/BLOB data, IPs or filesystem paths.

Literal keywords include \`ReadVin\`, \`GetScript\`, \`VehicleIdentity\`,
\`VIN\`, \`CEM\`, \`XC90\`, \`F114\`, \`B9FB\`, \`AddVIN\`, and \`SetX40Serial\`.
**A hit is text evidence only**, NOT observed runtime diagnostic traffic
or a resolved CEM / ECU transport route.

No released binaries, no CEM PIN operations, no emulator CAN responses,
no device programming and no public Actions artifacts.

## Owner action

With the VM booted and runner Windows service online, open:
https://github.com/vorlocsev/virtualcar/actions/workflows/vida-offline-catalog-audit.yml

Choose **Run workflow** on \`main\`. The last step prints a bounded JSON
block between \`VIDA_CATALOG_AUDIT_BEGIN\` and
\`VIDA_CATALOG_AUDIT_END\`. The owner can share that JSON and run ID;
do not upload the private SQLite/ZIP datasets. If any privacy regression
fails, the workflow stops before even opening the private databases.

## Interpretation gates after first run

- Verify actual \`ReadVin\` / \`GetScript\` / \`VehicleIdentity\` literal
  count distribution across \`DiagSwdlRepository\`, \`CarCom\`,
  \`BaseData\`, and \`DiagSwdlSession\`.
- Identify whether \`dbo.Script\` and \`dbo.ScriptType\` exist via
  metadata, plus their predefined vetted column categories. Counts are
  NOT evidence of VIN value or selected diagnostic request.
- Follow up with targeted, owner-local, read-only analysis of original
  \`ReadVin\` ZIP/XML and its selection linkage, reporting only redacted
  counters/evidence. Keep the original script on VM.
- Continue Virtual Car's strict identification boundary; don't synthesize
  CEM/ECU replies without an observed matching request and known response.
