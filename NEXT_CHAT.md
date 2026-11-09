# Virtual Car: продолжение разработки в новом чате

## VERIFIED: P0 operator log-path identity across begin/finish (2026-11-09)

- **Latest code commit `development`:** `43138d2ecf408fc32ebd214f37586697bdcea450`,
  [PR #237](https://github.com/vorlocsev/virtualcar/pull/237) **MERGED**,
  exact-SHA owner-only
  [VMware CI #42578608256](https://github.com/vorlocsev/virtualcar/actions/runs/42578608256)
  **SUCCESS**, **449/449 Python tests**, **29/29 workflow steps**.
- **Real bug fixed:** the two-phase `audit_sectorv_operator_session.py`
  previously checked historical log *content* but not the *source path*
  across `begin` and `finish`. Alternate empty logs or identically
  prefixed clones could create a valid-looking but misattributed session
  report. The collector now stores private canonical-path SHA256 bindings
  for both log sources inside its private manifest, verifies them before
  reading windows, rejects forged/swapped source paths, and never exports
  path tokens or raw paths to either redacted report. Existing canonical
  path aliases remain valid. Eight additional synthetic regression
  cases passed. Old pre-fix collector private manifests must not be
  resumed; start a new `begin` for the actual GUI run.
- **P0 still unresolved [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4):**
  perform one **real SectorV GUI read-only session** in the user's own
  isolated Windows VMware guest using the
  [operator guide](emulator/README_SECTORV_FRESH_WINDOW_RU.md),
  a passive loaded-DLL snapshot while client GUI is open, then finish
  with the six actually observed GUI categories. Current self-hosted
  VMware CI tests code in a runner service context, not real GUI acceptance.
  No true XC90 V8 MY2009 VIN, ECU list, OEM B9FB or physical adapter
  validation evidenced. Do not fabricate missing A3/A6/B9F0 replies,
  touch `main` or publish a release.

---

## VERIFIED: one-run SectorV GUI operator collection (2026-11-09)

- **Latest code commit:** `168dbe77ec472ecd3cae7d6310876c0548d46b28`,
  [PR #235](https://github.com/vorlocsev/virtualcar/pull/235) **MERGED**
  to `development`. Owner-only exact-SHA
  [VMware #42576837517](https://github.com/vorlocsev/virtualcar/actions/runs/42576837517)
  **SUCCESS**: **441/441 Python tests**, **29/29 CI steps**, new
  10/10 operator-collector safety checks, native C J2534 regression,
  x86/x64 builds, .NET and IPC checks.
- **New code:** `emulator/tools/audit_sectorv_operator_session.py` is a
  Python two-phase **operator-only** collector. `begin` exclusively creates
  a local private baseline of the J2534/backend logs and Registry32 provider.
  **After** a separate, genuine read-only GUI run, `finish` requires explicit
  operator assertions for isolated VM, disconnected physical J2534,
  plus six allowlisted, manually observed GUI categories; an optional
  separately captured redacted DLL module snapshot is accepted.
  Existing bounded-prefix, schema/provenance, redaction and GUI triage
  validators are reused. Two new redacted reports result; raw logs, hashes,
  VIN and source paths are never exported. The collector never starts
  SectorV, changes the system or creates ECU traffic. See
  [operator guide](emulator/README_SECTORV_FRESH_WINDOW_RU.md).
- **P0 still unresolved:** [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
  requires a **real authorized SectorV GUI session on the user's own
  Windows VMware guest**, not a service-session CI runner. During it,
  verify the observed selected J2534 DLL, B9FB read-only request and RX
  categories, and GUI VIN and ECU-list observations. No real GUI evidence
  has yet been collected. Do not claim successful XC90 V8 MY2009 OEM VIN,
  ECU identity, VIDA compatibility or physical adapter behavior from
  synthetic CI. No new releases or `main` merge.

---

## VERIFIED: periodic J2534 transport guard and three-source SectorV triage (2026-11-09)

- **Latest native change:** [PR #233](https://github.com/vorlocsev/virtualcar/pull/233),
  squash merged as `da5155ee2550738267ea548678fecaedd8a3fdaa`.
  Exact-SHA owner-only
  [VMware #42574500120](https://github.com/vorlocsev/virtualcar/actions/runs/42574500120)
  **SUCCESS**, **431/431 Python tests**, **29/29 workflow steps** and
  the new native C `PASS J2534 periodic TX: shared protocol, CAN DLC/ID,
  ISO and valid repeat` check. The actual `emulator/src/virtualcar.c`
  now shares side-effect-free `validate_tx_message` across immediate
  `PassThruWriteMsgs` and `PassThruStartPeriodicMsg`, closing the
  previous bypass for protocol mismatch, >8-byte classic CAN,
  30/32-bit CAN IDs and strict ISO15765 extended-address requests.
  Invalid schedules create no periodic slot or ID. Ordinary valid
  tester-present repeating RX remains tested. This is offline only.
- **Earlier GUI diagnostic feature:** [PR #232](https://github.com/vorlocsev/virtualcar/pull/232)
  merged as `65677f363de7906d6b39f8f58764c129cd826dd6`;
  exact-SHA [VMware #42573617336](https://github.com/vorlocsev/virtualcar/actions/runs/42573617336)
  **SUCCESS**, **431/431 Python tests** and **29/29 CI steps**.
  `emulator/tools/audit_sectorv_ui_window_triage.py` accepts an
  **optional third redacted operator module snapshot** in addition
  to the bounded J2534/backend summary and curated GUI states.
  Strict schema and private-data checks do not promote DLL snapshot
  or operator assertions into OEM VIN/ECU acceptance.
- **Unresolved [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4):**
  a genuine SectorV GUI session on the **user's actual isolated
  VMware Windows guest** is still unperformed; the CI runner is a
  different, non-interactive observation scope. The user should
  use [operator instructions](emulator/README_SECTORV_FRESH_WINDOW_RU.md)
  for one read-only run, registered x86 DLL snapshot while GUI open,
  bounded log window, curated GUI status and optionally three-source
  triage. Do not invent CEM replies, publish binaries or claim
  real VIN/ECU success. No modification to `main`.

---

## ACTIVE: P0 genuine SectorV GUI J2534 binding gate (2026-11-09)

- **Latest feature `development` commit:**
  `b3d85ad4c5c665ddaa0aa737d805baa220591c87` (merged
  [PR #230](https://github.com/vorlocsev/virtualcar/pull/230)).
  Its owner-only, exact-SHA
  [VMware CI #42572280068](https://github.com/vorlocsev/virtualcar/actions/runs/42572280068)
  **SUCCESS**: **423/423 Python tests**, **29/29 workflow steps**,
  PowerShell **9/9 existing + 8/8 new** synthetic process-binding /
  local DLL-comparison tests, native C J2534 and x86/x64/.NET/Host checks.
- **New real operator tool, not a GUI test:** run
  `emulator/tools/audit_vmware_sectorv_process.ps1 -OperatorSession`
  **inside the target guest while genuine SectorV is running**.
  It passively lists name-matched process modules and optionally compares
  the registered Registry32 J2534 DLL with an operator-provided **reference**
  using `-ReferenceDll`; never assumes that reference was CI-built.
  Optional `-OutputFile` exclusively creates a new redacted JSON outside
  source tree. Exact byte equivalence is point-in-time only and does not
  prove genuine SectorV identity, a loaded DLL's actual calls, or VIN/ECU
  acceptance. See
  [VM guest instructions](emulator/README_SECTORV_FRESH_WINDOW_RU.md).
- **P0 blocker remains open [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4):**
  CI-runner's Registry32 provider is x86 and has all required named exports,
  but again reported `binary_comparison=different_bytes`,
  `executable_sections=different_bytes` and
  `client_not_observed_in_runner_context` in #42572280068. This is
  **not evidence of a faulty DLL nor the user's GUI guest state**.
  Next concrete step: one permitted, isolated genuine SectorV GUI run
  on the Windows guest, snapshot its loaded registered DLL while open,
  then collect bounded redacted J2534 + backend and operator GUI categories.
  No physical J2534, VIN/coding/PIN/security, made-up CEM fixtures or release.

---

## PRIOR VERIFIED: P0 native J2534 + B9FB transport boundary (2026-11-09)

- **Latest code commit on `development`:**
  `f59fd7a4b5edd40af2fab856a485382882787c22`,
  [PR #228](https://github.com/vorlocsev/virtualcar/pull/228) **MERGED**.
  Exact-SHA [VMware CI #42570483619](https://github.com/vorlocsev/virtualcar/actions/runs/42570483619)
  **SUCCESS**, 29/29 workflow steps, **423/423 Python tests**,
  new native C eight-group D2 retry/supersession checks, x86/x64,
  .NET and synthetic IPC/Host checks. When a recognized CB xx B9
  F0/FB/FC read arrives, the same-channel old staged/queued D2 response
  is cancelled **before** fixture lookup, even if the next target/opcode
  has no recorded reply. Other CAN RX and channels remain unaffected.
  No fabricated positive CEM response or real GUI identity validation.
- **Earlier B9FB validation:** the native `validate_d2_fixture` and Python
  `import_p2_trace.validate_response` now require the terminal `4F`
  for the *published 13-frame, 08-series D2 example*, matching the
  existing Go `p2audit` check. Earlier permissive `48..4E` endings
  could be misclassified as complete transport. Other lengths and
  10-series subforms retain generic validation; this rule is NOT a
  general OEM B9FB schema. New synthetic tests reject corrupted import
  before writing INI and never export VIN or private capture content.
  This change is [PR #226](https://github.com/vorlocsev/virtualcar/pull/226),
  merged as `747261169c443c1e69928ffc2ad0baa34d3319c5`, verified by
  [VMware CI #42569321824](https://github.com/vorlocsev/virtualcar/actions/runs/42569321824)
  **SUCCESS** (423 Python tests, 29/29 workflow steps).
- **Preceding native transport changes, already verified:**
  [PR #225](https://github.com/vorlocsev/virtualcar/pull/225)
  `3cf3a69e200d977ce8b3603f7ed8037e4bd50ba5`
  [VMware #42568202704](https://github.com/vorlocsev/virtualcar/actions/runs/42568202704)
  **SUCCESS** (419 Python, 29/29 steps): J2534 TX CAN ID must fit 29 bits.
  [PR #222](https://github.com/vorlocsev/virtualcar/pull/222)
  added CAN/ISO15765 ProtocolID and classic CAN DLC write guards;
  [PRs #223–224](https://github.com/vorlocsev/virtualcar/pull/224)
  repaired old synthetic tests under the new guards; verified
  [VMware #42567553908](https://github.com/vorlocsev/virtualcar/actions/runs/42567553908)
  on `f50876de93757845bddd8d5be2c2ba13142bb249`, **SUCCESS**.
  [PR #221](https://github.com/vorlocsev/virtualcar/pull/221)
  rejects zero CAN speed on Connect/SET_CONFIG atomically.
  [PR #220](https://github.com/vorlocsev/virtualcar/pull/220)
  verifies synthetic baseline → bounded J2534 window → redacted GUI triage.
- **Unresolved highest-priority [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4):**
  run **one truly isolated and authorized SectorV GUI session on the
  user's Windows VMware guest**, with the selected virtual J2534
  provider and no physical adapter. Use
  [fresh-window operator guide](emulator/README_SECTORV_FRESH_WINDOW_RU.md)
  to capture redacted connection, B9FB 0x40/0x50 transport and
  the GUI's actual VIN and ECU-list categories. Runner's synthetic
  Windows CI does not load SectorV GUI, verify original XC90 V8 MY2009
  B9FB or establish client acceptance. Prioritize *actual observed*
  driver loading/transaction and GUI evidence instead of speculative
  fake A3/A6/B9F0/E3 replies.
- Do not publish binaries, merge `main`, copy raw VIN/INI/log/DLL or
  claim physical J2534/VIDA/SectorV identity acceptance.
  The dated VIDA SQL GetScript work below is a historical,
  independently still-unverified research track.

---

## HISTORICAL: VIDA GetScript any-schema catalog visibility (2026-11-07)

- [PR #166](https://github.com/vorlocsev/virtualcar/pull/166)
  **MERGED** as `21d36b93e49dfb5254177b401b449a0c9493505f`.
  Exact-feature owner-only
  [VMware #42400692068](https://github.com/vorlocsev/virtualcar/actions/runs/42400692068)
  **SUCCESS** with source SHA
  `7d7c03334948e1280746b3a8988bb0175979843e`,
  Python **324**, native x86/x64 CTest **8/8**
  each, C# Host **17/17**, no artifacts.
  Its ASCII shape utility is synthetic-only and
  does not modify actual CEM or J2534 behavior.
- [Draft PR #169](https://github.com/vorlocsev/virtualcar/pull/169)
  carries the all-schema GetScript SQL catalog visibility
  fix with six new source safety checks (expected
  Python **330**, feature VMware unverified).
  Manual trusted source selection was added through
  merged CI-only [PR #170](https://github.com/vorlocsev/virtualcar/pull/170)
  on `main` and [PR #171](https://github.com/vorlocsev/virtualcar/pull/171)
  on `development`. This CI selector is NOT
  a successful feature test; run exact-SHA
  `vmware-development-validation.yml` manually
  before promoting draft.
- **Current unverified source branch**
  `fix/vida-getscript-nondbo-visibility` extends the
  existing read-only Windows catalog tool
  `emulator/scripts/Inspect-VidaGetScriptSchema.ps1`:
  `GetScript` name visibility is now counted
  **across all SQL-visible schemas** while the five
  parameter signatures remain explicitly
  `dbo.GetScript`-only.
  Reports categorical singleton, non-dbo and
  multi-schema ambiguity, never actual schema names.
  A zero count means absent **or hidden from the
  current principal**, not proven missing.
- Six new static source-safety checks extend 8
  catalog tests to 14, expected full Python **330**
  (previous 324 exact-feature verified), but the
  new branch has **NOT YET PASSED** exact-SHA
  Windows VMware/PowerShell or live SQL catalog.
  No SQL call, procedure body, XML, connection
  string, original DLL or VIN is committed.
  Source note:
  [VIDA SQL catalog boundary](docs/research/vida-2015a-getscript-sql-catalog-gate.md).
- Main P0 blocker remains **authorized SQL
  catalog metadata of actual installed 2014D-derived
  offline VIDA 2015A**, selected
  `GetScript(ReadVin=4)` XML, then continuous
  CarCom/J2534/identity/ECU read-only session.
  [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
  is open. No manufactured CEM A3/E3/A6,
  VIN, PIN/security access, ECU programming
  or Virtual Car binary releases.
- [Draft PR #143](https://github.com/vorlocsev/virtualcar/pull/143)
  remains independently blocked on its own exact
  source Windows VMware evidence.

---

## HISTORICAL: Original Util.DLL IsValidVIN shape (2026-11-07)

- [PR #163](https://github.com/vorlocsev/virtualcar/pull/163)
  **MERGED** on `development` as
  `70f67039776b3e1ae2ef54d456ed0571ccdde959`.
  Owner-only manual [VMware #42398799888](https://github.com/vorlocsev/virtualcar/actions/runs/42398799888)
  **SUCCESS** on exact feature
  `77ee751f5283b111b7ad9698e7a6303ae23fbf21`,
  Python **316**, CTest Windows x86/x64 **8/8** each,
  C# Host **17/17**, no artifacts. Post-merge
  [#42399043914](https://github.com/vorlocsev/virtualcar/actions/runs/42399043914)
  **SUCCESS** on exact squash SHA.
  JBoss startup log analyzer and source note are merged.
- Important new original owner-provided `Util.DLL`
  was found in Drive folder (previous filename search
  missed it). SHA-256
  `a0ef808188bab12de429fcb4467a9ceadfbfc3747cfb68580664495550ce263d`.
  Static MethodDef `0x06000278`
  `VinValidator.IsValidVIN` requires nonnull,
  `.Length==17` (UTF-16 code units),
  last six decimal digits via `IsValidChassisNbr`
  -> `IsNumeric` with `Regex.Match("\\D")`,
  and one of four two-letter prefixes:
  `YV`, `PN`, `LV`, `LY`. No whole-VIN
  charset/checkdigit validation in this method.
  The `VehicleResolverService.ResolveVin` caller
  was verified independently.
  **9/9 original-source static checks PASS**.
- [Draft PR #166](https://github.com/vorlocsev/virtualcar/pull/166)
  carries the source note and synthetic-only utility.
  Trusted owner-only manual VMware source selector
  was merged via [CI PR #167](https://github.com/vorlocsev/virtualcar/pull/167)
  into main and [CI PR #168](https://github.com/vorlocsev/virtualcar/pull/168)
  into development. Neither of those baseline runs
  validates the **exact PR #166 feature SHA**.
  Run `vmware-development-validation.yml` with
  `source_ref=research/vida-original-vinvalidator-ascii-shape-gate`
  from main, inspect the source commit and Python test count,
  then and only then promote the Draft.
- New standalone **synthetic ASCII-only** shape
  reference `emulator/tools/vida_vin_shape_ascii.py`
  is NOT wired into emulator, VIDA, CEM or J2534.
  Its eight synthetic regression groups pass locally
  **8/8**. Full Python expected **324** after
  previously Windows-verified 316; exact feature
  Windows VMware has **not** been run yet.
  No real VIN, script XML, SQL or proprietary DLL
  committed. See
  [updated resolver note](docs/research/vida-vin-validator-resolver-profile-il.md).
- Primary P0 remains unresolved: selected
  `DiagSwdlRepository.GetScript(ReadVin=4)`
  script XML and a continuous authorized
  2014D-derived offline 2015A J2534/CarCom
  client run for XC90 V8 MY2009. A string
  matching these weak shape rules is **not**
  VIDA vehicle identity/profile acceptance.
  [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
  remains OPEN. Do not synthesize A3/E3/A6,
  use PIN/SecurityAccess or programming, or
  publish Virtual Car builds.

---

## HISTORICAL: VIDA JBoss WSL/SQL server startup evidence (2026-11-07)

- Source of truth `development` at the start of this task:
  `b85c73baca72207cb0bdb9182665a6651090e17c`,
  [PR #162](https://github.com/vorlocsev/virtualcar/pull/162)
  **MERGED**, docs-only VIN resolver profile evidence.
  The latest verified post-merge VMware is
  [#42396946803](https://github.com/vorlocsev/virtualcar/actions/runs/42396946803)
  on earlier PR #159 merge SHA
  `0541e8282b481da450f30329421eb13023b12994`.
  No exact Windows CI for this new source branch yet.
- Owner's *private* `server.log` 2026-10-29 is a
  **JBoss/WildFly web server log**, not a .NET VIDA
  `ReadVin`/J2534 log. Bounded local inspection:
  **two** sessions, each reporting VIDA web deployment
  and startup, SQL JDBC product, accessserver/BaseData
  initialization, CarCom datasource binding, VIDA2014D
  installed-base label, and **WSL self-integrity failure**
  during `PreLoginAction`. Zero literal `GetScript`,
  `ReadVin`, `DiagSwdlRepository`, `J2534` in this
  file, which is **not** proof those operations never ran.
  WSL is a separate login/provider problem unless
  real client linkage is established.
- [Draft PR #163](https://github.com/vorlocsev/virtualcar/pull/163)
  adds the bounded JBoss startup source-observer and synthetic
  regressions. Trusted owner-only VMware source selector was
  merged via [CI PR #164](https://github.com/vorlocsev/virtualcar/pull/164)
  on `main` and [CI PR #165](https://github.com/vorlocsev/virtualcar/pull/165)
  on `development`. These CI selectors do **not** prove
  the new feature SHA passed. Manually run the existing
  workflow with `source_ref=feature/vida-jboss-startup-provenance-audit`
  before merging this Draft PR.
- New offline private-log categorizer
  `emulator/tools/audit_vida_server_startup.py`:
  two-session boundary counts, strict whitelist,
  no raw log/user/path/VIN export, exclusive output.
  Eight new synthetic Python regressions **8/8 local
  PASS**, expected full Python suite **316**.
  Actual user-supplied server log was inspected
  **only locally**; no original logs committed.
  Windows VMware **NOT YET VERIFIED** on this new
  branch; don't merge before exact feature SHA checks.
  [Full research note](docs/research/vida-jboss-server-startup-wsl-sql-evidence.md).
- Primary P0 still unresolved: actual authorized
  offline VIDA 2014D-derived 2015A `GetScript(ReadVin=4)`
  stored-procedure metadata, selected XML and one
  continuous diagnostic-client CarCom/J2534/identity
  session for XC90 V8 MY2009. Keep
  [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
  open. No CEM A3/A6/B9F0 fabricated response,
  SecurityAccess, PIN, ECU programming, physical
  adapter test or Virtual Car release.
- [PR #143](https://github.com/vorlocsev/virtualcar/pull/143)
  remains Draft pending separate exact-feature VMware.

---

## HISTORICAL: validated XML graph and VIN resolver profile boundaries (2026-11-07)

- [PR #159](https://github.com/vorlocsev/virtualcar/pull/159)
  **MERGED** as `0541e8282b481da450f30329421eb13023b12994`.
  Exact-feature owner-only
  [VMware #42396681284](https://github.com/vorlocsev/virtualcar/actions/runs/42396681284)
  **SUCCESS** with source SHA
  `6774f270cd7b920bb888087c68c1cb5f1d39abb7`:
  Python **308**, native x86 and x64 CTest **8/8** each,
  C# Host **17/17**, no artifacts. Exact-merge
  [post-merge VMware #42396946803](https://github.com/vorlocsev/virtualcar/actions/runs/42396946803)
  **SUCCESS**. The new safe `audit_vida_readvin_xml_graph.py`
  currently knows only **synthetic XML**, not an original
  ReadVin script. Runtime identity flags stay false.
- New original static analysis of
  `BizServices.VehicleResolver.DLL`, pinned SHA
  `31d107b0ca13ae22a2c2f3893c76d38550ac3ce160648d07888866ddafe46720`,
  **8/8 source-only local checks PASS**. A `ResolveVin`
  path calls `VinValidator.IsValidVIN`; other
  overload/override paths consult SQL and construct
  model/year/engine/transmission/vehicle structures.
  `ProfileFromVin` then calls `CreateVehicleProfile`
  with possible `VehicleProfile.Empty` fallback;
  `profileFromComponents` uses composite-vehicle,
  engine and gearbox attributes. **NOT proof this whole
  pipeline executed** in one VIDA session, nor that
  the validator's internal rules or target MY2009
  profile have been verified. Source note:
  [resolver IL audit](docs/research/vida-vin-validator-resolver-profile-il.md).
- Additional owner-supplied `server.log` (1116 lines,
  Oct 2026 JBoss/WildFly/Undertow hosting) contains no
  literal `GetScript`, `ReadVin`, `DiagSwdlRepository`
  or `J2534` event. This is **not** proof VIDA
  never fetched a script; it is a different log source.
- Authorized original `DiagSwdlRepository` SQL rows
  and actual `GetScript(ReadVin=4)` XML are **not available**
  in inspected Drive attachments. Need a separate,
  consented local SQL/private read-only VIDA session to
  test selected XML → CarCom → J2534 → returned
  identity type → VIN resolver → non-empty vehicle
  profile → *live* alive ECU inventory.
- Open P0 [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
  remains **UNRESOLVED**. [Draft PR #143](https://github.com/vorlocsev/virtualcar/pull/143)
  is still pending exact-feature Windows verification.
  No fabricated CEM A3/E3/A6, SecurityAccess/PIN, ECU
  programming, raw VIN/SQL/XML export or Virtual Car release.

---

## HISTORICAL: original VIDA reflective XML identity graph (2026-11-07)

- [PR #158](https://github.com/vorlocsev/virtualcar/pull/158)
  **MERGED** as `4a290fc31f9807de20e005c7b00a009bf245e9a8`;
  docs-only original-source ReadVinComponent → CarCom → D2
  route boundary, **no emulator code changes**. Its
  post-merge Windows run was not observed as of this audit;
  the last code-bearing verified SHA remains PR #155.
- New local source-only original IL evidence **8/8 PASS**:
  `Script.Parse` reads structural `nodes/node` and
  `handlers/eventhandler`. `EventHandlerCall.Parse` uses
  `node`, `method`, `disabled`, `parameter`.
  `ScriptNode.GetMethods` discovers methods via reflection;
  `ScriptNode.CallMethodCallback` resolves target and
  invokes `System.Reflection.MethodBase.Invoke`.
  `ScriptEngine.GetOutput` resolves the special
  `Output` node. This makes a dynamic XML-directed
  `AddVIN`/`SetX40Serial` call possible, **not
  proven executed**. Original DLLs were not copied.
- [Draft PR #159](https://github.com/vorlocsev/virtualcar/pull/159)
  implements an offline, privacy-safe XML graph inspector.
  Owner-only VMware feature ref allowlist was added through
  merged CI-only [PR #160](https://github.com/vorlocsev/virtualcar/pull/160)
  and [PR #161](https://github.com/vorlocsev/virtualcar/pull/161).
  The **PR #159 exact source SHA** requires manual VM validation
  and a subsequent post-merge run before promotion; do not
  confuse development baseline with feature verification.
- New source-bounded privacy-safe
  `emulator/tools/audit_vida_readvin_xml_graph.py`
  accepts one **authorized local UTF-8 script XML**;
  reports only categorical identity-method event edges,
  count/disabled states and safe booleans. No original
  XML, VIN, script/node IDs, private paths or payloads
  are emitted. DTD/ENTITY, UTF-16, symlinks,
  duplicate node IDs and write inside Git are rejected.
- Eight synthetic `test_audit_vida_readvin_xml_graph.py`
  regression groups **8/8 local PASS**, expected
  complete Python suite **308** after previous
  Windows-verified 300. **New branch Windows VMware
  is NOT YET VERIFIED**. Exact SHA manual feature
  source must pass before merge. No hardware/SQL/VIDA
  execution.
- The actual selected
  `DiagSwdlRepository.GetScript(ReadVin=4)` XML,
  callback path, client-accepted VIN/X40 and
  XC90 V8 MY2009 alive ECU inventory remain **unknown**.
  P0 [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
  stays open. Do not synthesize A3/E3/A6, use
  SecurityAccess/PIN, write ECU or publish Virtual Car
  releases. [Full source audit](docs/research/vida-readvin-reflection-xml-graph-audit.md).

---

## HISTORICAL: VIDA ReadVinComponent to CarCom / D2 route (2026-11-07)

- [PR #155](https://github.com/vorlocsev/virtualcar/pull/155)
  **MERGED** on `development` at
  `cddb73072de75e3dad4020b32cc23f8c83feefd5`.
  Trusted owner-only [VMware #42393664033](https://github.com/vorlocsev/virtualcar/actions/runs/42393664033)
  **SUCCESS** with Source commit
  `73c4f4f2d1436c57fa64871e0e04ea58915550ce`
  (Python **300**, native x86/x64 CTest **8/8** each,
  C# Host **17/17**; no generated release).
  Post-merge [VMware #42393944365](https://github.com/vorlocsev/virtualcar/actions/runs/42393944365)
  **SUCCESS** on exact merged SHA. The private-log VIDA
  auditor now prevents cross-log-session `ReadVin`
  pairing and tracks literal VIDA2014D/2015A labels
  as **provenance only**, not incompatible engines.
- New original-source-only research: the owner's
  offline VIDA 2014D-derived 2015A
  `BizServices.Scripting.ReadVinComponent.Execute`
  configures VehComm, adds a diagnostic parameter,
  calls SetupTester and executes a service. It does
  **not directly call** VehicleIdentityOutput.AddVIN
  or SetX40Serial. The actual selected XML and
  later identity-output script component remain unknown.
- `VehCommBase.setupVehComm` offers independent
  ECU-variant/type/address construction, and the
  service pipeline runs CarCom request handler,
  `DiagnosticVehCommService.execute`, candidate
  ECU configurations, response set and
  `VehicleService.ParseResponse`.
  `VehCom2.J2534.DiagConnection.Send_D2onCan`
  has an explicit ReadVin-check branch and separate
  HS/MS bitrate and retry sources. These are **original
  static call edges**, not measured MY2009 route values
  or positive ECU replies. See
  [source audit](docs/research/vida-readvin-component-carcom-d2-source-audit.md).
- **8/8 offline original source topology checks PASS**
  on three exact SHA-256 pinned assemblies. None of
  these are Windows VMware/physical/SQL/VIDA
  execution tests; no original proprietary binary
  or VIN/ECU data was copied.
- Primary next P0 gate: original **selected**
  `GetScript(ReadVin=4)` XML in an authorized
  offline VIDA 2015A session, effective
  `ReadVinComponent` properties, CarCom route
  and same-run J2534/accepted VIN/ECU evidence.
  Existing [Draft PR #143](https://github.com/vorlocsev/virtualcar/pull/143)
  remains unmerged pending its own verified Windows
  feature SHA; no fake E3/A6, PIN/security access,
  writes, driver installs or published Virtual Car builds.

---

## HISTORICAL: correct 2014D log attribution and session-aware VIDA audit (2026-11-07)

- **User build-context correction (2026-11-07): VIDA 2015A is
  a modified / relabeled offline VIDA 2014D build family**, not an
  independently incompatible diagnostic platform. The earlier claim
  that a `VIDA2014D` log marker excludes the 2015A-labeled
  installation was **incorrect**. The same supplied `VIDA.log`
  literally declares **VIDA2014D** four times across four sessions
  (Sep 25–26, 2026), zero `VIDA2015A` markers and no
  `SP: GetScript` line. These are **source metadata**, not a
  reason to discard the log for 2015A-labeled VIDA research.
  Static original DLL hashes and observed runtime SQL/XML
  are still required for exact behavioral/patch identity.
- **Original ReadVin SQL caller-branch check, offline 8/8 PASS**:
  SHA-pinned original `BizServices.ScriptRepository.DLL` and
  `AppServices.Scripting.DLL` show type-4 ReadVin -> five-arg
  `GetScript` -> `GetOneScriptFromDb`; `GetFromDb` branches on
  profile null versus `CommaSeparate(profile.Profiles)`,
  script-ID empty/nonempty, and ECU-type sentinel -1.
  No SQL rows can raise `ScriptMissingException`, a lookup
  failure distinct from ECU transport/no-VIN; a result
  array returns its first XML, not proof of VIN acceptance.
  See [SQL caller branch note](docs/research/vida-2015a-getscript-sql-catalog-gate.md).
  No SQL, VIDA instance or physical adapter was executed.
- One Sep 26 VIDA2014D SQL failure names **ImageRepository**
  via VehicleImageProvider.GetImage; **not GetScript** or
  DiagSwdlRepository. One J2534 driver **load attempt**
  is logged, without evidence of successful connection.
- `VidaMonitor.log` on Oct 29, 2026 separately detects
  DiagSwdlRepository twice and records VIDA started twice.
  `db_attach_log.txt` separately reports attached databases
  and several orphaned-user relinks. **Dates/sessions are not
  correlated**; no proof this repaired the Sep 26 SQL failure
  or that ReadVin executed.
- [Source provenance note](docs/research/vida-supplied-logs-2014d-session-provenance.md)
  and [pending feature branch](https://github.com/vorlocsev/virtualcar/tree/fix/vida-session-release-provenance-gate)
  extend existing VIDA text auditor with release/session
  boundaries and source-specific error/loading counters.
  Versions in counters are **literal reported release labels**,
  NOT proof of different engines or incompatible protocols.
  Eight synthetic regression groups (#17–24), expected
  Python total **300**; feature Windows VM and physical
  hardware **NOT YET VERIFIED**. Do not merge until exact
  feature-SHA trusted owner-only VMware validation.
- [PR #151](https://github.com/vorlocsev/virtualcar/pull/151)
  was merged as `6ab7e20d4e0ef2ae9334551c7bcf629e86c18413`,
  exact-feature [VMware #42389575016](https://github.com/vorlocsev/virtualcar/actions/runs/42389575016)
  **SUCCESS** (Python **292**, CTest x86/x64 **8/8** each,
  C# Host **17/17**) and post-merge
  [#42389868361](https://github.com/vorlocsev/virtualcar/actions/runs/42389868361)
  **SUCCESS**. [Docs PR #154](https://github.com/vorlocsev/virtualcar/pull/154)
  was merged as `88043c4f0f8927bfae6e22d6c0f3609a5018ef44`
  without a dedicated post-merge Windows run.
- Still missing: **authorized active VIDA2015A** effective config,
  read-only `GetScript(ReadVin=4)` SQL/catalog evidence,
  actual selected XML, and a continuous client/J2534 CEM
  session with accepted VIN and separately confirmed alive ECU.
  Do not synthesize CEM A3/E3/A6, SecurityAccess, PIN, ECU
  programming or publish Virtual Car builds.
- [Draft PR #143](https://github.com/vorlocsev/virtualcar/pull/143)
  native unimplemented marker audit is still awaiting its
  own exact-SHA VMware verification.

---

## HISTORICAL: VIDA 2015A VIN versus X40 and ECU-state evidence (2026-11-07)

- [PR #151](https://github.com/vorlocsev/virtualcar/pull/151)
  **MERGED** as `6ab7e20d4e0ef2ae9334551c7bcf629e86c18413`.
  Exact-source [manual VMware #42389575016](https://github.com/vorlocsev/virtualcar/actions/runs/42389575016)
  **SUCCESS** on `4c4ee7470e398cac78611d7cce4004d8b6aa8518`.
  Post-merge [#42389868361](https://github.com/vorlocsev/virtualcar/actions/runs/42389868361)
  **SUCCESS** on the merge SHA. Manual: **292 Python** passed,
  native CTest x86/x64 **8/8** each, C# Host **17/17**, no artifacts.
  `ReadVin` / explicit `EMPTYPROFILE` triplets now have
  separate categorical evidence in the log auditor; this
  **does not** prove the identity script content or accepted VIN.
- Direct original VIDA2015A static IL follow-up, source-only
  **8/8 checks PASS**:
  `BizServices.Scripting.VehicleIdentityOutput.AddVIN` stores an
  identity string; `SetX40Serial` sets `IsX40` and *overwrites
  the same field*. `AddVIN` does **not** clear `IsX40`.
  `AppServices.VehicleAccess.IdentifyVehicle` consumes
  `GetIdentity`, `get_IsX40`, returns a `VehicleIdentity`
  with type flag `not IsX40`, and has a `VinException` path
  for null identity. Non-null identity is CR/LF-trimmed.
  These are original **static branches and mock test code**, not
  a physical accepted VIN, VIN checksum validation or proof of
  which ReadVin XML branch runs.
- Distinct original ScriptOutputConverter paths are
  `GetAliveEcus`, `GetNotAliveEcus` and
  `GetNotPresentEcus` (MecuReadout not-in-config);
  the not-alive path can consult a **default CarCom ECU**.
  Database expectation is not a positive observed ECU.
  See [original-source audit](docs/research/vida-2015a-identity-vin-x40-ecu-states-il.md).
- Next P0 research gate remains the **actual original VIDA2015A**
  `DiagSwdlRepository.GetScript(ReadVin=4)` selection,
  first returned XML, actual selected VIN/X40 output type and
  separately observed alive/not-alive/not-in-config ECU states,
  plus one authorized read-only VIDA+DiCE/J2534 trace.
  **These outcomes are not yet observed.**
- [PR #143](https://github.com/vorlocsev/virtualcar/pull/143)
  A3/A6 native unimplemented marker audit remains **DRAFT**,
  without exact-source Windows feature validation; do not
  merge or claim its 16 additional tests verified.
- Do not publish Virtual Car builds or upload original DLLs,
  VINs, XML scripts, raw logs, SQL, donor INI, device IDs,
  protected requests, SecurityAccess, PINs or ECU responses.
  No replay, DiCE hardware, real MY2009 VIN, ECU, or vehicle
  acceptance has been confirmed.

---

## HISTORICAL: VIDA 2015A ReadVin SQL and public 2014D fallback evidence (2026-11-07)

- [PR #148](https://github.com/vorlocsev/virtualcar/pull/148)
  **MERGED** as `a3052a0bfa27233a3a296ff127a3e55079151879`.
  Exact-feature [owner-only VMware #42387634616](https://github.com/vorlocsev/virtualcar/actions/runs/42387634616)
  **SUCCESS** on `c715acfa88af5532ea917414195f913fdcd2f244`,
  with **284 Python**, native 8/8 x86 and 8/8 x64, C# Host 17/17 and
  no artifacts. Post-merge
  [#42387878814](https://github.com/vorlocsev/virtualcar/actions/runs/42387878814)
  **SUCCESS** on the exact merge SHA. The SQL catalog helper is
  **not** live-VIDA-2015A-tested; the actual GetScript procedure
  signature and returned XML remain unknown.
- Original 2015A `BizServices.ScriptRepository.DLL` static IL
  inspection now confirms `GetOneScriptFromDb` chooses the
  first `GetFromDb` XML if nonempty (otherwise null), with
  a separate possible `ScriptMissingException` path, and
  `GetZippedScriptXml` performs SQL binary -> ZIP -> XML.
  **8/8 offline source-only checks PASS**; no original DLL is committed.
- New external evidence: published **VIDA2014D**, **2003 S40**
  [read-only unsuccessful trace](https://www.matthewsvolvosite.com/forums/viewtopic.php?start=10&t=102268)
  shows `ReadVin` / `EMPTYPROFILE` GetScript-Fetched-Running,
  P3 `22F114`, then D2 `B9FB` 0x40 and 0x50 across different
  channel/protocol/baud settings with J2534 read errors.
  This is NOT a successful MY2009 XC90 VIN read, script XML,
  accepted ECU, required normal-mode sequence or universal routing.
- [PR #151](https://github.com/vorlocsev/virtualcar/pull/151)
  **DRAFT / FEATURE-SHA NOT YET VALIDATED**:
  metadata-only `ReadVin` script-selection counters and explicit
  `EMPTYPROFILE` with eight synthetic regressions. Expected full
  Python **292**, not yet claimed. Owner-only manual VMware source
  selector was added via CI-only PRs #152/#153; do not confuse
  baseline run with validation of feature PR #151.
- Older [PR #143](https://github.com/vorlocsev/virtualcar/pull/143)
  (A3/A6 native unimplemented marker analysis) is independently
  **DRAFT**; do not merge until verified exact feature Windows SHA.
- Primary P0 blocker remains authorized original **VIDA2015A**
  `GetScript(ReadVin=4, EMPTYPROFILE)` SQL metadata + selected XML
  and a continuous read-only VIDA/DiCE/J2534 client session. Never
  invent A3/E3, PIN, VIN acceptance, ECU inventory or publish
  Virtual Car binaries. No new DiCE/physical adapter test exists.

---

## HISTORICAL: P0 CEM discovery evidence acquisition after B9FB audits (2026-11-07)

**Development checkpoint:** `ba84518c7ee47b2a2d9834c57bc98a73494c3487`
(merged [PR #139](https://github.com/vorlocsev/virtualcar/pull/139)).
Exact feature [VMware #42381421766](https://github.com/vorlocsev/virtualcar/actions/runs/42381421766)
**SUCCESS** on source `31be7b60c6ae5bd10df3b6b23ca7b52ca1618be6`.
Automatic [post-merge #42381987918](https://github.com/vorlocsev/virtualcar/actions/runs/42381987918)
**SUCCESS** on exact merge SHA. Both: Python **276** passed,
Windows native C++ x86/x64 **8/8 CTest** each, C# Host **17/17**,
M5D2eB accepted read/crash/cancel/crash/recovery PASS on x86/x64,
zero uploaded artifacts. Legacy C/Go/.NET gates also passed.

PR #132 added conservative SectorV↔J2534 report boundaries; PR #136
separated B9FB CEM target **40/50/unknown**; PR #139 now separates
`CAN`/`ISO15765`/`other`/`unknown` channel metadata. Target-50
B9FB delivery is still **transport-only**, not a proven client VIN/ECU
acceptance. Do **not** synthesize A3/E3 or normal-mode acceptance.

**Unblocked next work:** Issue [#4](https://github.com/vorlocsev/virtualcar/issues/4)
needs an authorized continuous **read-only** SectorV client + J2534
same-run capture, or a verified client code path tied to the exact
SectorV build. Use existing local source-aware tools, NOT a new
synthetic reply:
1. Record separately the diagnostic client/version, selected fictional or
   authorized model and client-side outcome (B9FB matcher, Hardware CEM
   A3 target 50/40, warning, reachable ECU count); redact at source.
2. Preserve locally the original J2534 transport channel, CAN/ISO15765,
   11/29-bit flags, HS/LS baud, connection and filter status, TX/RX
   timing and read timeout. Never commit raw logs, VIN/INI, ECU dumps,
   protected A3 operands, personal/device IDs or credentials.
3. Run `audit_j2534_discovery.py`, `audit_sectorv_gate.py`, then
   `audit_p2_discovery_boundary.py` on local redacted JSON reports;
   the `--same-run-reviewed` flag is a **manual provenance assertion**,
   never proof of per-transaction matching. Instructions:
   [boundary audit](docs/research/p2-sectorv-j2534-boundary-audit.md).
4. In a real MY2009 V8 session, require independent proof of SectorV
   client VIN acceptance and separate ECU enumeration before any
   new positive read-only fixture. Old MY2005 LAB saw B9FB 13/13
   but A3 no RX, 0 reachable ECUs: not MY2009 acceptance.
5. If no authorized capture exists, mark the acceptance predicate
   **unknown** and do not add invented hardware/identity data.

Dvinholm remains the primary product. Virtual Car stays private and
read-only, with no J2534 driver install, PIN/security access, writes
or published builds. A passing synthetic VM test is **not** a real
DiCE, adapter or SectorV interoperability test.

---

## HISTORICAL checkpoint: B9FB provenance before PR #139 (2026-11-07)

- Private, **read-only** Virtual Car laboratory. Never publish a release,
  register a driver, claim XC90 V8 MY2009 ECU recognition, guess A3/E3
  SecurityAccess, write flash or add fabricated OEM response bytes.
- [PR #132](https://github.com/vorlocsev/virtualcar/pull/132) established
  privacy-safe J2534-versus-SectorV evidence boundaries; post-merge Windows
  [VMware #42378820296](https://github.com/vorlocsev/virtualcar/actions/runs/42378820296)
  **SUCCESS**, Python **260**, native CTest **8/8** per architecture,
  C# Host **17/17**.
- [PR #136](https://github.com/vorlocsev/virtualcar/pull/136) fixed late-P2
  B9FB target **0x40 / 0x50 / unknown** separation, merged as
  `a6855672784953112d384d62b9494162cf66d122`.
  Exact feature [VMware #42380164553](https://github.com/vorlocsev/virtualcar/actions/runs/42380164553)
  **SUCCESS** on `9420807c57ad539746c6f108c3e368406dab5231`:
  Python **268**, native Windows x86/x64 **8/8 CTest**, C# Host **17/17**.
  Automatic post-merge
  [VMware #42380456268](https://github.com/vorlocsev/virtualcar/actions/runs/42380456268)
  **SUCCESS** on the precise merged code commit.
- [PR #139](https://github.com/vorlocsev/virtualcar/pull/139)
  **DRAFT / NOT YET FEATURE-VERIFIED**: adds source `protocol_categories`
  to each J2534 stage and prevents a target-50 `delivered` response with
  solely ISO15765/unknown metadata from skipping source-protocol review.
  Includes eight synthetic test groups (total expected Python **276**);
  do not merge until an **owner-only Windows VMware** run validates exact
  feature HEAD, followed by a post-merge run. No emulator/J2534 DLL
  implementation changed.
- Workflow owner-only feature allowlist was mirrored to `main` and
  `development` via CI-only PRs #140/#141. A baseline CI success
  does **NOT** verify PR #139.
- Issue [#4](https://github.com/vorlocsev/virtualcar/issues/4) remains
  **unresolved**: SectorV MY2005 LAB matched B9FB frames but had no
  accepted A3 Hardware RX, no reachable ECUs; do not generalize to XC90
  V8 MY2009. Full authorized matched client/J2534 acquisition is still
  missing, as is the normal-mode predicate.
- When resuming, check exact GitHub refs, Actions/PR status and real
  logs **before** changing code or claiming completion. Keep any
  captured VIN/INI/CAN or private client material off GitHub.

---

## HISTORICAL checkpoint: M5D-2eB verified (2026-11-07)

Virtual Car remains a PRIVATE synthetic/read-only lab separate from Dvinholm.
No releases, adapter installation, firmware writes, SecurityAccess or genuine ECU
positive responses are authorized. Dvinholm remains the primary product.

### Confirmed live development state

- `development` merge HEAD at this checkpoint:
  `f1c1b7b4a349d89ba81a52fb643ac69de2281055`.
- M5D-2eB isolated Ledger cancellation, expiry and Host-owner race tests
  merged via [PR #125](https://github.com/vorlocsev/virtualcar/pull/125).
  [Manual VMware #42373748380](https://github.com/vorlocsev/virtualcar/actions/runs/42373748380)
  validated exact feature SHA `6eb2b69d205ae1bcc06126e655d98dbc34127b2c`.
- M5D-2eB live Windows C++/C# test merged via
  [PR #128](https://github.com/vorlocsev/virtualcar/pull/128).
  It tests two owned C# Host crashes separated by a cooperative cancel on
  one retained native session and then a **fourth** clean synthetic F187 Host.
  [Feature VMware #42375232666](https://github.com/vorlocsev/virtualcar/actions/runs/42375232666)
  validated exact source `b084c695141c38280e2d4e7bf671449481d8fdcc`:
  x86 and x64 native 8/8 CTest each, new cross-process test PASS on each
  architecture, C# Host 17/17, Python 252, Go/C and managed checks PASS.
- [Post-merge VMware #42375477826](https://github.com/vorlocsev/virtualcar/actions/runs/42375477826)
  completed SUCCESS on exact development SHA
  `f1c1b7b4a349d89ba81a52fb643ac69de2281055`.
  Both x86/x64 Host crash/cancel/crash and final recovery tests actually PASS,
  CTest 8/8 per arch, Python 252, C# 17/17. **Zero uploaded artifacts**.
- Owner-only validation runs on Windows self-hosted VM. Manual feature
  selection is allowlisted on main; workflow files are synchronized with
  development. The fail-closed C++ J2534 DLL is **not linked** to the
  synthetic local Host read path.

### Next unblocked priority

Return to [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4):
read-only XC90 V8 MY2009 CEM identification, specifically verified
SectorV client normal-mode predicate and the A3/A6/B9F0 route/response
evidence. The available MY2005 LAB SectorV example matched B9FB 13/13 but
then saw no hardware A3 RX and zero reachable modules. It does NOT verify
MY2009 compatibility, authorize A3/E3 replies or establish normal-mode
acceptance. No real MY2009 full discovery capture is present in the
repository. Keep B9FB replay and READ128 unchanged.

Best next engineering increment is **evidence-bound**: audit an
anonymized, single continuous client/J2534 trace with actual client
outcome to decide whether transport, identity parsing or subsequent
ECU discovery fails. Require verified provenance before adding any
positive vehicle response. Follow AGENTS.md: focused PR, 6-8 checks,
exact SHA VMware validation when a Windows component changes.

---

## HISTORICAL checkpoint (archived): M4B-2, before M5A integration

Dvinholm remains PRIMARY. Virtual Car is a PRIVATE, read-only development
lab, not a released or registered J2534 driver. Never publish Virtual Car
builds or enable programming/security-access behavior.

### Latest verified development state

- Current development HEAD: `e1d9dc01c1c5a4cf1ecea0cec3d9bb9d097e6299` (latest two commits only refresh handoff/progress documentation).
- [VMware Windows runner validation #42313066763](https://github.com/vorlocsev/virtualcar/actions/runs/42313066763):
  **SUCCESS** on code source commit `c4d436b0aae2262bce440b4b60c7b734accc895c` selected from `development`.
- Python: **252 tests passed**.
- Legacy C host protocol regression: PASS.
- Clang/LLD produced `VirtualCarJ2534.dll` for Windows x86.
- PE validation: **PE32/i386, exactly 14 undecorated J2534 exports**.
- Native x86 legacy DLL route regression and privacy-safe evidence audit: PASS.
- Go tests + vet: PASS.
- Native C++20 x86 and x64 configure/build/CTest: PASS.
- .NET 10 Core, SQLite Storage and Scenario Compiler checks: PASS.
- **M4B-2 actual legacy C DLL vs independently generated C++20 RX parity: 8/8 PASS.**
- No artifacts uploaded, no release/package publication or driver registration.

### Exact proof boundary

The M4B-2 test dynamically loaded the independently built legacy x86 C DLL
and compared its J2534 messages with the separate C++20 ISO-TP RX module on
eight explicitly synthetic F187/F189 scenarios. Compared protocol/status/
flags/size/extra-index and every payload byte; only volatile timestamps were
excluded. This does NOT prove a functional replacement C++ J2534 DLL,
physical CAN/DiCE behavior, VIDA/SectorV/VDASH acceptance, a real XC90 V8
MY2009 identity, or Dvinholm end-to-end operation.

### M5A status: current feature branch requires one fresh VMware run

- [PR #85](https://github.com/vorlocsev/virtualcar/pull/85) remains Draft,
  base `development`, head
  `42df2953cb8287eb81a1e94052020b353a80eb03`.
- It contains the C# .NET 10 one-client Windows Named Pipe preflight:
  current-user-only pipe, 256-bit launch secret, versioned 28-byte frame
  header, 256-byte payload cap, session/generation binding, bounded I/O,
  and only HELLO/KEEPALIVE/GOODBYE. No CAN/ECU commands.
- Nine Windows integration groups are present, including idle accept
  deadline and listener re-arm. An earlier VMware run #42307844300 passed
  9/9 on the older source head recorded in PR #85. The latest head has since
  received CI compatibility fixes in `virtualcar_test.c`, `build-cross.sh`
  and `virtualcar.c`; the current M5A head has NOT yet been validated by
  the VMware workflow.
- The successful run #42313066763 used `source_ref=development`; M5A was
  correctly skipped because `VirtualCar.Service.Checks` is not in
  `development`.
- PR CI runs #42313398352, #42313398144 and #42313398379 on the latest
  M5A head failed before runner assignment (runner_id=0, no executed steps
  or logs). Do not classify these as code-test failures; the current head
  still needs a real run on the private VMware runner.
- [PR #87](https://github.com/vorlocsev/virtualcar/pull/87) is the stacked
  M5B C++20 named-pipe client; [PR #88](https://github.com/vorlocsev/virtualcar/pull/88)
  adds manual M5B VMware validation. Both remain Draft and depend on M5A.
  Do not merge them independently or mark M5 complete.

### Next action

Dispatch the existing owner-only VMware workflow from `main` while selecting
the current M5A source branch:

```powershell
$repo = 'vorlocsev/virtualcar'
gh workflow run vmware-development-validation.yml --ref main `
    -f source_ref=feature/m5a-secure-local-ipc-preflight -R $repo
```

Watch the resulting run and confirm the M5A step reports **9/9** alongside
the Python, native DLL, C/C++, Go and .NET gates. Only then review PR #85.
Do not merge development to main or publish Virtual Car.

Cross-chat trigger: **virtual car**.

---

## Checkpoint 2026-11-06: Stage 47 VIDA identity-script and ECU resolution boundaries, PR #55 merged

- **development squash commit:** `40c2b3f58d7c1c652866ef3b70883b60c2565831`. [PR #55](https://github.com/vorlocsev/virtualcar/pull/55) merged. Research doc, one read-only categorical evidence tool, eight synthetic Python tests ONLY; no J2534/C emulator changes, no original binaries, VIN, D2 fixtures, main, Dvinholm or releases.
- **Original VIDA 2015A DLL IL static analysis:** exact user-provided source `ai/VirtualCar/Distributions/VIDA/jboss/standalone/deployments/VidaEar.ear/VidaWeb.war/Diagnostics`. Five SHA-256-identified assemblies: `AppServices.VehicleAccess.DLL` SHA `3bcaac2ce2dbe0b986a1c8588bbe3d75fe579bb41bb1eada759ccdb7214545a0`, `AppServices.Scripting.DLL` `c5f092eddceac8b9eb583fb9a54536d482402a64797bd3597fd0cc6b387f3b7f`, `BizServices.Scripting.DLL` `d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028`, `BizServices.VehicleResolver.DLL` `31d107b0ca13ae22a2c2f3893c76d38550ac3ce160648d07888866ddafe46720`, `BizServices.CarCom.VehicleServices.DLL` `1735d8ac20d63a20afe13742ea5156cce5a5328392bd3e44d9ec3cd8ae0dbd07`.
- **Verified IL path**: `RunScriptService.RunIdentifyVehicleScript` (0x06000071) gets engine without selected ECU context (constant 4), invokes `RunScript`, returns `VehicleIdentityOutput`. `VehicleAccess.IdentifyVehicle` (0x060000ED) consumes `GetIdentity` and throws `VinException` if null/empty; otherwise creates `VehicleIdentity` with `IsIdentityVin = !IsX40`. `VehicleIdentity..ctor` (0x06000104) `TrimEnd` strips trailing CR/LF, confirmed by original NUnit `VehicleIdentityWithCrLfTest` (0x060000B5).
- `VehicleIdentityOutput.AddVIN/SetX40Serial/GetIdentity` (0x0600037D..7F) store and retrieve the identity, not validate it. **Distinct** `VehicleResolverService.ResolveVin` (0x06000015/17) calls `VinValidator.IsValidVIN` and SQL stored procedure; `ProfileFromVin` uses separate resolve/create profile and empty fallback. The inspected `IdentifyVehicle` method **does not directly call ResolveVin**. `VehicleAccess.PerformEcuIdentification` (0x060000E7) uses separate ECU identification scripts. `MecuReadoutOutput.AddVehicleInfoParam` (0x060002F5) stores parameter name/display value; does not define OEM B9FB schema.
- **Static original DLL check**: 8/8 verified IL invariants (local `/mnt/data/vida_stage47_identity_il_audit.py`, output `/mnt/data/VIDA_stage47_identity_IL_evidence.json`, report `/mnt/data/VIDA_stage47_identity_chain_report_RU.md`). No source DLL binaries/identity data committed. New repo `emulator/tools/audit_vida_identity_boundary.py`: privacy-safe, strict categorical single-run summary, never claims valid profile from transport. `emulator/tests/test_audit_vida_identity_boundary.py`: eight synthetic tests; doc `docs/research/vida-identity-ecu-boundary-il.md`.
- [Windows x86 CI #42212462927](https://github.com/vorlocsev/virtualcar/actions/runs/42212462927): `build` and `native-routes` **success**, **212/212 Python tests**, C/J2534 and Go pass, native checks **22/22 legacy, 46/46 strict, 19/19 strict_queue** + eight native route groups. [VMware LAB package #42212462898](https://github.com/vorlocsev/virtualcar/actions/runs/42212462898): package success, prerelease step skipped, **no guest testing**.
- **Stage48 next**: find actual **SQL/XML identify-vehicle script** supplied via `BizServices.ScriptRepository.IScriptProvider.GetScript` for `getScriptEngineNoEcuContext(4,...)`, likely in `DiagSwdlRepository_Data.MDF` in user's Drive. Need evidence of exact opcode calls B9FB/B9F0 and how script maps data to `VehicleIdentityOutput.AddVIN`. Until verified, **DO NOT claim B9FB directly feeds IdentifyVehicle**. Real SectorV normal-mode predicate still unknown; Issue #4 open.

## Checkpoint 2026-11-06: Stage 46 original VIDA IL B9FB matcher, PR #54 merged

- **development squash commit:** `edb1484b4606a2e671efd9ad42f3e89407e27331`. [PR #54](https://github.com/vorlocsev/virtualcar/pull/54) merged. Only research documentation and eight **synthetic importer tests** added. Emulator C/J2534 code, ECU response payloads, main, Dvinholm and Virtual Car releases not changed.
- Source verified by offline static IL inspection of the user's **original VIDA 2015A .NET DLL files** from `ai/VirtualCar/Distributions/VIDA/jboss/standalone/deployments/VidaEar.ear/VidaWeb.war/Diagnostics`. No DLL, original test-response payload, real VIN or private ECU IDs committed.
- `BizServices.DroResultFileProducer.DLL` SHA256 `99ab19223e14a06cf633e28a3017f2ed41fd52a2e34c3010f9f925a67fd8a307`: `TestWithB9FB` MethodDef `0x0600004E` is a **DRO report-production unit test**, NOT proof of real VIDA/ECU detection. `getRequestType` `0x06000056`: `B9FB -> D2_VEHICLE_INFORMATION enum 17`. `AddParsedResponse` `0x06000057` routes 17 to **generic `addD2Parameters`** and XML; no confirmed OEM B9FB 88-byte universal schema.
- `VehCom2.DLL` SHA256 `3a08f5ff5819396e676eac8751fdb57475e8f76e20488926259993674ec97e82`: `D2ResponseInterpreter.IsPositiveResponse` MethodDef `0x060001CB` confirms `J2534.Data[6] == requestService + 0x40`, and for `requestService=0xB9` additional `Data[7] == requestedOffset`. `D2onCanApplicationDICE.ReadReply` `0x060001C2` rejects a wrong ECU address at `Data[5]`; `ParseMultipleCanFrame` `0x060001C3` checks D2 frame types, intermediate sequence counter and final.
- Static offline IL checks: **8/8 passed**, reported only locally in `VIDA_B9FB_transport_match_RU.md` and privacy-safe evidence JSON. [CI #42210093324](https://github.com/vorlocsev/virtualcar/actions/runs/42210093324): build and native-routes **success**; **204/204 Python tests**, native **22/22 legacy, 46/46 strict, 19/19 strict_queue**, and 8 native routes pass. [VMware package #42210093348](https://github.com/vorlocsev/virtualcar/actions/runs/42210093348): package success, publication skipped, **NOT** guest-client testing.
- New `emulator/tests/test_vida_b9fb_match_contract.py` eight groups explicitly cover positive 13-frame/single-frame reply, wrong B9 block offset F0/FC, wrong positive service, wrong CEM target, missing final/wrong sequence/early final, mixed CAN IDs, preserved negative B9 as negative. All response bytes are invented synthetic zeros after `50 F9 FB`.
- Research doc: `docs/research/p2-vida-b9fb-matcher-il.md`. **No proof** of VIDA/SectorV vehicle acceptance, XC90 V8 MY2009 truth, B9FB checksum, normal-mode predicate or valid A3/E3 positive. Keep Issue #4 open; next focus read-only ECU identification/VIN acceptance path in `BizServices.Scripting.DLL` and `VehicleResolver`, with exact IL owner/source constraints, not speculation or firmware writes.

## Checkpoint 2026-11-06: Stage 45 SectorV client gate evidence boundaries, PR #53 merged

- **development squash commit:** `cd6d7b693f04eea82e70fb7248e20481f92085a1`. [PR #53](https://github.com/vorlocsev/virtualcar/pull/53) merged squash. Only a read-only audit script, eight Python tests and research documentation changed; **J2534 DLL, ECU responses, CEM B9FB/A3/A6/B9F0 fixtures, main, Dvinholm and published releases unchanged**.
- Revisited [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4), [PR #30](https://github.com/vorlocsev/virtualcar/pull/30) and `docs/research/p2-public-capture-followup.md`. The **separate MY2005 LAB** SectorV 1.1.0 client run has B9FB matcher **13 observed / 13 matched / 0 ignored**, then CEM Hardware A3 target50/40 without matching RX and client-reported ~5000/5001 ms timeouts, 24 configured ECU / zero reachable and a normal-mode warning. **This is not an XC90 V8 MY2009 run or an exact client normal-mode acceptance predicate**.
- Previous notes mentioned a proposed `E3 02` positive prefix or 2500-ms acceptance window. Neither has a reproducible verified, same-version SectorV parser method or successful full client trace in the sources currently available. D2 `A3` is listed as Security Access Mode, therefore **no fabricated positive E3, security access simulation, bypass or inferred authorization has been implemented**.
- Added `emulator/tools/audit_sectorv_gate.py`: accepts only tightly allowlisted, human-reviewed one-run **anonymized event JSON** for client-side B9FB matcher, hardware A3, normal-mode warning and ECU count. Rejects mixed run scope, private fields/raw operands, suspicious client versions, duplicates or malformed counts. Output is privacy-safe and **always** reports normal-mode predicate, expected E3 bytes, A3 authorization, B9FB vehicle identity and ECU acceptance as **unknown**, with `replay_approved=false`.
- Added `emulator/tests/test_audit_sectorv_gate.py`: **8 synthetic regression tests**. Research doc `docs/research/sectorv-normal-mode-gate-evidence.md` describes workflow and evidence requirements.
- [CI Windows x86 #42142055385](https://github.com/vorlocsev/virtualcar/actions/runs/42142055385): build/native-routes **completed success**; **196/196 Python tests passed**, Windows x86 DLL/PE exports and C/Go passed, native checks **22/22 legacy + 46/46 strict + 19/19 strict_queue** plus 8 route groups. [VMware package #42142055249](https://github.com/vorlocsev/virtualcar/actions/runs/42142055249): build/package **completed success**, prerelease step skipped; **not** a guest-VMware client run.
- **Next priority / blocker:** exact SectorV client normal-mode predicate and expected CEM response require either a verified 1.1.0 executable with identified parser callsite/execution or one continuous successful read-only SectorV + J2534 capture from a compatible P2 XC90 V8 MY2009, including client outcome. Earlier SectorV.zip and SectorV.DMP were mentioned in past conversations, but no executable is mounted in the current analysis environment. Do not invent method names/response bytes from historical assistant speculation; keep Issue #4 open. Do not publish Virtual Car releases.

## Checkpoint 2026-11-06: Stage 44 privacy-safe CEM B9FB structure audit, PR #52 merged

- **development merge SHA:** `fb6ae9b210443d4a58fef91cfa2d4982ca32eb05`. [PR #52](https://github.com/vorlocsev/virtualcar/pull/52) merged squash. **Source code of emulator/DLL, B9FB replay, ECU response payloads, main, Dvinholm and releases not changed.**
- Added `emulator/tools/audit_p2_b9fb_shape.py`: a **read-only**, privacy-safe analysis of a SINGLE captured-style D2 B9FB response. Reuses `import_p2_trace.validate_response` for D2 transport, then checks whether a block matches the structure of **one** published 88-byte sample (6 binary prefix bytes, 8 CRLF ASCII fields with documented widths), with VIN-shaped field at offset 11. Does **not** treat 0x57 as a verified length definition, generalize model number or checksum, or print VIN/chassis, private paths/PIDs/hosts, frames or hashes.
- Adds `emulator/tests/test_audit_p2_b9fb_shape.py`: **eight synthetic regression groups**, covering exact layout, disagreement of numeric candidates, invalid VIN shape, malformed D2 sequence, negative reply, unknown layout, mixed CAN IDs/target and privacy/multiple sessions/no overwrite. Multiple response sessions now require explicit CLI `--session-index`; no silent longest-session selection.
- [Emulator Windows x86 CI #42115803068](https://github.com/vorlocsev/virtualcar/actions/runs/42115803068): `build` and `native-routes` both **completed success**. Python unittest discover **188 tests passed**, including Stage44 eight groups; existing C/J2534, Windows DLL/exports, Go and native filter checks also passed. [VMware LAB package CI #42115803028](https://github.com/vorlocsev/virtualcar/actions/runs/42115803028): **build/package completed success**, NOT a guest run or client acceptance; prerelease step skipped.
- Research memo: `docs/research/p2-b9fb-identity-shape-audit.md`. Historical MY2005 SectorV client matcher 13/13 B9FB then Hardware/A3 no-RX ~5 s timeouts remains **separate** from XC90 V8 MY2009. A complete genuine client acceptance predicate for normal-mode/identity is **not** known. Read-only audit output always `vehicle_identity_verified=false`, `client_result=client_result_unknown`, `normal_mode_result=unknown`, `checksum_status=unknown`, `replay_approved=false`. A matched sample structure never constitutes a compatible CEM profile.
- **Next highest-priority Issue #4:** obtain one version-bound, read-only full client trace for XC90 V8 MY2009 with B9FB/A3/A6/B9F0, complete channel/baud/flags/CLEAR_RX, exact client parser outcome (acceptance/rejection), and hash/provenance. Without such capture, continue source-only safety tests and published-code study; do NOT invent E3/A3, vehicle configuration, VIN or CEM hardware IDs; no automatic Virtual Car release.

## Checkpoint 2026-11-06: Stage 43 ISO15765 extended-address guard and atomic RX pair, PR #51 merged

- **development squash commit:** `7f6b208d73f6eec2368b6c96c12b1ac30d473899`. [PR #51](https://github.com/vorlocsev/virtualcar/pull/51) merged into development; `main`, Dvinholm, P2 CEM data fixtures, and published Virtual Car releases remain unchanged.
- In **opt-in strict J2534 mode only** (`[Diagnostics] StrictJ2534Filters=1`, default `0`), unsupported `ISO15765_ADDR_TYPE=0x80` / five-byte addressing cannot silently fall through the standard UDS path: flagged ISO15765 filter returns `ERR_NOT_SUPPORTED (1)` before FilterID allocation and flagged ISO15765 TX returns `ERR_NOT_SUPPORTED (1)` with processed `NumMsgs` count; unflagged five-byte filter lengths still return `ERR_INVALID_MSG (10)`. This is an **explicit lack of support**, not an implementation of extended ISO15765 addressing.
- With `EmitIsoRxStart=1`, strict synthetic multi-frame reassembled response `START_OF_MESSAGE` + payload is now queued as an atomic two-slot unit: at 62/64 it fits, at 63/64 or 64/64 neither half enqueues, with queue_full/drop telemetry. Legacy mode and non-segmented responses retain prior behavior.
- **Eight new C host Stage43 groups passed**: explicit flags, five-byte guard, no TX-to-ECU fallthrough, standard single-frame unchanged, FIFO 62/63/64, recovery, independent channels. [Emulator Windows x86 CI #42111999646](https://github.com/vorlocsev/virtualcar/actions/runs/42111999646): build and native-routes both `completed success`; **native legacy 22/22, native strict 46/46, native strict_queue 19/19**, plus eight existing route groups. [VMware package CI #42111999666](https://github.com/vorlocsev/virtualcar/actions/runs/42111999666) completed success: package generation, **NOT VMware guest execution**; prerelease publication step skipped.
- Initial PR CI #42111711059 failed while compiling the *test harness* because PowerShell Add-Type treats an unused C# variable as an error. Fixed in the same PR at head `7b6a0466`; all checks passed on the corrected head. Do not attribute this initial test harness compile error to the DLL.
- **Evidence boundary:** real 5-byte ISO15765 transport, physical CAN CTS/STmin, authentic XC90 V8 MY2009 CEM discovery/normal mode, client SectorV/VDASH/VIDA acceptance, physical DiCE, and VMware guest runs remain unverified. No new OEM positive CEM response or donor VIN introduced.
- **Next:** return to Issue #4 evidence-bound P2 CEM normal-mode/identification gate, or a separate, tightly scoped native regression for concurrent ECU RX/FIFO telemetry if a specific reproducible defect is observed. Do not publish Virtual Car builds automatically.

## Checkpoint 2026-11-05: Stage 42 multi-ECU FC routing, PR #50 merged

- **development merge SHA:** `38756a7aa42e03f7efecb86e092fba840e6d25d9`. [PR #50](https://github.com/vorlocsev/virtualcar/pull/50) merged squash into development, based on previous Stage41 strict J2534 implementation. Source changes: `emulator/src/virtualcar.c`, host C tests, native J2534 PowerShell tests, strict-mode Russian documentation.
- **Only opt-in strict mode** (`[Diagnostics] StrictJ2534Filters=1`) changed. Default `legacy=0` unchanged, including prior P2 D2 B9FB read-only replay and no fabricated CEM A3/A6 response.
- Strict ISO15765 now rejects ambiguous existing FC filter RX/FlowControl CAN IDs or overlapping RX masks with **ERR_NOT_UNIQUE (0x18)** without consuming a FilterID. Filters remain independent per J2534 channel. For **synthetic reassembled** ISO15765 responses longer than seven UDS bytes, an exact 4-byte CAN ID mask and matching physical ECU FlowControl ID are required; functional `0x7DF` uses the responding ECU's physical request ID. Partial/wildcard masks can still authorize synthetic single-frame responses but not multiframe responses.
- [Emulator Windows x86 CI #42110198577](https://github.com/vorlocsev/virtualcar/actions/runs/42110198577): **build + native-routes completed success**. Eight explicit C host Stage42 groups passed, 22/22 native legacy checks, 46/46 native strict checks, including independent ECM `7E8→7E0` and CEM `72E→726` RX, duplicate FilterID rejection, wrong FC route blocking, functional dual-ECU fanout. Existing Python/Go, PE32 and J2534 export tests passed. [VMware LAB package CI #42110198413](https://github.com/vorlocsev/virtualcar/actions/runs/42110198413) **package build completed success only**; no VMware guest test.
- **Proof boundary:** this is a virtual preassembled UDS routing/FC authorization model, not physical CAN CTS/STmin/BS emission; no genuine DiCE or automotive bus behavior, VIDA/VDASH/SectorV acceptance, or XC90 V8 MY2009 identification is proven. No donor VIN, private captures or ECU dumps committed. `main`, Dvinholm and published Virtual Car releases not changed by this PR.
- **Next priority:** Issue #4 evidence-bound P2 MY2009 CEM normal-mode and identification, exact accepted client response predicate or one version-bound real read-only trace; do not synthesize CEM responses without evidence. Secondary transport work: test strict ISO 15765 addressing flags, masked single frames, queue overflow with concurrent ECU responses and actual synthetic FC state transition in laboratory only. No automatic Virtual Car release.

## Checkpoint 2026-11-05: Stage 41 StrictJ2534Filters, PR #49 merged

- **development merge commit:** `7a290d4f74d8a251fa0de0f82852ffed509f544a`. [PR #49](https://github.com/vorlocsev/virtualcar/pull/49) merged squash. `main`, Dvinholm and published Virtual Car releases not changed.
- Introduced optional `[Diagnostics] StrictJ2534Filters=1`, **default 0**. Existing legacy CAN/ISO15765 RX and P2 B9FB fixture behavior are preserved when disabled.
- In strict mode: CAN accepts PASS/BLOCK with ID + optional payload matching and rejects FC with `ERR_NO_FLOW_CONTROL`; ISO15765 accepts only `FLOW_CONTROL_FILTER`, requires a correctly formed `FlowControlMsg`, blocks RX without a matching FC filter, and suppresses START_OF_MESSAGE for rejected responses. CLEAR_MSG_FILTERS, full FilterID and disconnect/reconnect semantics retained.
- **Native Windows x86 verification:** [Emulator CI #42108537380](https://github.com/vorlocsev/virtualcar/actions/runs/42108537380), `build` and `native-routes` both **completed success**. Native filter contract: **22/22 legacy**, **27/27 strict**, including synthetic 20-byte VIN response delivered as a 24-byte `PASSTHRU_MSG` on ISO15765 only with a valid Flow Control filter; no donor VIN printed. Route checks 8/8; host C/J2534, Python, Go, PE32 validation also passed. [VMware LAB CI #42108537553](https://github.com/vorlocsev/virtualcar/actions/runs/42108537553) build/package **success**, **not** a guest VMware test.
- Scope limitation: ISO-TP UDS responses are preassembled inside the synthetic ECU; no actual hardware CAN Flow Control CTS/STmin/BS transmission, extended ISO15765 5-byte addressing, or real DiCE transport is implemented. This does **not** establish authentic XC90 V8 MY2009 ECU discovery or VIDA/SectorV/VDASH acceptance. Real P2 CEM A3/A6/B9F0 replies remain unimplemented without verified captures.
- New documentation: `emulator/README_STRICT_J2534_FILTERS_RU.md`; native tests in `emulator/tools/verify_native_filter_contract.ps1`.
- **Next priority:** evidence-bound read-only Issue #4 CEM P2 MY2009 normal-mode/identification predicate; in parallel extend native strict isolation with payload filtering / multiple ECU response IDs and test FC handling in the **actual application transport** before claiming full ISO-TP Flow Control compatibility. No automatic Virtual Car release.

## Checkpoint 2026-11-05: P3 raw CAN / ISO15765 RX format, PR #47 merged

- **development HEAD после PR #47:** `626a65aa0be0e7405adc763ce28fc34e860f5b20`. [PR #47](https://github.com/vorlocsev/virtualcar/pull/47) merged squash from `fix/p3-f114-transport-format-evidence-20261105` into development. `main`, Dvinholm, выпущенные Virtual Car сборки не менялись.
- В `emulator/tools/audit_j2534_discovery.py` подтверждённый кодовый пробел закрыт: сырые ISO-TP SF/FF на канале `ISO15765` распознаются как `unverified/p3_can_pci_on_iso15765_channel`; уже собранный `62 F1 14` без PCI на `CAN` как `unverified/p3_uds_without_pci_on_can_channel`. Это свидетельствует о несоответствии формата данных и метаданных, **не доказывает дефект ECU**. В P3 дополнительно проверяются противоречивые RX protocol/baud, TX indication и некорректный START_OF_MESSAGE.
- Добавлены **8 синтетических тестовых групп** `emulator/tests/test_audit_p3_mode_boundary.py`: корректные одиночные/многокадровые ответы, SF/FF в неправильном режиме, явно конфликтующие RX-метаданные, индикации J2534, настоящий неверный CF, повтор `F114` (PR #46) и приватность.
- [Emulator Windows x86 CI #41977369404](https://github.com/vorlocsev/virtualcar/actions/runs/41977369404) **completed success**: C/J2534 native code, Python tests, Go, Windows x86 DLL/GUI, native-routes. [VMware LAB package CI #41977369479](https://github.com/vorlocsev/virtualcar/actions/runs/41977369479) **completed success**: сборка и упаковка, не гостевой VMware run. Новых релизов нет.
- **Issue #4 остаётся OPEN**. Причина старого `partial_rx/invalid_iso_tp_framing` в исходном SectorV клиенте ещё не доказана; последние подтверждённые пользовательские VDASH native-данные не содержат повторной пары `22 F1 14`. Следующий критерий: version-bound один реальный read-only LAB capture двух идентичных запросов с контекстом protocol/channel/RxStatus/ExtraDataIndex/CLEAR_RX, сравнить с настоящей DLL. Без исходной трассы нельзя утверждать успешную CEM идентификацию и нельзя придумывать ответы A3/A6/B9F0.


## Checkpoint 2026-11-05: F114 retry attribution, PR #46 merged

- **development HEAD после PR #46:** `d3f50c814a245ec0534265ea178ec6eb6f384ce2`. [PR #46](https://github.com/vorlocsev/virtualcar/pull/46) merged squash; branch `fix/p3-f114-retry-attribution-20261105` была основана на `development`.
- Изменён только `emulator/tools/audit_j2534_discovery.py` и добавлен `emulator/tests/test_audit_f114_retry.py`. Если `22 F1 14` повторён на том же канале до терминального ответа первого запроса, следующий транспортно корректный ответ `62 F1 14` помечается `unverified / identical_f114_retry_unattributable` вместо необоснованного `delivered`. Явные CLEAR_RX, завершённый первый ответ, иной канал/DID и реальные ISO-TP ошибки сохраняют отдельный статус.
- Восемь синтетических групп тестирования: повтор ISO15765, прерванный raw CAN, сброс RX, другой канал, завершённый предыдущий запрос, иной DID, неверный CF, NRC 0x78 + privacy. В исходниках нет VIN, секретов и донорских данных.
- **CI HEAD PR #46:** [Virtual Car Emulator Windows x86 #41976097550](https://github.com/vorlocsev/virtualcar/actions/runs/41976097550) **success** (C J2534, Python regression, Go, Windows x86, native-routes); [VMware LAB package #41976097418](https://github.com/vorlocsev/virtualcar/actions/runs/41976097418) **success** (package build only, НЕ реальный запуск в гостевой VMware).
- **Ограничение:** корневая причина ранее наблюдавшегося `partial_rx / invalid_iso_tp_framing` не установлена. Нельзя доказывать по логическому request_id, что второй идентичный запрос получил именно свой ответ. В текущем этапе не выполнялись SectorV/VDASH, виртуальная машина или физический J2534, не менялись `virtualcar.c`, INI, DLL и ECU-ответы. Не выпускать Virtual Car build как release автоматически.
- **Следующее действие, Issue #4:** при наличии исходного локального обезличенного LAB-снимка с двумя `22 F1 14` провести дифференциальную проверку `CAN` raw ISO-TP и `ISO15765` собранного UDS, включая RX flags/ExtraDataIndex/канал/очистки/время. Без такого снимка продолжать только синтетические тесты и исследование доказательных P2 CEM сообщений, без фиктивных ответов.

## Текущая рабочая ветка: VDASH offline evidence (02.11.2026)

- По присланному пользователем `docs/research/VDASH_RESEARCH_HANDOFF.md` подготовлен отдельный этап `feature/vdash-offline-evidence` от development **`ee9e2cd66d2da9ea2087605f6ea06fc4ecd2ca83`**. PR/HEAD/CI сверять live; VDASH handoff требует оставить PR для review без автоматического merge. Main/Dvinholm/опубликованный prerelease не менять.
- PR #38 research уже merged: `ee9e2cd`; [Emulator #41393643625](https://github.com/vorlocsev/virtualcar/actions/runs/41393643625) и [cross-build #41393643578](https://github.com/vorlocsev/virtualcar/actions/runs/41393643578) success. Его docs-only source HEAD не запускал CI по path filters.
- `docs/research/VDASH_PROTOCOL_EVIDENCE.md` разделяет Handoff/static 2.5.115.79, reported runtime 2.0, SectorV и donor claims. Proprietary binary/IL report и исходный VDASH run в этом этапе не перепроверены; методам GetVin/GetConfig и HTTP Data не назначен CAN смысл. RxStart size4/index0 и VIN size24/index24 подтверждены текущим source/synthetic test, не историческим запуском VDASH.
- Existing discovery audit получил opt-in `--include-obd`: узкие 09 02/49 02 01 и 18DB33F1:3E80, отдельные start indications, source-order/repeat evidence, strict transport boundaries, metadata-only JSON и client_result_unknown. Восемь synthetic групп; локально 164 Python tests OK, 1 expected native-DLL integration skip. Без флага прежняя область/схема; DLL/профили/RX не меняются. Реальных VDASH/VMware/физических запусков нет.
- Следующий материал для объяснения пустого ECU list: связанный полный actual-client read-only trace от Open до UI outcome либо подтверждённый parser/executor predicate той же версии. Свидетельства разных клиентов/версий не объединять; новых положительных CEM fixtures нет. Уточнена прежняя формулировка: ECM7A A6 вне A6 allowlist, но B9F0 target7A распознаётся после поддерживаемого преобразования формата.

## Предыдущий checkpoint: публичное исследование после PR #36 (02.11.2026)

- База этапа `0db3f413bb1d2ae8d626b490d2d30859b3227890`: PR #34–36 уже merged, [Emulator #41392530265](https://github.com/vorlocsev/virtualcar/actions/runs/41392530265) и [cross-build #41392530215](https://github.com/vorlocsev/virtualcar/actions/runs/41392530215) success. Ветка `docs/p2-readonly-provenance-followup`; актуальный PR/merge/CI сверять по GitHub.
- В `docs/research/p2-public-capture-followup.md` добавлены авторские Jagrullar ECM AE11/B9F0/A6 выдержки с происхождением, ограниченной последовательностью и восемью проверками. Они не показывают CEM startup, normal-mode predicate или MY2009 compatibility. Перепечатка Swedespeed не второй capture; оригинальный permalink не найден. HTML форума недоступен (403), SHA отсутствует и не выдуман.
- Четыре официальные HTML страницы VIDA 321US04 сохранены/хешированы, manifest 63→67. Новое условие оценки эталона: VIDA может использовать прежний readout; требовать свежую запись TX/RX и подтверждение нового чтения. Это методика сравнения, не условие SectorV. Поддержка forum text проверена: 0 transactions означает неподдерживаемый формат/CEM scope, не RX=0.
- Следующий шаг Issue #4 ограничен опубликованным полным P2 сеансом или точным predicate SectorV. Повторный широкий поиск одноимённых проектов/неизменённый VMware scan не заменяет доказательство. Новый VDASH handoff описывает отдельный набор ранее сообщённых результатов; он не доказывает SectorV gate и не меняет пользовательский приоритет публичного исследования. Эмулятор/fixtures не изменены; main/Dvinholm/prerelease не трогать.

## Предыдущий checkpoint: VMware LAB preflight packaging (02.11.2026, PR #36)

- **PR #36** [include J2534 preflight in VMware LAB](https://github.com/vorlocsev/virtualcar/pull/36) merged squash into `development` at **`45df9b053987258521aa8a8778e1663add1d3be6`**. Exact PR HEAD `e6987437417a75539bdcd10c4e0ced21c5bd0648`: [VMware LAB package CI #41380338340](https://github.com/vorlocsev/virtualcar/actions/runs/41380338340) **completed success**, [Windows x86 native DLL CI #41380338485](https://github.com/vorlocsev/virtualcar/actions/runs/41380338485) **completed success**.
- Closed-allowlist VMware ZIP now includes `tools/audit_j2534_connect.py` and `README_P3TOOL_J2534_PREFLIGHT_RU.md`. Package test group #1 explicitly verifies these entries; 8 original group checks including SHA-256 and synthetic/no-CEM-fixture remain. `emulator/README_VMWARE_LAB_RU.md` has exact PowerShell command. This corrects an overlooked packaging hole in PR #35; no behavioral changes to DLL/ECUs in PR #36.
- After extracting **new CI artifact only**, run `py -3 .\\tools\\audit_j2534_connect.py "$env:TEMP\\SectorVVirtualCar.log" --output "$env:USERPROFILE\\Desktop\\j2534-connect-audit.json"` from archive root. Use a new filename if existing. Review JSON before sharing; do not share raw text log. Earlier vmware-lab-2026-11-01 prerelease remains unchanged, without these files and telemetry. No physical-J2534/VMware guest validation.
- **Next:** Issue #4 authentic P2 MY2009 read-only CEM identification/normal-mode evidence; a fresh VMware connect report from verified new DLL may help separate adapter protocol failures from missing ECU fixture. Do not alias undocumented P3Tool vendor modes blindly. `main`, Dvinholm, draft PRs #2/#12/#15 unchanged. Post-merge development CI separately verify.

## Актуальный checkpoint: P3Tool J2534 preflight (02.11.2026, PR #35)

- **PR #35** [P3Tool J2534 read-only preflight](https://github.com/vorlocsev/virtualcar/pull/35) merged squash into `development` at **`96e78ec5873821e1868ccf2802ebc8a32980fa18`**. Exact PR HEAD `fc3f0f64916f85a38a00efc565f8967390ff28ec`; [VMware LAB package CI #41380046765](https://github.com/vorlocsev/virtualcar/actions/runs/41380046765) **completed success**; [Windows x86 emulator / native DLL routes CI #41380046733](https://github.com/vorlocsev/virtualcar/actions/runs/41380046733) **completed success**. Post-merge development CI separately verify.
- Source: user-uploaded `3.zip/P3Tool/p3tool.exe`, verified SHA-256 `908bbbf4a14fbde97404fe8a95bbca8c988e43a3545237daec3842048d235719`. IL static report indicates P3Tool 0.13.7.0 calls `PassThruConnect` equivalents for standard 5/6, provider-specific 0x8004/0x8005/0x10000001, numeric flag `0x20000000` on 125k. This **does not** establish which path a connected client will use, or any P2 OEM compatibility.
- DLL now logs exact `J2534 Connect result protocol/flags/baud/status (BE)` for successful/failed attempts and `J2534 SET_CONFIG channel/parameter/value/applied (BE)` to distinguish `DATA_RATE` actually applied from accepted-but-ignored `LOOP_BACK`, `BIT_SAMPLE_POINT`, `ISO15765_BS`, `ISO15765_STMIN`, `J1962_PINS`. Unknown SetConfig param and value redacted; no new CAN RX, protocol alias, J2534 return-code change, CEM positive response, PIN or EEPROM handling.
- Added `emulator/tools/audit_j2534_connect.py` (allowlisted aggregate JSON, no VIN/frames/PID/path/host) with eight Python groups, eight native C groups, and [Russian VMware instructions](emulator/README_P3TOOL_J2534_PREFLIGHT_RU.md). Published `vmware-lab-2026-11-01` prerelease unchanged and does not contain PR #35. Physical adapter and new VMware guest test **not performed**.
- **Next:** Issue #4 real P2 read-only identification/normal-mode evidence with exact accepted client response, or perform fresh controlled VMware connect preflight with new CI DLL. Do not map P3Tool P3 protocol IDs to P2 ECU identity without evidence. `main`, Dvinholm and draft PRs #2/#12/#15 unchanged. No release published for this PR.

## Актуальный checkpoint: Volvo P2 Informer CAN observer-only (02.11.2026, PR #34)

- **PR #34** [source-bound Volvo P2 Informer probes](https://github.com/vorlocsev/virtualcar/pull/34) merged squash into `development` at **`251f6b2349266a023dac5222311019e17da3f9e9`**. Exact PR HEAD **`f30e277c8eb85cd5c1e3555b486e71b1f35bf435`**: [Emulator Windows x86, native route regressions #41375922257](https://github.com/vorlocsev/virtualcar/actions/runs/41375922257) **completed success**, [VMware LAB package CI #41375922284](https://github.com/vorlocsev/virtualcar/actions/runs/41375922284) **completed success**. First red builds were fixed before merge (different TCM padding and expected legacy P3 0x726 F190 attribution).
- Public source reviewed: [drpioneer/Volvo-P2-informer `main@9cd3a6f603915e074ac28c73eccec6b7473e8297`](https://github.com/drpioneer/Volvo-P2-informer/tree/9cd3a6f603915e074ac28c73eccec6b7473e8297), source says XC90 **2.5T MY2011**, *not* OEM B8444S MY2009 proof. Independent observer recognizes exact read-only TX shape `03 22 F1 90 00 00 00 00` on P2 LS 125k / CAN 0x000FFFFE, and five module-family request selector groups (ECM/TCM/DEM HS 500k; REM/CCM LS 125k). Six allowlisted `P2INF_*` tokens supplement existing 20 D2/P3 labels in backend JSONL, with strict baud/protocol, raw payload length/selector guards and Python spoof rejection. **No CAN RX changes, B9FB fixtures, CEM positive replies, ECU route claims, or real vehicle identity**. Details `docs/research/p2-informer-observer.md`.
- Eight native C test groups and eight Python tests ensure metadata-only classification, wrong transport/baud, 11-bit/P3 noninterference, no invented RX, privacy, legacy D2 probe coverage. Native routes verified in PR CI. No VMware guest test performed for PR #34; published `vmware-lab-2026-11-01` prerelease remains unchanged and does **not** contain PR #34 changes. No new release published.
- **Issue #4 remains OPEN.** Higher-priority unresolved need: proven complete P2 read-only CEM MY2009 identification/normal-mode preparation, exact accepted response predicate or suitable complete real trace. Do not turn P2 Informer 2.5T request observations into positive A3/A6/B9F0/B9FB data. `main`, Dvinholm and draft PRs #2/#12/#15 unchanged. Post-merge development HEAD CI check separately after this docs update.

## Актуальный checkpoint: опубликованный VIDA prefix и offline parser (02.11.2026)

- База этапа — development `b12a4d84b07a9ff6051fa649478fed2da60198c7`, PR #32 merged; CI [Emulator/native x86 #41361756276](https://github.com/vorlocsev/virtualcar/actions/runs/41361756276) и [cross-build #41361756233](https://github.com/vorlocsev/virtualcar/actions/runs/41361756233) success. Ветка нового этапа: `fix/audit-vida-j2534-format`; её PR/merge SHA и CI сверять по GitHub.
- В боковой FUNK3_S80 найден подлинный опубликованный VIDA2013A J2534 log (610158 bytes, SHA в manifest). Соседний файл подписан S80 2007, но автомобиль каждого файла независимо не установлен; не назначать ему S60 MY2009 из README. Prefix 1–2040 содержит только 181 UDS 22 и 10 TesterPresent; с 2041 начинается RoutineControl, эта часть не используется как обычное обнаружение. CEM F114: 0x726→0x72E, ISO15765/500k/11-bit, 258 UDS bytes/384ms; это собранное сообщение, не один CAN frame и не совместимая MY2009 fixture. Предикат SectorV normal-mode всё ещё неизвестен.
- Исправлен доказанный пробел offline text audit: раньше VIDA comma-byte/call/thread format давал 0 transactions. Теперь выбранный prefix даёт 14 CEM reads: delivered=11, negative_response=3, parse_errors=0. Восемь synthetic групп; 140 Python tests OK, 1 expected host native-DLL skip. Точный MY2005 PR30 suffix 91852 bytes: все 37 transactions/counts/parse_errors равны базе. DLL/профили/RX не меняются; нового VMware run нет.
- В manifest 63 уникальных public files. Полностью проверены 17 P2 CSV (1338607 rows; выбранных diagnostic IDs=0 до фильтра) и восемь .trc неизвестной Volvo 2013 (1262578 rows; IDs=0). Timestamps/baud/Dir для неподтверждённых форматов не выдумывались. Подробности — `docs/research/p2-vida-published-prefix.md`.
- Следующая задача Issue #4: достоверный полный P2 read-only scan с provenance/route и наблюдаемым переходом клиента через normal-mode preparation либо опубликованное точное условие клиента. Не добавлять предполагаемые E3/E6/258-byte UDS replies и не повторять прежний VMware scan без нового evidence. Main/Dvinholm/prerelease не менять; raw/VIN остаются вне Git.

## Предыдущий checkpoint: дополнительный поиск публичных P2 captures (02.11.2026)

- Кодовая база — development `625b09a366a6ae2a5d39fb854f4e69f5b9384008`, PR #31 merged. CI [Emulator/native x86 #41359332645](https://github.com/vorlocsev/virtualcar/actions/runs/41359332645) и [cross-build #41359332653](https://github.com/vorlocsev/virtualcar/actions/runs/41359332653) success. Этот следующий этап меняет только research docs и handoff; актуальный docs HEAD/CI сверять по GitHub.
- По уточнению пользователя продолжать именно поиск опубликованных данных. Исходник/успешный сеанс у пользователя повторно не запрашивать без новой причины. Проверены новые public candidates, добавлены 20 SHA-256 (36 всего); см. `docs/research/p2-public-capture-followup.md`. Блог XC90 MY2009 содержит адреса/пассивные выдержки, не полный scan. CANLogger big.logdata: 41 761 корректный SLCAN-подобный record, 27 IDs, проверяемых D2/P3 diagnostic IDs=0; baud/direction/timestamps не угаданы. Нового подтверждённого CEM response нет.
- В уже существующем приватном main client log PR30 подтверждено: один VIN read target50 получил matched=13/observed=13/ignored=0. Затем Hardware-session target50/500k и target40/125k: observed=0, elapsed=5000/5001 ms, Hardware TimeoutException. A3 TX 7/8 согласуются по порядку/маршрутам; A3 TX13 повторяет operands, но его точный accepted-response predicate не известен. Не считать ранний Hardware exception доказательством причины отдельного UI normal-mode warning. Client wall clock и backend QPC не склеивались; PIN-операции не используются как эталон.
- Следующая задача Issue #4: подходящий опубликованный успешный read-only P2 scan с route/connect metadata и наблюдаемым переходом клиента через Hardware/normal-mode preparation. Кодовые изменения допустимы при конкретном дефекте либо подтверждённой совместимой записи; не добавлять предполагаемый E3/E6 и не повторять прежний VMware scan без нового evidence. Raw files/VIN/приватные operands остаются вне Git. Main/Dvinholm/prerelease не меняются.

## Предыдущий checkpoint: offline A6/E6 validator (02.11.2026)

- База этого этапа — development `c993844cafb24fa73d07a9da5fd3dbd036d08f46`; итоговые PR/merge SHA и CI сверять по GitHub. Ветка этапа: `fix/audit-d2-a6-single-frame`. Новый код меняет только Python evidence audit; исходник DLL, ECU responses и профили остаются прежними.
- Полный single-frame E6 теперь сопоставляется с формой `CD target A6 identifier 01`: известный CEM CAN ID candidate, target/identifier echo, declared length, data-record byte и предоставленный channel/protocol/baud context. В JSON не выводятся identifier/value. Значения ignition/identity/normal-mode не интерпретируются; delivered означает только transport. Другие requests, E3 и multipart/negative A6 не становятся delivered. См. ограничения в `emulator/README_DEV31_EVIDENCE_RU.md`.
- Восемь новых synthetic test groups. Локально 132 Python tests OK, один expected host-C integration skip; C suite и native x86 проверяются CI. Старая база не проходила новую регрессию. Для нормализованной опубликованной S80 MY2002 request/reply выдержки теперь RX=1/delivered; неизвестные channel/protocol/baud/window не заполняются.
- Точный суффикс прежнего MY2005 VMware run PR #30 повторно разобран offline: все 37 распознанных transactions/counters/parse_errors совпали до/после; raw source и старый prefix не изменены. Два A6 всё ещё без RX; новый SectorV/VMware scan не выполнялся.
- Следующая задача Issue #4 — доказать конкретное условие SectorV normal-mode preparation по подлинному успешному read-only CEM сеансу либо исходному описанию условия клиента. В исследованных публикациях нет сопоставимой непрерывной записи P2; положительные CEM responses по предположению не добавлять. MY2005 local tests разрешены пользователем, но не доказывают MY2009 compatibility. Не повторять неизменённый VMware scan как замену отсутствующему evidence.

## Предыдущий checkpoint: P2 research и PR #29/#30 (02.11.2026)

- **Кодовая база development после PR #30:** `c44af9972bad1b469f8d3387198ee99e9fa6f555`. Текущий HEAD и post-merge Actions сверять по GitHub; обновление этого handoff меняет только документацию.
- **PR #29** объединён squash: `ccc475167eedf857106a114d6f287404e9a163d1`. Текстовый аудитор распознаёт полные prefixed D2 A3/A6, не публикуя параметры; восемь новых групп. **PR #30** объединён squash: `c44af9972bad1b469f8d3387198ee99e9fa6f555`. Общая проверка формы в DLL принимает CA–CF/known CEM target/полную declared length; malformed frames не получают эту метку. Только `unimplemented_probe/no_response`, без новых ECU RX.
- CI объединённого HEAD PR #30 `55510cb6ffc11ded9bda66c3075aebdd6d7bc8b0`: [Emulator x86 + native-routes #41357702051](https://github.com/vorlocsev/virtualcar/actions/runs/41357702051) и [VMware LAB #41357701994](https://github.com/vorlocsev/virtualcar/actions/runs/41357701994) success. Локально combined Python suite: 124 tests OK, 1 expected skip; C MSVC x86 host suite выполнен отдельно и прошёл. C source blob `ec93441396f80998e4ecb322044f49c1477b422d` совпадает с испытанным в VMware PR #30 source.
- **Отдельный MY2005 read-only run PR #30 выполнен:** SectorV 1.1.0/VMware20,1; загруженная DLL из CI #41329015042 подтверждена по пути модуля и SHA-256. Два сохранённых log offsets и SHA исходных префиксов выделяют ровно этот run: 46 TX из одного процесса / 8 внутренних connection sessions, invalid=0; delivered=3, no_fixture=23, unsupported=20, conflicts=0. Это один UI run, не восемь независимых тестов.
- Оба CD/50/A6 теперь CEM/unimplemented/no-RX, текст независимо фиксирует read timeout. Первый A6 запрашивает 1A04 перед сообщением о неопределённом положении зажигания; после закрытия сообщения следует A3. Второй A6 в конце запрашивает D0D1, назначение не установлено. B9FB50: три доставки по 13 кадров, dequeued=39; B9FB40: пять no_fixture. UI: 12,5 V, 24 модуля, на связи 0; «CEM не подтвердил подготовку обычного режима». ECU identity и MY2009 compatibility не подтверждены; DTC=0 без связи не означает отсутствие ошибок. Подробности: `emulator/README_DEV31_EVIDENCE_RU.md`.
- **PR #28** research объединён: `fa3c12982e6f219de07e52648738f59f8125692b`. Отчёт `docs/research/p2-readonly-discovery-evidence.md` содержит восемь проверок, source table, ограниченную chronology и 16 проверенных SHA-256. S80 MY2002 VIDA даёт отдельные read-only примеры; полного подходящего непрерывного P2 scan среди проверенных источников нет. Jan Jansen — V50/P1 с предположением об E6; ссылающийся на него код не является независимым capture. Нельзя добавлять по этим примерам MY2009 CEM responses.
- **Следующая точная задача Issue #4:** offline A6/E6 RX validator пока не поддерживается. Нормализованная опубликованная S80 A6/1A04 request/reply выдержка распознаёт TX, но даёт rx_frames=0/off_route_rx=1/unverified; воспроизводимый пример есть в research report. Допустим отдельный связанный PR с 6–8 группами проверки target/identifier/length/route и CI, без E3/Security Access и без изменений ответа DLL. Этот пробел аудитора не объясняет настоящий RX=0 VMware-сеанса. Доказательство normal-mode gate всё ещё требует успешного сравнимого сеанса CEM или точного условия клиента.
- Пользователь разрешил локальные read-only тесты с MY2005. Это не разрешение на programming/reset/security и не MY2009 evidence. После run SectorV закрыт, прежняя J2534 registration восстановлена. Приватные профили/VIN/raw logs остаются вне Git. Main, Dvinholm и опубликованный VMware prerelease не менялись.

## Архив checkpoint: PR #25 и MY2005 read-only run (01.11.2026)

- **PR #25** `fix/p3-f114-missing-cem-evidence` объединён squash в `development`: merge SHA `c7660645e8f1a666201c2fb27f0c9fcc6148fa40`. Exact-HEAD PR checks и post-merge checks успешны: Emulator Windows x86 #41323997651/#41324993934 (включая настоящий x86 DLL verifier), VMware package #41323997656, cross-build #41324993954. PR workflow publication step **skipped**; опубликованный VMware prerelease не менялся.
- При точном ISO15765 запросе `22 F1 14` к P3 IDs `0x726` или `0x18DA50F1`, если текущий профиль не содержит соответствующего ECU, backend фиксирует маршрут CEM и `unimplemented_probe/no_response`; RX не генерируется. Настроенный ECU и произвольные/искажённые запросы сохраняют прежнюю обработку. Это profile-specific evidence, не вывод о MY2009 CEM.
- Сверена обезличенная MY2005 SectorV 1.1.0 сессия, выполненная до PR #25: 11 запросов / 7 сессий / invalid=0; B9FB target 0x40: 5 `no_fixture`, target 0x50: 2 `delivered`; A3: 2 `unimplemented_probe`; P3 F114: 2 прежних `unhandled_request`; конфликтов=0, RX dequeued=26. Клиент не подтвердил normal mode, reachable ECU=0, ECU identity не подтверждена. `delivered` означает только J2534 transport.
- Локально подготовлен отдельный артефакт из CI run #41324993934, commit `c766064`, SHA-256 `f24fca7144bf8415b16e3ed2ccb9a86cabf539b72622b7dc8a0ae12322c6c2aa`. Тестовый MY2005 профиль остаётся только локально: 13 кадров сохранены для target 0x50 B9FB, target 0x40 пуст, остальные P2 response fixtures выключены, passive traces/CAN выключены, telemetry включена. Приватный профиль, VIN, кадры и JSONL в GitHub не копировать.
- **Post-PR #25 VMware run завершён:** SectorV 1.1.0 подключился к выделенной виртуальной J2534 регистрации с локальным MY2005 профилем (12,5 V), выполнил полный read-only scan 24 блоков и отключён. Клиент сообщил `CEM did not confirm normal-mode preparation`; доступных ECU=0, DTC=0, identity не подтверждена. Программирование и reset не запускались.
- Обезличенный backend suffix после сохранённого префикса: 46 запросов / 8 сессий / invalid=0; `delivered`=3, `no_fixture`=23, `unsupported`=20, `unverified`=0. `delivered` — только J2534 RX delivery. B9FB target `0x40`: 5 `no_fixture`; target `0x50`: 3 транспортные доставки. Все шесть прежних route-only конфликтов не повторились в этой сессии; это не переписывает историческое evidence.
- P3 F114: отдельный 11-bit CAN запрос к `0x726` остался `UNHANDLED`; exact ISO15765 запросы к `0x726` и `0x18DA50F1` получили маршрут `CEM` с `unimplemented_probe/no_response`, без RX. Это подтверждает telemetry-классификацию PR #25 на MY2005 профиле, не поведение MY2009 CEM.
- Приватный профиль, VIN, raw J2534/backend logs и payload не включены в GitHub. После теста SectorV закрыт, J2534 registration возвращена к предыдущей PR22 DLL; `main`, Dvinholm и опубликованный VMware prerelease не менялись.
- **Следующий блокер Issue #4:** для улучшения B9FB/MY2009 discovery нужен подлинный совместимый MY2009 CEM capture/fixture с provenance и маршрутом. Не переносить MY2005 target `0x50` fixture на `0x40`, не добавлять synthetic positive replies и не заявлять MY2009 identity по этому запуску. Подтверждённое изменение PR #25 остаётся в `development`; следующий кодовый этап должен опираться на новый аутентичный capture или конкретный дефект в исходниках, а не на недостающие ответы.

## 1. Задача и границы

- Проект: **Virtual Car**, автономный Windows **x86** эмулятор Volvo P2 через J2534 PassThru DLL + Go-приложение управления. Цель: обнаружение виртуального **XC90 V8 MY2009** и чтение VIN/идентификаций ECU через диагностический клиент в VMware.
- В рамках текущего этапа только **read-only лабораторная диагностика**. Никаких программирований ECU, изменения конфигураций, Security Access, иммобилайзера или поддельных положительных ответов.
- **Dvinholm** — другой проект и другой репозиторий, его не трогать. В Virtual Car пользовательские логи могут содержать имена SectorV/VDASH: это имена тестовых клиентов, не названия Dvinholm.

## 2. Где исходники и как читать историю

| Путь в development | Содержимое |
| --- | --- |
| `emulator/src/virtualcar.c` | Основной пользовательский исходник настоящей J2534 DLL **v0.3.6.6**, обновлённый в dev28 |
| `emulator/src/p2core/` | Наблюдатель CEM/D2, маршрутизатор HS/LS и мост с J2534 |
| `emulator/control/` | Go Control.exe; `p2audit/` предупреждает об отсутствующих P3 CEM маршрутах |
| `emulator/tools/import_p2_trace.py` | Строго ограниченный импорт D2 B9F0/B9FB/B9FC, с проверкой последовательности |
| `emulator/tools/analyze_can_csv.py` | dev30: read-only статистика SavvyCAN CSV, **без** подготовки CAN-replay |
| `emulator/tests/` | C/J2534 и Python протокольные регрессии |
| `proxy/`, `cmd/oneclick/` | **Отдельный J2534 прокси/трассировщик dev26**, не заменяет эмулятор |
| `docs/ROADMAP.md`, `docs/research/` | План и результаты исследования ранних P2 CAN, не подтверждённые для MY2009 |
| `AGENTS.md`, `docs/CHAT_GITHUB_WORKFLOW_RU.md` | Требования к PR, проверкам, безопасности и кратким отчётам |

Источником истины является код GitHub `development`, а не прежние ZIP-архивы dev23–dev30 и не рассказ предыдущего чата.

## Текущая точка: импорт D2 и проверенный VMware сеанс (01.11.2026)

- Исправление импортера: новый output без перезаписи исходного log/profile, существующих файлов и их aliases; точное однокадровое F9/opcode либо 7F B9 эхо согласовано с DLL. Восемь новых групп, локально 14 тестов. Статус задачного PR/CI проверять по GitHub. См. `emulator/README_IMPORT_SAFETY_RU.md`.
- Среда локальных native тестов подтверждена как VMware (VMware20,1). Native x86 регрессия прошла восемь групп; опубликованная старая DLL отклоняется negative control.
- Read-only SectorV 1.1.0 проверен через новую виртуальную регистрацию: подключение/12,5 В подтверждены, VIN не получен. Только эта попытка: 13 запросов / 6 сеансов / invalid=0, B9FB no_fixture=10, P3 F114 unsupported=2, wrong-baud=1, RX=0, conflicts=0. Сеанс отключён; старый префикс backend сохранён.
- Локально найдена частная MY2005 fixture target 50 B9FB, 13 кадров. Отдельный native READ128 replay сравнил все кадры побайтно: queued/dequeued=13, drops/conflicts=0, delivered — только транспорт. Original private INI и основной backend не изменены. Содержимое фикстуры/VIN/логи в GitHub не переносить. Совместимость с MY2009 не подтверждена; активный профиль не переключать автоматически.
- Следующая задача Issue #4: получить подлинную совместимую CEM запись целевого MY2009 с происхождением/маршрутом. Не повторять synthetic упаковку или тесты как замену отсутствующим данным, не придумывать положительные ответы. Main, Dvinholm и опубликованный prerelease не менять.

## Следующий этап: native x86 route regression (01.11.2026)

- Новый локальный backend audit: 13 запросов / 6 сеансов / invalid=0, B9FB no_fixture=10, P3 F114 unsupported=2, strict wrong-baud unsupported=1; conflicts=0, unattributed=0. Старые шесть silent ECM запросов не наблюдались: это не полная VMware-проверка исправления PR #22.
- Добавлены `emulator/tools/verify_native_routes.ps1` и `verify_native_routes.py`: восемь групп на настоящей x86 DLL через LoadLibrary/stdcall, отдельный synthetic профиль и отдельные журналы, без регистрации адаптера. Native Windows CI запускается после cross-build; статус финального PR/HEAD проверять в GitHub.
- Локально DLL PR #22 проходит; опубликованная исходная DLL отклоняется по старому route conflict в negative control. В отчёте identity/client acceptance остаются false. Подробности и команды: `emulator/README_NATIVE_ROUTE_CHECK_RU.md`.
- Следующая практическая задача Issue #4: выполнить обе команды native regression в гостевой Windows, затем отдельно проверить диагностический клиент. Для продвижения по B9FB всё ещё нужны подлинные совместимые фикстуры; не добавлять положительные CEM ответы.

## VMware backend audit: PR #22 (01.11.2026)

- Проверенный код: [PR #22](https://github.com/vorlocsev/virtualcar/pull/22), code HEAD `d4cd882263565fd7fb40e3e89a9d6e20acc7f3c9`, база `ad333635d37fffea651733745af5f1ce3f35d2ba`. Состояние интеграции и финальный SHA документационного обновления сверять по GitHub. На code HEAD [Emulator CI #41309278841](https://github.com/vorlocsev/virtualcar/actions/runs/41309278841) и [VMware packager #41309278839](https://github.com/vorlocsev/virtualcar/actions/runs/41309278839) **success**; публикация prerelease **skipped**. CI финального HEAD проверять отдельно.
- Исправлены противоречивые маршруты физического silent completion (ECM/CEM → ECU_OTHER), дополнительного D2_Node и functional fanout. Ответы на шине не добавлены. Аудитор выводит `observed_routes` и `evidence_conflicts`; исторические конфликты остаются unverified. Восемь групп C/Python регрессий, в том числе настоящая цепочка C-emitter → Python-auditor; локально полный MSVC x86 host suite и 44 Python-проверки.
- Исходный приватный backend JSONL найден локально и повторно проанализирован: **38 запросов / 14 сеансов / invalid=0**, no_fixture=20, unsupported=6, unverified=12. Все шесть inconsistent_route_or_channel — **только route**, ECM/ECU_OTHER. Для каждого подтверждена цепочка TX UNKNOWN → route_selected ECM → terminal ECU_OTHER/no_response; channel/protocol/baud не расходятся. Сервис этих запросов не маркирован. Шесть explicit_no_response также остаются без известного сервиса; это не доказательство A3/A6/B9FB.
- 20 B9FB без фикстуры соответствуют пустым CEM D2 fixtures опубликованного synthetic профиля; ещё два target 50 на 250 kbit/s отклонены strict routing. Четыре P3 0x726/F114 остаются unsupported при профиле только с ECM. Никакие CEM ответы/узлы автоматически не добавлять.
- **Следующая задача: Issue #4**, новый read-only VMware сеанс с CI сборкой PR #22: проверить отсутствие новых конфликтов меток. Для B9FB отдельно нужны подлинные совместимые fixtures; отсутствие конфликта не означает успешную идентификацию. Полный пользовательский журнал, профиль, payload и исходные request/session ID в GitHub не публиковать. Новый обезличенный аудит остаётся локально в workspace `.cache/backend-audit-route-details.json`.
- Main, Dvinholm, draft PR #2/#12/#15 и опубликованный VMware prerelease/tag/assets не менять. Новая DLL в VMware и физический J2534 после исправления **не проверены**.

## VMware LAB prerelease 2026-11-01 (PR #21, verified)

- **PR #21** `feature/vmware-readonly-release-package → development` merged squash at `f2eb76e8f19731239d93dec229d2eed487c5ca27`. Exact PR head `f59d7ce5f9c8ec3c7a2c4e4648f997a52e2dc2bf`, [Emulator CI #41305708695](https://github.com/vorlocsev/virtualcar/actions/runs/41305708695) **success**, [VMware packager CI #41305708832](https://github.com/vorlocsev/virtualcar/actions/runs/41305708832) **success**.
- Explicit, separate `vmware-release/2026-11-01` branch at `f2eb76e` triggered [read-only VMware release CI #41305885489](https://github.com/vorlocsev/virtualcar/actions/runs/41305885489), **success** with C/J2534, Python, Go/vet, Windows PE32 DLL/GUI, ZIP+SHA256 validation, and GitHub prerelease publication. **Published release:** https://github.com/vorlocsev/virtualcar/releases/tag/vmware-lab-2026-11-01 (prerelease, private repo), tag `vmware-lab-2026-11-01`, asset `VirtualCar-VMware-LAB-vmware-lab-2026.11.01-Windows-x86.zip`. Verified asset SHA256 `30ac68fa60bd6dcf1f548e1d403327c276b91137184fb90ba21231f541f9aef5`.
- VMware ZIP includes Win32 J2534 DLL + Control GUI, install/uninstall PowerShell scripts, strict **synthetic P2 read-only** profile `ECUCount=1` with `BackendTelemetryEnabled=1`, zero active CEM D2 B9 fixtures, known A3/A6 missing-implementation status, metadata analyzer and Russian instructions. It has build information and SHA256 manifests; approved allowlist prevents private donor INIs/raw logs/ECU dumps. Eight Python packager checks added. No new positive ECU answers; no Stable/main changes.
- **Validation boundary:** VM guest use with SectorV/VDASH, client acceptance of VIN, and real physical J2534 still NOT VERIFIED; Issue #4 remains OPEN. Next: run read-only discovery with this **exact prerelease** and analyze only redacted `backend-audit.json`. Never assume delivered RX proves ECU identity.
- Release was explicitly requested by user. Do not automatically republish / overwrite the tag. Draft PR #2 (`development → main`), #12 and #15 remain separate and unmerged.

## Явная маршрутизация CEM A3/A6 без фиктивных ответов (01.11.2026, PR #20)

- **PR #20** `fix/issue4-a3-a6-silent-cem-routing → development` объединён squash-коммитом `fc2eb08ffae12bc6e127d31dc23aaeeedafb2f30`. PR HEAD `ac5bbd64f7f4412174ad1909c66ccccbd43e129d`, [Emulator Windows x86 CI #41304616832](https://github.com/vorlocsev/virtualcar/actions/runs/41304616832) **success** (J2534/C, PE32 DLL/exports, Python, Go/vet, Windows x86 GUI и артефакт).
- D2 CAN `0x000FFFFE` для target `0x40/0x50`, A3/A6 и префиксов `CB/CF/CA` теперь проходит известный маршрут `CEM` и выдаёт мета-событие `unimplemented_probe/no_response` при **полностью прежнем отсутствии ответа на шине**. Это неподдерживаемый в Virtual Car ответ, не утверждение о возможностях реального OEM CEM. Нет синтетических ответов E3/E6, зажигания, VIN и идентификационных данных. Неизвестные CAN ID остаются `UNHANDLED`; B9F0/B9FB/B9FC и их записанные фикстуры не изменены.
- Backend auditor отличает `unsupported/unimplemented_probe` от `no_fixture/missing_profile` и неизвестных `unhandled_request`. Девять C host-маршрутных сценариев, семь Python регрессий #30–#36, включая отсутствие RX, разделение B9, конфликт маршрутов, противоречивые терминалы и неразглашение частных полей.
- **Issue #4 остаётся OPEN** до настоящей read-only сессии SectorV/VDASH в VMware с текущей DLL и анализа обезличенного `backend-audit.json`. Нет положительных OEM A3/A6/B9F0 для XC90 V8 MY2009, верификации принятия VIN и физического J2534. Post-merge CI на новом SHA `development` проверять отдельно. Draft PR #12/#15 и #2 не объединять; `main`, релизы Virtual Car и Dvinholm не трогать.

## Матрица CEM probes и точное P3 DID (01.11.2026, PR #19)

- **PR #19** `feature/issue4-cem-probe-coverage → development` объединён squash-коммитом `ca16ca04cc74ed5bacc0a296003bcd6b09d69248`. PR HEAD `3bc6dcc788b01a47412514b0e9426368854be5cd`, [Windows x86 emulator CI #41304043679](https://github.com/vorlocsev/virtualcar/actions/runs/41304043679) **success** (J2534/C regressions, DLL x86/exports, Python fixtures/audit, Go/vet, x86 GUI, artifact).
- `emulator/tools/audit_backend_evidence.py` теперь формирует `coverage` для **всех известных 20 форм** D2 CEM 40/50 A3/A6/B9F0/B9FB/B9FC и P3 0x726/0x18DA50F1 F114/F1B0/F1A3/F106/F190: `observed_requests`, `status_counts`, `attributed_requests`, `unattributed_requests`. **Не наблюдалось** не значит `unsupported`, `no_fixture` или таймаут. Конфликтные/запоздалые метки не приписываются известному probe. Восемь Python регрессий #22–#29.
- `emulator/src/virtualcar.c` больше не помечает составной J2534 ISO15765 `22 F1xx F1yy` как одиночный `22F1xx`: для классификации требуется ровно три UDS-байта. Существующий raw CAN single-frame без изменений. Новые C host-проверки составного, избыточного и короткого ISO15765 payload. **Сами J2534 ответы и CEM фикстуры не изменены**.
- **Главный блокер Issue #4:** нужен реальный read-only `backend-audit.json` из VMware с актуальной DLL и клиентом. Положительные CEM A3/A6/B9F0 XC90 V8 MY2009, VIN принятие клиентом, физический J2534 пока не доказаны. Без настоящего capture не добавлять synthetic positive. Post-merge CI на новом `development` SHA проверить отдельно. Draft PR #12/#15 и gate #2 не сливать; `main` и Virtual Car releases не трогать.

## Проверка целостности backend evidence (01.11.2026, PR #18)

- **PR #18** `fix/issue4-backend-event-integrity → development` объединён squash-коммитом `5307106c2a78d342c4206cd673fa47668ffe7777`. Аудитор `emulator/tools/audit_backend_evidence.py` теперь отмечает `unverified` при `rx_dequeued` без предшествующего `rx_queued`, при невручённых кадрах на момент `responded`, повторном/переставленном TX, запоздалой классификации запроса, нарушении порядка QPC ticks или частоты, либо `no_response` вместе с RX. `rx_dropped` может относиться к неудачной постановке в очередь, поэтому не трактуется как dequeue. Доработаны 8 регрессий (#14–#21), текущие старые тесты адаптированы к достоверной очереди. Исходные J2534 ответы не менялись.
- PR HEAD `e28cc511aebcb4978853d07b6b0c66f380cf914d`, [Emulator Windows x86 CI #41303547651](https://github.com/vorlocsev/virtualcar/actions/runs/41303547651) **success**: DLL, x86 exports, Python, Go/vet, GUI и артефакт. Post-merge CI проверять отдельно на актуальном development SHA.
- **Блокер Issue #4 прежний:** нет реального сеанса read-only VMware/диагностического клиента с текущей DLL; никакого доказанного положительного CEM A3/A6/B9F0 или ECU identification XC90 MY2009. Следующий этап: изучить только реальный обезличенный `backend-audit.json`, снять наблюдаемые пробелы по сервисам/каналам/ответам. Не публиковать оригинальный VIN/дампы. PR #12/#15 и gate #2 остаются draft, без автоматического merge; `main`/релизы не трогать.

## Текущее состояние (01.11.2026, Issue #4: probe-aware backend evidence)

- **PR #17** `feature/issue4-allowlisted-probe-evidence → development` **объединён** squash-коммитом `ea80ea52834cf1f70a9c9853e3cade7c9a79fa42`. При включённом `BackendTelemetryEnabled=1` реальный J2534 TX может создать `probe_classified` для закрытого списка известных форм запросов D2 CEM 40/50 A3/A6/B9F0/B9FB/B9FC и P3 0x726 / 0x18DA50F1 F114/F1B0/F1A3/F106/F190. Метка связывается с дальнейшим RX по внутреннему `request_id`, но не выдаёт VIN, CAN payload и неизвестные CAN ID.
- **PR #17 CI на точном HEAD** `ed77ffc063645e45260f175f9f39f05180450896`: [Windows x86 emulator run 41300194753](https://github.com/vorlocsev/virtualcar/actions/runs/41300194753) **success**: C/J2534, READ128/B9FB, сборка DLL + экспортов, Python-аудит, Go/vet, Windows x86 GUI и артефакт. Первый запуск CI `c2d765f` не прошёл из-за устаревшего ожидания счётчика A3 в тесте, исправлен и полностью перепроверен. Development post-merge CI ещё необходимо проверять на новом SHA.
- **PR #16** (backend JSONL audit) ранее объединён как `6d0048818e66408ebec001ed16fbda44747c181c`, а **PR #13** (ISO-TP FC/backpressure+STmin) как `3503234aaf3da6945007750a2f016a2981c5cdfe`. На `development` до PR #17 обе CI-сборки были успешны на `23b8d36`.
- Новый `emulator/tools/audit_backend_evidence.py` по известной метке может вывести `service`, `target`, `can_id` и 11/29-bit (только для заранее перечисленных ID). В старом JSONL или для неизвестного запроса атрибуция остаётся `null/unknown`. `delivered` означает выдачу RX через J2534, не полный D2/ISO-TP и не принятие ECU. Файл: `%LOCALAPPDATA%\VirtualCar\dev47-backend.jsonl`.
- Frame-level локальная проверка: `emulator/tools/audit_j2534_discovery.py` с приватным исходным J2534-логом. Исходный текстовый лог может содержать VIN, поэтому в репозиторий и CI не добавлять. Обезличенный backend JSONL и его отчёт без payload можно использовать для лабораторного анализа.
- **Следующий приоритет Issue #4**: собрать реальную read-only сессию новой DLL в VMware с SectorV/VDASH и сопоставить отдельные TX A3/A6/B9F0/B9FB, P3 0x726/0x18DA50F1, CH, baud, наличие фикстуры, RX и сбросы. Приоритет: доказательство принятия VIN / выявление отсутствующего OEM ответа; выдуманных CEM positive replies не добавлять. Нет доказательств полноценного XC90 V8 MY2009 ECU discovery или испытаний физического J2534.
- **PR #12** (functional OBD VIN / physical FC) и **PR #15** (proxy) остаются отдельными draft. **PR #2** `development → main` остаётся draft gate. Ни один из этих PR не сливать без своих проверок; Virtual Car releases не публиковать без явной готовности.

## 3. Проверенный снимок состояния (31.10.2026)

- Последний проверенный `development` **перед dev33**: `96220cc57d5f12c1431bce39eefe2d3f380aff6f` (dev32 PR #7). Проверять фактический HEAD после слияния dev33.
- `main` при проверке начала dev33: `c20f1870d125ebca8683c97a11b507910824fb0f` (изменён отдельно от работы dev33). **Не объединять development в main без ручных end-to-end проверок**.
- **PR #2** `development → main`: https://github.com/vorlocsev/virtualcar/pull/2 — **draft/open**, это ворота проверки в VMware; не закрывать и не сливать автоматически.
- **PR #3** завершён: регламент Chat+GitHub, path-filtered CI, изменения документации.
- **PR #6** завершён в `development`: dev31 безопасный J2534 CEM evidence audit. **PR #7** завершён: dev32 P3 ISO-TP/Flow Control/negative-response. **PR #10**: dev33 UDS NRC78 responsePending и запрет считать заголовок `62 F1xx` без данных полным ответом; статус сверять по GitHub.
- Для dev32 HEAD `96220cc` оба CI завершились **success**: [Emulator x86](https://github.com/vorlocsev/virtualcar/actions/runs/41189336332), [Proxy/OneClick](https://github.com/vorlocsev/virtualcar/actions/runs/41189336296). Результат dev33 проверять только на SHA PR #10.
- Новые PR должны открываться **из отдельной ветки в `development`**, максимум один фокус на PR. В CI есть отдельные workflows для эмулятора и прокси; успешная сборка не доказывает работу в VMware.
- Dev30: проверка SavvyCAN CSV; офлайн выполнены **26 Python-тестов**, но при новом изменении запускать актуальные CI вместо повторения устаревшей цифры.

## 4. Подтверждено vs неизвестно

**Подтверждено по исходникам/тестам:**
- `PassThruReadMsgs` принимает `NumMsgs=128` при внутренней очереди 64 (регрессионный тест; не равняется проверке в конкретной Windows сессии).
- В лабораторном D2 B9FB есть механизм воспроизведения **13 кадров** из настроенного профиля. Предыдущий приватный донорский лог подтверждал отправку 13 кадров на запрос; файл не входит в GitHub.
- Для донорского P2 2005 INI `ECUCount=1` и ECM `0x7E0` не заданы диагностические P3 CEM запросы `0x726` и `0x18DA50F1`. `p2audit` предупреждает об этом.
- B9FC, F106 и дополнительные ECU-фикстуры поддерживаются **условно при настройке**, а не гарантируют идентификацию XC90 2009.
- Для MY2009 HS-CAN задано **500 kbit/s**, LS-CAN **125 kbit/s** в нашем лабораторном профиле. Сторонние трассы 2002/2003 с HS 250 kbit/s нельзя считать эталоном.

**Не подтверждено:**
- Настоящие **положительные** ответы CEM **A3**, **A6**, **B9F0** на целевом XC90 V8 MY2009; `E3 02` — гипотетический признак, не подтверждённая фикстура.
- Завершённое обнаружение XC90 V8 MY2009 в SectorV/VDASH при использовании **текущей** DLL.
- Конкретная успешная проверка READ128 (`NumMsgs=128`) и полной P3 CEM идентификации в VMware.
- Реальные испытания с физическим J2534.
- Привязка LS-CAN-идентификаторов ранних VolvoCan/V70/S60 и их bit-offset к XC90 MY2009.

**Безопасность и секреты:** донорский `private-P2-donor-2005/xc90v8-2005-donor.ini` и пользовательские дампы/полные логи имеют личные VIN и **не должны попадать в Git, GitHub Actions artifacts, публичные отчёты или контекст новых PR**. Для функциональных испытаний они остаются только в VMware/на стороне пользователя. В GitHub только синтетические и обезличенные примеры.

## 5. Что делать в новом чате первым

**Активный блокер: [Issue #4 — P0 CEM discovery diagnostics](https://github.com/vorlocsev/virtualcar/issues/4).** Backend telemetry (PR #11) и ISO-TP backpressure с сохранением STmin (PR #13) интегрированы в development. Приоритет теперь за VMware read-only трассой и классификацией фактических CEM-запросов. Не вводить положительные ответы A3/A6/B9F0 без подлинного подтверждённого capture. Проверить незавершённый PR #12 отдельно, но не использовать его как доказательство идентификации. Проверять GitHub Actions на текущем SHA, а не только на HEAD PR #13.

1. Сверить `PassThruWriteMsgs/ReadMsgs` с временными метками, ChannelID, baud, protocol и 11/29-bit форматами; отдельно сравнить D2 и P3 маршруты.
2. Проверить `A3/A6/B9F0/B9FB` и `0x726/0x18DA50F1` без предположений о положительных ответах.
3. Отличать `no_fixture`, `unsupported`, `timeout`, `partial_rx`, `negative_response`, `delivered` и `unverified`. Доставка RX не означает принятие VIN диагностическим клиентом.
4. Не допускать смешения каналов, сброса при ISO-TP Flow Control и ложной полноты First Frame.
5. Сохранять B9FB 13 кадров, READ128 и отсутствие новых положительных ECU-ответов.
6. Не публиковать частный INI, VIN, исходные дампы или журналы; использовать только метаданные и синтетические тесты.
7. Для нового PR выполнять 6–8 содержательных проверок и CI на HEAD.
8. До результата реального запуска Windows/VMware и проверки физического J2534 не объявлять CEM обнаруженным.

**PR #2 `development → main` остаётся отдельным gate: не сливать и не выпускать релиз без явного подтверждения.**

## 6. Проверки и сборка

Из чистого checkout `development` в Linux CI:

```bash
cd emulator
bash build-cross.sh
gcc -std=c11 -O2 -Wall -Wextra -o /tmp/virtualcar_test \
 tests/virtualcar_test.c src/p2core/p2_cem_router.c \
 src/p2core/p2_ls_observer.c src/p2core/p2_vehicle_core.c \
 src/p2core/p2_j2534_bridge.c
/tmp/virtualcar_test
python3 -m unittest discover -s tests -p 'test_*.py'
(cd control && go test ./... -count=1 && go vet ./...)
```

Артефакты x86: `VirtualCarJ2534.dll` и `VirtualCarControl.exe` в GitHub Actions по `.github/workflows/emulator.yml`. Проверять PE32 и 14 J2534 PassThru exports. Для dev26 прокси отдельно `bash build_dev26.sh` из корня репозитория.

## 7. Как вести чат и обновлять эту контрольную точку

- Пользователь предпочитает **русский**, короткие ответы, **6–8 осмысленных проверок на этап**, реальное изменение кода и **один PR** вместо бесконечных микропатчей.
- Команда **«далее»**: узнать актуальный Issue/PR/HEAD/CI, выполнить следующий полезный этап и сообщить **коммит/PR, подтверждённые проверки, блокеры и следующий шаг** без пересказа истории.
- **После слияния задачи в development** обновить только изменившиеся факты этого `NEXT_CHAT.md`: текущую точку, закрытые проблемы и ближайший Issue. Не коммитить в `main` ради обновления checkpoint.
- Не заявлять успех Windows/VMware, если были только Linux/cross-build тесты. Не публиковать стабильный релиз без явного подтверждения пользователя.
- Когда приватный репозиторий не читается из нового чата, сначала запросить подключение **GitHub**, а не создавать новый проект с нуля.

## 8. Готовый текст в новый чат

```text
Продолжи разработку Virtual Car из приватного GitHub-репозитория
https://github.com/vorlocsev/virtualcar .
Рабочая ветка development (не main). Сначала прочитай
https://github.com/vorlocsev/virtualcar/blob/development/NEXT_CHAT.md
и AGENTS.md, затем проверь актуальные Issues, PR и CI.
Начни с Issue #4. Выполни следующий этап кодом и тестами,
создай один PR в development. PR #2 и main не сливай до
подтверждённых VMware-тестов; никаких выдуманных ответов CEM
и приватных VIN в GitHub. Отчёт кратко по-русски.
```

*Этот документ создан для продолжения с **нового чата**. Его состояние обновляется через GitHub, а не зависит от памяти или истории текущей беседы.*


