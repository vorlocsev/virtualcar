# B3A334 — passive Procmon CSV: did a candidate process read diagnostic.config.xml?

This stage **does not inspect a running original VIDA instance**. It provides
only an offline, read-only classification of an existing owner-selected
Windows Sysinternals Process Monitor CSV export. It cannot confirm that a
name-matched process is genuine VIDA or applied the file's settings.

Previous, separately checked gates:
- B3A332: an explicitly selected XML file may contain
  UseClientSettings=false / DiagnosticConnection=NoCommConnection.
  A static candidate is not an effective runtime setting.
- B3A333: a passive snapshot can observe a registered virtual J2534
  module path in a name-matched Windows process; that does not establish
  original VIDA process authenticity or which XML was parsed.
- Original VIDA ReadVin and ECU identification remain NOT VERIFIED.

Process Monitor provides file-system operations with Process Name, PID,
Operation, Path and Result columns. Reference:
https://learn.microsoft.com/sysinternals/downloads/procmon

## Only if an authorized CSV capture already exists

Keep the original raw CSV and PML privately **outside the repository and CI**.
Do not upload either file, an XML, VIN or original diagnostic payloads.

Use an exact, operator-reviewed name from a closed set:
iexplore.exe, java.exe, vidamonitor.exe or w3wp.exe.
These are possibilities, not verified VIDA executables. The example below
uses a placeholder name and file path, not a guessed installed location:

    py -3 emulator/tools/audit_vida_procmon_config_read.py --csv "EXISTING_PRIVATE_PROCMON_CSV_PATH" --process-name iexplore.exe

The tool never starts or installs Procmon, VIDA or a service; it does not
read diagnostic.config.xml itself, open J2534, alter anything on disk or
enumerate processes. It reads only the selected CSV, capped at 32 MiB and
300,000 rows. UTF-8 with optional BOM and UTF-16 with BOM are supported.
The CSV must contain Process Name, PID, Operation, Path and Result columns.

It checks exact Windows basename diagnostic.config.xml and the
following events from **one selected name-matched category**:
- CreateFile with Result SUCCESS;
- ReadFile with Result SUCCESS;
- CloseFile with Result SUCCESS.

For a bounded sequence, it groups by PID + normalized Windows path, and
counts when an earlier successful CreateFile occurred before a successful
ReadFile, with no observed intervening CloseFile. Procmon CSV does NOT
provide sufficient Windows handle identity for this to prove these were
the same underlying file handle. A read without the matching prior open
still counts as a read observation, not as a transport failure.

Reported categories include no file I/O, failed-only, open-only,
read-without-prior-open, read-after-same-PID-and-path-open, reads involving
multiple candidate paths and reads by multiple name-matched PIDs.
Counters and zero/one/multiple buckets are the only exported evidence.
There are **no raw paths, PIDs, original timestamps, XML, event details,
process command lines, hashes, VINs or CAN frames** in the output.

The parser rejects missing/duplicate required CSV columns, malformed
selected PID values, oversized CSV/fields, non-CSV files and symlinks.
A failed parse produces one generic error, not original data.

## Strict non-inference

Even a read-after-open SUCCESS does **not** establish:
1. whether the process image was an original authenticated VIDA binary;
2. whether CSV is unfiltered, complete or in chronological event order;
3. whether the chosen process actually parsed or selected the XML;
4. whether NoCommConnection, J2534 or DiCE was *effective at runtime*;
5. whether the B3A333 module snapshot belongs to the **same** session;
6. which GetScript(ReadVin) was selected or executed;
7. real PassThruWriteMsgs/ReadMsgs, accepted VIN or ECU identification.

A positive read observation is an input for a later independently
authorized effective-config/process attribution gate. A negative
observation from a filtered CSV is **not** proof that VIDA never read
any configuration: a service in another process may do so.

No new original VIDA GUI session, SQL execution, registry modification,
physical adapter operation, J2534 driver injection, or CEM frame
synthesis is authorized by this script. The actual emulator DLL,
B9FB/CEM fixtures, main and release builds remain unchanged.
