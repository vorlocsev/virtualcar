# VDASH MY2005: аргументы PS setup, 03.11.2026

Задачи #37/#4, PR #42. Ограниченный Windows-запуск установил ранее скрытые
аргументы: **три PASS_FILTER с CAN_PS/DataSize4 без flow-control**, а также
**пять D8 periodic-registration calls с interval1000ms**. Все API по-прежнему
вернули ERR_NOT_SUPPORTED. Настройка фильтра, таймер, CAN transmission или
ответ ECU не создавались. Это входы для отдельного API-outcome эксперимента,
а не подтверждение CAN_PS transport или причины предупреждения клиента.

## Происхождение

| Компонент | Проверенный источник / SHA-256 |
| --- | --- |
| Runtime source | PR #42 `615329754f35cffed7142867e8ca91f96762b08b` |
| CI | [Emulator/native x86 41542195017](https://github.com/vorlocsev/virtualcar/actions/runs/41542195017) и [VMware LAB 41542194974](https://github.com/vorlocsev/virtualcar/actions/runs/41542194974): success; prerelease publish skipped |
| Artifact / merge ref | ID13186614212 / `fbf3ec4296425ddec2cf6c7334ab1d1120183543`, merge ref отличается от source HEAD |
| Outer archive | `3e534a2aed6f58815137ca103acacf3212962b751308ebd544e557cf904adf79` |
| Реально загруженная DLL | `346df8f6b783a846e339c5b39b518ef3785297a8de2c956496a7c6a3808c3e94` |
| Synthetic MY2005 profile | `cca3fc41ad09381a2c6239313466afb5c4b52b421e8015bacc276c839b2af860` |
| Frontend 2.5.115.85 | `eed3f62e84dbaf295f9225c8b82f043bd25d61fea74209e4b5c31c8a2d843ea8` |
| Native worker | `b29b7f5e90645c9b04a12d12578a154b6ee7441c7aab1865a5e19d31277fe1aa` |
| Private supervisor | `5fa798a85db353dfd03966f79ff84273e69b80c6e9199b4874452c3c2ff806e1` |

Outer/inner архивы и все file checksums проверены. Профиль тот же synthetic
MY2005 с одним ECM, opt-in configuration probe, RxStart/telemetry, без CEM
fixtures/passive traffic. GUI/worker hashes не изменились после запуска;
VMware guest и physical J2534 не использовались. Proprietary client binaries
не включены в Git, издательское происхождение клиента не установлено.

В отличие от [предыдущего длительного запуска](VDASH_CAN_PS_REJECTED_RUNTIME_20261103.md),
**прямой module binding получен**: 32-bit PSAPI sampler увидел библиотеку в
единственном captured worker, expected path и DLL/image hashes совпали.
PID сопоставлен как uint32, без публикации его значения; все native строки
принадлежат этому же процессу. Sample23:09:28.829617Z внутри интервала
запуска. Это доказательство текущего run, прежний пробел им не закрывается.

## Ограничение длительности и полнота

Один GUI invocation с ручным входом. Supervisor был готов до открытия GUI:
ожидание worker максимум900s, затем3 наблюдаемых Close либо90s работы.
Он остановил собственные процессы по **worker_runtime_deadline**, увидев
к этому моменту два Close. Полный suffix после остановки содержит **три
Open и три Close**: нельзя переименовывать trigger в «три Close» или считать
финальный Close доказательством, что весь run завершился до deadline.
Внешнее окно supervisor23:07:04–23:11:00Z включает ручной вход; worker
впервые замечен23:09:27.802Z. Эти отметки не назначаются CAN timestamps.

Вместо прежних многочасовых повторов записаны354 text lines /48 JSONL lines.
Нет nested/unmatched/unfinished API-сеансов. Это три API-цикла одной
виртуальной конфигурации, не три независимых vehicle tests.

| Полный suffix | Bytes | SHA-256 |
| --- | ---: | --- |
| Native text | 41728 | `50a00b45ec65829660473ffdabdea33bd21dab40e5ac9f7af8bcba2382ed6e8e` |
| Backend JSONL | 11970 | `24e9f9ebaaa28ad91297b9bdb71a6854fdabcc941b159dcbb8ad80275cbfb488` |

SHA-256 прежних префиксов обоих журналов сохранились. Raw bytes, VIN,
настройки аккаунта, профиль и screenshots остаются вне Git.

## Подтверждённые аргументы

| Calls | Type / protocol / sizes / flags / flow | Mask/pattern категория |
| ---: | --- | --- |
| 2 | PASS_FILTER; оба CAN_PS; оба ID-only4; оба flags0; flow absent | mask other-redacted; pattern nonzero11-bit range |
| 1 | PASS_FILTER; оба CAN_PS; оба ID-only4; оба flags0x100; flow absent | mask zero; pattern zero |

Произвольные mask/pattern values не опубликованы. Other-redacted mask не
означает invalid mask: битовая маска отличается от CAN ID. Таблица не
представляет установленные фильтры или подтверждённый routing.

Все пять periodic calls: declared CAN_PS, interval **1000ms**, valid catalog
interval. Отдельные rejected-attempt records дают D2_D8_unverified_prefix,
observed pins3/11, inspected raw classic CAN. Было также пять таких же
WriteMsgs attempts. Всего10 rejected-attempt records и8 setup records;
periodic records описывают одни и те же пять calls, их нельзя складывать
как разные TX. Ни periodic firing, ни transmitted D8 не наблюдались.

Новая filter metadata валидна3/3, periodic5/5, malformed0. Старые27 probe
records:7 allocations +7 pin SET +3 filter rejects +5 write rejects +5 periodic
rejects. Все семь pin SET наблюдали3/11 на125000; физическое wiring MY2009
не устанавливалось. Connect23:7 PS OK,6 ISO15765 OK,1 CAN OK,9 protocol3 rejects.

Первый API-сеанс, source-order строки полного suffix:

| Строки | Наблюдение | Следующий шаг |
| --- | --- | --- |
| 20,25–26 | Open; CAN_PS flags0x800/125000 OK, pins3/11 | PASS-filter rejects35/39 |
| 46–47 | PS flags0x900 OK, pins3/11 | Extended PASS-filter reject56 |
| 62,81 | Standard CAN, затем ISO15765/500000 | TesterPresent90, VIN request100 |
| 104,107 | Отдельные RX start/data | Extended ISO15765 setup113 |
| 122 | Extended functional TesterPresent | PS channel, pins3/11 в126–127 |
| 134 | D8-prefix WriteMsgs rejected | StartPeriodicMsg |
| 136–137 | Requested1000ms setup + D8-prefix record одного periodic call, rejected | Disconnect/Close143 |

Остальные periodic setup records:178/241/284/347, также1000ms. Число и
порядок вызовов не превращаются в измеренный firing rate. Каналы после
Disconnect переиспользуются; inter-log clocks не склеиваются.

## Обычный транспорт, UI и восстановление

Девять обычных TX — по три7DF TesterPresent,7DF OBD VIN и extended functional
TesterPresent. Backend9 roots/9 terminals,3 sessions; delivered/unsupported/
unverified по3, queued=dequeued6, drops/filter-drops/conflicts/invalid0.
Text auditor:3 VIN deliveries,3 extended TesterPresent requests, D2/P3
recognized0, parse errors0. Это транспортные observations без CEM identity.
Все6 RX metadata records проверены, missing/invalid/off-route0; actual RX
полностью учтены, ignored RX0.

Agent видел synthetic XC90/P2/B8444S/MY2005 и12.5V, затем communication warning
о недоступных ECU. Нажата только OK для закрытия предупреждения; рекомендация
reset не выполнялась. ECU list до автоматической остановки **не наблюдался**,
поэтому исход прежнего run сюда не переносится. Start live logging, DTC clear,
reset, security и programming agent не нажимал.

Supervisor завершал только собственные процессы по path/start/PID guards.
Первое ожидание завершения Frontend превысило2s, последующий ограниченный
проход и независимая проверка подтвердили remaining0 для GUI/monitor/worker.
Прежний LastDevice восстановлен, собственная временная регистрация удалена,
исходная PR22 регистрация не менялась. DLL/profile hashes сохранились.

## Следующий обоснованный эксперимент

Параметры больше не приходится угадывать: filter envelopes ограничены
PASS/ID-only, flow отсутствует, период VDASH здесь1000ms. Опубликованный
[comparative VIDA/spnda контекст](VDASH_CAN_PS_REJECTED_RUNTIME_20261103.md#сопоставление-с-опубликованными-первичными-источниками)
с4000ms не устанавливает значение этого клиента.

Теперь можно отдельно спроектировать default-off **API-outcome injection**:
filter-only, exact-D8-write-only и periodic-registration-only, со своими
PS-local handles, без generic pump, bridge, backend TX или ECU RX. Такой
STATUS_NOERROR был бы смоделированным исходом API, не подтверждением передачи
и не D8 ACK. Нужны независимые условия, сохранённый baseline и новый bounded
version/module-bound run; одновременное принятие всех трёх не установит gate.
В этом этапе принятие API и transport не реализованы. Условие SectorV/VDASH
normal-mode preparation и подходящие MY2009 CEM ответы остаются неизвестны.

## Восемь проверок

1. Exact source/merge ref, artifact и внутренние checksums.
2. Прямой module path/hash + sole-worker PID match, неизменная версия клиента.
3. Bounded supervisor, действительный deadline trigger и три полных API-цикла.
4. Неизменные префиксы и полные suffix с SHA-256.
5. Три filter envelopes и пять interval1000ms records без raw private values.
6. Отдельные setup/attempt counts и прежние27 probe records, без API success.
7. Обычные TX/RX/backend и UI warning отдельно от не наблюдавшегося ECU list.
8. Собственные процессы/регистрация/selection восстановлены; никаких новых
   CEM replies, raw data, main/Dvinholm/prerelease изменений.

Connect/backend auditors — runtime source6153297. Text auditor PR #41
`c0f6484`, SHA-256
`e38170b56ec60467f5ff64bd89b4353a425f532a707d81bae010070466139233`,
с `--include-obd`; прежние форматы поддержаны. Локальные188 Python checks
OK/1 expected native-DLL skip; C/native x86 выполнены в указанном CI.
[Metadata-only summary](vdash-can-ps-setup-runtime-20261103.summary.json).
