# VIDA: выборка оригинальных строк без обезличивания

Инструмент emulator/tools/vida_original_table_reader.py теперь принимает
--filters-json для поиска конкретных записей ECU Profile, InitHw,
Service или DiceTiming в исходных таблицах SQL Server. Исходные имена,
Unicode, числовые и бинарные значения **не маскируются**.

## Прежде чем запускать

Получите реальную схему своей VIDA через
vida_original_schema_reader.py. Ни T161_Profile, ни колонка identifier
пока не проверены на оригинальной установке VIDA 2015A; они приведены
в качестве примера. Используйте только обнаруженные имена.

Для SQL Server требуются pyodbc, DSN с валидным TLS-сертификатом и
SQL-учётная запись с ограниченными правами чтения.
ApplicationIntent=ReadOnly не заменяет SQL-права.

## Пример конфигурации в PowerShell

    $private = Join-Path $env:USERPROFILE 'VIDA-original-private'
    New-Item -ItemType Directory -Force -Path $private | Out-Null
    $filterPath = Join-Path $private 'CarCom-profile-filter-001.json'

    $filter = @{
      schema_version = 'virtualcar-vida-original-table-filters-v1'
      clauses = @(
        @{ column = 'identifier'; operator = 'eq'; value = 'XC90 V8' }
      )
    }

    $body = $filter | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText(
      $filterPath, $body, (New-Object System.Text.UTF8Encoding $false))

JSON поддерживает от одного до четырёх независимых условий AND.
Для равенства используйте operator eq, для NULL используйте
operator is_null без поля value. Поддерживаются Unicode-строки,
целые, логические значения, а также структурированные исходные
decimal-text, binary-base64 и uuid-raw-hex. Пример условия:

    {"column":"original_col","operator":"is_null"}

Имена должны существовать в фактическом SQL-каталоге таблицы.
Имена в SQL экранируются, а значения передаются параметрами ODBC.
Произвольные SQL-фрагменты в фильтры вставить нельзя.

## Пример получения оригинальных строк

    $env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
    $output = Join-Path $private 'CarCom-profile-selected-original-001.json'
    py -3 emulator/tools/vida_original_table_reader.py --database CarCom --schema dbo --table T161_Profile --filters-json "$filterPath" --max-rows 1000 --output "$output"
    if ($LASTEXITCODE -ne 0) { throw 'Исходные строки не прочитаны' }

Имена таблиц, колонок и значения здесь условные. Укажите данные
из собственного оригинального SQL Server-каталога.

Выход содержит оригинальные значения всех колонок выбранных строк,
а также полный исходный фильтр с **неизменёнными** значениями.
Данные остаются локально, вне GitHub, CI и релизов.
В Windows проверьте ACL приватной папки, а в POSIX файл
создаётся с режимом 0600.

## Как трактовать результат

Без фильтров прежний full_table_extracted_within_row_limit остаётся
true при успешной полной выгрузке. При фильтрации отчёт включает:

- selection_scope = filtered_subset_only
- selection_clauses_original_values с настоящими значениями
- selection_sql_parameters_bound = true
- filtered_subset_complete_within_row_limit = true
- full_table_extracted_within_row_limit = false
- full_table_row_count_verified = false

При превышении лимита строк (1–5000) отчёт не создаётся.
Успешная фильтрация не доказывает, что профиль был реально выбран
приложением VIDA, и не гарантирует атомарность SQL-снимка.
Анализатор vida_original_fk_value_audit.py специально отклоняет
такой результат, поскольку для него требуются полные таблицы.

Для проверки объявленных FK внутри исходного SQL Server используйте
vida_original_fk_sql_probe.py; межбазовые связи CarCom/DiceTiming
нужно подтверждать отдельно.

## Проверено

Изолированный локальный Python 3.13.5: **223/223 синтетических
unittest PASS**, compileall PASS. Четырнадцать новых тестов
проверяют параметризацию, оригинальные Unicode/бинарные/decimal/GUID
значения, NULL, ограничения, отсутствие SQL-инъекции, защиту
файлов и отказ от ложной полноты таблицы.

Не проверены: оригинальная VIDA 2015A, VMware exact-head CI,
фактический GetScript/ReadVin, VIN acceptance и физический J2534.


## Проверка FK по выбранной выборке

Тот же `--filters-json` теперь поддерживается напрямую в
`vida_original_fk_sql_probe.py`. Он применяет условия к
**исходной таблице выбранного FK**, а серверный `EXISTS`
проверяет существование соответствующих целевых ключей
по правилам SQL Server. Колонки фильтра перед запросом
подтверждаются через `sys.columns`, значения SQL-параметризованы.

Это отличается от локального сопоставления полных JSON-таблиц:
крупную исходную таблицу не нужно целиком экспортировать.
Сохраняются оригинальные значения и имя FK; результат
помечается `filtered_subset_only` и не доказывает
выбор ECU приложением VIDA.

Полная команда приведена в
[инструкции по исходному SQL FK](vida-original-fk-sql-probe.md).
16 новых синтетических тестов; локально 239/239 PASS,
`compileall` PASS.


## Проверка связей от исходного профиля к зависимым таблицам

Если в оригинальной схеме внешний ключ объявлен **в таблице
InitHw/Service**, а ссылается на **ECU Profile**, используйте
`vida_original_fk_sql_probe.py --target-filters-json`.
Целевой фильтр применяется к колонкам настоящего профиля,
после чего SQL Server независимо проверяет существование
обычного FK и совпадение с нужным профилем.

Таким образом наличие другого корректного профиля не
обозначается ошибочным внешним ключом.
Реальные имена FK, столбцов и значения остаются без
обезличивания в локальном JSON.

Полная команда и значения четырёх возможных статусов:
[проверка целевого ECU Profile через SQL FK](vida-original-fk-sql-probe.md).
Локальный тестовый прогон: 255/255 синтетических PASS.
