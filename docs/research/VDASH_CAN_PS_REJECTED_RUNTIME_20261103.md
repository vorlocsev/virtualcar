# VDASH MY2005: формы отклонённых CAN_PS попыток, 02–03.11.2026

Задачи #37 / #4, PR #42. Новая инструментированная DLL классифицировала
**4022 отклонённых API calls**: 2011 WriteMsgs и 2011 StartPeriodicMsg
registration. Все получили одну узкую метку **D2_D8_unverified_prefix**.
Она означает только CAN ID FFFFE и восемь bytes D8 + семь нулей в разрешённой
форме raw CAN. Эти calls не создали передачи, periodic registration, RX или
ответа ECU.
Роль D8 в этой версии клиента, требование ответа и причинная связь с
обнаружением не установлены.

## Происхождение и границы

| Компонент | Проверенный источник / SHA-256 |
| --- | --- |
| Исходник DLL | PR #42 `7a41da141df17c935fd80b76cea32976f1c64637` |
| CI | [Emulator/native x86 41493503068](https://github.com/vorlocsev/virtualcar/actions/runs/41493503068) и [VMware LAB 41493503105](https://github.com/vorlocsev/virtualcar/actions/runs/41493503105): success; публикация prerelease skipped |
| Artifact build ref | `a486d27c2fbb2a57d6093c316e3ff3100ae4d052`, PR merge ref, не source HEAD |
| Artifact archive | ID 13165466500, `2d3cf1e9cfd6cc9c9872d199130a8c086ce3b886f3ff8288f234450ccda88407` |
| DLL в отдельной регистрации | `9693b8d2c49ec02b888f1ce5d91bee3cb7dcf5ef272c39e8e6d6ab2a20580524` |
| Synthetic MY2005 profile | `cca3fc41ad09381a2c6239313466afb5c4b52b421e8015bacc276c839b2af860` |
| Frontend после запуска, file/UI version 2.5.115.85 | `eed3f62e84dbaf295f9225c8b82f043bd25d61fea74209e4b5c31c8a2d843ea8` |
| Native worker | `b29b7f5e90645c9b04a12d12578a154b6ee7441c7aab1865a5e19d31277fe1aa` |

Outer/inner archive checksums и все SHA256SUMS entries проверены до подготовки
регистрации. DLL/profile после запуска не изменились. Профиль тот же, что в
[прежнем probe run](VDASH_CAN_PS_PROBE_RUNTIME_20261102.md): synthetic MY2005,
один ECM, RxStart, telemetry и opt-in включены, CEM fixtures/passive выключены.
VMware guest и физический J2534 не использовались.

Подготовительный хеш Frontend ещё был прежним 2.5.115.84
`bb9153650a736e3f03ca1a4cea265d6a5692fe1123729b3169d60f9614eea0f9`.
После открытия приложение показало release notes и Login версии 2.5.115.85;
рабочее окно и файл подтвердили новую версию/хеш. Механизм изменения файла
не устанавливался. Worker hash остался прежним. Это отдельное наблюдение
новой версии, а не повтор того же 2.5.115.84 клиента. Подлинность клиента
по издательскому каналу этим исследованием не подтверждается.

**Прямой module sample получить не удалось.** Первый 64-bit watcher и
последующий 32-bit watcher не увидели загруженную DLL; второй включён уже
после начального обнаружения. Это не доказательство отсутствия загрузки.
Имеются configured library/hash, новое уникальное metadata instrumentation
и совпадающий профиль, но нет прямой связи loaded module → captured worker.
Хеш зарегистрированного файла не следует называть хешем реально загруженной
DLL. Прежний успешный module sample сюда не переносится.

Один GUI invocation оставался открыт между сообщениями и продолжал фоновые
повторы. Окно подготовки/восстановления: 02.11 17:44:14Z–22:37:49Z
(20:44 02.11–01:37 03.11 Europe/Moscow). Эти внешние границы не назначаются
timestamps CAN-кадров. Захват содержит **1006 Open / 1006 Close**, а не 1006
независимых машин или ручных scans. Agent не запускал refresh/Start logging.

| Полный suffix | Bytes / lines | SHA-256 |
| --- | --- | --- |
| Native text | 12176524 / 103655 | `a5f1becdc7098a5bb463f538fe7b7bdbe7138147c79262089630fa70a3af44bd` |
| Backend JSONL | 4030036 / 16096 | `2bdb0712bbba3cfb6ab91ea6f9e4699056b3079213e856d68c65cd84525506e0` |

Оба прежних префикса подтверждены SHA-256 без изменения. Raw suffix,
профиль, VIN, screenshots и account data остаются вне Git.

## Что классифицировано

| Наблюдение | Calls/events | Подтверждённая граница |
| --- | ---: | --- |
| PS Connect/125000 OK | 2013 | Только configuration-only channel allocation |
| PS J1962_PINS SET 0x030B OK | 2013 | Pin observation 3/11, не физическая коммутация |
| StartMsgFilter rejected | 3 | ERR_NOT_SUPPORTED |
| PS WriteMsgs rejected | 2011 | CAN_PS declaration, pins3/11, inspected raw CAN, D8-prefix, count0 |
| PS StartPeriodicMsg rejected | 2011 | Та же форма, registration call, не firing |
| Старые probe metadata | 8051 | invalid0; не складывать с новыми records как TX |
| Новые rejected metadata | 4022 | invalid0; unknown/excluded/malformed/других shapes0 |

Первый завершённый API-сеанс, source-order строки полного suffix:

| Строки | Запрос/наблюдение | Следующий наблюдаемый шаг |
| --- | --- | --- |
| 20 | Open | PS Connect |
| 24–27 | CAN_PS/125000 OK; SET pins3/11 OK | Filter rejects 35/38 |
| 43–46 | Другой PS channel; тот же pin observation | Filter reject 54 |
| 59,78 | Standard CAN/500000, затем ISO15765/500000 OK | Обычные TX |
| 87,97 | 7DF TesterPresent, затем OBD VIN request | RX start/data 101/104 |
| 110,119 | Extended ISO15765; functional TesterPresent | Ещё один PS channel |
| 122–125 | CAN_PS OK; SET pins3/11 OK | WriteMsgs |
| 131,133 | D8-prefix write и periodic registration rejected | Disconnects, Close139 |

В первом сеансе одна пара отказов; в каждом из остальных 1005 — две пары:
`4022 = 2 + 1005 × 4`. Последний сеанс занимает строки 103572–103655,
последний Close103655. Нет nested Open, unmatched Close или незавершённого
сеанса. Номера каналов переиспользуются; состояние по ним/часам не склеено.

Все новые записи имеют outcome `rejected_not_transmitted`. В области
**этих классифицированных PS calls** отсутствуют распознанные A3/A6/B9F0/
B9FB/B9FC и P3 формы. Это утверждение ограничено каталогом и захватом.
Оно не восстанавливает 25 непрозрачных отказов прежней DLL/версии клиента,
не доказывает отсутствие всех мыслимых CEM попыток и не делает D8 эталоном
read-only. Параметры excluded security/control не исследовались.

## Обычный транспорт и UI

3018 обычных app TX создали 3018 backend roots/terminals, 1006 sessions.
Text auditor наблюдает 1006 VIN requests/deliveries и 1006 точных extended
TesterPresent requests; D2/P3 recognized0, parse errors0. Backend statuses:
1006 delivered, 1006 unsupported, 1006 unverified. Эти категории из ветки
#42 нельзя сравнивать с classifier draft #39 как outcome rates.

Обычные TX — ровно по 1006 `7DF:3E80`, `7DF:0902`, `18DB33F1:3E80`,
все protocol6/500000. RX: 1006 отдельных start (protocol6/status2/size4/index0)
и 1006 data (protocol6/status0/size24/index24). Backend queued=dequeued2012,
drops/filter-drops/conflicts/invalid lines0. Это доставка виртуального
транспорта, не подтверждённая CEM identity или принятие ECU клиентом.
Все 2012 RX metadata records проверены: missing/invalid/off-route0.

GUI показал synthetic XC90/P2/B8444S/MY2005 и 12.5V. Вкладка Live datalogging
by ECU была пуста и после длительного ожидания. **Предупреждение прежнего
запуска agent здесь не наблюдал**: ручной вход уже завершился к возврату
управления; отсутствие захваченного warning не подтверждает его отсутствие.
Start, reset, security, programming и DTC clear agent не нажимал.

Нормальная кнопка Close скрыла UI, но процессы остались. После проверки
image/start time завершены только собственные Frontend/worker/monitor этого
invocation. Затем восстановлен прежний LastDevice, удалена собственная
временная регистрация; исходная PR22 регистрация не менялась. Клиентских
процессов не осталось. Main/Dvinholm и опубликованный prerelease не менялись.

## Сопоставление с опубликованными первичными источниками

| Источник / происхождение | Что поддерживает / чего не устанавливает |
| --- | --- |
| [Olaf, Success!, 01.12.2012](https://hackingvolvo.blogspot.com/2012/12/success.html), S80 MY2002, VIDA; двигатель/CEM/version/ignition для фрагмента не установлены | Автор наблюдал FFFFE/D8 с нулями каждые 1–5s и предположил keepalive. Это рассказ о реальном P2 опыте, без полного startup capture или D8 RX. Не XC90 MY2009. |
| [Sardine Arduino 18e213a, 25.01.2015, строки610–626](https://github.com/hackingvolvo/SardineCAN-Arduino/blob/18e213ace887d045bc0ba7aa57e55d5f87123934/sardine.ino#L610), [таймер935–940](https://github.com/hackingvolvo/SardineCAN-Arduino/blob/18e213ace887d045bc0ba7aa57e55d5f87123934/sardine.ino#L935) | Авторский код firmware0.4alpha формирует точный extended FFFFE/DLC8 D8 и отправляет по таймеру без ожидания RX. По умолчанию таймер выключен. Это код, не capture; тот же автор, что блог, не независимый успешный сеанс. |
| [Sardine Win32 b87e397, интерфейс62–67](https://github.com/hackingvolvo/SardineCAN-Win32/blob/b87e3974f8b93f0b8268b50c0af15c558dcc9b73/ARDUINO-DLL-COMM.txt#L62) | Документирован тот же кадр и задаваемый период. Подтверждает интерфейс инструмента, не условие ECU. |
| [spnda d2.py e2f8ee1, 15.10.2026, строки20–21](https://github.com/spnda/volvo_vida_db/blob/e2f8ee165e373360d7f7fd0e80298f68c25bc07e/scripts/d2.py#L20), [38–39](https://github.com/spnda/volvo_vida_db/blob/e2f8ee165e373360d7f7fd0e80298f68c25bc07e/scripts/d2.py#L38) | Автор связывает точный D8/4000ms с VIDA DiagnosticSessionKeeper, контекст VIDA2014D. Это реконструкция ПО; автомобиль/год/CEM/адаптер/зажигание не установлены, vehicle capture отсутствует. |
| [andreas80, 05.04.2010, #396615](https://www.jagrullar.se/forum/viewtopic.php?f=19&start=40&t=48773#p396615), ранее проверенный [ECM fragment](p2-public-capture-followup.md) | D8 предшествует AE11→EE11. Ответ относится к ECM read, не D8. Нет времени кадров, Connect или UI outcome; контекст V70n-00/VCT2000 из соседних сообщений не доказывает происхождение каждой строки. Не CEM MY2009. |

У Sardine [send_CAN_msg315/335](https://github.com/hackingvolvo/SardineCAN-Arduino/blob/18e213ace887d045bc0ba7aa57e55d5f87123934/sardine.ino#L315)
сообщает постановку в MCP2515 TX buffer, не подтверждённую доставку CAN/ECU.
У spnda [98 и125–130](https://github.com/spnda/volvo_vida_db/blob/e2f8ee165e373360d7f7fd0e80298f68c25bc07e/scripts/d2.py#L98)
такой формат выделен как безадресный, без service payload. Общую формулу
положительного service response нельзя переносить на D8. Публикации
поддерживают **гипотезу session maintenance**, но не D8 ACK, обязательность
передачи или точный predicate VDASH/SectorV.

Исходные blog/spnda хеши уже находятся в
[source manifest](p2-readonly-source-manifest.json). Добавлены два pinned
файла Sardine: 24916 bytes / SHA-256
`7d6925a063821935311171f4e56a147344737445254aa6061ef54aec6436478f`
и 4284 bytes /
`ca98d1879e7d46c67e78a62a09c9ab7c9f76e545b8b73dd582375f6f7fe7fc82`.
Файлы сохранены вне Git, implementation code не копировался. Для forum
fragment downloadable original file/hash отсутствует и не выдуман.

## Вывод и проверяемый следующий вопрос

Новая телеметрия закрыла конкретный пробел формы отклонённых API attempts:
в данном запуске это D8-prefix, а не распознанные B9FB/A3/A6/P3. Probe
намеренно отвергает передачу/filters/periodic, поэтому этот опыт не определяет
обмен, который позволяет клиенту продолжить нормальное обнаружение.

Проверяемая гипотеза: VDASH повторяет подготовку session maintenance, а
дальнейшая последовательность зависит от PS API шага, который сейчас
отклонён. Равные write/registration counts согласуются с этим, но не
доказывают причинность. Сейчас одновременно отклонены filter/write/periodic;
нельзя выбрать один из них как доказанный gate.

Подтверждением стало бы появление следующей отличающейся read-only пробы
после изолированного устранения соответствующего API отказа **без ECU RX**.
Отсутствие перехода ослабит гипотезу. Для такого отдельного этапа сначала
нужны обоснованный pin-bound virtual transport contract, read-only границы
и прямое version/module binding. Успешный VDASH startup capture или точный
predicate клиента остаются более сильным недостающим доказательством.
Новые ответы CEM и предполагаемый D8 ACK не добавляются.

## Восемь проверок

1. Source/merge refs, artifact digest, inner archive и file checksums.
2. Раздельные frontend versions/hashes и явно отсутствующий module sample.
3. Полные suffix, неизменные префиксы, 1006 завершённых API-сеансов.
4. Все pin observations; без физического wiring или clock joins.
5. Все 4022 rejected calls, раздельные origins, no-transmit/no-approval flags.
6. Обычные TX/RX и backend отдельно от отклонённых PS calls.
7. Самостоятельный UI outcome, длительный интервал и warning not observed.
8. Восстановление selection/registration, остановка собственных процессов,
   отсутствие raw/private data в PR.

Connect/backend auditors из runtime source #42. Существующий text auditor
PR #41 `c0f6484`, SHA-256
`e38170b56ec60467f5ff64bd89b4353a425f532a707d81bae010070466139233`,
применён с `--include-obd`; форматы поддержаны, новых анализаторов нет.
[Metadata-only summary](vdash-can-ps-rejected-runtime-20261103.summary.json).
