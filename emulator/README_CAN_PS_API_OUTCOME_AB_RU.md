# Virtual Car: изолированный A/B/C эксперимент CAN_PS API

Статус: экспериментальная ветка, **не полноценный CAN_PS транспорт**.
Только виртуальная J2534 DLL. Не применять к физическим адаптерам и ECU.
Не включать в Stable, main или пакеты выпуска до проверки поведения VDASH.
Происхождение: наблюдения в PR #42 и docs/research/VDASH_CAN_PS_SETUP_RUNTIME_20261103.md.

## Включение

Один режим на одну отдельную копию каталога DLL и INI; после каждого
изменения закрыть VDASH и все процессы, загружающие DLL:

```ini
[Diagnostics]
EnableCanPsConfigProbe=1
CanPsApiOutcomeMode=0
```

Допустимые значения `CanPsApiOutcomeMode`:

| Значение | A/B-тест | Что меняется | Что НЕ происходит |
| --- | --- | --- | --- |
| 0 | Контроль | Сохраняются прежние отказы фильтра, WriteMsgs, periodic | Никаких CAN_PS TX/RX |
| 1 | A, filter-only | Только наблюдаемый PASS_FILTER возвращает OK и PS-local FilterID | Фильтр не маршрутизирует RX |
| 2 | B, D8-write-only | Только одна точная D8 попытка возвращает OK, NumMsgs=1 | Нет TX, ECU-обработчика, D8 ACK |
| 3 | C, periodic-only | Только регистрация точной D8 формы на 1000 мс возвращает OK, выделяет PS-local PeriodicID | Нет firing, TX, RX |

По умолчанию режим 0. Если `EnableCanPsConfigProbe` отсутствует либо не равен
1, экспериментальная настройка полностью игнорируется. Значения вне 0..3
также отключают A/B/C.

## Узкие критерии

- Только CAN_PS `ProtocolID=0x8004`, скорость 125000 и *наблюдённая*
  конфигурация `J1962_PINS=0x030B` (пара 3/11, факт API, не физическое
  подключение).
- A: `PASS_FILTER`, ID-only маска и шаблон (`DataSize=4`),
  `ProtocolID=0x8004`, одинаковые `TxFlags=0` или `0x100`,
  указатель FlowControl отсутствует. Возвращается локальный FilterID;
  `PassThruStopMsgFilter` и `CLEAR_MSG_FILTERS` сбрасывают его.
- B: `NumMsgs=1`, `ProtocolID=0x8004`, `TxFlags=0x100`,
  `DataSize=12`, CAN ID `0x000FFFFE`, ровно
  `D8 00 00 00 00 00 00 00`. Возвращается успешный *API outcome*,
  без фактической передачи.
- C: та же точная D8 форма и интервал **1000 мс**;
  `PassThruStopPeriodicMsg` и `CLEAR_PERIODIC_MSGS` завершают
  локальную регистрацию, а `pump_periodic` исключает CAN_PS.
- Все остальные формы сохраняют исходный `ERR_NOT_SUPPORTED`.
  Нельзя распространять успех на защищённые UDS сервисы, произвольные
  D2 команды или реальные J2534 устройства.

## Метаданные и интерпретация

Новый текстовый marker:

```text
J2534 CAN_PS API-only outcome mode/operation/status (BE)
```

Содержит три 32-битных Big Endian числа: mode (1/2/3),
operation (5=filter, 4=write, 6=periodic), status (0=OK).
**Не является TX**, не содержит VIN, PIN, CAN payload либо адреса ECU.
При успешных A/B/C **не** создаётся backend `tx_received`,
не создаются `TX context`, `RX context` и `RX delivered`.

Ни одно изменение не затрагивает стандартный ISO15765 OBD VIN,
B9F0/B9FB/B9FC, обработчик CEM либо защиту от программирования.

## Правильное сравнение в VDASH

Использовать четыре отдельные папки и четыре изолированных GUI-запуска:
CONTROL (0), A (1), B (2), C (3). Снимать только новые suffix-строки
журнала после исходного размера в байтах. Проверять загруженную DLL по
module path/SHA-256, не по одной строке версии. Фиксировать версию VDASH
и профиль MY2005/MY2009. Нельзя сравнивать числа из одного накопительного
лога как независимые попытки обнаружения.

В каждом запуске фиксировать: PassThruConnect/SetConfig, фильтр,
WriteMsgs, periodic, отдельно 09 02 → 49 02 01 + 17 байт,
события после VIN, статус/список ECU в GUI, все Close. Удачный
`STATUS_NOERROR` не является доказательством связи с ECU;
положительный GUI-результат не доказывает соответствие автомобиля MY2009.

## Восемь проверок до публикации

1. Режим 0 и отсутствие opt-in сохраняют прежние ERR_NOT_SUPPORTED.
2. A разрешает только PASS_FILTER ID-only с сохранением PS-local handle.
3. B разрешает только один точный D8 вызов, модифицированные байты отклонены.
4. C разрешает только 1000 мс и поддерживает Stop/Clear handle.
5. CAN_PS не вызывает pump, ECU route, backend TX либо доставку RX.
6. Режимы независимы и не меняют обычный CAN / ISO15765.
7. Данные VIN, профили и proprietary client binaries не публикуются.
8. Отдельная Windows x86 проверка DLL/GUI и строгая provenance-связь;
   офлайн CI не объявляется подтверждением VDASH или физического адаптера.

Отчёты об исходных наблюдениях:
- `docs/research/VDASH_CAN_PS_PROBE_RUNTIME_20261102.md`
- `docs/research/VDASH_CAN_PS_REJECTED_RUNTIME_20261103.md`
- `docs/research/VDASH_CAN_PS_SETUP_RUNTIME_20261103.md`
