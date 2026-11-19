# B3A312 — оригинальная VIDA 2015A: аргументы newobj и получатель callvirt

19 ноября 2026; isolated Draft PR #376. Оригинальная установленная VIDA
2015A, SQL/J2534/CEM, main/development и CI не изменяются.

## Подтверждённые исходные результаты владельца

Реальный read-only SHA256-pinned audit_vida_2015a_inithw_eh_regions.py
для трёх локальных оригинальных DLL:
- CarCom.DB: 140 CIL method bodies, 0 внешних GetInitHwSettings calls.
- VehicleCommProvider: 175 method bodies; 1 GetInitHwSettings callvirt
  внутри try с ОДНОЙ small EH секцией и ДВУМЯ обработчиками
  (catch=1, finally=1). Нет границы EH между непосредственно
  предшествующим ldfld и вызовом.
- Workflow: 1719 bodies; все 5 target calls вне EH регионов,
  0 extra sections в их пяти методах.

Ещё ранее из исходных owner-original JSON установлено:
- все 6 вызовов GetInitHwSettings — callvirt после ldfld FieldDef;
  во всех 6 форма/локальный TypeDefOrRef class FieldSig согласуется
  с единственным явным параметром GetInitHwSettings;
- VehicleCommProvider target FieldDef записывается двумя stfld:
  в конструкторе сразу после newobj MemberRef (constructor
  принимает ОДИН явный параметр, его owner type совпадает
  с FieldDef class TypeDefOrRef); в другом методе сразу после
  callvirt MemberRef (ZERO явных параметров, но есть receiver;
  return type совпадает с типом FieldDef);
- Workflow target FieldDef записывается одной stfld в .ctor
  сразу после newobj MemberRef с ОДНИМ явным параметром;
  owner type совпадает с FieldSig;
- нет прямого branch/switch/leave target прямо на 3 stfld
  или 6 GetInitHwSettings calls. Это не доказательство
  непрерывного потока данных и не доказывает state ReadVin.

Ни один из JSON не содержит оригинальных имён полей/методов,
типовых индексов, исходных IL или профилей/настроек.

## Новый узкий аудитор — на шаг ближе к входным аргументам

Файл emulator/tools/audit_vida_2015a_inithw_writer_inputs.py

Оригинальные три SHA256 DLL только читаются; код не выполняет
сборки и не редактирует файлы. Сканирует все IL MethodDef и
определяет FieldDef, прочитанные при GetInitHwSettings calls.
Затем для stfld в эти FieldDef:
1. Проверяет предыдущую newobj/callvirt MemberRef, её число
   явных параметров и same-module типовой индекс владельца
   newobj либо возвращаемого типа callvirt;
2. Для одного явного параметра newobj или receiver нуль-
   параметрного callvirt определяет ТОЛЬКО класс инструкции,
   непосредственно перед newobj/callvirt:
   load_arg_or_address, load_local_or_address,
   load_field_or_address, nested_call_or_calli_unresolved_return,
   new_object_or_array, load_numeric, load_null,
   другие фиксированные категории или none.
3. Отмечает отдельными счётчиками, если прямой branch/switch/leave
   может попасть непосредственно к newobj/callvirt (producer)
   либо к предыдущей инструкции (precursor). Отсутствие таких
   переходов НЕ исключает другую семантику CFG, EH,
   перезаписи локальных переменных и aliasing.
4. Отмечает только наличие MoreSects в методах-писателях;
   не подменяет этот флаг полноценным EH/stack analysis.

Выводятся только числовые категории:
- immediately_before_writer_producer_opcode_family;
- writer_predecessor_kind_counts;
- writer_memberref_arity_by_kind;
- writer_type_relation_by_kind;
- producer_has_direct_branch_entry;
- producer_input_has_direct_branch_entry;
- writer_method_has_more_sections;
- writer_source_arity_as_expected.

Все оригинальные IL bytes, branch offsets, metadata row IDs,
имена неизвестных методов, типов и полей, аргументные значения,
VIN, profileIdentifiers, пути установки остаются приватными
и не экспортируются.

**Главная граница:** инструкция перед newobj или callvirt может
быть лишь текстовым соседом, но не реальным источником
аргумента или receiver по CLR stack. При ветвлениях, EH,
нестандартном IL, aliasing или сложном выражении остаётся
необходимость точного stack/CFG и межметодного def-use.
Даже категория ldarg не означает, что известен состав
списка профилей, переданного при начальном VIDA ReadVin.

## Windows: локально только у владельца

Из корня checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_writer_inputs.py -v

Только после Ran 19 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_writer_inputs.py --folder 'E:\vida'

На момент коммита **новые 19 synthetic Windows tests и оригинальный
аудит ещё НЕ выполнялись**. GitHub static source review — не
замена тестов. Ни ReadVin acceptance, ни generic MY2009 XC90 InitHw,
ни CEM D2 baudrate, ни действительные profileIdentifiers
по-прежнему не доказаны.

Без merge, CI/workflow dispatch, релизов, изменения original VIDA
или основных веток.
