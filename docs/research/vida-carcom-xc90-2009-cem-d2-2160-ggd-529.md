# VIDA CarCom: XC90 V8 MY2009 — CEM D2 2160 / GGD 529

**Дата исследования:** 2026-11-21  
**Источник:** read-only SQL SELECT к установленной владельцем VIDA CarCom; выгрузки CSV и нормализованный локальный JSON-манифест. **Класс доказательства: SOURCE_RESEARCH / OWNER_LOCAL**, не CLIENT_OBSERVED, не CI_EXACT_HEAD и не OEM wire trace.

> Эта страница описывает **схемы интерпретации данных в CarCom**, а не готовые ответы физического CEM. Наличие идентификатора в базе не доказывает, что оригинальная VIDA действительно запросила его в конкретной сессии или приняла ответ.

## 1. Проверенная связь vehicle profile → CEM

Выборка из `T161_Profile`, `T160_DefaultEcuVariant`, `T100_EcuVariant`, `T101_Ecu`:

| Поле | Значение |
|---|---|
| Profile ID | **163120** |
| Профиль | `XC90 2009 B8444S` |
| Идентификаторы профиля | `model_id:275,model_year:2009,engine:184` |
| CEM D2 | **ECUVariant 2160**, part number `31296075 AA`, `fkT101_Ecu=525` |
| CEM GGD | **ECUVariant 529**, part number `30682825  A`, `fkT101_Ecu=802` |
| Более поздние варианты для сравнения | D2 **3018** / `31327407 AA`; GGD **3044** / `31327408 AA` |

Это **два диагностических представления**, а не доказанные «режимы прошивки» одного физического ECU. Номер `30786890` по этой выборке не является подтверждённым ECUVariant целевого профиля.

## 2. Протоколы, сервисы и конфигурации сети

`T122_Protocol`: **id=5, D2, version=7**; **id=7, GGD, version=2**.  
`T110_Service_EcuVariant` + `T111_Service`: у **2160 и 3018 по 54 привязки сервиса**; у **529 и 3044 по 9**. В выгрузках определения D2 совпадают по ServiceId, режимам и XML (там, где XML присутствует).

| ECUVariant | Конфигурация | Шина CarCom | Physical address | Functional address | Address-size |
|---|---:|---|---|---|---:|
| D2 2160 | 1824 | High s 1 CAN | `D0` | `50` | 29 |
| D2 2160 | 1825 | Low speed CAN | `40` | `C0` | 29 |
| GGD 529 | — | High s 1 CAN | `50` | `33` | 29 |
| GGD 3044 | — | High s 1 CAN | `50` | `33` | 29 |

Для GGD в CarCom указана скорость **500000** и поле `canAddress=18DA50F1`. Для D2 скорость и окончательные TX/RX CAN ID **не доказаны** этой выборкой: `busRate` пустой; `canAddress=FFFFE` является сырым полем базы, **не подтверждённым CAN frame ID**. D2 physical/functional address также нельзя приравнивать к CAN arbitration ID без трассы.

**D2 2160:** `B9` (ServiceId 2, Read Data Block By Offset), `A6`, `AE` и другие D2-сервисы. XML `B9` содержит Service(8 бит), Identifier(8 бит); описание ответа: BLOFF(8 бит) + динамический список PARAM. Это схема **прикладных данных**, не описание всех CAN/ISO-TP кадров.

**GGD 529:** `22` (ServiceId 100, Read Data By Identifier), `10 02/82`, `11 01/81`, `27 02`, `3E 00/80`; XML `22` использует REID(16 бит) + динамические PARAM. Дерево GGD построено через **REID**, поэтому поиск только `BLOFF` ошибочно даёт пустой результат.

### GGD: записи REID

| DID из `T150_BlockValue.CompareValue` | Поле CarCom | Длина описания |
|---|---|---:|
| `F110` | Online Diagnostic Database Reference | 24 байта |
| `F114` | Vehicle information section | 166 байт |
| `F106` | Vehicle Configuration Parameters | 130 байт у 529; 133 байта у 3044 |
| `F120` | ECU Software 2 number | 24 байта |
| `A45F` | Key Switch System Input Signal | 1 байт |
| `DD02` | Main ECU supply voltage | 1 байт |

Наиболее обоснованный **кандидатный** прикладной запрос для GGD Vehicle Information — `22 F114`, для Vehicle Configuration — `22 F106`. Подтверждение клиентским TX/RX с `62`-ответом требуется отдельно.

## 3. D2 2160: B9 block tree

Дерево `T144_BlockChild` для ECUVariant 2160, блоки типа BLOFF:

| Запросный идентификатор B9 | Root BlockId | Длина структуры | Дочерние PARAM |
|---|---:|---:|---:|
| `F0` | 4686268 | **15 байт** | 2 |
| `FB` | 4687470 | **166 байт** | 16 |
| `FC` | 4686717 | **130 байт** | 127 |

**B9F0:** 0–7: `ECU Complete Part Number` (8 байт); 8–14: `ECU Diagnostic Software number` (7 байт). `T143_BlockDataType id=53` = `BCD+Ascii`; `T155_Scaling id=177`, type=53, definition=`x`. Это **не** даёт подлинных 15 байт для номера конкретного физического CEM.

**B9FB:** координаты ниже — `T141_Block.offset/length` в битах, пересчитанные в байты; позиции относятся к **описанному CarCom блоку**, а не автоматически к индексу 8-байтового CAN кадра:

| Offset (байт) | Length (байт) | Название |
|---:|---:|---|
| 0 | 1 | Data length |
| 1 | 5 | Car Config Doc No |
| 6 | 3 | Car Config Issue No |
| 11 | 17 | VIN |
| 30 | 9 | FYON |
| 41 | 3 | Type (PNR-3) |
| 46 | 6 | Chassis |
| 54 | 2 | Factory code |
| 58 | 6 | Structure week |
| 66 | 20 | Package Identity |
| 88 | 40 | Неименованное поле в D2 2160 |
| 128 | 2 | Marketing code |
| 132 | 4 | Interior code |
| 138 | 5 | Exterior color code |
| 145 | 5 | S-message |
| 152 | 14 | Service information |

16 полей покрывают 142 из 166 байт; остаются **12 двухбайтовых промежутков = 24 байта**, которые нельзя объявлять CRLF без оригинального ответа. У GGD 529 вложенная структура FB имеет похожие именованные поля, но промежуточное поле 88–125 в отдельной выгрузке описано как **38 байт**, поэтому нельзя молча считать деревья побайтно одинаковыми.

**B9FC:** 127 однобайтовых PARAM занимают байтовые позиции 2–129 за исключением 7. **Не описаны байты 0–1 и 7**. Вариант D2 3018 описывает 133 байта; GGD 529 — 130, GGD 3044 — 133. Таблицы ENUM необходимо хранить по ECUVariant, а не смешивать.

Ключевые значения `CompareValue`, сопоставленные с `T191_TextData` (en-US) и проверенные внутри дерева **2160**:

| Offset (байт) | Параметр | Код | Значение CarCom |
|---:|---|---|---|
| 2 | 001-AC Vehicle main type | `0x40` | XC90 (PpeValue: P28) |
| 3 | 002-C1 Steering position | `0x01` | Left hand driven |
| 8 | 007-DF Gear box type | `0x02` | Automatic gearbox |
| 9 | 008-DB Gear box | `0x20` | TF-80SC AWD |
| 10 | 009-AE Vehicle sub type | `0x06` | XC90 (PpeValue: P28) |
| 12 | 011-AJ Power train | `0x02` | 4 wheel drive |
| 16 | 015-CB Engine dynamics/STC | `0x07` | 8 cyl non-turbo engine, petrol |
| 36 | 035-CF Engine | `0x61` | B8444S |
| 123 | 122-YB Year Designation Letter | `0x09` | Model year 2009 (PpeValue: YEAR9) |

**Это разрешённые значения каталога, а не фактически считанная конфигурация конкретного VIN.** Не конструировать «OEM CarConfig» из нескольких найденных кодов. `AsValue` и `PpeValue` — разные представления; сохранять оба.

## 4. D2 2160 vs 3018: service + init equality, schema inequality

Для 2160/3018 сопоставлены 54 диагностических сервиса и 56 строк `T130/T131/T132` (28 параметров на вариант). **28/28 значений инициализации** совпадают при сопоставлении по шине/роли/имени параметра; внутренние ConfigId/InitId различаются. Таблица ниже — **числа CarCom без утверждения единиц времени**.

| Параметр | D2 HS | D2 LS |
|---|---|---|
| retries / keep diag | 3 / 10 | 3 / 10 |
| T1 min/max | 20 / 25 | 40 / 45 |
| T2 min/max | 0 / 20 | 0 / 256 |
| T6 min/max | 0 / 50 | 0 / 60 |
| T7 min | 20 | 40 |
| T8 min/max | 5 / 50 | 0 / 60 |
| T9 min | 100 | 100 |
| T10 min/max | 10000 / 10050 | 10000 / 10050 |

Общая таблица инициализации и обработчик сервисов D2 разумны; **B9FC и ENUM остаются variant-specific**. Данные CarCom не устанавливают, в каких единицах хранятся T1–T10, и не разрешают напрямую переносить числа в таймеры J2534.

## 5. Provenance и контроль целостности выгрузки

SHA-256 локальных CSV (содержимое исходной БД и сырые трассы **не включаются в Git**):

| Локальный файл | SHA-256 |
|---|---|
| `XC90-CEM-Profile-Candidates.csv` | `da662668728bbc4a215a831f34395382acbbbdc947a88d77c2a169c18f986612` |
| `XC90-2009-CEM-B9-Tree.csv` | `20058277745701083353dba0a51e2ced8799e84c707b84dc22dc9db71e00a7b1` |
| `CEM-D2-2160-Services.csv` | `fff2cdca59aaf7857282eb1185af207db3e4b0491ddc6e313b6ef5b9edbe7315` |
| `CEM-D2-2160-Network.csv` | `c16d34451427431d678dede852728cb9804ff14f3238c3b9760c1d9ede3c71a6` |
| `CEM-D2-2160-3018-Init-Comparison.csv` | `2945fce1c6ffc6fb33de38a5b0681efe04643565680499e44360c30dd066bcaf` |
| Локальный нормализованный `CEM-D2-2160-VIDA-verified-manifest.json` | `eb5f6d1e390badec72429fb34fc5de5d3f1b1d84baa39ed1471e799472267478` |

Указанный JSON сформирован из read-only CSV и **не означает успешной приёмки VIDA**. Полный локальный экспорт, VIN из private donor, незамаскированные J2534 логи, исходная SQL/VIDA БД и ECU-дампы не публикуются.

## 6. Сопоставление с текущим Virtual Car и следующий gate

См. Draft [#418](https://github.com/vorlocsev/virtualcar/pull/418) и [#419](https://github.com/vorlocsev/virtualcar/pull/419): это PS-адаптер и side-by-side регистрация, **не подтверждение ReadVin**.

На момент статического просмотра [`emulator/adapters/cem50/virtualcar.ini`](../../emulator/adapters/cem50/virtualcar.ini) в ветке #419:

- `[D2_40] B9FBFrameCount=0`; `[D2_40_B9F0] FrameCount=0`;
- `[D2_50] B9FBFrameCount=13`, 500000, **только синтетическая 88-байтовая историческая структура**;
- `[D2_50_B9F0] FrameCount=0`; `D2_40_B9FC` / `D2_50_B9FC` frame count 0;
- `ECUCount=1` с `7E0/7E8`, **нет отдельно настроенного P3 CEM `726/72E`**.

Ранее ограниченное окно B3A55 ([#419](https://github.com/vorlocsev/virtualcar/pull/419)) классифицировало **98 app TX, 0 delivered RX**, в т.ч. D2 `B9F0` на CAN 125000 без fixture и запросы `22 F114`/ `22 F106` на P3. В текущем файле нет надёжной атрибуции активного INI для того сеанса, поэтому статический анализ файла **не доказывает**, что именно он был загружен VIDA.

**План read-only, без изменения рабочего PS provider:**

1. Зафиксировать **точный загруженный INI + полный путь и SHA DLL** внутри процесса-источника; не выводить успех из выбранного имени в GUI.
2. В свежем bounded окне зафиксировать raw **TX route: protocol / baud / CAN ID / адресат / сервис**, и отдельно native enqueue/read/deliver для каждого ответа.
3. Развести тесты **D2 LS/HS `B9 F0/FB/FC`** и **GGD `22 F110/F114/F106`**, не смешивать GGD и D2 в одном фикстурном ответе.
4. Проверить транспортную сборку 166-байтового B9FB по оригинальной трассе или достоверному донорскому ответу; **не подменять исторический 88-байтовый fixture нулями до 166 байт**.
5. Сохранить отдельные gate: PassThruOpen → Connect → app TX → RX enqueue → RX deliver → VIDA ReadVin → ECU identification → T111/T122. Нет прямого положительного подтверждения последних трёх.
6. Не включать неподтверждённые B9F0/A3 позитивные ответы, PIN/программирование, не запускать CI и не менять установленные DLL/Registry32 без отдельного действия и доказательства.

**Итог:** этот документ закрывает исследовательский этап сопоставления каталога MY2009 и D2 init, **не** закрывает сетевой acceptance gate.
