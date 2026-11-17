# B3A274 — opt-in лабораторный GGD CEM_50 (только чтение)

## Источники и границы доказательств

- Исходная ветка: `feature/b3a189-j2534-filter-scope`, commit `1efce9cd83bdce1694a630bee4946e1a9227664e`.
- В оригинальной VIDA (CarCom) вариант ECU `529`, `30682825  A`, P1/P2 GGD, конфигурация `541`.
- `T121_Config`: `fkT122_Protocol=7` (GGD v2), `commAddress=50`, `canAddress=18DA50F1`, `busRate=500000`, `addressSize=29`, `fkT130_Init_Diag=1081`, `fkT130_Init_Timing=1082`.
- Запросы `22 A4 5F` и `22 DD 02` реально зарегистрированы в оригинальной VIDA на `18DA50F1`; B3A261 уже доставлял `18DAF150: 7F 22 31` через `PassThruReadMsgs`.
- `T150_BlockValue` и `T148_BlockMetaPARA` для ECU-варианта 529: A45F — набор битовых масок одного байта состояния переключателей ключа (маска 04 = Ignition switch 15); DD02 — сырое 8-битное значение напряжения CEM с масштабом `x*0.25`; синтетические `0x32=12.50 V`.
- Это согласованные с CarCom **синтетические лабораторные значения**, а не фактические показания машины. Совпадение адреса и параметров ещё не доказывает выбор варианта 529 конкретным сеансом VIDA.
- `T111_Service` GGD `22`: `<request><item name="Service" length="8" /><item name="Identifier" /></request>`; ответ включает 16-битный REID и динамические PARAM. Длина исходного значения двух указанных DID в выбранном варианте — 1 байт. Предполагаемое кодирование `62 + DID + 1 байт` требует проверки оригинальной VIDA.

## Изоляция и конфигурация

По умолчанию новый путь выключен. Для **отдельной копии** `virtualcar.ini` рядом с новой x86 DLL, *без изменения старых B3A258/B3A261*:

```ini
[Diagnostics]
EnableGGDCemLab=1

[Vehicle]
ECUCount=2

[ECU1]
RequestId=18DA50F1
ResponseId=18DAF150
```

Этот фрагмент — только указание изменяемых ключей, **не заменять им полный профиль**. В приватной копии сохраняются исходные секции D2/ReadVin и остальные собственные параметры. J2534 provider должен иметь отдельное имя и отдельный путь к новой DLL/INI; зарегистрированные эталоны не перезаписывать.

Точный охват обработчика: `PROTO_ISO15765` (J2534 protocol 6), `500000` bps, **строго `CAN_29BIT_ID` в флагах канала (0x100)**, запрос CAN ID `18DA50F1`, ECU request/response `18DA50F1/18DAF150`, полная UDS payload длиной строго 3 байта. Не обслуживает сырые CAN-запросы или другие 125/250 kbit/s каналы.

| Входная payload | Новая ответная payload | Примечание |
| --- | --- | --- |
| `22 A4 5F` | `62 A4 5F 04` | Синтетическое зажигание 15 включено |
| `22 DD 02` | `62 DD 02 32` | Синтетические 12.5 В |
| Другие DID | Прежний обработчик | Без новой генерализации DID |
| Режим off | Прежний обработчик | Без регрессии поведения |

Никаких положительных ответов для D2 A3/A6, SecurityAccess, программирования, конфигурации или сброса автомобиля не добавлено. SessionControl `10` и TesterPresent `3E` не изменены — в последних выбранных логах оригинальной VIDA эти команды на данном маршруте не подтверждены.

## Тесты и приёмка

Код теста добавлен в `emulator/tests/virtualcar_test.c`: проверка default off, обоих payload, неподдерживаемого DID, укороченного запроса, неверного CAN ID, ответа ECU, скорости, протокола и отсутствующего/лишнего флага 29-битной адресации; полный проход J2534 PassThruConnect / PassThruWriteMsgs / PassThruReadMsgs / PassThruDisconnect с откатом режима в off. Эти тесты **добавлены, но ещё не исполнены на exact-head**.

Для сборки из клона **этой ветки** на Linux (LLVM/LLD, GCC, Python):
```bash
cd emulator
gcc -std=c11 -O2 -Wall -Wextra -o /tmp/virtualcar_test tests/virtualcar_test.c src/p2core/p2_cem_router.c src/p2core/p2_ls_observer.c src/p2core/p2_vehicle_core.c src/p2core/p2_j2534_bridge.c
/tmp/virtualcar_test
bash build-cross.sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

До запуска реальной VIDA: проверить SHA и PE32 собранной DLL; выполнить isolated native J2534 tests для провайдера с новым именем; удостовериться, что B3A258 13/13 frames и ReadVin по-прежнему проходят. Затем с исходной VIDA проверить `PID`, точный provider/INI, два положительных `PassThruReadMsgs -> delivered`, состояние NETWORK и отдельно **ECU Identification**. Не объявлять последнюю пройденной на основании двух `62`.

## Статус

- Исходный транспортный baseline: B3A258 ReadVin PASS (операторский результат), B3A261 29-bit TX/RX и NRC31 доставлены (операторский результат).
- Изменения B3A274: код и тесты подготовлены, но оригинальная VIDA, нативная x86 DLL, host C, Python и exact-head CI не проверены.
- Не публиковать Stable/release и не заменять эталонные J2534 провайдеры.
