# Bounded CarCom T111/T122 reference coverage (research only)

Status: **source-only, synthetic-tested**. Owner-private 2015A SQL Server data
has not been queried. A successful sample is **not** evidence of a selected
ReadVin profile, correct CEM D2 baud, CAN/ISO-TP behavior, or VIN acceptance.

## Purpose and strict scope

The optional `audit_vida_t111_t122_aggregate.py` tool counts only three
classes of sampled reference coverage:
- T111_Service.fkT122_Protocol is NULL;
- non-NULL value resolves to T122_Protocol.id;
- non-NULL value does not resolve.

It scans **at most the first 1000 service rows ordered by T111_Service.id**,
and uses SQL Server EXISTS/NOT EXISTS in one bounded aggregate SELECT.
Python receives exactly four integer counts, no original IDs, text, VIN,
SQL definitions, XML, scripts, ECU packets, or row values. These counts
are not full-catalog coverage. A non-unique order may also limit sample
reproducibility, and even a 1000-row sample is not a vehicle-specific proof.

## Fail-closed gates

Before that optional aggregate, the code connects only to CarCom via the
locally configured Windows-authenticated ODBC DSN. It requires TLS with
certificate validation, validates DB_NAME() == CarCom, reads only fixed
SQL Server metadata catalog queries, and demands exactly one visible
T111_Service and T122_Protocol across SQL schemas with known id and
fkT122_Protocol columns. Ambiguous or missing tables and columns fail
closed. User/database-provided schema identifiers are quoted with SQL
Server bracket escaping; raw private names never appear in output.

Login and query deadlines are 8 seconds. The output is a newly created
JSON file outside the repository, and errors print only generic classes.
ApplicationIntent=ReadOnly is **advisory, not access control**. The local
owner must use a SQL Server login with database SELECT-only permissions
and metadata visibility, with no write access.

## Usage, only after reviewed Windows validation and schema confirmation

Keep output entirely inside the private VMware guest. First verify the
unified metadata-only analysis on this exact 2015A SQL Server and review
catalog visibility and required columns. Then, if the owner approves
reading at most 1000 CarCom service references:

~~~powershell
$python=(Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
$env:VIDA_SQLSERVER_DSN='VIDA_READONLY'
& $python '.\emulator\tools\audit_vida_t111_t122_aggregate.py' --output 'E:\VirtualCar\VIDA-private\t111-t122-sample-001.redacted.json'
~~~

Never upload the report without separately reviewing aggregate privacy.
This phase verifies only whether *some sampled T111 rows* have references
to T122. It does not choose a XC90 V8 MY2009 profile, connect T110/
T100/T160/T161, inspect InitHw values, select ReadVin, or authorize replay.
All those gates remain false in the output. Keep B9FBFrameCount=0.

## Verification

The exact source and 10 regression tests were executed on Linux Python
3.13 with a synthetic mocked SQL Server connection: **10/10 PASS**. The
full pre-existing 48 VIDA tests plus 10 new tests: **58/58 PASS**.
Python compileall: **PASS**. The GitHub blob SHA of both new files was
verified against the local copies.

No original VIDA instance or vehicle data was accessed. Windows Python
3.12, trusted VMware CI on the exact merged SHA, physical J2534, SectorV
and VIDA VIN acceptance remain **NOT TESTED**.
