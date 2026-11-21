# CEM: реализация и граница приёмки

Дата: 2026-11-15. База development: `2731edb474f745184b84feea40428b265b493113`.
PR #344–348 проверены: все открытые draft, ни один не объединён.
Этот эксперимент не завершает приёмку автомобиля в оригинальной VIDA.

## Изменения

1. Загрузчик D2 отклоняет SF, в котором declared length не включает адрес,
   положительное эхо/селектор (минимум 3), либо адрес/7F/service/NRC (минимум 4).
   Неиспользуемый padding не интерпретируется. Python preflight согласован с C.
2. Отдельный opt-in `[D2_40_AE1B]`, `Enabled=1`, `FrameCount`, `Frame0...`,
   `ResponseId=00800003`. По умолчанию ответа нет. Только CAN/125000,
   `CB 40 AE 1B` с нулевым padding; положительное эхо EE/1B, отрицательное 7F/AE.
   Передача использует существующую очередь канала и её фильтры. Новый запрос
   отменяет старую передачу только в своём канале. CEM_50 не добавлен.
   Аналогично добавлены default-silent `[D2_40_B9F5]` и `[D2_40_B9F8]`
   с `Enabled=1`, `FrameCount/FrameN`, только CAN/125000 и точными CB40B9F5/F8
   с нулевым padding. Отдельные backend labels сохраняют видимость запросов.
3. Генератор B3A146 переработан: прежние донорские поля не переносятся.
   VIN поступает из private JSON; chassis-сегмент согласован с его суффиксом.
   Остальные поля — явно синтетические заполнители; реальные номера CEM,
   FYON, TypePNR3, завод и structure week неизвестны. B9F0 opt-in содержит
   15 нулевых байт, не номер запчасти. Это исследовательский контракт,
   а не согласованный OEM-профиль XC90. AE1B включается только флагом `--enable-synthetic-ae1b`: оригинальный
   ResponseHandler с неизменённым T111 определением принял mode 1B и пустой
   DtcList. Это не измерение DTC автомобиля и не доказательство присутствия ECU.
   Контракт v6 заменяет v2–v5, старый профиль следует заново сгенерировать в новой папке.
   Поле номера документа теперь содержит пять нулевых BCD-байт: прежний
   маркер `LAB!` включал недопустимый BCD nibble C. Factory содержит числовой
   ноль из двух байт вместо ASCII `00` (0x3030). Маркеры синтетического
   происхождения сохранены в текстовых полях и provenance.
   `--enable-synthetic-ident-followups` добавляет явно синтетические пустые
   списки F5/F8; требует отдельного включения synthetic B9F0. Реальные номера
   и серийные номера не придумываются. Нулевой B9F0 остаётся только тестовым:
   оригинальный D2Interpreter выдаёт строки с NUL-суффиксами, не валидные OEM номера.
   Новый независимый `--enable-synthetic-cem50-b9f0` заполняет существующий
   native слот D2_50_B9F0: target 50, ResponseId 01000003, три кадра и 15 нулевых
   байт. По умолчанию он выключен; включение не зависит от CEM40 B9F0.
   Это отдельный синтетический ответ идентификации для HS/500000, а не перенос
   CEM40 B9FB или каталожного номера. CEM50 B9FB/FC/F5/F8 остаются без ответа.
4. Новый сценарий Begin/Snapshot/Finish повторного тестирования использует
   существующий collector, проверяет Registry32, точный путь DLL, PE32,
   неизменность DLL/INI/identity, снимок модулей включая WOW64, целостность
   исходного префикса журналов. Ничего не регистрирует и не активирует.

## Запросы и источники

Полная необходимая для успеха последовательность пока НЕ установлена.
Ниже — найденные запросы, не перечень гарантированных обязательных команд.

| Запрос | Подтверждение / текущее ограничение |
|---|---|
| CEM_40 B9F0 | Исторические TX на 125000; CarCom: 120 бит, Complete Part Number 8 байт и Diagnostic Software number 7 байт, BCD+ASCII. Реальные значения неизвестны. |
| CEM_40 B9F5 / B9F8 | Оригинальный P2 20V8 ECU Identification запускает эти чтения после положительного B9F0. F5 — software part numbers, F8 — hardware serial numbers, не VIN. Opt-in synthetic empty lists реализованы. Факт запуска этого сценария в текущем GUI не подтверждён. |
| CEM_50 B9F0 | Каталоговый default CEM для XC90/2009/B8444S имеет первым маршрут 50/HS. В v6 отдельный opt-in synthetic F0 проверен на CAN/500000, положительное эхо принято оригинальным header interpreter. Реальный вызов из GUI и OEM поля не подтверждены. |
| CEM_40 B9FB | Исторические TX на 125000; наблюдавшийся envelope 88 байт, не доказанная схема целевого CEM. Положительное эхо F9/FB. |
| CEM_50 B9FB | История содержит 250000 и 500000; не переносить успешность одного маршрута на другой. |
| CEM_40 AE1B | 12 исторических TX с именем iexplore; CarCom T111: чтение 2-byte DTC с counters 1,3–7. Ответ Mode8 и список DTC16/C1-16/C3-16/C4-16 (C5–7 имеют нулевую длину в найденном определении). |
| CEM_40 A3/02 | CarCom: Security Access Mode Request; автоматический положительный ответ не добавлен. |
| CEM_40 A6/1A, A6/D0 | Исторические TX; ответ не реализован. В CarCom запрос A6 имеет Identifier16 + Mode8: пары 1A/D0 недостаточно для восстановления всех параметров. |
| B9FC | Имеющийся условный replay сохранён. В просмотренной истории iexplore CEM_40 B9FC не найден; обязательность не установлена. |

В известном B9FB body (без target/F9/FB) offsets: VIN 11/17, FYON 30/9,
TypePNR3 41/3, chassis 46/6, factory 54/2, structure WEEK 58/6,
package 66/20. FYON не является полем двигателя; structure week не является
годом модели. В каталоге CarCom найден также Vehicle Information Section
длиной 784 бита (98 байт), включая ELVP-complete No в позиции 88/10.
Поля имеют типы BCD (document 1/5), unsigned (factory 54/2), ASCII
(VIN, FYON, TypePNR3, chassis, week, package). Найденные варианты каталога
нельзя автоматически приписать целевому CEM: обязательная длина ответа
для выбранного ECU ещё не установлена. Контракт v6 сохраняет наблюдавшийся
88-байтовый envelope и не добавляет неподтверждённое расширение.
Источник: локальные неизменённые экспорты оригинального CarCom.
Оригинальные XML/SQL, IL и журналы остаются приватными и в PR не включены.

Оригинальный VehCom2 D2ResponseInterpreter проверяет service+0x40, а для B9
дополнительно block offset. `verify_original_vida_d2_headers.ps1` проверяет
эти методы на синтетических входах без открытия диагностического канала.
Этот тест не проверяет весь payload parser или ReadVin. Дополнительно
`verify_original_vida_empty_dtc.ps1` выполнил 6 проверок оригинального
ResponseHandler: Mode=1B, пустой DtcList, отсутствие доступа к базе, другой mode,
пустой буфер и переход к metadata lookup при непустом списке. Все PASS.
Использован неизменённый AE/1B fragment из T111, служебная обёртка id=0
и запрещающий доступ к БД интерфейс. Парсер сам по себе не отклоняет
отсутствующий mode; строгая проверка длины эмулятора остаётся необходимой.
`verify_original_vida_field_formats.ps1` проверил оригинальный Formatter.Format
на шести синтетических BCD/ASCII примерах. Это проверка отдельных типов,
а не полного B9 ResponseHandler с каталогом выбранного ECU.

Дополнительно `prepare_original_vida_b9fb_probe.py` и
`verify_original_vida_b9fb_parser.ps1` проверяют полный оригинальный
ResponseHandler на B9FB с явно выбранным фрагментом каталога CEM D2.
Связь BLOFF/FB подтверждается сравнением `0xFB` в T150_BlockValue;
описание T142 со ссылкой на T146_BlockMetaIDENT оказалось устаревшим:
такой таблицы нет и в работающей локальной SQL-базе. Проверены только
SELECT и определение процедуры; исходная база не изменялась.

Стенд использует неизменённый T111 XML и строки T141/T142/T144/T150/T155
из приватного immutable SQLite. Кэш BlockHandler заполнен в памяти,
локализованные подписи заменены пустыми строками; исходные сравнения,
типы, offsets и scaling сохранены с правилами оригинального addBlocks.
Конструктор подключения к базе не вызывается, fallback отключён,
другие операции интерфейса блокируются. Это ограниченный B9FB-каталог,
не доказательство того, что оригинальный ReadVin выберет этот вариант ECU.

Оригинальная DLL SHA256:
`1735d8ac20d63a20afe13742ea5156cce5a5328392bd3e44d9ec3cd8ae0dbd07`.
Для трёх каталоговых схем выполнено по 6 проверок: VIN равен private JSON,
изменённый VIN не совпадает, обрезанный ответ не возвращает исходный VIN,
неверный selector и пустой ответ не возвращают VIN, нет незапланированных
операций интерфейса. Все PASS; значения VIN не выводились.

| Каталоговая схема | Body профиля | Параметров в каталоге | Выдано парсером | Сопоставлено с блоками |
|---|---:|---:|---:|---:|
| 704 бита | 88 байт | 10 | 10 | 9 |
| 784 бита | 88 байт | 11 | 10 | 9 |
| 688 бит, вариант из ReadVin XML | 88 байт | 10 | 10 | 9 |

Во всех трёх схемах VIN извлечён. Синтетический factory=0 не совпадает с
перечислением допустимых кодов завода. В 784-битной схеме дополнительно
отсутствует ELVP-complete No: парсер пропускает выходящее за буфер поле.
Следовательно, успешное извлечение VIN не означает полноту или OEM-согласованность
ответа. Фактический вариант каталога целевого автомобиля остаётся неизвестным;
его нельзя выбрать по совпадению длины или подставить в B9F0.

### Связь с оригинальным ReadVin XML

Из приватного DiagSwdlRepository извлечён без изменения один XML-кандидат
типа ReadVin (SQL type 7, language 1; это не numeric enum приложения).
Ветка `NO_RELAY40B9FB` явно задаёт EcuVariant, ServiceId, FB и адрес 64.
Генератор snapshot теперь разрешает этот EcuVariant через T100, подтверждает
ServiceId через T111 и проверяет связь результата с полем VIN каталога.
ECU-номер из скрипта используется только как шаблон парсера, не как ответ B9F0.

Установленная статическая цепочка: положительный CEM_40 B9FB → ResultVIN →
`Parameters / 59790 / value` → AddVIN. Начальная ветка EuCD (F114) при
OnNoResponse/OnNegativeResponse/OnNoContact переходит к CEM_40 без реле;
та же неудача CEM_40 переводит выполнение к CEM_50. B9F0 CEM_40 в этой
VIN-ветке отсутствует. CanHiSpeedValue=250000 в узле CEM_40 относится к
настройке HS тестера и не является доказательством скорости LS.

По варианту из XML (секция 688 бит) оригинальный ResponseHandler извлёк VIN
из 88-байтового body v5: 10 параметров, 9 сопоставлений. Оригинальные методы
ResultGet выполнили путь с числовым ключом, затем оригинальные AddVIN и
GetIdentity вернули тот же VIN; IsX40=false. Шесть отрицательных/положительных
parser gates прошли и с этим путём. Не запускались планировщик скриптов,
диагностический канал VIDA или GUI. AddVIN сам по себе только сохраняет строку
и не проверяет модель/подлинность VIN.

В отдельном оригинальном сценарии «ECU identification, P2 20V8» для D2:
B9F0 positive → B9F5, B9F8 и AddIdentificationD2; B9F0 no response,
negative или no contact → SetEcuNotAlive. Это конкретное найденное условие
неответившего ECU. Не доказано, что AE1B либо успешные F5/F8 обязательны для
выхода из этого состояния. Оригинальный D2Interpreter принимает пустые F5/F8,
но также возвращает пустые списки для некоторых обрезанных ответов; native
проверки significant length остаются обязательными.

`verify_original_vida_ecu_state.ps1` выполнил 6 проверок оригинального
EcuIdentificationOutput с синтетической function group 0: начальное состояние,
SetEcuNotAlive, нулевой F0, пустые F5/F8, обрезанный F0, противоречивые вызовы.
Все PASS. Нулевой F0 даёт запись Alive с NUL в идентификационных строках;
даже один байт F0 создаёт запись Alive до ошибки разбора аппаратного номера.
SetEcuNotAlive не удаляет Alive, и обратный вызов не очищает NotAlive:
оба списка могут содержать один ключ. Это поведение отдельного компонента,
не конечный статус ECU. Стенд не повышает статус GUI по членству в этих списках.

`verify_original_vida_ecu_converter.ps1` проверил следующий оригинальный метод,
ScriptOutputConverter.GetAliveEcus, в семи изолированных случаях. Каталог заменён
строго ограниченным in-memory интерфейсом, function group 0 и профиль null —
синтетические входы, не профиль автомобиля. Оригинальный конвертер:

- При найденном Diagnostic Part Number использует соответствующий вариант.
- При отсутствии номера вызывает GetDefaultEcuId(function group, vehicle profile)
  и создаёт запись по варианту по умолчанию. Исходный номер с NUL остаётся
  в DiagNumber, а каталоговый идентификатор отдельно попадает в EcuVariantIdentifier.
- При null вместо варианта либо пустом PossibleEcuAddress выбрасывает исключение;
  ошибка поиска также выходит из метода. Это не переход в NotAlive.
- Для свежего output и output только с SetEcuNotAlive возвращает пустой Alive
  без обращения к каталогу.

Все 7 проверок PASS на оригинальном AppServices.VehicleAccess.DLL SHA256
`3bcaac2ce2dbe0b986a1c8588bbe3d75fe579bb41bb1eada759ccdb7214545a0`.
Read-only запрос к локальному снимку T100_EcuVariant подтвердил 0 совпадений
для диагностической строки нулевого v5 B9F0. Это ещё не доказательство отказа:
фактический профиль, выбранный текущей VIDA, неизвестен.
Доступ к реальному репозиторию, выполнение сценария и NETWORK этот тест не имитирует.

Следующая проверка `audit_cem_default_variant.py` использует неизменяемый SQLite
снимок CarCom. Она воспроизводит установленные по локальным исходникам правила
GetCompatibleProfiles / vadis_GetDefaultEcuVariants: десять равенств атрибутов
с NULL как wildcard с обеих сторон, folderLevel > 1 и убывание folderLevel.
Для ChassisFrom/To исходник использует именно равенство, не проверку диапазона.
Оригинальный DefaultEcuVariantCache проверен дополнительно в шести случаях:
первое сопоставление сохраняется, обратный порядок меняет результат, группы
ECU и профили изолированы, неизвестный ключ возвращает 0. Поэтому при разных
вариантах с равным верхним приоритетом аудитор фиксирует неоднозначность,
а не выбирает один по числовому ID.

В локальном снимке найдены 43 профиля с точными model=XC90, year=2009,
engine=B8444S. Все имеют один и тот же верхний CEM(D2) default на folderLevel=3;
пропусков и неоднозначностей нет. Результаты отдельно сверены с оригинальной
read-only процедурой SQL для всех 43 профилей: 43/43 совпадений.
Это существующий каталоговый fallback; подставлять его Diagnostic Part Number
в B9F0 как подлинный номер эмулируемого ECU нельзя.

Исходник vadis_GetEcuVariantData задаёт порядок по Config.Priority. У выбранного
default два маршрута: commAddress 50 / HS bus identifier 1 / priority 1 и
commAddress 40 / LS bus identifier 0 / priority 2. В обоих busRate NULL:
500000 для HS берётся из исторического канала владельца, а не из этих строк.
Таким образом CEM40-only профиль мог оставить первый HS-запрос без фикстуры;
это предположение о следующем запросе, не зафиксированный отказ GUI.
Отдельный opt-in v6 позволяет проверить его без переноса данных между адресами.

Оригинальные SQL определения прочитаны без изменения и остаются приватными.
SHA256 UTF-8 снимков GetCompatibleProfiles и vadis_GetDefaultEcuVariants:
`0dfc674875a15efbd7b16f856eaf41b51c9d4bfc79d8b16af64d97dc1dd5406f` и
`432b1d5842b93be23bbd8756b89696edebe5fb64c62d2e644eddeffd038b7aef`.

Внешние источники сверены: [volvo_vida_db](https://github.com/spnda/volvo_vida_db),
[cem-cracker](https://github.com/vtl/volvo-cem-cracker),
[VolvoDiagToolkit](https://github.com/MarvinParanoid/VolvoDiagToolkit),
[P2-informer](https://github.com/drpioneer/Volvo-P2-informer).
Исходники сторонних проектов в реализацию не копировались.
Два указанных сообщения MatthewsVolvoSite вернули HTTP 403; не использованы
как подтверждение неизвестных полей или последовательности приёмки.

## Выполненные проверки

- Python: полный набор — 932 теста, 3 skip, PASS; контракт профиля — 17/17,
  каталог и ReadVin bindings — 14/14 PASS.
- Аудитор default CEM: 8/8 synthetic SQLite тестов; read-only SQL parity 43/43.
- Нативный C host suite: PASS, включая 6 SF и 8 AE1B групп.
- B9F5/F8: по 7 native групп на selector PASS; original identification-list
  interpreter — 6/6 PASS. Свежая x86 DLL прошла route/filter регрессии.
- Оригинальный EcuIdentificationOutput: 6/6 synthetic state gates PASS;
  отдельно проверены обрезанные данные и независимость Alive/NotAlive.
- Оригинальный ScriptOutputConverter: 7/7 с синтетическим каталогом PASS;
  проверены fallback и его ошибки; DefaultEcuVariantCache — ещё 6/6 PASS.
- Оригинальный VehCom2: 10 проверок заголовков PASS, включая CEM50 F0;
  прикладная приёмка не проверена.
- Новая x86 DLL: PE32, ровно 14 J2534 exports.
- Изолированные вызовы настоящей DLL: 9 групп маршрутизации PASS;
  22 проверки filter/ABI PASS. Реальный адаптер не открывался.
- Генератор/аудит: private профиль v6 создан вне checkout без активации;
  новая DLL загрузила оба адреса с независимыми каналами и фильтрами.
- Оригинальный empty-DTC parser: 6/6 PASS; форматтер BCD/ASCII: 6/6 PASS.
- Оригинальный B9FB ResponseHandler: по 6/6 PASS для двух сравнительных
  схем и схемы из ReadVin XML; VIN совпал, полнота остальных полей не подтверждена.
- PowerShell helper: 9 binding, 7 module snapshot, 8 PE32 и 8 byte-comparison PASS.
- Интервалы 12 мс в host suite использовали управляемые часы. Фактическое
  время доставки оригинальной VIDA в этом сеансе НЕ измерено.
- Exact-head CI не запускался; автоматический persistent runner не обходился.

## GUI приёмка и технический блокер

Хост определён как VMware. Локальная оригинальная VIDA запущена в Internet
Explorer. Инструмент Computer Use остановил доступ к этому браузеру, поскольку
для него не поддерживается URL policy enforcement. Экран NETWORK после
изменений не прочитан. Обход этого ограничения не предпринимался.

| Проверка | Статус |
|---|---|
| Новая DLL реально загружена VIDA | NOT_TESTED — не активирована |
| CEM Network Status | NOT_TESTED; последнее подтверждённое пользователем состояние Not responding |
| ReadVin | NOT_TESTED |
| T111 | NOT_TESTED; структура, synthetic transport и offline empty-list parser |
| T122 | NOT_TESTED |
| ECU Identification / XC90 V8 MY2009 | NOT_TESTED |

Первое подтверждённое прежнее условие отказа — отсутствие фикстур
CEM_40/B9F0 и B9FB. Следующий блокер: неизвестные валидные значения
идентификации и отсутствие GUI-приёмки. Шаблон каталога CEM_40 в найденном
ReadVin XML теперь установлен; выполнение именно этого XML текущим GUI ещё не доказано.
Нулевой B9F0 не совпадает с каталогом; для всех 43 точных XC90/2009/B8444S
профилей установлен одинаковый fallback. Выбор одного из этих профилей
самой VIDA, обработка полного результата и NETWORK остаются непроверенными.
Называть отсутствие совпадения B9F0 доказанной причиной Not responding нельзя.
Заголовок EE/1B сам по себе не доказывает, что VIDA сочтёт CEM присутствующим.

## Один сценарий повторной проверки

1. В отдельном lab-каталоге создать профиль генератором
   `build_b3a146_cem40_lab_profile.py --identity-json <private JSON> --output <lab>/b3a146-cem40-lab.ini --enable-synthetic-b9f0 --enable-synthetic-ae1b --enable-synthetic-ident-followups --enable-synthetic-cem50-b9f0`.
2. Сначала `--validate-only --profile <INI> --identity-json <JSON>`.
   Для контролируемой активации остановить диагностический клиент, сохранить
   текущую конфигурацию, выбрать отдельный lab adapter и новую копию DLL с
   соседним `virtualcar.ini`. Не менять Dvinholm или его регистрацию.
   Сценарий не выполняет этот отдельный операторский шаг автоматически.
3. Запустить `invoke_vida_cem_trial.ps1 -Phase Begin -SessionDirectory <new-private-dir>
   -ReferenceDll <lab-DLL> -IdentityJson <JSON> -AdapterKey <exact-Registry32-subkey>
   -VidaLog <original-log>`. По умолчанию native log берётся из TEMP.
4. В оригинальной VIDA выбрать лабораторный интерфейс, DIAGNOSTICS → NETWORK → UPDATE.
   Пока интерфейс открыт, тот же сценарий с `-Phase Snapshot -ClientProcessId <actual-client-PID>`.
5. Сохранить локальные скриншоты NETWORK, чтения VIN, T111, T122 и ECU identification.
   Затем тот же сценарий `-Phase Finish`. Заполнить созданный
   `gui-observations-private.json` отдельными статусами и ссылками на доказательства.
   RX не переводит эти статусы в PASS автоматически.
6. Восстановление: закрыть клиент, выбрать исходный интерфейс. При ручной замене
   файлов восстановить сохранённую копию после проверки, что DLL выгружена.
   В текущем сеансе штатные DLL/INI/реестр не менялись, откат им не требуется.

Приватные INI, manifest, скриншоты и полные журналы не публиковать в GitHub.

`verify_cem40_lab_runtime.ps1` прошёл с private profile v5 и новой x86 DLL
PR #350: B9F0=3, B9FB=13, AE1B=1, B9F5=1, B9F8=1 кадр; CAN/125000, RxStatus CAN_29BIT_ID,
odd-ID PASS filter, terminal length и пустая очередь проверены. DLL загружена
только отдельным тестовым процессом из новой папки, не оригинальной VIDA.
При продолжении каждый выданный байт D2, включая padding, дополнительно
сравнен с прошедшим preflight INI: все 19 кадров пяти ответов совпали.

Фактические замеры финального запуска (Stopwatch, время от начала WriteMsgs
до возврата ReadMsgs, с накладными расходами журнала):

| Ответ | Первый кадр, мс | Последний, мс | min/max между возвратами, мс |
|---|---:|---:|---:|
| B9F0 | 5.005 | 37.400 | 16.144 / 16.250 |
| B9FB | 4.166 | 156.366 | 1.214 / 25.377 |
| AE1B | 4.067 | 4.067 | неприменимо |
| B9F5 | 5.033 | 5.033 | неприменимо |
| B9F8 | 4.251 | 4.251 | неприменимо |

Это измерение выдачи J2534, не времени обработки в VIDA. Конфигурация 12 мс
не является доказательством интервала 12 мс между возвратами клиенту.
Дополнительный запуск v6 прошёл на свежесобранной x86 DLL: прежние 19 кадров
CEM40, три кадра CEM50 B9F0, затем повтор HS B9F0 при уже начатом LS B9F0 —
все 28 выданных кадров побайтно совпали с INI. CEM50 на 125000 и CEM40 на
500000 остались без ответа; незаданные CEM50 FB/F5/F8 тоже молчат.
Фактический первый/последний HS F0: 8.278/43.987 мс, интервалы 15.366–20.343 мс;
повтор HS: 4.004/29.428 мс. LS B9FB: 2.748/156.251 мс, интервалы 1.013–26.225 мс.
Начатый ответ LS не отменён запросом HS. Никакая DLL не регистрировалась для VIDA.
Повторить без регистрации: `verify_cem40_lab_runtime.ps1 -DllPath <built DLL>
-ProfilePath <private generated INI> -IdentityJson <private JSON>
-OutputDirectory <new directory outside checkout>`.
Оригинальный empty-list parser: `verify_original_vida_empty_dtc.ps1
-VehicleServicesAssembly <original BizServices.CarCom.VehicleServices.DLL>
-DefinitionXml <private unchanged AE1B definition fragment from T111>`
в 32-битной Windows PowerShell. Фрагмент извлекается read-only из локального
CarCom; в репозиторий не входит.
Проверка форматов: `verify_original_vida_field_formats.ps1
-VehicleServicesAssembly <original BizServices.CarCom.VehicleServices.DLL>`
в 32-битной Windows PowerShell, без диагностического подключения или доступа к БД.

Повтор полного B9FB parser: сначала `prepare_original_vida_b9fb_probe.py
--carcom <private CarCom.sqlite> --variant <explicit catalog row id>
--profile <private generated INI> --identity-json <private JSON>
--output <new lab directory>/b9fb-parser-input.json`, затем в x86 PowerShell
`verify_original_vida_b9fb_parser.ps1 -VehicleServicesAssembly <original DLL>
-PrivateInput <private b9fb-parser-input.json>`. Snapshot содержит приватный VIN
и исходные каталоговые данные, публиковать его нельзя. Неизвестные,
унаследованные и неоднозначные варианты отклоняются, длина ответа
автоматически не дополняется. Никакие исходные профили не активируются.

Для привязки к исходному ReadVin вместо `--variant` указать `--readvin-xml
<private unchanged XML> --readvin-node NO_RELAY40B9FB`. Parser-тесту дополнительно
передать `-ScriptingAssembly <original BizServices.Scripting.DLL>`. Дубли узлов,
динамические входы, неоднозначный каталог и несовпадение числового ключа VIN
отклоняются. Проверка списков: `verify_original_vida_ident_lists.ps1
-ScriptingAssembly <original DLL>` в x86 Windows PowerShell.
Проверка отдельного компонента состояния: `verify_original_vida_ecu_state.ps1
-ScriptingAssembly <original BizServices.Scripting.DLL>
-VehicleServicesAssembly <original BizServices.CarCom.VehicleServices.DLL>`.
Используются только публичные синтетические байты и function group 0;
конструктор создаёт внутренние коллекции, окна и диагностические соединения не открываются.

Проверка следующего преобразования: `verify_original_vida_ecu_converter.ps1
-DiagnosticsDirectory <original Diagnostics directory>` в x86 Windows PowerShell.
Она печатает SHA256 используемых сборок; логгер и каталог подменяются только
внутри тестового процесса, оригинальные файлы и настройки не изменяются.

Повтор каталожной проверки: `audit_cem_default_variant.py --carcom <private
CarCom.sqlite> --model XC90 --year 2009 --engine B8444S`. Вывод содержит только
счётчики и флаги границ доказательства, без VIN, профилей и номеров ECU.
Код 0 означает единый default для всех найденных точных профилей, 1 — отсутствие,
неоднозначность или различие default, 2 — неподдерживаемый/неполный вход.
