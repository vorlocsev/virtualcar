# VDASH: происхождение доказательств и офлайн-наблюдение OBD

Проверено 02.11.2026. База: development
`ee9e2cd66d2da9ea2087605f6ea06fc4ecd2ca83`; Issue #4.
Исходное задание: [VDASH_RESEARCH_HANDOFF.md](VDASH_RESEARCH_HANDOFF.md),
добавленное commit `0db3f413bb1d2ae8d626b490d2d30859b3227890`.
SHA-256 полученного файла:
`c544044827837c9b99dd5918af96f7e4a69065d4f17330b1bee1cbea111583c7`.
Это хеш handoff, **не** хеш VDASH или исходного capture.

Результат этапа: расширен существующий офлайн-аудитор, чтобы отдельно видеть
OBD VIN, RX start и TesterPresent. Подлинные ответы CEM и обработка DLL не
изменены. Исторические утверждения handoff остаются сообщёнными результатами:
его proprietary assemblies/IL report и связь с конкретным runtime не проверены.
Продолжение ниже независимо проверяет ограниченные формы RX и порядок событий
в имеющемся частном журнале; версия клиента и результат UI всё ещё неизвестны.
Ни число восстановленных методов, ни синтетический тест не заменяют эти источники.

Новое runtime-свидетельство: [Windows GUI run MY2005, 02.11.2026](VDASH_MY2005_RUNTIME_20261102.md).
Frontend 2.5.115.84 показал синтетический XC90/B8444S/P2/MY2005, предупреждение
о недоступных ECU и пустой список ECU. Зафиксированы хеши и live module sample
одного из двух worker; 33 VIN deliveries / 66 checked metadata, но также **68
ERR_INVALID_PROTOCOL на CAN_PS/125k**. Это конкретный транспортный пробел,
не доказанная причина предупреждения. Raw/личные данные вне git; VMware guest
и физический J2534 в этом запуске не использовались.

## Локальные артефакты после PR #40 (02.11.2026)

При поиске по именам в Desktop, Downloads и Documents/ChatGPT найдена
локальная папка VDASH2. Прочитаны только файловые version resources, размеры
и SHA-256; приложения не запускались, IL и клиентский обмен не исследованы.
Это локальная копия с неизвестным источником загрузки: хеш фиксирует байты,
но сам по себе не подтверждает издателя или целостность поставки.

| Файл | Bytes | FileVersion | SHA-256 |
| --- | ---: | --- | --- |
| Frontend.exe | 12338712 | 2.5.115.84 | `bb9153650a736e3f03ca1a4cea265d6a5692fe1123729b3169d60f9614eea0f9` |
| Vdash.Frontend.exe | 198168 | 2.5.115.84 | `1e14082a2103fa18a9f959b68fe7585672f27f3c208a709faed23f7555e9ee4c` |
| Vdash.Monitor.exe | 282648 | 0.1.2.1 | `336381e05d6ce9053bfc1cbdf19bee8740ceb3e055f9c62aa84d74379e5d523c` |
| Client.Core.dll | 520216 | 1.0.0.0 | `f9b784b11b2562d3052c643f154e7e569f7dbcfb29bd3fae6d1e308b34e8c1de` |
| Core.dll | 2512920 | 1.6.176.159 | `c84ad76ccbd9d6e5f091d2403ff2720d5f68e83ed83576db255e9fc744468b12` |
| Frontend.Client.Core.dll | 1582104 | 1.0.0.0 | `897abe44a88ebcea7c0fed1e52bed0336e8fa244c966544cd50643435e5c71b2` |
| Frontend.Core.dll | 159768 | 1.0.0.0 | `3fe43c8526b71754823bc33f50d8f6039e8bba11289ce58e1348db0da231d12a` |

Frontend **2.5.115.84 отличается от 2.5.115.79** в handoff. Его токены
методов, recovered-body counts и call graph нельзя переносить на эту копию
без отдельной проверки. Имя папки VDASH2 также не доказывает соответствие
историческому runtime «2.0». Семь выбранных файлов — инвентаризация по именам,
а не подтверждение прежнего анализа семи assemblies.

В ограниченном поиске не найден исходный IL report или диагностический
capture, связанный именно с этой копией. Найденные файлы WebView2 не исследовались:
наличие browser logs не устанавливает диагностический обмен. Это не поиск
по всему компьютеру. Следующий шаг Issue #4 — получить привязанный к хешу
клиента read-only J2534 trace и UI outcome либо проверить точное условие
парсера этой версии. Причина пустого ECU list и предупреждения SectorV
остаётся недоказанной; новых ответов CEM из этой инвентаризации не следует.

## Накопленный native log: проверенные формы RX, неизвестная версия

При продолжении проверен существующий частный `SectorVVirtualCar.log`:
4 545 440 bytes, SHA-256
`febdc02c272fb15c9e8f67f3a1925cc6a06b72ed6bae368a614eac6eb8c90336`.
Raw log остаётся вне git. Его 13 162 строки с host label `vdash_u.exe`
включают 375 Open и 372 Close; это накопленный журнал нескольких запусков,
а не один полный сеанс с установленным результатом UI.

Проверены **все 382** ISO15765 metadata suffix в этом подмножестве:
каждый непосредственно следует за native delivered RX того же PID.
166 имеют `(protocol,status,size,index) = (6,2,4,0)` и ровно четыре bytes
arbitration ID; 216 — `(6,0,24,24)`, 24 bytes и header `49 02 01`.
Значения VIN не экспортировались и не проверялись. Примеры второй формы:
delivery/metadata source lines **5019/5020**, **5053/5054**, RX ID `0x7E8`.
Это независимо подтверждает отдельные start/data сообщения в данном файле;
числа 166 и 216 нельзя превращать в пары запрос/ответ или число принятых VIN.

Ни одной TX/RX context строки для этого host label нет. Поэтому 371 узкий
`09 02` request и 149 `18DB33F1:3E80` остаются в аудите с неизвестным
transport context; ни один VIN не получает `delivered` по строгой корреляции.
382 suffix помечаются `unbound_iso15765_metadata`: это отсутствие привязки,
а не доказательство испорченных RX или сбоя клиента. Повторить проверку
ограничения можно обычным `audit_j2534_discovery.py --include-obd` на исходном
файле: без контекста suffix не создаёт канал и не подтверждает запрос.
Самостоятельная проверка форм выше сравнивает соседние строки/размер bytes,
но не восстанавливает отсутствующую маршрутизацию.

Версия `vdash_u.exe`, его хеш на момент запуска и UI outcome в этих строках
не установлены. Первоначальный поиск Desktop/Downloads/Documents/ChatGPT
файл не нашёл; последующий поиск в локальном cache VDASH нашёл описанный ниже
артефакт. Подменять исторический процесс найденным Frontend 2.5.115.84 нельзя.
Эта запись не доказывает совместимость MY2009 или обнаружение CEM.

## Найденный native artifact и ограниченная хронология (продолжение)

В локальном VDASH Temp найден **`vdash_u.exe`, 1 855 256 bytes**, SHA-256
`b29b7f5e90645c9b04a12d12578a154b6ee7441c7aab1865a5e19d31277fe1aa`.
Поля FileVersion/ProductVersion пусты. Windows Authenticode на момент проверки
вернул **Valid**, signer subject `D5T5 s.r.o.`. PE header: machine `0x14C`,
optional-header magic `0x10B`, CLR directory RVA/size `0/0`. Файл не запускался;
обход защиты, извлечение ключей и восстановление IL не выполнялись.

Подтверждены текущие байты подписанного x86 PE, а не версия исторического
запуска. Совпадение basename и время файла не доказывают, что в журнале
исполнялся этот hash. Отсутствие CLR directory также не связывает его с
managed pipeline handoff: .NET method tokens нельзя непосредственно назначить
этому PE. Связь Frontend → native executor остаётся отдельным вопросом.

Наиболее полный выбранный **read-only фрагмент сравнения** имеет явные Open
и Close одного PID, исходные строки **12662..12697** файла с хешем выше.
Сохраняются исходные номера строк; timestamps и каналы не восстанавливаются.
Здесь ровно три app TX, все перечислены в таблице. Названия сообщений —
стандартные opcode/header, значения VIN и личные данные не опубликованы.

| Исходная строка | Запрос / возвращённое сообщение | Следующий наблюдаемый шаг |
| ---: | --- | --- |
| 12662 | Open marker | Connect 12664: protocol 5, flags `0x900`, baud 500000; filter 12667 type 1; timeout marker 12671 |
| 12674 | Connect marker: protocol 6, flags `0x800`, baud 500000 | TX 12676: ID `0x7DF`, `3E80`; filter 12678 type 3 |
| 12683 | TX ID `0x7DF`, `0902` | RX 12687: ID `0x7E8`, четыре bytes ID без payload |
| 12688 | Metadata предшествующего RX: `(6,2,4,0)` | Отдельный data RX 12689 |
| 12689 / 12690 | RX ID `0x7E8`, header `490201`, 24 bytes; metadata `(6,0,24,24)` | Connect 12692: protocol 6, flags `0x900`, baud 500000 |
| 12694 | TX ID `0x18DB33F1`, `3E80` | Close marker 12697 |

Между 0902 и указанными RX/следующим TX другого app TX этого PID нет.
Это **порядок источника**, а не доказанная корреляция транспортного канала
или принятия VIN клиентом. Ранний timeout 12671 предшествует 0902 и не является
таймаутом этого запроса. Connect здесь не содержит возвращённого ChannelID
или кода успешного завершения; его protocol/baud не назначаются соседнему RX.
Close не объясняет, был ли это обычный выход, отмена или ошибка клиента.

Второй аналогичный закрытый фрагмент: Open 12708 → `0x7DF:3E80` 12713 →
0902 12720 → start RX/metadata 12724/12725 → VIN-header RX/metadata 12726/12727
→ `0x18DB33F1:3E80` 12731 → Close 12735. Это повтор формы обмена,
а не независимый автомобиль/клиент или успешное обнаружение блоков.

Предел области особенно существенен: все 1 143 TX с host label `vdash_u.exe`
включают 599 `0x7DF:3E80`, 371 `0x7DF:0902`, 149 `0x18DB33F1:3E80` и
**24 остальных TX** вне выбранной allowlist. Среди остальных есть 12 сообщений
на `0x000FFFFE`; они сосредоточены в трёх других закрытых non-VIN фрагментах.
Их содержимое не используется как read-only эталон. Поэтому ноль
`recognized_d2_p3_probes` у узкого анализатора **не означает отсутствие всех
ECU-проб**. Весь накопленный host subset не объявляется read-only сеансом.

Восемь проверок применительно к выбранному фрагменту:

| Проверка | Установлено / предел вывода |
| --- | --- |
| 1. Происхождение / P2 | Частный lab log, hash и source lines известны; автомобиль/год/двигатель/CEM не установлены. Это не опубликованный authentic P2 capture. |
| 2. Транспорт | Есть Connect intent и ID/ISO metadata; нет TX/RX ChannelID. Полную карту маршрутов/baud нельзя восстановить. |
| 3. Начало | Open, три TX, два отдельных RX и Close подтверждены source order. UI outcome неизвестен. |
| 4. A3 | В выбранном фрагменте отсутствует; условие обычного режима не проверено. |
| 5. A6 | Отсутствует; состояние зажигания не определяется по VIN или напряжению. |
| 6. B9F0/B9FB | Отсутствуют; требование F0 перед FB и CEM reply не установлены. |
| 7. Другие ECU / P3 | В выбранном фрагменте только указанные три TX; другие фрагменты вне области не дают права объявить отсутствие ECU-проб глобально. |
| 8. SectorV | Для сопоставления первого отличия нужен общий запрос/состояние и точное условие клиента; в этом фрагменте их нет. Нельзя считать 3E80 причиной предупреждения SectorV. |

Следующее необходимое доказательство: один новый read-only запуск с хешами
реально загруженных client/DLL, TX/RX context каждого сообщения, lifecycle и
результатом UI. Либо воспроизводимо найденное условие продолжения конкретной
версии клиента. Эти данные нужны до изменения ответов CEM; настоящее чтение
VIN-префикса не заменяет CEM discovery.

## Проверка native ISO15765 metadata в продолжении PR #41

В существующем opt-in OBD audit suffix теперь связывается только с
непосредственно предшествующим атрибутированным ISO15765 RX того же PID.
Любая промежуточная физическая строка, другой PID или lifecycle boundary
обрывают привязку. Протокол и RxStatus сравниваются с RX context; DataSize —
с числом напечатанных bytes; ExtraDataIndex — с формой текущего native emitter:
4/0 для ID-only RxStart и size/size для data. Это проверка формата Virtual Car,
а не универсальное требование для сторонних адаптеров J2534.

Противоречивые/неполные suffix переводят транзакцию в `unverified` с
фиксированной причиной. Отсутствие suffix сохраняет прежний transport result,
но отражается в `iso15765_rx_metadata.missing_frames`; `checked_frames` и
`invalid_frames` показывают проверенные и конфликтные записи. Timestamp suffix
не сравнивается с RX context: это enqueue time и delivery time соответственно.
Вне opt-in режима прежний отчёт сохраняется.

Восемь новых synthetic групп проверяют формы start/data, противоречия полей,
malformed bytes, отсутствие, PID/channel/source-order isolation, lifecycle/EOF,
разные timestamps/wrap и privacy/default compatibility. Локально: 172 Python
tests OK, один ожидаемый native-DLL integration skip. Это офлайн-проверка;
нового VDASH/VMware/физического запуска и подтверждённого client predicate нет.

## Матрица утверждений

Обозначения: **H** — названный handoff; **S** — текущие исходники Virtual Car;
**T** — синтетические тесты этого репозитория. «Сообщено» означает, что факт
зафиксирован в H, но первичное наблюдение заново не подтверждено. Уверенность
в S/T ограничена поведением исследованного исходника/сценария.

| Утверждение | Источник / версия / тип | Степень подтверждения | Недостающее доказательство |
| --- | --- | --- | --- |
| Семь .NET assemblies, ConfuserEx AntiTamper Normal; восстановлено 55 786 из 56 665 IL bodies | H §1; VDASH portable 2.5.115.79; сообщённый static analysis | Не перепроверено; полнота IL не равна полноте протокола | Хеши assemblies, версия и воспроизводимый законный отчёт; защита/ключи здесь не исследуются |
| `Detect` token `0x0600132B` → CreateCommand → Enqueue → VddCommand.Execute | H §1; 2.5.115.79; static | Точные token/name сохранены как сообщённые | IL тела и call graph именно этой сборки |
| `VdashClient.CreateOrUpdateNonDbWr` token `0x0600038E` → ICrudMemory.CreateOrUpdateNonDbWr → CrudClient/V2ClientBase.Send | H §1; 2.5.115.79; static | Сообщено; не установлен native PassThru callsite | Точная привязка managed-вызова к исполнительному компоненту |
| Serialization/compression/encryption → HTTP PUT | H §1; 2.5.115.79; static | Сообщённый путь команд, не CAN trace | Runtime соответствие конкретной команды/результата; содержимое Data не объявлять CAN payload |
| Envelope: Status, Session, Voltage, Data, Hash | H §1; 2.5.115.79; static | Имена полей сообщены, wire-семантика неизвестна | Схема и прослеживаемое происхождение значения каждого поля |
| Status 0 Created, 1 Sent, 2 Executed, 3 Failed, 4 AllFailed, 5 GotResponse | H §1; 2.5.115.79; static | Сообщённый enum; GotResponse не приравнивается к ECU acknowledgement | Привязка состояния к J2534 RX и клиентскому результату |
| ParseData интерпретирует DataViewV2; VddDetect строит configuration/ECU result | H §1; 2.5.115.79; static | Сообщено, происхождение возвращённых данных не установлено | Соответствующие тела методов и вход результата |
| GetVin читает PreDetectResult/Volvo.Vin; GetConfig читает DetectResult.Config | H §1; 2.5.115.79; static | Сообщённое чтение сохранённых объектов; не доказательство прямой CAN передачи | Где и каким исполнителем заполнены эти объекты |
| FastDetectEcu найден stub в исследованном пути | H §1; 2.5.115.79; static | Не доказывает отсутствие других путей обнаружения | Точное тело, ветки/реализации и выбранный runtime путь |
| Очередь → внешний/service executor; B9FB handler не восстановлен | H §1; 2.5.115.79; граница static/inferred | Сообщённая граница анализа; алгоритм исполнителя неизвестен | Исполнитель и реальный transport trace. Нельзя назначить method token конкретному CAN ID |
| READ_VBATT около 12,5 V | H §2; VDASH 2.0; сообщённый lab runtime | Не перепроверено; напряжение адаптера не определяет зажигание/CEM state | Исходный журнал с границами run и версией клиента/DLL |
| OBD 09 02 → 49 02 01 + 17 bytes; упомянуты START_OF_MESSAGE и 24/24 | H §2; 2.0; runtime | Неясно, к одному или разным RX относятся status/size/index | Отдельные PASSTHRU_MSG records и RxStatus каждого |
| При EmitIsoRxStart=1 UI показал XC90 V8 MY2005, ECU list пуст | H §2; 2.0; runtime/UI | Сообщённый результат отдельного lab сценария; не MY2009 | Совпадающие client log/UI и J2534 trace; из корреляции нельзя заключить, что flag является единственной причиной |
| После VIN наблюдались CAN 18DB33F1 и 3E80 | H §2; 2.0; runtime | Сообщённая форма TesterPresent; не последовательность ECU discovery | Канал/protocol/flags/полный порядок событий и следующие запросы |
| SectorV получил 13 B9FB fragments target50, затем встретился A3 без подтверждённого ответа | H §2 и прежний [SectorV evidence](p2-public-capture-followup.md); другой клиент | Отдельное свидетельство, не VDASH command; причина normal-mode warning не доказана | Predicate точной версии SectorV или сопоставимый успешный сеанс; private operands не повторяются |
| Донор: 13 fragments, envelope 50 F9 FB, 88 payload bytes, VIN offsets 11..27; внутри есть NUL и ASCII поля | H §3; сообщённый donor analysis | Точная раскладка первичного donor capture здесь не перепроверена; bytes надо обрабатывать binary-safe | Исходная полная запись с происхождением и границами payload |
| У донорского примера XC70-like model/chassis не согласуются с синтетическим VIN | H §3; identity interpretation | Не совместимая XC90 MY2009 fixture; конкретные личные значения не повторяются | Правила формата и authentic согласованная запись; догадки о checksum запрещены |
| B9F0, B9FB, B9FC — разные запросы; обязательность F0 перед FB не доказана | H §3, S request classifier; source + inference limit | Разделение opcodes подтверждено кодом; требование порядка не установлено | Успешный полный клиентский сеанс или точное условие клиента |
| PassThruClose сам по себе не объясняет исход запуска | H §3; inference limit | Код/трасса close не содержит причины клиента | Client outcome: cancel, normal close, parser error либо mode switch |
| RxStart — отдельный ID-only RX: size4/index0; VIN data — size24/index24 | S `enqueue_status`, T native OBD test; Virtual Car, **не исторический VDASH runtime** | Подтверждено исходником и synthetic native assertions; не объединять два сообщения | Нативный CI текущего PR и реальный client run для проверки потребления |
| VIN header/length может быть доставлен, когда CEM requests в выбранном фрагменте не наблюдаются | T нового opt-in audit; synthetic VDASH 2.0-style flow | Подтверждено только synthetic scenario; результат UI остаётся unknown | Реальная связь delivered → принятие VIN → заполнение ECU list |

Публичные ссылки H на Matthews/vtl относятся к контексту донорского исследования,
а не к открытому исходному VDASH capture. Ранее проверенные ограничения этих
источников изложены в [P2 research](p2-readonly-discovery-evidence.md).
Security/PIN части не используются как эталон обычного обнаружения.

## Переиспользованная архитектура и конкретный пробел

| Компонент | Уже умеет / граница |
| --- | --- |
| [audit_j2534_discovery.py](../../emulator/tools/audit_j2534_discovery.py) | Native/legacy/VIDA parsing, channel boundaries, CEM-oriented D2/P3 probes, ISO-TP sequence, timeout/clear/close. До этапа 09 02 и 18DB33F1:3E80 не попадали в transactions. |
| [audit_j2534_connect.py](../../emulator/tools/audit_j2534_connect.py) | Exact Connect results и SET_CONFIG; различает accepted/applied. Не заменяет ECU RX evidence. |
| [audit_backend_evidence.py](../../emulator/tools/audit_backend_evidence.py) | request_id/session_id, queue/dequeue/cancel, explicit missing fixture/filter_reject. Отсутствие payload ограничивает определение неразмеченного OBD service. |
| [trace_attribution/main.go](../../trace_attribution/main.go) | Proxy schema15 read/write intervals; RX после TX трактуется как временное соседство. Это другой источник, не log emulator. |
| [import_p2_trace.py](../../emulator/tools/import_p2_trace.py) | Binary bytes, D2 shape/echo/sequence/frame bounds, redaction. Это отдельный importer; в новом аудите не создаются INI/replay outputs. Application checksum и identity не валидируются. |
| [virtualcar_test.c](../../emulator/tests/virtualcar_test.c) | Существующие synthetic native OBD/RxStart и D2 transport tests. Они не доказывают discovery реальным VDASH. |

Новый независимый анализатор не создан. В существующий discovery audit добавлен
**opt-in `--include-obd`**; вызов без флага сохраняет прежнюю схему/область анализа.
Узкая область: VIN `09 02` на 0x7DF/0x7E0, ISO15765 либо raw CAN ISO-TP, и
точная наблюдавшаяся форма `18DB33F1: 3E80`. Последняя остаётся наблюдением
запроса с подавлением positive response, не требованием ACK и не ECU discovery.

Аудит проверяет reply header/record index и длину 20 application bytes, не VIN
characters/model/year/checksum. RxStart учитывается отдельно только при явно
записанном native RxStatus и отсутствии payload. ID-only VIDA record без RxStatus
не получает такую интерпретацию. В PR #40 ExtraDataIndex оставался вне аудита;
продолжение PR #41 добавляет описанную выше проверку native suffix.

Канал, protocol/baud/адресация, очистка очереди и disconnect ограничивают
сопоставление. Один функциональный запрос связывается с первым наблюдаемым
responder, другие отмечаются off-route и не склеиваются с его ISO-TP.
`request_line`/`last_rx_line` задают порядок внутри источника, не общий clock
двух журналов. OBD `window_ms` отсчитывается от TX до последнего matched RX,
а не означает время обработки ECU. `repeat_index` считает одинаковую узкую форму/transport tuple
в process scope до нового Open/session marker; это не backend request_id.

`observed_event_markers` считает явно записанные open/connect/config/filter/
TX/RX/clear/disconnect/close markers. Число markers не равно числу всех API calls;
нативный filter descriptor не содержит channel, поэтому filter effect остаётся
`not_observed`. Для причин queue/drop используется существующий backend audit.
Без общего request_id нельзя объединять его с текстом только по времени.

| Категория | Когда допустима |
| --- | --- |
| not_observed | Не увидено в поддерживаемой области данного источника; не означает, что события не было вообще |
| no_fixture | Явное missing-profile/fixture evidence; отсутствие RX само по себе недостаточно |
| filtered | Только явный backend filter_reject/filter_drop; не вывод из наличия фильтра. Это evidence category, не новый status enum: существующий backend audit сохраняет свои counts/reason и может оставить статус unverified |
| timeout | Явное read timeout, а не close/конец файла или не блокирующий пустой read |
| partial_rx | Неполный/ошибочный transport, неверная длина/последовательность |
| delivered | Проверенная транспортная форма RX; не принятие клиентом и не identity |
| client_result_unknown | Клиентский результат не устанавливается из транспортного журнала |

## Проверяемые объяснения пустого ECU list

1. **После VIN нет наблюдаемого discovery в доступном интервале.** Проверка:
   полный журнал от Open до результата UI с подтверждёнными границами, включая
   все каналы. Наличие поздних ECU requests опровергнет объяснение отсутствием
   отправки; ноль распознанных D2/P3 probes в коротком фрагменте его не доказывает.
2. **Ответ потерян в маршруте/фильтре/очереди.** Проверка: общий backend request_id,
   route, rx_queued, filter_drop, rx_dequeued и client receive. Доказанный dequeue
   нужного ответа исключит потерю до J2534 read, но не ошибку последующего parser.
3. **Клиент отвергает содержимое или ожидает дополнительное условие.** Проверка:
   соответствующий parser/result либо сопоставимый успешный read-only capture.
   Сам PassThruClose и показанный VIN не указывают, какое поле было отвергнуто.
4. **Команду исполняет другой/внешний компонент.** Это гипотеза из сообщённого
   managed command path 2.5.115.79. Проверка: связанный command ID и подтверждённый
   callsite/trace исполнителя. Обнаружение прямого native вызова в исследуемом
   пути опровергнет предположение об исключительно внешнем исполнении.

Ни одно объяснение пока не доказано как причина исторического VDASH 2.0 результата.
Статический анализ другой версии и SectorV A3 не закрывают этот пробел.

## Fixture и восемь групп проверок

[vdash20_obd_synthetic.txt](../../emulator/tests/fixtures/vdash20_obd_synthetic.txt)
полностью создан для теста по сообщённой форме flow и текущему формату logger.
Все 17 байтов record — ASCII нули, не реальный VIN. Файл не считается captured
VDASH session; DataSize/ExtraDataIndex разнесены между двумя synthetic RX.
Дополнительный D2 тест использует существующие synthetic 13 fragments; он не
проверяет подлинность донорского layout и не создаёт positive MY2009 fixture.

[test_audit_obd_observation.py](../../emulator/tests/test_audit_obd_observation.py):

1. Разделение RxStart, VIN data и неизвестного клиентского результата.
2. Length/echo, negative/pending и явные timeout без ложной identity.
3. Каналы, 11/29-bit routes, transport/baud/addressing mismatch, TX indications.
4. Raw CAN ISO-TP sequence/duplicates/truncation, FC и другая передача.
5. Повторы, clear/disconnect/close/Open и защита от stale RX.
6. Marker counts, redaction, malformed context/bytes, отсутствие догадок о фильтре.
7. Existing D2 binary/NUL/length/sequence validators отдельно от OBD и identity.
8. VIDA, совместимость режима без флага, CLI и отказ перезаписи входа/выхода.

Локальный полный Python suite: 164 tests, OK, один ожидаемый пропуск host native
DLL integration. Точный PR HEAD и CI фиксируются в PR, результаты старого SHA
не заменяют проверку нового. C/Go/DLL не меняются; их интеграционные проверки
выполняет текущий CI. Новых VDASH/VMware/физических J2534 запусков нет.
Для опубликованного VIDA prefix из предыдущего исследования default JSON целиком
совпал с базой: 14 transactions, 11 delivered, 3 negative_response. Это проверка
совместимости анализатора, не новая диагностика машины.

Пример только локального чтения:

```powershell
py -3 emulator/tools/audit_j2534_discovery.py PRIVATE.log --include-obd --output NEW-audit.json
```

Приватный input остаётся локально; output создаётся новым файлом. В JSON нет
payload, VIN, PID, host/path или HTTP Data. Никаких ECU responses, security,
programming, сетевого исполнения команд, расшифровки или изменения registration.
PR направляется в development и оставляется для review согласно VDASH handoff;
main, Dvinholm и опубликованный prerelease не затрагиваются.
