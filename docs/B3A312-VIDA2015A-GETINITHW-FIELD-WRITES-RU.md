# B3A312 — оригинальная VIDA 2015A: FieldDef и stfld

Дата: 2026-11-19. Только исследовательская ветка Draft PR #376.
Оригинальные установленные VIDA/SQL/J2534/DLL/CEM не менять.

## Подтверждённые результаты владельца

Три исходных неизменных SHA256-прикреплённых DLL были прочитаны
в режиме только чтения. Во всех шести статических callvirt
ICarComRepository.GetInitHwSettings непосредственно перед вызовом
стоит ldfld — загрузка значения поля экземпляра, FieldDef.
VehicleCommProvider: 1 из 1, Workflow: 5 из 5.
Все FieldSig имели token-neutral форму class, структурно совпадавшую
с типом единственного аргумента GetInitHwSettings (6/6).
Это ещё не доказательство того, что именно данные поля передаются,
или что поля содержат нужный список профилей.

## Новый анализ

Файл: emulator/tools/audit_vida_2015a_inithw_field_writes.py

Тот же набор трёх SHA256, только чтение локальных DLL.
В памяти инструмент:
1. Сравнивает простой class ELEMENT_TYPE_CLASS и локальный
   TypeDefOrRef coded index из FieldSig с единственным параметром
   GetInitHwSettings MemberRef в той же сборке. Выводит только
   равенство/различие/недоступность. Сырые токены не выводятся.
2. Подсчитывает число различных FieldDef, замеченных перед вызовами.
   Пять вызовов Workflow могут относиться к одному или разным полям:
   до этого этапа результат неизвестен.
3. Ищет инструкции stfld и stsfld с точно этими FieldDef tokens
   в CIL методов той же сборки, считает разные методы-писатели
   и фиксированные категории instance constructor (.ctor),
   type initializer (.cctor) и other method.
4. Возвращает только числовые категории и машинные ограничения.

Результат не содержит оригинальные имена полей, типов, методов,
метаданные токены, CIL байты, значения строк, VIN, профильные
идентификаторы, исходные пути или настройки автомобиля.
Исходные DLL не загружаются в CLR и не исполняются.

Точное совпадение TypeDefOrRef token в одном модуле — более сильный
признак, чем token-neutral совпадение формы. Но это НЕ доказывает
действительное значение аргумента или runtime dispatch.
Наличие stfld не доказывает, что его значение попадёт в callvirt.
Отсутствие stfld не доказывает, что другие сборки, рефлексия,
внешний код или другие механизмы не задавали поле.
CFG, стек, exception handlers и def-use остаются неразобранными.

Поля JSON:
- exact_same_module_typedeforref_token_equal_sites;
- exact_same_module_typedeforref_token_different_sites;
- exact_type_token_unclassified_sites;
- distinct_target_fielddefs_in_module;
- target_fielddef_stfld_write_sites;
- distinct_methods_writing_target_fielddefs;
- distinct_target_fielddefs_without_local_stfld;
- writer_method_family_counts.

## Windows owner-only

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_field_writes.py -v

Только после Ran 19 tests и OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_field_writes.py --folder 'E:\vida'

19 тестов синтетические. На момент добавления ни Windows
unittest, ни оригинальный новый аудит не выполнялись.
Статическая проверка исходника — не подтверждение 19/19 PASS.

Установлены false: exact_local_type_token_match_proves_argument_value_source,
observed_field_writes_exhaustive_across_all_assemblies,
control_flow_stack_or_exception_handlers_traced,
field_assignments_or_runtime_values_verified,
profile_identifiers_argument_proven,
original_vida_2015a_generic_profile_inheritance_verified,
d2_baudrate_verified, original_vida_readvin_accepted.

PR остаётся Draft; нет merge, workflow dispatch, изменений
main/development, исходной VIDA/SQL/J2534 или релиза.
