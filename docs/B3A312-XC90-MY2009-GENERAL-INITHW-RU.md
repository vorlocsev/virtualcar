# B3A312 — общие XC90 MY2009 / NULL engine: прямые InitHw (только числа)

Дата: 2026-11-19. Черновой PR #376. Источник — только оригинальные
офлайн-копии владельца BaseData.sqlite и CarCom.sqlite. Эта проверка
ещё не запускалась владельцем на реальных копиях.

## Наблюдения до этапа

Исходная статическая выборка BaseData XC90-prefix, 2009, B8444S
имеет 43 профиля; все 43 однозначно сопоставлены с
CarCom.T161_Profile.identifier. Среди них 9 прямых defaults у 2
профилей, 2 прямых CEM и 0 прямых InitHw. Среди 7 других ECU
есть один с лексическим префиксом ECM (не доказанный ECU тип).
Конфигурации строго CEM: D2=2 с NULL busRate в обеих,
GGD=1 с заполненным busRate. Значение GGD нельзя переносить на D2.

Ранний отдельный аудит сообщал об одном общем XC90 MY2009
профиле с прямым InitHw и семью заполненными параметрами. Его
состав и исходная принадлежность ещё не воспроизведены в этом
более новом exact-сопоставлении; это гипотеза для проверки.

## Новый инструмент

emulator/tools/audit_vida_basedata_xc90_general_inithw.py

Алгоритм:
1. Две базы открываются через mode=ro&immutable=1,
   PRAGMA query_only=ON, с контролем exporter identity,
   таблиц, колонок, обычных физических таблиц, row counts,
   sidecars и времени каждого SELECT.
2. В BaseData выбирается единственная модель с префиксом XC90,
   содержащая ровно 43 профиля MY2009 / B8444S; все 43 должны
   однозначно совпасть с CarCom.T161_Profile.identifier.
3. Отдельно выбираются профили той же модели и MY2009,
   но только с fkEngine IS NULL; эта группа уже отмечалась в
   предыдущем подсчёте как 150 записей, однако инструмент не
   подгоняет число под 150. Верхняя граница — 500.
4. Для каждого такого профиля подсчитывается наличие/отсутствие
   точного соответствия CarCom.T161_Profile.identifier и прямых
   T136_InitHw_Profile. Для уникально найденных связанных
   T130_Init читаются только категории по T131_InitValue и
   T132_InitValueType: всего значений, ненулевые значения,
   лексические названия типа с baud или speed. Реальное
   значение initValue, название типа, Id, VIN и прочие
   исходные значения не выводятся и не записываются.
5. Повторно встречающиеся Init учитываются по уникальным ID
   в памяти, чтобы не умножать число их значений.
   Null-ссылки, отсутствующие и неоднозначные CarCom
   профили подсчитываются отдельно.

NULL-engine не означает родительский профиль или
автоматический переход VIDA 2015A на его InitHw.
Лексически похожий на speed/baud тип также НЕ является
реальным D2 bitrate, даже если число ненулевых значений
совпадёт с прежним исследованием.

Постоянные флаги: general_candidates_are_ancestor_profiles_verified=false,
original_vida_2015a_inithw_runtime_selection_verified=false,
d2_baudrate_verified=false, ggd_baudrate_may_be_copied_to_d2=false,
original_vida_readvin_accepted=false. Источники не меняются,
приватные input lists не создаются, merge/release нет.

## Windows, команды по одной

Из корня checkout PR #376:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_basedata_xc90_general_inithw.py -v

Только после успешного OK:

    py -3 .\emulator\tools\audit_vida_basedata_xc90_general_inithw.py --folder 'E:\VirtualCar\VIDA-private'

Новый комплект: 12 синтетических тестовых методов, исходные
закрытые SQLite тестовые фикстуры. Реальный Win Python suite,
оригинальные строки общих профилей, наследование InitHw,
оригинальный VIDA GetInitHwSettings, ReadVin и ECU RX пока
не проверены этим этапом. Перед передачей JSON достаточно
проверить, что в нём только фиксированные поля/счётчики.

Никаких изменений оригинальной VIDA/SQL, J2534/CAN, CEM,
development, main, workflow_dispatch или релизов.
