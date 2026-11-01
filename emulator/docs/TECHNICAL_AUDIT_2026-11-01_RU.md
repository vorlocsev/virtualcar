# Технический аудит Virtual Car: неполная идентификация CEM

Дата: 01.11.2026. Основание: Issue #4. Проверены AGENTS.md, NEXT_CHAT.md, действующие PR и Actions. Аудит относится к исходникам GitHub, а не к установленной ранее архивной DLL.

## Проверенные версии и границы

- `development`: **a31482ee4663f7167d0312605338d08b5a74b373**. Dev33 PR #10 слит. CI Emulator [41190595172](https://github.com/vorlocsev/virtualcar/actions/runs/41190595172) и Proxy/OneClick [41190595235](https://github.com/vorlocsev/virtualcar/actions/runs/41190595235) успешны на этом SHA.
- Dev49 находится **только в открытом draft PR #11**, HEAD **439197b64639ba1e772ed7d4b88c4ee46ba715b4**. CI Emulator [41258974781](https://github.com/vorlocsev/virtualcar/actions/runs/41258974781) успешен. Код dev49 не является частью указанного development.
- Draft PR #2 `development → main` остаётся отдельным gate. Main, Dvinholm и релизы этим аудитом не изменяются.
- Новые экспериментальные проверки — unit/host tests со стабами и существующими синтетическими данными проекта. Они не обращаются к адаптеру или ECU. Приватный INI, донорский VIN, пользовательские сырые логи и сторонние бинарники не включены.
- Нет нового подтверждённого запуска DLL этого checkout в SectorV/VDASH/VMware. Не заявляется обнаружение XC90 V8 MY2009 или физического CEM.

## Главный вывод

Подтверждён конкретный программный разрыв raw-CAN ISO-TP для **уже существующего** функционального OBD VIN-запроса `0x7DF 09/02`:

1. После First Frame от ECM код сохраняет владельцем Flow Control функциональный ID `0x7DF`, поэтому FC на физический ECM ID `0x7E0` игнорируется.
2. При стандартных двух ECU последующий существующий NRC другого узла вызывает `emit_response`, который отменяет незавершённый ответ ECM.

Это объясняет воспроизводимую неполную транспортную передачу, но ещё не доказывает, что именно этот raw-CAN путь блокирует конкретный запуск VDASH или SectorV. Оба клиента могут использовать другие маршруты и J2534 ISO15765. Для установления причин конкретного клиентского отказа нужна трасса точного нового SHA.

Отдельно подтверждено: A3/A6 не имеют готовых положительных replay-ответов, B9F0 требует подходящую настроенную фикстуру, а наличие или отсутствие P3 CEM определяется таблицей ECU. Отсутствующие проверенные ответы MY2009 не являются основанием их придумывать. Программный дефект транспорта и недостаток протокольных данных — разные категории.

## Архитектура и фактические пути

```text
SectorV / VDASH
  → J2534 registration / x86 DLL
  → PassThruWriteMsgs → observer bridge → process_request
      ├─ CAN5 + 000FFFFE → process_d2 → configured D2 frames
      ├─ CAN5 + configured ECU → ISO-TP SF → answer_uds → FF/pending/FC/CF
      └─ ISO15765=6 + configured ECU → raw UDS → reassembled J2534 RX
  → installed ID filters → per-channel RX FIFO → PassThruReadMsgs
  → client framing/identity validation (не равнозначно доставке RX)

Vehicle Core / CEM router — наблюдатель; он не создаёт ECU-ответы.
Dev49 — optional metadata JSONL + управление настройкой из существующего
VirtualCarControl.exe; не замена backend и не новый диагностический клиент.
```

`PASSTHRU_MSG` имеет шесть U32 и Data[4128]. Внутренняя RX-очередь64 не ограничивает ёмкость массива вызывающей стороны: ReadMsgs128 поддерживается существующим тестом. Очередь и pending ISO-TP хранятся на CHANNEL; фильтры сравнивают первые четыре байта CAN ID. Тип3 используется как ID-pass mask, flow-payload не реализует полноценный внешний CAN-контроллер: ISO15765 здесь возвращает собранный ответ внутри симулятора. Из зелёного теста нельзя выводить полную реализацию SAE J2534/ISO-TP.

### Диагностические команды

| Путь | Что реализовано | Что не подтверждено |
|---|---|---|
| B9FB | `virtualcar.c:process_d2`, base slots0/2; сохранён legacy13-frame replay, pacing и очистка stale D2. | Подлинность конкретного MY2009 ответа и принятие его клиентом. |
| B9F0 | Base slots1/3 и optional nodes; только настроенные, валидированные D2 кадры. | Валидность framing не гарантирует требуемые клиентом15байт аппаратной идентичности или реальность блока. |
| B9FC | Base slots4/5; дополнительный guard существующей лабораторной21-frame/142-byte конфигурации. | Guard не является универсальной OEM-спецификацией; другие формы отключаются. |
| A3/A6 | `p2_cem_router.c` классифицирует запросы как требующие evidence. | В backend нет соответствующего положительного replay-handler/loader. TX success не означает ECU reply. |
| P3 `0x726` | Обслуживается, если такой request ID находится в configured ECU table. Existing F114 lab-handler возвращает синтетические данные; это не OEM CEM identity. | Реальный MY2009 маршрут/полнота CEM-identification. |
| P3 `0x18DA50F1` | Общий configured-ECU механизм может работать с29-bit physical ID; тест проверяет только synthetic transport. | Наличие этой ECU-записи в конкретном профиле и подлинный ответ `0x18DAF150`. Автомаппинга0x726→29-bit нет. |

## Подтверждённые программные ошибки

Строки ниже привязаны к исходному `development a31482e`, либо явно к `dev49 439197b`. После патча номера могут сдвинуться. «Воспроизведено» означает выполненный host/unit experiment; «source walk» — проверенный путь кода, не испытание в VMware. В строках с несколькими проявлениями исполнением подтверждены указанные конкретные случаи.

| ID / приоритет | Файл, функция, исходные строки | Причина и воспроизведение | Уверенность / состояние |
|---|---|---|---|
| F01 / **P1** | `emulator/src/virtualcar.c`, `process_request:737,768`; `emit_response:589–591` | Raw CAN: functional09/02→FF ECM→physicalFC7E0 даёт0CF; FC7DF вместо этого выпускает2CF. При2ECU второй NRC обнуляет pending до FC. | **Высокая, воспроизведено RED. Исправлено предлагаемым focused PR.** |
| F02 / **P1** | `virtualcar.c`, `send_can_cf:577`; `PassThruReadMsgs:851–854` | Заполнить RX FIFO64, затем CTS. Выдаётся0CF, pending остаётся. После чтения64 сообщений следующая Read пуста: pump для продолжения разрешённого burst отсутствует. | Высокая, host repro; follow-up. |
| F03 / **P2** | `virtualcar.c`, `process_request:736–748` | Однобайтовый FC `30` принимается как CTS/BS0 и выпускает2CF; минимальная длина FC не проверена. | Высокая, host repro; не исправлено здесь. |
| F04 / **P2** | `virtualcar.c`, `load_config:459,469–473`; `process_d2:697,714–715` | Пустая/невалидная optional запись сохраняет target/opcode; поздняя валидная запись допускается loader. Runtime останавливается на первой с count0. Host: first_count0, later_count2, queued0; при устранении конфликта queued1/staged2. | Высокая, воспроизведено. Реально мешает configured replay. |
| F05 / **P2** | `virtualcar.c`, `PassThruIoctl:993`; `p2core/p2_j2534_bridge.c`, `p2_bridge_connect:30`, `inspect_tx:55`, `inspect_rx:74` | SET_CONFIG/DATARATE500k→125k обновляет CHANNEL, но observer остаётся500k и сообщает route_mismatch. | Высокая, воспроизведено. **Ошибка наблюдения, не управляющая replay.** |
| F06 / **P2** | `emulator/tools/audit_j2534_discovery.py`, `_request:55–58` | A3/A6 ищутся в data[0], хотя у envelope CF/CB + route service находится в data[2]. Classification-only synthetic test: wrappedA3=False, bareA3=True. | Высокая, воспроизведено. Ошибка offline evidence, не ECU. |
| F07 / **P2** | `emulator/tools/import_p2_trace.py`, `validate_response:115–116`; `virtualcar.c:validate_d2_fixture:232–234` | Importer принимает одиночный кадр с другим echoed opcode, loader отвергает. Host example: expectedFB/gotF0 → importerTrue, loaderFalse. | Высокая, воспроизведено двумя валидаторами. |
| F08 / **P1**, dev49 | `virtualcar.c`, `process_request:855`, `emit_response:680`, `backend_end_if_drained:275–282` | Длинный ответ→FF queued→FC OVERFLOW доRead. Pending удалён без drop-state, единственный FF выдан, terminal=`responded`. Host подтвердил1FF/0CF и responded. Supersede имеет тот же источник рассинхронизации. | Высокая; overflow воспроизведён. **Ложная полнота телеметрии**, не новый ECU-ответ. |
| F09 / **P2**, dev49 | `virtualcar.c`, `enqueue_status:598–605`, `backend_end_if_drained:279–282` | Заполнить FIFO→запросить SF. Frame event=`queue_full`, terminal того же RID=`filter_reject`. Хранится только один dropped_trace на канал. | Высокая; несовпадение причин воспроизведено. |
| F10 / **P2**, dev49 | `emulator/control/backend_config.go`, `locateBackendSetting:26–33`, `rewriteBackendTelemetry:65–78` | Вход BOM+`[Diagnostics]`, без ключа. Первый parser видит секцию, повторный header-search её не находит; rewrite успешно создаёт дубликат. Собственный parser отвергает результат. Аналогичный source mismatch для `[ Diagnostics ]`. | **Высокая, BOM воспроизведён Go unit test.** |
| F11 / **P2**, dev49 | `virtualcar.c`, `PassThruIoctl:1112–1120`, `Disconnect:942`, `Close:919`, `process_d2:799–800` | Queued/staged ответ→CLEAR_RX/disconnect/close либо новый D2. Удаление состояния не имеет полного drop/terminal lifecycle; оставшиеся staged кадры не объясняются counters. | Высокая, source walk; отдельный runtime lifecycle test не выполнен. |
| F12 / **P2**, dev49 | `virtualcar.c`, `next_backend_request:243–248`, `load_config:362–371`, `backend_event:255–266` | RID=PID<<32\|serial, serial сбрасывается при загрузке DLL, JSONL append-only. Повторная загрузка/повторное использование PID даёт совпадающие RID; session nonce/start/end нет. | Высокая, source walk; повторная загрузка DLL не исполнялась. |
| F13 / **P2**, dev49 | `virtualcar.c`, `process_request:883–889` | Terminal drain check вызывается внутри functional ECU loop. Если первый ответ отфильтрован, terminal dropped возникает до генерации второго; возможен ещё один terminal для того же RID. | Высокая, source walk; отдельный runtime test не выполнен. |

Не выявлено подтверждённого **P0 программного дефекта**. Issue #4 остаётся P0 задачей получения доказательств клиентского обнаружения; это не основание переименовать все неподтверждённые гипотезы в P0 bugs.

## Известные ограничения и пробелы проверки

- **STmin не моделируется**, что уже отмечено в комментарии `send_can_cf:573`. Host: запрос16ms, дваCF с одинаковыми timestamps1234000us. Это подтверждённое ограничение, но влияние на конкретный клиент не измерено; P2 для планирования.
- Один pending segmented response на канал (`emit_response:587–604`). Общий functional F190 с несколькими отвечающими ECU может замещать предыдущую передачу. Узкое исправление09/02 не обещает общий multi-responder ISO-TP; P1 follow-up/source walk.
- Dev49 periodic replay вызывает process_request без нового RID; при active_trace0 backend events подавлены (`pump_periodic:900–907`, `WriteMsgs:965–971`). Это пробел охвата metadata counters, P2.
- Dev49 пишет JSONL синхронно под глобальным g_lock: задержки/ошибки диска в Windows не измерены. Тесты принудительно включают flag и используют успешные I/O stubs; opt-out и failure paths не подтверждены.
- Новый JSONL writer не содержит прямого VIN/payload/profile path. Но legacy `%TEMP%\SectorVVirtualCar.log` продолжает писать payload независимо от включения JSONL. Обезличивание относится **только к новому потоку**; legacy log остаётся приватным.
- Наличие static handlers, successful WriteMsgs, queued RX, delivered RX, complete transport и accepted ECU identity — разные события. В этой работе принятие MY2009 identity клиентами не доказано.

## Единственное предлагаемое изменение кода

Focused PR в development: **сохранить существующий ECM VIN-ответ после функционального OBD запроса и принимать FC по физическому адресу ответившего ECU**.

В `process_request`:

1. Для functional7DF09/02 пропустить не-ECM узлы, для которых существующий `answer_uds` уже не реализует положительный09/02. Их физический запрос по-прежнему получает прежний NRC.
2. Привязать pending_request_id к `ecu->req`, а не к broadcast ID исходного запроса.

`answer_uds`, данные ответа, VIN, конфигурации ECU, D2/B9FB replay, A3/A6/B9F0 handlers не изменяются. Новых положительных ответов, программирования или Security Access нет. Unit tests встроены в существующий `emulator/tests/virtualcar_test.c`; отдельное пользовательское диагностическое приложение не создаётся.

### Восемь групп тестов изменения

| Группа | Проверяемое поведение |
|---|---|
|1|Один ECU: functional09/02→FF→physicalFC→дваCF; сборка всех20 существующих байт.|
|2|Два default ECU: только ECM OBD response; второй узел не уничтожает pending; ReadMsgs128 возвращает фактическое число.|
|3|FC на functional ID и другой ECU не выпускает CF; правильный physical FC выпускает.|
|4|WAIT/reserved status не выпускают данные; BS1 выдаёт по одному CF и сохраняет sequence.|
|5|OVERFLOW отменяет pending; новый physical OBD запрос остаётся рабочим.|
|6|Одинаковый physical ID на другом ChannelID не потребляет pending исходного канала.|
|7|Существующий generic F190 transport с явно синтетическими29-bit req/resp сохраняет ownership и байты; это не фикстура CEM MY2009.|
|8|ISO15765 возвращает прежний assembled ECM ответ; physical CEM09/02 NRC остаётся прежним.|

RED на исходном коде: `FAIL line45: PassThruReadMsgs(cid,&m,&n,0)==ERR_OK`, exit1 — после physical FC отсутствуют CF. После двух изменений process_request полный HOST_TEST PASS/exit0, включая существующие B9FB, READ128, filters, FC и P3 регрессии. Независимое повторное ревью и полный TCC запуск также PASS. `git diff --check` PASS.

### Остальные выполненные проверки

- C HOST_TEST: TinyCC Win32, `-std=c11 -Wall -Wextra`, с четырьмя актуальными p2core C-файлами. Win32 APIs в тесте заменены стабами; это не запуск DLL диагностическим клиентом.
- Python: `python -m unittest discover -s tests -p 'test_*.py'` — **50 tests PASS**.
- Go Control: `go test ./... -count=1` и `go vet ./...` — PASS отдельно для development и dev49. Локальный Go1.27.3 Windows/amd64; CI использует собственную1.23 toolchain.
- p2core: существующие router12/12, Vehicle Core8/8, bridge11/11 группы собраны против актуального emulator/src/p2core и прошли.
- Dev49 overflow/queue-full host experiments и BOM Go unit experiment — PASS assertions **наличия текущих ошибок**, а не доказательство исправления.
- Точные исходные CI SHA приведены выше. CI нового focused PR следует проверять по его HEAD; успех прежнего SHA его не заменяет. Новые Windows x86 DLL/GUI не запускались в VMware или на машине пользователя.

## План P0/P1/P2

**P0 — доказательства:** сохранить Issue #4 открытым. После CI focused PR получить read-only трассу SectorV и VDASH на точном SHA: session/window, ChannelID, protocol, baud, flags, TX selectors, FC ownership/BS/STmin, filters, RX counts/timestamps, результат клиентского парсера. Остановку/no_fixture/negative/partial/delivered различать. Не включать приватный INI или полный payload в GitHub. Не генерировать неизвестные ответы ради прохождения обнаружения.

**P1 — узкие подтверждённые исправления:** сначала F01 (этот PR); затем возобновление разрешённой CF-передачи после RX backpressure (F02), общий multi-responder pending контракт, и truthful terminal lifecycle dev49 (F08) до использования его responded как evidence. Dev49 fixes должны продолжать одно приложение Virtual Car и сохранять текущую opt-in/privacy модель.

**P2 — совместимость и качество evidence:** минимальная длина FC; selector/parser/importer parity; выбор первой валидной optional D2 fixture; синхронизация observer baud; BOM-safe INI editor; session/RID lifecycle, clear/filter/queue causes, periodic coverage; отдельное измерение STmin и стоимости file I/O. Каждое исправление — с поведением, failure-mode и регрессиями, без расширения ECU-протокола неподтверждёнными ответами.

Критерий завершения основной задачи остаётся строже сборки: SectorV/VDASH на конкретном SHA должны получить полный transport response **и отдельно подтвердить принятие требуемой идентификации**. Для MY2009 на текущих данных этот критерий не достигнут.
