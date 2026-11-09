# P0: отдельный новый сеанс SectorV, J2534 и backend

Инструмент audit_sectorv_fresh_window.py **не запускает** SectorV, не
устанавливает драйверы, не открывает J2534 DLL, не передаёт CAN, не
меняет конфигурацию CEM и не создаёт ответов ECU. Он предназначен
для одного разрешённого лабораторного наблюдения без реальных адаптеров.

## Прямые и периодические J2534-запросы в отчётах

Виртуальный J2534 может отправлять B9FB, A3 или A6 как по прямому
`PassThruWriteMsgs`, так и по расписанию, установленному через
`PassThruStartPeriodicMsg`. Для каждого реально исполненного
периодического такта нативный журнал теперь содержит отдельную
строку `Periodic TX context channel/protocol/flags/baud/time-us (BE)`
и затем `J2534 periodic TX (read-only simulator)`.

`audit_j2534_discovery.py` учитывает такой запрос **только при корректном
контексте непосредственно перед кадром** и помечает его в подробных
транзакциях как `request_origin=periodic_scheduler`. Обычный вызов
имеет `request_origin=direct_write`. В сводке ограниченного окна
учитываются оба типа реальных запросов, поэтому счётчики B9FB теперь
не расходятся только из-за способа отправки. Источники сохраняются
раздельно: периодический тик не считается новым вызовом GUI, а
Flow Control не считается самостоятельным диагностическим запросом.

Текстовые журналы старых DLL без периодического контекста остаются
неподтверждёнными, даже если в backend есть `tx_received`. Связь
транзакций между двумя журналами всё ещё не аттестована независимо;
`delivered` означает получение через J2534, **не принятие VIN**
программой SectorV.

## Короткий сбор P0: один операторский сеанс

Вместо ручного создания JSON можно использовать новый Python-скрипт
emulator/tools/audit_sectorv_operator_session.py. Он повторно использует
проверенные анализаторы журналов, провайдера J2534 и GUI, но **не**
запускает SectorV, не открывает CAN/J2534, не меняет реестр и не
утверждает, что VIN принят клиентом.

В гостевой Windows полностью закройте SectorV, отключите физические
J2534 и выполните из каталога emulator:

~~~powershell
$j = Join-Path $env:TEMP "SectorVVirtualCar.log"
$b = Join-Path $env:LOCALAPPDATA "VirtualCar\dev47-backend.jsonl"
$private = Join-Path $env:USERPROFILE "VirtualCarLab"
New-Item -ItemType Directory -Path $private -Force | Out-Null
$session = Join-Path $private "p0-gui-001" # новое имя для каждого запуска
$collector = ".\tools\audit_sectorv_operator_session.py"
py -3 $collector begin --session-dir $session --j2534 $j --backend $b
~~~

Затем **вручную** откройте настоящий SectorV, выберите виртуальный
адаптер и выполните один краткий **только читающий** сеанс.
Пока клиент открыт, можно сохранить пассивный обезличенный снимок
загруженных модулей:

~~~powershell
$module = Join-Path $session "p0-module.redacted.json"
$ps = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
& $ps -NoProfile -ExecutionPolicy Bypass -File ".\tools\audit_vmware_sectorv_process.ps1" -OperatorSession -OutputFile $module
~~~

После **полного закрытия** SectorV задайте фактические шесть состояний
интерфейса. Значение unknown означает отсутствие достоверного
наблюдения, не успешное подключение:

~~~powershell
$listed = "unknown"      # yes / no / unknown
$selected = "unknown"    # yes / no / unknown
$connection = "unknown"  # connected / failed / not_attempted / unknown
$ecus = "unknown"        # populated / empty / not_opened / unknown
$identity = "unknown"    # displayed / not_displayed / unknown
$errorKind = "unknown"   # none / adapter_missing / connect_error /
                         # vin_read_failed / vehicle_unrecognized /
                         # timeout / other / unknown
$opts = @(
 "finish", "--session-dir", $session, "--j2534", $j, "--backend", $b,
 "--isolated-read-only-vm", "--physical-adapter-disconnected",
 "--adapter-listed", $listed, "--adapter-selected", $selected,
 "--connection", $connection, "--ecu-list", $ecus,
 "--vehicle-identity", $identity, "--error-category", $errorKind,
 "--module-snapshot", $module
)
py -3 $collector @opts
~~~

Если снимок модулей не делался, удалите из массива два последних
элемента, --module-snapshot и $module. При несомненно едином сеансе
можно дополнительно включить --single-run-confirmed. Это **утверждение
оператора**, а не независимая аттестация совместного запуска.

На первом этапе создаётся p0-before.private.json, на последнем
p0-window.redacted.json и p0-triage.redacted.json. Приватный
манифест содержит чувствительные хеши: **не отправляйте его в GitHub
или чат**. В нём также сохраняются приватные отпечатки **полных путей
к двум исходным журналам**. Поэтому `finish` должен использовать
те же два файла, что и `begin`, даже когда оба файла ещё пустые:
подмена путей между фазами теперь приводит к отказу. Смена написания
пути, указывающего на тот же канонический файл, разрешена. Это
не аттестация GUI-сеанса, но защита от случайной подстановки другой
истории журналов. Начинайте новый опыт с нового `begin`: старые
манифесты без привязки путей не поддерживаются.

Отчёты хранят только фиксированные категории и счётчики,
не сырые VIN, CAN, пути или отпечатки. Скрипт отказывает при повторной
попытке создать тот же файл и при неподтверждённой изоляции; GUI-успех
и идентичность OEM остаются not_verified. Подробный ручной сценарий ниже
по-прежнему поддерживается.

## До короткого запуска SectorV в изолированной VM

Полностью закройте SectorV и другие программы, которые могут писать в
эти же журналы. Подтвердите snapshot и отсутствие физического J2534.
Не выполняйте PIN, SecurityAccess, сброс, программирование, изменение
конфигурации, запись ECU.

Из каталога emulator выполните PowerShell:

    $tool = ".\tools\audit_sectorv_fresh_window.py"
    $j = Join-Path $env:TEMP "SectorVVirtualCar.log"
    $b = Join-Path $env:LOCALAPPDATA "VirtualCar\dev47-backend.jsonl"
    $private = Join-Path $env:USERPROFILE "VirtualCarLab"
    New-Item -ItemType Directory -Path $private -Force | Out-Null

    # Каждый сеанс требует новых имён: отчёт никогда не перезаписывается.
    $manifest = Join-Path $private "bin7-before-01.private.json"
    $report = Join-Path $private "bin7-fresh-01.redacted.json"
    py -3 $tool baseline --j2534 $j --backend $b --manifest $manifest

Baseline сохраняет размеры, признак конца строки и SHA-256 старых
журналов, а также **приватный снимок зарегистрированного 32-битного J2534
провайдера**: категорию PE32/x86, SHA-256 нормализованного локального пути
и SHA-256 бинарника (если он доступен). Это **приватный** файл.
Не копируйте его в GitHub или чат. Реальный путь и DLL в manifest
не записываются, но отпечатки файлов остаются чувствительными.
Проверка читает единственный канонический ключ реестра без изменений,
не загружает DLL и не запускает SectorV.

После успешного baseline выполните **один** короткий read-only сеанс
SectorV с явно выбранным виртуальным J2534. Запишите отдельно
наблюдения в интерфейсе: выбран ли адаптер, состояние «Подключено»,
есть ли список ECU и текст ошибки VIN. После сеанса полностью
закройте SectorV и связанные процессы.

## Пока SectorV открыт: проверка загруженной DLL (необязательный шаг P0)

Если SectorV уже запущен в **той же изолированной гостевой Windows**,
до его закрытия можно сделать пассивный снимок модулей процесса. Эта команда
не запускает SectorV, не открывает диагностическое устройство, не изменяет
реестр и не загружает DLL сама. Выполняйте из каталога `emulator` в
PowerShell 5.1:

```powershell
$probe = ".\tools\audit_vmware_sectorv_process.ps1"
$moduleReport = Join-Path $private "p0-sectorv-module-01.redacted.json"
# Необязательно: укажите локальный эталонный файл, если его происхождение
# известно отдельно. Путь НЕ включается в результат.
$referenceDll = "C:\VirtualCarLab\Reference\VirtualCarJ2534.dll"
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -NoProfile -ExecutionPolicy Bypass -File $probe `
    -OperatorSession -ReferenceDll $referenceDll -OutputFile $moduleReport
```

Если эталонного файла нет, уберите `-ReferenceDll $referenceDll`: результат
будет `installed_vs_reference_dll=not_compared`, а не ложное совпадение.
Запускайте проверку **пока GUI ещё открыт**. Имя `SectorV.exe` и совпадение
путей загруженных модулей доказывают только факт локального наблюдения,
**не подлинность бинарника SectorV**, не использование DLL при конкретном
запросе и не принятие VIN. Запуск в CI зафиксирует только процессы CI,
а не другой гостевой Windows; флаг `-OperatorSession` лишь отражает
намерение оператора, не аттестует машину.

Категории в новом отдельном отчёте
`virtualcar-sectorv-process-binding-operator-v1`:

- `observation`: зарегистрированная DLL присутствует среди модулей
  совпавшего по имени процесса, отсутствует в доступном списке,
  список недоступен, либо клиент не наблюдался;
- `installed_vs_reference_dll`: `exact_bytes_at_snapshot`,
  `different_bytes_at_snapshot`, `comparison_unverifiable` или
  `not_compared`. Это сравнение двух локальных файлов **на момент снимка**.
  Оно не удостоверяет архитектуру, происхождение эталона, версию или то,
  что эталон собран из CI-коммита;
- `next_safe_gate`: следующий консервативный шаг. Даже при совпадении
  все поля принятия автомобиля останутся `not_verified`.

Отчёт создаётся **только с новым именем**, вне дерева исходников.
Не храните в репозитории приватные базовые манифесты, логи или локальные
бинарники. Обезличенный отчёт можно отдельно проверить перед передачей.
Этот снимок **не присоединяется автоматически** к J2534-транзакциям:
между ним, логами и GUI нет независимо установленного общего ID сеанса.

## После выхода SectorV

    # Только при подтверждённом оператором одном изолированном сеансе.
    py -3 $tool analyze --j2534 $j --backend $b --manifest $manifest --output $report --operator-one-run-confirmed

Если гарантировать границу одного запуска нельзя, НЕ указывайте
флаг --operator-one-run-confirmed.

Инструмент проверяет неизменность старых префиксов по SHA-256, отвергает
усечённые или изменённые журналы, ограничивает добавленные данные
16 MiB на файл и игнорирует неполные граничные строки. Существующие
анализаторы обрабатывают новые строки **в памяти**, без создания
временных файлов с CAN/VIN. Исходные логи не меняются.

В новом обезличенном JSON остаются только:
- числа новых байтов и полных строк без имён файлов;
- категории J2534 Connect;
- статусы D2 A3/A6/B9F0/B9FB/B9FC на CEM 0x40 и 0x50;
- число доставленных RX по фиксированным корзинам;
- отдельная, несопоставленная напрямую backend coverage;
- client_vehicle_identity_accepted=not_verified;
- cross_log_transaction_attribution=not_established;
- `registered_provider.binary_endpoint_consistency`: `same_at_endpoints_only`,
  `changed_between_endpoints`, `provider_state_changed` либо
  `not_verified`, без путей, SHA и содержимого DLL.

Отсутствие лога не равно отказу ECU. Если исходный файл растёт
во время анализа, меняется его исторический префикс или превышен
лимит, скрипт должен остановиться. Даже если пользователь
подтвердил один сеанс, это не даёт общей per-request идентичности
между независимыми логами.

## Следующая интерпретация

1. Есть ли реальные TX 0x40/0x50 B9FB в новом окне?
2. Выданы ли no_fixture, unsupported, partial_rx, timeout или delivered?
3. Если delivered, сколько именно RX получил J2534-клиент?
4. Совпало ли это с отдельным наблюдением сообщения «Не удалось
   получить VIN автомобиля» в SectorV?
5. Ни один результат не разрешает выдумывать B9FB/B9F0/A3/E3
   или утверждать OEM-идентификацию XC90 V8 MY2009.

**Ограничение:** сравнение двух отпечатков не доказывает, что
провайдер оставался неизменным *внутри* сеанса, что SectorV загрузил
именно эту DLL или что программа приняла VIN. Снимок имени и хеша не
является независимым доказательством одной гостевой Windows.
Результат интерфейса SectorV нужно фиксировать отдельно в том же
лабораторном сеансе. `client_ui_result` остаётся `not_observed_by_this_tool`.
Выполняйте оба этапа в одной изолированной Windows, не в CI-runner
вместо неё. Доступность зарегистрированного провайдера на CI-runner
не означает наличие SectorV GUI.

Инструмент исследовательский; сборки и релизы Virtual Car здесь
не публикуются.


## Совмещение обезличенного J2534-окна с наблюдением GUI

После получения локального `bin7-fresh-01.redacted.json` отдельно зафиксируйте
шесть категорий состояния интерфейса SectorV в **новом локальном**
`sectorv-ui-private.json`. Пример для случая, когда адаптер выбран,
подключение отображается, VIN не показан, а список ECU пуст:

```json
{
  "schema_version": "virtualcar-sectorv-ui-observation-v1",
  "client": "SectorV",
  "scenario": "P2_MY2009_lab",
  "source": "human_ui_observation",
  "run_scope": "single_vm_client_run",
  "read_only": true,
  "physical_adapter_disconnected": true,
  "observations": {
    "adapter_listed": "yes",
    "adapter_selected": "yes",
    "connection": "connected",
    "ecu_list": "empty",
    "vehicle_identity": "not_displayed",
    "error_category": "vin_read_failed"
  }
}
```

Это **пример формата**, а не новый факт о SectorV. Не копируйте пример
как результат испытания, если фактический экран показал другое состояние.
Никаких VIN, CAN-кадров, скриншотов, текста ошибок, путей или идентификаторов
в этот JSON не добавляйте.

В той же изолированной гостевой Windows с Python 3.12:

```powershell
$tool = ".\tools\audit_sectorv_ui_window_triage.py"
$ui = Join-Path $private "sectorv-ui-private.json"
$triage = Join-Path $private "bin7-one-run-triage.redacted.json"
# При наличии снимка модулей из этого сеанса передайте его третьим входом.
# Без снимка просто уберите --module-snapshot и соответствующий аргумент.
py -3 $tool --window-report $report --ui-observation $ui --module-snapshot $moduleReport --output $triage --operator-same-run-confirmed
```

**Флаг `--operator-same-run-confirmed` допустим только когда оба источника
действительно относятся к одному изолированному сеансу** и у исходного
анализатора уже установлен `--operator-one-run-confirmed`. Без
подтверждения запустите без флага; итог будет `run_pairing=unpaired`.
Для одиночного исторического скриншота флаг недопустим.

При переданном `--module-snapshot` итоговый JSON отдельно содержит
`operator_module_snapshot`: факт локального наблюдения совпавшего по
имени процесса, категорию сравнения зарегистрированной и эталонной DLL,
а также следующий безопасный шаг по этому **отдельному** источнику.
Снимок необязателен; старый режим двух входных файлов сохранён.
Анализатор проверяет точную схему, категории, ограничения размера
и соответствие рекомендаций наблюдениям. Локальные пути, VIN,
имена модулей и хеши не принимаются и не копируются.

**Ограничение:** отдельный снимок, даже со значением
`registered_library_loaded_in_name_matched_client`, не является
аттестацией того, что это подлинный SectorV в той же гостевой машине,
что он использовал DLL для конкретных J2534-запросов или что VIN принят.
Поля `j2534_binary_loaded_in_gui_client=not_verified`,
`transaction_level_correlation=not_established` и
`client_vehicle_identity_accepted=not_verified` сохраняются.
`operator_module_snapshot.next_safe_gate` не подменяет основной
`first_next_gate` анализа протокола и интерфейса.

Результат `audit_sectorv_ui_window_triage.py` полностью категоризирован.
Он покажет количество запросов B9FB и запросов с ненулевым числом RX
в пределах отчёта, состояние GUI и приоритет проверки.
Если J2534-журнал отсутствует, вывод будет **«получить журнал»**, а не
**«клиент не запросил VIN»**. Если в новом окне были отброшены неполные
начальная или конечная строки и среди оставшихся полных записей нет B9FB,
анализатор выбирает `review_discarded_j2534_line_boundaries`, а не
`review_absent_b9fb_in_bounded_j2534_window`. Поле
`j2534_discarded_partial_boundary_lines` отмечает эту потерю границ.
Такая метка **не означает**, что B9FB точно присутствовал в отброшенной
строке. При наличии проверенной полной записи B9FB она продолжает
учитываться, но не подтверждает принятие VIN клиентом.
Совпадение DLL в двух точках не доказывает,
что SectorV загрузил эту DLL или что она была неизменной весь сеанс.

Даже при `run_pairing=operator_asserted_not_independently_verified`
инструмент оставляет `transaction_level_correlation=not_established`,
`client_vehicle_identity_accepted=not_verified` и
`oem_vin_and_ecu_verified=false`. Нужны независимые данные клиента
и допустимые диагностические образцы для подтверждения OEM-идентификации.
