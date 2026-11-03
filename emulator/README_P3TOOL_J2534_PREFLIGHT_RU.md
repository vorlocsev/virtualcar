# Virtual Car: P3Tool J2534 read-only compatibility preflight

## Source and limits

Source: user-supplied **3.zip/P3Tool/p3tool.exe** with SHA-256
\`908bbbf4a14fbde97404fe8a95bbca8c988e43a3545237daec3842048d235719\`.
The uploaded static-IL report identifies P3Tool v0.13.7.0, managed
\`SAE.J2534\`, and several **alternative** adapter/channel initialization
branches. Analysis is static: no P3Tool execution, vehicle connection or
proof that these branches are necessarily exercised on one adapter.

Observed J2534 \`PassThruConnect\` combinations:

| Source branch | Protocol (decimal / hex) | Flags | Baud | Virtual Car action |
| --- | --- | --- | ---: | --- |
| standard HS CAN | 5 / 0x5 | 0 | 500000 | channel allocated |
| standard HS ISO15765 | 6 / 0x6 | 0 | 500000 | channel allocated |
| standard LS ISO15765 | 6 / 0x6 | 0x20000000 | 125000 | allocated; flag retained, not a physical LS bus |
| extended LS CAN_PS | 32772 / 0x8004 | 0 | 125000 | ERR_INVALID_PROTOCOL_ID |
| extended LS ISO15765_PS | 32773 / 0x8005 | 0 | 125000 | ERR_INVALID_PROTOCOL_ID |
| CAN_XON_XOFF HS | 268435457 / 0x10000001 | 0x600 | 500000 | ERR_INVALID_PROTOCOL_ID |
| CAN_XON_XOFF LS | 268435457 / 0x10000001 | 0x20000600 | 125000 | ERR_INVALID_PROTOCOL_ID |

These are **P3** client code paths, not proof of P2 CEM MY2009 compatibility.
0x8004/0x8005 name optional J2534-2 pin-switching protocols. A later opt-in
[configuration-only probe](README_CAN_PS_CONFIG_PROBE_RU.md) can allocate a
quarantined 0x8004 channel; default behavior in this table stays unchanged.
The reported flags have provider-specific semantics. Alias-converting
0x8004/0x8005/0x10000001 to 5/6 would be misleading and is not implemented.

## Emulator change

After each \`PassThruConnect\` attempt, Virtual Car writes a fixed 16-byte
big-endian metadata record into its existing local text log:

\`J2534 Connect result protocol/flags/baud/status (BE)\`

Four fields are uint32: requested ProtocolID, Flags, BaudRate, actual J2534
result code. Existing success logging stays unchanged. Failed attempts
are now logged even if the backend cannot allocate a channel. **No change**
to return codes, filters, ISO-TP behavior, profiles or ECU replies.

Each \`SET_CONFIG\` entry writes another fixed metadata record:

\`J2534 SET_CONFIG channel/parameter/value/applied (BE)\`

The final field is \`1\` only for parameter \`DATA_RATE=1\`, which changes
the virtual channel's baud. For the currently unimplemented parameters
\`LOOP_BACK=3\`, \`BIT_SAMPLE_POINT=23\`, \`ISO15765_BS=30\`,
\`ISO15765_STMIN=31\`, \`J1962_PINS=32769 (0x8001)\`, the call preserves old behavior:
returns success but does not implement the hardware/transport option;
the metadata records \`applied=0\`. Unknown parameter values and IDs
are zeroed before logging, not silently emitted. The old label J1962_PINS=779
was an ID/value error: 779 (0x030B) is a pin-pair value, not the parameter ID.

## Safe post-session report (run inside Windows VMware)

After a single diagnostic session with the **new** DLL from CI, execute
from the emulator project directory with Python installed:

\`\`\`powershell
py -3 .\tools\audit_j2534_connect.py "$env:TEMP\SectorVVirtualCar.log" --output "$env:USERPROFILE\Desktop\j2534-connect-audit.json"
\`\`\`

The new report uses an allowlist. Only fixed category labels and counts
are exported; no raw CAN data, VIN, PID, host names, source paths or
arbitrary numeric values. Existing output is never overwritten.
Do not upload the **raw** text log: it includes diagnostic payloads.
Older Virtual Car logs lack the new record and correctly show 0 attempts.

## Gates and remaining work

Eight C groups cover standard CAN/ISO HS, LS and VOLVO_CH2 flag preservation,
extended protocols explicitly rejected, 0x10000001 rejected, null/device
failure, actual baud config, accepted-but-no-effect options and privacy/RX
noninterference. Eight Python groups cover exact log parsing, mode and
failure taxonomy, config no-op reporting, data minimization and output
non-overwrite. CI is software-only; new physical J2534 and VMware guest
tests are not claimed. Existing CEM A3/A6/B9FB and P3 F114 remain unchanged.
