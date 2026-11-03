# VDASH MY2005: filter-only API outcome, 03.11.2026

Задачи #37/#4, PR #42. Маска1 дала **три локальных успеха PASS_FILTER**;
после них клиент по-прежнему встретил PS ReadMsgs timeout100ms и отключил
каналы. Позже три D8 Write и три periodic-registration остались отклонены.
GUI показал communication warning. В этом опыте **локальный успех filter
не устранил наблюдаемые timeout и warning**. Опыт не установил причину
предупреждения VDASH, условие normal-mode в SectorV или необходимый обмен CEM.

## Происхождение и условия

| Компонент | Проверенный источник / SHA-256 |
| --- | --- |
| Runtime source | PR #42 `1a78b82c4c8c2ba6f12bb49a6cb2eb958da31028` |
| CI | [Emulator/native x86 41621035280](https://github.com/vorlocsev/virtualcar/actions/runs/41621035280), [VMware LAB 41621035695](https://github.com/vorlocsev/virtualcar/actions/runs/41621035695): success; publish skipped |
| Artifact / merge ref | ID13222683769 / `a98a9332cc3fdd30d1bd9fc79c01d464c57e4756`, не source HEAD |
| Outer archive | `6d9d1dd284c91826b4d7a7c5b96a5f2a4b500b2b46833e89f5dab5a165ce50c1` |
| Реально загруженная DLL | `ab9494e47e8585f8d9ab9ec8ad84c65ca9f8d7d722af795a4758ed51d61f43c7` |
| Synthetic MY2005 profile, mask1 | `f5f196c7fdb3a021baba06b046d53a0e29a7b02bbe10e6e3a36821392ae3725b` |
| Свежий control profile, mask0 | `421eaa88bf47c2f5fde28aa48a713a89d3f126cd754d04f65af22b5a7322b246` |
| Frontend 2.5.115.85 | `eed3f62e84dbaf295f9225c8b82f043bd25d61fea74209e4b5c31c8a2d843ea8` |
| Native worker | `e35bf82258b84292cf87c6c6f90ab472d354424c13ec9d9ba73dd9299870773f` |

Outer/inner архивы и file checksums проверены. Профиль получен из прежнего
synthetic MY2005 baseline с SHA-256
`cca3fc41ad09381a2c6239313466afb5c4b52b421e8015bacc276c839b2af860`
добавлением только CanPsApiOutcomeMask=1. INI master1/mask1 проверены до
запуска. Один ECM, RxStart/telemetry, CEM fixtures/passive выключены.

Прямой module sample10:51:59.500689Z подтвердил expected path, DLL и worker
hash для единственного captured native PID; сравнение PID как uint32,
значение не публикуется. Все snapshot/call records имеют mask1. GUI/worker/
DLL/profile hashes после завершения не изменились. Физический J2534 и VMware
guest не тестировались; происхождение proprietary клиента по издательскому
каналу не подтверждается.

Один GUI invocation с ручным входом. Supervisor остановил собственные
процессы по90s worker deadline, увидев два Close. Полный suffix содержит
**2 Open/2 Close**, окна20–154 и174–268, без nested/unmatched/unfinished.
Worker впервые замечен10:51:58.139923Z, supervisor завершился10:53:28.678875Z;
cleanup включён в этот внешний интервал. Ожидание ручного входа не является
временем CAN обмена. Automatic finalizer сохранил suffix и восстановил
выбор адаптера без дальнейшего UI ввода.

| Полный suffix | Bytes / lines | SHA-256 |
| --- | --- | --- |
| Native text | 32501 /268 | `7a4722ae9ffe9ae122af47c38b87fe3d6fa4ad1a8eed42bea46899a991a86458` |
| Backend JSONL | 8012 /32 | `daec92d2d7adb8c294b9850d08141990460062392a2d0b4b5af36d3a105dcb4f` |

Префиксы обоих исходных журналов подтверждены без изменения. Raw logs,
профиль, VIN, account data и screenshots остаются вне Git.

## Свежий mask0-контроль с теми же бинарниками

После обнаружения исторического различия worker выполнен новый mask0 run
на **том же source1a78b82/DLL, GUI85 и worker e35bf822…**. Direct module/PID/
hash binding получен в обоих run, все hashes стабильны до/sample/после.
Профили побайтово отличаются ровно одним символом значения маски1→0.
Для каждого run использована отдельная временная регистрация и папка DLL;
совпадение binary hashes не означает совпадения всех внешних условий.

Control supervisor также завершил worker по90s deadline, увидев2 Close;
полный suffix содержит2 Open/2 Close, окна20–151 и171–263. Warning того же
типа прочитан и намеренно оставлен открытым; ECU list не проверен.
Остановка11:10:37.439157Z включает cleanup, первый worker11:09:06.473799Z.
Процессы/selection/registration восстановлены, исходные префиксы целы.

| Control suffix | Bytes / lines | SHA-256 |
| --- | --- | --- |
| Native text | 31989 /263 | `81cb5bfbcf793eea795a8cfeadaad8a567aeb380f75170fd17c4c1fa3022dd59` |
| Backend JSONL | 8012 /32 | `edec5c3f43f3c5f671cca1b16397ae39a9b485143e9b6e9a57657a110957df0b` |

Mask0 auditor:5 snapshots отдельно от9 creation calls. Все9 rejected:
3 filter,3 Write,3 periodic1000ms; injected/lifecycle/capacity/invalid0.
Исторический baseline6153297 остаётся отдельным источником; основное
сравнение ниже использует именно свежий mask0 с текущими бинарниками.

## Локальные исходы и следующий шаг

API-outcome auditor:5 mode snapshots отдельно от14 calls. Из calls:
3 filter successes,6 creation rejections и5 clear-periodic local operations;
invalid0/capacity0. Все три success — PASS_ID_ONLY, pins3/11,125000, mask1,
`simulated_api_success_no_transport`. Сохранялись только PS-local handles,
не generic filters, CAN transmission или ECU RX.

Три Write и три periodic calls дали exact D8, ERR_NOT_SUPPORTED. Старые
rejected setup records подтверждают interval1000ms для periodic. Других
распознанных PS write shapes в этом capture нет.16 старых probe records:
5 allocation,5 pin SET,3 write reject,3 periodic reject; filter reject0
означает отсутствие отклонённых filters, **не отсутствие filter attempts**.
Legacy text marker filter_start не включает новые PS-local success records.

Сравнение первого полного API-цикла на одной DLL/worker, source-order строки:

| Свежий control, mask0 | Filter-only, mask1 | Следующий наблюдаемый шаг |
| --- | --- | --- |
| Filter rejects36/41 | Filter success36/41, затем CLEAR_RX38/43 | Read timeout44 в обоих,100ms, consecutive1 |
| Disconnect45–46 | Clear-periodic45, Disconnect46–47 | Второй PS Connect |
| Extended filter reject60 | Extended filter success61, затем CLEAR_RX63 | Read timeout63/64,100ms, consecutive1 |
| Disconnect64–65 | Clear-periodic65, Disconnect66–67 | Standard CAN/ISO15765 fallback |
| TesterPresent95, VIN105, extended TesterPresent127 | Те же классы97/107/129 | VIN RX и последующий D8 setup |

В mask1 наблюдаются **три дополнительных CLEAR_RX_BUFFER после filter
success**. В первом цикле16 против13, во всём capture22 против19. Поэтому
полный API порядок нельзя называть одинаковым: клиент реагировал на
локальный success, но следующий PS Read всё равно завершился timeout.

Clear-periodic outcome records добавляются только при nonzero mask. Их
отсутствие в baseline metadata не доказывает отсутствие прежнего Clear call;
по этой разнице нельзя приписывать клиенту новую ветку управления.

Первый backend session в обоих captures имеет одинаковую последовательность
16 **категорий событий**:3 roots/3 terminals, по одному delivered/unverified/
unsupported, queued=dequeued2. Все32 backend events обоих run совпали по
kind/channel/protocol/baud/route/reason/outcome, не bytes/timestamps/IDs.
Нет drops/filter-drops/conflicts/invalid. Межжурнальные часы не склеивались.

Полный filter capture:6 обычных TX/backend roots/terminals, по2 каждого
класса7DF TesterPresent/OBD VIN/extended functional TesterPresent;2 backend
sessions,2 VIN deliveries,4 RX metadata checks, queued=dequeued4.
Missing/invalid/off-route/ignored RX и parse errors0. Recognized D2/P3 probes0
в области имеющихся анализаторов, CEM identity не подтверждена.
Свежий mask0 имеет те же обычные TX/RX/backend количества и результаты.

## UI, восстановление и ограничения вывода

GUI показал synthetic XC90/P2/B8444S/MY2005 и12.5V, затем предупреждение
о недоступных ECU. Попытка закрыть его через OK вернула geometry error;
подтверждение **не установлено**. При повторном выборе окна supervisor уже
завершил приложение. ECU list до остановки не проверен. Reset-рекомендация,
Start live logging, DTC clear, security и programming не выполнялись.

Исторический [baseline6153297](VDASH_CAN_PS_SETUP_RUNTIME_20261103.md)
использовал другую DLL и другой worker: прежний SHA-256
`b29b7f5e90645c9b04a12d12578a154b6ee7441c7aab1865a5e19d31277fe1aa`,
текущий e35bf822… подтверждён подготовительным manifest, live module sample
и файлом после завершения. File/ProductVersion worker пусты; механизм
изменения не установлен. Свежий control устраняет это конкретное различие:
в обоих новых run DLL/GUI/worker одинаковы. Это по одному invocation на
условие, без полного контроля внешнего сервиса/истории клиента. В mask1
acknowledgement не установлен, в mask0 warning намеренно не закрывался.
Количество повторов не является outcome rate; warning не устанавливает
predicate клиента. CI и этот API-experiment не доказывают физический transport.

Все собственные процессы завершены, final remaining0 проверен отдельно.
Прежний LastDevice восстановлен, temporary registration удалена; исходная
PR22 registration не менялась. Main/Dvinholm/prerelease не изменены.

Вывод ограничен наблюдением: filter API можно принять локально; клиент
добавляет CLEAR_RX, но сохраняются100ms ожидание без PS RX, disconnect и
прежние D8 отказы. Новый распознанный CEM probe не появился. Гипотеза, что
одного filter success достаточно для устранения наблюдаемого timeout/warning,
в этой паре опытов не получила поддержки. Это не доказательство ненужности
filters в полном транспорте и не повод придумывать входящие кадры.
Следующий отдельный опыт — mask2, exact D8 Write при отказе filter/periodic;
mask4 проверяется отдельно. В каждом случае контролировать hashes и baseline.

## Восемь проверок

1. Artifact/merge/source refs, checksums, одна mask-character разница профилей.
2. Direct module/PID/hash binding в обоих run, одинаковые DLL/GUI/worker.
3. Bounded deadline,по2 полных API-цикла, полные suffix/prefix hashes.
4. 5 snapshots отдельно от14 calls, три локальных filter successes.
5. Write/periodic остаются rejected D8, interval1000, no transport/ECU proof.
6. Парное сопоставление: дополнительные CLEAR_RX и прежний100ms PS timeout.
7. Обычные TX/RX/backend, UI warning и acknowledgement uncertainty отдельно.
8. Автоматическая остановка/восстановление, privacy, отсутствие CEM replies.

Connect/backend auditors — runtime source1a78b82. Text auditor PR #41
`c0f6484`, SHA-256
`e38170b56ec60467f5ff64bd89b4353a425f532a707d81bae010070466139233`,
`--include-obd`.196 Python tests OK/1 expected native-DLL skip; native C,
actual x86 matrix и стандартный13-request route fixture проверены CI.
[Metadata-only summary](vdash-can-ps-filter-outcome-runtime-20261103.summary.json).
