# VDASH MY2005: наблюдён rejected A6 selector1A04, 03.11.2026

Задачи #37/#4, PR #42. В новом bounded Windows run один selector record
подтвердил **A6/1A04 к target0x40**, declared CAN_PS, pins3/11,125000, mask4.
Write вернул `ERR_NOT_SUPPORTED`; A6 не передан, ECU response отсутствует.
После него новых Read/RX markers не наблюдалось. Это запрос текущего VDASH worker в synthetic
MY2005 сценарии, не capture реального CEM или подтверждение MY2009 discovery.

## Источник и важное изменение worker

| Компонент | Проверенное значение / SHA-256 |
| --- | --- |
| Source HEAD | `823357ec825e1eefcc58b26d8608245a283aa529`, PR #42 |
| Source CI | [Emulator/native x8641690439864](https://github.com/vorlocsev/virtualcar/actions/runs/41690439864), [VMware LAB41690439506](https://github.com/vorlocsev/virtualcar/actions/runs/41690439506): success; prerelease publish skipped |
| Artifact / merge ref | ID13256888721 / `14b95e036daf7c908c9da57af0609013f5305062` |
| Outer artifact | `06f9b4432f587a09b33511e6def6a9c879a27af7e6e6cc4a65771f9d4fd8339b` |
| Inner package | `b47b54dbbf24fd5109054aca02971a304e0f16c6a9f24cd408c7839500f64b2a` |
| Loaded DLL | `33c61247b4a5add02ed2302f326f3376ede453ede7499654667c9b8ee52b4815` |
| Profile | `f1bca25aa0b48aff73d41148767b8e6ad2ede7f1f7608ae748d2c340501841e4` |
| GUI FileVersion2.5.115.85 | `eed3f62e84dbaf295f9225c8b82f043bd25d61fea74209e4b5c31c8a2d843ea8` |
| Worker before GUI launch | `e35bf82258b84292cf87c6c6f90ab472d354424c13ec9d9ba73dd9299870773f` |
| Sampled worker and file after stop | `988f31c0a0dff1335d86a19e6cdaf41faac7a78149c72f5620161831aad81090` |

Outer/inner checksums, all package SHA256SUMS entries, BUILDINFO merge ref
и PE32/i386 проверены до регистрации. К прежнему локальному mask4 profile
добавлен только selector flag1; master1, mask4, synthetic MY2005, один ECM,
CEM fixtures/passive traffic выключены. DLL тоже новая, поэтому это
instrumented follow-up, не strict same-binary A/B.

**Во время запуска изменился worker.** Pre-launch hashE35 сохранён отдельно;
его нельзя выдавать за loaded worker hash. Module sample18:18:17.7507569Z
прямо связывает единственный native log emitter с expected DLL path/hash
и image hash988. После остановки worker file также имеет988; DLL/profile/GUI
сохранили первоначальные hashes. File/ProductVersion worker не установлены.
Причина замены worker не исследована. Нельзя приписывать различия относительно
прежнего mask4 только новому probe или переносить selector на старую запись.

## Ограниченный запуск и сохранённая запись

Один GUI invocation, ручной вход пользователя, без agent diagnostic/refresh
click. Supervisor ожидал worker до15min, затем90s либо3 Close markers.
Первый worker18:18:15.2700682Z; stop18:19:45.1315493Z по worker deadline.
Одна полная Open–Close window, строки20–162; nested/unmatched/unfinished0.
Времена здесь UTC, не clock диагностического обмена и не ECU processing time.

| Полный suffix | Bytes / lines | SHA-256 |
| --- | --- | --- |
| Text | 20201 /162 | `356cb34ee935b82267a2377c566353b3eac9b3fe614284e754e8b7d67d4eaa38` |
| Backend | 4006 /16 | `ecf7fb4375d96a8e86156d1065bab32e636d55b643d625f7554df9a5f39b7664` |

Исходные log prefixes сохранены. Raw logs, profile, VIN, account data,
screenshots и proprietary binaries не включены в Git.

## Наблюдаемая последовательность

| Строки text suffix | Наблюдение | Следующий шаг |
| --- | --- | --- |
| 142–144 | Exact D8 Write rejected | Periodic registration |
| 145 | Local exact-D8/1000ms periodic-registration success | CLEAR_RX146–147 |
| 148–150 | Дополнительный PASS_FILTER rejected | Новый Write |
| 151–154 | A6 Write rejected; старый lexical marker152 и **selector1A04 marker153** | StopFilter155 |
| 155–156 | StopFilter invalid_filter_id; READ_VBATT | Disconnect |
| 157–161 | Disconnects, local clear-periodic159 | Close162 |

Строгий [контракт emitter](../../emulator/README_CAN_PS_A6_SELECTOR_RU.md)
позволяет восстановить форму запроса из закрытых категорий:
ID0x000FFFFE, extended flags0x100, DataSize12, body
`CD 40 A6 1A 04 01 00 00`, declared ProtocolID0x8004. Это вывод из проверенной
формы marker, не публикация raw trace и не подтверждённая read-only семантика
selector. Pins — remembered3/11 hint, не физически проверенная проводка.

Один selector event не новый API call. API outcomes:3 snapshots отдельно,
11 calls =1 local periodic success +6 creation rejects +4 lifecycle records;
invalid metadata/capacity0. Lifecycle:3 clear-periodic и1 invalid StopFilter.
Rejected attempt classifier:2 writes — D8 и A6. Четыре filters rejected;
новых periodic-rejection records нет, поскольку registration получила локальный
success. Periodic firing отсутствует по реализации, не симулируется на шине.

A6 не попадает в ordinary TX/backend. Новых Read/RX markers после A6 нет;
положительный или отрицательный ECU response на него не наблюдался. Из этого
нельзя заключить, какой response удовлетворил бы VDASH, или что filter failure
не влияет на дальнейшее чтение. Пустой ReadMsgs polling с timeout0 не
журналируется; отсутствие любых ReadMsgs calls после A6 не доказано.

## Обычный обмен, UI и сравнимость

Backend:3 ordinary TX/roots/terminals,1 session, statuses по1 delivered/
unsupported/unverified, invalid lines0; queued=dequeued2, drops/filter-drops/
route conflicts0. Text auditor:1 VIN transport delivery +1 suppressed
TesterPresent observation,2 checked RX metadata, missing/invalid/off-route0,
parse errors0. Recognized ordinary D2/P3 probes0 не означает отсутствие A6:
он находится в отдельной rejected metadata до ordinary TX.

UI показал XC90/MY2005/B8444S/P2,12.5V и Home NOTFOUND/CONNECT. Warning
не наблюдался на snapshots; его отсутствие не доказано. ECU list до stop
не проверен. VIN/UI decoding не подтверждает CEM identity или MY2009.
Agent не запускал refresh, reset, DTC clear, programming/security или live
diagnostics; вход выполнил пользователь.

В прежнем mask4 были те же aggregate API categories и последовательность
periodic success → filter reject → A6 reject. Совпадение категорий/порядка
сравнивается отдельно от bytes/timestamps/IDs. **Новая DLL и новый worker**
не позволяют из этого выделить причинный эффект probe или задним числом
назначить прежнему A6 selector1A04. По одному invocation — не outcome rates.

Все собственные monitor/frontend/worker закрыты, remaining0 проверен.
Saved LastDevice восстановлен точно; удалён только изолированный key с
проверенными Name/FunctionLibrary. У исходной регистрации неизменны эти два
проверенных поля; побайтовая проверка всех registry properties не заявляется.
Main/Dvinholm/опубликованный prerelease не изменялись.

## Восемь групп свидетельств и следующий пробел

1. Source/CI/artifact/PE32/package manifests и DLL/profile/GUI hashes.
2. MY2005/master/mask4/selector1 и отсутствие новых CEM fixtures.
3. Один emitter, direct module binding; worker transitionE35→988 явно сохранён.
4. Deadline, полная window20–162, checksum/prefix integrity.
5. Periodic success → CLEAR_RX/filter rejection → A6 source-order.
6. Selector1A04/target40/pins3/11/125k/protocolPS/status1, без double-count.
7. Нет A6 ordinary/backend TX/RX; normal transport и UI в отдельных scopes.
8. Guarded cleanup, точный saved selection restore, privacy и предел сравнения.

Connect/backend auditors взяты из проверенного artifact source823357e.
Text auditor — PR #41 commit`c0f6484f62f0cc78afb8c8b804dffd78f1363dce`,
SHA-256`e38170b56ec60467f5ff64bd89b4353a425f532a707d81bae010070466139233`,
`--include-obd`. Этот standalone audit не означает merge #41 в #42.

Теперь установлен **конкретный запрос текущего worker**, но не значение
CEM parameter1A04, его совместимый response и условие продолжения VDASH.
Ранние S80 reads являются сравнительным источником, не MY2009 fixture.
Для SectorV дополнительно нужен его точный normal-mode predicate/успешный
сопоставимый сеанс; наблюдение VDASH его не заменяет. Нового RX или positive
CEM ACK по этому результату не добавляется. VMware guest/physical J2534 этим
локальным Windows run не проверялись.

[Metadata-only summary](vdash-can-ps-a6-selector-runtime-20261103.summary.json).
