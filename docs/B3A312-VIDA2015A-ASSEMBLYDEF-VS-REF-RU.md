# B3A312 — VIDA 2015A: локальный AssemblyDef и внешние ICarComRepository AssemblyRef

19 ноября 2026. Только Draft PR #376. Без записи в original VIDA,
SQL, J2534, CEM, main/development, без workflow dispatch.

## Подтверждённые владельцем результаты предыдущего аудита

Оригинальные SHA-pinned три DLL: BizServices.CarCom.DB.DLL,
BizServices.VehicleCommProvider.DLL, Workflow.DLL.

- 2034/2034 оригинальных IL method bodies полностью разобраны.
- 6 статических call/callvirt в VehicleCommProvider (1) и Workflow (5)
  к MemberRef GetInitHwSettings с родительским TypeRef по
  простому имени ICarComRepository, ResolutionScope AssemblyRef.
- Одна исходная CarComRepository→ICarComRepository InterfaceImpl.
- Два внешних MemberRef имеют тот же полный namespace/type name, что
  InterfaceImpl репозитория, и ту же token-neutral форму сигнатуры,
  хотя сырые CLR #Blob bytes различаются.
- Последний аудит AssemblyRef сообщил:
  repository_interface_scope_local_typedef=1;
  caller_interface_scope_assemblyref=2;
  stored_full_typename_equal=2;
  stored_assemblyref_identity_not_comparable=2;
  stored_assemblyref_identity_equal=0, different=0.

Последние нули означают не несовпадение: интерфейс в
CarCom.DB задан **локальным TypeDef**, поэтому сравнивать
две внешние AssemblyRef со внутренней *AssemblyRef* неверно.
Следует сравнить их с **AssemblyDef (таблица 0x20)**,
содержащего этот локальный TypeDef исходного модуля.

## Новый аудит

emulator/tools/audit_vida_2015a_inithw_assemblydef.py

Требует те же три оригинальных SHA-256 и только read-only local
PE/CLI SQLite-independent parsing. Из прежнего корректного
парсера TypeDef/TypeRef/InterfaceImpl/MemberRef/AssemblyRef
берёт единственный локальный TypeDef ICarComRepository,
затем читает единственную запись оригинального AssemblyDef
из CarCom.DB.DLL. Две внешние TypeRef AssemblyRef читаются
в VehicleCommProvider/Workflow.

Для трёх assembly identities сравнивает только **в памяти**:
- assembly simple name;
- four-part version;
- culture;
- normalized strong-name PublicKeyToken;
- non-public-key assembly flags как отдельную категорию;
- полное CLR namespace + type name интерфейса.

AssemblyDef хранит полный открытый ключ. Его token вычисляется
для сравнения с AssemblyRef: последние 8 байт SHA-1 от полного
открытого ключа в обратном порядке. AssemblyRef может хранить
либо уже 8-байтовый token, либо полный открытый ключ при флаге
PublicKey (0x0001). При отсутствии ключа сравнение unsigned
выполняется отдельно, а некорректная длина key/token отвергается.

Никакое реальное имя сборки, версия, культура, ключ, токен, путь
или полное имя оригинального типа не выводятся в JSON — только
числа равенств/различий. Например:
- stored_canonical_name_version_culture_token_equal / different;
- normalized_publickeytoken_equal / different;
- assembly_simple_name_equal / different;
- assembly_version_equal / different;
- caller_assemblyref_keys_are_token / full / unsigned.

Даже полное сохранённое совпадение AssemblyDef↔AssemblyRef
**не является** доказательством загруженной CLR assembly identity,
успешного InterfaceImpl / MethodImpl binding, runtime исполнения
метода, аргумента profileIdentifiers, применения общего InitHw,
скорости D2 или принятого оригинальной VIDA VIN.

Стандарты для источников обработки:
- ECMA-335 II.22.2 Assembly и II.22.5 AssemblyRef;
- Microsoft Learn System.Reflection.AssemblyName.GetPublicKeyToken.

## Windows — запуск владельцем

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

Затем только синтетические тесты (13):

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_assemblydef.py -v

Только после Ran 13 tests и OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_assemblydef.py --folder 'E:\vida'

**Новый Windows unittest transcript и запуск на трёх оригинальных
DLL ещё не получены**. Все изменения внесены только в Draft PR #376.
Не выполнять оригинальные SQL routines, не редактировать VIDA,
не программировать ECU и не переносить GGD bitrate в D2.

Следующий отдельный этап: canonical TypeDefOrRef signature types,
MethodImpl или implicit interface dispatch, и доказательство того,
что original VIDA 2015A caller передаёт нужный список T161 профилей
(включая общий с InitHw) именно в исходном ReadVin.
