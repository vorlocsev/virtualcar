# Code provenance and interpretation limits

- emulator/ originates from user-supplied full VirtualCarJ2534 source v0.3.6.6, integrated in dev28 with independently authored observation-only P2 Vehicle Core and READ128 changes; older v0.3.6.1 was an intermediate dev27 experiment.
- proxy/, cmd/oneclick/, trace_attribution/, cmd/trace_summary/ and cmd/ignition_report/ are diagnostic proxy/reporting sources from dev26 and related stages; not the same thing as the actual emulator DLL.
- research/dev23/, research/dev24/, research/dev25/ are historical C99 snapshots retained for comparison.
- User-supplied PRIVATE donor INI/hotfix contains personal vehicle identifiers; it is intentionally excluded from GitHub, CI artifacts and generic distribution.
- Public B9FB, B9F0 and CAN trace excerpts are redacted or synthetic and do not establish complete XC90 V8 MY2009 authenticity.
- olegel/VolvoCan and damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering inform **early P2 CAN research only**. No GPL third-party code is incorporated by copying. See docs/research/.
- Neither a successful CI build nor a synthetic ECU response is evidence that the virtual XC90 V8 MY2009 has been discovered by real diagnostic software.
- Existing proprietary diagnostic software and user-owned original binaries are not redistributed here.

- External source review (2026-11-13): [volvo-vida/volvo-vida-diagnostics applicability](research/volvo-vida-diagnostics-applicability.md) separates generic Python CAN/ISO-TP/UDS/J2534 design from Volvo P2 D2 and XC90 V8 MY2009 evidence. The upstream's V40/V60 DBC files were **not** imported, and no third-party GPL/LGPL/MIT code was copied. The new synthetic D2-vs-ISO-TP boundary tests exercise only existing Virtual Car validators.

- External VIDA database source review (2026-11-13): [spnda/volvo_vida_db applicability](research/spnda-volvo-vida-db-applicability.md) maps actual 2014D CarCom profile and T111_Service concepts, Volvo D2 message handling and a documented odd-extended-RX-ID filter into *read-only research*. Added an offline categorical filter-candidate field to the existing B9FB auditor with synthetic tests only. No source code, SQL credentials, OEM/VIDA XML or private VIN copied; upstream licensing not established.
