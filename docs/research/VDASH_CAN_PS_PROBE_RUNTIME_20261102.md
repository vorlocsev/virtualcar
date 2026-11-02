# VDASH MY2005: фактический CAN_PS configuration probe, 02.11.2026

Задачи #37 / #4, draft PR #42. Один запуск GUI на текущей Windows,
ручной вход пользователя, автоматическое обнаружение, **без refresh**.
Профиль синтетический MY2005: один ECM, RxStart включён, passive traffic
выключен, CEM fixtures отсутствуют. VMware guest и физический адаптер не
тестировались. Raw logs, профиль, VIN, account details и screenshots вне Git.

## Происхождение и границы

| Компонент | Проверенный источник / SHA-256 |
| --- | --- |
| Исходник DLL | PR #42 HEAD `8247a5948e9ec951c5df97913b27fde892f2a7d4`, CI run [41486957920](https://github.com/vorlocsev/virtualcar/actions/runs/41486957920), artifact merge ref `dc4011a33be9ca46a1db21202f78872487d83555` |
| CI artifact | `17118f1e228372e02ff5377277b1e92a7cecfb87712a2a632f927896214e0c85` |
| Реально загруженная DLL | `682b8bc482011a7ff3f0584b4564e142d8f227c931a2de7e4ff602001595f601` |
| Synthetic profile с opt-in | `cca3fc41ad09381a2c6239313466afb5c4b52b421e8015bacc276c839b2af860` |
| Frontend 2.5.115.84 | `bb9153650a736e3f03ca1a4cea265d6a5692fe1123729b3169d60f9614eea0f9` |
| Native worker | `b29b7f5e90645c9b04a12d12578a154b6ee7441c7aab1865a5e19d31277fe1aa` |

В capture один worker. Live module sample содержит тот же PID, что и все
native строки: сравнение выполнено как uint32 (native PID напечатан hex,
sample хранит decimal); значения PID не публикуются. Хеши image/DLL совпали,
sample получен внутри интервала запуска. Это прямое module binding для
единственного captured worker, а не только проверка выбранной регистрации.
Файлы GUI/worker/DLL/profile после завершения не изменились.

Исходные префиксы обоих глобальных журналов остались неизменны; извлечены
только новые полные строки, без clock-based или row-by-row join:

| Suffix | Bytes / lines | SHA-256 |
| --- | --- | --- |
| Native text | 151172 / 1326 | `43a8d25ab579670d62f03a4cccd534df75f9738e0f1dfedc18fefc53129089ae` |
| Backend JSONL | 52078 / 208 | `6d330d328547614519fa3eac37c2c62a09cebc4a30b982624d90b00d38203596` |

Зафиксированы 13 Open / 13 Close без незавершённого API-сеанса. Это повторы
внутри одного GUI invocation, не 13 независимых автомобилей или испытаний.
Подготовительный checkpoint выполнялся во время ручного входа, когда новые
строки уже появились; его нельзя называть доказательством отсутствия pre-login
I/O. Весь capture ограничен интервалом до запуска GUI — после его завершения.

## Подтверждённый следующий API-шаг

Все **27 CAN_PS Connect** на 125000 вернули OK только в configuration-only
режиме. После каждого зарегистрирован успешный SET_CONFIG:

**Parameter `0x8001` (J1962_PINS), Value `0x030B` (пара 3/11).**

Значение `0x060E` не наблюдалось. GET pin observation, rebind и ошибка pin value
также не наблюдались. Это фактический выбор клиента в этом synthetic MY2005
запуске; он не доказывает физическую коммутацию или wiring MY2009.

Затем клиент попытался использовать транспорт:

| Операция | Количество | Фактический результат probe |
| --- | ---: | --- |
| StartMsgFilter | 3 | ERR_NOT_SUPPORTED |
| WriteMsgs | 25 | ERR_NOT_SUPPORTED, write count 0 |
| StartPeriodicMsg | 25 | ERR_NOT_SUPPORTED, регистрация отсутствует |

107 probe metadata records разобраны без ошибок: 27 allocation, 27 SET pins,
3 filter, 25 write, 25 periodic rejection. Это намеренные границы probe API,
не ошибки CEM fixtures. Периодических firing markers нет; **попытки регистрации
при этом точно были**, поэтому отсутствие firing не означает отсутствия вызова.

### Первый завершённый сеанс: исходные строки suffix

| Строка | Наблюдение | Следующий шаг |
| ---: | --- | --- |
| 20 | Open | Пробы Connect |
| 24–25 | CAN_PS ch1, flags0x800, 125000 → OK | SET pins |
| 26–27 | J1962_PINS=0x030B → OK | StartMsgFilter |
| 35 / 38 | Filter → ERR_NOT_SUPPORTED | Timeout и disconnect 39–41 |
| 43–46 | CAN_PS flags0x900 → OK, снова pins0x030B → OK | Filter rejection 54, disconnect 55–57 |
| 59 | Обычный CAN/500000 → OK | Fallback к ISO15765 |
| 78 | ISO15765/500000 → OK | `7DF:3E80` 87, `7DF:0902` 97 |
| 101 / 104 | Отдельные RX start/data от 0x7E8, size4/24, VIN header490201 | Extended ISO15765 |
| 110 / 119 | ISO15765/500000 → OK, `18DB33F1:3E80` | Ещё один PS channel |
| 122–125 | CAN_PS ch2, flags0x900 → OK; pins0x030B → OK | WriteMsgs |
| 131 / 132 | Write и periodic registration → ERR_NOT_SUPPORTED | Disconnects / Close 133–137 |

Номера каналов переиспользуются после disconnect; это не одна непрерывная
линия. Все обычные TX здесь protocol6/500000. Часы разных журналов не склеены.

## Что известно о запросах, а что осталось скрыто

Зафиксировано **39 обычных app TX**, по 13 каждого: `7DF:3E80`, `7DF:0902`,
`18DB33F1:3E80`. В их области A3/A6/B9F0/B9FB/P3 не распознаны. 13 VIN-shaped
data и 13 отдельных start прошли 26 metadata checks; missing/invalid/off-route
и parse errors равны нулю.

Но это **не все попытки записи клиента**: CAN_PS guard возвращает ошибку до
`TX (app request)` и backend root. **Payload и CAN ID 25 отклонённых WriteMsgs
не записаны.** Они могли содержать другие диагностические формы; их семантика
неизвестна, они не используются как эталон чтения. Нельзя делать вывод
«VDASH не пытался обратиться к CEM» по отсутствию CEM среди 39 обычных TX.

Backend содержит 39 roots / 39 terminals, 13 sessions, 26 queued/dequeued RX,
без drops/filter drops/conflicts/invalid lines. Классы: 13 delivered,
13 unsupported, 13 unverified. DLL #42 основана на development и не включает
классификаторы/provenance draft #39: отличие от прежнего статуса suppressed
для 29-bit TesterPresent не является доказательством изменения wire behavior.
Абсолютные числа прежнего запуска с 33 Open не сравниваются как outcome rates.

## UI и вывод для следующего этапа

GUI 2.5.115.84 с brand VDASH 2.0 - Sponsored снова показал synthetic
XC90/MY2005/B8444S/P2/12.5 V, warning о недоступных ECU и пустой список
**Live datalogging by ECU**. Кнопки reset, programming, security, DTC clear и
Start live logging не нажимались. Процессы закрыты, monitor остановлен,
прежний выбор адаптера восстановлен, временная регистрация удалена.

Установлен конкретный путь клиента **Connect → J1962_PINS 3/11 → filter и/или
write/periodic**. Причина исходного предупреждения всё ещё не доказана:
probe намеренно отказывает в этих операциях и не проверяет полноценный
CAN_PS transport. Следующий содержательный результат — безопасное наблюдение
форм отклонённых PS write attempts с явной меткой rejected/not transmitted,
либо отдельно спроектированный virtual transport с pin binding. Не превращать
попытку API в успешный TX и не добавлять положительные ответы CEM.

## Восемь проверок

1. Artifact digest, actual x86 preflight, GUI/worker/DLL/profile hashes.
2. Direct module sample для единственного worker, без публикации PID.
3. Неизменные префиксы, полные suffix и все 13 Close.
4. Все 27 pin SET, правильный ParameterID, никаких догадок по baud.
5. Все 107 probe events, явные rejected filter/write/periodic.
6. 39 обычных TX / 26 RX metadata; scope excludes 25 unknown rejected writes.
7. Backend roots/terminals/queues без конфликтов; без межжурнального clock join.
8. Независимый UI outcome, восстановление состояния и отсутствие личных данных в Git.

Анализ: Connect auditor из #42; backend auditor из его CI artifact; text auditor
из PR #41 commit `c0f6484`, SHA-256
`e38170b56ec60467f5ff64bd89b4353a425f532a707d81bae010070466139233`.
Результаты анализаторов не повышают client/identity flags после наблюдения UI.
[Metadata-only summary](vdash-can-ps-probe-runtime-20261102.summary.json).
