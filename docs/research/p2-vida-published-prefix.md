# Опубликованный VIDA UDS prefix: сравнение и поддержка формата

Проверено 02.11.2026; база `development b12a4d8`, связано с Issue #4.
Новый код меняет только offline-аудит текста. Эмулятор, профили и ответы CEM
не изменяются; нового VMware/физического сеанса нет.

## Результат и происхождение

В сохранённой боковой ветке `waal70/S60CAN: FUNK3_S80` найден
[оригинальный журнал](https://github.com/waal70/S60CAN/blob/5676f6be5f2b1544459ae38f586c0446d6b320ce/S60CAN/LiveLogs/S80_verbinding.log).
В просмотренном `master` его нет; утверждение, что он был удалён из master,
не делается. Версия зафиксирована commit
`5676f6be5f2b1544459ae38f586c0446d6b320ce` от 16.10.2016.
Сам журнал объявляет дату 17.01.2016 и VIDA2013A; часовой пояс неизвестен.
Размер 610 158 bytes, SHA-256
`9ec562aeef8f3f95dc31b358341cdb4d4de3e3cd4cb0774ab847126ccbf1ab8f`.

| Проверка происхождения | Установлено | Ограничение |
| --- | --- | --- |
| Автомобиль | [Соседний S80_olie](https://github.com/waal70/S60CAN/blob/5676f6be5f2b1544459ae38f586c0446d6b320ce/S60CAN/LiveLogs/S80_olie#L1) подписан S80 2007 Patrick | Это контекст ветки, а не независимое подтверждение автомобиля каждого файла. Двигатель, CEM variant и зажигание основного журнала не установлены; VIN не декодировался |
| Клиент/адаптер | Журнал VIDA2013A, J2534 DiCE | Версия firmware/подлинность адаптера неизвестны; serial не публикуется |
| Платформа | Наблюдается ISO15765/UDS, 11-bit, CEM request 0x726, reply 0x72E | Подлинная P2/D2 discovery запись не установлена. Метка `route=P3` аудитора означает семейство адресов проб, а не доказанную платформу машины |
| Полнота | Есть начало Read VIN, Connect, TX/RX и последующие запросы | Весь файл смешанный: далее есть RoutineControl. Не считать его целиком эталоном обычного read-only обнаружения |
| Связанные файлы | [directcompares60s80.txt](https://github.com/waal70/S60CAN/blob/5676f6be5f2b1544459ae38f586c0446d6b320ce/S60CAN/LiveLogs/directcompares60s80.txt) сопоставляет D2 ECM A6 и UDS ECM read | Это два фрагмента, без общего startup/Connect; не независимый CEM capture. README про S60 MY2009 нельзя автоматически назначить S80-журналу |

В качестве сравнительного материала использованы **строки 1–2040** оригинала.
Этот исходный prefix занимает 209 543 bytes, SHA-256
`f41635fe371aaae07f267889a06aba1b0ee6ac0c46853dd5c0af106e41184f75`;
строки выделены с сохранением исходных line endings.
Первый `31` запрос начинается на строке 2041; его и последующую часть не
использовали как эталон. Отдельный подсчёт всех raw TX в выбранном prefix:
181 запрос `22`, 10 `3E`; A3/A6/B9, Security Access, reset и programming TX
в этом prefix не обнаружены. Эти счётчики не означают 181 обнаруженный ECU.

## Наблюдаемая хронология CEM

Все времена ниже взяты из журнала; часы не объединялись с QPC локального run.
Значения ответов и идентификационные записи не копируются.

| Запрос → ответ | Маршрут / время | Следующий наблюдаемый шаг |
| --- | --- | --- |
| `22 F1 14` → `62 F1 14` | [Connect/TX/RX, строки 18–27](https://github.com/waal70/S60CAN/blob/5676f6be5f2b1544459ae38f586c0446d6b320ce/S60CAN/LiveLogs/S80_verbinding.log#L18): channel 2, protocol 0x06, flags 0, 500000; 0x726 → 0x72E. TX 11:22:59,871, RX 11:23:00,255; 384 ms | Ответ возвращён слоем VehComm, затем channel 2 отключён; на channel 3 виден следующий read |
| `22 41 1F` → `62 41 1F` | [Строки 61–68](https://github.com/waal70/S60CAN/blob/5676f6be5f2b1544459ae38f586c0446d6b320ce/S60CAN/LiveLogs/S80_verbinding.log#L61): channel 3, ISO15765/500000; 11:23:01,192 → 11:23:01,211 | После паузы наблюдаются `3E 80`, затем следующее чтение CEM. Причина паузы не восстановлена |
| `22 D1 34` → `62 D1 34` | [Строки 112–117](https://github.com/waal70/S60CAN/blob/5676f6be5f2b1544459ae38f586c0446d6b320ce/S60CAN/LiveLogs/S80_verbinding.log#L112): тот же channel 3; 19 ms | Далее `3E 80` и `22 F1 06` |
| `22 F1 06` → `62 F1 06` | [Строки 179–189](https://github.com/waal70/S60CAN/blob/5676f6be5f2b1544459ae38f586c0446d6b320ce/S60CAN/LiveLogs/S80_verbinding.log#L179): channel 3; 376 ms | Далее видны reads других адресов ECU и дополнительные reads CEM, до границы RoutineControl |

F114 RX содержит **258 UDS bytes**; F106 RX — 257. Это уже собранные сообщения
ISO15765 от J2534, не одиночные CAN frames. ID-only RX длиной четыре bytes
не содержит UDS ответа и сам по себе не доказывает доставку данных.
Наблюдаемое окно TX→RX включает клиент/драйвер/шину; оно не является требуемым
дедлайном SectorV или временем обработки ECU.

В prefix аудитор выделяет **14 CEM ReadDataByIdentifier transactions**:
11 delivered, 3 negative_response, parse_errors=0. Другие ECU видны в исходнике,
но CEM-аудитор не выдаёт их за свои CEM transactions. Принятие байтов транспортом
и запись VehComm response не доказывают готовность всех модулей или UI result.

## Сравнение с MY2005 SectorV

В точном суффиксе прежнего PR #30 есть `22 F1 14` к 0x726 по
ISO15765/500000/11-bit, RX=0 и read timeout. В опубликованном материале
соответствующая адресная проба получает `62 F1 14`. Это установленное
различие **данной UDS-пробы**, а не первая точка расхождения двух полных
сопоставимых P2 сеансов.

Источник не даёт совместимой XC90 V8 MY2009 fixture: автомобиль основного
журнала независимо не подтверждён, engine/CEM version неизвестны, payload
vehicle-specific. Он также не содержит условия продолжения SectorV.
Ранний Hardware/A3 no-reply и отдельное предупреждение normal-mode по-прежнему
нельзя объяснить только успешным F114 другого клиента. E3/ACK и содержимое
258-byte записи в эмулятор не добавлялись.

## Конкретный пробел формата и исправление

До изменения `audit_j2534_discovery.py` выдавал для этого журнала **0 transactions,
parse_errors=0**: VIDA пишет `PassThruWriteMsgs(channel,...)` отдельно от
`---> (index)` и comma bytes; аналогично для RX. Старые Virtual Car markers
этим строкам не соответствуют.

Теперь parser связывает call и packet только по тому же logged thread,
сохраняет явно объявленные channel/protocol/flags/baud и исходные часы.
Client-level `VehComm request/response` не заменяет raw TX/RX.
Пропущенный Connect оставляет protocol/baud неизвестными. Коллизия ChannelID
между разными DeviceID остаётся неоднозначной до disconnect/границы.

Поддерживаются полные comma-byte records, индексированные batches, ID-only RX,
read errors, disconnect/close/новый logsession и явно записанный CLEAR_RX_BUFFER.
При clear без channel наблюдения завершаются с неизвестным channel очистки.
Malformed/непривязанные записи не достраиваются; повреждение RX не превращается
в положительный результат. ERR_BUFFER_EMPTY при wait=0 не объявляется таймаутом.
`3E` на ISO15765 не считается raw-CAN Flow Control.
Неизвестные форматы строк не конвертируются с придуманными параметрами.
JSON whitelist и значение delivered как transport-only сохранены.

## Восемь synthetic test groups

Тесты `emulator/tests/test_audit_vida_text.py` используют только вымышленные
байты и имена; ни один captured payload не перенесён в fixtures.

1. CEM ISO15765 metadata/тайминг, длинный собранный reply, ID-only RX и отсутствие двойного счёта VehComm.
2. D2 13-frame sequence, одиночный A6/E6 и отсутствие положительного вывода для A3.
3. Потоки/каналы, 11/29-bit addressing, wrong-route RX, DeviceID collision и TesterPresent.
4. Неизвестные protocol/baud, отсутствующие timestamps и неподдержанный protocol.
5. Orphan/malformed bytes, batch indexes/counts и разрыв достоверности TX/RX.
6. Empty/timeout/device/write errors и UDS pending/final negative response.
7. Disconnect/close/session/clear/reconnect, отсутствие переноса stale reply и сохранение metadata после clear.
8. Приватность JSON, отделение client text и сохранение native/legacy format.

Базовая версия не проходит новые группы: формат VIDA не распознаётся.
После исправления полный набор: **140 Python tests OK, 1 expected native-DLL skip**
на этом хосте. Точный PR30 suffix 91 852 bytes повторно разобран: все 37 transactions,
counts и parse_errors совпадают с базой. C/native x86 и сборки проверяются CI
точного PR/merge SHA; результатов нового VMware run нет.

## Дополнительный screening реальных файлов

[Корпус S60/V70](https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering/tree/90030c213e1439c6ab163af2ea87ef7d363e4f8e)
проверен полностью по 17 CSV этой версии: S60 MY2002 B5244S2 M56; V70 D5244T M56,
папка 2003, README MY2004. Два файла из этих 17 уже проверялись ранее.
Это passive key/drive/buttons и car/ECU captures, не объявленные VIDA scans.
Firmware/иммобилайзерные разделы и содержимое security frames не используются
как эталон обычного обнаружения.

| Набор | Строки / проверка | Результат |
| --- | --- | --- |
| Все 17 P2 CSV, 74 621 847 bytes | 1 338 607 rows; существующий CSV analyzer принял 1 264 538. Откаты времени 74 067, не-classic DLC 2 | В ID column всех исходных rows, **до** time/payload фильтра, выбранных diagnostic IDs=0; invalid ID rows=0 |
| [8 volvoextradisp .trc](https://github.com/backeliten/volvoextradisp/tree/10003acbed6079bf2660be19685374ba56e5791e), 55 553 840 bytes | 1 262 578 rows; строгая отдельная проверка приняла 1 258 326, отвергла 4 252 (неполные bytes, nonhex и DLC9) | ID field прочитан во всех rows; выбранных IDs=0 до отбрасывания payload. README говорит только Volvo 2013, модель/двигатель/платформа неизвестны |

Набор IDs: 0x000FFFFE, 0x00800003, 0x01000003, 0x01200003, 0x726, 0x18DA50F1.
Вывод ограничен этим набором и pinned files. В `.trc` header `Time ID DLC Data Comment`
нет направления, канала или единицы времени; это не SavvyCAN CSV и не доказанный
PCAN trace format. Эти параметры не назначались и файлы не конвертировались.

Дополнительно просмотрены деревья 22 default-history commits SardineCAN-Win32,
14 Arduino и 44 S60CAN, а также текущие refs S60CAN (46 уникальных деревьев);
усечённых деревьев нет. В первом SardineCAN присутствуют build logs Visual Studio,
а не найденный диагностический capture. Файл S80 найден именно в боковой ветке.
Это не проверка всех forks, dangling objects или недоступных форумных вложений.

В общем [manifest](p2-readonly-source-manifest.json) теперь **63 уникальных файла**:
добавлены 23 новых capture files и четыре файла ветки S80. Все размеры/SHA-256
сверены с локальными оригиналами; raw files остаются вне Git.

Дополнительные кандидаты проверены по README и деревьям файлов, без выполнения
инструментов. Код, definitions и mock tests не приняты за автомобильные сеансы:

| Источник / просмотренный commit | Почему не эталон P2 discovery |
| --- | --- |
| [MooseShim](https://github.com/Sirse/MooseShim/tree/a3eea66c03b7246da000c08dc41c22f2a57e91b5) | J2534 shim для SDA; D2 experimental, тесты на mock, исходного vehicle capture в выбранном дереве нет |
| [Nordlink](https://github.com/ahussainNCL/volvo/tree/16a640507a14e25962854324818698603b8b62dd) | Цель V40 MY2013 D2; D2 в названии машины не доказывает диагностический протокол или принадлежность P2. Автор прямо пишет, что vehicle transport не реализован |
| [OpenMoose](https://github.com/rlinewiz/OpenMoose/tree/a652204674e732a9615c6b72c87112b7de6b11f6) | ME7 flash/read tool, logging по README не работает. Flashing/ECU dumps исключены, нормального discovery журнала нет |
| [OpenCFE](https://github.com/beckettloose/OpenCFE/tree/ac24cc05120a2e5c88fa5713103ebf2adb072346) | Establish CAN communication/test vehicle ещё не отмечено выполненным; code/console logging не vehicle trace |
| [volvo-monitor](https://github.com/lukaszradziak/volvo-monitor/tree/5d56e0e07e7eaf8a7f89349e4a1be2eb383f1c4e) | CSV CEM/ECM MY02 — parameter definitions; нет непрерывного timestamped startup с RX. Точные автомобиль/CEM/клиент выбранного capture не заявлены |
| [volvo-ddd](https://github.com/vtl/volvo-ddd/tree/127db78b959da4bcdc89ea1224c6e9852cbf3999) | Definitions/исходники, без отдельного discovery trace; security части не использованы |
| [Volscan: CEM configuration](https://volscan.tech/blog/volvo-cem-vehicle-configuration/), 28.10.2026 | Авторское описание read-only F106/P3; illustrated values и working-app claim не заменяют исходный сеанс с route/timestamps |

Новый индексированный VIDA/VXDIAG фрагмент Matthews
[сообщение 672017](https://www.matthewsvolvosite.com/forums/viewtopic.php?p=672017)
относится к неудачному S40 MY2003 запуску; страница вернула 403, оригинал/его SHA
не получены, как успешный P2 эталон не использован. В просмотренной
[Motor-Talk ветке](https://www.motor-talk.de/forum/der-can-bus-im-volvo-t4420570.html?page=8)
есть offline VIDA/activation примеры и проблемы подключения, без подходящего
непрерывного read-only обнаружения. Старый svxc.se URL из публикации Olaf вернул
404; его содержимое и вложения не восстановлены догадками.

Следующее доказательство для Issue #4 — подлинная полная P2 read-only запись
с provenance/Connect и наблюдаемым переходом клиента через normal-mode preparation
либо опубликованное точное условие SectorV. Найденный UDS prefix улучшает
сравнение и инструмент аудита, но этого условия не устанавливает.
