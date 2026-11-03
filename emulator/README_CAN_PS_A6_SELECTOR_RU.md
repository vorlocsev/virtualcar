# CAN_PS: отдельное наблюдение A6 selector без транспорта

Связано с #37/#4 и PR #42. В [фактическом mask4 run](../docs/research/VDASH_CAN_PS_D8_OUTCOMES_RUNTIME_20261103.md)
после локального periodic-registration success появился rejected `D2_40_A6`.
Прежний logger намеренно не сохранял два selector bytes. Новый probe позволяет
различить только закрытый каталог; он не восстанавливает прошлую запись.

В новой изолированной лабораторной копии профиля:

```ini
[Diagnostics]
EnableCanPsConfigProbe=1
CanPsApiOutcomeMask=4
EnableCanPsA6SelectorProbe=1
```

Новый флаг по умолчанию0, требует master probe и принимает только строку `1`,
возвращённую `GetPrivateProfileString`. INI API Windows может нормализовать
пробелы/кавычки исходного файла. Другие считанные значения дают0. Значение
читается при Open и копируется в отдельное поле PS channel при Connect;
редактирование INI не переключает открытый device/channel.

Флаг включает только metadata. API mask не меняется, A6 Write/periodic
по-прежнему возвращают `ERR_NOT_SUPPORTED`, Write count0, periodic output ID
не изменяется. Нет CAN_PS TX, RX, backend root, periodic firing или ответа CEM.
Никакой selector не считается подтверждением read-only semantics/normal-mode.

## Узкая форма и закрытый каталог

Record возникает только для уже проверенного rejected A6 envelope:

- channel protocol CAN_PS0x8004, новый channel flag включён;
- один message: zero/batch counts не разыменовывают message array;
- declared message protocol CAN5 либо CAN_PS0x8004;
- DataSize12, extended TxFlags0x100, CAN ID0x000FFFFE;
- восемь bytes `CD 40/50 A6 xx xx 01 00 00`.

| Metadata enum | Публичная категория | Что это подтверждает |
| --- | --- | --- |
| 0 | `other_redacted` | Selector вне каталога; точное значение остаётся неизвестным |
| 1 | `1A02` | Совпадение двух selector bytes |
| 2 | `1A04` | Совпадение двух selector bytes |
| 3 | `D0D1` | Только lexical selector; назначение не установлено |

Каталог не предсказывает запрос клиента. `1A02/1A04` из раннего S80 и `D0D1`
из отдельного MY2005 SectorV не доказывают их использование текущим VDASH.
Raw operands и произвольные 16-bit значения не экспортируются. Иные длины,
ID/flags/protocol/header/tail, control/security и D8 не создают selector record.
Существующие rejected markers и API outcomes не меняют формат/счётчики.

Наблюдаемые pins и baud — отдельный контекст:0/unselected,3/11,6/14;
baud125000/500000 либо0/redacted. Metadata может описывать другой маршрут,
но не включает его поддержку. Pins являются remembered hints, не проверенной
физической проводкой. Scope исходного mask4 — pins3/11 и125000; другие
контексты не смешиваются с ним.

## Metadata и аудит

`J2534 CAN_PS A6 selector channel/origin/pins/baud/protocol/target/selector/mask/status (BE)`

Девять uint32: channel, origin1 Write/2 periodic registration, pins, baud,
declared protocol, target40/50, selector enum0..3, текущий API mask0..7,
status1. Нет новых CAN records. Строка содержит результат отклонённой попытки,
не факт отправки и не последующее firing периодического сообщения.

Существующий `audit_j2534_connect.py` добавляет optional `can_ps_a6_selectors`
только при новом marker. Он строго проверяет36 bytes и закрытые категории;
невалидные metadata считаются отдельно. JSON содержит aggregate/events и
source_order до20000 записей, без channel/PID/host/path/raw values и state joins.
Это дополнительное наблюдение тех же API calls: events нельзя прибавлять к
`rejected_can_ps_attempts.calls` или `can_ps_api_outcomes.calls`.

Стандартный вызов, с новым output filename:

```powershell
py -3 .\tools\audit_j2534_connect.py "$env:TEMP\SectorVVirtualCar.log" --output "$env:USERPROFILE\Desktop\a6-selector-audit.json"
```

Transmission/ECU/periodic-firing/read-only-approval/selector-semantics flags
остаются false. Старые logs не получают придуманный selector: при отсутствии
нового marker optional section отсутствует, прежний report неизменён.

## Восемь групп проверки и следующий запуск

1. Default-off/master, malformed flag, Open/Connect snapshot.
2. Три catalog selectors и opaque other, targets40/50, CAN/CAN_PS, обе API origins.
3. Near misses header/tail/size/ID/flags/protocol и непрозрачные control/security.
4. Zero/batch/huge count, null pointers и invalid channel без чтения operands.
5. Pins/baud категории, разные каналы, rebind и Close/Open lifecycle.
6. Сохранение status/count/output/message, отсутствие backend/bridge/RX/scheduler effects.
7. Strict decoder/36-byte contract, invalid metadata, limit/source-order без joins.
8. Privacy, exclusive output, прежний audit/default behavior и реальная x86 DLL.

Native runner имеет отдельный `-A6SelectorRegression`, несовместимый с
`-ApiOutcomeRegression`: свежая папка, synthetic profile, flag0/1/01 и mask4.
Проверяет24 rejected calls и8 selector records только при flag1, backend0,
READ128 без RX. Прежняя матрица API outcomes и13-request route fixture отдельно.
Это regression, не capture автомобиля или выполнение VDASH.

Следующий client run — bounded mask4 с этим флагом, fixed DLL/GUI/worker/profile
hashes, direct module binding, полным Open/Close suffix и наблюдением UI.
Если A6 повторится и совпадёт с каталогом, selector будет установлен этим
новым наблюдением. Если будет `other_redacted` либо A6 не повторится, пробел
останется явным. Ответ CEM и условие SectorV этим probe не устанавливаются.
В [новом фактическом VDASH run](../docs/research/VDASH_CAN_PS_A6_SELECTOR_RUNTIME_20261103.md)
наблюдён один rejected **A6/1A04 target40**, PS/pins3/11/125000, mask4.
Во время запуска worker изменился E35→988; sampled hash совпадает с файлом
после stop. Это наблюдение нового worker с новой DLL, не раскрытие прежнего
capture и не strict A/B. Read/RX markers после A6 отсутствуют; empty polling
timeout0 не журналируется, поэтому любые ReadMsgs calls не исключены.
Ответ CEM/значение parameter и SectorV predicate не установлены. VMware guest
и physical J2534 этим локальным Windows run не проверялись.
