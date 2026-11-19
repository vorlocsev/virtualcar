# B3A312 — VIDA 2015A: число параметров писателей и входящие IL-переходы

19 ноября 2026, только Draft PR #376. Три исходные неизменные
SHA256-закреплённые DLL анализируются read-only без запуска VIDA,
CLR, SQL, J2534 или ECU. Не запускать CI/workflow, не делать merge.

## Фактический результат владельца до этого шага

Исходный JSON audit_vida_2015a_inithw_writer_memberrefs.py:
- VehicleCommProvider: один GetInitHwSettings callvirt читает локальный
  FieldDef; 2 stfld в это поле, оба вне метода вызывающего
  GetInitHwSettings. В .ctor непосредственно перед stfld находится
  newobj MemberRef; тип владельца конструктора — тот же локальный
  CLR TypeDefOrRef coded index, что и тип поля. В другом методе
  перед stfld — callvirt MemberRef с точно таким же локальным
  CLASS return token, что тип поля.
- Workflow: пять GetInitHwSettings callvirt читают один локальный
  FieldDef; один stfld вне всех пяти вызывающих методов, в .ctor,
  непосредственно после newobj MemberRef с точным равенством
  локального типа владельца конструктора и типа поля.
- Таким образом 3/3 совпадения декларативных CLR типов:
  два newobj owner и один callvirt return. Нет различий и
  неразобранных случаев. Оригинальные сборки не исполнялись.

Всё это НЕ доказывает последовательность записи в полях,
попадание значений в GetInitHwSettings, список T161
profileIdentifiers, использование общего XC90 InitHw, D2 bitrate
или успешный ReadVin оригинальной VIDA.

## Новый консервативный аудит

Файл:
emulator/tools/audit_vida_2015a_inithw_stack_boundaries.py

Для того же строго SHA-256-набора и только в памяти:
- читает MemberRef сигнатуры newobj и callvirt непосредственно
  перед целевыми stfld. Число явных аргументов в сигнатуре
  выводит только категориями zero, one, two_or_more, unclassified.
  Значения, имена параметров, типовые индексы не публикуются;
- по границам CIL-инструкций собирает прямые цели short/long
  branch, leave и switch, проверяя выравнивание на начала
  инструкций. Считает, может ли статический переход
  попасть прямо на исследуемый stfld или
  GetInitHwSettings call/callvirt (после ldfld);
- отдельно отмечает наличие флага MoreSects в fat method header.
  Это НЕ разбор try/catch/finally, а лишь предупреждение,
  что могут присутствовать дополнительные IL-секции;
- сверяет суммы результатов, не выводя исходные IL offsets,
  токены, локальные/оригинальные имена, типы, значения,
  paths, VIN или профили.

Ключевые поля:
writer_predecessor_arity, sink_with_static_direct_branch_entry,
sink_without_static_direct_branch_entry,
sink_in_method_with_more_sections,
sink_in_method_without_more_sections.

Отсутствие прямого перехода на stfld не доказывает отсутствие
других CFG-веток и стека, а отсутствие MoreSects не доказывает
происхождение значения. Классы параметров — только статическая
сигнатура, не содержимое аргументов или реально выполненные
методы. Все флаги доказательства runtime/ReadVin остаются false.

## Запуск на Windows владельца

Из корня checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_stack_boundaries.py -v

Только после Ran 18 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_stack_boundaries.py --folder 'E:\vida'

На момент добавления эти 18 synthetic Windows-тестов и
новый исходный аудит оригинальных трёх DLL НЕ выполнялись.
GitHub static source review не является успешным тестом.

Следующий этап зависит от реального отчёта: при потенциальном
входящем переходе или дополнительных секциях потребуется
CFG с точным EH; при отсутствии — всё равно отдельная
консервативная стековая симуляция вокруг источников
и потребителей, затем receiver aliasing, def-use и
origin profileIdentifiers. Ничего не переносить
в Virtual Car как подтверждённый D2 InitHw.
