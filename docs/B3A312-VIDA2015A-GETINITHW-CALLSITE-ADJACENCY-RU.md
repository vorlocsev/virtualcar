# B3A312 — оригинальная VIDA 2015A: GetInitHwSettings, первый ограниченный обзор аргумента

19 ноября 2026. Только Draft PR #376. Никакого изменения original VIDA, SQL, J2534/CEM, main/development, CI.

## Подтверждённые owner-original результаты

На трёх неизменных SHA-pinned оригинальных DLL установлено:
- BizServices.CarCom.DB.DLL: по одному GetInitHwSettings MethodDef в
  ICarComRepository и CarComRepository; их raw методовые сигнатуры
  побайтово одинаковы внутри исходной DLL. Interface public/instance/
  virtual/abstract; class public/instance/virtual/newslot, nonabstract.
  Явных записей MethodImpl у класса нет: это совместимо с неявной
  реализацией интерфейса и НЕ является отсутствием реализации.
- VehicleCommProvider.DLL и Workflow.DLL: два исходных внешних
  ICarComRepository TypeRef → AssemblyRef; полное совпадение сохранённой
  AssemblyDef идентичности и имени интерфейса 2/2, формы сигнатур 2/2.
- В исходных CIL подтверждены шесть статических call/callvirt:
  1 в VehicleCommProvider, 5 в Workflow. 2034/2034 CIL bodies
  полностью декодированы исправленным декодером.
- Runtime dispatch, реальный аргумент со списком профилей,
  наследование общего InitHw, D2 скорость и ReadVin НЕ проверены.

## Новый пробник — только предыдущая CIL-инструкция

Файл: emulator/tools/audit_vida_2015a_inithw_callsite_adjacent.py

Работает только с теми же тремя проверенными SHA-256 оригинальными
DLL. Открывает их только для чтения, не загружает сборки, не
исполняет VIDA, SQL или J2534.

Для каждого подтверждённого выровненного call/callvirt к
ICarComRepository.GetInitHwSettings (MemberRef сигнатуры с одним
параметром и HasThis) определяет лишь категорию непосредственно
предшествующего CIL opcode:
- load_local_or_address, load_arg_or_address, load_field_or_address;
- nested_call_or_calli_unresolved_return, new_object_or_array;
- load_null, load_string, load_numeric, duplicate_stack_item;
- type_cast_or_transform, array_element_or_length,
  load_method_or_type_handle, prefix_not_value_producer, nop,
  other_or_unresolved или none.

В JSON попадут только счётчики MethodDef CIL тел, точек вызова,
инструкций call/callvirt и эти фиксированные категории.
Никакие оригинальные opcode-байты, MethodDef/MemberRef tokens,
имена неизвестных методов, исходные профили/идентификаторы,
пути установки, VIN или hardware settings не публикуются.

Критическая граница: соседняя CIL инструкция НЕ доказывает,
что она произвела реальный объект profileIdentifiers. Код может
переходить к call через другую ветку, обрабатываться через EH,
получать локальные переменные из нескольких мест или быть
частью многовызовного выражения. Для доказательства источника
потребуются отдельная CFG/data-flow, def-use локальных
переменных, типовая сигнатура и динамический контекст.
Даже положительный ldloc означает только опкод в тексте IL,
а не доказанный состав T161 профилей.

Флаги являются false: adjacent_opcode_proves_actual_argument_source,
profile_identifiers_argument_proven,
original_vida_2015a_generic_profile_inheritance_verified,
d2_baudrate_verified, original_vida_readvin_accepted.

## Запуск на Windows локально у владельца

Из корня checkout ветки feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_callsite_adjacent.py -v

Только после Ran 17 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_callsite_adjacent.py --folder 'E:\vida'

На момент добавления новые 17 тестов и анализ трёх реальных DLL
не запускались и не подтверждены. Только static source review.
Не запускать CI jobs и не менять оригинальные системы.
