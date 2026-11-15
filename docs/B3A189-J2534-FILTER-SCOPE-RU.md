# B3A189 — жизненный цикл J2534 каналов и фильтров (RU)

## Назначение

В оригинальном B3A158 VIDA-seance было 28 полных Flow Control фильтров, но старый журнал не указывал канал регистрации. Нельзя из одного `pattern/flow` доказать, что соответствующий ISO15765-канал на 500 kbit/s мог принять RX. Эта правка — **только метаданные J2534**. Физического автомобиля, OEM-ответов и принятия VIN она не эмулирует.

## Формат новой строки

Отдельная запись в прежнем `SectorVVirtualCar.log`:

`[PID=XXXXXXXX PROCESS] J2534 scope <event> (BE) XX XX ...`

Всегда 32 байта, восемь целых `uint32` в формате big-endian:

| Offset | Поле | Назначение |
|---:|---|---|
| 0 | channel_id | Номер J2534 канала в процессе |
| 4 | session_hi | Старшие 32 бита монотонного номера сеанса канала |
| 8 | session_lo | Младшие 32 бита номера сеанса |
| 12 | wire_protocol | Исходный J2534 протокол (0x0006, 0x8004, 0x8005 и т. п.) |
| 16 | effective_baud | Текущая скорость канала |
| 20 | connect_flags | Флаги успешного PassThruConnect |
| 24 | filter_id | ID фильтра или 0 для события канала |
| 28 | filter_type | 1/2/3 или 0 для события канала |

События (только после успешной операции): `channel_connect`, `filter_registered`, `filter_stopped`, `filter_cleared`, `filter_disconnect`, `channel_disconnect`, `filter_device_close`, `channel_device_close`, `channel_rate_changed`.

Старые строки `PassThruStartMsgFilter type/id`, `filter mask`, `filter pattern`, `flow control`, `TX context` и `RX context` сохранены. **Новый scope не содержит VIN, сырых CAN данных, DID ответа или абсолютных путей.** Приватные значения, уже присутствующие в старом транспортном журнале, не следует публиковать.

## Состояния фильтра

* `filter_registered` открывает lifetime `(PID,channel_id,session_hi,session_lo,filter_id)`.
* `filter_stopped`, `filter_cleared`, `filter_disconnect` и `filter_device_close` закрывают lifetime.
* `channel_rate_changed` меняет эффективную скорость всех оставшихся фильтров данного сеанса.
* При `PassThruDisconnect` и `PassThruClose` закрываются все оставшиеся активные фильтры.
* Неправильный ID фильтра и отклонённые операции не генерируют успешное событие lifetime.
* Если журнал неполон, нет строки регистрации или пропущено снятие фильтра, статус должен оставаться `UNKNOWN`, а не `PASS`.

## Что подтверждают испытания

В текущей ветке добавлены **восемь детерминированных Host C проверок**: successful connect, successful Flow Control registration, rejected stop, successful stop, CLEAR_MSG_FILTERS, DATA_RATE retune, Disconnect с повторным использованным номером канала, device Close и изоляция логов от VIN. Эти тесты должны пройти на точном SHA и быть отдельно подтверждены хозяином Windows. Тесты не являются запуском оригинальной VIDA.

После локальных Python + Host C + x86 PE32 тестов потребуются новый отдельный исходный журнал VIDA и сопоставление `scope` с RX контекстом **того же канала и сеанса**. Только после этого можно обсуждать, пропускают ли реальные фильтры соответствующую пару 29-битных CAN ID. Даже совпадение фильтра не подтверждает OEM-ответ или VIDA ReadVin.

## Ограничения

- Только журналирование уже существующих API вызовов под текущей блокировкой `g_lock`. Не включать новую функциональность UDS или ISO-TP.
- Никаких изменений в установленной VIDA, DLL провайдеров, Registry32, SQL или Dvinholm.
- Не запускать Jobs и не публиковать релизы без отдельного подтверждения.
- Изменение — дополнительный слой поверх draft PR #352, который остаётся отдельной интеграционной базой.
