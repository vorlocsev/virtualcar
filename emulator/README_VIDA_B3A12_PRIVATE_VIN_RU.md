# B3A12: проверка локального VIN в лабораторной конфигурации Virtual Car

**Назначение:** удостовериться, что VIN, предоставленный владельцем, действительно присутствует в отдельном `virtualcar.ini` B3A7 и связан с точной экспериментальной x86 DLL J2534. Это проверка конфигурации, **не** доказательство автоматического `READ VEHICLE` в VIDA и не эмуляция ответа CEM.

По экрану VIDA 2014D ранее подтверждено **ручное** профилирование: XC90 (-16), MY2009, B8444S, TF-80SC AWD. Этот результат остаётся отдельным от общения с ECU.

## Конфиденциальность

Полный VIN и номер шасси находятся **только в локальном частном** файле `vehicle-identity.json` и на машине владельца. Эти данные **не входят** в код, тесты, документацию и коммиты GitHub. Отчёт B3A12 намеренно не содержит VIN, шасси, их хешей и адресов файлов; оригинальные журналы VIDA не меняются и не обезличиваются.

## Исходная B3A7 привязка

- Код B3A7, от которого собрана протестированная DLL: `0722b530aa48a7f1790d5f0dd1dddbe790518705`.
- SHA256 нативной DLL: `AFB19B26C3BA6BE11D3ADD321EC7A90BEF4E005F36EC7B963AC0C8F25E4EF210`.
- Путь лаборатории: `Downloads\VirtualCar-VIDA-KLine-B3A7-Isolated-PR319`.
- Приватный исходник: `Downloads\VirtualCar-VIN-MY2009-Apply\vehicle-identity.json`.

Аудитор читает `virtualcar.ini`, исходный манифест и DLL, проверяет заголовок PE x86, сверяет VIN/год/шасси/двигатель/трансмиссию с частной записью, проверяет флаги ISO9141/B3A6/B3A7/CAN_PS/строгой фильтрации, отсутствие любых включённых `B9FB` кадров, выключенную пассивную шину и соответствие J2534 Registry32 **при запуске под Windows**. Запросов к ECU/VIDA он не делает.

## Применение

1. **Закрой VIDA и Internet Explorer**, если ещё не сделал этого.
2. Если ранее запускался `Set-VirtualCar-MY2009-VIN.ps1 -Mode Apply`, переходи к проверке ниже. Если не запускался, сначала выполни `-Mode Inspect` и `-Mode Apply` **из уже созданного отдельного частного ZIP** `VirtualCar-VIN-MY2009-Apply.zip`. Проверочный инструмент B3A12 сам не меняет INI.
3. Запусти из Windows PowerShell 5.1 (Python 3.10+):

```powershell
$lab="$env:USERPROFILE\Downloads\VirtualCar-VIDA-KLine-B3A7-Isolated-PR319"
$identity="$env:USERPROFILE\Downloads\VirtualCar-VIN-MY2009-Apply\vehicle-identity.json"
$auditor="$env:USERPROFILE\Downloads\B3A12\emulator\tools\audit_vida_b3a12_private_profile.py"
py -3 "$auditor" --lab "$lab" --private-identity "$identity" --out "$env:USERPROFILE\Downloads\B3A12-result.json"
```

При успешном результате ожидается:

```
B3A12 PASS: private XC90 V8 MY2009 LAB identity, B3A7 DLL and strict no-RX settings
J2534 Registry32: REGISTERED_EXACT
Original VIDA automatic ReadVIN: NOT PROVEN
```

**Если `vin mismatch`**: сначала проверь, был ли выполнен локальный Apply. Сам B3A12 не исправляет несоответствие. **Если `NOT_REGISTERED`**: точная DLL/INI согласована, но экспериментальный адаптер не зарегистрирован; результат нельзя считать испытанием VIDA. **Если `REGISTRY_MISMATCH`**: проверка завершается ошибкой, не следует перенаправлять VIDA на неизвестную DLL.

Для повторного запуска используй новое имя выходного JSON либо не передавай `--out`. Существующие файлы аудитор не перезаписывает.

## Тесты и ограничения

```powershell
py -3 -m unittest discover -s "$env:USERPROFILE\Downloads\B3A12\emulator\tests" -p "test_audit_vida_b3a12_private_profile.py" -v
```

В локальном окружении разработки: **8/8 синтетических тестов PASS**, `compileall` PASS. Полный runtime B3A12 на Windows пока **не проводился**. Реальное применение `-Mode Apply` на машине владельца **не подтверждено выводом PowerShell**. Последний оригинальный VIDA B3A7 `ReadVIN` имел 27/27 тайм-аутов. Ни один файл B3A12 не создаёт/не подставляет VIN в J2534 ECU RX и не делает `FIVE_BAUD_INIT` успешным.

**Следующий отдельный этап:** после локального PASS и явного выбора B3A7 LAB в VIDA необходимо провести изолированную проверку, что VIDA действительно загрузила изменённый `virtualcar.ini`, без утверждения автоматического чтения VIN. Не публиковать частный VIN, локальные INI или необезличенные исходные OEM-журналы в публичный PR.
