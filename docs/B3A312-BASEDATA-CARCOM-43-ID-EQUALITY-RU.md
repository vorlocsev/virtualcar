# B3A312 — 43 BaseData XC90 V8 MY2009 ↔ CarCom T161 identifier

Дата: 2026-11-19. Черновой PR #376. Статус: исходный код и синтетические
тесты подготовлены; реальный этот этап на SQL/SQLite владельца не запускался.

## Основание и границы

Фактический ответ владельца от read-only BaseData audit:
- ровно два XC90-prefix VehicleModel кандидата, год=one, двигатель=one;
- один из кандидатов имеет 3880 всех профилей, 349 на MY2009,
  **ровно 43** на MY2009 и B8444S;
- другой имеет ноль профилей по всем проверенным категориям.

Это воспроизводит *число* 43 внутри BaseData, но пока не доказывает,
что это те же 43 CarCom профиля или что VIDA использует их при ReadVin.

Исследовательский публичный VIDA 2014D порт spnda/volvo_vida_db,
pinned revision e2f8ee165e373360d7f7fd0e80298f68c25bc07e,
реализует get_vehicle_profiles как выбор BaseData.VehicleProfile.Id,
а carcom.get_vehicle_ecus принимает эти ключи и соединяет с
CarCom.T161_Profile.identifier. Это **гипотеза для воспроизводимой
строгой проверки на оригинальных приватных копиях**, а не
авторизованный 2015A foreign key или доказательство фактического
выбора runtime.

## Новый инструмент

emulator/tools/audit_vida_basedata_carcom_43_equality.py

Открывает только E:\VirtualCar\VIDA-private\BaseData.sqlite и
CarCom.sqlite, в отдельных mode=ro&immutable=1 соединениях с
PRAGMA query_only=ON. Проверяет подлинность экспортного метакаталога,
разрешённые физические обычные таблицы, актуальные подсчёты строк,
отсутствие WAL/SHM/journal и предел времени.

Сначала в памяти проверяются два XC90-prefix VehicleModel, однозначное
точное имя ModelYear.Description=2009 и Engine.Description=B8444S.
Только если **ровно один** модельный кандидат имеет строки для
точной тройки и их ровно 43, считываются до 43 BaseData.VehicleProfile.Id
в память. ID валидируются (уникальны, без скрытой очистки/padding),
преобразуются lossless из целочисленного типа в десятичную строку.
Каждый ID ищется как точное равенство в CarCom.T161_Profile.identifier
через параметризованный SELECT c LIMIT 3.

Итог — только число уникально найденных, пропущенных или
неоднозначных ссылок. Исходные Model ID, VehicleProfile ID, названия,
CarCom Profile ID, VIN, реальные значения и пути не печатаются,
не записываются, не публикуются.

Даже **43/43 уникальных точных совпадений** подтверждает только
реализованную в этом инструменте кандидатскую equality-связь
между двумя офлайн-экспортами. Прямые T160 defaults / InitHw,
согласованность с предыдущим отчётом 9 defaults/2 профиля,
оригинальные 43 private strings, parentage,
VIN/ReadVin, живой ECU, D2 baud, и OEM значение CEM не проверяются
этим этапом. Это следующий исследовательский gate, не принятие VIDA.

## Запуск только на локальной машине владельца

Из проверенного checkout соответствующей ветки PR #376.
Сначала обновить исходники:

    git pull --ff-only

Запустить новый синтетический набор:

    py -3 -m unittest discover -s emulator/tests -p test_vida_basedata_carcom_43_equality.py -v

Только после OK:

    py -3 .\emulator\tools\audit_vida_basedata_carcom_43_equality.py --folder 'E:\VirtualCar\VIDA-private'

Результат содержит категории cross_reference_gate и counts.
Если gate=source_identifier_equality_classified и
all_43_have_unique_exact_identifier_matches=true, можно планировать
следующий owner-private proof: связать эти 43 с CarCom T160/T136
агрегатами (9 defaults across 2 profiles, 0 direct InitHw),
отдельно проверив предыдущую протокольную сводку.
Если отсутствуют 1+ ссылки, не подбирать их по похожему имени/ID
и не создавать private profile lists.

original_profile_selection_provenance_verified=false,
same_as_prior_43_selection_verified=false,
carcom_profile_inheritance_verified=false,
original_vida_runtime_profile_selected=false,
original_vida_readvin_accepted=false.

Скрипт не делает SQL Server EXEC/UPDATE, не пишет ни в одну базу,
не создаёт .txt с ключами, не трогает VIDA/J2534/INI/main/development,
не запускает CI и не публикует релиз.
