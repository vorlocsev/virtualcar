# B3A312 — исходная VIDA 2015A: предшественники stfld и совпадение методов записи/вызова

2026-11-19. Draft PR #376. Только статический read-only аудит строго
трёх оригинальных SHA-256-закреплённых DLL VIDA 2015A, без запуска
оригинальной VIDA, SQL, J2534 или CEM.

## Фактическое доказательство владельца до этого этапа

Оригинальный JSON владельца из audit_vida_2015a_inithw_field_writes.py:
- BizServices.CarCom.DB.DLL: 140 CIL методов, нет целевых внешних вызовов;
- BizServices.VehicleCommProvider.DLL: 175 CIL методов,
  1 GetInitHwSettings callvirt после локального FieldDef ldfld;
  1 distinct FieldDef; точное равенство одного локального
  TypeDefOrRef coded index между FieldSig и параметром MemberRef
  1/1; 2 aligned stfld в это FieldDef, по одному в двух
  разных MethodDef: 1 в .ctor, 1 в другом методе;
- Workflow.DLL: 1719 CIL методов,
  5 GetInitHwSettings callvirt после одного и того же локального
  FieldDef ldfld; точное совпадение локальных TypeDefOrRef
  coded index 5/5; 1 aligned stfld в это FieldDef,
  в одном MethodDef .ctor;
- total 6/6 exact local type references, 2 distinct
  FieldDef (ONE PER MODULE, NOT A SINGLE SHARED FIELD),
  3 static aligned stfld, 3 distinct writer methods,
  no stsfld.

Это не означает, что во всех реальных вызовах было одно
фиксированное значение, а в Workflow поле может быть заполнено
из неизвестного аргумента конструктора. Выполнение
MethodDef / CIL, список профилей и runtime состояние НЕ
подтверждены.

## Новая узкая классификация без реконструкции стека

Расширение ранее существующего файла:
emulator/tools/audit_vida_2015a_inithw_field_writes.py

Добавлены числа:
- immediately_preceding_stfld_opcode_family_counts:
  только фиксированные категории предыдущей инструкции
  до каждого найденного stfld/stsfld, например load_arg_or_address,
  load_local_or_address, nested_call_or_calli_unresolved_return,
  new_object_or_array, load_field_or_address, none,
  other_or_unresolved;
- distinct_target_call_methods_in_module;
- distinct_target_call_methods_with_local_field_write;
- distinct_target_call_methods_without_local_field_write;
- target_field_write_sites_in_target_call_methods;
- target_field_write_sites_outside_target_call_methods.

Это только близость инструкций в CIL и факт принадлежности
к одному исходному MethodDef. Совпадение MethodDef не
устанавливает порядок исполнения записей и вызовов на
любом пути управления и не отслеживает receiver aliasing.
Соседний opcode перед stfld может загружать не параметр,
а другую часть выражения. Значение объекта, передаваемого
в GetInitHwSettings, не считается доказанным.

Счётчики согласуются с числом найденных записей и
различных методов. Приватные имена полей/методов,
оригинальные metadata tokens, IL bytes, профили, VIN,
пути исходных DLL не выводятся. Три хеша SHA-256
по-прежнему обязательны. Оригинальные файлы только читаются.

## Локальная проверка

Из checkout ветки feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_field_writes.py -v

Только после Ran 25 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_field_writes.py --folder 'E:\vida'

Было 19 synthetic tests, добавлено ещё 6 на категории
предшествующих инструкций и наличие/отсутствие
записи в том же MethodDef, итого 25. Новые тесты на
Windows и оригинальный JSON с новыми категориями ещё
не запускались / не подтверждены. Static source review
не означает 25 PASS.

Следующий отдельный gate: ограниченный граф
потока управления с корректными границами try/catch/finally,
стековая симуляция callvirt/GetInitHwSettings и stfld;
сопоставление producer и consumer с явной категорией
unresolved. Не делать вывод об унаследованном общем
InitHw для XC90 MY2009, фактической скорости CEM D2
или принятом VIN в оригинальной VIDA.

Флаги неизменно false:
- preceding_stfld_opcode_proves_value_source;
- writer_and_caller_same_method_proves_write_reaches_call;
- exact_local_type_token_match_proves_argument_value_source;
- control_flow_stack_or_exception_handlers_traced;
- field_assignments_or_runtime_values_verified;
- profile_identifiers_argument_proven;
- original_vida_2015a_generic_profile_inheritance_verified;
- d2_baudrate_verified;
- original_vida_readvin_accepted.

Никакого workflow dispatch, CI, merge, публикации релиза
или изменений main/development.
