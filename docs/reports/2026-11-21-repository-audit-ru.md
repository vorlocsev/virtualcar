# Virtual Car — аудит репозитория и доказательств (21.11.2026)

> **Снимок состояния, а не сертификат автомобиля.** Основание: GitHub `vorlocsev/virtualcar`, ветки `main`/`development`, PR, Issues, Actions и документы, просмотренные 2026-11-21. Статусы разных SHA, процессов, автомобилей и испытаний нельзя объединять в один «PASS». Исходный код эмулятора в этой задаче не менялся.

## 1. Краткий итог

Virtual Car — экспериментальный **Windows x86** виртуальный J2534-адаптер/эмулятор для read-only исследования Volvo P2 XC90 V8 MY2009. В `development` находится исходник эмулятора на основе предоставленной владельцем v0.3.6.6 и диагностические средства; `main` содержит более старый reviewed baseline с трассирующим прокси. Проект не связан с Dvinholm.

На `development` подтверждены сборка, регрессии и лабораторное воспроизведение синтетического 13-кадрового CEM50 B9FB. J2534-2 PS реализован в отдельных Draft PR и прошёл **локальную x86-проверку владельца**, но не интегрирован в доверенный `development`. Подлинное сквозное чтение VIN оригинальной VIDA, ответ Hardware, ECU identification, T111/T122 и физический J2534 **не подтверждены**.

## 2. Точные опорные версии

| Объект | Состояние на момент аудита | Доказательство |
|---|---|---|
| `main` HEAD | `f2aac74407611a5e30c5cb604b6421a515efb10f` | [Коммит](https://github.com/vorlocsev/virtualcar/commit/f2aac74407611a5e30c5cb604b6421a515efb10f) |
| `development` HEAD | `e86ff1f0ec7e02c7bcdc2c512003c3f5c450414f` | [Коммит](https://github.com/vorlocsev/virtualcar/commit/e86ff1f0ec7e02c7bcdc2c512003c3f5c450414f) |
| Доверенный CI `development` | `44871560856`, push, completed / **success**, именно SHA `e86ff1f0...` | [Actions](https://github.com/vorlocsev/virtualcar/actions/runs/44871560856) |
| Ветка → `main` | [Draft PR #2](https://github.com/vorlocsev/virtualcar/pull/2), открыт, не слит | GitHub PR |
| J2534-2 PS реализация | [Draft PR #418](https://github.com/vorlocsev/virtualcar/pull/418), HEAD `9ab3738d6c53442f83c57727f6eaaf44e383c618`, base `development` | GitHub PR |
| Отдельный PS-провайдер | [Draft PR #419](https://github.com/vorlocsev/virtualcar/pull/419), HEAD `04d94f928108ab93600c2f00bfd42d379402e351`, *stacked* на #418 | GitHub PR |

Сравнение GitHub `main...development`: **diverged**, `development` на 438 коммитов впереди и 58 позади `main` в момент запроса. Это не линейная «версия релиза». Список файлов compare ограничивается выдачей API; нельзя трактовать его как полный аудит каждого изменения. HEAD и PR нужно перепроверять перед следующим решением.

## 3. Карта исходников: что чем является

| Область | Назначение и источник | Граница доказательства |
|---|---|---|
| `emulator/src/virtualcar.c`, `emulator/src/p2core/` | Реальный исходник лабораторной J2534 DLL на `development`, наблюдательный P2 Vehicle Core, D2 и ECU-фикстуры | Не OEM-прошивка CEM; не подтверждает приёмку клиента |
| `emulator/adapters/cem50/` | Отдельный классический CEM50 J2534-1 провайдер, синтетический профиль, установочный скрипт и native smoke | Classic CAN B9FB ≠ поддержка J2534-2 PS или ReadVin |
| PR #418 / #419 | PS-протоколы/пины и отдельный side-by-side адаптер | Код и действия в PR **ещё не в `development`**; локальные доказательства отдельно |
| `proxy/`, `cmd/oneclick/` | Наследованный dev26 J2534-прокси, трассировка и GUI | Прокси не является эмулятором автомобиля |
| `emulator/tools/`, `emulator/tests/` | Скрипты аудита VIDA/SectorV/J2534, тесты, synthetic fixtures | Валидатор, матчинг и C/Go/Python PASS не равны GUI acceptance |
| `dotnet/`, `emulator/managed/` | Read-only C++/C# и синтетическая IPC/Host-инфраструктура | Не доказанный рабочий доступ к физическому CEM |
| `docs/research/` | Поисковые и статические исследования D2, CarCom, SectorV, источники | Кандидатные ECU/маршруты — не живые ECU-ответы |
| `research/dev23–dev25/` | Исторические снимки | Не текущий runtime |

Ограничения происхождения: [PROVENANCE](../PROVENANCE.md), [README emulator](../../emulator/README_RU.md), [основной README](../../README.md).

## 4. Единая таблица acceptance-gates

| Gate / тема | Проверенный результат | Статус и что ещё не доказано | Опорные материалы |
|---|---|---|---|
| Сборка и регрессии доверенного `development` | VMware workflow **success** на точном SHA `e86ff1f0...` | **CI PASS для указанного SHA**, не для Draft #418/#419 и не OEM | [Run #44871560856](https://github.com/vorlocsev/virtualcar/actions/runs/44871560856) |
| CEM50 классический CAN, D2 B9FB | Синтетическая фикстура, 13/13 кадров в native x86 smoke; включён в доверенный baseline | **Synthetic/native PASS**. Не подлинный MY2009 ECU-профиль и не принятый VIDA VIN | [Issue #417](https://github.com/vorlocsev/virtualcar/issues/417), [CEM50](../../emulator/adapters/cem50/README_RU.md) |
| J2534-2 `CAN_PS` / `ISO15765_PS` | Владелец сообщил для exact PR #418: 1089 Python tests, OK (1 skipped); C host, PE32 x86, isolated native PS B9FB 13/13, F190, разделение HS/MS и `CEM50_PS_ALL_PASS` | **OWNER_LOCAL PASS, не GitHub CI**. Не интегрировано в `development`; клиентское ReadVin не проверено | [PR #418](https://github.com/vorlocsev/virtualcar/pull/418) |
| Отдельная регистрация CEM50 PS | Для Draft #419 сообщены локальные dry-run/Registry32 readback, затем отдельный PS provider установлен в VMware и присутствует в выборе инструмента VIDA | **OWNER_LOCAL installation/UI observation**. Успешные live `PassThruOpen/Connect`, выбор DLL в конкретном сеансе и ECU RX не доказаны | [PR #419](https://github.com/vorlocsev/virtualcar/pull/419) |
| Оригинальная VIDA: ReadVin | Исторически в другом F114-сеансе были положительные RX, но GUI отклонил VIN по контексту Partner Group; позже VIDA показала историю/профиль с CEM50 PS | **NOT VERIFIED** в актуальной PS-сессии. История/ввод VIN не означает автоматическое чтение | [PR #357](https://github.com/vorlocsev/virtualcar/pull/357), [PR #419](https://github.com/vorlocsev/virtualcar/pull/419) |
| Оригинальная VIDA: Diagnostics / Network | В интерфейсе видна эталонная сеть с цветными ECU; поле идентификации пустое | **UI навигация наблюдалась; ECU ID NOT VERIFIED** | [PR #419](https://github.com/vorlocsev/virtualcar/pull/419) |
| SectorV D2 VIN transport | В клиентском журнале приняты 13 кадров B9FB по `0x50/500k`; это отличное от VIDA наблюдение | **Transport observed; vehicle/OEM identity NOT VERIFIED** | [B3A319](../research/b3a319-sectorv-hardware-client-route-attribution.md) |
| SectorV Hardware | Клиентский Hardware 0x50/500k и 0x40/125k завершился no-reply; в других логгер-группах наблюдались запросы B9F0 к разным адресам | **Hardware FAIL в наблюдаемой попытке; ECU-response/identity NOT VERIFIED**. Нельзя писать «B9F0 вообще не запрашивался» | [B3A319](../research/b3a319-sectorv-hardware-client-route-attribution.md), [B3A318](../research/b3a318-xc90-v8-cem-catalog-and-sectorv-routing.md) |
| CarCom, T111/T122, варианты CEM D2/GGD | Статические каталоги, кандидаты, offline-join и route audits | **RESEARCH ONLY**; фактическая выбранная VIDA последовательность и принятые ответы T111/T122 не установлены | [ROADMAP](../ROADMAP.md), [CarCom research](../research/spnda-volvo-vida-db-applicability.md) |
| Физический J2534 / реальный XC90 V8 MY2009 | Нет проверенного соответствующего испытания | **NOT TESTED** | [ROADMAP](../ROADMAP.md) |

**Важно для B9FB:** опубликованный 13-кадровый пример содержит транспортные заголовки D2, `50 F9 FB`, бинарный префикс и текстовые поля; 88 байт — длина именно разобранного примера, а не универсальная спецификация всех CEM. Ряд полей не расшифрован. Для синтетического XC90 изменённые VIN/шасси и остальная донорская структура **не являются OEM-аттестацией MY2009**. См. [проверку формы/идентичности](../research/p2-b9fb-identity-shape-audit.md).

## 5. Самые свежие наблюдения VIDA: не смешивать источники

По сведениям [Draft #419](https://github.com/vorlocsev/virtualcar/pull/419) владелец показал оригинальную VIDA на странице Vehicle Profile с CEM50 PS и затем Diagnostics/Network. Последующий bounded аудит B3A46 не обнаружил ожидаемых native-маркеров в просмотренных хвостах; моментальный `tasklist /m` не нашёл DLL. При этом общий VIDA.log содержал совпадения текстов `PassThru...`/`ReadVin` — это **строковые вхождения**, не доказанные API-вызовы выбранного PS-провайдера.

В парном B3A45 append delta изменились VIDA log (462 байта) и кандидатный VirtualCar log (39 614 байт), но распознанных native `PassThruOpen` / connect markers — 0 / 0. Путь native-файла взят из shell TEMP, не независимо из процесса VIDA. **Причина пока неизвестна:** нельзя объявлять ни исправное соединение, ни гарантированный отказ DLL или транспорта.

Следующий решающий эксперимент — **одна ограниченная по времени read-only операция `TEST COMMUNICATION TOOL`**, с независимым доказательством реально выбранной DLL/процесса, точным окном логов и видимым результатом UI. Сравнивать нужно записи *одного подтверждённого сеанса*, а не разрозненные исторические снимки.

## 6. Обнаруженные проблемы организации данных

1. **Устаревший `README_RU.md` на `development`** всё ещё говорил, что оригинального исходника `virtualcar.c` нет, хотя `emulator/` там присутствует. Требуется синхронизация с англоязычным README.
2. **`docs/progress/CURRENT.md` — исторический журнал**, начинается с 7 ноября и смешивает Dvinholm/Virtual Car в заголовке. Не считать его текущей сводкой.
3. **`NEXT_CHAT.md` — длинный журнал передачи контекста** с несколькими контрольными точками и старыми next steps. Использовать его вместе с живыми SHA, а не вместо статуса GitHub.
4. **Сотни исследований и Draft PR** часто описывают разные уровни подтверждения: static, synthetic, native, owner-local, observed UI и acceptance. При поиске по ключевому слову «PASS» их легко перепутать.
5. **`main` и `development` разошлись**, а PR #2 остаётся Draft. Не называть код `development` выпущенной версией или подтверждённым `main`.

Правило для новых документов: всегда писать **источник → точный SHA/дата → сценарий → вид доказательства → результат → предел вывода**. Виды: `CI_EXACT_HEAD`, `OWNER_LOCAL`, `CLIENT_OBSERVED`, `SYNTHETIC_ONLY`, `SOURCE_RESEARCH`, `NOT_VERIFIED`. Запрос и его отправка, получение 13 кадров, успешный разбор VIN, идентификация ECU и GUI acceptance — **разные этапы**.

## 7. Приоритет дальнейшей работы

1. **P0 — реальная граница VIDA ↔ PS-провайдер.** Зафиксировать результат одной оригинальной `TEST COMMUNICATION TOOL` и связанный process/module/append-delta; не менять зарегистрированную DLL только из-за отсутствия маркера.
2. **P0 — ревью Draft #418 и #419.** Сверить exact-head код, локальные доказательства и инсталлятор; для запуска на постоянном VMware runner соблюдать trusted-ref политику. Локальный `CEM50_PS_ALL_PASS` не заменяет GitHub CI.
3. **P0 — ReadVin в том же сеансе.** Отдельно доказать `PassThruOpen/Connect`, TX, RX, 17-байтовое содержимое, исход обработчика VIDA и выбранную конфигурацию.
4. **P1 — Hardware/ECU ID.** Сначала установить реально выбранный SectorV клиентский маршрут и подтверждённый ответ, затем T111/T122; не синтезировать неподтверждённые A3/E3/A6/B9F0 позитивы.
5. **Release gate.** Только после релевантного exact-development VMware CI, проверки безопасности, прямой клиентской приёмки и отдельного решения о переносе PR #2 в `main`. Физический J2534 — самостоятельная будущая проверка.

## 8. Ограничения безопасности и публикации

Не коммитить закрытые VIN/донорские INI, исходные логи J2534, SQL/VIDA материалы, бинарники SectorV/VIDA, ключи, PIN или ECU-дампы. Уже явно разрешённый публичный синтетический VIN CEM50 остаётся исключением **только в существующем опубликованном профиле**; в этом отчёте не дублируется. Никаких Security Access, программирования, сброса ECU, подмены реального автомобиля, автоматического `main` merge или релиза.

---

Актуальные правила: [AGENTS](../../AGENTS.md), [порядок GitHub](../CHAT_GITHUB_WORKFLOW_RU.md). Навигация по материалам: [индекс доказательств](../EVIDENCE_INDEX_RU.md).
