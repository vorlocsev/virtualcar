# B3A52: историческая загрузка D2 B9FB в исходном журнале виртуальной DLL

## Предпосылки

В оригинальной VIDA (приватная гостевая Windows) `READ VEHICLE` завершился
`No response from the vehicle`. B3A50 однозначно отнёс шесть D2 запросов
`B9FB` к следующим исходам: 0x40/125k x2 без фикстуры,
0x50/250k x3 несовпадение маршрута, 0x50/500k x1 без фикстуры.
B3A51 установил, что `[Vehicle] VIN` **не генерирует** D2 `B9FB`:
ответы должны загружаться из отдельных `[D2_40]`/`[D2_50]` кадров.

## Новое в B3A52

В исходнике лабораторной DLL PR #319 `load_config` после `Active INI:`
пишет 14 записей
`P2 fixture target/opcode/response-id/frame-count (BE)`, включая
базовые `0x40/B9FB` и `0x50/B9FB`. B3A52 классифицирует
**историческое событие загрузки**, а не изменённый сегодня INI.

В GitHub: `emulator/tools/audit_vida_b3a52_loaded_fixtures.py`,
чистая функция `classify_initialization(historical_lines, frozen_window_lines)`.
Она допускает классификацию только при **одном** исходном текстовом PID
для D2 `B9FB`, проверяет последнее `Active INI:` с тем же PID
до окна B3A47, полный набор 14 метаданных в фиксированном порядке и
число кадров не более 64. Выводит только классы
`zero_frames_loaded`, `frames_loaded_unverified` или
`not_observed` отдельно для 0x40/0x50. Не возвращает INI path,
VIN, CAN, PID, SHA, ResponseId и произвольные байты.

Отдельный переносимый owner-only скрипт
`Invoke-VirtualCar-B3A52-LoadedFixtures.py` читает только
**прежнюю** приватную сессию B3A47:
- находит родной `SectorVVirtualCar.log` по сохранённому
  B3A46 manifest и строгому `source_id`;
- сравнивает полный исторический SHA256-префикс с B3A47 baseline;
- читает не более **8 МиБ перед baseline** и точно сохранённый
  append-интервал (не позже конца оригинального B3A47);
- не открывает исходный `virtualcar.ini` и ничего не перезаписывает.

Локальная синтетическая проверка переносимого инструмента 8/8 PASS.
Для запуска из Windows `Downloads`, при сохранении прежних
`%LOCALAPPDATA%\VirtualCar\OwnerPrivate\B3A46` и `B3A47`:

```powershell
$f=Get-ChildItem "$env:LOCALAPPDATA\VirtualCar\OwnerPrivate\B3A47\run-*\delta-categorical.json" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
py -3 "$env:USERPROFILE\Downloads\Invoke-VirtualCar-B3A52-LoadedFixtures.py" --session-dir $f.Directory.FullName
```

**Ограничения:** PID может повторно использоваться ОС, текстовая метка
`iexplore.exe` не доказывает оригинальный VIDA-клиент, отсутствие
`Active INI` в ограниченном хвосте не доказывает отсутствия загрузки DLL.
Положительный `frame_count` **не доказывает** подлинность данных ECU и
не означает успешный VIN. Отсутствие исторической метки должно давать
`not_observed`, а не выдуманную конфигурацию.
Скрипт не запускает VIDA, не создаёт ответы CEM, не модифицирует
`virtualcar.ini`, прошивки ECU, исходный J2534 или приватные логи.

По результатам: если `zero_frames_loaded`, очевидно, что статический
VIN не может пройти D2 без фикстуры. Если `frames_loaded_unverified`,
следующий шаг требует источника, CAN-таймингов и отдельной доказанной RX.
Если `not_observed`, требуется другая приватная аттестация INI;
нельзя поднимать gate VIN.

#326/#4 остаются OPEN до оригинальной VIDA VIN acceptance.
