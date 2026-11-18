# B3A300 — VINDecodeModel + VINDecodeVariant: офлайн-предикат (не оригинальный VIDA decoder)

Исходный блокер: VIDA после доставленного J2534 `62 F1 14 + VIN17`
ранее показала `The VIN can not be decoded on selected Partner Group`
(B3A275, PR #357). Только исследование `VINDecodeModel` из B3A299
недостаточно: декодер может потребовать сопряжённый вариант двигателя
и трансмиссии.

## Новое техническое свидетельство

Открытый проект `spnda/volvo_vida_db` содержит
`scripts/vin_decoder.py` (рассмотрен точный Git blob
`5e2ccee5e0dbaa417a7b0d20006b253844dc45aa`):
https://github.com/spnda/volvo_vida_db/blob/main/scripts/vin_decoder.py

Это самостоятельная реализация исследования исходной VIDA 2014D
на Python/DuckDB, **не оригинальный декодер Volvo**. Автор объединяет
`VINDecodeModel` и `VINDecodeVariant` через
`fkVehicleModel`, `fkModelYear`, `fkPartnerGroup`, сравнивает
заданные подстроки `VinCompare`, символ `YearCode` в
`YearCodePos` и шестизначный номер шасси в диапазоне;
после этого дополнительно фильтрует несколько возможных
комбинаций двигателя/трансмиссии через `VehicleProfile`.
Этот последний шаг **не реализован** в B3A300 и не должен
считаться подтверждённым.

При отсутствии оригинальных BaseData значений и исходной реализации
декодера VIDA это доказательство *правдоподобных условий отбора*,
но не алгоритма, реально запущенного пользователем. Различия SQL
колляции/типов и кодирования CHAR также могут влиять на сравнение.

## Новый инструмент

`emulator/tools/vida_vin_model_variant.py` — отдельный локальный
Python 3 офлайн-проверяющий, без pyodbc, DuckDB, сети, оригинальных
DLL или адаптера:

- Проверяет два JSON-экспорта формата
  `virtualcar-vida-original-table-capture-v1`, полученных утилитой
  `vida_original_table_reader.py` из **Draft #317**.
- Сравнивает модель, год, партнёрскую группу, участки VIN,
  диапазон шасси, годовой символ, совпадения вариантов.
- Строго различает полную в рамках лимита и фильтрованную выборку,
  не утверждает отсутствие записей в остальной базе.
- Отбрасывает неподтверждённые/неподдерживаемые схемы вместо
  угадывания данных.
- Сохраняет исходный VIN и исходные числовые ключи/сочетания
  **без обезличивания только в закрытом локальном JSON**, а не в PR.
- Не делает никаких запросов к оригинальной SQL, не вызывает VIDA,
  не изменяет исходные строки, не устанавливает J2534 DLL и
  не создаёт ответов ECU.

## Запуск на компьютере владельца

Прежде всего получить действительные метаданные `BaseData` из
B3A299 и убедиться, что **обе оригинальные таблицы и колонки есть**.
Использовать существующий DSN/учётную запись с реально
ограниченными правами чтения. Исходные файлы хранить вне checkout.

В отдельном checkout **Draft PR #317**:

```powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
New-Item -ItemType Directory -Path $private -Force | Out-Null
$model = Join-Path $private 'VINDecodeModel-original-001.json'
$variant = Join-Path $private 'VINDecodeVariant-original-001.json'
py -3 emulator/tools/vida_original_table_reader.py --database BaseData --schema dbo --table VINDecodeModel --max-rows 5000 --output $model
if ($LASTEXITCODE -ne 0) { throw 'VINDecodeModel original capture unavailable' }
py -3 emulator/tools/vida_original_table_reader.py --database BaseData --schema dbo --table VINDecodeVariant --max-rows 5000 --output $variant
if ($LASTEXITCODE -ne 0) { throw 'VINDecodeVariant original capture unavailable' }
```

Если какая-либо таблица превышает 5000 записей, `#317`
**не создаёт полный отчёт**; использовать
`--filters-json` с подтверждёнными в схеме колонками, не
публиковать содержимое. Фильтрованные результаты не означают,
что других совпадений не существует.

Полный исходный VIN сохранить **только локально** в
`%USERPROFILE%\VIDA-original-private\vin-input-001.txt`.
Никакой VIN в скрипты или GitHub не добавлять.
Нужно знать оригинальный `fkPartnerGroup` по фактической
локальной базе/GUI. Для примера `1002` часто называется EUR в
открытой реализации, но это **не подтверждение выбранной группы
пользователя**.

В отдельном checkout этого **Draft PR B3A300**, тот же
приватный каталог и файлы:

```powershell
$vinFile = Join-Path $private 'vin-input-001.txt'
$result = Join-Path $private 'B3A300-vin-model-variant-001.json'
py -3 emulator/tools/vida_vin_model_variant.py --vin-file $vinFile --partner-group 1002 --model-rows $model --variant-rows $variant --output $result
if ($LASTEXITCODE -ne 0) { throw 'Offline model/variant selection could not be established' }
```

**Замените `1002` на фактически выбранную Partner Group.**
Файл `$result` должен быть новым. Исходные данные, VIN,
Partner Group и результат остаются owner-local; загрузка на GitHub
не разрешена автоматически.

## Как интерпретировать отчёт

- `model_variant_candidate_pair_count` — только количество
  совпадающих пар **в данной выгрузке**, а не число реально
  обнаруженных ECU или вероятность успешного VIDA.
- `filter_stage_counts_in_given_captures` показывает, на каком
  из ограниченных этапов отсечены исходные записи.
- `partial_capture_cannot_exclude_missing_rows` сохраняет
  предупреждение, если хотя бы одна таблица отфильтрована.
- `vin_original` содержит переданный VIN **без замены на hash**;
  он не публикуется, не передаётся удалённым API.
- `vehicle_profile_engine_transmission_filter_applied=false`:
  последующее сопоставление с VehicleProfile ещё отсутствует.
- `actual_vida_decoder_algorithm_verified=false`,
  `original_responsehandler_addvin_verified=false`,
  `client_vin_acceptance_verified=false`,
  `ecu_identity_verified=false`.

Нулевое число кандидатов в неполной выборке **не доказывает**
отсутствие подходящего VIN в исходной VIDA. Даже ненулевое число
не доказывает успешное срабатывание оригинального декодера.

## Проверки и границы

Локально в изолированной среде: Python `unittest`
**14/14 PASS**, `compileall PASS`. Все фикстуры синтетические,
включая условные numeric IDs модели и VIN. Эти значения
**не подтверждены как оригинальные ключи** целевой BaseData.

Точный Git blob локально протестированного инструмента:
`4da0c6b615cca96bff51226f7c05344b31163051`.
Точный Git blob локально протестированных тестов:
`e2db168bfcc3f16a01c6ce4b54c350f145c1beb3`.

Original VIDA/VMware, SQL BaseData table capture, GUI ReadVin,
ECU Identification, T111/T122, original `ResponseHandler`,
exact-head CI и физический J2534: **NOT TESTED** на этом этапе.

Нет изменений в original VIDA, SQL, J2534 Registry32/DLL, CEM Core,
Dvinholm, исходных VIN/ECU или рабочих конфигурациях. Draft,
без merge, сборки или публикации.
