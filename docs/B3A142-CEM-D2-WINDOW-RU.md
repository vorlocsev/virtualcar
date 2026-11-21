# B3A142: ограниченный аудит ответа CEM на D2 B9F0/B9FB

## Что подтверждено

В локальном отчёте владельца B3A138 зафиксированы 20 запросов D2, включая CEM 0x40/B9F0 и CEM 0x40/B9FB на 125000 бит/с. Для них зарегистрированы "no validated response fixture", но отсутствуют "P2 D2 read-only recorded frames staged" и "P2 D2 delivered". В статическом INI присутствуют нулевые количества кадров D2_40/B9F0 и B9FB, тогда как D2_50/B9FB содержит 13 синтетических кадров. Эти наблюдения не подтверждают положительное чтение ECU в VIDA.

В исходнике emulator/src/virtualcar.c новый запрос D2 отменяет предыдущую незавершённую D2-передачу на том же J2534 канале. "PassThruReadMsgs -> delivered" включает **любые** кадры, а "P2 D2 delivered channel/generation/frame/... (BE)" отдельно идентифицирует кадры staged D2. GetTempPathA вызывается внутри процесса, загрузившего DLL. Весь журнал может содержать приватные данные и не должен публиковаться.

## Инструмент

emulator/tools/audit_vida_b3a142_cem_d2_window.py читает только последние 8 MiB нативного журнала (максимум 16 MiB по явному параметру), не копирует журнал и не вызывает VIDA/J2534. Выделяет CEM 0x40/0x50, B9F0/B9FB и отличает:

- missing_validated_fixture и no_matching_target_fixture;
- strict_bus_rejected;
- staged_not_delivered_in_bounded_span;
- staged_then_clear_rx_seen_not_causal_proof;
- native_d2_delivered_not_vida_accepted;
- no_categorized_outcome.

События сопоставляются **только по одинаковому текстовому [PID=... HOST]** до следующего D2-маркера этого же префикса или конца ограниченного окна. Это не доказательство единого канала, идентичности процесса, фактической VIDA, корректности ECU данных или причинности CLEAR_RX_BUFFER.

Не выводятся VIN, PID, хост, пути, байты кадров, ResponseId и сырые строки. Отчёт содержит только категории и количества событий. При обрезанном окне или несвязанном логгере возможны неполные выводы.

## Команды

Из доверенной локальной копии репозитория:

~~~powershell
py -3 .\emulator\tools\audit_vida_b3a142_cem_d2_window.py --native-log "$env:LOCALAPPDATA\Temp\SectorVVirtualCar.log"
py -3 -m unittest discover -s emulator/tests -p test_audit_vida_b3a142_cem_d2_window.py -v
~~~

При обнаружении missing_validated_fixture нельзя автоматически переносить 13 кадров CEM_50/B9FB в CEM_40/B9FB или добавлять чужие идентификационные данные B9F0. Для внедрения новых фикстур требуется отдельная доказательная проверка их формата, маршрута, CAN ID и J2534-фильтра.

## Критерии готовности

- Офлайн-тесты классификатора 16/16 PASS.
- Данные оригинального VIDA и неизменённый INI не модифицируются.
- Применение к приватному нативному журналу на компьютере владельца пока **не выполнено**.
- Реальная доставка ответов CEM и результат DIAGNOSTICS → NETWORK **не доказаны**.
