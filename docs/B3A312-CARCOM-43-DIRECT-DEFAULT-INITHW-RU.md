# B3A312 — проверка прямых CarCom defaults / InitHw для 43 профилей

Дата: 2026-11-19. Draft PR #376. Только офлайн-анализ исходных
копий BaseData.sqlite и CarCom.sqlite, без записи в них.

## Проверенные предыдущие результаты

Локальный анализ владельца:
- один из двух BaseData.VehicleModel кандидатов с префиксом XC90
  содержит ровно 43 VehicleProfile для года 2009 и двигателя B8444S;
- все 43 BaseData.VehicleProfile.Id однозначно совпали с
  CarCom.T161_Profile.identifier при точном текстовом равенстве;
- отсутствующих и неоднозначных совпадений нет;
- это не оригинальное исполняемое GetScript/VIDA, и не proof, что
  данный набор *побайтово* совпадает с прежней частной выборкой.

Ранее историческая офлайн-сводка упоминала 9 непосредственных
default ECU назначений на 2 профилях, включая 2 CEM и 1 ECM,
и ноль прямых T136_InitHw_Profile ссылок среди 43. До выполнения
этого нового этапа это исторические сведения, а не результат
повторной проверки данным кодом.

## Инструмент

emulator/tools/audit_vida_basedata_carcom_43_direct_links.py

Два исходных SQLite открываются через mode=ro&immutable=1,
PRAGMA query_only=ON, с проверкой метакаталога, исходных столбцов,
физических обычных таблиц и количества строк. Тайм-аут запросов
ограничен 90-секундным SQLite progress handler, число прямых
назначений на профиль ограничено 32.

После повторной проверяемой последовательности
BaseData.VehicleProfile.Id -> CarCom.T161_Profile.identifier
с 43/43 уникальными совпадениями в памяти читаются только:

- CarCom.T160_DefaultEcuVariant, T100_EcuVariant и T101_Ecu:
  количество профилей с defaults, количество прямых назначений,
  количество назначений CEM, ECM и прочих ECU;
- CarCom.T136_InitHw_Profile: число профилей с прямым InitHw,
  число прямых ссылок и количество NULL fkT130_Init.

Ни один оригинальный Id, VIN, название ECU, профиль, baud rate,
значение InitHw или исходная строка не попадает в вывод.
Скрипт не создаёт private p0-exact-43-private.txt и
p0-general-private.txt, ничего не сохраняет на диск и не
выполняет CAN/J2534/ECU действия.

**Даже если выход покажет 9 assignments / 2 default profiles /
2 CEM / 1 ECM / 0 direct InitHw, это лишь прямые каталожные
связи в офлайн-копии, не действующие ECU и не применённая
VIDA настройка.** Наследование через folderLevel и фактическая
скорость D2 остаются неподтверждёнными.

## Локальный запуск владельца

Из корня актуального checkout PR #376, по отдельным строкам:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_basedata_carcom_43_direct_links.py -v

Только после успешного OK:

    py -3 .\emulator\tools\audit_vida_basedata_carcom_43_direct_links.py --folder 'E:\VirtualCar\VIDA-private'

Перед публикацией даже числового JSON необходимо убедиться,
что в выводе нет приватных значений. Никогда не публиковать
оригинальные SQLite, профили, VIN, D2/CEM payload или оригинальную
SQL Server конфигурацию.

Статус нового этапа на момент добавления: 13 синтетических
тестовых методов написаны, Windows и исходные базы владельца
ещё не испытаны. Нет PR merge, workflow_dispatch, релиза,
изменения original VIDA, installed SQL, ECU или J2534.

В отчёте всегда false: same_as_previous_43_source_set_verified,
original_sqlserver_fk_semantics_verified,
effective_inithw_inheritance_verified,
effective_d2_baudrate_verified,
actual_selected_vida_profile_verified, client_ecu_alive_verified,
original_vida_readvin_accepted.


## Фактический первый Windows-запуск и исправление (2026-11-19)

Владелец обновил ветку до HEAD 075110f и исполнил новый
test_vida_basedata_carcom_43_direct_links.py. Результат:
**13 запущено, 2 PASS, 11 ERROR**. У всех ошибок одна причина:
KeyError: 'T160_DefaultEcuVariant' в выборе подсхемы CarCom до
обращения к реальным строкам. Это **дефект кода**, а не признак
повреждённой SQLite-копии; в предоставленном журнале запуска
на оригинальных BaseData/CarCom после тестов нет.

Причина установлена по исходникам: прежняя функция
audit_vida_profile_fk_counts._catalog() возвращала только
NEEDED["CarCom"] (T161_Profile, T162_ProfileValue), хотя новый
анализатор требует ещё T160_DefaultEcuVariant, T100_EcuVariant,
T101_Ecu, T136_InitHw_Profile.

Исправление: _catalog получает необязательный явный
required_tables с лимитом на число таблиц; без этого параметра
прошлый выбор NEEDED[name] остаётся неизменным. Новый анализатор
передаёт фиксированный CARCOM_REQUIRED, а синтетические тесты
проверяют, что все шесть каталогов найдены и исходная область
выбора не расширилась неявно. Добавлен отдельный регрессионный
тест, итого **14 тестовых методов**.

Только после нового Windows результата Ran 14 tests ... OK
разрешается запуск следующего real-data агрегатного этапа.

Нет новых доказательств 9 defaults / 2 CEM / 1 ECM / 0 InitHw
по этому последнему анализатору. Прежний 43/43 BaseData↔CarCom
остается самостоятельным, уже выполненным gate.


## Реальная проверка исходных копий и расхождение ECM (2026-11-19)

Владелец предоставил результат:
- gate=all_43_direct_links_counted, matched_exact_profile_count=43;
- profiles_with_direct_defaults=2, direct_default_link_rows=9;
- direct_default_cem_rows=2, **direct_default_ecm_rows=0**,
  direct_default_other_ecu_rows=7;
- profiles_with_direct_inithw=0, direct_inithw_link_rows=0,
  profiles_without_direct_inithw=43;
- source_rows_read=true, source_writes_performed=false,
  original_source_identifiers_or_values_emitted=false.

Это **подтверждает** итог 9 прямых defaults / 2 профиля /
2 CEM / 0 прямых InitHw. Это **НЕ подтверждает** исторический
отчёт «1 ECM». Его правило классификации не сохранилось;
проверенная реализация считала ECM только при точном
T101_Ecu.identifier.strip().upper() == ECM, поэтому 7 записей
оставались в категории other. Нельзя приравнивать CEM или любой
other к ECM по предположению, а также считать найденные ECU живыми.

Для узкого следующего этапа добавлены три дополнительные
**лексические** категории только внутри other:
direct_default_other_ecm_prefix_rows (идентификатор начинается
с токена ECM), direct_default_other_ecm_token_rows (токен ECM
в любом месте) и direct_default_other_ecm_substring_rows
(встречается подстрока ECM). Категории пересекаются и НЕ
являются признаками настоящего ECM: возможны ложные совпадения,
а название двигателя/ECU может не содержать ECM вовсе.
Сырой идентификатор не выдаётся. Отдельный флаг
ecm_lexical_name_matches_prove_ecu_identity=false.

Добавлены два синтетических теста; всего **16** в
test_vida_basedata_carcom_43_direct_links.py. Существующие
счётчики прямых defaults и InitHw неизменны. Данные
самостоятельного нового тестового прогона и расширенного JSON
на момент записи отсутствуют — не заявлять 16/16 PASS.
Новые исходники необходимо проверить на Windows перед
повторным ограниченным локальным аудитом.
