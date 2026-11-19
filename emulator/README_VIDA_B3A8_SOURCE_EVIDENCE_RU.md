# B3A8 | Original VIDA source-evidence and ECU reply provenance

Stage: read-only, no synthetic ECU RX, no altered or anonymized original VIDA/DiCE logs.

## Original 2026-11-11 VIDA B3A7 evidence

Source: owner-provided B3A7-original-VIDA-evidence.zip; ZIP SHA256 CA59D81A2643B5571CCEF22360FE6F0A79BF211B8C7F3E01029357DC572E8B1E. Exact B3A7 HEAD 0722b530aa48a7f1790d5f0dd1dddbe790518705. Staged DLL SHA256 reported in original manifest: AFB19B26C3BA6BE11D3ADD321EC7A90BEF4E005F36EC7B963AC0C8F25E4EF210. The ZIP does not contain that DLL to rehash.

Source files were independently inspected locally: ZIP CRC passed, both original full logs and both since-arm suffixes match byte-for-byte at the arm offsets. All 378 new VirtualCar log lines came from the original VIDA IEXPLORE.EXE PID 00003328.

Requests in actual VIDA order: 726:22F114 (ISO15765 500k), 40:B9FB (CAN_PS 125k), 50:B9FB (CAN 250k), 50:B9FB (CAN 500k), 50:B9FB (relay-assisted 10400 ISO9141/CAN), 40:B9FB (CAN_PS 125k), 50:B9FB (relay-assisted 10400 ISO9141/CAN), 51:B9F0 (ISO9141 10400). Eight attempted requests and 27 of 27 PassThruReadMsgs ERR_TIMEOUT. The 20 later waits are 5000 ms each.

Original B3A7 FIVE_BAUD_INIT input target 0x51 and one input byte, output *capacity* 2. It still returns ERR_NOT_SUPPORTED. Previous B3A6 five exact local ACKs are present (3 relay close + 1 B9F0 + 1 teardown); those acknowledgements are from the J2534 DLL, not ECU RX.

The emulator logs 1 missing P3 F114 fixture, 3 missing D2 fixtures and 3 strict-route rejects. The original B3A7 INI has both D2_40 and D2_50 B9FBFrameCount=0. VIDA ends with Could not retrieve VIN from vehicle. Thus the original VIDA observer is PASS but authentic ECU replies are NOT PROVEN and VIN acceptance FAILED.

## Source compatibility matrix (not permission to inject)

| Existing reference | Possible value | Not yet source-verified for XC90 V8 2009 |
| --- | --- | --- |
| emulator/samples/p2_b9fb_public_redacted.txt | Public historical D2 B9FB CAN frame sample | VIN removed; model and original ECU route unverified |
| emulator/virtualcar-p2-b9fb-demo.ini | Historical redacted B9FB demonstration | Not a captured XC90 V8 reply |
| emulator/virtualcar-p2-b9fb-lab-vin.ini | 13 CAN B9FB frames with substituted lab VIN | Synthetic bytes, not original ECU identity |
| emulator/samples/p2_b9f0_public_excerpt.txt | Historical CAN 0x50:B9F0 trace excerpt | Different protocol and address from ISO9141 0x51:B9F0 |
| emulator/CEM_module_numbers_sanitized.json | Static flash part-number hints | Not an observed live B9F0 reply |
| github.com/MarvinParanoid/VolvoDiagToolkit/blob/main/docs/volvo-protocol.md | Real VIDA capture and D2 codec for 2007 V50 D4164T | Different Volvo platform and engine; not a XC90 V8 source |
| github.com/vtl/volvo-cem-cracker | General P2 CEM generations and CAN speed evidence | No byte-exact response captured for this original session |

## Reproducible fail-closed test

Run locally from the repository root with Python 3.10+:

    python emulator/tools/audit_vida_b3a8_evidence_zip.py PATH_TO_ORIGINAL_B3A7_ZIP --out B3A8-source-verified.json
    python -m unittest discover -s emulator/tests -p test_audit_vida_b3a8_evidence_zip.py -v

The auditor checks the original ZIP CRC, complete raw-log suffixes, immutable offsets and hashes, exact HEAD and operator DLL identity, a single matching PID, the eight request IDs in order, 27 timeouts, absence of successfully logged RX, original FIVE_BAUD_INIT ABI, five local ACKs, and missing fixture diagnostics. Eight independent tests use synthetic bytes only. No OEM raw files are checked into GitHub; original bytes are left unchanged.

The audit report is *aggregate evidence*, not a reconstructed real ECU response. All emitted request records have verified_ecu_response=false and replay_approved=false. If logs unexpectedly show an ECU RX, the auditor fails closed and requires manual trace validation; it cannot convert unknown bytes to a fixture.

## Next step

Obtain and independently cross-check source-accurate read-only responses to ISO9141 51:B9F0, CAN/D2 40/50:B9FB and ISO15765 726:22F114, recording exact vehicle/ECU identity, bus/protocol, address/CAN ID, bitrate, filters, timing, original bytes and immutable trace hash. Do not assign a donor XC70/P3/V50 payload to XC90 V8, and do not invent five-baud keywords or VIN. Keep PR Draft, no merge/release.
