# CAN_PS: раздельный API-outcome experiment

Задачи #37/#4, продолжение configuration-only probe. Режим меняет локальный
результат выбранного J2534 вызова. **STATUS_NOERROR означает смоделированное
принятие API без CAN transmission, periodic firing, ECU RX или D8 ACK.**
Обычная гарантия периодической отправки J2534 здесь не реализована.

В [фактическом MY2005 run](../docs/research/VDASH_CAN_PS_SETUP_RUNTIME_20261103.md)
с direct module binding наблюдались PASS_FILTER с CAN_PS/DataSize4/null flow,
exact D8 WriteMsgs и periodic-registration с interval1000ms. Все возвращали
ERR_NOT_SUPPORTED. Эти данные не определяют, какой отказ мешает продолжению
клиента. Новый эксперимент позволяет изменять исходы независимо, сохраняя
отсутствие ECU ответов. Источники D8 не доказывают ACK или normal-mode predicate.

## Включение

Только в новой изолированной лабораторной копии профиля:

```ini
[Diagnostics]
EnableCanPsConfigProbe=1
CanPsApiOutcomeMask=1
```

По умолчанию маска0. Считанное значение должно быть одним decimal символом
0..7; malformed/hex/overflow значения дают0. Без master flag эксперимент
не включается. Профиль читается на Open, маска сохраняется в новом channel.
Изменение файла не переключает уже открытый канал.

| Бит | Локальный экспериментальный исход |
| --- | --- |
| 1 | Создать PS-local PASS-filter handle |
| 2 | Вернуть успех одиночного exact D8 WriteMsgs, count1 |
| 4 | Создать PS-local periodic handle для exact D8/1000ms |

Для первых сравнений использовать отдельные0/1/2/4, по одному фиксированному
условию на capture. Комбинации3/5/6/7 проверяют сочетания; включение всех
трёх сразу не изолирует gate. Пакетные профили и prerelease не изменяются.

## Узкий контракт

Creation/write success требует observed pins0x030B, baud125000 и отдельного
ProtocolID0x8004. Это условия виртуального эксперимента, не доказанная карта
проводки MY2009 и не alias стандартного CAN.

- Filter: только PASS/type1; mask/pattern ProtocolID8004/DataSize4, flow NULL,
  совпадающие TxFlags0 либо0x100. Pattern укладывается в11-bit при flags0 или
  29-bit при flags0x100; extended zero pattern допустим. Mask — произвольная
  32-bit битовая маска. Создаётся только handle, payload не сохраняется.
- Write: input count1, ProtocolID8004, TxFlags0x100, DataSize12, IDFFFFE,
  D8 + семь нулей. Count возвращается1, но frame не попадает в обычный TX
  logger, backend, bridge, dispatch или RX queue. Zero/batch остаются
  отклонены без разыменования message array.
- Periodic: та же D8 форма и **interval1000ms**. Сохраняется только handle,
  без message/timer/delivery. Иной interval сохраняет прежний отказ, даже
  если допустим в обычном J2534.
- Иные формы, включая B9FB/A3/A6/P3 и control/security, сохраняют прежний
  отказ probe. Новых положительных CEM replies нет.

PS handles отделены от generic FILTER/PERIODIC и payload buffers. Лимиты:
MAX_FILTERS24 и MAX_PERIODIC4. Отдельные положительные PS counters сохраняются
между Open; до переполнения/знаковой границы выдача прекращается. Capacity
failure возвращает ERR_EXCEEDED_LIMIT, не изменяя output ID.

Stop/Clear освобождают PS-local ресурсы и после изменения DATA_RATE. Чужие
или устаревшие handles не затрагивают другой channel. Disconnect/Close
удаляют local state. При mask0 прежние Stop/Clear paths сохраняются.
Стандартные CAN/ISO ресурсы и счётчики не используются. PS ReadMsgs обходит
все pumps/dequeue даже при принудительно заполненном внутреннем состоянии.

## Телеметрия и проверки

`J2534 CAN_PS API outcome channel/mask/operation/pins/baud/shape/status (BE)`

Семь uint32, только закрытые категории. Operation1 — mode snapshot;
2 filter registration;3 Write;4 periodic registration;5/6 Stop;7/8 Clear.
Creation records содержат маску также для отказов/mask0: состояния по
channel/PID/часам не связываются. Shape1 — узкая PASS ID-only форма,
42 — exact D8 (для periodic также1000ms),0 — none/outside envelope.
Shape не является разрешением или подтверждённой read-only semantics.

Старые hardcoded-rejected markers остаются только при фактическом status1.
Success/capacity не записываются как rejected или принятый CAN TX. Existing
`audit_j2534_connect.py` добавляет `can_ps_api_outcomes`: snapshots, injected
successes, rejections, capacity и lifecycle counts отдельно. Успешный outcome:
`simulated_api_success_no_transport`. Transmission/ECU/firing/read-only
approval flags остаются false. Channel/PID/bytes/operands не экспортируются,
source-order ограничен20000 records.

Восемь native/Python групп проверяют strict opt-in/snapshot, независимые биты
и route guard, filter bounds, exact D8/zero-batch, interval1000, lifecycle/
capacity/overflow, no RX/pump/backend и metadata/privacy. Actual x86 runner
имеет отдельный `-ApiOutcomeRegression`: master-off, все восемь масок,
malformed mask, cleanup после смены baud, READ128 и отказ B9FB при полной
маске. Backend requests должны остаться0; прежний runner отдельно сохраняет
13-request fixture.

Client run требует фиксированных версий/hashes GUI/worker/DLL/profile,
direct module binding, одной маски, полного suffix и bounded deadline.
Следующий новый read-only probe после одного изменённого API-исхода поддержит
гипотезу gate; это не доказательство SectorV normal-mode condition или ECU
response. Отсутствие перехода ослабит только конкретную проверенную гипотезу.
В [фактическом filter-only run](../docs/research/VDASH_CAN_PS_FILTER_OUTCOME_RUNTIME_20261103.md)
на source1a78b82 три локальных filter successes не устранили следующий
PS ReadMsgs timeout100ms/disconnect. Write/periodic остались rejected D8,
warning наблюдался, ECU list до deadline не проверен. Direct module binding
подтверждён. Исторический baseline имел другую DLL/worker, поэтому отдельно
выполнен свежий mask0 с теми же source1a78b82/DLL/GUI/worker; профили отличаются
одним символом маски. В mask1 есть3 дополнительных CLEAR_RX после filters,
но сохраняются те же100ms PS timeout/disconnect и обычный backend обмен.
В обоих warning, ECU list не проверен; по одному invocation на условие.
Количества повторов не сравниваются как outcome rates.

В [отдельных D8 runs mask2/mask4](../docs/research/VDASH_CAN_PS_D8_OUTCOMES_RUNTIME_20261103.md)
на тех же DLL/GUI/worker, с direct module binding, mask2 дал3 локальных Write
successes, но последующий periodic оставался rejected. Mask4 дал1 локальный
periodic-registration success; затем появились CLEAR_RX, дополнительный
rejected filter и rejected **D2_40_A6 Write**. После A6 нового Read нет,
A6 не передан и ответа CEM нет. Selector operands logger не сохранял;
значения1A04/1A02 и положительный ответ по аналогии не выводятся.

Все отдельные0/1/2/4 условия проверены в bounded run; это по одному GUI
invocation, с разным количеством полных API-циклов, не outcome rates.
Mask2 warning наблюдался; mask4 Home NOTFOUND/CONNECT наблюдался, отсутствие
warning не доказано. ECU list не проверен. Stop/restore/prefix integrity
подтверждены. Следующий материал — точный A6 selector/условие клиента и
совместимый read-only источник ответа. CI не заменяет фактический UI outcome.
