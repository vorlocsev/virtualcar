# B3A312 — T161 stored constraint keys: точные 43 vs один общий InitHw

Дата: 2026-11-19. Draft PR #376. Граница: анализ только исходных
офлайн-копий BaseData.sqlite и CarCom.sqlite в памяти, без вывода
приватных ключей, значений InitHw и VIN.

## Основание

Владелец подтвердил:
- 43/43 XC90/MY2009/B8444S BaseData.VehicleProfile.Id однозначно
  совпали с CarCom.T161_Profile.identifier;
- для 43 точных профилей прямых T136 InitHw-связей нет;
- два прямых CEM-варианта имеют три конфигурации: D2=2 с
  NULL busRate; GGD=1 с не-NULL busRate;
- среди 150 XC90/MY2009 с NULL engine все 150 однозначно
  сопоставились с CarCom, ровно один имеет одну прямую T136
  InitHw-связь: связанный Init содержит **9 заполненных
  InitValue**, из которых **7 типов лексически содержат baud или speed**.

Таким образом, старое описание «7 заполненных параметров» не полностью
соответствует новому, более точному счёту (здесь 9 заполненных, 7
скоростеподобных по имени). Ни одно значение скорости не опубликовано.
Это не означает, что InitHw выбран VIDA при ReadVin.

## Новый ограниченный сравнительный инструмент

emulator/tools/audit_vida_xc90_generic_inithw_constraints.py

Сначала вновь проверяет исходную точную выборку 43 в BaseData,
43/43 уникальных совпадения в CarCom, отдельно выбирает только
MY2009/NULL engine для той же доказанной модели XC90.
Для всей группы общих профилей проверяет точное сопоставление с
CarCom, затем **требует ровно один профиль с прямой T136-связью,
ровно одно связанное T130_Init**. При отсутствии или неоднозначности
не строит сравнение.

Далее сравнивает хранимые CarCom.T161_Profile:
- fkT162_ProfileValue_Model
- fkT162_ProfileValue_Year
- fkT162_ProfileValue_Engine
- folderLevel

Для каждого из первых трёх измерений на 43 точных профилях
возвращает четыре взаимоисключающих количества: обе ссылки
заполнены и совпадают, обе заполнены и различаются, у общего
ссылка NULL, у точного ссылка NULL при заполненной общей.

Для folderLevel возвращает только количество точных профилей
с меньшим, равным, большим или несравнимым значением относительно
единственного общего профиля. Исходные числовые folderLevel
не показываются; при нечисловом или пустом значении приоритет
не выдумывается.

**Все эти числа — только статические категории равенства ключей.**
NULL на общем профиле не считается wildcard, совпавшая модель/год
не является доказательством parentage, а направление сравнения
folderLevel не является установленным алгоритмом приоритета.
Остальные 7 полей ограничений T161 в этом этапе не сравниваются.
Оригинальная процедура VIDA 2015A GetInitHwSettings здесь не
исполняется и не подтверждена.

Постоянные статусы false:
folderlevel_order_is_precedence_or_parentage_verified;
general_profile_is_runtime_ancestor_verified;
original_vida_2015a_getinithwsettings_verified;
d2_baudrate_verified; original_vida_readvin_accepted.

Источники: mode=ro&immutable=1 и query_only=ON;
строгий exporter identity, фиксированные таблицы/столбцы,
проверка физического типа и количества строк, ограниченные
SQLite queries и отказ на неуникальных/пропущенных ссылках.
Выход: только агрегированный JSON. Нет SQL/VIDA/J2534/ECU записей.

## Windows, запуск владельцем после отдельной проверки тестов

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_xc90_generic_inithw_constraints.py -v

Только если новые 15 синтетических тестов завершились OK:

    py -3 .\emulator\tools\audit_vida_xc90_generic_inithw_constraints.py --folder 'E:\VirtualCar\VIDA-private'

Пока тесты и исходный профильный анализ новым кодом **не выполнялись**
на Windows владельца. Статические проверки кода не заменяют
Windows/VMware result и exact-head CI. PR остается Draft; нет
merge, workflow_dispatch, изменений original VIDA, development/main
или релиза.
