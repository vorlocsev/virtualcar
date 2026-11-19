# B3A312 — оставшиеся семь ограничений профиля: XC90 MY2009 InitHw

Дата: 2026-11-19. Только приватные офлайн-копии BaseData.sqlite
и CarCom.sqlite. Draft PR #376, никаких изменений исходной VIDA.

## Что подтверждено владельцем

После точного BaseData XC90 V8 MY2009 отбора 43 записей:
- все 43/43 имеют уникальное равенство с CarCom.T161_Profile.identifier;
- в точной группе нет прямых T136 InitHw-ссылок;
- в отдельной группе 150 XC90 MY2009 с NULL engine 150/150 найдены
  в CarCom; ровно один профиль имеет одну прямую T136 ссылку к Init;
- связанный Init содержит 9 ненулевых T131 InitValue, 7 из типов с
  лексическими названиями baud или speed;
- в CarCom все 43 точных профиля имеют такие же модель и год,
  как единственный общий InitHw-профиль; его поле двигателя NULL,
  а folderLevel у всех 43 точных профилей численно больше, чем
  у общего. Приоритет и реальное наследование не доказаны;
- два прямых CEM default-варианта имеют конфигурации D2=2
  с NULL busRate и GGD=1 с non-NULL busRate. Нельзя использовать
  скорость GGD как скорость D2.

## Новый аудит

emulator/tools/audit_vida_xc90_generic_inithw_remaining_constraints.py

Сначала снова проверяет 43/43 точных BaseData->CarCom совпадений,
однозначность года, двигателя, модели, отсутствие пересечения
exact/general и ровно один общий профиль, имеющий **одну**
прямую T136→T130 InitHw связь. В обеих копиях используется
только mode=ro&immutable=1 и PRAGMA query_only=ON, строгие
метакаталог/физические таблицы/row counts, ограниченные запросы.

Сравнивает для этого одного общего профиля следующие CarCom
T161_Profile FK поля с 43 точными профилями:
- fkT162_ProfileValue_Body
- fkT162_ProfileValue_ChassisFrom
- fkT162_ProfileValue_ChassisTo
- fkT162_ProfileValue_ControlUnit
- fkT162_ProfileValue_Market
- fkT162_ProfileValue_Steering
- fkT162_ProfileValue_Transmission

Для каждого измерения возвращает четыре взаимно
исключающие категории: same_both_present, different_both_present,
general_null, exact_null_when_general_present. Возвращает также
число точных профилей без противоречий среди семи полей,
с одним или более противоречием заполненных ключей,
и с одним или более NULL на точной стороне при заполненной общей.
Эти три итоговые категории могут пересекаться (две последние)
и НЕ являются решением о применимости профиля.

NULL не считается wildcard; равенство ключей не доказывает
parentage; числовая полнота 43/43 не доказывает, что исходная
VIDA 2015A применяет эти параметры, тем более их конкретные
значения. Параметры InitValue, ключи профилей, скорость D2, VIN,
названия ECU и исходные строки не публикуются.

Ключевые флаги в JSON:
null_generic_constraint_is_wildcard_verified=false;
carcom_key_equality_is_original_sqlserver_fk_verified=false;
general_profile_parentage_verified=false;
vida_2015a_getinithwsettings_runtime_verified=false;
d2_baudrate_verified=false; client_vin_accepted=false.

## Проверка Windows на машине владельца

В актуальном checkout ветки PR #376 выполнить по одной команде:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_xc90_generic_inithw_remaining_constraints.py -v

Только после успешных 13 синтетических тестов:

    py -3 .\emulator\tools\audit_vida_xc90_generic_inithw_remaining_constraints.py --folder 'E:\VirtualCar\VIDA-private'

Код добавлен, но **13 синтетических тестов и реальный
аудит на Windows владельца ещё не выполнены**. Статическая
проверка исходников/PR отдельно не означает тестовый PASS.

## Что ещё потребуется

Оригинальный алгоритм VIDA 2015A GetInitHwSettings нужно
подтвердить отдельным источником: кодом процедуры, IL с
точной атрибуцией установленного компонента либо
воспроизводимыми наблюдениями фактического исполнения.
Офлайн SQLite с таблицами не содержит этой семантики.
Никаких исходных приватных данных, SQL procedure source,
действующих D2 битрейтов и ECU TX/RX в коммитах.

Никаких изменений оригинальной VIDA/SQL, J2534/CEM,
main/development, запуска workflow или релиза.
