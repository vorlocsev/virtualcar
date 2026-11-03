# VDASH MY2005: отдельные D8 Write и periodic outcomes, 03.11.2026

Задачи #37/#4, PR #42. На тех же бинарниках, что matched mask0, проверены
два независимых условия. **Mask2** дал три локальных D8 Write successes,
но следующий periodic call оставался rejected и нового CEM probe не было.
**Mask4** дал один локальный periodic-registration success: затем появились
CLEAR_RX, дополнительный filter и **новый rejected D2_40_A6 Write**.

Это наблюдаемое продолжение VDASH после API-исхода, не CAN transmission,
periodic firing, ECU ACK или подтверждение normal-mode в SectorV. A6 также
отклонён; его PID operand текущий logger не сохранял, ответ неизвестен.

## Происхождение и сравнимость

| Компонент | Проверенный источник / SHA-256 |
| --- | --- |
| Runtime source | `1a78b82c4c8c2ba6f12bb49a6cb2eb958da31028`, PR #42 |
| Source CI | [Emulator/native x86 41621035280](https://github.com/vorlocsev/virtualcar/actions/runs/41621035280), [VMware LAB 41621035695](https://github.com/vorlocsev/virtualcar/actions/runs/41621035695): success; prerelease publish skipped |
| Artifact / merge ref | ID13222683769 / `a98a9332cc3fdd30d1bd9fc79c01d464c57e4756` |
| Outer artifact archive | `6d9d1dd284c91826b4d7a7c5b96a5f2a4b500b2b46833e89f5dab5a165ce50c1` |
| DLL, одинаковая в mask0/2/4 | `ab9494e47e8585f8d9ab9ec8ad84c65ca9f8d7d722af795a4758ed51d61f43c7` |
| GUI 2.5.115.85 | `eed3f62e84dbaf295f9225c8b82f043bd25d61fea74209e4b5c31c8a2d843ea8` |
| Worker, File/ProductVersion пусты | `e35bf82258b84292cf87c6c6f90ab472d354424c13ec9d9ba73dd9299870773f` |
| Control profile, mask0 | `421eaa88bf47c2f5fde28aa48a713a89d3f126cd754d04f65af22b5a7322b246` |
| Write-only profile, mask2 | `7712c1df37952185ee74e8e2e9ac7010751bef20f1ca0283a2e3cdbd359c5edd` |
| Periodic-only profile, mask4 | `8022c3c02c7bb78e0507817b624b5431054c678994b7030f53a251af16b9417c` |

Новый DLL build не нужен: использована та же проверенная CI-библиотека из
[matched control](VDASH_CAN_PS_FILTER_OUTCOME_RUNTIME_20261103.md). Каждый
профиль отличается от mask0 ровно одним символом значения маски. Master
probe включён; synthetic MY2005, один ECM, RxStart/telemetry, CEM fixtures и
passive traffic выключены. Read-only и отсутствие CAN_PS RX сохранены.

В каждом run один GUI invocation и captured worker, direct module path/
PID/hash binding подтверждён; DLL/GUI/worker/profile hashes до/sample/после
согласованы. Module samples: mask2 11:40:59.946786Z, mask4 11:48:03.067120Z.
Это локальные supplied client artifacts, не подтверждённый publisher release
или подлинный capture автомобиля MY2009. VMware guest/physical J2534 не
тестировались. Временные registration names/folders различались; внешнее
состояние клиента/сервиса не полностью контролировалось.

Оба новых supervisor завершили собственные процессы по90s worker deadline.
Mask2 увидел2 Close и сохранил2 полных окна20–152/172–262; mask4 увидел1 Close,
полное окно20–161. Nested/unmatched/unfinished0. Это не outcome rates;
сравниваются первые завершённые циклы и конкретные source-order шаги.

| Полный suffix | Bytes / lines | SHA-256 |
| --- | --- | --- |
| Mask2 text | 31913 /262 | `6612b062da28a1d75d0b4e9806178cc9f71b08ee560fa5fbbf47608dca1cc82c` |
| Mask2 backend | 7980 /32 | `1c12b527fe0c275bcc46631e6cd52d3a878bcbb3ef4b95677cff307b09cb66cb` |
| Mask4 text | 19978 /161 | `fb5f9b1e09cb29913e042394d529f7238c17978c672bdbe10c12382e788882b0` |
| Mask4 backend | 4006 /16 | `2447a0535ea0fc4371dc9ab94c325dc16a9bf45740ec33a6c36570219d8c9053` |

Исходные префиксы обоих общих журналов сохранены без изменения в каждом run.
Raw logs, profiles, VIN, account data и screenshots остаются вне Git.

## API-исходы и продолжение клиента

| Проверка | Mask0 control | Mask2 Write-only | Mask4 periodic-only |
| --- | ---: | ---: | ---: |
| Mode snapshots, отдельно от calls | 5 | 5 | 3 |
| Creation successes | 0 | 3 Write | 1 periodic registration |
| Creation rejects | 9 | 6 | 6 |
| Lifecycle records | 0 | 5 clear-periodic | 3 clear-periodic +1 invalid StopFilter |
| Calls без snapshots | 9 | 14 | 11 |
| Invalid metadata/capacity events | 0/0 | 0/0 | 0/0 |

Все injected successes: pins3/11, CAN_PS/125000, exact D8; periodic только
1000ms. Это локальный API result, не отправленный кадр. Старые hardcoded
rejected markers отсутствуют для success по контракту, поэтому их уменьшение
не означает отсутствия Write/periodic attempts. Nonzero-mask lifecycle
records не доказывают новых Clear calls относительно неинструментированного
legacy cleanup mask0. Обычный TX auditor не охватывает rejected PS frames.

Начальные PS filters во всех трёх условиях остаются rejected, затем
ReadMsgs timeout100ms/consecutive1 и disconnect. Mask2 не добавляет CLEAR_RX:
19 во всём capture и13 в первом цикле, как mask0.

| Первый цикл, source-order | Mask0 | Mask2 | Mask4 |
| --- | ---: | ---: | ---: |
| Первые filter rejects | 36/41/60 | 36/41/61 | 36/41/61 |
| PS Read timeout100ms | 44/63 | 44/64 | 44/64 |
| D8 Write result | reject140 | success142 | reject142 |
| Следующий periodic1000ms | reject143 | reject143 | success145 |

После mask2 success142 немедленно следует periodic rejection143 и legacy
metadata144–146; затем disconnect147–148, clear-periodic149, disconnect150–151,
Close152. Остальные Write successes186/251 также сменяются periodic rejects
187/252. Нового PS Read после этих Write не наблюдалось.

**Mask4 меняет следующую последовательность:**

| Строки mask4 | Наблюдаемый шаг |
| --- | --- |
| 145 | Local periodic-registration success |
| 146–147 | CLEAR_RX context/buffer clear |
| 148–150 | Дополнительный PASS_FILTER rejected |
| 151–153 | Новый Write rejected; lexical class D2_40_A6 |
| 154 | StopFilter → invalid_filter_id |
| 155 | READ_VBATT |
| 156–160 | Disconnects и local clear-periodic |
| 161 | Close |

Дополнительный filter: CAN_PS, ID-only, обе flags extended, flow отсутствует,
mask redacted-other, pattern nonzero11-bit category. A6 attempt: declared
CAN_PS, pins3/11,125000, target0x40; narrow classifier подтверждает raw classic
CAN/extended envelope. **PID не наблюдается**, его значение/назначение не
угадываются по источникам других лет. После A6 нового Read нет. Фильтр не
установлен, A6 не передан, backend root для него отсутствует. Первый цикл
CLEAR_RX увеличился13→14. Это наблюдение запроса клиента, не CEM response.

## Обычный обмен, UI и границы вывода

Первый backend session во всех случаях содержит16 событий с одинаковыми
kind/channel/protocol/baud/route/reason/outcome:3 обычных TX/roots/terminals,
1 VIN delivery,2 RX metadata, queued=dequeued2. Сравнение не побайтовое и
не соединяет clocks/IDs разных запусков. Нет drops/filter-drops/conflicts.

Полный mask2:6 обычных TX/roots/terminals,2 VIN deliveries,4 valid RX metadata;
все32 backend events категориально совпадают с mask0. Полный mask4:3 обычных
TX/roots/terminals,1 VIN,2 valid RX metadata, один API-цикл. Из этого нельзя
делать вывод об уменьшении traffic или росте success rate. Missing/invalid/
off-route/ignored RX, parse errors и invalid backend lines0.

Normal-TX analyzer показывает recognized D2/P3=0. Это **не отсутствие A6
attempt**: он находится в отдельной rejected metadata, до ordinary TX/
backend logger. Никакая CEM identity или response acceptance не подтверждена.

В mask2 agent прочитал communication warning и оставил его открытым. В mask4
agent наблюдал Home с NOTFOUND/CONNECT; warning не наблюдался, его отсутствие
не доказано. ECU list в обоих run до stop не проверен. Диагностику/refresh,
reset, DTC clear, security/programming agent не запускал. UI labels являются
отдельным наблюдением и не расшифровывают predicate native worker.

Оба run автоматически завершены, final remaining0 проверен отдельно.
Сохранённый LastDevice восстановлен точно, temporary registrations удалены,
исходная registration не менялась. Main/Dvinholm/prerelease не изменены.

## Вывод и следующий материал

В этой проверенной серии отдельный periodic API success связан с новым
продолжением до A6, которого нет в mask0/1/2 captures. Это поддерживает
гипотезу API gate по результату StartPeriodicMsg в текущем VDASH worker.
Не установлены универсальное условие клиента, SectorV normal-mode predicate
или пригодные ответы CEM MY2009. Другие API всё ещё отклонены, а periodic
delivery намеренно отключена; это не работа полноценного CAN_PS transport.

Следующий конкретный пробел — точный A6 selector и ожидаемый read-only обмен
на этом маршруте. Их нельзя восстановить из одного label D2_40_A6 или
подставить1A04/1A02 и положительный ответ по аналогии. Нужны проверенное
наблюдение запроса/условия клиента и совместимый источник ответа; новые CEM
fixtures или ACK этим этапом не добавляются.

## Восемь проверок

1. Source/artifact hashes и один mask-character профиля относительно control.
2. Direct module/PID binding и стабильные DLL/GUI/worker/profile hashes.
3. Bounded deadlines и полные Open/Close окна, без сравнения rates.
4. Snapshots/calls/success/reject/lifecycle раздельно, invalid/capacity0.
5. Mask2 Write success → periodic reject, без нового ordinary/backend TX.
6. Mask4 periodic success → CLEAR_RX/filter/A6, PID явно unobserved.
7. First-cycle normal TX/RX/backend и UI outcomes в собственных scopes.
8. Prefix/capture checksums, cleanup/restore, privacy и отсутствие новых CEM replies.

Connect/backend auditors — runtime source1a78b82. Text auditor PR #41
`c0f6484`, SHA-256
`e38170b56ec60467f5ff64bd89b4353a425f532a707d81bae010070466139233`,
`--include-obd`. Code CI проверил196 Python tests/1 expected skip, C/native
x86 матрицу всех8 masks и прежний13-request route fixture. Client результаты
выше не выводятся из CI. [Metadata-only summary](vdash-can-ps-d8-outcomes-runtime-20261103.summary.json).
