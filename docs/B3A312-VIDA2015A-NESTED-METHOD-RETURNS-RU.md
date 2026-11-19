# B3A312 — original VIDA 2015A: локальный MethodDef перед newobj

Дата: 19 ноября 2026. Только Draft PR #376, owner-only, read-only.
Не запускать оригинальные VIDA DLL, SQL/J2534/CEM, CI или workflows,
не изменять main/development или публиковать релизы.

## Зафиксированные исходные результаты владельца

По оригинальным SHA-256-pinned установленным DLL VIDA 2015A:
- BizServices.CarCom.DB.DLL: 140 CIL methods, 0 целевых внешних calls.
- BizServices.VehicleCommProvider.DLL: 175 methods, 1 GetInitHwSettings
  target call, 2 static stfld в один локальный FieldDef.
  В пути конструктора непосредственно перед newobj находится callvirt
  к локальному MethodDef; его CLASS return-тип точно совпадает
  с CLASS единственного параметра newobj. Метод локального
  MethodDef объявлен как **instance_zero_explicit** (HasThis=true,
  ноль явных параметров), инструкция перед ним относится к
  категории load_arg_or_address. В другом методе stfld
  предшествует нуль-параметрный callvirt MemberRef, перед которым
  стоит ldarg.1: slot1 — первый явный аргумент INSTANCE MethodDef,
  тип которого имеет такую же локальную CLR TypeRef, как
  объявленный owner вызываемого MemberRef (1/1).
- Workflow.DLL: 1719 methods, 5 target calls читают один локальный
  FieldDef. В конструкторе единственный stfld расположен
  сразу после newobj(один параметр STRING); перед newobj стоит
  ldstr, совпадение STRING-сигнатуры 1/1; содержимое строки
  НЕ анализировалось и не экспортировалось.
- Предыдущий original EH-анализ: единственный
  GetInitHwSettings call в VehicleCommProvider находится в try
  с одним catch+finally, ldfld в той же EH-области; все
  пять Workflow calls вне EH.

Реальное выполнение вызовов, IL stack source, receiver aliasing,
состояние полей, profileIdentifiers, generic XC90 MY2009 InitHw
fallback, фактический D2 baud и ReadVin acceptance
по-прежнему НЕ подтверждены.

## Новый узкий оригинальный IL audit

Файл:
emulator/tools/audit_vida_2015a_inithw_nested_method_returns.py

Использует только ТОТ ЖЕ набор из трёх SHA-256-pinned original
DLL, в режиме чтения байтов без загрузки или выполнения CLR.

Ищет только локальный METHODDEF callvirt перед newobj и stfld,
которые записывают поле, позднее читаемое при GetInitHwSettings.

В original caller MethodDef:
- классифицирует точный слот load arg / load address перед
  локальным callvirt: slot0, slot1, slot2plus, address_...;
- сравнивает его с сигнатурой caller MethodDef (HasThis +
  число явных параметров): instance_this, instance_first_explicit,
  static_first_explicit и другие фиксированные категории;
- это ТОЛЬКО интерпретация объявленного слота, не runtime receiver
  и не подтверждение перехода значения по стеку.

В локальном target MethodDef, один раз для каждого различного
MethodDef:
- сверяет объявленную сигнатуру instance_zero_explicit,
  CLASS-return с данным статическим следом;
- считывает его локальный CIL, если RVA доступен, и считает
  ВСЕ инструкции ret и семейство непосредственно предыдущего
  opcode: load_field_or_address, load_local_or_address,
  nested_call_or_calli_unresolved_return, load_arg_or_address,
  other_or_unresolved и прочие фиксированные категории;
- считает direct branch/switch/leave target НА САМ ret;
- отмечает MoreSects, но не разбирает EH обработчики заново.
  Отсутствие MoreSects не доказывает истинность пути.

Ни original code bytes, IL offsets, metadata токены, имена
типов/методов/полей, исходные строки, значения
возвращаемых объектов, список профилей и исходные пути
не попадают в JSON и ошибки.

Категории результата:
nested_call_input_slot_counts;
nested_call_caller_arg_role_counts;
nested_method_signature_counts;
distinct_nested_local_methoddefs;
nested_method_with_il_body / nested_method_without_il_body;
nested_method_return_sites;
nested_method_return_preceding_opcode_families;
nested_method_return_direct_branch_entry;
nested_method_moresects / nested_method_no_moresects.

Если непосредственно перед ret стоит ldfld, это кандидат на
поле-источник, а НЕ доказательство значения в стеке.
Реальный путь требует консервативного CFG+EH, анализа стека,
def-use и возможного межметодного aliasing. Статическая
совместимость типов сама по себе ничего не доказывает
о VIDA ReadVin и CEM InitHw.

## Запуск владельцем

Из корня checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_nested_method_returns.py -v

Только после Ran 16 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_nested_method_returns.py --folder 'E:\vida'

Это **16 синтетических тестов**. На дату добавления они НЕ были
выполнены на Windows владельца, а новый original read-only
scan по трём DLL НЕ выполнялся. Проверка кода и файла PR —
не равно PASS набора и не равно исходному фактическому результату.

Изменения только в Draft PR #376, без CI, workflow dispatch,
merge, оригинальной VIDA, SQL/J2534/CEM, development/main и релизов.
