# Stage 60 | Local SQLite laboratory catalog (developer-only)

## What exists and what does not

- Existing: the historical Windows x86 C J2534 emulator and Go control GUI;
  a Stage 59 pure-Go `labcore` lifecycle skeleton.
- New in Stage 60: optional **Python standard-library** SQLite bootstrap and
  catalog authoring helper. It reads the existing checked SQL schema v1,
  creates a new database exclusively, records its SHA-256 migration checksum
  and validates checksum/integrity on every opening.
- **Not yet integrated:** Go headless engine, SQLite driver in Go, named pipes,
  x64 J2534 DLL, scenario runtime compilation, Dvinholm E2E.
- The SQLite database is NOT a live ECU state engine; it is a metadata
  preparation tool until Stage 61/62. No J2534/VIDA clients read it.

## Local start (Windows PowerShell)

Choose a **private** directory outside the Git checkout, with access to
your Windows user only. Avoid personal real VIN/PIN and donor identifiers.

```powershell
$Dir = Join-Path $env:LOCALAPPDATA "VirtualCar\Lab"
New-Item -ItemType Directory -Path $Dir -Force | Out-Null
$Db = Join-Path $Dir "lab.db"
python emulator\tools\lab_catalog.py init "$Db"

# Deliberately generic synthetic lab, not a genuine Volvo ECU profile:
python emulator\tools\lab_catalog.py add-profile "$Db" --id lab-generic --label "Synthetic test car" --platform GENERIC --year 2009
python emulator\tools\lab_catalog.py add-bus "$Db" --id hs-can --profile lab-generic --label "Test CAN" --bitrate 500000 --format 11bit
python emulator\tools\lab_catalog.py add-ecu "$Db" --id synthetic-ecm --bus hs-can --label "Generic ECU" --transport iso15765 --request-id 0x7E0 --response-id 0x7E8
python emulator\tools\lab_catalog.py add-scenario "$Db" --id smoke --revision-id smoke-r1 --label "Generic smoke" --profile lab-generic
python emulator\tools\lab_catalog.py inspect "$Db"
```

All entries are metadata, disabled or draft by default; these commands
**do not cause CAN traffic or ECU replies**. Real Volvo CEM route, VIN, F0,
B9FB and ECU inventory acceptance remain UNVERIFIED.

## Safety and maintenance

- `init` refuses an existing DB and never implicitly migrates it. Creation
  is transactional in a temporary DB on the same filesystem and published
  using an exclusive hardlink (no overwrites on race).
- `inspect` uses SQLite read-only and outputs only counts and invariant
  false flags, never profile IDs, labels, VIN or full error messages.
- The helper refuses database paths under the checked-out Git repository
  and simple symlink destinations. `.gitignore` also covers DB/WAL files
  and encrypted lab artifacts as a second defensive layer.
- A mismatched migration version/checksum fails closed. DO NOT edit applied
  schema 0001 to force a corrupt/old database to load.
- Read-write mode uses foreign keys, WAL, busy timeout and FULL synchronous
  commits; an actual controlled backup/recovery mechanism is a Stage 61 task.
- SQLite metadata can still be private. Keep the DB out of GitHub, CI
  artifacts, chat uploads and shared folders. Avoid entering personal identifiers.
- Old Virtual Car INI-based workflows are unchanged.
- Automatic Dvinholm Stable release gates must NOT infer OEM compatibility
  or authorize ECU configuration changes from this database.

## Tests

```bash
python3 -m unittest discover -s emulator/tests -p 'test_lab_catalog_repository.py'
python3 -m unittest discover -s emulator/tests -p 'test_lab_catalog_schema.py'
```

Ten explicit Stage 60 repository tests and eight Stage 59 SQL schema tests
must be re-run by CI and tracked in `docs/project/STATUS.md`.

Reference: https://github.com/vorlocsev/virtualcar/issues/60
