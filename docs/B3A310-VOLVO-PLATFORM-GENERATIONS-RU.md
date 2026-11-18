# B3A310 — различение Volvo P2, P2 Restyling, P3 в Virtual Car

Дата: 2026-11-18. Stacked на Draft PR #373 (CEM-H/L).
Цель: идентифицировать платформу и фазу рестайлинга как отдельный атрибут автомобиля; **не использовать это поле как замену CarCom, J2534 или проверенному ответу ECU**.

## 1. Контракт значений

INI `[Vehicle] Generation`:
- `P2`: ранняя фаза модели на платформе P2 до её основного рестайлинга.
- `P2-Restyling`: поздняя рестайлинговая фаза **на той же P2**, это не платформа P3.
- `P3`: другая платформа, реализованная на следующих поколениях ряда моделей.
- `Unknown` (по умолчанию): модель/год/производство не проверены.

В native C рантайме:
- `g_vehicle_generation`: 0 Unknown, 1 P2, 2 P2-Restyling, 3 P3.
- `vehicle_platform_family()`: `2` для P2 **и** P2-Restyling, `3` для P3, `0` при Unknown.
- Рестайлинговый флаг — только `generation==P2-Restyling`.
- Значение только записывается как отдельная metadata-строка журнала; **не** активирует D2, GGD, ISO-TP, CAN_PS, VIN, J2534 DLL, ECU fixtures и ничего не меняет в CAN RX/TX.

Это **три пользовательских варианта** для текущего запроса, но строго **две семейства платформ**: P2 (первоначальная и facelift) и P3.

## 2. Проверенные/допустимые ориентиры по модельному году (не по году производства)

| Модель | P2 до рестайлинга | P2 Restyling | P3 | Примечание |
|---|---|---|---|---|
| XC90 I | MY2003–2006 | MY2007–2014 | — | XC90 II начиная с MY2015 относится к SPA; НЕ классифицировать как P3 |
| S80 | MY1999–2003 | MY2004–2006 | MY2007–2016 | Отдельные поколения S80, facelift первой генерации |
| S60 | MY2001–2004 | MY2005–2009 | MY2011–2018 | MY2010 намеренно Unknown до подтверждения рынка |
| V70 | MY2001–2004 | MY2005–2007 | MY2008–2016 | MY2000 может быть P80, не назначать P2 |
| XC70 | MY2001–2004 | MY2005–2007 | MY2008–2016 | Отдельный рестайлинг MY2005 |
| XC60 | — | — | MY2009–2017 | US-публикации часто начинают с MY2010 |
| V60 | — | — | MY2011–2018 | Начало продаж зависит от рынка |

Ориентиры подлежат сверке с VIN/VIDA и рынком: особенно на границах модельных годов; этот список не является декодером VIN или перечнем утверждённых OEM ECU профилей. Неизвестная модель/год не переводятся в P3 автоматически. Модели P80, P1, SPA, CMA сознательно не охвачены этим трёхпозиционным классификатором.

**XC90 AWD V8 B8444S MY2009 → P2-Restyling, platform family P2**, а не P3. Дата появления платформы P3 (MY2007 S80) не меняет платформу параллельно выпускавшегося XC90.

### Источники
- Volvo Cars, официальная пресс-информация о рестайлинге S60 MY2005:
  https://www.volvocars.com/intl/media/press-releases/2654693A11F81CE1/
- Volvo Cars, V70 MY2005:
  https://www.volvocars.com/intl/media/press-releases/E8F30970BCD59E36/
- Volvo Cars, XC70 MY2005:
  https://www.volvocars.com/us/media/press-releases/FA477EBB2322B929/
- Volvo Cars, XC90 facelift MY2007 (Volvo press release as PDF):
  https://mb.cision.com/Main/23622/4199435/3565887.pdf
- Volvo Technical Journal TJ19245, platform/type/year tables:
  https://static.nhtsa.gov/odi/tsbs/2024/MC-11009807-0001.pdf
- FCP Euro platform histories:
  https://www.fcpeuro.com/blog/volvo-p1-p2-and-p3-whats-it-all-mean
  https://www.fcpeuro.com/blog/Volvo-XC90-Generations-Explained
- Volvo S80 first-generation facelift MY2004:
  https://www.volvocars.com/us/media/press-releases/B57624B9BB32B56E/

## 3. Отдельно от CEM и протокола

Идентичность автомобиля в эмуляторе следует рассматривать как набор независимых осей:

```text
Vehicle
  Model = XC90
  ModelYear = 2009
  Engine = B8444S
  Generation = P2-Restyling  => family P2
  CEMHardware = Unknown      => H/L не выводить из года
  CEMDiagnosticProtocol = Unknown  => D2/GGD не выводить из поколения
  J2534 route = separately verified evidence
  ECU fixture = separately approved owner-attested read-only capture
```

Платформенная фаза не является идентификатором диагностической конфигурации. Например, исходный VIDA `ReadVin` использует F114 GGD и альтернативы B9FB D2 при fallback. Нельзя маркировать весь P2 Restyling как «только GGD» или весь P3 как «только F114». Год не свидетельствует о CEM-H либо CEM-L.

## 4. CLI для консультационной классификации, не для прошивки

```sh
python emulator/tools/audit_volvo_platform.py --model XC90 --model-year 2009 --engine B8444S
```

Выводит `generation=P2-Restyling`, `platform_family=P2`, `p2_restyling=true`, а также неизменно `approved_for_ecu_response_selection=false`, `original_vida_runtime_verified=false`.
`--generation P3` при XC90/MY2009 — явный конфликт, итог `Unknown` с предупреждением, не скрытый override.
Параметры `--cem-hardware H/L/Unknown` и `--protocol D2/GGD/Unknown` независимы.

## 5. Проверки и ограничения

Восемь групп Python: XC90 MY2009, MY2007 boundary и MY2015 out-of-scope, MY2005 S60/V70/XC70, S80/V70/XC70 P3 switch, XC60/V60, независимость CEM/протокола, конфликт explicit generation, неправильные/неподдерживаемые вводы.

Восемь групп C-host: default Unknown, P2, P2-Restyling-family2, P3-family3, недопустимые аналоги, независимость CEM-H/L, независимость D2/GGD, сброс defaults.

Тесты находятся в исходниках, но **реальное выполнение Python/C, x86 Windows build, CI на exact head, оригинальная VIDA ReadVin и ECU-ID не доказаны**. Публикация сборки, merge, provider install, SQL/VIDA/Registry32/ECU modification не выполнялись.

**Дальше:** выполнить host Python/C suite на exact SHA и лишь затем в отдельном gate проверить выбранные модель/профиль/CarCom T100/T121 на оригинальной VIDA. Все CAN/ECU ответы должны оставаться независимыми от этого поля.
