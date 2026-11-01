# Virtual Car: продолжение разработки в новом чате

> **Старт здесь.** Приватный репозиторий: https://github.com/vorlocsev/virtualcar. **Рабочая ветка: `development`**, а не `main` (default branch пока содержит старую dev26-базу). Документ является контрольной точкой, а не заменой фактической проверки GitHub.

## Актуальный checkpoint: дополнительный поиск публичных P2 captures (02.11.2026)

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


