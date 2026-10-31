# Проверка dev25 (2026-10-31)

## Локальные проверки

- `tests/run_tests.sh`: 8/8 групп под GCC.
- `tests/run_tests.sh`: 8/8 групп под Clang.
- `tests/run_tests.sh`: 8/8 групп под Clang AddressSanitizer/UndefinedBehaviorSanitizer.
- Обратная совместимость dev23: 12/12 групп (`test_cem_router.c`).
- Обратная совместимость dev24: 18 проверок (`test_ls.c`).
- Компиляция `src/*.c` в Windows x86 COFF `.obj` с помощью Clang target `i686-pc-windows-msvc`.
- Сборка статической библиотеки `.lib` из трёх объектов с `llvm-ar`.
- Линковка проверочного PE32 DLL без CRT с `lld-link /dll /noentry /machine:x86 /export:p2_vehicle_init`.

## Не проведено

- Запуск интегрированного Virtual Car в Windows VMware.
- Интеграция с рабочим `virtualcar.c` (исходник не предоставлен).
- Функциональные ответы настоящего Volvo CEM на A3/B9F0.
- Подтверждение широковещательного ID CEM на конкретном XC90 V8 MY2009.

**Запросы A3/F0 только классифицируются. B9FB остаётся в существующей DLL.**
