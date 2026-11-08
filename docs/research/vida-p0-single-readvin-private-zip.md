# VIDA P0: one original ReadVin ZIP, analyzed privately and offline

## Research boundary

The installed VIDA SQL investigation previously identified CLR enum ReadVin = 4
and SQL ScriptType.Id = 7 / Description = ReadVin as separate namespaces.
The installed database was reported to have one Script row for SQL type 7
and 17 ScriptContent language entries. This is a local catalog observation,
NOT proof that this XML was selected during a live VIDA session.

Independent published 2014D extractors (Tigo2000/Volvo-VIDA,
spnda/volvo_vida_db) document ScriptContent.XMLDataCompressed as a ZIP
containing a single XML file; language key 15 was used by an external
extractor. This does not prove that key 15 is correct for every installation.

The original DLL analysis established RunIdentifyVehicleScript,
five-argument GetScript, GetZippedScriptXml, and reflective XML event
handlers. A public 2014D S40 read attempt tested 22F114 and several
B9FB fallback routes. This is not a required XC90 V8 MY2009 sequence.

## Prerequisites

Owner-authorized local SQL instance and trusted SqlServer module
(Invoke-Sqlcmd), Windows PowerShell 5.1+, Python 3, exact source
checkout, and a private directory outside the repository. No
vehicle, physical J2534, PIN, SecurityAccess or programming required.

The PowerShell script uses two fixed SELECT queries: one COUNT_BIG /
DATALENGTH and then one compressed binary row from three catalogued
tables, matching SQL type ID 7, ReadVin description, and explicit
fkLanguage (default 15). The output is bounded to 1 MiB and must
have one matching row and a PK ZIP signature. Invoke-Sqlcmd defaults
to 1024 returned binary bytes, so MaxBinaryLength is explicitly set
and checked against the original SQL DATALENGTH.

## Commands for Windows PowerShell

Use your trusted checkout of this feature branch at C:\VirtualCar-ReadVin
(or replace the path below), and run:

~~~powershell
$repo = "C:\VirtualCar-ReadVin"
$private = Join-Path $env:USERPROFILE "VIDA-private"
New-Item -ItemType Directory -Path $private -Force | Out-Null
$archive = Join-Path $private "readvin-l15.private.zip"
$report = Join-Path $private "readvin-l15.redacted.json"

& "$repo\emulator\scripts\Export-VidaSingleReadVinZip.ps1" -ServerInstance '(local)\VIDA' -LanguageId 15 -OutputZip $archive
py -3 "$repo\emulator\tools\audit_vida_single_readvin_zip.py" $archive --output $report
~~~

The ZIP is a **private original VIDA script archive**; NEVER upload
it or the source MDF, SQL passwords, VIN or J2534 logs. The Python
tool analyzes archive/XML in memory, never extracts XML onto disk
and emits only redacted numeric categories and false acceptance
flags. Both commands refuse overwriting existing outputs.

If connecting to a verified local SQL Server requires explicit
certificate trust, the first script supports opt-in
-TrustServerCertificate with a sufficiently new SqlServer module.
It is off by default. Do not weaken TLS for untrusted connections.

## What a safe report means

- Lexical presence only: F114, B9FB, B9F0, B9FC, AddVIN,
  SetX40Serial in XML text and attributes, without comments.
- Declaration counts: ReadVinComponent, VehicleIdentityOutput,
  candidate event edges and unresolved target nodes.
- Never claims selected VIDA runtime script, B9FB -> VIN branch
  reachability, client VIN acceptance, XC90 V8 MY2009 identity
  verification, or replay approval.
- The existing ZIP/XML validator rejects multiple entries,
  path traversal, encrypted ZIPs, oversized XML, compression
  bombs, DTD/entities and malformed XML. For an unexpected
  original encoding or document shape, stop; do not disable
  these safety checks or silently reinterpret data.

## Next research gate

After the private owner-run report exists, review F114/B9FB
lexical flags and ReadVinComponent -> AddVIN/SetX40Serial
declaration counts, then compare with the pinned original .NET
method IL. A script row matching SQL metadata is not evidence
that VIDA actually selected this script at runtime.

Only a genuine authorized read-only CEM MY2009 RX capture could
authorize a specific emulated reply. Current B9FBFrameCount=0
and StrictRouting remain untouched, with no new Virtual Car
binary publication.
