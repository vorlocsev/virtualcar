# P0: static ReadVin.ServiceId to T111_Service catalog gate

Scope: offline, owner-authorized VIDA ReadVin XML ZIP and \`carcom.T111_Service.csv\` from the same claimed installation. No SQL access, DLL execution, physical adapter, emulated ECU response, or firmware writes.

The original VIDA scripting code statically reads \`ServiceId\` from a ReadVin node and uses the CarCom provider to obtain a diagnostic service. The public \`spnda/volvo_vida_db\` exporter selects \`id\`, \`service\`, \`mode\`, and other fields from \`carcom.dbo.T111_Service\`; **the numeric \`id\` is the only join key inspected here**. We do not inspect \`service\`, \`mode\`, or binary \`definition\`, and do not infer CAN or D2 bytes from the join.

## Offline local invocation

\`\`\`powershell
py -3 emulator/tools/audit_vida_readvin_service_catalog.py \`
  'C:\VIDA-private\selected-readvin.zip' \`
  'C:\VIDA-private\T111_Service.csv' \`
  --output 'C:\VIDA-private\service-catalog.redacted.json'
\`\`\`

Inputs remain on the owner's machine. The script rejects input symlinks, large/complex XML, multi-entry or risky ZIP members, malformed or oversized CSV files, duplicate XML node IDs, and non-exclusive report outputs. Reports contain only fixed keys, counts and false runtime flags; no VIN, node IDs, ServiceId values, names, raw XML/CSV, paths, trace frames, SQL secrets, or diagnostic responses.

## Conservative evidence rules

- A \`ReadVinComponent\` must contain exactly one direct \`<property name="ServiceId" class="Int" value="..."/>\` with a canonical decimal integer to count as a literal.
- CSV rows must have a unique \`id\` column. Missing matches and duplicate catalog IDs are classified separately.
- A directly declared, enabled propertyhandler setter into that same ReadVin node's \`ServiceId\` blocks a promotion to an unmodified literal join. Its presence is not proof the setter ran. \`disabled\` attribute presence disables a setter, even if the text says \`false\`.
- \`Identifier\` setters are separately counted because they can affect the actual diagnostic request.
- A \`static_unique_catalog_candidate_present=true\` merely indicates lexical numeric equality. It **does not** verify that the two sources are from the same installation, the selected runtime \`GetScript\` result, a dynamically resolved ServiceId, \`T111_Service\` definition, ECU/bus configuration, valid TX/RX, VIN acceptance, or replay eligibility.

## Verification and next gate

Nine synthetic-only local unit tests cover the unique join, missing/duplicate rows, propertyhandler overrides, ambiguous literals, privacy, malformed sources, size and path limits, and exclusive CLI output. No original private ReadVin ZIP or T111 CSV was exercised. The exact-current-head Windows VMware CI has not run.

Next: run this audit locally with the **original selected** private ReadVin ZIP and the **same-installation** T111 CSV. Only if the static match is unambiguous, separately inspect selected \`T111\` service/mode/definition and confirm the matching \`GetScript\` runtime selection before considering wire-level behavior. Never fabricate CEM B9FB/F114 replies based solely on a join.
