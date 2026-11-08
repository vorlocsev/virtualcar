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
was constructed for offline owner review, but the owner
reported that the downloaded file was unavailable and
instead **ran equivalent inline read-only PowerShell**.

**Owner-run exact result (2026-11-08):** of the three
name-matching `Registry32/PassThruSupport.04.04` entries
(sorted by registry subkey name), **Entry 1** has
`DLLExists=True`, `PEMachine=x86`, `FileVersion=Unknown`,
`BinaryGroup=DLL1`; **Entry 2 and Entry 3** have
`DLLExists=False`, `PEMachine=Unknown`, `FileVersion=Unknown`,
`BinaryGroup=None`. The result confirms **one existing x86
PE image** referenced by a matching J2534 registry entry,
plus **two stale/broken FunctionLibrary path references**.
It does not prove that Entry 1 has all required J2534
exports, can be loaded by a client, is the current official
Virtual Car build, or was used for historical logs.
`FileVersion=Unknown` means the check did not find a
numeric standard file-version resource; it is **not** a
reliable failure criterion. No paths, hashes or provider
names were exposed; no DLL was loaded or called.

**Next safe gate:** on this same Windows, inspect only
Entry 1's declaration metadata (`CAN`, `ISO15765`,
`MessageVersion`) plus local file size/timestamp, **without**
revealing paths or provider names and **without** changing
any registry keys. Consider a subsequent static PE export
inspection if suitable tooling exists; registry declarations
and x86 header alone do not establish functional J2534 ABI.
Do not delete Entries 2/3 yet, auto-register Entry 1,
or use the physical J2534/vehicle. First verify whether
this Windows is the intended isolated VM and which exact
provider the diagnostic application is configured to select.

## Метаданные единственной существующей x86 J2534 DLL (2026-11-08)

Владелец выполнил ещё одну read-only проверку **Entry 1** из
трёх name-matched J2534 Registry32 провайдеров. Обнаружено:

| Свойство | Значение |
|---|---|
| DLLExists | True (из предыдущего owner check) |
| PEMachine | x86 (из предыдущего owner check) |
| FileSizeKiB | **9,5** |
| ModifiedUTC | **2026-10-31 02:37** |
| Объявлено `CAN` | **1** |
| Объявлено `ISO15765` | **Missing** |
| `MessageVersion` | **Missing** |
| `FileVersion` | Unknown (из предыдущего owner check) |

Это **настоящие результаты чтения реестра и метаданных локального
файла**, но не фактическая верификация PassThru API.
Отсутствие ключа `ISO15765` и `MessageVersion` у единственной
существующей DLL может влиять на выбор адаптера диагностическим
клиентом, но не означает, что J2534 функции обязательно отсутствуют.
Размер 9,5 KiB не позволяет установить, это эмулятор, proxy или
узкий тестовый ABI-stub. `FileVersion=Unknown` не является
фатальным результатом и не раскрывает идентичность версии
исторических журналов.

**Дальнейший gate:** только статически прочитать таблицу
**PE экспортов** указанной Registry32 DLL, без `LoadLibrary`,
без J2534 вызовов и без теста на физическом адаптере.
Сравнить объявленные имена 14 функций PassThru04.04 с
экспортами; если они отсутствуют, потребуется выяснить
правильную лабораторную DLL. **Наличие всех 14 имён не
доказывает рабочий backend, корректный ISO-TP и
принятие VIN клиентом**. Файл не публиковать,
не копировать в GitHub, не выводить путь или hash.
Не исправлять реестр и не удалять две устаревшие записи
до проверки, какую выбирает клиент.

## Статические PE-экспорты существующей J2534 DLL (2026-11-08)

Владелец повторно выполнил локальный PowerShell + Python
read-only PE export inspection **единственного существующего
x86 файла**, найденного через реестр. В предыдущем
PowerShell первая попытка была прервана из-за
отдельной интерактивной строки `else {`, но
переработанный независимый static-PE считыватель
успешно завершился:

```text
[VirtualCar] PEExportInspection
PEMachine=x86
TotalExportNames=14
ExactJ2534Exports=14/14
PassThruOpen=Exact
PassThruClose=Exact
PassThruConnect=Exact
PassThruDisconnect=Exact
PassThruReadMsgs=Exact
PassThruWriteMsgs=Exact
PassThruStartPeriodicMsg=Exact
PassThruStopPeriodicMsg=Exact
PassThruStartMsgFilter=Exact
PassThruStopMsgFilter=Exact
PassThruSetProgrammingVoltage=Exact
PassThruReadVersion=Exact
PassThruGetLastError=Exact
PassThruIoctl=Exact
Result=OK
```

Это доказывает **наличие имён в PE export directory**,
но не ABI calling convention или фактическое поведение,
не успех `PassThruOpen/Connect`, не готовность ISO15765
и не признание ECU клиентом. Исполняемый код не запускали.

**Выявлена конкретная гипотеза для проверки происхождения:
** `emulator/native-cpp/CMakeLists.txt` собирает
`VirtualCarJ2534Cpp` из
`emulator/native-cpp/src/j2534_fail_closed.cpp`
как **M3 fail-closed ABI validation DLL**, прямо запрещённую
к регистрации как функциональный PassThru.
Она также декларирует **14 бездекорированных
`PassThru*` экспортов**, но `PassThruOpen`
завершает `ERR_DEVICE_NOT_CONNECTED`,
`PassThruWriteMsgs` блокирует TX, не
открывает транспорт/IPC/автомобиль и не эмулирует ECU.
Поскольку её имя сборки `VirtualCarJ2534Cpp`
и бинарное происхождение **не доказано** для
локальной DLL 9,5 KiB, нельзя объявлять
установленный файл M3 только из совпадения
числа экспортов.

**Следующий безопасный дифференцирующий признак**:
локально без запуска DLL проверить наличие
точных embedded ASCII strings
`Virtual Car lab service not connected`,
`Virtual Car lab operation unavailable`,
`Null J2534 parameter` из известного
fail-closed исходника. Вывести только
логические индикаторы присутствия, без текста
других строк, содержимого бинарника, пути
или полного хеша. Даже если все найдены,
это **сильная сигнатура кода**, не
криптографическая проверка происхождения;
если нет, это не доказывает рабочий эмулятор.
Ничего не устанавливать, не загружать DLL,
не обращаться к J2534 или реальному автомобилю.

## Статическая проверка M3 fail-closed строк (2026-11-08)

Владелец выполнил read-only локальное чтение встроенных ASCII-строк
единственной найденной DLL с `PEMachine=x86` и `ExactJ2534Exports=14/14`:

```text
DLLReadable=True
FailClosed_ServiceNotConnected=False
FailClosed_OperationUnavailable=False
FailClosed_NullParameter=False
```

Ни одна из трёх характерных ASCII-строк из
`emulator/native-cpp/src/j2534_fail_closed.cpp` не найдена.
Это **ослабляет, но не опровергает** гипотезу об идентичности
локальной DLL и M3 fail-closed заглушки: компоновка,
оптимизация, иной код/кодировка или версия могут менять
строки. Файл не загружался, J2534 функции не вызывались,
никакие параметры реестра не менялись. Наличие всех 14
экспортируемых имён по-прежнему не доказывает полноценную
реализацию Virtual Car.

**Новая обоснованная альтернативная гипотеза из исходников:**
`proxy/j2534_trace_proxy.c` является x86 J2534 forwarding
proxy: все 14 J2534 API вызовов направляются к другому DLL,
а в текстовых логах сохраняются лишь разрешённые категории
метаданных. Он не является автономным CEM эмулятором
и **не гарантирует read-only в реальной машине**.
Характерные локальные литералы этой реализации:
`VCAR_TRACE_REAL_DLL`, `VCAR_TRACE_LOG_PATH`,
`VirtualCarJ2534Trace.jsonl`.
**Следующий шаг**: только локально проверить наличие
этих точных ASCII/UTF-16 литералов в бинарнике;
сообщить лишь `True/False`, не показывать другие
строки, путь, payload или содержимое. Положительные
совпадения дадут сильное косвенное свидетельство
родства с proxy, но не криптографическое подтверждение
происхождения. Отсутствие не докажет полноценный
эмулятор. Никакой тест с физическим J2534/автомобилем
или загрузкой DLL не разрешается на этом шаге.

## Статическая проверка альтернативной trace-proxy гипотезы (2026-11-08)

После неудачного доступа к временной переменной `$path`
(`DLLPathNotAvailable=True`, что **не означало удаления файла**)
владелец повторно прочитал registry `Registry32`,
нашёл существующий файл **Entry 1** и проверил его точные
публичные строковые признаки из
`proxy/j2534_trace_proxy.c` без запуска или копирования DLL:

```text
[VirtualCar] J2534 DLL Inspection
Entry=1
DLLFound=True
SizeKiB=9.5
TraceProxyRealDll=False
TraceProxyLogPath=False
TraceProxyLogName=False
Result=OK
```

Проверяемые строки:
`VCAR_TRACE_REAL_DLL`, `VCAR_TRACE_LOG_PATH`,
`VirtualCarJ2534Trace.jsonl`; код искал ASCII и UTF-16.
Все три отсутствуют, что **ослабляет, но не исключает**
гипотезу точного соответствия данной DLL текущей
исходной реализации proxy (разные компиляция/версия/
конфигурация могут менять литералы). Ранее три
точные fail-closed M3 ASCII-строки также отсутствовали,
при этом имена PassThru **14/14** и PE32 x86 подтвердились.

**Статус:** бинари 9.5 KiB остаётся **неатрибутированным**;
ни совпадение 14 экспортов, ни отсутствие шести
литералов не доказывает автономный полноценный
виртуальный CEM или работающий backend.
Обнаружены две устаревшие Registry32 J2534 записи
с несуществующими DLL; нет доказательства, какую
выбирает диагностический клиент.

**Следующее рациональное действие:** вместо новых
догадок по строкам можно локально прочитать PE
import table или надёжные метаданные сборки;
все выводы только агрегированные, без paths,
секретов, payload и сырых бинарников, а окончательную
идентификацию версии делать по собственному
BUILDINFO/артефакту, если он доступен.
Не загружать/вызывать DLL и не менять registry.
Один новый clean-room VMware read-only сеанс должен
опираться на заранее проверенный идентификатор
сборки и одно конкретное имя провайдера,
а не на смешанные исторические логи.

## Проверка соседних файлов единственного живого J2534 provider (2026-11-08)

Владелец выполнил локальный read-only поиск по **каталогу,
в котором расположен единственный существующий Registry32
PassThruSupport.04.04 FunctionLibrary**. Код не выводил путь
или само имя DLL. Получены шесть отрицательных признаков:

```text
DLLNameKnown=False
DLLNameCpp=False
BuildInfoPresent=False
ChecksumsPresent=False
ControlAppPresent=False
ConfigPresent=False
```

Иными словами, текущая 9,5 KiB x86 DLL с 14/14 J2534
PE export names **не называется** `VirtualCarJ2534.dll`
или `VirtualCarJ2534Cpp.dll`, а рядом с ней **не
обнаружены** `BUILDINFO.json`, `SHA256SUMS.txt`,
`VirtualCarControl.exe`, `virtualcar.ini`. Это
**не доказательство** отсутствия исходной сборки,
её неправильной установки или чужого происхождения:
бинарник мог быть переименован, конфигурация
может находиться отдельно, а каталог может быть
результатом ручного копирования.

Совокупный статус происхождения: **UNATTRIBUTED**
(до этого 3/3 известных M3-строк отсутствовали,
3/3 известных proxy-строк отсутствовали, стандартные
exports 14/14). Ранее найденные исторические успешные
J2534 вызовы и 119 завершённых B9FB нельзя присвоить
этой DLL.

**Практический следующий gate:** проверить наличие
достоверного пакета `VirtualCarJ2534.dll` и
`BUILDINFO.json` в контролируемой изолированной
лабораторной VM, либо в локальных собственных
архивах, **только по именам/наличию и размеру**,
без запуска и без установки. Не перечислять чужие
приватные пути или другие файловые имена. Не
менять J2534 registry и не делать вывод об успешном
CEM identity по имеющимся историческим журналам.

## Owner local file inventory: 24 named VirtualCarJ2534.dll (2026-11-08)

The owner ran a **read-only** local inventory of exact-name
`VirtualCarJ2534.dll` files under their own Downloads, Desktop and
Documents folders. Only sanitized metadata was printed. Results:

- **24** named DLL copies, modified **2026-11-01 to 2026-11-03 UTC**;
  sizes **59–71.5 KiB**.
- All **24** were found with adjacent `virtualcar.ini`.
- **9** had an adjacent `VirtualCarControl.exe`.
- **4** had an adjacent `BUILDINFO.json`. Those four include two
  copies dated Nov 3 (71.5 KiB and 70.5 KiB), and Nov 2
  (65 KiB and 66 KiB), all with the control EXE and INI.
  No private filenames beyond these standard names, paths,
  VIN, INI content or hashes were exported.
- The independently registered **9.5 KiB x86 DLL** is named
  neither `VirtualCarJ2534.dll` nor `VirtualCarJ2534Cpp.dll`;
  it remains un-attributed. It must **not** be conflated
  with the 24 archive/extracted DLL copies or with the
  historical logged sessions.

**Interpretation:** candidate lab bundles clearly exist on this
Windows, but timestamp and size are insufficient to conclude
build ancestry, functional status or client acceptance.
`BUILDINFO.json` may help establish commit provenance;
do not print arbitrary raw metadata, URLs, machine paths,
private profile values or all file hashes.

**Next owner-local read-only gate:** compute SHA256 **only
locally** to group same-content DLLs by ordinal `BinaryGroup`,
without displaying hash values, using exact-name DLL matches;
also show counts of candidates grouped by size and the
presence of `BUILDINFO.json`, `VirtualCarControl.exe`,
`virtualcar.ini`. For the four `BUILDINFO.json` candidates,
inspect only the **top-level key names**, not values, first
to establish safe schema before selecting allowlisted
`commit/version` metadata. All paths and content stay local.
No `gh` downloads, no firmware/ECU interaction, no
J2534 registration edits, and no binaries/releases published.

## Owner hashes 24 candidate VirtualCarJ2534.dll copies locally (2026-11-08)

The owner has run the next read-only inventory (hashes were
used **locally only** to assign anonymous ordinal labels,
never printed or uploaded):

```text
[VirtualCar] TotalCopies=24
[VirtualCar] UniqueBinaries=11
[VirtualCar] BuildInfoCandidates:
Group SizeKiB ControlApp KnownFields
BIN7   71.5      True       architecture,version
BIN8   70.5      True       architecture,version
BIN9   65        True       architecture,version
BIN11  66        True       architecture,version
Result=OK
```

There are **11 content-distinct DLL files among 24 copies**,
and four full-looking bundles include `BUILDINFO.json`,
`VirtualCarControl.exe`, `virtualcar.ini`. These four
have top-level **discovered allowlisted** BUILDINFO
key names `architecture` and `version`; other metadata
keys or nested provenance were **not enumerated**.
Do **not** infer a commit SHA, branch, CI build identity
or newest version from file modification time, SHA256
group ordinal or size. None of these files were run,
and their association with earlier accumulated logs is
unknown. The **currently registered** 9.5 KiB x86
DLL remains a separate unattributed file.

**Next local read-only gate:** for those four candidates,
extract only top-level `architecture` and `version`
values after validating they are short, non-sensitive
plain strings, plus independently read the x86/x64
PE machine header. Report `Group`, `PEMachine`,
`Version`, `DeclaredArchitecture`; never print
paths, raw BUILDINFO, hashes or configuration. Use
the **same sorted file order and hash grouping** as
previously to preserve BIN7/8/9/11 labels.
If metadata is missing or unexpectedly complex,
report only `Unknown` rather than dumping it.
Further provenance and controlled VMware testing
will need verified build identity; no registry
modifications or physical J2534 testing now.

## Four BUILDINFO version and architecture values (owner Windows, 2026-11-08)

The owner performed read-only PE inspection and extracted strictly
allowlisted values for the four local `BUILDINFO.json` candidates:

```text
Group   PEMachine   Version                 DeclaredArchitecture
BIN7    x86         vmware-lab-2026.11.01    windows-x86-pe32
BIN8    x86         vmware-lab-2026.11.01    windows-x86-pe32
BIN9    x86         vmware-lab-2026.11.01    windows-x86-pe32
BIN11   x86         vmware-lab-2026.11.01    windows-x86-pe32
Result=OK
```

Although all four match the expected x86 architecture and use
the **same version label**, their SHA256 content groups differ.
This is **not a reason** to assume they are identical builds,
and size/mtime/anonymous group index do not establish version
ordering or success of client acceptance.

**Crucial source-schema correction**: code review of
`emulator/tools/package_vmware_lab.py` shows that the package
builder sets top-level `source_commit` from a validated 40-digit
hexadecimal input, plus `format`, `version`,
`architecture`, `profile`,
`vmware_e2e_verified=False`,
`ecu_identity_verified=False`, etc.
The previous local key-name inspection filtered only names
beginning with `commit`, `sha`, `git`, `version`,
`build`, etc., so **`source_commit` was excluded by
the regex**. Lack of this field in prior **filtered output
does NOT mean missing from the actual JSON**.

Next owner-local gate: read the four local `source_commit`
values **only if they match 40 hex digits**, printing just
the leading 12 commit SHA digits, together with BIN group,
and selected literal safety flags. This differs from
displaying SHA256 of a private binary: a source revision
identifier is needed to correlate a *specific commit*
with a known candidate package. Keep binary file hashes,
paths, ZIPs, INI and VIN private. Verify commit ancestry
against repository before selecting a candidate. No
registry edits or real vehicle testing.

## Four local packages' source_commit linked to GitHub (2026-11-08)

The owner extracted only the first 12 hex characters of
`BUILDINFO.json/source_commit` plus two verification flags for four
content-distinct bundled DLL groups. All `vmware_e2e_verified` and
`ecu_identity_verified` values were explicitly **False**:

| Binary group | GitHub source_commit prefix | Actual commit timestamp (UTC) |
|---|---|---|
| BIN7 | `14b95e036daf` | 2026-11-03 18:05:24 |
| BIN8 | `a98a9332cc3f` | 2026-11-03 10:39:03 |
| BIN9 | `a486d27c2fbb` | 2026-11-02 17:41:14 |
| BIN11 | `fbf3ec429642` | 2026-11-02 23:02:17 |

All four SHA prefixes resolve to **existing GitHub commits** in
`vorlocsev/virtualcar`. They are four distinct generated merge
commits of feature heads into the same historical base
`ac1f523a319a0d29e61d7e5ac07307446925cf16`.
Six pairwise GitHub compare checks reported **diverged**, not a
linear ancestor-descendant sequence. Consequently BIN7 is **only
the latest by commit timestamp**, not proven to contain every
change in the other candidates, not the latest branch build,
and not functionally approved.

Source-diff context: the later BIN7 merge touches research and
native CAN_PS diagnostic routing investigations. BIN8/BIN9/BIN11
include related but diverging code paths. Do not interpret
commit dates, version-label equality or file sizes as acceptance
proof.

The GitHub connector showed **zero pull-request-triggered
workflow runs** associated with each of the four merge SHAs,
and **zero separate commit statuses** for each. These endpoints
are not an exhaustive check of all possible CI events;
therefore report **no CI evidence discovered via these checks**,
not "CI never ran" or "CI failed".

**Next safe verification:** independently select the locally
BUILDINFO-bearing **BIN7** candidate (only a first candidate,
not an approved release), then check the **adjacent**
`SHA256SUMS.txt` entry for `VirtualCarJ2534.dll` using
local SHA-256, printing only booleans and group, not
expected/actual hash or paths. If there is no checksum
file or the stored hash differs, do not install or register.
A matching self-contained checksum validates package
integrity **relative to that manifest**, not authenticity,
trusted source origin, correct J2534 behavior or actual
vehicle identity. No J2534 DLL loading, client calls or
physical CAN testing at this stage.

## Owner-local BIN7 J2534 DLL manifest check (2026-11-08)

The owner selected the candidate with
`BUILDINFO.source_commit` prefix `14b95e036daf`
(the GitHub-resolvable merge commit
`14b95e036daf7c908c9da57af0609013f5305062`),
and ran a read-only local verification of its adjacent
`SHA256SUMS.txt` entry for `VirtualCarJ2534.dll`.

```text
Group              : BIN7
SourceCommit12     : 14b95e036daf
ManifestPresent    : True
DLLChecksumEntries : 1
DLLChecksumMatches : True
Result=OK
```

**Narrow conclusion:** this DLL's SHA256 matches exactly
one corresponding entry in the **local** manifest. This
supports same-package file integrity relative to the local
manifest; it does **not** authenticate package origin,
independently verify the source-to-binary build, validate the
**rest of the bundle**, J2534 functionality, CEM identity,
or historic session attribution. A locally editable manifest
could have been edited together with the binary.

The source packaging tool
`emulator/tools/package_vmware_lab.py` generates a manifest
with **14** allowlisted entries (12 copied source files,
generated `virtualcar.ini`, and generated `BUILDINFO.json`);
the manifest itself is not listed. It packages two 32-bit PE
binaries, synthetic read-only P2 config and three analyzers.
The next read-only owner-local check should validate all
**14 exact listed filenames**, compare every local hash,
and report only counts of missing, mismatched, unexpected
and duplicate manifest entries. **Do not print** filenames,
source content, raw INI, VIN, hashes, paths or raw binaries.
Do not register/execute DLL or modify registry. Only after
the complete package passes this limited integrity check
can the owner consider a controlled, rollback-ready VMware
diagnostic VM session, not physical J2534/ECU.

## Owner-local BIN7 complete 14-file manifest check (2026-11-08)

Owner completed a read-only check of all 14 expected
`VirtualCar-VMware-LAB` files in the local package whose
`BUILDINFO.source_commit` exactly matches
`14b95e036daf7c908c9da57af0609013f5305062`.
Output (names of personal files and local hashes withheld):

```text
Group              : BIN7
ExpectedEntries    : 14
ManifestEntries    : 14
InvalidEntries     : 0
DuplicateEntries   : 0
MissingEntries     : 0
MissingFiles       : 0
ChecksumMismatches : 0
UnreadableFiles    : 0
BundleChecksumOK   : True
Result=OK
```

Thus **all 14 allowlisted file hashes** match the companion
local manifest, with no missing, duplicate or malformed entries.
This validates **self-consistency against the local
SHA256SUMS.txt**, not independently signed provenance
or bitwise source-build reproducibility. The check did not
enumerate arbitrary additional files outside the manifest
and does not establish whether the current host is an
isolated VMware guest or has a snapshot.
**Never** infer J2534 client acceptance, XC90/CEM
identity or safe runtime behavior from checksums.

**Next read-only gate before considering a VM session:**
check the selected BIN7 `BUILDINFO.json` and
`virtualcar.ini` values **without displaying the raw
contents or synthetic VIN**: source commit, x86 architecture,
synthetic P2 profile label, read-only telemetry enabled,
ECUCount=1, StrictRouting=1, PassiveCAN/PassiveTrace
disabled, D2 section active fixture counts all zero,
and extra D2 node disabled. If any fail, do not proceed
to install/execute. Confirm explicitly that testing takes
place **inside a snapshot-backed, disconnected
VMware lab**, with no physical J2534 adapter or vehicle;
do not alter the current Windows' 3 existing registry
entries (two stale). When safety checks pass, any
installation/diagnostic test must be separately planned
for that isolated environment and **never automatically
published or claimed successful**.

## BIN7 SafetyPreflight: one PassiveTrace false negative (2026-11-08)

The owner ran a read-only locally reconstructed BIN7 configuration
preflight after a Python-to-PowerShell argument quoting issue and a
path-variable capture issue; the final **PowerShell-only** preflight
reported:

```text
BuildInfoValid=True
SyntheticProfileDeclared=True
SyntheticVIN=True
ECUCountOne=True
StrictRouting=True
PassiveCANDisabled=True
PassiveTraceDisabled=False
D2FixturesDisabled=True
ExtraD2NodesDisabled=True
TelemetryEnabled=True
NoVerifiedIdentityClaim=True
Result=FAIL
```

**Important correction based on source-commit inspection:** the
source `emulator/virtualcar-p2.ini` at BIN7 commit
`14b95e036daf7c908c9da57af0609013f5305062` **does
not include a `[PassiveTrace]` section**. In the exact
commit's `emulator/src/virtualcar.c`, the runtime uses
`GetPrivateProfileStringA("PassiveTrace","Enabled","0",...)`
and only activates the trace when `parse_num(v,0)==1`.
The same commit's
`emulator/tools/package_vmware_lab.py` uses
`cfg.getint("PassiveTrace", "Enabled", fallback=0)`,
which allows a missing section as **disabled**. The owner
preflight had erroneously required the literal
`[PassiveTrace] Enabled=0`, so this one failing item
is **consistent with a false-positive preflight failure**
rather than evidence of enabled trace replay.

**Caveat:** the local BIN7 `virtualcar.ini` has not yet
been independently probed to show whether the section
is indeed absent versus explicitly `Enabled=1` or
some unexpected value. Keep `SafetyPreflight` status
**NOT YET PASS** until an owner-local read-only check
distinguishes `MissingSection`, `MissingEnabledKey`,
`ExplicitZero`, `ExplicitOne`, `Unexpected` with
no raw INI, VIN or local paths printed. If missing,
treat as disabled **as runtime does**; if explicit 1
or unexpected, stop and review privately before any
DLL loading/registration/VM test. Do not alter the
14-file manifest or modify user files to force a pass.

## BIN7 PassiveTrace corrected effective state (2026-11-08)

The owner ran a **read-only** targeted check of the
`virtualcar.ini` next to their locally self-consistent
BIN7 package. Reported:

```text
[VirtualCar] BIN7 PassiveTrace Verification
PassiveTraceState  MissingSection
EffectivelyDisabled True
CorrectedSafetyCheck True
Result=OK
```

At the exact BIN7 source commit `14b95e036daf7c908c9da57af0609013f5305062`,
`emulator/src/virtualcar.c` reads PassiveTrace/Enabled with
default `"0"`, and only enables replay for parsed value 1.
Thus a missing `[PassiveTrace]` is an **effectively
disabled replay state** under this implementation.
The previous `PassiveTraceDisabled=False` reflected
an overly strict local check requiring explicit `Enabled=0`,
not an enabled trace. The other 10/11 local checks
previously returned true; with this corrected criterion,
the **static BIN7 SafetyPreflight is now 11/11 PASS**.
The local 14/14 checksum matches remain verified
relative to their companion manifest.

**Scope and next gate:** this is a **static, local profile
and package consistency** result, NOT an independent
signature check or functional J2534 validation. No ECU
or vehicle identity acceptance has been established.
The next user-side action should verify that a future
test is conducted inside the intended VMware guest
and that the guest has a snapshot plus **no physical
J2534 or USB pass-through devices**. The snapshot
and physical-disconnect state cannot be reliably
proven by guest OS heuristics; they require manual
verification from the VMware UI. Guest registry can
be inventoried read-only without revealing names,
paths or raw diagnostic data. Do not install or register
the candidate, change host keys, or run SectorV until
the VM-safety prerequisites are confirmed.

## Owner guest Windows VMware and J2534 read-only inventory (2026-11-08)

After the static BIN7 package SHA256 14/14 and corrected profile
safety 11/11 checks passed, the owner ran the read-only
guest-environment inspection:

```text
VMwareDetected  J2534Providers  VirtualCarMatches  RegistryModified
True            6               3                  False
Result=OK
```

The OS hardware strings matched VMware, and the Registry32
`HKLM\SOFTWARE\PassThruSupport.04.04` key contained six provider
subkeys, three with names resembling Virtual Car or legacy SectorV.
The output's `RegistryModified=False` was a literal field printed
by the read-only script, **not** an independent registry change audit.
These counts match an earlier local check but **do not** prove
whether it is the same Windows installation or exact DLL set
without further read-only verification.

The source `emulator/scripts/install.ps1` creates/updates
the **exact** 32-bit provider key
`SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car`, with
`FunctionLibrary` pointing to the package
`VirtualCarJ2534.dll`, `CAN=1`, `ISO15765=1`
and `MessageVersion=0x0404`. The earlier narrow inspection
did not find that exact key on the inspected Windows, and
the other three name matches previously included an
unattributed existing 9.5 KiB x86 DLL plus two paths
to nonexistent files. A **provider count is not
hardware presence or client acceptance proof**.

**Hard gate before touching any Windows registration or
executing BIN7:** in the VMware application (host-side),
manually confirm an existing snapshot/revert point and
no physical USB/J2534 adapter passthrough, nor a
connected real vehicle. The guest-side manufacturer/model
check cannot prove a snapshot or absence of physical
passthrough. Confirm that BIN7's vetted package is
available inside this VM; do not mix with the existing
unattributed x86 DLL. Retain a reversible plan for
registration that does not touch unrelated J2534 keys.
No run/installation is approved by these findings alone.

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
