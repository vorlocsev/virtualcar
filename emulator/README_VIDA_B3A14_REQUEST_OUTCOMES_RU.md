# B3A14: Original VIDA ReadVin request-outcome audit (read-only)

## Scope

Original VIDA 2014D **B3A12** private VIN/Registry32 verified and **B3A13** original VIDA laboratory J2534 configuration loaded with B9FB response frame counts still zero. The next gate is to distinguish actual diagnostic requests, driver TX, timeouts and delivered frames in the *already collected* original B3A13 logs. Neither manual VIN profile acceptance nor an emulator-delivered frame proves an authentic Volvo ECU response.

This tool **never edits** original logs, the VIDA installation, J2534 DLL/registry, PIN/configuration or the owner VIN. No synthetic B9FB/B9F0/F114 response is generated. Do not commit or publish the full VIN, original logs or local owner INI. The aggregate contains only request categories/counts and source SHA256, not raw OEM payload, VIN, PID or local paths.

## Operator (PowerShell 5.1; prior B3A13 evidence)

Unzip the B3A14 operator package into Downloads. Keep the original B3A13 evidence folder unmodified. Original VIDA need **not** run again for this audit.

```powershell
$d="$env:USERPROFILE\Downloads"; $e=Get-ChildItem -LiteralPath $d -Directory -Filter 'B3A13-evidence-*' | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'B3A13-aggregate.json') } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $e) { throw 'No B3A13 evidence found' }; py -3 "$d\B3A14\emulator\tools\audit_vida_b3a14_request_outcomes.py" --b3a13-evidence $e.FullName --out "$d\B3A14-aggregate.json"
```

A new aggregate file is created exclusively; existing files are not overwritten. **Never upload the raw B3A13 evidence folder to the public PR.** Send only the three summary terminal lines and, if needed, the aggregate JSON in a private conversation.

## Classifications

- `NO_READVIN_REQUESTS_IN_EVIDENCE_WINDOW`: only LAB INI/J2534 loading observed in this B3A13 window; run a **new isolated read-only** VIDA request session if needed.
- `REQUESTS_TIMEOUT_NO_DELIVERED_FRAMES`: requested services with real VIDA ERR_TIMEOUT and no emulator-delivered frames.
- `REQUESTS_NO_DELIVERED_FRAMES_RESULT_PENDING`: requests exist, outcome not determined from the logs.
- `EMULATOR_DELIVERY_PRESENT_SOURCE_UNVERIFIED`: data reached the J2534 client; **physical ECU provenance/VIDA automatic VIN acceptance still not established**.
- `FAIL-CLOSED`: B3A13 source report invalid, original log delta sizes changed, or malformed requests/PID scope.

## Historical baseline (not current acceptance)

B3A7 untouched original archive reproduced **8 VIDA requests**, 7 corresponding driver TX, 27/27 VIDA ReadMsgs ERR_TIMEOUT and **zero delivered frames**: 1x `726:22F114`, 2x `40:B9FB`, 4x `50:B9FB`, 1x `51:B9F0`. Last request attempted FIVE_BAUD_INIT observer; no original OEM keyword response was obtained.

B3A14 code was verified against this unmodified historical ZIP and with 16 local synthetic regression tests; B3A8–B3A14 **68/68 local Python tests PASS**. These checks are not an exact-head PR Windows x86 CI run or original VIDA *new* ReadVin success. Original data remains private; PR stays Draft.
