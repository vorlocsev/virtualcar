# B3A299 — офлайн-анализ оригинального BaseData VINDecodeModel / Partner Group

## Цель и зависимость

Продолжение B3A298, Draft #362. После оригинального GUI отказа
`The VIN can not be decoded on selected Partner Group` (PR #357) нужна
**проверка самого каталога** прежде чем менять F114/ответ CEM.

Этот этап добавляет `emulator/tools/vida_partner_group_catalog.py`, который
разбирает **локальные JSON-выгрузки оригинальной BaseData**, созданные
утилитами из **Draft PR #317**. Он **НЕ подключается к SQL Server**,
не открывает VIDA/DiCE/J2534, не меняет SQL/Registry32/DLL, не
переписывает оригинальные данные и не отправляет их в GitHub.

В отличие от форумных советов для MY2016/17, **не выполнять UPDATE
VINDecodeModel или искусственную замену YearCode**, чтобы
«разблокировать» декодирование VIN.

## Шаг 1. Получить реальную схему (только в отдельном checkout PR #317)

Условие: уже настроен DSN `VIDA_READONLY`, проверяемый TLS и
действительно ограниченные права SQL SELECT/catalog.
`ApplicationIntent=ReadOnly` **сам по себе не защищает** от записи.

Владельческий Windows PowerShell:

```powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
New-Item -ItemType Directory -Path $private -Force | Out-Null
$schema = Join-Path $private 'BaseData-schema-vin-001.json'
py -3 emulator/tools/vida_original_schema_reader.py --database BaseData --output $schema
if ($LASTEXITCODE -ne 0) { throw 'Original BaseData schema read failed' }
```

**Не угадывать наличие** `dbo.VINDecodeModel`. Его нужно сначала
увидеть в оригинальной схеме. Затем в отдельном checkout этого PR:

```powershell
py -3 emulator/tools/vida_partner_group_catalog.py --schema $schema --output (Join-Path $private 'B3A299-schema-review-001.json')
if ($LASTEXITCODE -ne 0) { throw 'Offline schema review failed' }
```

Это только структурная проверка: какие исходные имена, объявленные
FK и предполагаемые поля действительно присутствуют. Если таблицы
нет в видимом каталоге, результат не доказывает, что декодера нет
в VIDA.

## Шаг 2. Получить оригинальные строки (только если таблица есть)

Инструмент PR #317 `vida_original_table_reader.py` создаёт
отдельную выгрузку с **оригинальными Unicode-именами и значениями без
анонимизации**, только в приватной папке. Ни одна программа этого PR
не изменяет или не публикует оригинальный JSON.

Только для таблицы/полей, существование которых уже подтверждено
в шаге 1:

```powershell
$rows = Join-Path $private 'BaseData-VINDecodeModel-original-001.json'
py -3 emulator/tools/vida_original_table_reader.py --database BaseData --schema dbo --table VINDecodeModel --max-rows 5000 --output $rows
if ($LASTEXITCODE -ne 0) { throw 'Original VINDecodeModel capture not available' }
```

Если в таблице больше 5000 строк, утилита откажется создавать
«успешный полный» отчёт. Тогда в PR #317 используйте
`--filters-json` для реально существующего `fkPartnerGroup`
(не более четырёх параметризованных предикатов).
Фильтр может быть сформирован на основе *известной из GUI/SQL*
оригинальной Partner Group. Не выводить её из номера региона
в статье или из VIN по догадке.

Пример **формата** приватного context-файла B3A299 — число
`1002` приведено здесь **только как синтетический пример**, а не
как правильная группа текущего владельца:

```json
{"schema_version":"virtualcar-vida-partner-group-selection-v1","fkPartnerGroup_original":1002}
```

`fkPartnerGroup_original` может быть числом, строкой или SQL NULL
в зависимости от фактической схемы. Не заменять строку числом.

## Шаг 3. Офлайн-аудит исходных значений

В checkout **B3A299**, при существующих приватных JSON:

```powershell
py -3 emulator/tools/vida_partner_group_catalog.py --schema $schema --rows $rows --group-context (Join-Path $private 'PartnerGroup-context-001.json') --output (Join-Path $private 'B3A299-group-catalog-001.json')
if ($LASTEXITCODE -ne 0) { throw 'Offline Partner Group audit failed' }
```

Скрипт принимает `--schema` в обязательном порядке, `--rows` и
`--group-context` необязательны; context допустим только вместе с rows.
Выходной файл должен быть **новым**; существующий не перезаписывается.

Отчёт сверяет точные названия и порядок столбцов схемы и выборки,
проверяет исходный database/schema/table, распознаёт полный / фильтрованный
охват, перечисляет **реальные декларации FK**, исходные имена колонок,
количество записей в выгрузке по **точным значениям** `fkPartnerGroup`
и, если context задан, число строк этой группы именно в выборке.
Исходные значения `fkPartnerGroup` не обезличиваются и не заменяются.

Отчёт не копирует все оригинальные строки; они остаются в неизменённом
приватном JSON, который является исходным доказательством. Это
структурная сводка, а не замена оригинальным данным.
Выход содержит только новые имена полей аудита и копии точных
декларативных FK/групп, если они были в source.

## Непреодолимая граница на этом этапе

**Наличие строки Partner Group не доказывает совпадение VIN**.
`VinStartPos/EndPos`, `VINCompare`, `YearCodePos/YearCode`,
`ChassisNoFrom/To` могут иметь семантику и порядок выбора, которые
из одних названий колонок не следуют. Полное применение оригинальной
SQL-модели/ .NET декодера, выбор Partner Group во время работы,
принятие F114, вызов Output.AddVIN, GUI VIN acceptance, ECU-ID,
T111/T122 и физический J2534 остаются **NOT VERIFIED**.

Даже если выборка была полной в пределах заявленного лимита,
`original_schema_reader` и `original_table_reader` не подтверждают
единый транзакционный снимок или одинаковое runtime-происхождение
выполненных в разные моменты запросов.

## Локальная проверка нового кода

- Изолированный Python 3.11: **14/14 unittest PASS**
- `compileall` для двух файлов: PASS
- Все тесты используют синтетический каталог/строки и не содержат
  оригинального VIN, SQL-подключения или реального автомобиля.
- Exact-head CI/owner VMware/original BaseData: **НЕ ЗАПУСКАЛИСЬ**.
- Не изменены CEM/ECU responses, J2534, F114, SQL, VIDA, Dvinholm.

Следующий этап после оригинальной BaseData выгрузки: отдельно,
owner-local, отыскать настоящий вызов VIN decoder в оригинальных
.NET DLL и его predicate/priority по `VINDecodeModel`,
затем сопоставить с ручным VIN A/B из B3A298.
