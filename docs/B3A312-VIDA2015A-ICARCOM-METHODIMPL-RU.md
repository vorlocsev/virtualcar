# B3A312 — оригинальный VIDA 2015A: GetInitHwSettings и MethodImpl

19 ноября 2026, Draft PR #376. Исходная VIDA, SQL/J2534, ECU/CEM и
основные ветки не изменяются; анализ только read-only.

## Установленный факт до нового аудита

Владелец проверил три исходные SHA256-pinned сборки:
- BizServices.CarCom.DB.DLL (содержит локальные TypeDef CarComRepository
  и ICarComRepository, один InterfaceImpl, GetInitHwSettings MethodDef);
- BizServices.VehicleCommProvider.DLL и Workflow.DLL (два TypeRef →
  AssemblyRef на ICarComRepository; шесть статических call/callvirt).

AssemblyDef локального интерфейса CarCom.DB и оба внешних AssemblyRef
совпадают по сохранённым именам, версиям, culture, нормализованному
PublicKeyToken и прочим флагам **2/2**. Внешние ссылки не подписаны,
ключи/токены отсутствуют в обеих. Полное имя интерфейса совпадает 2/2.
Метод-сигнатура GetInitHwSettings совпадает структурно 2/2 по
calling convention, return и параметру, но сырые #Blob байты различны.

Это сильная **статическая CLR цепочка**. Фактическая загруженная сборка,
runtime MethodImpl/dispatch и исходный список аргументов не доказаны.

## Новый шаг

emulator/tools/audit_vida_2015a_inithw_methodimpl.py

Нужно подтвердить, что локальный ICarComRepository *объявляет*
GetInitHwSettings, а локальный CarComRepository содержит собственный
GetInitHwSettings. Скрипт читает три закреплённые по SHA256 DLL только
как бинарные источники, без загрузки/исполнения, без SQL и J2534.

Из CarCom.DB читает CLR TypeDef MethodList, MethodDef (0x06),
MethodImpl (0x19), проверяет ровно по одному target-методу в локальном
интерфейсе и классе. Возвращает только фиксированные числа:
- наличие двух TypeDef и двух target MethodDef;
- совпадение/различие сырых MethodDef #Blob сигнатур **в одном модуле**
  (локальные TypeDefOrRef индексы здесь уже в общей области);
- флаги public/instance/virtual/abstract/newslot;
- число MethodImpl записей владельца CarComRepository;
- число MethodImpl с точным локальным Body MethodDef кандидатом,
  точным локальным Declaration MethodDef интерфейса,
  и их точное совместное совпадение в одной записи.

Если явный MethodImpl отсутствует, это **НЕ доказывает**, что интерфейс
не реализован: возможна неявная реализация по имени/сигнатуре.
Если есть MethodImpl, это статическая декларация, но **НЕ доказывает**
реальный runtime вызов исходной VIDA. Непроверенные MemberRef/TypeSpec
declarations не считаются точным сопоставлением.

Скрипт не экспортирует оригинальные токены, имена неизвестных типов,
сигнатуры, IL-байты, пути, профильные ключи, VIN или hardware settings.
Обозначенные как false флаги исключают преждевременное заключение
об исполнении, наследовании InitHw, скорости CEM D2 и принятом ReadVin.

## Windows (owner-only)

Из checkout feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_methodimpl.py -v

Только после Ran 13 tests ... OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_methodimpl.py --folder 'E:\vida'

Тестовый файл содержит 13 полностью синтетических проверок, включая
отсутствие явного MethodImpl, положительный exact MethodDef pair,
отсутствующие методы, неправильный SHA и отсутствие утечки.
На момент коммита исходные Windows-тесты и реальный owner-run JSON
**ещё не выполнялись**. Статическая проверка не равна test PASS.

Следующий научно-практический блокер — откуда original VIDA 2015A
получает аргумент profileIdentifiers, включая случай начального
ReadVin с EMPTYPROFILE. До доказательства этого пути переносить
параметры общего InitHw-кандидата в Virtual Car как обязательные
параметры D2 нельзя.
