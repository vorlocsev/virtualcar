# P0: отдельный новый сеанс SectorV, J2534 и backend

Инструмент audit_sectorv_fresh_window.py **не запускает** SectorV, не
устанавливает драйверы, не открывает J2534 DLL, не передаёт CAN, не
меняет конфигурацию CEM и не создаёт ответов ECU. Он предназначен
для одного разрешённого лабораторного наблюдения без реальных адаптеров.

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
py -3 $tool --window-report $report --ui-observation $ui --output $triage --operator-same-run-confirmed
```

**Флаг `--operator-same-run-confirmed` допустим только когда оба источника
действительно относятся к одному изолированному сеансу** и у исходного
анализатора уже установлен `--operator-one-run-confirmed`. Без
подтверждения запустите без флага; итог будет `run_pairing=unpaired`.
Для одиночного исторического скриншота флаг недопустим.

Результат `audit_sectorv_ui_window_triage.py` полностью категоризирован.
Он покажет количество запросов B9FB и запросов с ненулевым числом RX
в пределах отчёта, состояние GUI и приоритет проверки.
Если J2534-журнал отсутствует, вывод будет **«получить журнал»**, а не
**«клиент не запросил VIN»**. Совпадение DLL в двух точках не доказывает,
что SectorV загрузил эту DLL или что она была неизменной весь сеанс.

Даже при `run_pairing=operator_asserted_not_independently_verified`
инструмент оставляет `transaction_level_correlation=not_established`,
`client_vehicle_identity_accepted=not_verified` и
`oem_vin_and_ecu_verified=false`. Нужны независимые данные клиента
и допустимые диагностические образцы для подтверждения OEM-идентификации.
