# Virtual Car dev30: read-only SavvyCAN CSV metadata audit

**Status:** research tool. **NOT a J2534 DLL change, not a replay importer, not a verified CAN map for XC90 V8 MY2009.**

The repo [damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering](https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering) includes captures of a **2002 S60 B5244S2 M56** and **2003 V70 D5244T M56 (MY2004)**. Early samples use 250 kbit/s powertrain CAN (Bus 1) and 125 kbit/s body CAN (Bus 0). The current XC90 V8 MY2009 emulator stays at its separately validated 500 / 125 kbit/s settings. **Do not silently replay early-model messages on the 2009 profile.**

Implemented in the independently written Python standard-library script `emulator/tools/analyze_can_csv.py`; no upstream GPL source code was copied.

## Run

```bash
python3 emulator/tools/analyze_can_csv.py "my-private-capture.csv" \
  --source-model "S60" --source-model-year 2002 \
  --bus-speed 0=125000 --bus-speed 1=250000 \
  --output "can-metadata-report.json"
```

For a MY2004 V70 trace use `--source-model "V70 D5244T" --source-model-year 2004`. Bus bitrate flags are **user-declared metadata**, not something a CSV can measure. For the synthetic example:

```bash
python3 emulator/tools/analyze_can_csv.py emulator/samples/can-synthetic-dev30.csv \
  --source-model 'Synthetic P2 test' --source-model-year 2002 \
  --bus-speed 0=125000 --bus-speed 1=250000 \
  --output /tmp/virtualcar-can-summary.json
```

The output is newly created with exclusive-write semantics, so it never overwrites the source CSV or a preexisting report. The report includes `replay_approved: false` even when the model/year text matches the target because a declared model is **not authenticity proof**.

## Accepted input and validation

- SavvyCAN CSV columns: `Time Stamp,ID,Extended,Bus,LEN,D1...D8`; `Dir` is optional. `Time Stamp` is interpreted in **microseconds** for the reviewed traces.
- Classic-CAN payload length `0..8`; invalid LEN values, including unusual `LEN=15` rows observed in one historical capture, are **quarantined and counted** (they are not silently truncated to 8).
- Standard identifiers must fit 11 bits; extended identifiers must fit 29 bits. The ID+extended flag+bus is the key.
- Each payload byte is validated as exactly two hex digits. Output includes **no raw payloads, payload hex, VINs, or ECU credentials**.
- Per-bus frame count, reported bitrate, per-ID period average/min/max, rejected reasons, and activity gaps are recorded. Out-of-order frames are discarded from timing statistics. A gap is not evidence of a key position or successful diagnostic A3/A6 acknowledgment.
- The source model and year are explicit; reports distinguish verified **capture parsing** from unverified **compatibility with XC90 V8 2009**.

## Diagnostic isolation

**Do not** merge this analysis with `emulator/tools/import_p2_trace.py` automatically. That existing tool imports a *verified* matching D2 B9F0/B9FB/B9FC response fixture. The new SavvyCAN tool is for background CAN observations only. The D2 A3/A6 responses remain unknown. The tested B9FB 13-frame fixture and READ128 logic are untouched.

## Validation plan (eight groups)

1. Source-year separation and explicit provenance; no automatic MY2009 replay.
2. 250k/125k capture annotations never mutate 500k/125k emulator defaults.
3. 11-bit vs 29-bit ID and bus identity remain independent.
4. Classic CAN payload lengths and hex bytes are checked; LEN>8 is rejected.
5. Microsecond timestamps produce millisecond period statistics.
6. Out-of-order timestamps and long activity gaps are handled without false ignition claims.
7. Report contains metadata only; no VIN or raw CAN byte payload.
8. Original Virtual Car C/Go/Python regression suites continue to run; DLL untouched.

**Original project references:**
- https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering/blob/main/docs/message_format.md
- https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering/blob/main/2002%20Volvo%20S60%20B5244S2%20M56/README.md
- https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering/blob/main/2003%20Volvo%20V70%20II%20D5244T%20M56/README.md
