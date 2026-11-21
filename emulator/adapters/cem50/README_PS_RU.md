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
