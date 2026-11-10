# VIDA: оригинальные имена схемы, FK и индексов

Этот этап нужен для анализа реальной структуры **CarCom** и **DiceTiming** без
обезличивания. Новая утилита `emulator/tools/vida_original_schema_reader.py`
читает у владельца исходные названия схем, таблиц, колонок, индексов и
объявленных внешних ключей SQL Server и сохраняет их в локальном JSON.
Имена, включая Unicode и регистр, не заменяются масками и не хешируются.

## Запуск на Windows VMware

Требуется существующий DSN с проверяемым TLS-сертификатом и реально
ограниченными правами чтения метаданных SQL Server. Сам флаг
`ApplicationIntent=ReadOnly` не заменяет ограничения прав.

Из корня репозитория PR #317:

```powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
New-Item -ItemType Directory -Force -Path $private | Out-Null

py -3 emulator/tools/vida_original_schema_reader.py --database CarCom --output (Join-Path $private 'CarCom-original-schema-001.json')
if ($LASTEXITCODE -ne 0) { throw 'Не удалось прочитать оригинальную схему CarCom' }

py -3 emulator/tools/vida_original_schema_reader.py --database DiceTiming --output (Join-Path $private 'DiceTiming-original-schema-001.json')
if ($LASTEXITCODE -ne 0) { throw 'Не удалось прочитать оригинальную схему DiceTiming' }
```

Каждое имя выходного файла должно быть **новым**. Каталог вне Git;
исходные данные автоматически не публикуются в GitHub/CI. На POSIX
файлы создаются с правами `0600`; на Windows проверьте ACL папки.
В Windows необязательно иметь одинаковые права для CarCom и DiceTiming.
Отказ доступа означает отсутствие подтверждённой структуры, а не её отсутствие.

## Что внутри

- Реальные `source_database`, `schema`, `table`, `object_id`.
- Все видимые имена колонок, `column_id`, SQL-типы, длины, precision,
  scale, collation, флаги `NULL`, identity и computed.
- Имена и состав уникальных индексов и первичных ключей.
- Объявленные FK с **реальными** именами, последовательностью колонок,
  отключённым/недоверенным статусом и действиями DELETE/UPDATE.

Для составных FK дополнительно сопоставляется полный список столбцов
с целевым уникальным индексом. Пропущенная позиция или неполный
составной ключ вызывают ошибку, а не фиктивный успешный результат.

**Важная граница:** это оригинальные метаданные SQL Server, а не строки
прикладных таблиц. Для извлечения всех значений одной реально найденной
таблицы используйте `vida_original_table_reader.py` из того же PR:

```powershell
py -3 emulator/tools/vida_original_table_reader.py --database CarCom --schema dbo --table T161_Profile --max-rows 1000 --output (Join-Path $private 'CarCom-T161_Profile-original-001.json')
```

`T161_Profile` приведена исключительно как ранее известная гипотеза.
Сначала посмотрите результат **своей** схемы и используйте фактическое
имя. Полные значения данных не обезличиваются. Поскольку SQL Server не
поддерживает обычные FK между разными базами, отсутствие FK между
CarCom и DiceTiming **не доказывает отсутствия программной связи**.
Такая связь требует отдельного исследования исходных значений и кода VIDA.

Флаги `complete_catalog_visibility_verified`, `actual_row_joins_verified`,
`transactional_snapshot_verified` и `runtime_readvin_verified` всегда
`false`: метаданные не удостоверяют права просмотра всей базы, совпадение
снимков между запросами или реальное выполнение диагностического сценария.

## Проверено

Локально на синтетическом SQL-каталоге выполнены **12/12 PASS** и
`compileall` PASS. Исходные байты GitHub совпадают с локально
протестированными Git blobs:

- Инструмент: `ac621caba2c2b83fbe9daeb644fd75bf4b86057b`
- Тесты: `0ce16fa030e04fde97031b42ad4dc5beed57f76d`

Оригинальная VIDA 2015A не открывалась; реальный SQL Server, VMware
exact-head CI, значения D2 и физический J2534 на этом этапе не испытаны.
