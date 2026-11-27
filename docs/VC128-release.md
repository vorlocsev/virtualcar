# VC127G / VC128 release evidence

Status: tested local x86 candidate; public release publication is a separate step.

## Source and CI

- Accepted source: `a855acf2b2d7eb0c4b3deeaf1c10cd31ef9b949d`;
  [hosted CI 45974377430](https://github.com/vorlocsev/virtualcar/actions/runs/45974377430): 35/35.
- Integration: `ca9aaf44b64fa926a972b876574324f7345a92b8`;
  [CI 45987447317](https://github.com/vorlocsev/virtualcar/actions/runs/45987447317): success.
- Main merge: `bed22d31a7d5253dab6218f512ab17962ba03426`;
  [CI 45987851858](https://github.com/vorlocsev/virtualcar/actions/runs/45987851858): success, 35/35 verified by the staging script.
- Local candidate CI: 25/25 transport, 10/10 isolated controller groups.
  Hosted CI rebuilds are not the identical locally accepted binary.

## Local binary acceptance (2026-11-27)

VC127G2 clean installation: PASS. VC127G3 operator observations: 9/9.
VC127G4 comparison with VC126 RC1: PASS within tested scope.

| Gate | Evidence |
|---|---|
| Adapter and VIN | Operator PASS; two B9FB responses, 13 delivered frames each |
| Basic ECU identity | 7 HS + 20 LS addresses |
| DTC | Positive read responses across 25 addresses; TCM snapshot and extended data |
| Selected ECM polls | 2769/2769 matched positive requests for D994, D998, DA48 |
| Controller closed | Operator confirmed |
| Profile and registration | Unchanged across acceptance, as reported |

The two versions were tested with different selected DIDs and session counts.
Full extended ECU identity remains partial; T111/T122, physical J2534,
VDASH, SectorV and candidate 30-minute stability are not verified.
The session included 250 NRC 0x31 replies and 56 requests without delivered
responses; only two of three open calls have a recorded close. No OEM accuracy
or complete protocol support is implied.

## Accepted archive

`VirtualCar-VC127G1-FULL-PROFILE-LOCAL-x86.zip`

SHA256: `2D996757E355819848522225B39AE8337F9797D31E71A6B896EA48797C1F28D8`

| Member | SHA256 |
|---|---|
| VirtualCar.exe | `3F550C021F4433659123B1186D9B4DA696D0F87CF90D215C6E7C7DE6BB50235B` |
| VirtualCarJ2534.dll | `D02E05F56337B6A4CBCC1DE070AEC32E23BAE4C47128AF42148606AE2F8DC036` |
| virtualcar.ini | `DB9F9A0BF27D835381510827ECDCA29D8D0CB1BBF427AD99F84FEFDC9828B3AA` |

Keep original ZIP bytes; supply this note, checksum, MIT license and license
scope as companion release assets. Profile redistribution and unredacted VIN
were authorized by the project owner on 2026-11-27; no independent legal
assessment or blanket MIT license over third-party data is implied. Historical
repository review remains incomplete. Do not attach original commercial software,
raw logs or unreviewed screenshots.
