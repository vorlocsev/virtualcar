# B3A312 — подсчёт связей профилей CarCom / BaseData (только чтение)

Дата: 2026-11-19. Статус: новый инструмент и синтетические тесты;
**реальные пользовательские строки SQLite ещё не запрашивались этим инструментом**.

## Подтверждённая схема

Предыдущий владелец-локальный запуск inspect_vida_profile_selection_schema.py
нашёл BaseData: 23 таблицы, CarCom: 51 таблицу. По этим фактически
наблюдаемым именам создан emulator/tools/audit_vida_profile_fk_counts.py.

Инструмент проверяет ровно шесть кандидатов-ребер:

- BaseData: VehicleProfile.fkVehicleModel → VehicleModel.Id;
  VehicleProfile.fkModelYear → ModelYear.Id;
  VehicleProfile.fkEngine → Engine.Id.
- CarCom: T161_Profile.fkT162_ProfileValue_Model → T162_ProfileValue.id;
  T161_Profile.fkT162_ProfileValue_Year → T162_ProfileValue.id;
  T161_Profile.fkT162_ProfileValue_Engine → T162_ProfileValue.id.

Это **внутрибазовые** ссылки; нельзя выводить, что VehicleProfile
автоматически соответствует T161_Profile или что число 43 воспроизведено.

## Запуск владельцем на Windows

Из корня проверенного checkout feature/b3a312-installed-vida-carcom-readonly,
после отдельного git pull --ff-only:

    py -3 -m unittest discover -s emulator/tests -p test_vida_profile_fk_counts.py -v

Затем, только после успешных тестов и проверки локальной команды:

    py -3 .\emulator\tools\audit_vida_profile_fk_counts.py --folder 'E:\VirtualCar\VIDA-private'

Скрипт ничего не записывает в исходные базы или другие файлы.
В консоли выдаётся только JSON с числовыми классами для шести
заранее зафиксированных связей: source_rows, null_fk_rows,
missing_target_rows, unique_target_rows, ambiguous_target_rows,
а также фиксированные предупреждающие флаги.

## Защита и границы доказательств

- Только исходные копии SQLite CarCom.sqlite и BaseData.sqlite, где
  проверены schema_version / source_database / scope, ожидаемые
  столбцы, одинарные физические обычные таблицы и совпадение количества
  строк с экспортным каталогом.
- Открытие mode=ro&immutable=1 + PRAGMA query_only=ON; запрет
  -wal, -shm, -journal; ограничение размеров таблиц, 90 секунд
  на SQLite progress handler для каждой базы.
- Никакие ID профилей, VIN, исходные описания/названия, ключи FK,
  скорости, адреса, CAN-кадры, SQL-определения, значения или пути
  в JSON не попадают. Ошибка выводится только как error_class.
- Отчёт не создаёт private списков p0-exact-43-private.txt,
  p0-general-private.txt; они по-прежнему отсутствуют.
- cross_database_profile_mapping_verified=false,
  original_selection_of_43_reconstructed=false,
  exact_xc90_v8_my2009_profile_verified=false,
  runtime_vida_readvin_accepted=false.

Даже если все шесть связей совпадают, это подтверждает только форму
и целостность ссылок в приватных **офлайн-копиях**. Оригинальная
SQL Server FK-семантика, фактический VIN, выбранный VIDA профиль,
скорость D2, CEM аппаратная версия, ECU identification, T111/T122
и исходная выборка 43 кандидатов остаются отдельными gates.

Никаких изменений установленной VIDA/SQL, J2534, INI, ECU, PR merge,
development, main или публикации релиза.
