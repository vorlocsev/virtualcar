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
