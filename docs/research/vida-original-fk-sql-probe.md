# VIDA: проверка оригинальных FK непосредственно в SQL Server

`emulator/tools/vida_original_fk_sql_probe.py` позволяет локально
проверять **исходные значения одного объявленного FK** запросом SQL Server
`SELECT … CASE WHEN EXISTS (SELECT 1 …)`. Сравнение выполняет сервер
с его собственными правилами сопоставления, а не Python по JSON.

**Без обезличивания:** сохраняются реальные имена базы, схем, FK,
таблиц, колонок и значения ключей, включая Unicode. Для бинарных
значений используется обратимый Base64, для Decimal текстовое значение.

## Пример Windows VMware

Сначала откройте [оригинальную схему](vida-original-schema-and-fk.md)
и найдите точное имя FK и таблицы-источника. Названия ниже
**условные** и не подтверждают наличие таблицы в VIDA 2015A.

Потребуются `pyodbc`, настроенный DSN, валидный TLS-сертификат
SQL Server и отдельная учётная запись с фактическими правами
**только на чтение**. `ApplicationIntent=ReadOnly` не является
разрешением или запретом на изменение данных.

~~~powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
New-Item -ItemType Directory -Force -Path $private | Out-Null
py -3 emulator/tools/vida_original_fk_sql_probe.py --database CarCom --schema dbo --table T136_InitHw_Profile --foreign-key FK_НАСТОЯЩЕЕ_ИМЯ --max-rows 1000 --output (Join-Path $private 'CarCom-FK-native-SQL-001.json')
if ($LASTEXITCODE -ne 0) { throw 'Проверка оригинального FK не выполнена' }
~~~

Замените `FK_НАСТОЯЩЕЕ_ИМЯ` на реальное имя из
своей базы. Анализатор не угадывает профиль и не обращается
к другим базам автоматически. Для DiceTiming с подтверждённым FK
можно выполнить отдельный запуск с `--database DiceTiming`.

## Проверки и ограничения

1. `DB_NAME()` должен соответствовать указанной базе.
2. `sys.foreign_keys` и `sys.foreign_key_columns` должны вернуть
   однозначное определение FK со всеми позициями составного ключа.
3. Количество членов FK сверяется с целевым уникальным индексом.
4. SQL `EXISTS` проверяет ключи на равенство в самой базе;
   `NULL` в исходном ключе учитывается отдельно.
5. Определение FK считывается повторно после выполнения запроса.
   Обнаруженное изменение вызывает ошибку.

Чтение ограничено 1–5000 исходными строками и размером результата
50 МиБ. При превышении лимита результат не создаётся.
Выходной JSON сохраняется только локально новым файлом вне Git.
В POSIX установлен режим 0600; на Windows проверьте ACL папки.
Никакие оригинальные значения не отправляются в GitHub, CI,
комментарии или релизы.

**Границы:** SQL `EXISTS` действительно применяет серверные
правила равенства к строкам в момент запроса, но не доказывает
транзакционно атомарный снимок. Совпадающие результаты двух чтений
каталога не удостоверяют полноту прав просмотра или работающую
проверку FK. Межбазовые связи `CarCom ↔ DiceTiming` могут быть
реализованы кодом VIDA, а не объявленным SQL FK. Не проверяются
выбор XC90 ECU Profile, InitHw priority, D2 baud, GetScript/ReadVin,
приём VIN и физический J2534.

## Проверено локально

Python 3.13.5, **209/209 синтетических unittest PASS**,
`compileall` PASS. Добавлено 12 тестов SQL `EXISTS`
и два теста защиты от внедрения свойств ODBC-подключения
через название базы в прежних оригинальных инструментах.
Оригинальные базы VIDA 2015A и VMware exact-head CI не запускались.


## Проверка FK только для выбранного оригинального профиля (2026-11-10)

Теперь этот же инструмент принимает необязательный `--filters-json`,
используя **точно тот же формат** что и
[выборка оригинальных записей Profile/InitHw](vida-original-targeted-profile-query.md).
Это позволяет проверить нативный SQL `EXISTS` только по строкам,
удовлетворяющим условиям выбранного профиля. Допускаются 1–4 условия
`eq` и `is_null` с логическим AND. Значения не маскируются;
включая Unicode, Decimal и Base64 для исходных бинарных данных.

Пример PowerShell (все имена таблицы, колонок и FK здесь условные;
подставьте фактические имена из собственной SQL Server-схемы):

~~~powershell
$root = Join-Path $env:USERPROFILE 'VIDA-original-private'
$filters = Join-Path $root 'CarCom-profile-filter-001.json'
$result = Join-Path $root 'CarCom-profile-FK-native-002.json'

py -3 emulator/tools/vida_original_fk_sql_probe.py --database CarCom --schema dbo --table T136_InitHw_Profile --foreign-key FK_НАСТОЯЩЕЕ_ИМЯ --filters-json "$filters" --max-rows 1000 --output "$result"
if ($LASTEXITCODE -ne 0) { throw 'Проверка FK для выбранных исходных строк не выполнена' }
~~~

Фильтры могут ссылаться не только на столбцы FK. Прежде чем
выполнить запрос к исходным строкам, утилита отдельно считывает
`sys.columns` указанной исходной таблицы и подтверждает наличие
всех колонок фильтра и самих FK. Исходные названия экранируются
как SQL-идентификаторы, а значения передаются **параметрами ODBC**,
не текстом SQL. Значения фильтра остаются в локальном JSON без
обезличивания.

Для фильтрованного результата явно устанавливаются:
`source_selection_scope=filtered_subset_only`,
`source_complete_within_row_limit=false`,
`filtered_source_subset_complete_within_row_limit=true` и
`full_source_table_row_count_verified=false`.
Один успешный SQL EXISTS подтверждает соответствие именно
проверенным строкам в момент запроса, но **не полноту всей таблицы
и не фактический выбор ECU Profile приложением VIDA**.
Без `--filters-json` прежнее поведение не изменилось.
Порядок строк не гарантируется, так как у запроса нет `ORDER BY`.

Код и 16 новых синтетических регрессий локально проверены на Python 3.13.5:
**239/239 PASS** для всего доступного исследовательского набора,
`compileall` PASS. SHA-1 Git blobs совпадают с протестированными:
- `vida_original_fk_sql_probe.py`: `2e858c2c9bbd97343d9366fe30c2b24f838d570d`
- `test_vida_original_fk_sql_filtered.py`: `e51bc33e1ff6b678faedbf174b726620868f09ca`

Оригинальная VIDA 2015A, настоящий SQL Server, VMware exact-head CI
и физический J2534 здесь не запускались.


## Проверка исходного FK по полям целевого ECU Profile

Новая опция `--target-filters-json` позволяет выбирать связанный
профиль **по оригинальным колонкам целевой таблицы FK**.
Это особенно важно, когда `InitHw` или таблица связи хранит
внешний ключ на `ECU Profile`, а имя/идентификатор нужного профиля
находится только в целевой таблице. В отличие от
`--filters-json`, которая ограничивает строки **источника**,
новая опция проверяет поля **цели**. Оба фильтра можно использовать
вместе; до четырёх условий допускаются с каждой стороны.

Сначала прочитайте реальную схему своей VIDA и найдите
конкретный FK, его исходную и целевую таблицы. Затем подготовьте
локальный UTF-8 JSON с оригинальным значением профиля:

~~~json
{
  "schema_version": "virtualcar-vida-original-table-filters-v1",
  "clauses": [
    {"column": "РЕАЛЬНАЯ_КОЛОНКА_ПРОФИЛЯ", "operator": "eq",
     "value": "РЕАЛЬНОЕ_ЗНАЧЕНИЕ_ИЗ_VIDA"}
  ]
}
~~~

Имена выше служат исключительно заполнителями и **не являются
подтверждёнными объектами VIDA 2015A**. Данные фильтра не
обезличиваются, а хранятся только в локальном файле.

~~~powershell
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
$targetFilters = Join-Path $private 'ecu-profile-target-original-001.json'
$output = Join-Path $private 'InitHw-profile-FK-target-001.json'

py -3 emulator/tools/vida_original_fk_sql_probe.py --database CarCom --schema dbo --table T136_InitHw_Profile --foreign-key FK_НАСТОЯЩЕЕ_ИМЯ --target-filters-json "$targetFilters" --max-rows 1000 --output "$output"
if ($LASTEXITCODE -ne 0) { throw 'Проверка исходного FK для целевого профиля не выполнена' }
~~~

В этой команде таблица и FK условные. Подставьте реальные имена,
полученные в исходной базе. Выход хранит настоящие названия и
значения ключей без маскирования.

Внутри выполняются **два независимых нативных EXISTS**:
первый проверяет FK вместе с целевым фильтром, второй проверяет
FK без фильтра. Это исключает ложный вывод «сломанный FK»,
если ссылка ведёт на другой допустимый профиль.

Результат разделяется на четыре категории:

- `sql_exists_target_filter_matches`: совпадает FK и целевой профиль
- `sql_exists_matches_outside_target_filter`: FK существует, но целевой
  профиль не удовлетворяет условию
- `sql_exists_unmatched`: отсутствует совпадение для самого FK
- `sql_null_key_rows`: хотя бы один компонент исходного FK равен NULL

Общее поле `sql_exists_matches` содержит **обе категории
корректного совпадения FK**, независимо от фильтра.
Оригинальные значения фильтра находятся в
`target_filter_clauses_original_values` без обезличивания.
Флаг `vida_runtime_selected_profile_verified` всегда `false`.
При наличии отдельного фильтра источника порядок ODBC-параметров
проверен: значения целевой части запроса идут первыми.

SQL-семантика проверки `EXISTS` подтверждается документацией
Microsoft, однако отсутствие транзакционного снимка, полнота
прав на метаданные, реальные связи CarCom и DiceTiming,
выбор VIDA GetScript/ReadVin и физический J2534 требуют отдельных
доказательств. <https://learn.microsoft.com/en-us/sql/t-sql/language-elements/exists-transact-sql>

Локально выполнено **255/255 синтетических тестов PASS**
(239 прежних и 16 новых), `compileall` PASS, Python 3.13.5.
Git blob SHA исходников и тестов совпадают с локально
протестированными:
- `emulator/tools/vida_original_fk_sql_probe.py`
  `30ffbedf531b04f54afe9ec24597eaafc47d11f4`
- `emulator/tests/test_vida_original_fk_sql_target_filtered.py`
  `443ca1e6191e61dc296903746446948d92e00f0d`

Оригинальная VIDA 2015A и VMware exact-head CI не запускались.


## Однозначный исходный ECU Profile: строгая проверка целевого фильтра

В обычном режиме `--target-filters-json` SQL `EXISTS` допускает
несколько целевых строк, подходящих под одно условие. Наличие хотя бы
одной подходящей записи **не доказывает**, что идентифицирован один
конкретный ECU Profile.

Для исследования исходного профиля без этой неоднозначности добавлен
**необязательный** параметр `--require-unique-target`. Он допускается
только совместно с `--target-filters-json` и выполняет отдельный
параметризованный запрос `SELECT TOP (2)` по целевой таблице FK:

- **0 строк**: отказ, целевая запись не найдена.
- **2 строки**: отказ, фильтр не однозначен.
- **1 строка**: продолжается прежняя проверка FK через SQL `EXISTS`,
  а оригинальный составной ключ найденной записи включается в
  `selected_target_original_key_values` без обезличивания. Бинарные
  значения сохраняются в обратимом Base64.

Невалидные колонки, неподдерживаемые типы, NULL в выбранном целевом
ключе и неожиданная SQL-проекция приводят к ошибке. Фильтр
проверяется по оригинальному `sys.columns`; значения остаются
**ODBC-параметрами**, не вставляются в SQL-текст. Результаты
`sql_exists_target_filter_matches`,
`sql_exists_matches_outside_target_filter`,
`sql_exists_unmatched` и `sql_null_key_rows` сохраняют прежнюю
четырёхклассовую семантику.

Пример из корня checkout, с **условными** именами FK и таблиц.
Подставьте фактические значения из вашей собственной VIDA 2015A:

~~~powershell
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
$targetFilter = Join-Path $private 'ecu-profile-target-original-001.json'
$out = Join-Path $private 'InitHw-unique-profile-FK-003.json'

py -3 emulator/tools/vida_original_fk_sql_probe.py --database CarCom --schema dbo --table T136_InitHw_Profile --foreign-key FK_НАСТОЯЩЕЕ_ИМЯ --target-filters-json "$targetFilter" --require-unique-target --max-rows 1000 --output "$out"
if ($LASTEXITCODE -ne 0) { throw 'Не удалось однозначно определить целевой профиль' }
~~~

Дополнительные поля результата:
`target_unique_selector_checked=true`,
`target_unique_row_count_at_probe=1`,
`selected_target_original_key_values`,
`target_key_selected_at_query_time_only=true`.
`transactional_snapshot_verified=false` и
`vida_runtime_selected_profile_verified=false` **не меняются**.

**Ограничение:** поиск единственного целевого ключа и последующий
`EXISTS` являются двумя отдельными SQL-запросами. Они используют
одно подключение, но без единого транзакционного снимка между ними
профиль может измениться. Такой результат подтверждает
однозначность фильтра **на момент отдельного чтения**, но не факт
выбора ECU профиля приложением VIDA, не значения D2 baud и не
выполнение GetScript/ReadVin.

**Локальная проверка:** Python 3.13.5, **270/270 синтетических
unittest PASS**, `compileall` PASS. Из них 15 новых проверок
охватывают 0/1/2 найденных профиля, составной ключ, NULL,
бинарные значения, Unicode, порядок ODBC-параметров,
совместимость старого режима, CLI и отказ при ложных входных
данных. Точные протестированные Git blobs:
- `emulator/tools/vida_original_fk_sql_probe.py`:
  `8e91d06f4536683cc006f71f18fe271df8f6ac58`
- `emulator/tests/test_vida_original_fk_sql_unique_target.py`:
  `24040dae1c77e75665268889d98117b251c24e1b`

Оригинальная VIDA/VMware, exact-head CI и физический J2534 на этом
этапе не запускались.


## Единый транзакционный снимок Profile и FK (необязательный режим)

Ранее `--require-unique-target` проверял ровно одну запись
целевого ECU Profile и затем выполнял FK `EXISTS` двумя независимыми
SQL-запросами. Между ними реальные данные могли измениться.

Новая опция **`--require-snapshot`** доступна только вместе с
`--require-unique-target` и `--target-filters-json`.
При её включении инструмент:

1. Проверяет идентичность подключённой базы через `DB_NAME()`.
2. Читает `sys.databases.snapshot_isolation_state` и принимает только
   значение **1 = ON**. При OFF (0), переходных состояниях (2/3) или
   недоступном метаданном поле завершается ошибкой.
3. Устанавливает для **своего подключения**
   `SET TRANSACTION ISOLATION LEVEL SNAPSHOT` и выполняет
   `BEGIN TRANSACTION`; `SELECT @@TRANCOUNT` должен вернуть **1**.
4. Внутри единственной явной транзакции подтверждает оригинальный
   FK, проверяет источниковые и целевые фильтры по `sys.columns`,
   требует ровно одну запись целевого профиля через
   `SELECT TOP (2)` и выполняет нативный SQL `EXISTS`.
5. Повторно сравнивает объявление FK, затем выполняет
   `COMMIT TRANSACTION`. Если произошло исключение после начала
   транзакции, пытается выполнить `ROLLBACK TRANSACTION`,
   закрывает подключение и **не создаёт успешный JSON**.

Режим **не выполняет ALTER DATABASE** и ничего не изменяет в
исходных данных. Если SQL Server не разрешает SNAPSHOT, инструмент
не переключает глобальные настройки и завершается с отказом.

### Пример запуска в Windows VMware

Используйте действительные имена из оригинальной VIDA SQL-схемы;
следующие названия таблиц и FK приведены только для примера.

~~~powershell
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
$target = Join-Path $private 'ecu-profile-target-original-001.json'
$out = Join-Path $private 'CarCom-profile-FK-snapshot-001.json'

py -3 emulator/tools/vida_original_fk_sql_probe.py --database CarCom --schema dbo --table T136_InitHw_Profile --foreign-key FK_НАСТОЯЩЕЕ_ИМЯ --target-filters-json "$target" --require-unique-target --require-snapshot --max-rows 1000 --output "$out"

if ($LASTEXITCODE -ne 0) { throw 'Единый SQL SNAPSHOT не подтверждён' }
~~~

Если база допускает SNAPSHOT и все SQL-запросы транзакции успешно
выполнены и зафиксированы, отчёт помечается:
`transactional_snapshot_verified=true`,
`sql_snapshot_isolation_required=true`,
`sql_snapshot_transaction_committed=true`.

Без новой опции поведение прежнего режима сохраняется,
а `transactional_snapshot_verified=false`.
Во всех режимах оригинальные имена таблиц, колонок, ключей,
значения фильтров и ключи записываются **без обезличивания**
в локальный JSON, вне GitHub и CI.

### Что остаётся неподтверждённым

Транзакционный уровень SNAPSHOT обеспечивает согласованность
версий прикладных строк между запросами **в одной базе**.
Но системные метаданные SQL Server не версионируются.
Конкурентный DDL может привести к ошибке 3961, которая должна
прервать проверку, а не считаться успехом. Также режим не доказывает
полноту SQL-прав на просмотр каталога, активное выполнение
ограничения FK, межбазовые отношения CarCom/DiceTiming,
выбор профиля самой VIDA, реальные D2-тайминги, выполнение
GetScript/ReadVin, принятие VIN или физический J2534.

Документация Microsoft:
- [SET TRANSACTION ISOLATION LEVEL: SNAPSHOT](https://learn.microsoft.com/en-us/sql/t-sql/statements/set-transaction-isolation-level-transact-sql)
- [ALTER DATABASE: ALLOW_SNAPSHOT_ISOLATION](https://learn.microsoft.com/en-us/sql/t-sql/statements/alter-database-transact-sql-set-options)
- [SQL Server row versioning and DDL metadata limitations](https://learn.microsoft.com/en-us/sql/relational-databases/sql-server-transaction-locking-and-row-versioning-guide)

### Тестирование

На локальном Python 3.13.5 выполнено **283/283 синтетических unittest
PASS**, `python -m compileall -q emulator/tools emulator/tests` PASS.
13 новых тестов проверяют успешный BEGIN/COMMIT, `@@TRANCOUNT`,
отказ при выключенном/переходном SNAPSHOT, нулевом/неоднозначном
профиле, SQL-ошибке, попытке ROLLBACK, старом режиме, исходных
значениях Unicode, параметризации и CLI.

Граничные реальные испытания с оригинальной VIDA 2015A,
VMware exact-head CI и физическим J2534 **не выполнялись**.
Тестовые Git blob SHA:
- инструмент: `d5abdbae9d3002c94d6fdf1ce26ca5f248bf392a`
- новые тесты: `5330c725235b5bad20057f9d38c627b3232f39be`
