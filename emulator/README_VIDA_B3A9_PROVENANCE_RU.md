# B3A9 | Проверка происхождения ответов ECU для VIDA 2014D

Статус: **локальные Python-тесты 8/8 PASS; подлинный ECU RX НЕ ПОЛУЧЕН; VIN НЕ ПРОЧИТАН**.
Этап опирается на точный B3A8 JSON и оригинальные журналы B3A7 (HEAD `0722b530aa48a7f1790d5f0dd1dddbe790518705`). Этот коммит меняет **только исследовательские Python-файлы и документацию**, не DLL J2534.

## Почему нельзя просто вставить 13 кадров B9FB

Оригинальная VIDA попыталась получить `726:22F114` (1), `40:B9FB` (2), `50:B9FB` (4), `51:B9F0` (1). Во всех 27 вызовах `PassThruReadMsgs` был тайм-аут. B3A7 подтвердил ABI `FIVE_BAUD_INIT` и 5/5 локальных ACK, но **не получил** ни одного настоящего ответа ECU. См. B3A8-отчёт и PR #319.

В `emulator/samples/p2_b9fb_public_redacted.txt` есть опубликованный исторический DiCE-захват. В `emulator/virtualcar-p2-b9fb-lab-vin.ini` VIN подставлен в лабораторные кадры. У `emulator/samples/p2_b9f0_public_excerpt.txt` другой маршрут CAN ECU 0x50, а не ISO9141 ECU 0x51. Эти примеры можно использовать для проверки структуры, но **не как доказательство ответа XC90 V8 MY2009**. Данные автомобилей P3 и V50 также нельзя автоматически переносить на XC90 P2.

Ссылки на первоисточники: [публичный исторический DiCE-захват, vtl, 2021](https://www.matthewsvolvosite.com/forums/viewtopic.php?p=573073), [VolvoDiagToolkit, реальный V50 2007, другая модель](https://github.com/MarvinParanoid/VolvoDiagToolkit/blob/main/docs/volvo-protocol.md), [сервисный бюллетень XC90 2009 о CEM 0x50 на P2 после 2004 года](https://lemon-manuals.la/Volvo/2009/XC90%20FWD%20L6-3.2L%20VIN%2098%20B6324S/Repair%20and%20Diagnosis/Powertrain%20Management/Computers%20and%20Control%20Systems/Technical%20Service%20Bulletins/Customer%20Interest/Computers%2FControls%20-%20CEM%20Download%20Interrupt%20Recovery/). В бюллетене рассмотрен XC90 с другим двигателем, поэтому он подтверждает только семейство адресации, не конкретный ответ V8.

## Что умеет B3A9

- `emulator/tools/audit_vida_b3a9_provenance.py` принимает итоговый `B3A8-source-verified.json`, проверяет 8 запросов, 27 тайм-аутов и отсутствие ECU RX. В этом режиме результат: `AWAIT_AUTHENTIC_ECU_CAPTURE`, у всех маршрутов `replay_approved=false`.
- Дополнительный режим `--manifest` + `--raw-capture` проверяет **только кандидата 0x50:B9FB на D2 CAN** в формате оригинального текстового журнала DiCE/J2534 с байтами вида `PassThruReadMsgs() msg[0].Data = [0x..]`. Не нужно заявлять, что инструмент уже проверяет ISO9141 `0x51:B9F0` или ISO15765 `726:22F114`.
- Требуются неизменный исходный файл и его SHA256/длина; подтверждённые метаданные XC90 V8 2009 P2 и хеш документа-основания; номера строк и SHA256 каждой исходной строки TX и RX; правильные заголовки `CB 50 B9 FB` / `8F 50 F9 FB`, CAN-ID, порядок кадров, `4F` и временные метки.
- Даже если структура соответствует, итог **`STRUCTURE_ONLY_PENDING_INDEPENDENT_REVIEW`**. Поле `vehicle` в манифесте является *заявлением оператора*, а не независимым подтверждением идентичности. Автоматически активировать ответы ECU по такому манифесту запрещено.
- Подлинные данные никуда не отправляются, исходные файлы не меняются и не обезличиваются. В агрегированном отчёте нет байтов VIN и ECU. Создание отчёта с `--out` откажет, если файл уже существует.

## Локальная проверка

```powershell
python emulator\tools\audit_vida_b3a9_provenance.py --b3a8-report B3A8-source-verified.json --out B3A9-provenance-status.json
python -m unittest discover -s emulator\tests -p test_audit_vida_b3a9_provenance.py -v
```

Ожидается `AWAIT_AUTHENTIC_ECU_CAPTURE`, все 8 синтетических тестов PASS. Никакой автомобиль/DiCE/VIDA не запускаются.

При появлении настоящего DiCE-захвата:

```powershell
python emulator\tools\audit_vida_b3a9_provenance.py --b3a8-report B3A8-source-verified.json --manifest OriginalVehicleCapture.manifest.json --raw-capture OriginalVehicleCapture.log --out B3A9-candidate-review.json
```

Файл манифеста создаётся отдельно, без подмены исходника. Требуется внешний контроль идентичности автомобиля и авторитетное сопоставление ответов с каналами и реальным ECU. SHA256 исходного журнала не доказывает сам по себе его происхождение. Ни один результат этого инструмента **не разрешает** воспроизведение на виртуальном ECU.

## Следующие границы

1. Найти оригинальную, привязанную к XC90 V8 2009, сессию DiCE с реальными ответами `0x50:B9FB` и проверить её в B3A9, включая идентичность автомобиля.
2. Отдельно получить `0x51:B9F0` ISO9141 и ключевые байты FIVE_BAUD_INIT, если они вообще применимы к этому ECU в этой конфигурации. Не выдавать выходную *ёмкость 2* за считанные байты.
3. Отдельно проверить `726:22F114` как возможный fallback/probe, а не автоматически приписывать его P2 CEM.
4. После появления реально подтверждённых байтов нужен новый isolated x86 build, 6–8 host/native проверок и оригинальная VIDA acceptance. PR оставить Draft, без релиза и программирования ECU.
