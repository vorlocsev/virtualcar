# B3A312 — VIDA 2015A: шесть callvirt после загрузки поля, типы FieldSig

Дата: 2026-11-19. Only owner-private read-only Draft PR #376.

## Фактический исходный результат владельца

Владелец выполнил audit_vida_2015a_inithw_callsite_adjacent.py
на прежних трёх SHA256-закреплённых оригинальных DLL.
Получено:

- BizServices.CarCom.DB.DLL: 140 CIL bodies, 0 внешних вызовов;
- BizServices.VehicleCommProvider.DLL: 175 CIL bodies, 1 callvirt
  к ICarComRepository.GetInitHwSettings, непосредственно до него
  стоит инструкция из семейства load_field_or_address;
- Workflow.DLL: 1719 CIL bodies, 5 callvirt к тому же интерфейсному
  методу; у всех пяти предыдущая инструкция тоже из семейства
  load_field_or_address;
- итого 6/6 статических интерфейсных вызовов — callvirt,
  6/6 непосредственно после загрузки поля/адреса; call=0.

Ранее локальные CLR MethodDef в ICarComRepository и CarComRepository
имели одну точную бинарную сигнатуру; флаги public/instance/virtual,
интерфейс abstract, класс concrete/newslot. Явных MethodImpl 0,
что совместимо с неявной реализацией. Оба external AssemblyRef
полностью совпадают с исходным AssemblyDef 2/2 по сохранённым
идентификаторам, и 2034/2034 CIL bodies успешно декодированы.

Доказано только соседство инструкции, а НЕ реальный источник
единственного аргумента GetInitHwSettings, не происхождение его
значения и не runtime invocation/ReadVin.

## Новый аудит ровно следующего уровня

emulator/tools/audit_vida_2015a_inithw_field_shapes.py

По тем же трём фиксированным SHA-256 DLL:
- декодирует границы CIL так же, как прежний проверенный анализатор;
- для каждой целевой инструкции call/callvirt записывает только
  фиксированную категорию предыдущего field opcode:
  ldfld (0x7B), ldflda (0x7C), ldsfld (0x7E), ldsflda (0x7F);
- проверяет поле как metadata token FieldDef (table 4) либо
  MemberRef (table 10), читает исходную FieldSig (0x06) из #Blob;
- сравнивает **только token-neutral структуру** типа поля с
  типом одного параметра внешнего GetInitHwSettings MemberRef;
- для ldflda / ldsflda сравнивает произведённый managed pointer
  к полю (byref<T>), а не сам тип поля;
- выводит числовые счётчики совпадений, несовпадений,
  неподдерживаемых/сложных форм и фиксированную категорию
  примитив/class/valuetype/generic_instance/szarray/byref/и т. д.;
- при недопустимых токенах и повреждённой FieldSig завершает
  проверку ошибкой с одной только категорией исключения.

Все исходные имена полей, TypeDefOrRef coded indices, имена
приватных типов, сигнатуры/байты, реальные IL/метки,
профили T161, VIN, исходные пути установки и настройки
автомобиля остаются только в памяти или не считываются
вовсе. Оригинальные DLL только читаются, не загружаются
в CLR и не выполняются; SQL, J2534 и CEM не затрагиваются.

**Ограничение интерпретации:** даже если тип поля структурно
совпадает с типом параметра, это НЕ доказывает семантическую
CLR type identity, реальное связывание MemberRef, происхождение
значения поля, корректность CFG/exception handlers, или то,
что именно результат последней инструкции находится на стеке
при вызове. Если структура не совпадает, требуется исключить
случаи разной области GenericInst, type-token контекстов и
неподдерживаемых форм. Значение поля и все операции записи
в поле пока вообще не отслеживаются.

## Windows owner-only: сначала 20 synthetic тестов

Корень checkout ветки feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_field_shapes.py -v

Только если Ran 20 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_field_shapes.py --folder 'E:\vida'

В новом JSON обратить внимание на:
- immediately_preceding_field_opcodes;
- field_loads_with_fielddef_token / field_loads_with_memberref_token;
- field_type_shape_family_counts;
- field_shape_equal_to_target_parameter_ignoring_local_type_tokens;
- field_shape_different_from_target_parameter;
- field_or_parameter_shape_unclassified.

Тесты полностью синтетические, в том числе field address vs
field value, фальшивые токены внутри операндов, повреждённая
FieldSig и SHA mismatch. На момент коммита новые 20 тестов
и запуск исходного аудитора на оригинальных DLL **не выполнены**.

Следующий gate по фактическому JSON — ограниченное отслеживание
присваиваний исходному полю (stfld/stsfld) и порядка операций с
проверкой CFG/stack; если не разрешимо, фиксировать unresolved.
Нельзя считать общую XC90 MY2009 InitHw настройку применённой
при начальном ReadVin до доказательства фактического списка
profileIdentifiers. D2 bitrate и VIDA ReadVin acceptance false.
