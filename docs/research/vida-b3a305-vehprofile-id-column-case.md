# B3A305 — Original BaseData VehicleProfile column case: id vs Id

Дата: 2026-11-18. Draft поверх B3A304 / PR #368. Только исследовательские инструменты (без эмуляции или изменения VIDA).

## Исходные данные, которые проверены

В ранее полученной владельцем оригинальной read-only выгрузке
VIDA 2014D из \`BaseData.dbo.VehicleProfile\` заголовок столбца
идентификатора указан как **\`id\`** (нижний регистр), значение
\`0c00c8af80205920\`, \`FolderLevel=0\`. См. файл исследования
\`docs/research/vida-owner-readvin-global-profile-confirmed-2026-11-10.md\`
в ветке \`feature/vida-redacted-evidence-summary-v1\`.

В независимом публичном декодере
[spnda/volvo_vida_db](https://github.com/spnda/volvo_vida_db/blob/main/scripts/vin_decoder.py)
метод \`Vehicle.get_vehicle_profiles()\` читает столбец **\`Id\`**
(верхний регистр). Это подтверждено исходником, но **не доказывает**
такое написание в локальной SQL-схеме владельца.

Инструмент оригинальной выгрузки \`vida_original_table_reader.py\`
из Draft PR #317 получает имена через \`sys.columns\`,
затем выдаёт \`SELECT *\`, сохраняя исходные имена без изменения.
Поэтому downstream Python \`dict(zip(columns, values))\` не может
подменять \`id\` на \`Id\` без явной проверки.

**Ограничение:** этот PR не доказывает точные имена всех остальных
колонок, наличие новых строк, а также совместимость локальной
оригинальной установленной VIDA 2015A. Основание — прежняя оригинальная
выгрузка VIDA 2014D и независимый открытый исходник.

## Исправление

В B3A301 (\`vida_vin_vehicle_profile.py\`) и B3A302
(\`vida_vin_public_disambiguation.py\`):

- Источник с единственной колонкой \`id\` или \`Id\` принимается;
  источник с обеими колонками либо с неизвестным вариантом
  \`ID\`, \`iD\`, \`profileId\` отклоняется как неоднозначный.
- Валидация исходного значения остаётся строгой: 16 hex-символов,
  без преобразования в numeric CarCom ID.
- Внутренний псевдоним \`row['Id']\` создаётся только после проверки,
  не меняя исходный JSON, порядок столбцов или оригинальные значения.
- В локальный отчёт добавлено
  \`source_vehicle_profile_id_column_original\`, содержащее
  фактически прочитанное имя исходного столбца.
- Глобальный \`FolderLevel=0\` и NULL \`fkVehicleModel\` продолжают
  учитываться отдельно от модельно-специфических совпадений.
- Все флаги оригинального runtime, ReadVin GUI, ECU Identification,
  T111/T122 и физического J2534 остаются **NOT VERIFIED**.

## Проверки

Дополнительно записаны 10 синтетических unittest:
- 5 в \`test_vida_vin_vehicle_profile.py\`,
- 5 в \`test_vida_vin_public_disambiguation.py\`.

Проверяют оригинальное \`id\`, сохранение регистра/значения,
обратную совместимость с публичным \`Id\`, конфликт \`id\`+\`Id\`,
неизвестные варианты регистра, отдельный global NULL-профиль и
отсутствие ложного VIN acceptance.

**Эти новые тесты на B3A305 exact head не запускались.**
Предыдущее успешное 73/73 относится только к B3A304. Нельзя
считать его проверкой данной ревизии.

Локальные команды для checkout этого PR:

~~~powershell
py -3 -m unittest discover -s emulator/tests -p 'test_vida_vin_vehicle_profile.py' -v
if ($LASTEXITCODE -ne 0) { throw 'B3A305 VehicleProfile regression failed' }
py -3 -m unittest discover -s emulator/tests -p 'test_vida_vin_public_disambiguation.py' -v
if ($LASTEXITCODE -ne 0) { throw 'B3A305 Public Disambiguation regression failed' }
py -3 -m compileall -q emulator/tools/vida_vin_vehicle_profile.py emulator/tools/vida_vin_public_disambiguation.py emulator/tests/test_vida_vin_vehicle_profile.py emulator/tests/test_vida_vin_public_disambiguation.py
if ($LASTEXITCODE -ne 0) { throw 'B3A305 Python syntax failed' }
~~~

После проверки на синтетических данных — отдельная owner-approved
read-only выгрузка реального \`BaseData.VehicleProfile\` из PR #317,
исходные имена и строки без обезличивания локально; результат
B3A305 не передавать в публичный GitHub и не интерпретировать
как работающий GUI ReadVin.

Изменения не затрагивают исходную VIDA, SQL, J2534 DLL,
реестр, CEM/ECU, Dvinholm. Нет merge, release, CI dispatch.
