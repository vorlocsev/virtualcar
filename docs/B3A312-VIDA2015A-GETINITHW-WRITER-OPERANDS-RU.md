# B3A312 — VIDA 2015A: точный предшественник stfld

19 ноября 2026. Только Draft PR #376, оригинальная VIDA 2015A
используется как локальный read-only источник. Не запускать оригинальные
DLL/SQL/J2534/CEM, не менять main/development, не запускать CI/workflow.

## Фактическое доказательство владельца до изменения

Владелец выполнил прежнюю ревизию
emulator/tools/audit_vida_2015a_inithw_field_writes.py на трёх
строго SHA256-закреплённых оригинальных DLL и передал JSON:

- BizServices.CarCom.DB.DLL: 140 CIL тел; внешних target вызовов нет.
- BizServices.VehicleCommProvider.DLL: 175 CIL тел, 1 callvirt
  ICarComRepository.GetInitHwSettings через ldfld локального FieldDef.
  Совпадение FieldSig и единственного параметра MemberRef по
  точному локальному TypeDefOrRef index — 1/1. Поле записано
  двумя отдельными stfld в двух других MethodDef (один .ctor,
  один other). Предшествующие opcode FAMILY:
  new_object_or_array=1, nested_call_or_calli_unresolved_return=1.
  Методы-писатели не являются методом target callvirt.
- Workflow.DLL: 1719 тел, 5 callvirt в 5 отдельных MethodDef
  через одно и то же локальное FieldDef, точный локальный
  TypeDefOrRef index совпадает 5/5. Единственный stfld
  находится в .ctor, за пределами всех пяти вызывающих методов.
  Перед stfld: new_object_or_array=1.
- Итого 6 статических точных совпадений локальных TypeDefOrRef,
  2 разных FieldDef (один в каждой сборке), 3 stfld в 3
  различных MethodDef, 0 stsfld. Ни один writer MethodDef
  не совпал с target-caller MethodDef.

Это НЕ доказательство, что поле фактически содержит профили
XC90, что запись выполняется на пути ReadVin, что объект поля
был передан как единственный аргумент, или что поле было
инициализировано конкретным конструктором в рантайме.

## Новая строго ограниченная классификация

В том же emulator/tools/audit_vida_2015a_inithw_field_writes.py
добавлено:
- preceding_stfld_exact_opcode_counts: фиксированные числа
  для newobj, newarr, call, callvirt, calli, other_or_none;
- preceding_stfld_operand_token_kind_counts: только классы
  MethodDef, MemberRef, MethodSpec, TypeDef, TypeRef,
  TypeSpec, StandAloneSig, not_applicable; row ID не выводится;
- preceding_stfld_opcode_by_writer_method_family: кросс-таблица
  [instance_constructor, type_initializer, other_named_method]
  × [newobj, newarr, call, callvirt, calli, other_or_none].
- writer_write_sites_by_method_family: количество статических
  инструкций записи, а не число различных методов-писателей.

Скрипт проверяет формат 4-байтовых операндов методов/типов и
допустимые категории metadata table для каждого типа инструкции.
Числа согласуются с прежними target_fielddef_stfld_write_sites
и target_fielddef_stsfld_write_sites. Имена методов, AssemblyRef,
IL-байты, целевые metadata row IDs, строки, VIN, профили,
значения и исходные пути не публикуются.

Важное ограничение: соседняя инструкция newobj может
создавать объект, но без стека, CFG и проверки сигнатур
нельзя утверждать, что именно этот объект был записан.
call может возвращать объект, но это тоже пока не проверено.
Проверка MethodDef-флага .ctor лишь фиксирует, где
записан CIL, а не то, какой constructor был выполнен.
Совпадение поля и параметра по локальному TypeDefOrRef
не устанавливает фактический source-to-sink путь.

## Локальная Windows-проверка (без оригинальных DLL на этапе тестов)

Из checkout ветки feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_field_writes.py -v

Только после Ran 33 tests и OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_field_writes.py --folder 'E:\vida'

Было 25 synthetic тестов, добавлено 8 проверок точных opcode,
метаданных operand-kind, кросс-таблиц и отказа при неверных
метаданных. Новые 33 Windows synthetic-теста и original
three-DLL scan на момент коммита не выполнялись.
Статический source review не означает успешный unittest run.

Никакого заявления о доказанном origin профиля:
preceding_stfld_opcode_proves_value_source=false,
writer_predecessor_metadata_token_kind_proves_return_type=false,
writer_opcode_cross_tab_proves_runtime_write_order=false,
writer_and_caller_same_method_proves_write_reaches_call=false,
field_assignments_or_runtime_values_verified=false,
profile_identifiers_argument_proven=false,
original_vida_2015a_generic_profile_inheritance_verified=false,
d2_baudrate_verified=false, original_vida_readvin_accepted=false.

Следующий source-only gate зависит от реальных результатов:
если newobj, исследовать CLR тип конструируемого экземпляра
и его constructor signature, а не копировать исходные профили;
если call/callvirt, исследовать CLR return type shape / TypeRef
и возможность связи с FieldSig, без реконструкции runtime значения.
