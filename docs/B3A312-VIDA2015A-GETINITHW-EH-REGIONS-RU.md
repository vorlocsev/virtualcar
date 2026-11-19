# B3A312 — оригинальная VIDA 2015A: EH-области возле GetInitHwSettings

Дата: 19 ноября 2026. Только изолированный Draft PR #376.
Никакого выполнения исходных VIDA DLL, CLR/SQL/J2534/CEM
или изменений в оригинальной установке; CI/jobs не запускать.

## Фактический owner-only исходный отчёт до этого этапа

Предыдущая утилита audit_vida_2015a_inithw_stack_boundaries.py
успешно выдала для трёх SHA-256 закреплённых оригинальных DLL:
- CarCom.DB.DLL: 140 CIL тел, 0 внешних GetInitHwSettings;
- VehicleCommProvider.DLL: 175 тел, 1 GetInitHwSettings callvirt,
  2 stfld в целевое FieldDef. Перед stfld в конструкторе
  стоит newobj MemberRef с **одним явным параметром**; перед
  stfld в другом методе стоит callvirt MemberRef с **нулём
  явных параметров**. Внешний target call находится в методе,
  у которого fat IL header имеет MoreSects; оба writer
  метода не имеют MoreSects.
- Workflow.DLL: 1719 тел, 5 GetInitHwSettings callvirt,
  1 stfld в локальное поле, непосредственно после newobj
  MemberRef конструктора с **одним явным параметром**.
  Ни один из пяти caller методов и единственный writer
  метод не имеют MoreSects.

Ни в один из 6 callsite sink и 3 stfld sink не найден
прямой текстовый branch/switch/leave target (0/9).
Это НЕ является полным CFG, aliasing, EH, stack-provenance или
доказательством выполнения пути, где передаётся нужный список
T161 профилей.

Предыдущая цепочка: три операции перед stfld имеют
совпадающую с target FieldDef точную SAME-MODULE ссылку
CLR class TypeDefOrRef (2 newobj owner + 1 callvirt return,
3/3). Предшествующая инструкция и совпадение
типа НЕ доказывают реальный источник значения.

## Новый отдельный разбор секций EH

emulator/tools/audit_vida_2015a_inithw_eh_regions.py

Читает строго три прежние SHA-256 pinned DLL только как
байты; сканирует лишь те MethodDef, где присутствует
оригинальный GetInitHwSettings MemberRef callsite.

Для fat IL header с MoreSects:
- разбирает последовательно small и fat CorILMethod_Sect;
- различает EHTable (kind 0x01) и non-EH секции;
- считывает small/fat CorILMethod_Sect_EHClause;
- проверяет допустимые границы try/handler/filter и
  alignment с CIL instruction boundaries;
- считает только fixed categories: catch/filter/finally/fault,
  small_eh_sections, fat_eh_sections, other_extra_sections;
- для целевого call/callvirt считает положение относительно
  try/handler/filter и вне всех EH-областей;
- сравнивает EH-membership соседнего ldfld и call/callvirt.
  Различие — возможная граница исполнения и точка
  дальнейшего осторожного анализа IL.

Запрещён вывод оригинальных IL offsets, metadata tokens,
catch type identities, EH-кодов, имен методов/полей,
значений VIN, профилей или исходных файловых путей.
Ошибка в повреждённых/неподдерживаемых метаданных — fail-closed
с публикацией только имени класса исключения.

Ключевые поля результатов:
- target_calling_methods_with_extra_sections;
- small_eh_sections / fat_eh_sections / other_extra_sections;
- eh_clause_kind_counts;
- reader_in_try / reader_in_handler / reader_in_filter /
  reader_outside_eh_regions;
- reader_in_multiple_eh_regions;
- reader_ldfld_and_call_cross_eh_membership.

**Граница доказательства:** принадлежность к EH-области
не означает, что конкретный catch/finally выполняется,
не устанавливает адрес receiver, вершину стека или
гарантированную передачу значения в GetInitHwSettings.
Нет interprocedural CFG, def-use и runtime acceptance.
Если у метода присутствует MoreSects, это также может быть
non-EH секция — новый анализатор не предполагает catch
только по флагу header.

## Owner-only локальный запуск Windows

Из checkout ветки feature/b3a312-installed-vida-carcom-readonly:

    git pull --ff-only

    py -3 -m unittest discover -s emulator/tests -p test_vida_2015a_inithw_eh_regions.py -v

Только после Ran 17 tests и OK:

    py -3 .\emulator\tools\audit_vida_2015a_inithw_eh_regions.py --folder 'E:\vida'

17 тестов полностью синтетические: small/fat EH,
catch/finally/fault/filter, chained sections, boundary cross,
malformed flags/offsets, SHA fail-closed, privacy.
Ни Windows suite, ни оригинальный новый EH-аудит
на дату коммита не выполнялись. GitHub static review —
не замена выполненным тестам.

Оригинальный профиль XC90 V8 2009, T161→T136 InitHw fallback,
эффективная скорость CEM D2, содержимое аргумента
profileIdentifiers и принятый VIDA ReadVin всё ещё НЕ доказаны.

Изменения только в Draft PR #376: без workflow dispatch,
CI, merge, изменений main/development и релизов.
