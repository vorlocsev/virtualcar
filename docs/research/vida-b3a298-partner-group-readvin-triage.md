# B3A298 — VIDA Partner Group / VIN decoder: read-only triage before F114 changes

Дата исследования: 2026-11-18. Статус: исследовательский Draft; **ни одной новой приёмки VIDA**.
Область: оригинальные VIDA 2014D/2015A и XC90 V8 MY2009; **без изменения установленной VIDA, SQL, реестра, адаптера или оригинальных данных**.

## Новое внешнее подтверждение

Официальное руководство Volvo *VIDA HELP* © 2008, section **4.2.3 Include transmission at VIN read out**, PDF printed page 19 (87), отдельно описывает влияние *Partner Group* на декодирование VIN/трансмиссии. Для автомобилей USA/Canada/Mexico/Puerto Rico указана группа **AME**; для иных рынков — EUR/NOR/INT и особые случаи China/Arabia. Руководство допускает временное переключение группы в VIDA Admin для распознавания VIN не своего рынка. Это подтверждение **зависимости декодера от рынка**, но НЕ установление конкретной правильной группы для локального VIN.

- Официальный документ в публичном зеркале: https://www.autoscaners.ru/data/volvo%20dice/VIDA-Help-en-GB.pdf
- Дополнительное руководство *VIDA All-in-one Help* © 2013, раздел **5.1.1.2 VIN decoding**: при отключении декодирования можно вручную корректировать профиль; опция возвращается к On при новом VIN/Read Vehicle. Это обходной режим, **не доказательство правильной идентификации автомобиля**: https://manualzz.com/doc/23472941/vida-help---workshop-support-guide

Независимый обратный разбор VIDA 2014D за 2020 год указывает оригинальную **BaseData.dbo.VINDecodeModel** и поля **fkPartnerGroup**, **fkModelYear**, **VINCompare** (в описании также использованы диапазоны chassis). Его автор предлагал корректировать SQL для автомобилей 2016/2017:
https://amionrails.wordpress.com/2020/04/27/how-to-fix-vin-can-not-be-decoded-on-selected-partner-in-vida2014/

**Не применять SQL UPDATE или подмену модельного года** из этой статьи. Исходная таблица, её фактические поля, условия декодирования и строки **ещё не подтверждены для owner VIDA 2014D/2015A**, тем более для именно XC90 V8 MY2009.

## Соотнесение с наблюдаемым отказом

На прежней оригинальной VIDA в PR #357 / B3A275 наблюдались:
- 3 J2534 TX: `0x726 22 F1 14`;
- положительные RX: `0x72E 62 F1 14 + VIN17`;
- отказ UI с точным текстом: **The VIN can not be decoded on selected Partner Group**;
- без A6 и D2 B9 в **этом конкретном сеансе**.

Источник: https://github.com/vorlocsev/virtualcar/pull/357

Таким образом подтверждена **доставка положительного F114 на уровне J2534**.
Не подтверждены ни полная прикладная декодировка оригинальным `ResponseHandler`,
ни успешный `Output.AddVIN`, ни прохождение `VINDecodeModel`, ни VIN acceptance.

Кроме того, B3A278/PR #358 выявил в другом оригинальном запуске `TxFlags=0x40`
(`ISO15765_FRAME_PAD`), на который старый opt-in-обработчик не отвечал.
Не объединять наблюдения из разных головных SHA/сеансов.
https://github.com/vorlocsev/virtualcar/pull/358

**Неизвестно**, какая Partner Group была выбрана в отклонённом сеансе,
какой полный 17-символьный VIN использовался локально, какой точный
декодер/SQL-запрос отказал и существует ли соответствующая запись
`VINDecodeModel`. Наличие в исходниках Virtual Car демонстрационного
VIN с модельным годом 2010 не доказывает, что именно он был применён
в отказавшем оригинальном сеансе MY2009.

## Первый gate: фактическая схема локального BaseData (только чтение)

Использовать проверенную приватную, отдельно checkout-нутую ветку
исследовательских инструментов из **Draft PR #317**:
https://github.com/vorlocsev/virtualcar/pull/317

Требуются: Python+pyodbc, существующий DSN `VIDA_READONLY`, TLS с
проверкой сертификата, учётная запись с реально разрешённым только
SELECT/просмотром каталога. `ApplicationIntent=ReadOnly` сам по
себе НЕ запрещает SQL-запись. В текущей установке SNAPSHOT isolation
не следует включать или изменять.

Пример локального PowerShell, запускать **только в checkout PR #317**,
без создания новых таблиц/изменения базы:

```powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
New-Item -ItemType Directory -Force -Path $private | Out-Null
py -3 emulator/tools/vida_original_schema_reader.py --database BaseData --output (Join-Path $private 'BaseData-original-schema-partnergroup-001.json')
if ($LASTEXITCODE -ne 0) { throw 'BaseData read-only schema inspection failed' }
```

Затем исследовать в исходном JSON (без маскирования) точные таблицы/колонки:
`VINDecodeModel`, `PartnerGroup`, `fkPartnerGroup`,
`fkModelYear`, `VINCompare`, диапазоны chassis, а также реальные FK.
**Имена, отсутствующие в оригинальной схеме, не считать существующими.**
Схема и FK не доказывают, что VIDA реально применила ту или иную строку.

После подтверждения полей возможен **отдельный owner-local SELECT**
через `vida_original_table_reader.py --filters-json` по
действительно существующей колонке и конкретной Partner Group.
Выход содержит **исходные значения, не обезличивает VIN/строки/имена**,
сохраняется только в защищённом локальном каталоге и не включается в PR.
При лимите >5000 строк не выдаётся частичная успешная выгрузка.
Ни одного оригинального BaseData SELECT на эту тему в ходе B3A298 не выполнялось.

## Второй gate: дифференциальный ручной ввод VIN против J2534

Для отдельного owner-approved GUI-сеанса в VMware, без DB UPDATE,
без программирования ECU и при зафиксированной Partner Group:

1. Сохранить снимок текущей группы партнёров, версии/сборки VIDA,
   выбранного инструмента и использованного локального VIN (полное
   оригинальное значение **только owner-private**, без GitHub).
2. В той же группе выполнить **ручной ввод тех же 17 символов VIN**,
   без связи с Virtual Car. Сохранить точное сообщение, декодированные
   модель, MY, двигатель, transmission и появление профиля.
3. В независимом новом диагностическом сеансе с той же группой и
   строго записанным SHA Virtual Car выполнить Read Vehicle через J2534.
   Независимо зафиксировать TX, RX dequeue, ответ парсера если доступен,
   UI VIN outcome и профиль.
4. Только по отдельному решению оператора проверить **правильную
   для рынка исходного VIN Partner Group** при ручном вводе, а не
   менять группы вслепую или менять данные BaseData. Изменение VIDA Admin
   может затрагивать настройки самой установки; не выполняется этим PR.
5. Если есть owner-approved **контрольный VIN, заведомо поддерживаемый
   этой установкой**, использовать его только для отдельного теста
   декодера без ECU; контрольный VIN не вписывать в репозиторий.
6. Не использовать `VIN decoding off` как подтверждение ReadVin:
   ручной профиль в этом режиме не равен успешной декодировке.

### Интерпретация результатов (не автоматические PASS)

| Ручной VIN при группе G | J2534 VIN при той же G | Что следует проверить |
|---|---|---|
| Failed | Failed | Декодер/покрытие VIN/группа независимо от транспорта; J2534/формат не исключены |
| Passed | Failed | Сначала исходный F114 payload, `ResponseHandler`, `Output.AddVIN`, передачу VIN декодеру |
| Passed | Passed | Только VIN-acceptance для точного сеанса, ECU-ID/T111/T122 отдельно |
| Failed | Passed | Различия UI-path/кэша/сессии; повторить с независимыми журналами |

Наличие CAN TX/RX или `PassThruClose` само по себе не присваивает
ни одной проверке статус Passed. Смена Partner Group может менять
профиль; статус пригодности модели/двигателя/TCM требует отдельного подтверждения.

## Третий gate: локализовать именно отказавший этап

Из оригинального исследования:
- XML ReadVin ScriptId `0900c8af8184c004`, 14 узлов, first GGD `22 F114`;
- `Output.AddVIN` использует параметр `59790` в соответствующей ветке;
- `ReadVinComponent.Execute` вызывает диагностический сервис, но
  не содержит логики декодирования конкретного Partner Group;
- `DiagnosticAction.class` заполняет VIN из `VehicleSpecVO` и
  не выполняет CEM/J2534 опрос в исследованном `execute`;
- browser bridge: `JavaEventHandle` в `Core.DLL`, `ScriptExecutorUC`
  в `UI.DLL`; статическая декларация не является runtime-callgraph.

Искать в оригинальных owner-local файлах точный ресурс сообщения
`The VIN can not be decoded on selected Partner Group` / key сообщения,
а затем его вызывающий метод, выбранную группу и факт получения VIN.
Не путать UI web session, .NET script engine и SQL VINDecodeModel.

Следующие конкретные неопределённости:
1. Получил ли оригинальный `ResponseHandler` валидный F114 / B9FB?
2. Был ли вызван `Output.AddVIN` с исходным VIN?
3. Какой слой вызвал VIN decoder и какую `Partner Group` передал?
4. Какая именно строка / предикат `BaseData` не сопоставились?
5. Существуют ли различия версии VIDA 2014D и локально установленной 2015A?

## Acceptance и ограничения

- Official Partner Group ↔ VIN decoding dependency: **подтверждено руководством**.
- `VINDecodeModel`/fkPartnerGroup как форма общественного реверс-инжиниринга: **найдено, не проверено на owner's original**.
- В отказавшем сеансе original VIDA F114 J2534 RX доставлен, GUI failed: **подтверждено прежним owner report**.
- Manual-VIN A/B, BaseData schema inventory и точная группа в этой сессии: **NOT TESTED**.
- Разбор полного F114 original `ResponseHandler` и ECU ID: **NOT ATTESTED**.
- Работающий ReadVin/ECU Identification XC90 V8 MY2009: **НЕ ПОДТВЕРЖДЕНО**.

**Никаких SQL UPDATE, ALTER DATABASE, Registry32, установки DLL,
изменений исходной VIDA, J2534 TX, запуска CI, публикации сборок, merge или
автоматического обезличивания оригинальных источников в этом этапе нет.**
