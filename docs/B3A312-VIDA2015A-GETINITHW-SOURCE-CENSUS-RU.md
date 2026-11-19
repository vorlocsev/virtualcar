# B3A312 — первичная атрибуция оригинальной VIDA GetInitHwSettings

Дата: 2026-11-19. Draft PR #376.

## Что доказано в приватной офлайн-копии

Для XC90 V8 MY2009 все 43 точных BaseData профиля однозначно связаны
с CarCom.T161_Profile.identifier; у них нет прямого InitHw.
Общий XC90 MY2009 профиль с NULL engine имеет одну прямую InitHw
связь; его T130_Init содержит 9 заполненных T131_InitValue, семь
с типами, лексически содержащими baud/speed. Все 43 точных профиля
имеют с общим одинаковые T161 модель и год; на общем двигатель
NULL, folderLevel численно ниже. Для прочих семи T161 измерений
все 43 сравнения показывают NULL на общей стороне и ноль
конфликтующих заполненных FK, по результатам владельца.
Прямые CEM D2 конфигурации 2/2 имеют NULL T121.busRate; GGD
имеет один non-NULL busRate, который нельзя переносить на D2.

**Ни одно из этих наблюдений не подтверждает алгоритм выбора
GetInitHwSettings оригинальной VIDA 2015A.** NULL на общем
профиле — не доказанный wildcard, а folderLevel — не доказанное
правило выбора. Оригинальная процедура не исполнялась.

## Независимый источник — открытый исследовательский порт VIDA 2014D

Pin: spnda/volvo_vida_db,
commit e2f8ee165e373360d7f7fd0e80298f68c25bc07e,
scripts/carcom.py, get_hw_settings(), строки 273–291.

В этом порте функция получает *готовый* список profile_identifiers,
а не вычисляет предков сама. Затем выбирает прямые
T161_Profile.identifier → T136_InitHw_Profile → T131_InitValue
→ T132_InitValueType, сортирует по p.folderLevel и v.sortOrder,
перезаписывает значения с одинаковым именем типа более поздними
строками. Документация порта приписывает происхождение методу
Vcc.Vida.DiagSwdl.BizServices.CarCom.DB.CarComRepository.GetInitHwSettings
и классу EcuData.HwSettings.

Это ценный проектный ориентир. Он **не атрибутирует** конкретную
сборку оригинальной VIDA 2015A владельца, не показывает caller,
не доказывает, что общий профиль включён в фактически переданный
список, и не подтверждает оригинальный порядок разрешения настроек.

## Следующий безопасный локальный шаг

emulator/tools/audit_vida_2015a_inithw_binary_signatures.py

Открывает только *.DLL и *.EXE в указанной локальной папке
установленной VIDA, не загружая/не исполняя .NET сборки,
не обращаясь к SQL Server, J2534, ECU и VIDA API. Потоково
проверяет фиксированные ASCII/UTF-16LE токены:
GetInitHwSettings, vadis_GetHwSettings, GetHwSettings,
CarComRepository, HwSettings, folderLevel, T136_InitHw_Profile.

Для совпавших файлов выдаёт только basename (или закрытую
категорию для нестандартного имени), SHA-256 и Boolean
наличия перечисленных строк. Вся остальная информация
из исходного бинарного файла остаётся в памяти и не выходит
в JSON. Нет дизассемблирования, IL-декодирования, выгрузки
ресурсов и запуска оригинальных программ.

Ограничения: не больше 30 000 DLL/EXE, 8 GiB суммарно,
128 MiB на файл, 180 секунд; при превышении возвращается
класс ошибки, а не незавершённая «успешная» классификация.
Сканируются только regular files, симлинки исключены.

**Совпадение текста — не MethodDef и не call graph.** После
такого preflight потребуется независимый точный SHA-pinned
metadata/IL разбор кандидатной сборки и проверка её
подлинной принадлежности установленной VIDA 2015A.
Анализ только исходной библиотеки без caller тоже не докажет,
как приложение формирует profile_identifiers для XC90 V8.

## Windows: выполнение владельцем

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

Сначала 13 новых синтетических тестов (не используют VIDA):

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_binary_signatures.py -v

Только после OK, локальный бинарный preflight (не запускает DLL):

    py -3 .\emulator\tools\audit_vida_2015a_inithw_binary_signatures.py --folder 'E:\vida'

Если оригинальная VIDA расположена не в этом каталоге, параметр
--folder должен указывать фактическую локальную папку установленного
приложения. Прежде чем передавать JSON, проверить список basename:
не передавать личные или закрытые имена файлов. Не прикладывать
оригинальные бинарные файлы, их ресурсы, IL/исходники, приватные
идентификаторы профилей и VIN.

Результаты сканирования и 13 синтетических тестов на исходном
Windows компьютере **ещё не получены**. Статический аудит GitHub
не заменяет тест. PR остаётся Draft, original SQL/VIDA и
development/main не изменялись, CI/jobs не запускались.

Всегда false: token_match_proves_methoddef_or_il,
vida_2015a_procedure_callers_verified,
runtime_selected_profile_set_verified,
inherited_hardware_settings_verified, d2_baudrate_verified,
original_vida_readvin_accepted.
