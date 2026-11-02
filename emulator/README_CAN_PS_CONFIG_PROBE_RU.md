# CAN_PS: изолированная проверка конфигурации

Задачи #37 / #4. Это **configuration-only probe**, а не реализация CAN_PS
транспорта. По умолчанию выключен. Канал не отправляет запросы в обработчики
ECU, не принимает CAN и не выдаёт RX, даже после сохранения пары пинов.
Положительные ответы CEM и существующий B9FB replay не меняются.

## Основание этапа

В фактическом Windows-запуске VDASH с синтетическим MY2005 все 68 попыток
Connect `0x8004` /125000 были отклонены. VIN по обычному ISO15765 доставлялся,
но UI показывал предупреждение и пустой список ECU. Причинная связь между
этими фактами не доказана. Отчёт и хеши находятся в [PR #41, HEAD c0f6484](https://github.com/vorlocsev/virtualcar/blob/c0f6484f62f0cc78afb8c8b804dffd78f1363dce/docs/research/VDASH_MY2005_RUNTIME_20261102.md).
Runtime DLL там взята из draft PR #39, не из этого этапа.

Документация производителей подтверждает отдельный этап настройки PS-канала:

| Источник | Подтверждённый факт / ограничение |
| --- | --- |
| [ScanDoc, PassThruConnect](https://www.scandoc.org/en/develop/j2534/pt_connect.html), updated 11.01.2026 | PS означает переключаемые пины. Пример двух линий и их совместного использования относится к устройству производителя, а не устанавливает пины VDASH. |
| [ScanDoc, GET/SET_CONFIG](https://www.scandoc.de/en/develop/j2534/pt_ioctl_config.html), modified 11.01.2026 | ID параметра J1962_PINS — **0x8001 (32769)**; value кодирует primary/secondary pin в старшем/младшем byte. |
| [Controller Technologies, J2534 API 04.04 wrapper](https://remote.controllertech.com/downloads/J2534_API_Version_04p04_NET_Managed_Wrapper_08_14_19-0.pdf), Derek Will, 14.08.2019, pp.7–8 | После PS Connect пример задаёт пару 3/11 значением **0x030B (779)** и читает её обратно. Это пример ISO15765_PS, не запись VDASH и не подтверждение его выбора пинов. |

Исправлена путаница ID/value: прежняя allowlist телеметрии ошибочно называла
параметр **779** J1962_PINS. Теперь это **0x8001**; 779 как Parameter остаётся
неизвестным и редактируется. На стандартных CAN/ISO каналах сама legacy API
обработка не меняется: pin option всё ещё accepted_no_effect.

Оригинальные vendor HTML сохранены вне Git 02.11.2026:

| Страница | Bytes | SHA-256 |
| --- | ---: | --- |
| ScanDoc config | 40485 | `44d9107f860c8f4cb4fe5d8986efd7d6898cd5d9654e4c5e885db396f4de15d8` |
| ScanDoc connect | 27447 | `a0d20a928b996e0c5d28de9942114d5ac1ef874a8b49448e376fd83f32f6f5cd` |

PDF прочитан через web reader; прямое скачивание вернуло URLError, поэтому
хеш не указан. Чужой implementation code не переносился. Базовый стандарт
SAE J2534-2 полностью не верифицировался; соответствие ему не заявляется.

## Контракт probe-режима

В отдельном лабораторном `virtualcar.ini` рядом с DLL:

```ini
[Diagnostics]
EnableCanPsConfigProbe=1
```

Не добавлять флаг в рабочий или опубликованный профиль. Нужны новая папка,
отдельная регистрация и synthetic MY2005 профиль для следующего клиентского
испытания; этот этап сам не меняет установленную регистрацию.

- Connect `0x8004` выделяет отдельный quarantined channel с сохранённым
  ProtocolID, baud 125000/500000 и flags 0/0x100/0x800/0x900. Это не alias 5.
  Без opt-in прежний ERR_INVALID_PROTOCOL_ID. `0x8005` остаётся unsupported.
- GET_CONFIG J1962_PINS первоначально возвращает 0 — в этой модели наблюдение
  ещё не задано. SET_CONFIG сохраняет только 0x030B либо 0x060E; GET возвращает
  сохранённое значение. Это generic пары 3/11 и 6/14, а не доказанная карта P2.
- Неподдерживаемое значение — ERR_INVALID_IOCTL_VALUE; иная пара после первого
  выбора — ERR_NOT_SUPPORTED, прежняя остаётся. Повтор той же пары допустим.
  Списки конфигурации проверяются до применения, чтобы ошибка не меняла baud
  или pins частично. Pin selection не включает транспорт и не освобождает RX.
- WriteMsgs, StartMsgFilter и StartPeriodicMsg всегда ERR_NOT_SUPPORTED.
  Write count возвращается 0; output IDs не меняются. Ни backend TX root,
  ни периодическая отправка, ни ECU response не создаются.
- ReadMsgs возвращает пустой буфер/таймаут; канал исключён из passive/replay,
  ISO-TP, D2 и vehicle-bridge обработки. Disconnect/Close удаляют pin state.

Это намеренно неполный исследовательский API. Клиент может остановиться уже
на filter/config/write, не дойдя до J1962_PINS. Такой исход тоже нужно записать,
а не объявлять работу ECU или молча разрешать очередную операцию.

## Телеметрия и анализ

Новый metadata marker:

`J2534 CAN_PS config probe channel/operation/value/status (BE)`

Четыре uint32: channel, operation, allowlisted value, actual status.
Операции: 1 channel allocated, 2 SET pins, 3 GET pins, 4 write rejected,
5 filter rejected, 6 periodic rejected, 7 config rejected (invalid DATA_RATE
либо redacted unknown parameter). Неизвестное pin value редактируется
до 0. Это не CAN payload и не доказательство физической коммутации.

Существующий `tools/audit_j2534_connect.py` выводит новый раздел
`can_ps_config_probe` только при наличии marker. Он содержит фиксированные
категории/количества, без channel/PID/личных значений. Состояния разных каналов
и процессов не связываются; `state_correlation_performed=false`.
Connect OK означает лишь выделение probe-канала. Hardware pins и ECU identity
остаются неподтверждёнными. Отсутствие marker в старом отчёте не доказывает
отсутствие вызова стандартного J1962_PINS: прежняя DLL редактировала его ID.

### Отклонённые попытки без передачи

После фактического запуска добавлен отдельный marker для следующего измерения:

`J2534 CAN_PS rejected attempt channel/origin/pins/msg-protocol/shape/check/status (BE)`

Это семь uint32 (28 bytes), одна запись на отклонённый API call. Origin 1 —
WriteMsgs, 2 — StartPeriodicMsg registration, **не срабатывание таймера**.
Status остаётся ERR_NOT_SUPPORTED. Предыдущая четырёхсловная запись отказа
сохраняется; складывать её с новым marker как два TX нельзя.

В журнал попадают только фиксированные категории. Pin observation — 0/0x030B/
0x060E, declared message protocol — CAN/CAN_PS/ISO15765/other. Для одного
сообщения проверяются DataSize 5..12, CAN ID до 29 bits и узкие TxFlags:
0 для 11-bit, 0x100 для 29-bit. Иные комбинации получают причину без формы.
Zero-count и batch WriteMsgs не разыменовывают message array и не экспортируют
его размер. Null-pointer errors остаются прежними и нового marker не создают.

Каталог сравнивает full-eight-byte raw CAN envelopes; отдельная excluded SF
категория требует только полного короткого сообщения:

| Категория | Узкая форма; это не доказательство назначения ECU |
| --- | --- |
| OBD/TesterPresent | 7DF/7E0 `02 09 02` либо 7DF/18DB33F1 `02 3E 80`, padding 0 |
| D2 target40/50 | FFFFE: A3 prefix; A6 с suffix `01 00 00`; точные B9 F0/FB/FC с нулевым padding |
| P3 candidate | 726/18DA50F1: `03 22 F1` + 14/B0/A3/06/90, padding 0 |
| Excluded | CAN SF services 10/11/27/2E/31/34/36/37/85; D2 prefix FF C8. Параметры не сохраняются, как эталон чтения не используются |
| Unverified | FFFFE: D8 + семь нулей; значение/ACK/read-only статус не назначается |

Произвольные ID, operands, payload, длины, PIN/VIN не выводятся. A3/A6
параметры остаются opaque, а различие declared CAN/CAN_PS не нормализуется.
Любая форма остаётся **lexical candidate**, не разрешением передачи или
подтверждённым read-only запросом. Все прежние API отказы, no-RX, no-backend-root
и отсутствие ECU обработчиков сохраняются.

Тот же анализатор добавляет `rejected_can_ps_attempts`: число calls, категории,
порядок строк без PID/channel и outcome `rejected_not_transmitted`.
`read_only_reference_approved=false`, `ecu_response_verified=false`; состояния
не связываются. До 20000 валидных записей, затем явная ошибка вместо усечения.
Восемь дополнительных native и восемь Python групп проверяют формы, malformed
envelopes, batch/zero, origins, изоляцию, исключённые операции, тишину и legacy
поведение. Actual x86 CI использует один **synthetic**, отклонённый B9FB envelope;
его backend fixture остаётся с прежними 13 запросами.

### Форма отклонённой настройки

D8 shape не раскрывает аргументы StartMsgFilter и interval StartPeriodicMsg:
отказ probe предшествует обычному logger/validation этих API. Перед отдельным
API-outcome экспериментом добавлены два metadata marker, **с прежним отказом**:

- `J2534 CAN_PS rejected filter channel/type/protocols/sizes/flags/flow/mask/pattern/status (BE)`:
  девять uint32. Type — pass/block/flow-control/other; protocols — совпадающие
  CAN_PS/CAN/ISO15765, mixed-known либо redacted; sizes — обе ID-only, обе full
  classic CAN, одинаковые short, разные bounded либо outside catalog.
  Flags — оба0, оба0x100, mixed-known либо redacted. Flow фиксирует только
  наличие указателя: **он никогда не разыменовывается**.
- Mask/pattern bodies классифицируются только при совпадающих CAN_PS/CAN
  protocol и двух DataSize4. Mask — zero/full32/29bit/11bit/other; pattern —
  zero/11bit/29bit/outside range. FFFFFFFF является категорией битовой маски,
  а не ошибочным CAN ID. Произвольные значения/bytes не выводятся. Остальные
  тела остаются uninspected; числовые DataSize также не экспортируются.
- `J2534 CAN_PS rejected periodic channel/protocol/interval/check/status (BE)`:
  пять uint32. Protocol — фиксированная allowlist. Interval выводится только
  для 5/100/250/500/1000/2000/4000/5000/10000/60000ms; иной valid5..60000
  редактируется с отдельной меткой, invalid также редактируется.

Оба status всегда ERR_NOT_SUPPORTED. Null/invalid-channel precedence,
неизменные output IDs, no registrations/RX/backend roots сохраняются.
Старые rejected-attempt/config markers не заменяются. Анализатор добавляет
`can_ps_rejected_setup` с раздельными filter/periodic counts; periodic record
и прежний rejected-attempt record описывают один call, **не два TX**.
Source-order ограничен 20000 records; channel/PID и private bytes не выдаются.
Это аргументы API, не установленный filter, firing, wiring или ECU support.

Восемь новых native/Python групп проверяют bounded headers/body, flow pointer
без чтения, mask-vs-ID, интервалы, malformed metadata, privacy, отсутствие
регистраций и прежние API errors. Actual x86 CI добавляет synthetic rejected
PASS-filter и D8 periodic4000ms к прежнему rejected B9FB write: probe events9,
rejected attempts2, setup filter1/periodic1, прежние backend requests13.

В [ограниченном запуске setup](../docs/research/VDASH_CAN_PS_SETUP_RUNTIME_20261103.md)
на source6153297 подтверждены3 PASS_FILTER: CAN_PS/DataSize4, flow отсутствует;
два flags0 с redacted mask/11-bit pattern и один flags0x100 с zero mask/pattern.
Все5 periodic registrations запросили **1000ms**, не4000ms из сравнительного
VIDA примера. Получен прямой loaded-module path/hash binding, версия GUI85
не менялась. Supervisor остановил worker по90s deadline, увидев2 Close;
полный suffix содержит3 Open/3 Close. Warning наблюдался, ECU list до
остановки не проверен. Прежние отказы/no-RX сохранились; API-outcome
experiments остаются отдельным следующим этапом. Старые недостающие поля
других запусков задним числом не восстанавливаются.

## Восемь групп проверки

1. Default-off, opt-in Connect, ошибки и неизменные output pointers.
2. Правильный ID параметра, GET/SET и atomic validation списка.
3. Тишина до/после pin observation, отсутствие RX и backend roots.
4. Отклонение Write/filter/periodic и сохранение outputs.
5. Изоляция каналов, повтор выбора и отказ rebind.
6. Disconnect/Close/Open сбрасывают state и opt-in из профиля.
7. Строгие metadata records, минимизация данных и CLI no-overwrite.
8. Стандартные CAN/ISO и B9FB/READ128 остаются под прежними regression checks.

В [фактическом Windows-запуске MY2005](../docs/research/VDASH_CAN_PS_PROBE_RUNTIME_20261102.md)
клиент 27 раз задал J1962_PINS=0x030B, затем получал предусмотренные отказы
filter/write/periodic. Полный CAN_PS transport, VMware guest и physical J2534
не проверены. Payload/адреса прежних 25 rejected writes не сохранены и задним
числом не восстанавливаются.

В [новом длительном запуске 02–03.11](../docs/research/VDASH_CAN_PS_REJECTED_RUNTIME_20261103.md)
на source HEAD `7a41da1` и GUI **2.5.115.85** все 4022 rejected calls получили
метку `D2_D8_unverified_prefix`: 2011 writes и 2011 periodic registrations,
pins3/11, declared CAN_PS, invalid0. Это 1006 полных API-сеансов внутри одного
invocation с фоновыми повторами, не независимые тесты. ECU list пуст.
Прямого loaded-module sample в этом запуске нет; configured artifact/hash
и новые metadata records не заменяют такую проверку. Прежний warning agent
не наблюдал. Форма D8 установлена, но её смысл и условие продолжения клиента
нужно проверить отдельно; ACK/положительный CEM ответ не добавляется.
