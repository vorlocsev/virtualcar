# Code provenance and interpretation limits

- emulator/ originates from user-supplied full VirtualCarJ2534 source v0.3.6.6, integrated in dev28 with independently authored observation-only P2 Vehicle Core and READ128 changes; older v0.3.6.1 was an intermediate dev27 experiment.
- proxy/, cmd/oneclick/, trace_attribution/, cmd/trace_summary/ and cmd/ignition_report/ are diagnostic proxy/reporting sources from dev26 and related stages; not the same thing as the actual emulator DLL.
- research/dev23/, research/dev24/, research/dev25/ are historical C99 snapshots retained for comparison.
- User-supplied PRIVATE donor INI/hotfix contains personal vehicle identifiers; it is intentionally excluded from GitHub, CI artifacts and generic distribution.
- Public B9FB, B9F0 and CAN trace excerpts are redacted or synthetic and do not establish complete XC90 V8 MY2009 authenticity.
- olegel/VolvoCan and damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering inform **early P2 CAN research only**. No GPL third-party code is incorporated by copying. See docs/research/.
- Neither a successful CI build nor a synthetic ECU response is evidence that the virtual XC90 V8 MY2009 has been discovered by real diagnostic software.
- Existing proprietary diagnostic software and user-owned original binaries are not redistributed here.
