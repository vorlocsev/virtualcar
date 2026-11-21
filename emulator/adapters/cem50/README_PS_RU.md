# CEM50 PS — отдельная лабораторная регистрация J2534-2 для VIDA (Draft)

Этот эксперимент НЕ меняет установленный J2534 Diagnostic Interface CEM50 (J2534-1).

| Объект | Новый PS provider |
|---|---|
| Отображаемое имя | J2534 Diagnostic Interface CEM50 PS |
| Реестр | HKLM\SOFTWARE\PassThruSupport.04.04\J2534 Diagnostic Interface CEM50 PS, Registry32 |
| Каталог | %ProgramData%\J2534-CEM50-PS |
| DLL | J2534CEM50PS.dll |
| Конфигурация | virtualcar.ini из этого каталога |
| Заявляемые протоколы | CAN, ISO15765, CAN_PS, ISO15765_PS |
| Другие J2534-2 протоколы | Не объявлены |

CAN_PS=0x8004, ISO15765_PS=0x8005, J1962_PINS=0x8001. На HS 500000 используется 0x060E (пины 6/14), на MS 125000 — 0x030B (3/11). Режим только чтения; профиль синтетический, не OEM Volvo. Обнаружение provider не равно успешному ReadVin.

## Что подтверждено

Владелец выполнил на Windows полную проверку PR #418 по точному SHA:
- source SHA: 9ab3738d6c53442f83c57727f6eaaf44e383c618
- x86 DLL SHA256: 7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E
- Python 3.12: 1089 тестов, OK (skipped=1)
- C host: PASS, включая 13/13 B9FB PS на HS без утечки в MS
- C route evidence -> Python: 8/8 PASS
- Windows x86 PE32 cross-build: PASS
- изолированный native x86 probe: CEM50_PS_NATIVE_PASS, ISO15765_PS F190 с публичным VIN YV1CR855691511566
- общий результат: CEM50_PS_ALL_PASS

НЕ проверены: установленный PS provider, его отображение в оригинальной VIDA, выбранная DLL, PassThruOpen и Connect со стороны VIDA, ReadVin, принятый VIN, список CEM/ECM, T111 и T122. Предупреждение VIDA о J2534-1 не гарантирует, что одного объявления J2534-2 будет достаточно.

## Проверка установщика без установки

Install-J2534CEM50-PS.ps1 по умолчанию только проверяет. Он принимает лишь VirtualCarJ2534.dll из exact-head\emulator того же каталога, где находятся summary.json и native-ps\ps-native-check.json. Проверяются точные SHA DLL и исходного коммита, полные PASS-результаты Python/C/route/PE32/native, сохранение false для VIDA/ECU/physical, PE32 x86, профиль, VIN/шасси, отключённые непроверенные ответы и отсутствие выделенных PS ключа/каталога.

После локального клонирования отдельной ветки и изучения исходников, из каталога репозитория:

    $e = 'C:\path\to\CEM50-PS-PR418-<your-evidence-directory>'
    $installer = '.\emulator\adapters\cem50\Install-J2534CEM50-PS.ps1'
    $sha = '7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E'
    & $installer -SourceDll (Join-Path $e 'exact-head\emulator\VirtualCarJ2534.dll') -ExpectedSha256 $sha -SummaryJson (Join-Path $e 'summary.json') -NativeReportJson (Join-Path $e 'native-ps\ps-native-check.json')

Успех dry-run: PREFLIGHT_PASS, DRY_RUN_ONLY. Это не установка и не VIDA ReadVin PASS.

## Установка — только отдельное решение владельца

Для записи нового Registry32 ключа требуются явные -Apply -IConfirmOfflineSynthetic и повышенные права PowerShell. Только после проверки dry-run и отдельного разрешения владельца, в изолированной среде и при закрытых VIDA/J2534 клиентах можно повторить команду выше с этими переключателями. В этой Draft-ветке установка не выполнялась. Никакой CI не должен исполнять -Apply.

Проверка нового реестра без изменений:

    reg query "HKLM\SOFTWARE\PassThruSupport.04.04\J2534 Diagnostic Interface CEM50 PS" /reg:32

В оригинальной VIDA необходимо независимо подтвердить: выбранное полное имя, открытый путь именно к новому DLL, PassThruOpen/Connect, TX/RX и принятие VIN самим клиентом. PassThruClose без этого — не подтверждение.

## Откат только собственной регистрации

Remove-J2534CEM50-PS.ps1 тоже по умолчанию только проверяет. Перед удалением он требует собственный Registry32 ключ с точными Name/FunctionLibrary/SHA/протоколами, каталог ровно из J2534CEM50PS.dll и virtualcar.ini, правильный SHA и отсутствие reparse points. Если есть изменения или чужие файлы, прекращает работу.

    $sha = '7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E'
    .\emulator\adapters\cem50\Remove-J2534CEM50-PS.ps1 -ExpectedSha256 $sha

Для удаления после закрытия всех клиентов нужны отдельные -Apply -IConfirmClientClosed и повышенные права. Удаляются ТОЛЬКО выделенные PS ключ и каталог, не старые J2534-CEM50, J2534 Diagnostic Interface или CANPS Step6. Удаление файлов и ключа не атомарно: если оно прервётся, вручную проверить только выделенные объекты, не делать слепую очистку.

## Ограничения приёмки

- emulator/tests/test_cem50_ps_side_by_side_provider.py — статический контракт безопасности, не Windows runtime.
- Публикация бинарников, изменение development/main, запуск CI на постоянном VMware, установка на машину владельца НЕ выполняются этим PR.
- Этот PS provider — экспериментальная интеграция поверх проверенного кода PR #418. Оба PR остаются Draft до независимого ревью и реальных тестов VIDA.

Источники: https://opusivs.com/support/oem-customer-support/program-sae-j2534/discovery-of-the-dll/ ; https://github.com/diamondman/J2534-PassThru-Logger/blob/master/PassThruLogger/J2534_v0404.h ; https://manualzz.com/doc/23472941/volvo-all-in-one-vida-help


## Следующий критерий: реальное окно связи VIDA и PS provider

После установки и проверки Registry32 оригинальная VIDA 2014D/2015A на VMware20,1 отобразила
провайдер J2534 Diagnostic Interface CEM50 PS в выпадающем списке и связала его
с сохранённым профилем XC90 V8 2009. Открылось окно Diagnostics > Network,
однако ECU identification оставалось пустым. Схема сети/надпись Disconnect
**не доказывают** что PassThruOpen/Connect или ReadVin успешно выполнялись.
Это отдельные ступени: выбор адаптера, загрузка DLL, канал, TX/RX, полученный
VIN, обработка сценария ReadVin, идентификация ECU.

Для следующей одного контролируемого read-only GUI-испытания повторно собирать
эмулятор и переустанавливать DLL не нужно. Используйте существующие **не
исполняющие J2534** инструменты B3A46 и B3A45 из этого репозитория:

1. Найти только ожидаемый файл SectorVVirtualCar.log в ограниченных TEMP
   каталогах через tools/audit_vida_b3a46_log_source.py. Приватный
   candidate-paths.private.json оставлять **за пределами** Git checkout.
   Скрипт выводит только порядковые номера и категории кандидатов, но
   не доказывает процессную принадлежность VIDA.
2. Открыть приватный manifest **локально** и выбрать индекс (с 1)
   кандидата со статусом native_marker_in_tail. Если нет ни одного —
   записать NO_BOUNDED_MATCH; это не доказывает, что VIDA DLL не загружала.
3. До теста VIDA создать новый baseline через
   tools/audit_vida_j2534_session_window.py baseline с параметрами
   --vida-log "C:\Vida\System\Log\Diagnostics\VIDA.log",
   --candidate-manifest <private_manifest>, --candidate-index <index>,
   --private-baseline <new_private_baseline>. Пути проверять локально.
   Оба журнала допускаются отсутствующими и могут появиться позже.
4. В оригинальной VIDA с выбранным **новым** PS provider нажать только
   TEST COMMUNICATION TOOL, сохранить скриншот результата. Если это
   безопасная операция чтения, после успеха можно отдельно обновить
   Diagnostics > Network. Не использовать вкладку SOFTWARE, кодирование,
   SecurityAccess, программирование или физический автомобиль.
5. Запустить B3A45 delta с **тем же** manifest/index и baseline,
   указав новый --output <private_delta>. Оригинальные логи и baseline
   не загружать в GitHub; в обсуждение можно переносить лишь выведенные
   счётчики и категории, без путей/метаданных владельца.
6. Ключевое различие: PassThruOpen, успешный CAN_PS/ISO15765_PS
   PassThruConnect, TX и delivered RX в **том же окне** свидетельствуют
   о работе транспортной части, но не доказывают выполнение именно
   сценария VIDA ReadVin, принятый VIN или список живых ECU.
   B3A45 не удостоверяет PID или загрузку именно выделенной DLL.

Важное ограничение старого B3A45: его аудитор набора SET_CONFIG
создавался до этой PS сборки. Текущая DLL редактирует неизвестные
J1962_PINS metadata при выводе; **отсутствие значения HS 0x060E
в отчёте не является отрицательным результатом pin selection**.
Если необходимо доказать именно выбор пинов клиентом, понадобится
отдельный одобренный instrumentation build и повторная проверка его
SHA, но не переписывание установленной DLL.

Не считать VIN из списка Latest identified vehicles автоматическим
результатом J2534 ReadVin: профиль/история могли быть заполнены вручную.
Раздельные ReadVin (ScriptType=4) и EcuIdentification High/Low
(ScriptType=19/20) подтверждены только предыдущим статическим
исследованием оригинальной VIDA 2015A. Если ECU identification пуст,
этап идентификации не пройден.

## Анализировать запросы в том же окне (B3A55)

Используйте **тот же точный путь к журналу**, который передали в B3A45
при создании baseline. Если baseline был создан командой с
`--virtual-log (Join-Path $env:TEMP 'SectorVVirtualCar.log')`,
то B3A55 нужно запускать с тем же путём через `--virtual-log`.

B3A46-манифест можно использовать только если выбранная запись имеет статус
`native_marker_in_tail` и именно этот манифест/индекс использовались для
создания baseline. При `NO_BOUNDED_MATCH` кандидат со статусом
`present_no_marker_in_tail` **не проходит** строгий resolver B3A46 и не
должен подставляться как подтверждённый кандидат. В этом случае используйте
явный путь, совпадающий с B3A45 baseline.

Для ранее созданного baseline из инструкции выше:

    $repo = 'C:\Users\vorloc\Downloads\CEM50-PS-PR419'
    $priv = Join-Path $env:LOCALAPPDATA 'VirtualCar\OwnerPrivate\CEM50PS-VIDA-Window'
    $log = Join-Path $env:TEMP 'SectorVVirtualCar.log'
    $base = Join-Path $priv 'baseline.private.json'
    $out = Join-Path $priv ('transaction-delta-' + [guid]::NewGuid().ToString('N') + '.private.json')
    if (-not (Test-Path -LiteralPath $log -PathType Leaf)) { throw 'Original B3A45 virtual log path is unavailable' }
    if (-not (Test-Path -LiteralPath $base -PathType Leaf)) { throw 'B3A45 private baseline is unavailable' }
    py -3.12 (Join-Path $repo 'emulator\tools\audit_vida_j2534_window_transactions.py') --virtual-log $log --private-baseline $base --host-class iexplore --output $out

B3A55 использует точную границу B3A45 (размер, SHA256 исторического префикса,
идентичность пути, завершённые строки) и существующий J2534 transaction auditor.
Он выводит только количество запросов, их безопасные категории, protocol,
baud, статусы и причины. iexplore — только категория имени процесса, не
аутентификация компонента VIDA и не подтверждение полного пути DLL. Отчёт
остаётся приватным и не содержит PID, путей, CAN payload или VIN.

TX (app request) в нативном DLL-логе появляется внутри PassThruWriteMsgs
после проверки канала и сообщения. Поэтому такие записи означают, что
соответствующие вызовы записи дошли до DLL; отсутствие Open/Connect в
добавочном окне может означать, что канал был открыт раньше. PassThruReadMsgs
-> delivered отдельно подтверждает выдачу кадра клиенту, но не принятие VIN
или идентификацию ECU самой VIDA.


### Интерпретация B3A55 для CEM50 PS

В последнем окне владельца получено 98 принятых DLL TX, 89 распознанных
транзакций, 0 доставленных RX: D2 B9F0 x19 и B9FB x1 на CAN 125 kbit/s
завершились `explicit_missing_fixture`; P3 22A45F x32 и 22DD02 x32,
22F106 x1 и 22F114 x1 были закрыты маркером CLEAR_RX_BUFFER; три P3
наблюдения завершились J2534 read timeout. Сам по себе CLEAR_RX_BUFFER
не доказывает, что очередь содержала ответ: для этого надо сопоставить
его с `RX (simulated)` (RX enqueued) до очистки.

Статическая конфигурация репозитория `emulator/adapters/cem50/virtualcar.ini`
содержит только ECU0 7E0/7E8, ECUCount=1; P3 CEM ECU 726/72E отсутствует.
D2_40 B9FB и D2_40 B9F0 имеют ноль кадров; 13-кадровый B9FB находится
только в D2_50 (500 kbit/s). Это объясняет отсутствие фикстур в этой
конфигурации, но до чтения установленного INI и загрузочного маркера
`Active INI:` нельзя утверждать, что именно этот файл был загружен
текущим процессом VIDA.

Обновлённый B3A55 выводит счётчики `RX (simulated)`, CLEAR_RX,
D2 staged/missing/rejected, P3 CEM no-fixture/synthetic-reply/unmatched
и сохраняет CAN ID в группировке транзакций. Это различает ответ,
поставленный в очередь, доставленный клиенту и удалённый до чтения.
Ни один из этих статусов не является ReadVin или ECU acceptance.


## B3A56 — точная загруженная DLL в процессе VIDA (read-only)

Новый `emulator/tools/audit_vida_cem50_loaded_module.py` делает однократный
**снимок живых процессов** Windows через Toolhelp (processes/modules). Он
сравнивает **полный путь** реально отображаемого модуля
`J2534CEM50PS.dll` именно в процессе `iexplore.exe`, а не только имя
библиотеки. Затем **отдельно** вычисляет SHA256 текущего установленного
файла (проверка файла на диске **не удостоверяет байты уже загруженного
в память модуля**). Если каталог содержит `virtualcar.ini`, отмечается
только **наличие файла**, но не прочтение его содержания приложением.

Запускать из **корня актуального checkout PR #419** в активной VMware,
когда открыта оригинальная VIDA и выбран PS-провайдер.
PowerShell 5.1, **ровно одна строка**:

```powershell
py -3.12 (Join-Path (Get-Location).Path 'emulator\tools\audit_vida_cem50_loaded_module.py') --host-exe iexplore.exe
```

Используйте checkout **точной ветки PR #419**, содержащий новый скрипт,
а не историческую копию. Команда работает без запуска J2534 и не требует
администратора для доступных процессов. Если чужой процесс защищён,
Toolhelp может отказать в чтении модулей; скрипт сообщает
`INCONCLUSIVE_MODULE_ACCESS`, а не «DLL не загружалась».
При отсутствии процесса статус `NO_HOST_PROCESS_IN_SNAPSHOT`
относится только к моменту выполнения.

**Интерпретация:**

- `EXACT_DLL_IN_HOST_SHA_MATCH`: полный путь PS DLL присутствовал
  в модульном списке выбранного `iexplore.exe` на момент снимка,
  а текущий файл на диске совпадает с закреплённым SHA256 PR #418.
  **Это ещё не доказывает** `PassThruOpen`, запуск VIDA ReadVin или RX ECU.
- `ONLY_SAME_NAME_OTHER_PATH`: найдена одноимённая библиотека
  из другого каталога; установленная PS DLL не атрибутирована.
- `EXPECTED_DLL_NOT_SEEN_AT_SNAPSHOT`: в успешно прочитанных
  процессах она не обнаружена в момент снимка, но это не исторический
  отрицательный результат.
- `EXACT_DLL_IN_HOST_DISK_SHA_MISMATCH`: загруженный путь найден,
  но текущий файл на диске **не совпал** с проверенной PS DLL;
  остановить выводы о доверенной сборке.
- `INCONCLUSIVE_MODULE_ACCESS`: чтение модулей недоступно
  хотя бы для одного подходящего процесса. Не повышать статус.

Сводка по умолчанию печатается без PID, путей DLL, VIN, имён иных
модулей и исходных логов. Дополнительно можно передать
`--private-output <путь_вне_репозитория>`, чтобы сохранить
**только сводные значения** в новый (не перезаписываемый) JSON.

**Граница доказательств:** даже при `EXACT_DLL_IN_HOST_SHA_MATCH`
загруженный `virtualcar.ini` остаётся `NOT_VERIFIED`.
Код `load_config()` строит путь по собственному DLL module path и
печатает `Active INI:` только при инициализации, которая могла быть
до B3A45 baseline. Для завершения gate нужен *новый* ограниченный
read-only сеанс с моментом инициализации, точной записью `Active INI:`
из того же процесса и согласованной B3A45/B3A55 TX/RX-дельтой.
Наличие модуля не даёт права придумывать позитивные B9F0/A3/A6
ответы или переписывать текущие фикстуры.


## Результат владельца B3A56 (2026-11-21)

**Подтверждённый OWNER_LOCAL вывод:** 11/11 синтетических тестов PASS.
В работающем `iexplore.exe` при разовом снимке:
`EXPECTED_DLL_NOT_SEEN_AT_SNAPSHOT`; один процесс, список модулей
успешно перечислен; `exact_module_path_instances=0`,
`same_basename_other_path_instances=0`. Файл DLL на диске совпал с
проверенным PS SHA256, рядом существует `virtualcar.ini`. Предупреждение
Python `Could not find platform independent libraries <prefix>` не
привело к ошибке тестов.

**Вывод:** поиск был отрицательным только **в выбранном процессе и
только в момент снимка**. Не считать это доказательством, что VIDA
никогда не загружала DLL, что PS недоступен или что сборка неверна.
Равным образом совпадение SHA DLL и наличие INI не означает, что
именно эти файлы использовались в предшествующей VIDA-сессии.

Чтобы проверить другие допустимые категории хостов, из **корня
актуального checkout PR #419** выполните в Windows PowerShell 5.1
**одну строку** (без загрузки DLL, J2534 или изменения реестра):

```powershell
foreach ($hostExe in @('iexplore.exe','java.exe','vidamonitor.exe')) { Write-Host "=== $hostExe ==="; py -3.12 emulator/tools/audit_vida_cem50_loaded_module.py --host-exe $hostExe; if ($LASTEXITCODE -ne 0) { throw "B3A56 $hostExe failed" } }; tasklist.exe /m J2534CEM50PS.dll
```

`tasklist` подтверждает лишь наличие **имени DLL**, не полного пути.
Снимки B3A56 лучше выполнять во время контролируемой
**TEST COMMUNICATION TOOL** операции в оригинальной VIDA; после её
завершения DLL может быть выгружена. Отсутствие всех трёх категорий
также не исключает другой, пока неизвестный host EXE.

Далее собирайте **одно свежее B3A45/B3A55 окно** и отдельно
наблюдаемый результат клиента. `Active INI:` из начальной загрузки
DLL может отсутствовать в постфактум append-window. До прямого RX
delivered и положительного GUI ReadVin не добавлять фиктивный
B9F0/A3/A6 и не объявлять VIN/ECU acceptance.


## B3A63 — связать точную PS DLL и родной Active INI по текстовому PID (только чтение)

При последнем B3A55 были D2 B9 F0/B9 FB к \`0x40\` при 125000 бод и 0 доставленных RX. B3A56 отдельно находил точный PS DLL-модуль в одном из двух \`iexplore.exe\` на момент снимка. Эти два отчёта **не являются доказательством одного процесса**.

Новый \`emulator/tools/audit_vida_cem50_ps_same_pid_ini.py\` использует тот **самый** существующий локальный B3A45 baseline, тот же нативный журнал, метки \`P2 D2 request target/opcode/baud/flags (BE)\`, последние \`Active INI:\` и 14 нативных записей \`P2 fixture ... frame-count (BE)\` перед baseline. В процессе обработки сопоставляет текстовый PID с точным путём PS DLL в живом Toolhelp snapshot, но не печатает PID, путь INI, VIN или кадры. Проверка SHA относится **к DLL на диске**, а не к её образу в памяти.

Запускать в изолированной VMware при открытой оригинальной VIDA и существующих переменных PowerShell 5.1 \`$base\` (путь **именно к B3A45 baseline**) и \`$vlog\` (путь к **тому же** \`SectorVVirtualCar.log\`). Одна строка:

\`\`\`powershell
if (!(Test-Path -LiteralPath $base -PathType Leaf) -or !(Test-Path -LiteralPath $vlog -PathType Leaf)) { throw 'Нужно указать существующие $base и $vlog из B3A45/B3A55' }; py -3.12 emulator/tools/audit_vida_cem50_ps_same_pid_ini.py --virtual-log $vlog --private-baseline $base --host-exe iexplore.exe
\`\`\`

**Граница доказательства:** статус \`CORRELATED_SAME_TEXT_PID_EPOCH_NOT_ATTESTED\` означает совпадение текстового PID у D2 B9 FB, предыдущей инициализации и живого модуля в одном снимке. Не доказывает, что PID не использовался повторно, что INI имеет те же байты, какие прочитала DLL, что VIDA вызвала именно этот модуль в том же интервале или что VIN принят. Если нет раннего \`Active INI:\` в ограниченных 32 МиБ перед baseline, корректный результат — \`NO_PREBASELINE_ACTIVE_INI_FOR_REQUEST_PID\`, а не ошибка транспорта. При \`native_loaded_b9fb_cem40=zero_frames_loaded\` и \`CEM_50=frames_loaded_unverified\` подтверждается лишь содержимое **исторической записи загрузки** в этом нативном журнале.

Без запуска J2534, записи в Registry32, замены DLL/INI, установки VIDA, отправки запросов, исходных логов в GitHub или CI.
