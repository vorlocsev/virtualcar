# B3A312 — VIDA 2015A: ICarComRepository AssemblyRef provenance

Дата: 2026-11-19. Draft PR #376. Только исходные копии DLL,
локально у владельца. Не запускать исходную VIDA, DLL, SQL,
J2534 или CEM, не изменять файлы.

## Установленные статические факты

Проверены три оригинальные SHA256-pinned DLL:
- BizServices.CarCom.DB.DLL
- BizServices.VehicleCommProvider.DLL
- Workflow.DLL

В них были установлены:
- 2034/2034 корректно декодированных оригинальных CIL MethodDef body;
- шесть статических call/callvirt к ICarComRepository.GetInitHwSettings
  по имени интерфейсного TypeRef: один VehicleCommProvider,
  пять Workflow;
- одна CarComRepository InterfaceImpl→ICarComRepository по имени
  CLR TypeRef/TypeDef; один собственный GetInitHwSettings MethodDef;
- namespace: равенство 2/2 исходных интерфейсных ссылок с
  InterfaceImpl-кандидатом;
- HasThis=true и один явный параметр у всех трёх ролей;
- raw CLR #Blob сигнатуры внешних MemberRef vs репозитория
  различались 2/2; после отброса локальных TypeDefOrRef индексов
  STRUCTURAL signature shapes совпали 2/2, включая параметры,
  return и calling convention.

**Сходство формы не доказывает одинаковую семантическую сигнатуру
и реальное CLR interface dispatch.** Различие сырых #Blob
нельзя объявлять несовместимостью без разрешения модульных типов.

## Новый ограниченный инструмент

emulator/tools/audit_vida_2015a_inithw_assembly_identity.py

Использует только три уже закреплённые владельцем оригинальные
DLL и их старые точные SHA256; при ином хеше выдаёт
санитизированную ошибку без анализа чужого файла.

В памяти читает PE/CLI #~/#Strings/#Blob, TypeDef, TypeRef,
InterfaceImpl, MemberRef и AssemblyRef. Выбирает строго одну
CarComRepository→ICarComRepository запись InterfaceImpl и
строго по одной внешней ICarComRepository.GetInitHwSettings
MemberRef в двух остальных DLL.

Для каждого сравнивает:
- сохранённое CLR TypeNamespace + TypeName интерфейса;
- категорию ResolutionScope (AssemblyRef vs local TypeDef
  или другой/неразрешённый scope);
- **оригинальную AssemblyRef identity**: имя, версия,
  культура, флаги и PublicKeyOrToken как байты.

Имена, значения версий/культуры/ключи, namespace,
TypeRef indices и сигнатуры **не экспортируются**.
Отчёт содержит только числа: количество двух
совпавших/различных/несопоставимых identity,
совпадения полных имён интерфейса и виды scope.

Две AssemblyRef записи с идентичными сохранёнными полями
не доказывают, что именно эта сборка была загружена в
оригинальном процессе или что MethodImpl/implicit dispatch
свяжет данный MemberRef с конкретным MethodDef.
Если тип интерфейса в CarCom.DB локальный TypeDef,
сравнение AssemblyRef с внешними caller автоматически
помечается *not comparable*: такое сравнение требует
отдельного AssemblyDef + PublicKey token canonicalization.

Следующие отдельные gates: разрешение типовых идентичностей
аргумента/возврата по TypeDefOrRef + AssemblyRef, проверка
реальной реализации метода и происхождения исходного списка
T161 profile identifiers. Не выводить из этого реальные
InitHw, D2 bitrate или успешный VIDA ReadVin.

## Windows, команды владельца

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_assembly_identity.py -v

Только после Ran 12 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_assembly_identity.py --folder 'E:\vida'

Все 12 новых тестов используют только полностью синтетические
PE/CLR фикстуры, включая фальшивые AssemblyRef и SHA.
Реальные Windows-тесты и аудит оригинальных DLL новым
инструментом **ещё не выполнялись**. Static GitHub source
review не является успешным результатом запуска.

Original VIDA/SQL/J2534, ветки main/development, workflow
jobs и релизы не меняются; PR остаётся Draft.
