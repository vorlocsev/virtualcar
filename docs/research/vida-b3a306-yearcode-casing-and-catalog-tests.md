# B3A306 — VINDecodeModel year-column spellings and discoverable tests

Дата: 2026-11-18. Продолжение B3A305 / Draft #369.

## Основание, а не предположение о локальной VIDA

Проверен открытый исходник
[spnda/volvo_vida_db/scripts/vin_decoder.py](https://github.com/spnda/volvo_vida_db/blob/main/scripts/vin_decoder.py),
Git blob 5e2ccee5e0dbaa417a7b0d20006b253844dc45aa:
его DuckDB-запрос использует **VM.Yearcode** и **VM.Yearcodepos**.

При этом открытый файл
[spnda/volvo_vida_db/scripts/read_csv.py](https://github.com/spnda/volvo_vida_db/blob/main/scripts/read_csv.py)
содержит `TEXT_COLUMNS` для **YearCode**. SQL/ DuckDB при
соответствующей настройке может быть нечувствителен к регистру имён
колонок, тогда как Python словарь JSON, созданного настоящим
`vida_original_table_reader.py` из Draft #317, его сохраняет.

**Фактические имена этих колонок в локальной оригинальной BaseData
в данном этапе не читались.** Публичные исходники подтверждают только
два встретившихся написания, а не окончательный SQL-тип и регистр
нашей целевой установки VIDA 2014D / 2015A.

## Воспроизводимая несовместимость

До патча B3A300 (`vida_vin_model_variant.py`) требовал
`YearCode` и `YearCodePos`. В локальной синтетической копии
таблицы с написаниями `Yearcode` / `Yearcodepos` исходная версия
выдала:

```text
EvidenceError: original table lacks required columns
```

Это ошибка сопоставления исходной схемы, а **не доказательство
неправильного VIN или неисправности оригинальной VIDA**.

## Изменение B3A306

1. B3A300 принимает **ровно один** из `YearCode` /
   `Yearcode` и ровно один из `YearCodePos` / `Yearcodepos`.
   Двойные и неподтверждённые альтернативы не угадываются;
   анализ завершается ошибкой без подмены SQL значений.
2. Внутренний `row[canonical]` используется исключительно
   внутри Python для существующей проверки года; исходный
   JSON, имена колонок, порядок и значения остаются **нетронутыми**.
3. Выходной отчёт B3A300 включает
   `model_year_column_names_original` с точным выбранным
   написанием обеих колонок. Все поля
   `actual_vida_decoder_algorithm_verified`,
   `client_vin_acceptance_verified` и
   `ecu_identity_verified` по-прежнему **false**.
4. Каталог B3A299 теперь отдельно показывает присутствие всех
   четырёх известных вариантов в `original_column_presence`,
   а не объявляет `YearCodePos` ложным отсутствием без
   показа `Yearcodepos`.
5. Устранена независимая ошибка в
   `test_vida_partner_group_catalog.py`:
   прежний импорт искал инструмент в `emulator/tests`, в то
   время как в обычном репозитории он находится в
   `emulator/tools`. На прежнем оригинальном тесте
   `python -m unittest discover -s emulator/tests
   -p test_vida_partner_group_catalog.py` воспроизводился
   `ModuleNotFoundError`.

Нет других изменений в симуляторе CEM, VIN, ECU ответах,
J2534 DLL или оригинальной VIDA.

## Проверенные локальные тесты

Скопированы байт-в-байт исходники B3A305 (#369), B3A300 и
B3A299; в отдельной локальной Python 3.13.5 директории
внесены эти четыре исправления. Базовые файлы проверены
по Git blob SHA, конечные four corrected blobs также должны
совпасть с загруженными в GitHub:

- `emulator/tools/vida_vin_model_variant.py`:
  `866d2bbc723da4fe1db2f59c89f4018449a012b5`
- `emulator/tests/test_vida_vin_model_variant.py`:
  `cc0360f744ae20b0c1d2842c9b67882865216d53`
- `emulator/tools/vida_partner_group_catalog.py`:
  `8d05b777b84d1b36a151a604c7045931b906587e`
- `emulator/tests/test_vida_partner_group_catalog.py`:
  `8f4e5cecb10d3192c0fdfa7b1135a9cf7942eaf0`

```text
python -m unittest discover -s emulator/tests -p 'test_vida*.py' -q
Ran 116 tests in 0.025s — OK
python -m compileall -q emulator/tools emulator/tests — PASS
```

Включены 18 тестов B3A300, 15 тестов B3A299,
31 тест B3A301, 30 тестов B3A302 и 22 теста B3A303.
Новые проверки B3A306 охватывают публичное написание года,
смешанное написание, отказ при двусмысленной схеме, отказ
при неизвестном написании, сохранение исходного JSON
и discovery импорта каталога.

## Граница доказательств и следующий gate

- Tests: **synthetic-only**, исходных VIN от владельца нет.
- Exact-head GitHub CI: **не запускался**.
- Original `BaseData`/VIDA GUI/J2534 in VMware: **не запускались**.
- ReadVin, T111, T122, ECU Identification: **не подтверждены**.

Следующий реальный контроль — по уже созданному в PR #317
инструменту прочитать **исходный каталог BaseData** с
ограниченными правами SELECT и сопоставить точные оригинальные
имена/типы столбцов, после этого применить offline B3A300 и
сравнение manual-vs-J2534 B3A303. Нельзя делать вывод о VIN
acceptance по совпадению схемы.

Оригинальные VIN, SQL и журналы остаются неизменёнными и приватными.
Никаких SQL UPDATE/ALTER, патчей `Workflow.DLL`,
регистрации J2534, VMware jobs, merge и релизов в этом этапе нет.
