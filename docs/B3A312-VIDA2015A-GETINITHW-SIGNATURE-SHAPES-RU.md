# B3A312 — VIDA 2015A: метод GetInitHwSettings, сравнение форм сигнатур

19 ноября 2026. Draft PR #376, оригинальная VIDA используется только как источник чтения.

## Подтверждённый результат владельца

Три SHA-pinned оригинальные DLL: 2034/2034 CIL метода декодированы, 6 статических интерфейсных вызовов GetInitHwSettings, одна CarComRepository→ICarComRepository InterfaceImpl по простому имени. Namespace двух ICarComRepository MemberRef совпадает с namespace InterfaceImpl — 2/2. Однако сырые #Blob байты методов не совпадают с одним исходным CarComRepository.GetInitHwSettings MethodDef — 2/2 отличаются; HasThis и число параметров=1 совпадают. Это не доказывает ни эквивалентность, ни несовместимость типов: TypeDefOrRef coded indices привязаны к каждой сборке.

## Новый инструмент

emulator/tools/audit_vida_2015a_inithw_signature_shapes.py

Только чтение трёх установленных DLL по прежним именам и SHA256. Работает полностью в памяти, распознаёт ограниченные ECMA-335 формы сигнатур (атомарные типы, class/valuetype, byref, pointer, szarray, genericinst, VAR/MVAR и custommods). Игнорирует локальные TypeDefOrRef индексы и возвращает только агрегаты: сравнение всей формы сигнатуры, формы возвращаемого типа, параметров и calling convention. Неизвестная/сложная форма становится unclassified, без догадок. Исходные типы, сигнатуры, профили, IL, пути и VIN не выводятся.

Совпавшая token-neutral форма **не** доказывает CLR type identity, assembly binding или runtime dispatch. Разница также не доказывает невозможность вызова, если семантика типов ещё не разрешена. Полный AssemblyRef identity, MethodImpl и список profile identifiers остаются отдельными gate.

## Windows — владелец

В checkout ветки feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_signature_shapes.py -v

Только после Ran 17 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_signature_shapes.py --folder 'E:\vida'

Новое доказательство владельца/Windows-тесты на момент коммита НЕ выполнялись. Статическая проверка исходников не означает PASS. Исходная VIDA, SQL/J2534, main/development и релизы не меняются. Никаких выводов об унаследованных InitHw, D2 скорости или принятом ReadVin.
