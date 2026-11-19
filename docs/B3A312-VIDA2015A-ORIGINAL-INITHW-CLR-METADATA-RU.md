# B3A312 — CLR MethodDef/MemberRef оригинальных VIDA 2015A DLL

Дата: 2026-11-19. Draft PR #376. Следующий этап после
audiтa исходных установленных бинарных файлов, без исполнения
оригинальных DLL, исходной VIDA, SQL/J2534/ECU.

## Подтверждённая исходная картина

Владелец запустил audit_vida_2015a_inithw_binary_signatures.py на
исходной локальной установленной E:\vida: 183 файла *.DLL/*.EXE,
11 файлов с одним или несколькими строго фиксированными
ASCII/UTF-16LE текстовыми маркерами. Без бинарных исходных данных
или локальных путей в отчёте.

Три приоритетных оригинальных SHA256:

- BizServices.CarCom.DB.DLL:
  a54117e6b2cc97c28bacf5df72f060ee8694de85291194046235bfd85a700be6
  (строковые маркеры CarComRepository, GetInitHwSettings,
   GetHwSettings, HwSettings, vadis_GetHwSettings)
- BizServices.VehicleCommProvider.DLL:
  763c26d195ee7324fd08d6da1bf7304e0090a7220c29ec46038ae695db5a82e5
  (CarComRepository, GetInitHwSettings, HwSettings)
- Workflow.DLL:
  ba78b669efea360887d333353451e9411e82004e368b356f74200d8fcb427ebd
  (CarComRepository, GetInitHwSettings, HwSettings)

Этот источник доказывает только присутствие строк. Не подтверждены
MethodDef, объявляющий тип, сигнатура метода, внешний MemberRef,
реальная инструкция call/callvirt, вызывающий список профилей,
отладочные метки или фактическое исполнение VIDA.

## Новый hash-pinned metadata-only preflight

emulator/tools/audit_vida_2015a_inithw_metadata.py

Автономный стандартный Python 3: без dnfile, pefile, ctypes,
reflection, .NET SDK, network API, SQL или запуска DLL.

В указанном локальном дереве ищет ровно по одному из трёх
оригинальных basename. Для каждого требует побайтное SHA256
совпадение с приведённым пином. При несовпадении прекращает
анализ без эвристик и не выводит прочитанные исходные данные.

Разбирает только ограниченные метаданные PE/CLR:
PE COM Descriptor, CLR BSJB streams, #~/#- table stream и
#Strings; таблицы TypeDef (0x02), MethodDef (0x06),
MemberRef (0x0A) с их описателями. Возвращает:
- число объявлений типа CarComRepository внутри каждого модуля;
- число объявленных MethodDef с именами GetInitHwSettings,
  GetHwSettings и vadis_GetHwSettings;
- число из этих MethodDef, принадлежащих объявленному типу
  CarComRepository;
- число MemberRef с каждым из трёх имён.

Важно: наличие MemberRef **не доказывает**, что конкретный
метод-вызыватель выполняет call/callvirt или что внешний метод
в итоге был выбран. Metadata-only анализ не декодирует IL-тела
и не определяет параметры. Отсутствие MemberRef с этим
именем не исключает рефлексию, динамический вызов,
передачу делегата, другой слой, либо вызов по другим
именам типов.

Из исходных сборок не публикуются пути к установке,
содержимое, исходный IL, оригинальные профили/ID,
строки ресурсов, init значения, VIN или CAN кадры.
Результат только фиксированные имена и числовые категории
для уже открыто перечисленных трёх DLL плюс SHA256.
При ошибке выводится только status/имя класса ошибки.

При наличии MethodDef доказательством текущего шага будет
его существование в конкретном SHA-pinned исходном бинарном
файле. Следующая независимая проверка — IL инструкции
GetInitHwSettings и соответствующих вызывающих методов,
сигнатуры параметров, фактическая сборка profile list и
возможность включения общего MY2009 профиля в этот список.
До этого наследование и скорость D2 строго не проверены.

## Windows — локальное выполнение владельцем

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

Только синтетические самодостаточные PE/CLR фикстуры:

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_metadata.py -v

После результата Ran 13 tests ... OK выполнить:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_metadata.py --folder 'E:\vida'

Это прочитает только три оригинальные DLL с проверкой SHA256.
Если имя одного файла встречается более одного раза или
хеш не совпал — штатный отказ и отсутствие угадывания
местоположения исходника. Параметр --folder должен указывать
тот же каталог установленной VIDA, что проверялся
предыдущим исходным бинарным аудитом.

На момент коммита выполнение новых 13 тестов на Windows
и новый результат CLR-метаданных не подтверждены.
Статическая проверка исходного кода — не CI PASS.

Сохраняются флаги false:
il_call_instructions_inspected,
memberref_name_proves_actual_callsite,
original_vida_2015a_profile_list_callers_verified,
original_vida_2015a_inheritance_verified,
d2_baudrate_verified, original_vida_readvin_accepted.

Draft PR не объединён. Main/development, оригинальные
VIDA/SQL Server, J2534/ECU/CEM, firmware и релизы не изменены.
