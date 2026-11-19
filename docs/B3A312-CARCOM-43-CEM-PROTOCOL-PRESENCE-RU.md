# B3A312 — прямые CEM конфигурации D2/GGD для 43 XC90 V8 MY2009

Дата: 2026-11-19. Draft PR #376. Режим: только офлайн чтение копий VIDA.

## Фактически подтверждено до этого этапа

- BaseData.VehicleProfile: ровно 43 записи для одной XC90-prefix модели с годом 2009 и двигателем B8444S.
- 43/43 BaseData.VehicleProfile.Id имеют ровно один CarCom.T161_Profile.identifier при точном сравнении в приватных офлайн-копиях.
- T160→T100→T101: 9 прямых default ECU links на 2 профилях, 2 прямых CEM, 0 точных ECM, 7 прочих.
- Дополнительный оригинальный аудит имён: среди семи прочих один T101_Ecu.identifier с отдельным токеном ECM в начале. Это объясняет историческое число 1 ECM как **возможную** альтернативную классификацию, но не доказывает ECU-тип.
- Все 43 профиля не имеют прямых T136 InitHw-связей. Нет доказанного inheritance.
- Исходные ECU не отвечали в оригинальном VIDA: признания VIN/ECU нет.

## Новый анализатор и ограничения

Скрипт emulator/tools/audit_vida_basedata_carcom_43_cem_protocols.py
сначала независимо повторяет 43/43 точных сопоставления в памяти, открывая
только E:\VirtualCar\VIDA-private\BaseData.sqlite и CarCom.sqlite в
mode=ro&immutable=1 + PRAGMA query_only=ON, с проверкой экспортного каталога
и всех требуемых обычных физических таблиц, а также row count.

Только для прямых default-вариантов ECU с точным
T101_Ecu.identifier == CEM (после strip и uppercase) исследует цепочку:

T160_DefaultEcuVariant → T100_EcuVariant → T101_Ecu
→ T120_Config_EcuVariant → T121_Config → T122_Protocol.

Классы отчёта:
- количество CEM-default links с конфигурацией и без неё;
- количество прямых CEM config links и повторов одной ссылки внутри варианта;
- D2, GGD, иной протокол (по точному имени протокола);
- для каждой из трёх групп только число NULL / NOT NULL в T121_Config.busRate.

Выход: фиксированные имена ключей, числовые счётчики, False-предикаты.
Никаких ProfileId, VIN, CEM ECU part number, конфигурационных адресов,
реальных битрейтов, имён исходных профилей, сырых кадров CAN,
XML или SQL пользовательских значений. Никаких .txt файлов создаётся.
Прямое T120 назначение — **не доказательство эффективной конфигурации**
VIDA 2015A; заполненный GGD busRate нельзя переносить на D2, а NULL
нельзя трактовать как конкретную скорость.

## Выполнение владельцем только после тестов

Из корня checkout ветки PR #376, по одной строке:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_basedata_carcom_43_cem_protocols.py -v

После результата OK:

    py -3 .\emulator\tools\audit_vida_basedata_carcom_43_cem_protocols.py --folder 'E:\VirtualCar\VIDA-private'

На момент написания имеется 15 новых синтетических тестовых методов.
Ни они, ни скрипт на реальном владельческом Windows/SQLite пока
не выполнены; GitHub exact-head CI не заявляется.

Статусы остаются неподтвержденными: реальный ECU, выбранный
оригинальной VIDA профиль, наследование InitHw, D2 baud rate, ReadVin,
T111/T122 и оригинальная SQL Server FK/collation семантика.
Изменения оригинальной VIDA/SQL, J2534, эмулятора CAN,
development/main, jobs/релизов не производятся.
