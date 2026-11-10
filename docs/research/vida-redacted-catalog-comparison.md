# VIDA catalog report comparison (metadata only)

This tool compares two previously generated, redacted JSON reports from
emulator/tools/vida_unified_analyzer.py. It does not connect to SQL Server,
open SQLite databases, read original VIDA records, execute XML/SQL scripts,
or perform any diagnostic operation.

Input 1 must have backend 'sqlite-export', input 2 'sqlserver', and both must
have schema 'virtualcar-vida-unified-catalog-v1' and
status 'metadata_only'. All unverified evidence flags must remain false.
The tool refuses malformed or duplicate JSON keys, unsupported backend
identities, forged verification claims, missing/duplicate candidate edges,
or inconsistent known table/column inventories.

It compares only the fixed allowlist in
emulator/tools/audit_vida_carcom_schema_links.py: known table presence,
known column presence, and 12 service/hardware column-shape candidates.
It never outputs unknown source names, VIN, paths, original application
rows or values. Its output is a newly created JSON file outside Git.

## Owner-local use in the isolated Windows VM

After the reviewed Python tests have passed, generate two separate private
reports using the documented vida_unified_analyzer.py commands, one from
the checkpointed SQLite metadata exports, the other through a restricted
Windows-authenticated SQL Server ODBC DSN. Then:

~~~powershell
$python=(Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
& $python '.\emulator\tools\compare_vida_catalog_reports.py' --sqlite-report 'E:\VirtualCar\VIDA-private\unified-sqlite-001.redacted.json' --sqlserver-report 'E:\VirtualCar\VIDA-private\unified-sqlserver-001.redacted.json' --output 'E:\VirtualCar\VIDA-private\unified-comparison-001.redacted.json'
~~~

An empty discrepancy list is NOT evidence that either database snapshot
is complete, that SQL Server permissions reveal all metadata, that any
foreign-key join matches application rows, or that the selected XC90 V8
MY2009 ReadVin profile/baud/ECU identity is correct. The output explicitly
keeps record_joins_verified, client_vin_accepted,
readvin_execution_verified, and d2_baud_verified false. A discrepancy
is a lead for private, independent investigation, not proof of a bad ECU
configuration.

## Verification and privacy contract

Run locally from the exact reviewed checkout:

~~~powershell
& $python -m unittest discover -s emulator/tests -p 'test_compare_vida_catalog_reports.py' -v
& $python -m compileall -q emulator/tools/compare_vida_catalog_reports.py emulator/tests/test_compare_vida_catalog_reports.py
~~~

Nine synthetic test cases cover matching/different shapes, redaction,
forged verification, duplicate/missing edges, invalid known columns,
duplicate JSON keys, internally inconsistent edge claims, and exclusive output.
In an isolated Linux Python
3.13 environment, 9/9 new tests and 39/39 existing VIDA tests passed
with no skipped cases; compileall passed. The actual owner-private
VIDA source reports and VMware Windows Python 3.12 have NOT been tested.

Never upload original VIDA databases, raw reports, VIN, CAN/J2534 logs,
credentials or vehicle configuration. Keep B9FBFrameCount=0; this tool
does not authorize diagnostic replay or ECU programming.
