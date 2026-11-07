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
изменены. Исторические VDASH observations остаются сообщёнными результатами:
в этом этапе исходные proprietary assemblies/IL report и конкретный runtime
capture не исследованы. Handoff не задаёт их проверяемые хеши/пути.
Ни число восстановленных методов, ни синтетический тест не заменяют эти источники.

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
не получает такую интерпретацию. ExtraDataIndex здесь не валидируется;
сценарии 4/0 и 24/24 проверяются существующими native tests.

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
