# Virtual Car VMware LAB 2026-11-01

**Отдельный prerelease для изолированной VMware, не Stable и не выпуск для физического автомобиля.** Собран из ветки vmware-release после слияния изменений development до PR #20.

- Windows x86 J2534 DLL и Win32 Control.exe.
- Синтетический P2 read-only профиль со строгой HS/LS маршрутизацией и опциональными обезличенными backend JSONL событиями (для тестового ZIP включены).
- CEM A3/A6 распознаются и завершаются как unimplemented_probe/no_response, без выдуманных E3/E6; B9F0/B9FB/B9FC остаются условным replay по валидированным фикстурам.
- Матрица coverage для D2/P3 и строгий анализ жизненного цикла RX, без ложной атрибуции неизвестных запросов.
- В ZIP: PowerShell install/uninstall, Python audit, русская инструкция, SHA256SUMS.txt, BUILDINFO.json.
- Все offline CI-проверки выполняются до публикации. VMware acceptance, идентификация XC90 V8 MY2009 и физический J2534 пока **не подтверждены**.

**Внимание:** распаковать полностью, зарегистрировать J2534 DLL из новой папки и запускать только read-only CEM discovery.
