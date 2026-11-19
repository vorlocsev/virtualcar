# B3A312 — VIDA 2015A: тип аргумента нового объекта и слот receiver

Дата: 19 ноября 2026. Только отдельная исследовательская ветка
Draft PR #376; оригинальные VIDA DLL/SQL/J2534/CEM, main/development
не менять, CI или workflows не запускать.

## Проверенный результат предыдущего оригинального owner-only аудита

Из audit_vida_2015a_inithw_writer_inputs.py, source-only SHA256
на тех же трёх оригинальных DLL:
- BizServices.CarCom.DB.DLL: 140 методов CIL, 0 внешних target callsites;
- BizServices.VehicleCommProvider.DLL: 175 CIL методов,
  один GetInitHwSettings callvirt и два stfld в локальный FieldDef:
  в .ctor стоит «nested call/calli family → newobj(1 param) → stfld»,
  в другом методе «ldarg family → callvirt(0 explicit params)
  → stfld». До producer/precursor нет входящих direct
  branch/switch/leave target; оба writer methods без MoreSects;
- Workflow.DLL: 1719 CIL методов, 5 GetInitHwSettings callvirt
  через один местный FieldDef, единственная локальная запись
  «ldstr → newobj(1 explicit param) → stfld» в .ctor;
  direct branch entries 0, writer MoreSects отсутствует.
- Все три MemberRef producer-операции имеют тот же
  локальный class TypeDefOrRef, что тип соответствующего поля
  (newobj owner 2/2 и callvirt return 1/1).
- Ранее EH-аудит подтвердил, что один target GetInitHwSettings
  call в VehicleCommProvider находится в try с одним catch и
  одним finally; предыдущий ldfld в той же EH-области.
  Все 5 Workflow calls вне EH.

Ни одна из этих находок не доказывает, что реально передаётся
конкретный профайл, что общий XC90 MY2009 InitHw используется
или что оригинальный VIDA принял VIN.

## Новый audit source-only уровня CLR MethodSig

Файл:
emulator/tools/audit_vida_2015a_inithw_precursor_types.py

Инструмент читает те же ровно три SHA-256-pinned original DLL
строго read-only, не загружая CLR сборки и не выполняя VIDA.
Наружу сообщает только агрегированные категории, не публикуя
реальный ldstr User String, имена типов/методов, IL bytes,
CIL offsets, metadata tokens, сигнатуры, VIN, profile ID и
пути установки.

Для target FieldDef stfld с предшествующим newobj MemberRef:
1. Читает MethodSig конструктора, определяет тип его
   ЕДИНСТВЕННОГО параметра: string, class, primitive или
   other/unclassified.
2. Если прямо перед newobj стоит ldstr: проверяет только
   ELEMENT_TYPE_STRING у параметра конструктора, результат
   equal/different/unclassified, НЕ значение строки.
3. Если перед newobj стоит вложенный call/callvirt/calli:
   классифицирует конкретную инструкцию и источник
   MethodDef/MemberRef/other. Для локального MethodDef или
   MemberRef читает простую CLR return signature и сравнивает
   её с единственным параметром newobj (в пределах одной
   сборки, TypeDefOrRef coded token хранятся только в памяти).
   Для calli (StandAloneSig) пока unclassified — без
   подстановки произвольного return type. При mismatch это
   не доказательство невозможности наследования/приведения.
4. Для target FieldDef stfld, следующего после нуль-параметрного
   callvirt, если перед callvirt стоит ldarg/ldarga,
   определяет только индексную категорию: slot0, slot1,
   slot2plus или соответствующую address_slot категорию.
   Это НЕ подставляет исходное значение receiver и
   не доказывает, что slot0 равен this без проверки
   MethodDef HasThis/потока управления.

JSON ключи:
- producer_input_source_counts;
- newobj_constructor_one_param_kind;
- newobj_ldstr_constructor_parameter_relation;
- newobj_nested_call_opcode_counts;
- newobj_nested_call_token_kind_counts;
- newobj_nested_call_return_to_constructor_parameter_relation;
- callvirt_receiver_arg_slot_counts;
- callvirt_receiver_is_address / is_value;
- target_field_stfld_sites, newobj_producer_sites,
  callvirt_producer_sites.

Граница: простое совпадение локальной MethodSig/FieldSig
не доказывает фактическое значение операнда на IL stack,
вызов/порядок исполнения, состояние полей, aliasing,
первоначальный ReadVin и T161→T136 fallback. Без
interprocedural stack/CFG и последующей проверки оригинальной
VIDA ReadVin нельзя считать работу эмулятора принятой.

## Расширение: локальный MethodDef и сигнатура slot1

Дополнительно возвращаются только фиксированные агрегаты:
- nested_local_callvirt_methoddef_sites;
- nested_local_callvirt_methoddef_signature_counts:
  instance/static × zero/one/two_or_more explicit;
- nested_local_callvirt_immediate_input_family:
  фиксированный opcode family прямо перед nested local callvirt;
- callvirt_writer_slot1_method_signature_counts:
  instance_first_explicit / static_second_explicit /
  out_of_signature_or_unclassified;
- callvirt_writer_receiver_parent_token_kind_counts:
  typedef / typeref / other_or_unclassified;
- callvirt_writer_slot1_type_vs_receiver_parent:
  exact_same_module_type / different_type / unclassified.

Код проверяет original MethodDef и MemberRef metadata layout
в пределах одного и того же модуля. Числа не могут установить
semantic CLR assignability через наследование, runtime aliasing
или фактическое значение receiver.

## Выполнение локально на Windows владельца

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_precursor_types.py -v

Только если Ran 25 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_precursor_types.py --folder 'E:\vida'

Владелец уже выполнил предыдущие 18-case source checks на трёх
оригинальных SHA-pinned DLL и передал только JSON, а не
отдельный transcript unittest. Результат:
VehicleCommProvider: nested callvirt METHODDEF перед newobj,
возвращаемый CLASS совпадает с CLASS единственного параметра
конструктора 1/1; другой writer — ldarg.1 перед нуль-параметрным
callvirt, receiver value slot1, не address.
Workflow: ldstr непосредственно перед newobj, конструктор
принимает STRING, строгое type-match 1/1.

Этап расширен шестью дополнительными собственно synthetic
регрессиями (всего 25) на HasThis/arity локального MethodDef,
инструкцию до nested callvirt и сигнатуру метода-писателя
со slot1 (instance first explicit versus static second explicit),
сопоставление его SIMPLE CLASS TypeDefOrRef с MemberRefParent
receiver owner внутри одного CLR-модуля.

На момент этой ревизии повторный Windows unittest **25 tests**
и повторный аудит оригинальных DLL с новыми полями **НЕ
выполнялись / не подтверждены**. Static review не означает PASS.
Не утверждать, что slot1 реально был receiver, даже при
совпадении локальной CLR ссылки: требуется CIL operand-stack,
branch entry, aliasing и interprocedural def-use. Никаких workflow dispatch, merge,
релизов и изменений исходной VIDA.
