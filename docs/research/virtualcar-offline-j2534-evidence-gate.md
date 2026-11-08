# Virtual Car: офлайн-критерии доказательности J2534 и обнаружения CEM (2026-11-08)

## Статус и границы

**Это план проверки, а не отчёт о выполненном E2E-тесте.**
Проверены исходники исследовательской ветки `fix/vida-local-sql-tls-optin`, где уже имеются:
`emulator/tools/audit_j2534_connect.py`,
`emulator/tools/audit_j2534_discovery.py`,
`emulator/tools/audit_backend_evidence.py`,
синтетические тесты и документация `emulator/README_DEV31_EVIDENCE_RU.md`
и `emulator/README_VMWARE_LAB_RU.md`.

`main` и исследовательская ветка содержат **разные объёмы кода**.
Успешная GitHub Actions VMware development validation
[run 42303242177](https://github.com/vorlocsev/virtualcar/actions/runs/42303242177)
(2026-11-06, `main`, commit `606e33b`, job Python/Go/C++/.NET gates)
**не означает**, что исследовательская ветка прошла идентичную CI
или что VIDA, SectorV или VDASH обнаружили реальный XC90 V8 MY2009 в VMware.

Изолированная VM без подключённого реального J2534 и без автомобиля.
Только ранее разрешённые чтение/обнаружение; никаких PIN, SecurityAccess,
программирования, изменения CEM, конфигурационных записей, reset,
напряжения программирования, доступа к реальным ECU или имитации их успеха.
В репозиторий допускаются лишь проверенные обезличенные агрегаты.
Не загружать оригинальные трассы, VIN, INI, дампы, профили-доноры,
SQL scripts, персональные идентификаторы и чувствительные пути.

## Входные артефакты: сначала проверить их наличие, не подменять

- Локальный текстовый журнал виртуальной DLL (документация проекта
  приводит `%TEMP%\SectorVVirtualCar.log`). Существует только после
  подходящего запуска; может не содержать metadata BE из новой сборки.
- Необязательная backend-телеметрия
  (`%LOCALAPPDATA%\VirtualCar\dev47-backend.jsonl`) при включённом
  backend logging в совместимой DLL.
- Версия/архитектура именно использованной J2534 DLL и имя программы-клиента
  подтверждаются **локально**; не отправлять приватные пути или бинарники.
- Если ни одного достоверного исходного лога нет: **NOT_TESTED**;
  не создавать искусственный `PASS` на основе fixture или SQL-модели.

## Восемь независимых критериев

| № | Gate | Проверяемое свидетельство | Что не считается доказанным |
|---|---|---|---|
| 1 | Provenance | Настоящий изолированный запуск, бинарник x86, явная версия, без физического адаптера; хеш локально | Релиз, совместимость VIDA, аппаратный CAN |
| 2 | J2534 Connect | Фактическая успешная попытка PassThruConnect: CAN/ISO15765, flags, 125/500 кбит/с, статус | Физическая LS CAN; неизвестные протоколы 0x8004/0x8005/0x10000001 не переименовываются |
| 3 | Каналы и фильтры | Отдельные HS/LS/ISO каналы и события фильтрации без межканального смешения | Успех диагностики от одного только Connect |
| 4 | D2 запросы | Наблюдаемые допустимые read-only CEM A3/A6/B9F0/B9FB/FC с известными target и контекстом | Значения параметров A3, normal mode или подлинность VIN |
| 5 | Факт доставки RX | Только успешный PassThruReadMsgs / backend rx_dequeued, корректный канал и порядок | `response_generated`, `rx_queued` или `RX simulated` сами по себе НЕ равны доставке |
| 6 | B9FB и идентификация | Количество/порядок/финальный фрагмент, соответствие ожидаемой форме без сырых данных | «13 кадров» сами по себе НЕ подтверждают XC90 MY2009, декодирование VIN или принятие клиента |
| 7 | ISO-TP/UDS и отказы | FF/CF, FC, timeouts, NRC 0x78, отрицательный ответ, разделение `partial_rx`, `no_fixture`, `unsupported`, `unverified` | Отсутствие наблюдения != ECU отказал; успешный RX != успешная аутентификация |
| 8 | Межслойная сверка | Классифицированный TX → маршрут → backend outcome → RX dequeue в одной сессии, с отдельной ручной проверкой UI клиента | Корреляция по времени разных логов без общего ID; доказанный клиентский результат лишь по телеметрии |

Оценка каждого gate: `PASS_OFFLINE_METADATA`, `FAIL`, `NOT_OBSERVED`,
`NOT_TESTED`, `AMBIGUOUS`. **Отдельная графа**
`ClientAcceptedVehicleIdentity` остаётся `NOT_VERIFIED`,
пока диагностическая программа сама не показала подтверждённую
идентификацию в разрешённом тесте. Не подставлять реальный VIN для достижения «успеха».

## Безопасная обработка уже имеющейся частной трассы

Команды запускаются **локально из каталога `emulator`** внутри
изолированной лаборатории, только если указанные исходные файлы
действительно существуют. Выходные файлы должны быть **новыми**:
анализаторы отказываются перезаписывать существующий отчёт.
Оригинальные журналы никуда не отправляются.

```powershell
py -3 .\tools\audit_j2534_connect.py "$env:TEMP\SectorVVirtualCar.log" --output "$env:USERPROFILE\Desktop\j2534-connect-audit.json"
py -3 .\tools\audit_j2534_discovery.py "$env:TEMP\SectorVVirtualCar.log" --output "$env:USERPROFILE\Desktop\cem-audit.json"
py -3 .\tools\audit_backend_evidence.py "$env:LOCALAPPDATA\VirtualCar\dev47-backend.jsonl" --output "$env:USERPROFILE\Desktop\backend-audit.json"
```

Если backend JSONL отсутствует, третью команду **пропустить**;
это не `no_response` ECU. Если старая DLL не записывала метаданные
Connect, нулевой отчёт о Connect означает **нет достаточной телеметрии**,
а не отсутствие попытки подключения.

Выходные JSON нужно просмотреть вручную до передачи: штатные инструменты
ограничивают значения разрешёнными категориями, но отсутствие неизвестной
формы исходного журнала не гарантируется для всех будущих сборок.
Не публиковать raw log даже если он уже частично обезличен.

## Результат первого владельческого офлайн-аудита (2026-11-08)

Пользователь запустил `Run-VirtualCar-OfflineAudit-v2.ps1 -Stage Analyze`
на личной Windows. Подготовка через авторизованный GitHub CLI
вместо публичного raw URL прошла, затем все три pinned-анализатора
завершились с `Result=OK`. **Исходные локальные логи не загружались,
не изменялись и в GitHub не включаются.**

Метаданные входных файлов, наблюдавшиеся до анализа:
J2534 text ~23 993,5 KiB (последняя модификация 2026-11-05 02:14:36);
backend JSONL ~7 714,1 KiB (2026-11-03 21:18:18).
Даты последней модификации **не** устанавливают начальную/конечную
границу, число сеансов или синхронность журналов.

| Счётчик | Наблюдено |
|---|---:|
| J2534 Connect attempts, включая неизвестные успех/неудачу | **7510** |
| Discovery transactions | **1347** |
| Backend requests | **6468** |
| Backend parser-invalid lines | **66** |
| ClientAcceptanceVerified / VehicleIdentityVerified | **False / False** |

| Статус | Discovery | Backend |
|---|---:|---:|
| `delivered` | **144** | **2121** |
| `no_fixture` | **838** | **71** |
| `unsupported` | **32** | **1080** |
| `unverified` | **287** | **3196** |
| `timeout` | **39** | **0** |
| `partial_rx` | **4** | **0** |
| `negative_response` | **3** | **0** |

**Интерпретация по реализации анализаторов:**
`discovery.no_fixture` означает явное событие отсутствующей
фикстуры, `backend.no_fixture` означает терминальное
`missing_profile/no_response`; это разные критерии и
несвязанные локальные накопленные журналы. `backend.unsupported`
охватывает явные `unsupported_bus` / `unhandled_request` /
`unimplemented_probe` с отсутствием ответа. `backend.unverified`
включает неполный lifecycle, конфликт контекста, отсутствие
подтверждённого завершения, очередь без RX-доставки и другие
случаи, а не одну конкретную ошибку. `delivered` лишь подтверждает
доставку через J2534 по правилам каждого анализатора, но не
успешное обнаружение CEM, VIN или принятие клиента. 66 не
принятых строк не доказывают порчу файла: это могут быть
неразрешённые/несоответствующие схеме строки.

**Нельзя складывать или взаимно вычитать** 144 и 2121,
838 и 71, 287 и 3196: исходники разные, с разными датами
последней записи и независимыми моделями статусов.
7510 попыток Connect не равны 7510 успешным каналам; разбивка
по статусам пока не предоставлена. Исследователь не видел
сырых payload, VIN, индивидуальных сеансов или полного JSON.

**Следующий строго локальный срез без чтения raw logs:**
использовать три уже полученных обезличенных JSON под
`Downloads/VirtualCar-OfflineAudit-v2/reports`, выделив только
разрешённые категории: Connect status/mode, D2 CEM
target `0x40/0x50` × `A3/A6/B9F0/B9FB/B9FC` × статус,
backend `coverage.probes` для тех же D2, и агрегаты
причин `unverified`. Не печатать transaction/session ID,
CAN data, исходные пути, VIN или пользовательские идентификаторы.
Если окажется, что B9FB часто `no_fixture`, искать наличие
верифицированной фикстуры, но **не генерировать** неподтверждённые
положительные ответы. Если преобладает `unverified`, выяснять
терминальные события/доставку, не предполагать провал ECU.
Реальное принятие VIN/идентичности клиентом всё ещё `NOT_VERIFIED`.

## Повторная детализация накопленных обезличенных JSON (2026-11-08)

Оператор выполнил локальный `Summarize-VirtualCar-CEM-Audit.py`
только по сохранённым JSON из `VirtualCar-OfflineAudit-v2`.
Скрипт сообщил `RawLogsRead=False; NoNetwork=True; NoAdapterCalls=True`,
`Result=OK`. Исходные файлы, ключи, VIN, CAN payload и полные JSON
не передавались.

### Адаптер: подтверждённые категории попыток подключения

- Всего **7510** `Connect` attempts: **4228 `ok`** и
  **3282 `invalid_protocol`**. Это количество попыток, не число
  успешно идентифицированных ECU или независимых диагностических сеансов.
- Частые `ok` режимы: `ISO15765` / 500000 / `flags=other`
  **2126**; `CAN_PS` / 125000 / `flags=other` **2069**.
- Частая неудача: `protocol=other flags=other baud=other`
  `invalid_protocol` **3194**.
- Наличие `CAN_PS` success в **накопленном** журнале нельзя
  приписывать конкретной сборке, а `flags=other` означает лишь
  отсутствие разрешённой категории флага в таблице анализатора.
  Это отдельная **гипотеза несовместимости версий**, а не доказанная
  регрессия текущей DLL. В текущем `emulator/README_P3TOOL_J2534_PREFLIGHT_RU.md`
  есть явные `ERR_INVALID_PROTOCOL_ID` для vendor `0x8004/0x8005`
  в описанной там сборке; смешанные исторические данные сначала
  нужно разбить по **доказуемой границе сессии/версии**.

### Discovery: CEM target×service

| Target | Service | Total | Разбивка |
|---|---|---:|---|
| 0x40 | A3 | 32 | unverified 28, timeout 4 |
| 0x40 | A6 | 2 | unverified 2 |
| 0x40 | B9F0 | 29 | no_fixture 29 |
| 0x40 | B9FB | 250 | no_fixture 249, unverified 1 |
| 0x50 | A3 | 59 | unverified 55, timeout 4 |
| 0x50 | A6 | 56 | unverified 50, timeout 6 |
| 0x50 | B9F0 | 63 | no_fixture 35, unsupported 28 |
| 0x50 | B9FB | 155 | delivered 119, no_fixture 31, unsupported 4, unverified 1 |
| 0x50 | B9FC | 6 | delivered 2, no_fixture 4 |

Неатрибутированные конкретному CEM target/service в отчёте
группы: `OtherRoute D2=464`, `P3=231`.
Сумма 652 целевых CEM операций и 695 остальных = 1347
Discovery transactions. Итого **нет `delivered` для
`0x50 B9F0`**, а для `0x50 B9FB` `delivered`
**119 из 155 (76,8%)**. Нельзя заключать, что B9F0 требуется
для VIN в данной версии клиента или что доставленный B9FB
принят клиентом. Для `0x40 B9FB` почти всегда явное
`no_fixture`, но отсутствие 0x40 ответа не всегда
означает неверную работу P2 клиента/сети.

### Backend: отдельно от Discovery

Из известных CEM D2 coverage группы:
`D2_40_A3=3 unsupported`,
`D2_40_B9F0=2 no_fixture`,
`D2_40_B9FB=25 no_fixture`,
`D2_50_A3=5 unsupported`,
`D2_50_A6=2 unsupported`,
`D2_50_B9F0=4 (2 no_fixture, 2 unsupported)`,
`D2_50_B9FB=20 (8 delivered, 10 no_fixture, 2 unsupported)`.
Это **разные накопленные журналы** и другая классификация,
не 20 совпадающих с Discovery операций.

Все **3196** backend записей `unverified` получили
`reason=explicit_no_response`. Согласно исходнику
`audit_backend_evidence.py` это существующий терминальный
`outcome=no_response` **без достаточного основания**
отнести к `missing_profile` / `unsupported_bus` /
`unhandled_request` / `unimplemented_probe`. Это **не**
3196 доказанных сбоев ECU и не отсутствие терминальных
событий по умолчанию. `BackendInvalidLines=66` означает
непринятые анализатором строки; без чтения raw не установлено,
порча это или несовместимый формат.

### Следующий локальный диагностический gate

Только по уже обезличенному `discovery.json` проверить
`0x50 B9FB` и `0x50 B9F0` по типу транспорта
(`CAN/ISO15765/unknown`), скорости и **агрегированным корзинам
числа RX кадров** (0, 1–12, 13, 14+), а не по VIN или CAN
payload. Отдельно сгруппировать `CAN_PS` success из
`connect.json` как **накопленные** события без заявления
о текущей DLL. Возможно после этого понадобятся отдельно
проверенные границы односессионного лога, но не следует
получать их путём догадки по разным датам файлов.

**Критерий идентификации XC90 V8 MY2009 пока NOT_VERIFIED.**
Нельзя генерировать правдоподобные ответы `B9F0` или
`A3/E3` по одним только счётчикам.

## Локальный CEM Transport Gate по ранее обезличенным JSON (2026-11-08)

Владелец запустил `Summarize-VirtualCar-CEM-Transport.py`
**только по ранее подготовленным обезличенным JSON**.
`RawLogsRead=False`, `Network=False`, `J2534Calls=False`,
`Result=OK`. Ни SQL, ни адаптер, ни исходные журналы
не затронуты; никаких сырых кадров или VIN в отчёте нет.

**CEM 0x50, B9FB:** всего **155** анализируемых запросов:
**119 delivered**, **31 no_fixture**, **4 unsupported**,
**1 unverified**. Все **119 delivered имеют 13 RX кадров** по
счётчику анализатора. Из них только **11** имеют явно известные
`protocol=CAN, baud=500000`; у остальных **108** протокол
или скорость не известны. Среди B9FB `no_fixture`
**22** явно имеют CAN/500000, **9** не имеют этого контекста.
Все **4 unsupported** B9FB имеют CAN/250000.
По всем 155 B9FB **118** без channel и **118** без известной
пары protocol/baud. Отсутствующие поля **не заполнять
догадками**. По реализации `audit_j2534_discovery.py`
`delivered` для многофрагментного D2 указывает на
согласованную форму/завершение фрагментов, **не на
содержательную корректность VIN, модельный год
или принятие клиента**.

**CEM 0x50, B9F0:** всего **63**: **35 no_fixture**,
**28 unsupported**, **0 delivered**, **0 RX** по представленным
группам. Из `no_fixture` только **5** имеют CAN/500000,
**30** unknown; из `unsupported` **3** имеют CAN/250000,
**25** unknown. Для **55 из 63** отсутствует channel
и известная пара protocol/baud. На основании отсутствия
доставленного B9F0 в этих накопленных журналах нельзя
доказывать, что клиенту необходим ответ B9F0 для
идентификации, и тем более генерировать фиктивный.

**Backend как независимый накопленный журнал:**
CEM 0x50 B9FB **20** (**8 delivered**, **10 no_fixture**,
**2 unsupported**); B9F0 **4** (**2 no_fixture**,
**2 unsupported**). Это не те же самые 155/63 события
Discovery: **CrossLogCorrelation=NOT_VERIFIED**.

**Историческая CAN_PS статистика**:
**2082 ok**, **71 invalid_protocol**, версия каждого
сеанса `UNKNOWN`. Она не доказывает поддержку
CAN_PS текущей DLL и не даёт права трактовать
ошибки текущей сборки как регрессию без совпадения
версии/экземпляра/сессии.

### Решение после Transport Gate

Не повторять агрегирование 13-кадровых старых B9FB:
**завершение транспорта наблюдалось**, но валидность
профиля XC90 MY2009 и принятие клиента `NOT_VERIFIED`.
Следующий отдельно ограниченный этап: **только чтение**
регистрации J2534 в 32-битном Windows Registry View,
существования/PE32 архитектуры указанной там DLL и
обезличенных идентификаторов версии, без загрузки DLL,
смены регистрации, модификации INI, запуска ECU или
взаимодействия с реальным адаптером. Это подтверждает
**текущую** зарегистрированную DLL, не версии исторических
строк лога. Затем спланировать один новый
изолированный VMware-сеанс read-only с явной границей
нового сеанса и разрешёнными формами диагностики,
**без** неподтверждённых ответов A3/E3, B9F0 или
реального VIN; отдельно наблюдать UI acceptance.

## Проверка регистрации виртуального J2534 (2026-11-08)

Владелец запустил локальный `Inspect-VirtualCar-J2534ProviderReadOnly.ps1`
и получил:

```text
[VirtualCar] RegistryView=Registry32; ReadOnly=True
[VirtualCar] ProviderRegistrationPresent=False
[VirtualCar] Result=NOT_REGISTERED
[VirtualCar] ScriptFinished
```

Это **не отказ загрузки DLL и не доказательство отсутствия всех
виртуальных J2534 адаптеров**: инспектор целенаправленно смотрит
единственный путь `HKLM\SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car`
через `RegistryView.Registry32`. Репозиторный
`emulator/scripts/install.ps1` действительно создаёт именно
такой ключ при установке описанной сборки. Скрипт не
перечисляет соседние имена провайдеров, не проверяет
`Registry64` или версию `PassThruSupport.05.00`,
не запускает J2534 клиента и не доказывает, где именно
проводилась запись исторических журналов.

**Важная граница:** ранее собранные офлайн-отчёты о 4228
успешных Connect и 119 завершённых D2 B9FB 13-frame
относятся к **историческим накопленным логам**.
Они совместимы с последующим удалением регистрации,
с другим именем провайдера, с другой Windows/VM
или иным состоянием машины. Не утверждать, что
виртуальный адаптер зарегистрирован **сейчас**, и
не считать отсутствие одной записи программной ошибкой
текущей DLL.

**Следующий безопасный шаг:** на той же Windows прочитать
только количество подразделов J2534 в реестрах
`Registry32` и `Registry64`, разделы версий
`PassThruSupport.04.04` и `PassThruSupport.05.00`,
и наличие имени, совпадающего с `Virtual Car` или
`SectorV`. Не выводить FunctionLibrary-пути,
имена сторонних адаптеров и идентифицирующие данные;
не создавать, не удалять и не менять ключи.
Если результаты пусты, проверять VM/ПК, на котором
ранее действительно были получены логи, а не
немедленно запускать установщик/менять регистрацию.
Только после подтверждения среды планировать отдельный
изолированный диагностический сеанс.

## Four-view J2534 registry enumeration (owner's Windows, 2026-11-08)

After the **narrow** check of the one expected 32-bit name reported
`NOT_REGISTERED`, the owner ran a separate read-only enumeration
counting provider subkeys and Virtual Car / SectorV **name matches**
without revealing names, paths, DLLs or credentials:

| Registry view | PassThruSupport version | Provider subkeys | Virtual Car / SectorV name matches |
|---|---|---:|---:|
| Registry32 | 04.04 | **6** | **3** |
| Registry32 | 05.00 | 0 | 0 |
| Registry64 | 04.04 | **1** | **0** |
| Registry64 | 05.00 | 0 | 0 |

**Interpretation:** at least three 32-bit 04.04 provider-key
*names* match the laboratory adapter's old/new naming family.
The exact key `SectorV Virtual Car` probed earlier is absent,
but **other** names exist: the earlier `NOT_REGISTERED` output
was deliberately narrow and does not establish no virtual
provider registration in this Windows. A registry subkey match
alone does **not** prove `FunctionLibrary` is populated,
its DLL exists/has PE32 architecture, or any software used it.
The one 64-bit 04.04 provider has no name match and is not
claimed to be Virtual Car. These current settings are distinct
from the mixed historical J2534 logs.

**Next owner-local read-only check:** inspect only the **three
matched 32-bit keys**, recording ordinal `Match`,
`NameFamily`, whether `FunctionLibrary` is set,
`DLLExists`, `PEMachine`, numeric-only `FileVersion`,
and locally numbered `BinaryGroup` (equal SHA256 content
without printing hashes). Never show paths, exact provider
subkey names or other third-party providers; never load,
register or execute DLLs, call the J2534 API, or change any
setting. The helper `Inspect-VirtualCar-J2534Aliases.ps1`
was constructed locally for the owner to inspect before
running; no Windows execution or result of this helper
is yet claimed.

## Доказательства, имеющиеся сейчас

- В предыдущих исследованиях подтверждены браузер/WebView ↔ WildFly TCP
  и WildFly ↔ SQL Server TCP, но **не прохождение одного HTTP→SQL→J2534 запроса**.
- `DiagSwdlRepository.dbo.GetScript` существует; исходный caller и
  runtime `@scriptType` остаются неизвестными. Кэшированный план
  отсутствовал в одном снимке, что **не доказывает отсутствие прошлых вызовов**.
- Достоверный офлайн-запуск VIDA/SectorV/VDASH с Virtual Car, показывающий
  принятие VIN/идентичности XC90 V8 MY2009, в этом исследовании **не предъявлен**.
- Статус этапа: **готовность офлайн-анализаторов по исходникам подтверждена;
  новый реальный виртуальный J2534-сеанс NOT_TESTED**.

## Решение по следующему шагу

Сначала проверить наличие **ранее полученного** приватного лога подходящей
версии в изолированной VM; если есть, прогнать анализаторы и передать лишь
обезличенные JSON/агрегаты. Если логов нет, отдельно спланировать
одну короткую разрешённую read-only VM сессию без реального J2534.
Любой успех должен подтверждаться одновременно нужными J2534 метаданными
и состоянием диагностического клиента, а не угадываться из количества RX.

Не публиковать Virtual Car сборки, не менять `main`, не объединять
черновой исследовательский PR без отдельного решения.
