# Issue #4: evidence-only SectorV and J2534 boundary audit

The two existing tools describe **different observational layers**:

- `audit_j2534_discovery.py` produces a redacted
  `virtualcar-j2534-evidence-v1` report. A `delivered` transaction
  proves only J2534 delivery/transport framing, never ECU/client acceptance.
- `audit_sectorv_gate.py` produces a redacted
  `virtualcar-sectorv-gate-report-v1` from **human-curated client events**.
  A 13/13 B9FB matcher is still not proof of VIN parsing, normal mode or
  ECU enumeration.

New `audit_p2_discovery_boundary.py` audits these two safe summaries side
by side. **No matching by timestamps, frame count, CAN ID, or session number**
is performed because no shared request identifier is present in the inputs.
The optional `--same-run-reviewed` switch records only an independent
human provenance review that both summaries belong to the same acquisition.
It does not join their transactions or establish causality.

## Local command sequence

These commands operate on **local private files only**. Do not commit raw
client logs, donor INI, VINs, ECU captures, credentials or generated reports.

```sh
python emulator/tools/audit_j2534_discovery.py /private/j2534.log --output /private/j2534-safe.json
python emulator/tools/audit_sectorv_gate.py /private/curated-events.json --output /private/sectorv-safe.json
python emulator/tools/audit_p2_discovery_boundary.py /private/j2534-safe.json /private/sectorv-safe.json --output /private/stages-safe.json
```

Only after reviewing the provenance of **both** input reports, optionally use:

```sh
python emulator/tools/audit_p2_discovery_boundary.py /private/j2534-safe.json /private/sectorv-safe.json --same-run-reviewed --output /private/reviewed-stages-safe.json
```

The output has only aggregate request counts, transport status categories,
125/500 kbit/s (or unknown/other), 11/29-bit categories, missing channel
counts, safe client event outcomes, and next investigation priority. It never
copies CAN IDs, payloads, channel numbers, original file names, raw A3/E3
operands, passwords or VINs. Existing report files are not overwritten.

## Eight synthetic regression gates

1. Complete B9FB transport and 13/13 matcher remain separate from VIN.
2. Independent report inputs never acquire a synthetic shared-run identity.
3. Missing or partial B9FB J2534 evidence remains a capture/transport task.
4. A3 timeout cannot imply any valid E3/SecurityAccess/normal-mode acceptance.
5. A6, B9F0, P3 delivery cannot establish client ECU identity.
6. Target 40/50, 125/500 kbit/s and unknown routes never merge.
7. Forged positives, malformed fields and private extra fields are rejected.
8. Output excludes private names and refuses overwriting existing files.

Test inputs are invented **synthetic metadata**, not donor ECU responses.
The script requires no physical CAN or Windows driver. New Python tests and
all existing C/Python/Go/MSVC/.NET gates should pass on the exact PR HEAD
before the PR is merged into development.

## Evidence still missing

The known MY2005 SectorV laboratory run contained a B9FB 13/13 matcher,
hardware A3 no-reply observations and zero reachable ECUs. That is **not**
proof of XC90 V8 MY2009 compatibility. The exact client normal-mode
predicate remains unknown. This PR adds no positive A3/A6/B9F0 fixtures,
no programming/security functionality, no J2534 DLL wiring and no release.

Next useful evidence is **one continuous authorized read-only client/J2534
capture** including client acceptance/outcome and validated channel/baud
metadata. The user-reviewed data can then be reduced locally to the two
existing privacy-safe JSON summaries before being considered as evidence.
