# Virtual Car: продолжение разработки в новом чате

> **Старт здесь.** Приватный репозиторий: https://github.com/vorlocsev/virtualcar. **Рабочая ветка: `development`**, а не `main` (default branch пока содержит старую dev26-базу). Документ является контрольной точкой, а не заменой фактической проверки GitHub.

## Текущий этап: CAN_PS configuration-only probe (02.11.2026)

- Новый ограниченный run на **6153297**: **3 PASS_FILTER**, у mask/pattern CAN_PS и DataSize4, flow отсутствует. Два с flags0/redacted mask/11-bit pattern, один с flags0x100/zero mask+pattern. **5 periodic requests по1000ms**, все D8, pins3/11; ещё5 D8 writes, все отклонены. **Прямой module binding получен**, GUI2.5.115.85 и хеши не изменились. Supervisor сработал по90s worker deadline, увидев2 Close; полный suffix содержит3 Open/3 Close. Warning наблюдался, ECU list до остановки не проверен. Отчёт `docs/research/VDASH_CAN_PS_SETUP_RUNTIME_20261103.md` + summary.
- В этом run9 обычных TX/backend roots,3 VIN deliveries, invalid0. Процессы закрыты, прежние selection/registration восстановлены, префиксы журналов целы. Source CI [Emulator/native #41542195017](https://github.com/vorlocsev/virtualcar/actions/runs/41542195017) / [VMware LAB #41542194974](https://github.com/vorlocsev/virtualcar/actions/runs/41542194974) success, publish skipped. Следующий этап — отдельно спроектированный default-off API-outcome experiment для filter/write/periodic, без RX/ACK и general transport. Подтверждённые параметры не заменяют условие продолжения клиента.
- Продолжение #42: bounded metadata для ранее скрытых StartMsgFilter arguments и StartPeriodicMsg interval. API acceptance пока не меняется. Добавлены fixed9word filter и5word periodic markers в существующий connect auditor, отдельные counts без raw bytes/IDs/lengths. Восемь native/Python групп; local Python188OK/1expectedskip. Новый HEAD/CI сверять live; повторный многочасовой scan не нужен.

- Новый instrumented run **02–03.11** на source `7a41da1`: GUI **2.5.115.85** (изменился после launch; worker hash прежний), synthetic MY2005; **4022 rejected calls = 2011 writes + 2011 periodic registration**, все `D2_D8_unverified_prefix`, pins3/11, invalid0. **1006 Open/Close** — длительные фоновые повторы в одном GUI invocation, не независимые scans. 3018 обычных TX/3018 backend roots, 1006 VIN deliveries; ECU list пуст. Прежний warning в этом run agent не наблюдал. Прямого module sample нет, не называть registered hash loaded DLL hash. Отчёт/summary `docs/research/VDASH_CAN_PS_REJECTED_RUNTIME_20261103.md`. Клиент/собственные процессы закрыты, прежний adapter selection восстановлен, temp registration удалена, log prefixes целы.
- Source HEAD `7a41da141df17c935fd80b76cea32976f1c64637`: [Emulator/native x86 #41493503068](https://github.com/vorlocsev/virtualcar/actions/runs/41493503068) и [VMware LAB #41493503105](https://github.com/vorlocsev/virtualcar/actions/runs/41493503105) success; prerelease publish skipped. PR #42 открыт в development без merge. Следующий вопрос: происхождение/роль D8 и конкретное условие перехода после PS filter/write/periodic; D8 prefix не доказывает ACK или дефект ECU fixture. Не добавлять transport/ответы до отдельного обоснованного этапа.

- Actual Windows run PR #42 HEAD `8247a594`, отчёт `docs/research/VDASH_CAN_PS_PROBE_RUNTIME_20261102.md` + metadata summary: GUI 2.5.115.84, synthetic MY2005, один invocation/worker, все 13 Open/13 Close, direct module hash. **27 PS Connect OK и 27 J1962_PINS=0x030B SET OK**; далее 3 filter, 25 write, 25 periodic регистрации ERR_NOT_SUPPORTED по дизайну probe. 13 VIN deliveries/26 metadata OK, warning/ECU list empty unchanged. App/monitor закрыты, selection восстановлен, temporary registration удалена.
- Прежний gap: **payload/CAN ID 25 rejected PS WriteMsgs не логировались**; 39 ordinary TX не охватывают эти попытки. В том же PR #42 добавлена отдельная metadata-only классификация rejected/not-transmitted WriteMsgs и periodic registration calls: узкие D2/OBD/P3 shapes, invalid/unknown/excluded категории; zero/batch без разыменования массива. Транспорт по-прежнему отклонён, RX/backend roots не создаются. Новый run выше не восстанавливает прежние 25 попыток и не доказывает причину warning. Не добавлять фиктивные CEM ответы. VMware guest/physical run с probe не выполнялся.

- Development live base `ac1f523a319a0d29e61d7e5ac07307446925cf16` (PR #40 merged). PR #39 remains draft at `6f16bc34`; PR #41 open at `c0f6484`, CI [x86/native-routes #41449592025](https://github.com/vorlocsev/virtualcar/actions/runs/41449592025) и [VMware LAB #41449590010](https://github.com/vorlocsev/virtualcar/actions/runs/41449590010) success. Отчёт настоящего Windows GUI run MY2005 находится в #41: 68 CAN_PS/125k rejects, causal link с warning не доказана. Новая ветка `feature/can-ps-config-probe` создана от development, не включает код draft #39 и #41.
- Проверены primary vendor docs. J1962_PINS ID **0x8001**, прежнее **779** было pin value, а не ID. Реализуется default-off `[Diagnostics] EnableCanPsConfigProbe=1`: отдельный ProtocolID 0x8004, observation GET/SET pins, без транспорта, RX, filters/periodic или передачи ECU. Не alias CAN. Подробности/источники: `emulator/README_CAN_PS_CONFIG_PROBE_RU.md`.
- Gate version/hash-bound Windows run выполнен, J1962 value и следующие API шаги подтверждены выше. Для новых функций нужны отдельные проверки: текущий probe не является CAN_PS transport. VMware guest и physical run не заявлять. Не добавлять положительные CEM ответы; main/Dvinholm/prerelease не менять.

## Предыдущий этап: VDASH offline evidence (02.11.2026)

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


