# B3A312 — VIDA 2015A: конструкторы и возвращаемые типы перед stfld

Дата: 2026-11-19. Draft PR #376. Только чтение трёх закреплённых
SHA-256 оригинальных DLL владельца; не выполнять оригинальную VIDA,
SQL, J2534, не изменять DLL, ветки main/development или релизы.

## Что подтверждено фактическим исходным аудитом владельца

Исследован GetInitHwSettings в оригинальных VIDA 2015A:
- BizServices.VehicleCommProvider.DLL: один target callvirt читает
  ровно одно локальное поле (ldfld FieldDef). Поле содержит простой
  ELEMENT_TYPE_CLASS с тем же локальным TypeDefOrRef coded index,
  что единственный параметр метода (1/1). В этом FieldDef две
  инструкции stfld из двух других методов: в .ctor непосредственно
  перед stfld находится newobj с MemberRef, в другом методе —
  callvirt с MemberRef.
- Workflow.DLL: пять target callvirt читают один локальный FieldDef;
  точный локальный TypeDefOrRef encoded index совпадает с параметром
  GetInitHwSettings 5/5. Поле получает одну инструкцию stfld в .ctor,
  непосредственно перед которой находится newobj с MemberRef.
- Все 3 операции stfld вне 6 target caller methods, ни одной stsfld.
  В CarCom.DB нет этих внешних target callsites.
- Статическое считывание исходного IL: 2034/2034 body decoded,
  оригинальные сборки не исполнялись и не изменялись.

Соседний newobj или callvirt НЕ доказывает источник
значения в вершине IL стека, реальную запись, состав списка профилей
или выполнение этих путей в оригинальной VIDA.

## Следующий ограниченный аудитор

emulator/tools/audit_vida_2015a_inithw_writer_memberrefs.py

На тех же трёх SHA256 DLL, только по исходным CIL/CLR метаданным:
1. Выбирает только ldfld FieldDef непосредственно перед исходными
   ICarComRepository.GetInitHwSettings вызовами.
2. Находит статики stfld в такие локальные FieldDef того же модуля.
3. Для stfld с непосредственно предыдущим newobj MemberRef:
   читает имя .ctor, MethodSig HasThis и void return, а затем
   владельца MemberRef (TypeDef/TypeRef/TypeSpec);
   только в памяти сравнивает локальный TypeDefOrRef coded index
   владельца с простым class типом FieldSig.
4. Для stfld с непосредственно предыдущим callvirt MemberRef:
   читает MethodSig, HasThis, возвращаемый тип; если return —
   простой ELEMENT_TYPE_CLASS, сравнивает его исходный локальный
   TypeDefOrRef coded index с типом поля.
5. Любые неподдерживаемые сложные сигнатуры, отсутствующие поля,
   неподходящие TypeSpec/MemberRefParent и неоднозначные значения
   фиксирует как unclassified, не выдумывая совпадений.

Выводится только фиксированная числовая классификация:
- newobj_owner_exact_field_type / different / unclassified;
- callvirt_return_exact_field_type / different / unclassified;
- other_or_unclassified;
- writer_producer_relation_by_method_family — кросс-таблица
  этих семи категорий по .ctor/.cctor/другим методам;
- общее число исходных target callsites, различных FieldDef и stfld.

Никакие оригинальные типы, имена, сигнатуры, MethodRef и FieldDef
row ID, IL-байты, строки VIN, T161, пути установки или значения
не экспортируются; ошибки sanitised до класса исключения.

**Строгая граница:** даже точное равенство локальной CLR ссылки
сконструированного типа с FieldSig НЕ является доказательством
runtime field assignment, что объект не изменён, что именно
это значение передаётся в GetInitHwSettings, и тем более не
является доказательством выбранного generic XC90 MY2009 InitHw,
D2 bitrate и принятого ReadVin. Отличия токенов также могут
быть совместимы с наследованием/интерфейсами; не делать вывод
о невозможности приведения только из raw token inequality.

## Проверка владельцем Windows

Из корня checkout ветки feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

Только синтетический набор новых тестов:

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_writer_memberrefs.py -v

И только после Ran 18 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_writer_memberrefs.py --folder 'E:\vida'

На момент коммита этот набор тестов и новый оригинальный
аудит ещё НЕ выполнялись. Статическое чтение GitHub не
равно test PASS. CI/workflows не запускаются, PR остаётся Draft.
