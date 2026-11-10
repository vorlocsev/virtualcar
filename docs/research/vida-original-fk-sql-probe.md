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
