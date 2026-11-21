# Virtual Car — исследовательский эмулятор Volvo P2

**Статус (21.11.2026): экспериментальная разработка.** Цель — виртуальный **XC90 V8 MY2009** через Windows x86 J2534 для read-only тестов SectorV, VDASH и оригинальной VIDA. **Полная идентификация автомобиля ещё не подтверждена.** Проект отделён от Dvinholm.

## Где текущий код

- **`development`** — активная интеграционная ветка: `emulator/` содержит исходник эмулятора на основе предоставленной владельцем v0.3.6.6, лабораторный CEM, `emulator/tests/`, `emulator/tools/`, средства VMware.
- **`main`** — старый reviewed baseline; нельзя считать его равным `development`.
- **`proxy/`, `cmd/oneclick/`** — трассирующий J2534-прокси и GUI dev26, **не** сама DLL эмулятора.
- **`dotnet/`, `emulator/managed/`** — отдельная read-only/synthetic IPC инфраструктура.
- **`research/dev23–dev25/`** — архив, `docs/research/` — исследовательские материалы.

Сведения о происхождении кода: [PROVENANCE](docs/PROVENANCE.md).

## Проверки и пределы

Синтетический CEM50 B9FB успешно выдаёт **13/13 кадров** в лабораторных x86 тестах. Последний подтверждённый CI `development`: [#44871560856](https://github.com/vorlocsev/virtualcar/actions/runs/44871560856), SHA `e86ff1f0ec7e02c7bcdc2c512003c3f5c450414f`, **success**. Поддержка J2534-2 PS рассматривается отдельно в [Draft #418](https://github.com/vorlocsev/virtualcar/pull/418) и [#419](https://github.com/vorlocsev/virtualcar/pull/419): есть owner-local native proof и отдельный VMware-провайдер, но нет подтверждённого сквозного оригинального VIDA ReadVin.

**Не доказаны:** автоматический VIDA ReadVin на текущем PS, успешная Hardware Session SectorV, ECU ID, T111/T122, ответ реального CEM и испытания физического J2534. Тесты DLL/синтетических профилей нельзя выдавать за эти результаты.

## Сборка из исходников

Эмулятор на Linux host (LLVM/LLD, GCC, Go ≥1.23, Python):

```sh
cd emulator
bash build-cross.sh
gcc -std=c11 -O2 -Wall -Wextra -o /tmp/virtualcar_test tests/virtualcar_test.c src/p2core/p2_cem_router.c src/p2core/p2_ls_observer.c src/p2core/p2_vehicle_core.c src/p2core/p2_j2534_bridge.c
/tmp/virtualcar_test
python3 -m unittest discover -s tests -p 'test_*.py'
(cd control && go test ./... && go vet ./... && GOOS=windows GOARCH=386 CGO_ENABLED=0 go build -o ../VirtualCarControl.exe .)
```

Для **старого proxy/OneClick** запускайте в корне `bash build_dev26.sh`; это иная сборка. `go:embed` OneClick требует предварительно созданных скриптом assets.

## Навигация и дальнейшая работа

- [Сводный аудит на 21.11.2026](docs/reports/2026-11-21-repository-audit-ru.md)
- [Указатель доказательств и технических материалов](docs/EVIDENCE_INDEX_RU.md)
- [ROADMAP](docs/ROADMAP.md), [NEXT_CHAT](NEXT_CHAT.md), [правила агентов](AGENTS.md)
- [Релизный Draft #2](https://github.com/vorlocsev/virtualcar/pull/2): `development` → `main`, не считать выпуском.

**Безопасность:** только чтение и проверенные синтетические fixture. Не публиковать приватные VIN, оригинальные VIDA/SQL/J2534 логи, закрытые донорские INI, двоичные диагностические инструменты, ECU-дампы или секреты; не добавлять выдуманные положительные ответы A3/E3/A6/B9F0. Без программирования, Security Access, автоматического merge в `main` и релиза.
