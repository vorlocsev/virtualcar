# B3A301 — оригинальный BaseData.VehicleProfile: офлайн-проверка кандидатов VIN

Дата: 2026-11-18. Продолжение B3A300 / Draft PR #364.

## Почему это отдельный gate

В PR #364 кандидаты были восстановлены из двух оригинальных таблиц
`BaseData.VINDecodeModel` и `VINDecodeVariant`, но без проверки
`VehicleProfile`. Исследованный открытый декодер
[spnda/volvo_vida_db/scripts/vin_decoder.py](https://github.com/spnda/volvo_vida_db/blob/main/scripts/vin_decoder.py)
(бинарный Git blob `5e2ccee5e0dbaa417a7b0d20006b253844dc45aa`)
показывает два **различных** использования профилей:

1. `get_vehicle_profiles()` находит применимые профили, допуская
   `NULL` в `fkModelYear`, `fkPartnerGroup`, `fkEngine`,
   `fkTransmission`, `fkBodyStyle` и требуя `NULL` для
   `fkSteering`, `fkNodeECU`, `fkSpecialVehicle`.
2. `decode_vin()` дополнительно фильтрует кандидаты двигателя и
   трансмиссии через конкретные строки `VehicleProfile`, **только
   когда исходных комбинаций больше одной**.

Это Python/DuckDB реализация исследователя, **не доказанный алгоритм
оригинальной VIDA**. B3A301 реализует **только первый, диагностический
способ проверки применимых строк**, не выдавая его за второй
алгоритм разрешения неоднозначностей.

## Добавлен код

`emulator/tools/vida_vin_vehicle_profile.py` — локальный анализатор без
SQL-соединения и установки VIDA. Принимает:
- `--candidates`: JSON отчёта B3A300 схемы
  `virtualcar-vida-vin-model-variant-candidates-v1`;
- `--profiles`: JSON исходной выгрузки `BaseData.dbo.VehicleProfile`
  формата `virtualcar-vida-original-table-capture-v1`,
  созданной строго read-only инструментом из Draft #317;
- `--body-style-id`: **необязательный** оригинальный SQL
  `fkBodyStyle`, только если доказан в исходной установке;
- `--output`: **новый** приватный JSON (без overwrite).

Проверяются точные исходные FK, `NULL`-wildcard, специальные
ограничения, `FolderLevel`, целостность исходных метаданных,
состояние полной или фильтрованной выгрузки. Положительный результат —
**candidate_compatible**, а не «VIN decoded» или «ECU identified».
Если тип кузова не получен, профиль с конкретным `fkBodyStyle`
помечается **requires_more_context**, а не заведомо подходящим.
Аналогично для неизвестного двигателя или трансмиссии кандидата.

Важное различие ID: число `275` обозначает **VehicleModel.Cid
XC90** в открытом декодере, **НЕ** обязательно
`BaseData.VehicleModel.Id`. В `fkVehicleModel` следует
сопоставлять именно оригинальный SQL FK с FK из B3A300;
нельзя принудительно подставлять Cid=275. Также ранее найденные
`163119`, `163120`, `163191` — **CarCom T161_Profile** IDs,
не доказанные IDs `BaseData.VehicleProfile`.
Синтетические unittest используют отдельные придуманные IDs,
не приписывая их оригинальной базе.

## Owner-local запуск (только после подтверждения исходных таблиц)

В отдельном checkout **Draft PR #317** проверить оригинальную
схему `BaseData` и реально существующие столбцы `VehicleProfile`.
Использовать только подготовленный DSN `VIDA_READONLY` с
реально ограниченными правами на SELECT/catalog; указание
`ApplicationIntent=ReadOnly` **не обеспечивает запрета SQL-записи**.

```powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
New-Item -ItemType Directory -Force -Path $private | Out-Null
$profiles = Join-Path $private 'BaseData-VehicleProfile-original-001.json'
py -3 emulator/tools/vida_original_table_reader.py --database BaseData --schema dbo --table VehicleProfile --max-rows 5000 --output $profiles
if ($LASTEXITCODE -ne 0) { throw 'Original VehicleProfile read-only capture unavailable' }
```

**Важно:** при числе строк больше 5000 этот инструмент **не
выдаёт неполную таблицу за полную**; потребуется
`--filters-json` с условием по подтверждённому оригинальному
`fkVehicleModel` и, возможно, `fkModelYear` или
`fkPartnerGroup`. Сначала нужно установить точное SQL FK
из B3A300; не брать его из синтетических тестов и не путать с Cid.

В checkout **этого PR**, вне каталога исходных оригинальных данных:
```powershell
$candidates = Join-Path $private 'B3A300-vin-model-variant-001.json'
$result = Join-Path $private 'B3A301-profile-links-001.json'
py -3 emulator/tools/vida_vin_vehicle_profile.py --candidates $candidates --profiles $profiles --output $result
if ($LASTEXITCODE -ne 0) { throw 'Offline VehicleProfile evidence failed' }
```

Если оригинальный `fkBodyStyle` установлен независимым
владельческим чтением, возможно добавить к той же команде
`--body-style-id <original ID>`; **не** угадывать его.
Весь исходный VIN и все данные остаются в закрытой локальной папке,
без хеширования/изменения их значений. Не публиковать исходный JSON
или итоговый отчёт в GitHub.

## Интерпретация результата

- `candidate_compatible_profile_links` — записи профилей, чьи
  анализируемые nullable FK согласуются с кандидатом.
- `candidate_requires_context_profile_links` — записи, для которых
  недостаёт оригинального `fkBodyStyle` или других значений;
  они **не** объявляются успешным совпадением.
- `explicit_engine_transmission_pair_matches` — только число
  явно заданных совпадающих пар FK, а не подтверждение двигателя
  в автомобиле.
- `source_model_variant_scope_incomplete` и
  `profile_capture_incomplete` — отдельно сигнализируют о
  фильтрованных источниках; ноль совпадений в такой выборке
  не исключает отсутствующие записи.
- `original_folder_level` сохраняется без предположений о
  фактическом порядке применения VIDA.
- `cross_export_transactional_consistency_verified=false`:
  самостоятельные JSON не образуют доказанный SQL snapshot.
- `full_original_vida_profile_inheritance_verified=false`,
  `original_vida_decoder_runtime_verified=false`,
  `client_readvin_accepted=false`, `ecu_identification_verified=false`:
  эти проверки требуют отдельного оригинального runtime evidence.

Использование общего профиля с NULL не доказывает разрешение
связей с CarCom, наличие ECU, принятие VIN в GUI,
ReadVin/T111/T122 или успешность J2534.

## Испытания и ограничения

Локальный Python `unittest discover -s emulator/tests
-p test_vida_vin_vehicle_profile.py` — **20/20 PASS** на
синтетических оригинально-структурных значениях, не на исходных
данных VIDA. Python `compileall` **PASS**.
Точные проверенные Git blobs:
- `emulator/tools/vida_vin_vehicle_profile.py`:
  `1e1cc322585e0866edb73c9fa520e5d53d0e833d`
- `emulator/tests/test_vida_vin_vehicle_profile.py`:
  `52402e047d9a7159d1a6a41b9bba0c9257e71471`

Ни original BaseData, ни виртуальный J2534, ни оригинальный GUI VIDA
не запускались на этом этапе. Exact-head CI не запускался.
Без SQL UPDATE/ALTER, без реестра и DLL, без оригинальных VIN
в репозитории, без изменений CEM/ECU/Core, Dvinholm и без релиза.

Следующий шаг: на фактических исходных таблицах/GUI
определить разницу между `candidate_compatible`,
реальным `VINDecodeVariant` разрешением и успешным UI VIN/Partner Group
приёмом. Второй мультивариантный фильтр оригинального открытого
декодера имеет отдельные правила и не должен молча заменяться
проверкой generic VehicleProfile.
