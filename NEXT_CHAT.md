# Virtual Car: продолжение разработки в новом чате

> **Старт здесь.** Приватный репозиторий: https://github.com/vorlocsev/virtualcar. **Рабочая ветка: `development`**, а не `main` (default branch пока содержит старую dev26-базу). Документ является контрольной точкой, а не заменой фактической проверки GitHub.

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

