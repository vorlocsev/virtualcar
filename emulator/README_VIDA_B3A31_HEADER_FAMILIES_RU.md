# B3A31: семейства заголовков и учёт несвязанных TX-маркеров VIDA

Задача [#322](https://github.com/vorlocsev/virtualcar/issues/322) продолжает
read-only исследование **записей журнала**, а не реализацию ECU transport.
`tools/audit_vida_b3a31_header_families.py` читает существующий файл и создаёт
новый категориальный JSON. Исходный журнал не изменяется.

В issue владелец сообщил результат своего локального B3A30-запуска:
36 unbound TX-маркеров, 18 стрелок без поддержанного scope и 18 ошибок
`WriteMsgs ERR_NOT_SUPPORTED`. Это переданные владельцем агрегаты;
**оригинальный журнал NOT TESTED by Codex**. Равенство двух счётчиков по 18
не связывает маркеры с ошибками. Остальные unbound-записи нельзя объяснять
одним вычитанием: B3A31 проверяет отдельные приращения счётчиков на каждой
обработанной строке и сверяет суммы частей.

## База и зависимость

Новая ветка начинается от `development`
`98bfae3ade3a97cb955d6cd33f887569e474bad9`.
Необходимая зависимость B3A30 — файл
`tools/audit_vida_b3a30_tx_coverage.py` и его синтетическая регрессия
`tests/test_audit_vida_b3a30_tx_coverage.py`, перенесённые без изменений из
[Draft PR #321](https://github.com/vorlocsev/virtualcar/pull/321), точный HEAD
`4f46457592b77195e6def7aaedc74afa835a0a21`.
Это явная зависимость нового PR; ветка и содержимое #321 не меняются.

[Draft PR #319](https://github.com/vorlocsev/virtualcar/pull/319) остаётся
на `50040f5d11aa2bdfce202db55fa1a638d4d49a9a`.
Ни #319, ни #321 не перебазируются и не сливаются. B3A31 не меняет
`virtualcar.c`, J2534 runtime, флаги, ObserverOnly, DLL, установку VIDA,
Registry32 или автомобиль. ECU/VIN response fixtures не создаются.

## Что означают счётчики

`b3a30_inventory` сохраняет категориальную инвентаризацию базового аудитора.
`log_error_categories` содержит вычисленные категории ошибок. Статические
claims B3A30 про необходимость будущего owner-local запуска не переносятся
в новый отчёт: они не описывают факт текущего выполнения B3A31.

`marker_scope_counts` разделяет `ARROW` и `ALTERNATE`, а внутри каждого
типа — `EXACT_COMPONENT`, `OTHER_COMPONENT`, `UNSCOPED`. Для каждой ячейки:

```text
total = active_write_present + base_unbound
```

`active_write_present` означает только наличие активного `_Write` у
базового парсера на этом шаге. Это **не** подтверждение строгого TX.
Повреждённый, дублированный или нарушающий последовательность маркер,
а также маркер другого компонента могут иметь `base_unbound=0`.
Результат в `log_error_categories` сохраняет эти ограничения.

`unbound_reason_counts` имеет те же измерения типа и scope. Причина
описывает наблюдаемое состояние парсера, а не причину ошибки драйвера:

| Категория | Граница интерпретации |
| --- | --- |
| `UNKNOWN_THREAD_IDENTITY` | Поддержанная идентичность потока отсутствует; числа из другого семейства заголовков не используются для связи. |
| `NO_PENDING_SAME_THREAD_WRITE` | Подходящего активного Write того же потока нет. |
| `LAST_WRITE_CLEARED_BY_LIFECYCLE` | Наблюдавшееся событие жизненного цикла удалило прежнего Write-кандидата. |
| `LAST_WRITE_CLEARED_BY_INTERVENING_CALL` | Состояние прежнего Write прервал промежуточный вызов. |
| `LAST_WRITE_CLEARED_BY_TERMINAL_ERROR` | Прежнее состояние Write удалено при обработке terminal error. |
| `LAST_WRITE_CLEARED_BY_OTHER_RECORD` | Другая scoped-запись, например пустой RX-маркер, удалила прежнее состояние Write. |
| `LAST_WRITE_EXPIRED` | Прежнее состояние вышло за ограниченное окно базового парсера. |
| `CLOCK_MISSING_OR_BACKWARDS` | Отсутствующее или обратное время разорвало допустимую связь. |
| `UNKNOWN_LAYOUT_BARRIER` | Неизвестный формат не позволил сохранить прежнюю связь. |

Для каждой ячейки сумма причин равна её `base_unbound`. Сумма всех
unbound-частей `ARROW` и `ALTERNATE` должна совпасть с
`b3a30_inventory.unbound_tx_records`. Также сверяются итоги по scope,
типу маркера, семейству заголовка и размеру каждой proximity-группы.
Несогласованные приращения, неизвестная схема или нарушенные суммы
отклоняются; отчёт не выдаёт такой результат за доказанный учёт.
`bookkeeping.all_invariants_passed=true` устанавливается после проверки сумм.

Независимая ось `marker_syntax_counts` разделяет `VALID_SYNTAX`,
`MALFORMED_SYNTAX`, `UNVALIDATED_IDENTITY`. Валидный синтаксис payload не
устанавливает наличие активного Write, корректность последовательности,
смысл неизвестного заголовка или реальную передачу.

## Семейства заголовков — только синтаксис

`header_family_counts` использует фиксированный набор:

- `EXACT_COMPONENT_BRACKETS`: точный bracketed-компонент
  `J2534ChannelMana` с поддержанными полями потока и logger;
- `OTHER_COMPONENT_BRACKETS`: поддержанная bracketed-форма с другим
  компонентом; его имя не выводится;
- `LEGACY_NUMERIC_PREFIX`: время и два числовых поля фиксированной
  ширины 4/6 hex-символов без bracketed-компонента;
- `BARE_ARROW`: стрелка без заголовка;
- `OTHER_OR_UNKNOWN`: прочие или неполные формы.

Legacy-форма взята из существующей синтетической проверки формата.
Она не устанавливает смысл числовых полей и не превращает их в thread,
PID, канал или доказательство реального вызова. Обнаружение семейства
не подтверждает происхождение или подлинность входного файла.

## Близость строк не является связью J2534

`source_order_proximity` рассматривает две группы:
`UNSCOPED_ARROWS` и `BASE_UNBOUND_ARROWS`. Они **пересекаются**;
складывать их как независимые части общего числа маркеров нельзя.

Для каждой группы отдельно считаются расстояния до предыдущего и
следующего распознанного параметризованного Write и до предыдущей и
следующей записи Write error. Направления:
`PRECEDING_WRITE`, `FOLLOWING_WRITE`, `PRECEDING_WRITE_ERROR`,
`FOLLOWING_WRITE_ERROR`. Корзины: `ROWS_0_5`, `ROWS_6_20`,
`ROWS_21_100`, `ROWS_OVER_100`, `UNKNOWN`.

Write-reference включает распознанную параметризованную форму из любого
scope, включая форму с неверными числовыми полями. Error-reference —
буквальное упоминание `WriteMsgs ERR_NOT_SUPPORTED`, учтённое B3A30;
это не весь набор кодов ошибок и не доказательство реального вызова.

Это только **порядок исходных строк внутри одной logsession**.
`UNKNOWN` означает отсутствие подходящей записи в данном направлении
того же сеанса. Соседство не приписывает маркер потоку, ChannelID, ошибке
или успешной передаче и не восстанавливает отсутствующий timestamp.
Переход через полночь не доказывает дату события. Для базовой корреляции
сохраняются окна Write→error 20 строк/5000 мс и Connect-кандидата
200 строк/30000 мс; новая logsession разрывает состояние.

## Claims и конфиденциальность

Успешное выполнение на переданном входе отражают
`audit_execution_on_supplied_input=COMPLETED` и
`log_error_categories_computed=true`. Это результат работы программы,
а не подтверждение того, что вход действительно является оригинальным
журналом VIDA: `input_authenticity=NOT_VERIFIED`,
`actual_transport=UNVERIFIED`.

JSON содержит только фиксированные категории и агрегаты. В нём нет
исходных префиксов и строк, timestamp/thread/PID, payload, CAN ID, VIN,
script names, путей, идентификаторов, хешей исходного текста или примеров
строк. Инструмент не может удостоверить успешный PassThruConnect,
локальный ACK, B9FB/B9F0 authenticity, OEM ECU RX или принятие VIN.

Ввод ограничен 32 МиБ, 200000 строками и 32768 байтами на строку.
Используется строгий UTF-8 с допустимым BOM; последняя строка должна
заканчиваться переводом строки. Повреждённый, oversized или незавершённый
ввод отклоняется с краткой ошибкой без содержимого и путей.
Оригинальный журнал ради результата не перекодируется и не редактируется.
JSON создаётся эксклюзивно: существующий файл, включая входной файл,
не перезаписывается. Каталог результата заранее контролирует владелец.
Число отслеживаемых потоков и состояний также ограничено базовым парсером
и overlay; превышение лимита 256 отклоняется.

## Синтетические проверки: Windows PowerShell 5.1 / Python 3.12

Из корня checkout новой ветки, без приватных данных:

```powershell
py -3.12 --version
py -3.12 -m unittest discover -s emulator/tests -p test_audit_vida_b3a31_header_families.py -v
if ($LASTEXITCODE -ne 0) { throw 'B3A31 synthetic tests failed' }
py -3.12 -m unittest discover -s emulator/tests -p test_audit_vida_b3a30_tx_coverage.py -v
if ($LASTEXITCODE -ne 0) { throw 'Pinned B3A30 regression failed' }
py -3.12 -m unittest discover -s emulator/tests -p test_audit_vida_text.py -v
if ($LASTEXITCODE -ne 0) { throw 'VIDA text regression failed' }
py -3.12 -m unittest discover -s emulator/tests -p test_audit_j2534_discovery.py -v
if ($LASTEXITCODE -ne 0) { throw 'J2534 discovery regression failed' }
```

Фактически выполненные команды и результаты фиксируются в новом Draft PR.
Эти проверки не запускают оригинальную VIDA, VMware, J2534 DLL или DiCE.
Специальные задания на persistent self-hosted runner не требуются.

## Следующая команда только для владельца, opt-in

После review владелец может выполнить команду на исходной машине.
Ниже указан существующий штатный путь VIDA; выходной путь — вымышленный
пример нового файла в заранее созданном приватном каталоге владельца.
**Эта команда не исполнялась Codex на оригинальном журнале.**

```powershell
$vidaLogPath = 'C:\Vida\System\Log\Diagnostics\VIDA.log'
$ownerOutputPath = 'C:\OwnerPrivate\Reports\B3A31-new.json'
& py -3.12 .\emulator\tools\audit_vida_b3a31_header_families.py `
    --vida-log $vidaLogPath --output $ownerOutputPath
if ($LASTEXITCODE -ne 0) { throw 'B3A31 fail-closed; output not accepted' }
```

Извлекайте только агрегированный JSON. Не загружайте исходный журнал,
строки, payload или промежуточные частные файлы в issue, PR или artifacts.
До отдельного owner-local B3A31 результата связь исходных 36 маркеров с
18 ошибками не установлена. Успех синтетических тестов не меняет этого.
