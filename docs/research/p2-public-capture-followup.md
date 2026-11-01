# P2: дополнительные публичные источники и границы вывода SectorV

Проверено 02.11.2026. База development: `625b09a` (PR #31). Связано с Issue #4.
После уточнения пользователя поиск продолжен по опубликованным данным.
Изменений эмулятора и нового VMware-сеанса в этом этапе нет.

## Что удалось установить

Подходящего непрерывного успешного P2 discovery capture среди новых проверенных
материалов не установлено. Найдены два авторских источника с MY2009 P2, но без
нужной последовательности CEM. Доступный файл CANLogger содержит 41 761 строку,
однако проверяемых диагностических IDs в нём нет, а происхождение файла не
установлено. Название проекта, working-code claim и synthetic test не заменяют
запись автомобиля.

Отдельно изучен приватный журнал клиента от уже выполненного MY2005 run PR #30.
Он показывает, что один B9FB/VIN read прошёл matcher клиента (13 observed,
13 matched, 0 ignored), затем автоматическая идентификация остановилась на
Hardware с no-reply. Это более точная граница раннего отказа, чем только DLL
transport delivery. Точное условие последующего UI warning об обычном режиме
в этом журнале отсутствует; эти два результата не объединяются в одну доказанную
причину.

## Дополнительная таблица источников

Commit в ссылке фиксирует просмотренную версию. Даты, размеры и SHA-256 полученных
файлов сохранены в [общем manifest](p2-readonly-source-manifest.json); raw источники
в Git не копируются. В manifest теперь 36 файлов, из них 20 добавлены в этом этапе.

| Источник | Происхождение / условия | Что принято за evidence |
| --- | --- | --- |
| [VolvoDiagToolkit](https://github.com/MarvinParanoid/VolvoDiagToolkit/tree/9a5884cc45998702d35faaa95df32784b2d349d7), 05.08.2026 | Автор: V50 MY2007 D4164T, VXDIAG J2534; P1. Есть fake driver и synthetic dashboard | Реальная P1 reference-car заявлена автором; это не P2 capture. Fixtures и definitions не перенесены в эмулятор. |
| [volvo-p2-diagnostics](https://github.com/h3llo0p3rator/volvo-p2-diagnostics/tree/77bb3c18e6518ca62d93f7e6fdba84a786162aa4), 18.10.2026 | README описывает локальную UI shell. HARDWARE_TEST_RESULTS прямо сообщает, что PassThru и vehicle requests не выполнялись | P2 название не означает успешную диагностику. Simulated adapter/sample rows исключены из реальных сеансов. |
| [P2DiCETools](https://github.com/Trent175/P2DiCETools/tree/25b2902c1df18352f91546634edc2057a859cd77), 01.09.2026 | DiCE/J2534 source; автомобиль, год, двигатель, CEM и условия не приведены | В дереве 14 файлов, код/проект/README/LICENSE; исходного capture нет. В полученном списке issues — 0. Код не выполнялся. |
| [VolvoCANBUS](https://github.com/waal70/VolvoCANBUS/tree/5b7c9a60c65ecf2d5cfa78cf18beabf8e5c7ae14), 14.01.2026 | Автор: S60 MY2009, точный двигатель/CEM не названы; Raspberry Pi 3B + PiCAN2, can-utils, ключ II, HS500/LS125 | Релевантный MY2009 P2 контекст, но в просмотренном дереве нет непрерывной discovery трассы. Эти параметры не объявляются доказанными для XC90 V8. |
| [V-Link](https://github.com/BoostedMoose/v-link/tree/6e5d225e3c8ff87aab01cc83a6b422da1d07d217), 09.09.2025 | Raspberry Pi + собственный HAT; цель infotainment/live data; точная машина для выбранного файла неизвестна | `backend/dev/lin_test.txt` относится к другому формату; не принят за CAN/J2534 discovery. README ссылается на другие проекты, не добавляя независимый CEM capture. GPL code не копировался в Virtual Car. |
| [ESP32 car tool](https://github.com/cozadizzle/esp32-car-tool/tree/7eaee2d07bbdac706f496eb4ae5c653d489b7878), 12.06.2026 | README говорит о C70 MY2001, а DBC именован 2000; также есть Honda/bench/emulation части. Логи сохраняются на устройстве | В просмотренном дереве нет подходящего P2 CEM discovery файла. Vehicle-specific control/security/replay разделы исключены. |
| [DDFE](https://github.com/Vaizer/DDFE/tree/4749c5f1223ff8d8a4848b41a409229b6c5c561f), 24.12.2025 | Авторская конфигурация V70XC MY2001 B5244T, automatic; Arduino/MCP2515; есть заявления о других MY | Sketch/parameter mapping и DIM output, без непрерывного обнаружения CEM в текущем дереве. Заявление о работе не считается RX capture. |
| [P2 informer](https://github.com/drpioneer/Volvo-P2-informer/tree/9cd3a6f603915e074ac28c73eccec6b7473e8297), 26.05.2026 | Автор называет испытание XC90 MY2011 2.5T; Arduino Nano + 2 MCP2515. Есть идеи других авторов | Не XC90 V8 MY2009; sketches не являются журналом discovery. Проект связан с DDFE, не независимый источник всех параметров. |
| [volvodiag](https://github.com/Theralley/volvodiag/tree/ac904bf88092b3545fc7881a11ce88e406e397b4), 01.11.2026 | Заявленная цель: XC70 MY2005 2.5T AWD manual, ELM327, диагностика DEM после замены | README прямо указывает: car scans local/gitignored. В `captures/` только README. Simulator/selftests и clear-DTC операции не приняты за реальные read-only сеансы CEM. |
| [CANLogger](https://github.com/olegel/CANLogger/tree/630049469d907a20903533a85b71ed44468871ac), 28.05.2019 | Arduino/CAN-USB logging; README отмечает, что baud setting игнорируется. README ссылается на авторский XC90 blog, но привязка sample к машине не дана | `Samples/big.logdata` — доступный, но неатрибутированный sample. Отдельный `error.logdata` не считается ответом ECU. Авторская blog-страница оказалась недоступна; её содержимое не восстановлено догадками. |
| [moosesnif](https://github.com/najnesnaj/moosesnif/tree/bdedb6ec472dc86035a370942c8c4339ca2f9372), 16.10.2024 | Автор прямо называет Volvo P1/V50 и STM32 ECU simulation | Не P2. B9F0, которым отвечает микроконтроллер, не является подлинным ответом CEM. Это источник ранее рассмотренной документации Jan Jansen, не новая независимая трасса. |
| [XC90 MY2009: Identify Yourself](https://hackingvolvoxc90.blogspot.com/2018/01/identify-yourself.html), [Hardware](https://hackingvolvoxc90.blogspot.com/2018/01/the-hardware.html), [Day 0](https://hackingvolvoxc90.blogspot.com/2018/01/day-0-beginning.html), январь 2018 | Владелец заявляет XC90 MY2009; двигатель/CEM variant не указаны; Arduino Uno + Seeed MCP2515, LS125, Realterm. В тексте есть CEM40/50 и диагностический ID 0x00800003 | Ближе по MY, но это описание адресов и несколько пассивных кадров. Полной пары A3/A6/B9F0/B9FB и результата диагностического клиента нет. Комментарии про HS reply ID и другие MY не превращены в fixture. В других экспериментах автор использовал dummy data; такие примеры не смешиваются с реальной шиной. |

Просмотрены списки issues VolvoCANBUS/P2DiCETools/V-Link: подходящих вложений
в выбранных issue bodies не установлено. Это не аудит всех исторических веток,
релизов, комментариев или всего интернета. Недоступные страницы и бинарные
инструменты не запускались и не принимались за capture.

## CANLogger: проверка формата до анализа

Файл: `Samples/big.logdata`, commit
`630049469d907a20903533a85b71ed44468871ac`, 1 294 591 bytes,
SHA-256 `c3a4d35c082719ebfe2bed49986b0babc37510cc247ea23d9fdb35f40450643a`.

Он не является SavvyCAN CSV. Проведена отдельная строгая инвентаризация:
строка `T` + 8 hex ID + DLC (0…8) + 2×DLC hex payload + 4 hex suffix;
CAN ID должен помещаться в 29 bit. Приняты 41 761 строка, invalid=0,
27 уникальных CAN IDs. Единица suffix, wrap, wall clock, baud, bus/channel
и направление TX/RX не назначались. Программа FileLogger сохраняет RawText;
это не даёт отсутствующую информацию о происхождении sample.

В файле нет ни одной записи с ID из набора:
`0x000FFFFE`, `0x00800003`, `0x01000003`, `0x01200003`, `0x726`, `0x18DA50F1`.
Следовательно, в выбранном файле нет наблюдаемого D2 discovery запроса на
0x000FFFFE; из этого не следует отсутствие диагностики в других файлах/сеансах.

`analyze_can_csv.py` поддерживает другой формат, поэтому raw `.logdata` ему
не подавался и timestamps для конверсии не выдумывались. Воспроизводимый пробел
поддержки формата: первая строка указанного pinned файла —
`T0240162A8E0100040070019004337`. `csv.DictReader` получает одно поле вместо
обязательных headers `Time Stamp`, `ID`, `Extended`, `Bus`, `LEN`; проверка
в `analyze()` отклоняет такой вход с `CSV requires Time Stamp,ID,Extended,Bus,LEN headers`.
Поле `Dir` в CSV-анализаторе необязательное и без значения остаётся `unknown`.
Это ограничение формата, не найденный дефект эмулятора и не основание писать
новый replay/importer для sample без provenance.

## Отдельное локальное свидетельство: этапы клиента

Источник — приватный `sectorv.log` уже выполненного MY2005 run PR #30,
сверенный с его сохранёнными границами text/backend. Source hashes сохранены
только локально; файл не менялся. Шесть упоминаний пути испытанной PR30 DLL
согласуются с ранее проверенной загрузкой этого артефакта; сами упоминания пути
не подтверждают SHA-256 DLL. VIN, host names, paths,
A3 operands, PIN-log и сырые строки не включены в Git.

| Наблюдение | Подтверждение | Что это не доказывает |
| --- | --- | --- |
| Клиентский matcher VIN получил 13 frames target50, matched=13, ignored=0 | Прямое поле client log; в соответствующей части backend B9FB50 доставлен 13 кадрами | Authenticity VIN/ECU identity и принятие всех трёх B9FB replay не установлены |
| Hardware CAN target50/500k и target40/125k подключились с status=0 после CAN_PS fallback | Прямой client log; unsupported CAN_PS не остановил fallback | Не доказывает поддержку остальных протоколов/шины физического автомобиля |
| Hardware-session на обоих маршрутах: observed=0, ignored=0, matched=0; elapsed=5000/5001 ms, затем Hardware TimeoutException | Прямое client log событие | Не является условием UI warning normal-mode и не раскрывает ожидаемый ответ |
| TX 7/8 — A3 target50/40 без RX; между TX 5077.849 ms | Сохранённый text/backend; порядок/маршрут согласуются с Hardware попытками | В client log нет общего request ID; wall clock приложения и QPC не склеивались |
| TX 13 после A6/1A04 и закрытия сообщения о зажигании снова A3 target50; operands совпадают с предыдущими A3 | Text run + ранее наблюдавшийся UI порядок. Сравнение выполнено без вывода operands | Не доказывает accepted E3 bytes, таймаут или normal-mode predicate. Начало TX на другом channel через 403.819 ms не объявляется дедлайном A3 |
| В main client log нет сообщения/предиката normal-mode preparation | Проверка отдельного текущего запуска; UI warning известен из PR #30 | Отсутствие записи не означает отсутствие внутренней проверки |

Таким образом, ранний Hardware отказ локализован как отсутствие наблюдаемого
ответа после успешного VIN matcher. Связь с A3 согласуется с порядком и маршрутами,
но конкретный accepted-response predicate для ordinary preparation не доказан.
A3/Security Access не используется как эталон read-only ответа; положительный
E3 не добавляется по этому выводу.

## Восемь проверок этого этапа

1. Происхождение: реальные author claims отделены от P1, UI shell и simulations.
2. Версии: pinned commits/даты, сохранённые HTML bytes и 36 проверенных SHA-256.
3. Формат: .logdata валидирован отдельно от CSV/J2534; параметры не угадывались.
4. Диагностический маршрут: проверены конкретные IDs в 41 761 records, результат 0.
5. Успешная последовательность: working-code claims и passive snippets не выданы за полный scan.
6. Клиентский результат: frame matcher acceptance отделён от ECU identity/normal-mode gate.
7. Изоляция запусков/часов: использован PR30 suffix; QPC не превращён в отсутствующий wall clock.
8. Граница исправления: не установлены новые совместимые CEM response bytes; код DLL не меняется.

Следующий требуемый материал остаётся конкретным: опубликованный успешный P2
read-only запуск с connect metadata, всеми запросами/ответами и переходом клиента
через Hardware и normal-mode preparation. Отдельный E6 или адрес CEM не заменяет
такую запись. До этого не повторять неизменённый VMware scan и не придумывать ACK.
