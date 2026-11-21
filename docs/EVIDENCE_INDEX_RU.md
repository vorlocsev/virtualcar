# Virtual Car — указатель доказательств и технических данных

Этот указатель систематизирует материалы **ветки `development`**, но не объявляет любой архивный результат текущим. Датированный [аудит 21.11.2026](reports/2026-11-21-repository-audit-ru.md) содержит точные HEAD SHA, CI, открытые PR, матрицу acceptance-gates и блокеры. Перед изменением кода проверяйте живое состояние GitHub.

## Откуда начинать

| Задача | Основной источник |
|---|---|
| Краткое описание и команды сборки | [README](../README.md), [README RU](../README_RU.md) |
| Регламент безопасности, работа с ветками | [AGENTS](../AGENTS.md), [чат / GitHub](CHAT_GITHUB_WORKFLOW_RU.md) |
| Планы и критерии завершения | [ROADMAP](ROADMAP.md) |
| Передача следующему сеансу | [NEXT_CHAT](../NEXT_CHAT.md) — исторические точки перепроверять |
| Источники кода, сторонние данные | [PROVENANCE](PROVENANCE.md) |
| Доверенная baseline-ветка | [development](https://github.com/vorlocsev/virtualcar/tree/development), [Actions](https://github.com/vorlocsev/virtualcar/actions) |
| Релизный gate | [Draft PR #2](https://github.com/vorlocsev/virtualcar/pull/2) |

## По функциональным направлениям

| Направление | Исходники, документы и открытые работы |
|---|---|
| Базовая J2534 DLL и P2 Vehicle Core | [emulator/src](../emulator/src), [emulator/README](../emulator/README_RU.md), [tests](../emulator/tests) |
| Синтетический CEM50 CAN B9FB | [CEM50](../emulator/adapters/cem50), [Issue #417](https://github.com/vorlocsev/virtualcar/issues/417) |
| J2534-2 PS и side-by-side провайдер | [Draft #418](https://github.com/vorlocsev/virtualcar/pull/418), [Draft #419](https://github.com/vorlocsev/virtualcar/pull/419) |
| VIDA ReadVin, native логи / атрибуция | [Issue #326](https://github.com/vorlocsev/virtualcar/issues/326), [PR #419](https://github.com/vorlocsev/virtualcar/pull/419), [VIDA аудиторы](../emulator/tools) |
| SectorV, Hardware и ECU маршруты | [B3A318](research/b3a318-xc90-v8-cem-catalog-and-sectorv-routing.md), [B3A319](research/b3a319-sectorv-hardware-client-route-attribution.md) |
| B9FB: структура и пределы | [Identity shape](research/p2-b9fb-identity-shape-audit.md), [Provenance guard](research/p2-b9fb-target-provenance-guard.md) |
| CarCom / VIDA 2014D / T111 / T122 | [VIDA DB applicability](research/spnda-volvo-vida-db-applicability.md), [bounded aggregate](research/vida-t111-t122-bounded-aggregate.md) |
| CEM D2/GGD и модельные поколения | [Variant research](research/vida-cem-d2-variant-local-catalog.md), [B3A318](research/b3a318-xc90-v8-cem-catalog-and-sectorv-routing.md) |
| Ранние CAN исследования | [Early P2](research/p2-can-early-models.md), [SavvyCAN](research/savvycan-dev30.md) |
| Отдельный tracing proxy, OneClick | [proxy](../proxy), [cmd](../cmd) |
| Синтетические C++/C# IPC | [dotnet](../dotnet), [architecture](architecture) |
| Исторические отчёты | [docs/progress/CURRENT.md](progress/CURRENT.md) — не live статус; [research/dev23–25](../research) — архив |

## Классы доказательств

- **CI_EXACT_HEAD** — успешный Actions run с точно указанным исходным SHA и реально выполненными шагами.
- **OWNER_LOCAL** — локальный вывод владельца с указанной веткой/бинарником; не GitHub CI.
- **CLIENT_OBSERVED** — действие/результат SectorV или VIDA, подтверждённый клиентским журналом/экраном с ограничениями атрибуции.
- **SYNTHETIC_ONLY** — байтовые fixture tests, replay, native smoke без подлинного CEM.
- **SOURCE_RESEARCH** — статический анализ клиентских DLL, CarCom, IL или внешних публикаций.
- **NOT_VERIFIED** — нет достаточного прямого доказательства именно заявленного gate.

Каждый новый отчёт должен включать дату, SHA, протокол/скорость/маршрут при необходимости, источник, наблюдаемый результат и **что результат не доказывает**. Не повышайте «13/13 frame delivery» до «VIDA ReadVin PASS», а «ECU request observed» до «ECU identified».

В репозиторий нельзя переносить приватные донорские профили, неразрешённые VIN, сырые VIDA/J2534 логи, пароли, ключи и ECU-дампы. Достоверность исходной клиентской и нативной сессии проверяется отдельно.
