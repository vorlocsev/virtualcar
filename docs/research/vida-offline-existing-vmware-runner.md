# Offline VIDA SQLite verification on the existing Windows VMware runner

Scope: user-approved storage of **the user's own VIDA research copies** on
the existing persistent owner-controlled Windows self-hosted GitHub Runner.
This is not a recommendation to publish SQLite data or expose SQL Server.

## Local paths on the already configured VMware runner

- Source copies: `E:\VirtualCar\VIDA-private\` (9 SQLite and 9 matching
  `.manifest.json`, directly in this directory, never in checkout/_work).
- Tools: `E:\VirtualCar\VIDA-tools\verify_offline_collection.py` plus
  `verify_vida_sqlite.py` from the conversation's v0.2 ZIP.
- Existing runner Python manifest: `E:\VirtualCar\Tools\python312.path`.

**Run only on Windows** with the same authorized runner label:
`[self-hosted, Windows, X64, virtualcar-win]`.
Keep the source SQLite and manifests private. The source exporter's
read-committed copies were not an atomic nine-database snapshot.

## One-time local copy

Copy all 9 SQLite and 9 manifest files from the owner's completed
`VIDA-offline-full-private` export using a local VMware Shared Folder
or another owner-managed file transfer. Verify the copy is complete before
running any workflow. Never copy private data into
`$env:GITHUB_WORKSPACE`, the `_work` directory, the Git tree, or Actions
artifacts. Set filesystem permissions so that the runner service
account has **read** access; avoid broad/public shares.

Extract the offline v0.2 validator ZIP contents into `E:\VirtualCar\VIDA-tools`.
The scripts require Python 3.10+; the runner's Python 3.12 is suitable.
On the guest, one local dry-run:

~~~powershell
$python = (Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
& $python 'E:\VirtualCar\VIDA-tools\verify_offline_collection.py' --folder 'E:\VirtualCar\VIDA-private'
if ($LASTEXITCODE -ne 0) { throw 'VIDA offline validation failed' }
~~~

This prints only database names, row/table counts, structural metadata
counts and verification booleans, not SQL data, VIN, XML or binary payloads.
The validator verifies SHA256 against manifests, SQLite integrity and row
counts. It cannot verify all source databases were atomically consistent.

## Automatic runner process on VM boot

For a **Windows runner** check
`Get-CimInstance Win32_Service | ? Name -like 'actions.runner.*'`.
If configured as a Windows service, set Automatic start and Start-Service
from elevated PowerShell. If installed only as `run.cmd`, GitHub's official
Windows instructions require the runner to be removed/reconfigured with
`config.cmd` and `--runasservice`; preserve runner label `virtualcar-win`.
Service startup alone will not power on a powered-off VMware guest.

For VMware Workstation Pro, configure the VM's auto-start in the Workstation
host UI and check the host's VMware Autostart Service separately.
If the host is powered off or asleep, a cloud job cannot wake the guest
without another wake/host automation method.

## Owner-only workflow

`.github/workflows/vida-offline-sqlite-verify.yml` uses **manual
`workflow_dispatch` from `main`**, restricts actor to the repository
owner and dispatch branch to main, checks 9 private files via the fixed
local read-only script, and publishes only aggregate stdout. It performs
**no checkout**, installs no packages, performs no data upload, and creates
no artifacts or releases. No copy or script is executed by this workflow
until the owner places the data and tools on the runner. To trigger:
GitHub → Actions → VIDA offline SQLite verification (owner VM) → Run workflow
(main).

This is an intentional owner-accepted security boundary: a private GitHub
repository does NOT isolate persistent self-hosted runner files from
processes run by workflow jobs. Keep CI code reviewed and do not grant
untrusted PR workflows access to the same runner. Autostart the VM and
Windows runner service to avoid manually launching `run.cmd`.
