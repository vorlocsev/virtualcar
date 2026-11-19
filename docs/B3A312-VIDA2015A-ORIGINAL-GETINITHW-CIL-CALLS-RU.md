# B3A312 — оригинальные VIDA 2015A GetInitHwSettings: реальные IL callsite-кандидаты

Дата: 2026-11-19. Исследовательский Draft PR #376, без запуска
оригинальной VIDA, без записи в SQL Server, J2534 или CEM.

## Реальные результаты, уже полученные от владельца

Три оригинальные hash-pinned сборки, проверенные по SHA256:
- BizServices.CarCom.DB.DLL:
  a54117e6b2cc97c28bacf5df72f060ee8694de85291194046235bfd85a700be6
- BizServices.VehicleCommProvider.DLL:
  763c26d195ee7324fd08d6da1bf7304e0090a7220c29ec46038ae695db5a82e5
- Workflow.DLL:
  ba78b669efea360887d333353451e9411e82004e368b356f74200d8fcb427ebd

Результат владельца audit_vida_2015a_inithw_metadata.py:
- CarCom.DB имеет один TypeDef CarComRepository, ДВА
  MethodDef с именем GetInitHwSettings, из них ровно ОДИН
  определён в CarComRepository; 0 MemberRef с этим именем;
- VehicleCommProvider имеет один GetInitHwSettings MemberRef,
  ноль соответствующих MethodDef;
- Workflow имеет один GetInitHwSettings MemberRef,
  ноль соответствующих MethodDef.

Это подтверждает наличие исходного метода и внешних ссылок.
**Ни один MemberRef не доказывает вызов инструкции call/callvirt**;
две существующие локальные MethodDef не обязательно имеют общую
сигнатуру и не обязательно оба принадлежат CarComRepository.
Сигнатуры, конкретные источники аргументов и исходная цепочка
GetInitHwSettings оригинальной VIDA 2015A ещё не установлены.

## Новый инструмент

emulator/tools/audit_vida_2015a_inithw_il_calls.py

Работает только с перечисленными тремя оригинальными DLL, открывает
их как read-only бинарные файлы и сверяет SHA256. Входных файлов
не меняет, не загружает сборки в CLR и не выполняет код или SQL.

Повторно проверяет исходные TypeDef/MethodDef/MemberRef, извлекает
PE/RVA и CIL тела методов. В отличие от грубого поиска четырёх
байтов маркера, декодирует обычные CIL инструкции с границами
операндов. Только реальная инструкция call/callvirt, у которой
metadata token ссылается на именно найденный MemberRef либо
локальный MethodDef GetInitHwSettings, учитывается как
**статическая прямая точка вызова**.

Отдельно, но НЕ как вызовы, учитываются ldftn/ldvirtftn;
newobj также НЕ считается вызовом GetInitHwSettings.
Инструкция switch проверяется по числу элементов и не позволяет
случайно принять байты из таблицы переходов за opcode.
Любая неподдерживаемая/неполная CIL-инструкция приводит к
счётчику method_bodies_unsupported: если он не ноль,
all_present_cil_method_bodies_decoded=false. Сканирование
не может заявлять исчерпывающий результат при неполном IL.

В итоговом JSON есть только разрешённые имена трёх сборок,
их SHA256, числовые категории:
- method_bodies_present / decoded / unsupported;
- целевые MethodDef и MemberRef, число из них с owner
  CarComRepository;
- direct_call_memberref_sites / direct_call_local_methoddef_sites;
- отдельно прямые вызовы, у которых MemberRef/MethodDef
  при статическом разрешении относится к имени CarComRepository;
- distinct_methods_with_target_calls;
- ldftn_reference_sites_not_calls.

Это подсчёты без оригинальных IL-байтов, произвольных названий
классов-вызывателей, оригинальных ID профилей, пути установки,
INIT values, CAN кадров, VIN и источников SQL.
MemberRef с именем CarComRepository ещё не доказывает runtime
binding, метод может запускаться непрямо через интерфейс, reflection,
delegate или другие metadata token формы. MethodSpec и динамические
вызовы этим инструментом не разрешаются; их отсутствие в счёте
НЕ означает отсутствие соответствующего поведения.

## Критическая граница доказательства

Даже при реальном найденном call/callvirt это будет только
СТАТИЧЕСКАЯ точка вызова. Нужно отдельно восстановить
фактическую сигнатуру, роли аргументов, вызываемую ветку,
формирование списка CarCom T161 profile identifiers,
участие общего XC90 MY2009 InitHw-профиля и источник
эффективной скорости CEM D2. Владелец уже подтвердил:
43/43 точных XC90 V8 профиля согласованы по 10 измерениям
с единственным общим профилем с InitHw, но NULL не доказан
как wildcard, а folderLevel не доказан как реальный
приоритет в VIDA 2015A. Обе CEM D2 записи T121.busRate=NULL,
значение GGD не копировать.

## Windows owner-only

В C:\Users\vorloc\Projects\VirtualCar-B3A312:

    git pull --ff-only

Сначала только синтетические тесты (16 случаев, включая
ложные IL-токены внутри констант/строк, switch, callvirt,
ldftn, неподдерживаемый opcode и неверный SHA256):

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_il_calls.py -v

Только после "Ran 16 tests ... OK":

    py -3 .\emulator\tools\audit_vida_2015a_inithw_il_calls.py --folder 'E:\vida'

Если source hash не совпал, скрипт аварийно заканчивается
без попытки анализировать другой случайный бинарник.
Полученный JSON безопасен по контракту, но владелец должен
проверить его до отправки.

Статус при добавлении: новый Windows synthetic suite и реальные
IL вызовы на трёх исходных сборках **ещё не проверены**.
Статический обзор GitHub исходников не заменяет тестовый PASS.

В отчёте всегда false: static_calls_prove_execution,
callsite_arguments_or_profile_list_proven,
original_vida_2015a_generic_profile_inheritance_verified,
d2_baudrate_verified и original_vida_readvin_accepted.

Никакой PR merge, CI dispatch, изменения main/development, запуска
оригинальных функций VIDA, оригинальной установки SQL, прошивки,
J2534 или программирования ECU.


## Выполненный первоначальный IL-аудит и следующее уточнение (2026-11-19)

Владелец запустил предыдущий анализатор на точных SHA-pinned оригинальных
VIDA 2015A DLL. Фактически сообщено:

| Original module | Present IL | Decoded | Unsupported | Direct GetInitHwSettings MemberRef calls |
| --- | ---: | ---: | ---: | ---: |
| BizServices.CarCom.DB.DLL | 140 | 137 | 3 | 0 |
| BizServices.VehicleCommProvider.DLL | 175 | 175 | 0 | 1 |
| Workflow.DLL | 1719 | 1709 | 10 | 5 |

Всего 2021/2034 тел методов декодированы, 13 не декодированы;
найдено 6 настоящих статических call/callvirt к MemberRef с именем
GetInitHwSettings. Ни одна из шести ссылок в прежнем классификаторе
не имела parent **с простым именем CarComRepository**.
Из этого нельзя сделать вывод, что связи с репозиторием не существует:
это может быть ссылка на иной тип/интерфейс, а 13 тел не разобраны.
Ни один CALL не означает, что он исполнился в сессии владельца.

Уточнение на этом HEAD:
- target_memberref_parent_carcom_repository_rows;
- target_memberref_parent_hwsettings_rows;
- target_memberref_parent_other_or_unresolved_rows;
- target_methoddef_owner_hwsettings_rows / owner_other_rows;
- direct_target_calls_to_hwsettings_memberref;
- direct_target_calls_to_other_or_unresolved_memberref;
- distinct_target_caller_methods_in_carcom_repository,
  distinct_target_caller_methods_in_hwsettings,
  distinct_target_caller_methods_in_other_types.
  Последние три — число **различных методов-вызывателей**, НЕ
  количество инструкций вызова.
- method_bodies_unsupported_unknown_opcode,
  method_bodies_unsupported_truncated_or_invalid_operand,
  method_bodies_unsupported_other.
  Эти категории суммируются в method_bodies_unsupported.
- IL декодер также знает FE 19 no. prefix (корректный байт операнда
  позволяет безопасно сохранить границы следующей инструкции).

Никаких нестандартных имён оригинальных классов, IL-байтов или
реальных Profile ID инструмент не печатает. Текстовые категории
допускают только CarComRepository, HwSettings и другие/неизвестные.
Сравнение происходит по простому имени типа, не по полному
assembly-qualified имени и сигнатуре. Этого достаточно лишь для
ориентации следующего source audit, НЕ для утверждения о runtime
связывании конкретного MemberRef с CLR MethodDef.

Добавлены ещё 4 синтетических теста, всего **20**. Новые Windows
тесты и повторный анализ оригинальных DLL **ещё не выполнены**.
Прежние подтверждённые 6 статических точек вызова и 13 IL
декодерных пропусков относятся к **старой версии анализатора**;
не переносить их механически на новый HEAD.

Запуск на локальной машине владельца, только после обновления ветки:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_il_calls.py -v

При Ran 20 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_il_calls.py --folder 'E:\vida'

Дальше потребуется отдельный анализ сигнатур, метаданных родителя
MemberRef (включая namespace и assembly), аргументов callsite и
реальной процедуры формирования списка профилей. Этим счётчиком
наследование InitHw, скорость D2 и ReadVin не подтверждаются.


## Повторная классификация владельца и разбор MemberRefParent (2026-11-19)

Владелец запустил предыдущую 20-тестовую версию анализатора
на тех же оригинальных SHA-256 сборках. JSON подтвердил:
- CarCom.DB: 137/140 IL, три неизвестных опкода, 0 подтверждённых
  прямых вызовов GetInitHwSettings среди успешно прочитанных тел,
  два исходных MethodDef с этим именем, из них один определён в
  CarComRepository, другой — в неизвестном здесь классе;
- VehicleCommProvider: 175/175 IL, один прямой call/callvirt
  через MemberRef с классом other_or_unresolved, из одного
  метода-вызывателя вне CarComRepository/HwSettings;
- Workflow: 1709/1719 IL, пять прямых call/callvirt через
  такой же неполностью разрешённый MemberRef, 8 неизвестных
  опкодов, два ошибочных/неполных операнда, пять
  методов-вызывателей других типов.

Всего точно 6 подтверждённых **статических** вызовов
именованного MemberRef в декодированных методах и
13 не полностью декодированных тел. Отсутствие совпадения
с простыми именами CarComRepository/HwSettings не значит,
что связь невозможна через интерфейс, адаптер, nested TypeRef,
MethodDef/TypeSpec или другой промежуточный уровень.
Не установлен ни один исходный аргумент profileList.

### Узкое расширение того же анализатора

Добавлено раздельное отображение MemberRefParent coded-tag:
- typedef / typeref / moduleref / methoddef / typespec;
- TypeRef.ResolutionScope: module / moduleref / assemblyref /
  nested_typeref / unresolved (это **тип области**, не имя
  оригинальной DLL/сборки);
- фиксированные классы простых имён типа: CarComRepository,
  ICarComRepository, HwSettings, лексическая другая
  I*CarComRepository, либо other_or_unresolved.

Признак ICarComRepository, даже если появится, — лишь
проверенный текст имени в метаданных, **не доказательство
подлинной интерфейсной реализации, runtime binding или
семантики вызова**. Full namespace, AssemblyRef name,
GenericInst, сигнатуры return/arguments и actual caller-flow
этот этап ещё не разрешает.

Для оставшихся 11 неизвестных opcodes добавлен
unsupported_unknown_opcode_histogram: агрегированные
фиксированные имена opcode в формате cil_opcode_XX / FE_XX,
не raw IL bytes, без RVA, MethodDef token, тела методов,
строк/значений из сборок. Одно такое значение сообщает
только о месте до которого дошёл декодер; оно само по себе
не доказывает, что бинарник повреждён (возможна ошибка
таблицы opcode / неверная длина предыдущего операнда).

Проверяется сумма всех MemberRef-классов и сумма частот
неизвестных инструкций против прежних счётчиков. Добавлено
6 новых synthetic tests с TypeRef, неподдерживаемыми опкодами,
ошибочным parent row и несуществующим MemberRef token.
Всего **26** синтетических методов в тестовом файле,
новый Windows результат и оригинальный JSON **пока отсутствуют**.

Из корня checkout PR #376:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_il_calls.py -v

Только если 26 тестов OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_il_calls.py --folder 'E:\vida'

Отдельный источник-верификационный gate после нового JSON:
разбор подтверждённых сигнатур MethodDef/MemberRef и
namespace/assembly resolution, затем IL источников
аргументов и фактического формирования списка профилей.

По-прежнему FALSE: static_calls_prove_execution,
memberref_owner_name_proves_runtime_target_binding,
callsite_arguments_or_profile_list_proven,
original_vida_2015a_generic_profile_inheritance_verified,
d2_baudrate_verified, original_vida_readvin_accepted.

Никаких изменений оригинальных DLL, SQL, VIDA,
автомобиля/J2534, main/development и CI/job/release.


## Следующий исходный результат: ICarComRepository + исправление leave (2026-11-19)

Фактический owner-private запуск предыдущей 26-тестовой версии:

- BizServices.CarCom.DB.DLL: 0 обнаруженных call/callvirt в 137/140
  декодированных телах, 3 ошибки неизвестного opcode
  (0x24, 0xA9, 0xE3), два MethodDef GetInitHwSettings,
  один из них CarComRepository.
- BizServices.VehicleCommProvider.DLL: 1/1 GetInitHwSettings MemberRef
  имеет родитель TypeRef с простым именем **ICarComRepository**,
  ResolutionScope категории AssemblyRef; найден ровно один
  статический call/callvirt к этому MemberRef в 175/175 телах.
- Workflow.DLL: тот же класс MemberRef TypeRef ICarComRepository,
  ResolutionScope AssemblyRef; найдено пять статических
  call/callvirt в 1709/1719 декодированных телах. Неизвестные
  opcode-категории: 0x24, 0xA6, 0xA9, 0xBF, 0xC7, 0xF2,
  0xF3, 0xFC по одной, плюс две ошибки operand/switch.

Результат означает шесть статических инструкций через
**интерфейс ICarComRepository** по простому имени TypeRef.
Ни полный AssemblyRef identity, ни полный namespace,
ни бинарная сигнатура, ни фактическая реализация интерфейса
на рантайме пока не сопоставлены. Не утверждать, что все
шесть исполняются или доходят до нужного экземпляра CEM.

### Найдена ошибка нашего декодера

Таблица размеров CIL операндов неправильно относила
leave (0xDD) и leave.s (0xDE) к безоперандным операциям.
Согласно Microsoft Learn, leave имеет 4-байтовый
целевой offset, leave.s — 1-байтовый offset:

- https://learn.microsoft.com/en-us/dotnet/api/system.reflection.emit.opcodes.leave
- https://learn.microsoft.com/en-us/dotnet/api/system.reflection.emit.opcodes.leave_s

Это могло создавать ложные неизвестные opcode в байтах
переходов или нарушать границы следующих инструкций.
Исправлено: 0xDD теперь 4-байтовый operand; 0xDE 1-байтовый.
Добавлены 3 синтетических регрессии на boundary/callsite
(27–29). Старые числа 13 недекодированных тел относятся
к ошибочной версии декодера и **не могут служить вердиктом
о содержимом исходных бинарных файлов**.

### Дополнительная контрактная проверка

В тот же анализатор добавлены:
- carcom_repository_direct_icarcomrepository_interfaceimpl_rows:
  количество оригинальных CLR InterfaceImpl записей, где
  TypeDef называется CarComRepository, а присоединённый
  TypeDef/TypeRef — ICarComRepository. Только статическое
  имя, не runtime binding/MethodImpl resolution.
- getinithw_methoddef_parameter_count_categories
  и getinithw_memberref_parameter_count_categories:
  категории числа параметров Methods по заголовку
  Blob method signature, без публикации реальных сигнатур,
  имён/значений типов и аргументов.
- getinithw_methoddef_has_this,
  getinithw_memberref_has_this и vararg counts.
  Заполненные сигнатуры берутся из оригинального #Blob,
  недоступность считается отдельно, ничего не угадывается.

Добавлены ещё 4 synthetic tests (30–33) для
InterfaceImpl и двух вариантов сжатой method signature,
всего **33** тестовых метода в файле.
**Ни новый Windows тестовый запуск 33/33, ни повторный
аудит исходных SHA-256 сборок пока не проведены.**

Из корня PR checkout, по одной строке:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_il_calls.py -v

Только при Ran 33 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_il_calls.py --folder 'E:\vida'

В новом результате важны: all_present_cil_method_bodies_decoded,
method_bodies_unsupported, unsupported_unknown_opcode_histogram,
carcom_repository_direct_icarcomrepository_interfaceimpl_rows,
два словаря getinithw_*_parameter_count_categories, а также
прежние шесть прямых call/callvirt.

Даже совпадение InterfaceImpl и parameterCount **не докажет**
точную связку вызываемый MemberRef → исходный MethodDef:
нужны полные TypeRef/AssemblyRef и сигнатуры с токенами типов,
MethodImpl/implicit interface method mapping и доказательство
реального формирования списка T161 profile identifiers
в caller. Никакое заполненное значение GGD нельзя автоматически
считать D2 bitrate, а ReadVin original VIDA не подтверждён
для виртуального VIN в зафиксированных результатах.

Оригинальные DLL, VIDA/SQL, J2534/CEM, main/development
и релизы в этом этапе не изменяются.
