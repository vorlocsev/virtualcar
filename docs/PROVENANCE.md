# Code provenance and interpretation limits

- `proxy/`, `cmd/oneclick/`, `trace_attribution/` from Virtual Car dev26 generated in this project.
- `cmd/trace_summary/` from internal dev15 generated in this project, to make GUI assets reproducible.
- `cmd/ignition_report/` from dev26 generated in this project.
- `research/dev23/` CEM router prototype; `research/dev24/` passive LS observer; `research/dev25/` integrated vehicle core. These are historical snapshots, not additional independent runtime modules.
- VolvoCan by olegel was studied to infer provisional broadcast frame positions; no original third-party source was copied into runtime. Verify applicable CAN IDs on target XC90 V8 2009 before enabling them.
- Existing SectorV and VIDA software are not distributed here. Static observations of those programs do not establish real-vehicle ECU replies.
- Existing `VirtualCarJ2534.dll` v0.3.6.6 source was unavailable at bootstrap. A new proprietary binary was not reverse-created or represented as available.
