# Volvo P2 Informer: observer-only CAN patterns for Virtual Car

Source: drpioneer/Volvo-P2-informer, upstream main commit
9cd3a6f603915e074ac28c73eccec6b7473e8297
(https://github.com/drpioneer/Volvo-P2-informer/blob/9cd3a6f603915e074ac28c73eccec6b7473e8297/volvo-inf2dim.ino).
The README says the Arduino Nano + 2× MCP2515 device was tested on an
XC90 2.5T MY2011. No independently verified MY2009 B8444S CEM fixture or
complete VIDA/SectorV discovery transcript is supplied. Upstream has no
license file, so this change independently implements metadata-only patterns,
not source code. No CAN replay is sourced from this project.

## Source facts versus emulator assumptions

The code defines an extended 29-bit diagnostic sender ID 0x000FFFFE,
LS-CAN 125 kbit/s and HS-CAN 500 kbit/s for 2005+ (250 kbit/s for older
models). It defines a CEM LS frame ID 0x02803008, CEM HS 0x03200408,
ECM 0x01200021, TCM 0x01200005, DEM 0x01204001, REM 0x00800401,
CCM 0x00801001. These are source-labelled IDs. They are not verified for
XC90 V8 MY2009; in particular they are **not** all ECU diagnostic request
addresses, and must not be substituted for Virtual Car's real D2 B9FB
response routing or P3 UDS IDs.

The Arduino ReadVIN source sends the 8-byte CAN payload
03 22 F1 90 00 00 00 00 at 0x000FFFFE over LS-CAN.
It expects an extended frame with CEL_ID 0x02803008. The simple
receiver does not implement a complete ISO-TP flow-control or check for
62 F1 90: this is evidence of a *transmitted request shape*, not a
verified VIN reply/identification sequence. Do not synthesize a CEM
positive response from it.

The source's req[] table includes these non-CEM module families:
ECM CD 7A A6 (500k), TCM CC 6E A5 (500k), DEM CD 1A A6 (500k),
REM CD 46 A6 (125k), and CCM CD 29 A6 (125k). The observer checks
the *complete source-listed selector plus trailing envelope bytes*,
never just the A6 opcode. Therefore CD 7A A6 is not classified as
CB/CF/CA 40/50 A6, and the order of address bytes is not reinterpreted
as a new CEM ECU identification command.

## Added metadata-only labels (all on CAN ID 0x000FFFFE)

| Token | Source family | Required baud | service in audit |
| --- | --- | ---: | --- |
| P2INF_LS_VIN_F190 | source ReadVIN | 125000 | 22F190 |
| P2INF_LS_REM_A6 | REM request from req[] | 125000 | A6 |
| P2INF_LS_CCM_A6 | CCM request from req[] | 125000 | A6 |
| P2INF_HS_ECM_A6 | ECM request from req[] | 500000 | A6 |
| P2INF_HS_TCM_A5 | TCM request from req[] | 500000 | A5 |
| P2INF_HS_DEM_A6 | DEM request from req[] | 500000 | A6 |

The observer is strict about PROTO_CAN, exact 8-byte payload length,
29-bit request ID, model-year-relevant baud, listed selectors and
padding. J2534 tx_received may yield probe_classified even if the
virtual ECU does not respond; this is not client acceptance. The
Python backend-audit output adds these six source-qualified tokens
to the earlier 20-probe coverage matrix. There are no new ECU routes,
RX queue writes or source-derived answers in virtualcar.ini.

No private VIN, raw J2534 logs, source CAN dumps or donor ECU image
are copied into the repo or returned in backend JSONL. This is an
evidence-only improvement for Issue #4, not a fix for missing P2 B9FB
MY2009 fixtures or SectorV normal-mode preparation. Eight C test groups
and eight offline Python regression groups guard noninterference,
attribution, wrong bus/transport, legacy routes and privacy.
