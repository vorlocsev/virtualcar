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

## Восемь групп проверки

1. Default-off, opt-in Connect, ошибки и неизменные output pointers.
2. Правильный ID параметра, GET/SET и atomic validation списка.
3. Тишина до/после pin observation, отсутствие RX и backend roots.
4. Отклонение Write/filter/periodic и сохранение outputs.
5. Изоляция каналов, повтор выбора и отказ rebind.
6. Disconnect/Close/Open сбрасывают state и opt-in из профиля.
7. Строгие metadata records, минимизация данных и CLI no-overwrite.
8. Стандартные CAN/ISO и B9FB/READ128 остаются под прежними regression checks.

Новый VDASH/VMware/physical run с этим probe-режимом пока не выполнен. Следующий
результат — конкретный порядок вызовов и pin value после opt-in Connect той же
версии клиента. Только затем проектировать полноценный виртуальный transport
с явным pin binding и отдельной проверкой совместимости.
