# Virtual Car: первый запуск SectorV / VDASH на Windows

Это **исследовательский Windows x86 LAB**, не релиз и не подтверждение
совместимости с SectorV/VDASH. Внутри архива находится виртуальный
адаптер J2534 и только синтетический/непроверенный профиль. Никаких
операций записи в ECU, поиска PIN или программирования здесь нет.

## Подготовка

1. Распакуйте **весь** LAB ZIP в отдельную постоянную папку, например
   C:\VirtualCar-LAB. Не запускайте скрипты прямо внутри ZIP.
2. Убедитесь, что VirtualCarJ2534.dll, virtualcar.ini,
   VirtualCarControl.exe и каталоги scripts, tools, samples,
   docs лежат рядом в корне распакованного архива.
3. В Windows PowerShell от администратора зарегистрируйте
   виртуальный 32-битный адаптер, если ещё не зарегистрирован:

       & 'C:\VirtualCar-LAB\scripts\install.ps1'

   Скрипт меняет только запись виртуального адаптера в
   Registry32 J2534 04.04. Другие установленные адаптеры не затрагивает.
   Альтернатива: используйте кнопку Install основного GUI.
4. В обычном PowerShell, без прав администратора:

       cd C:\VirtualCar-LAB
       & .\scripts\diagnose.ps1

   Регистрация должна указывать **ровно на эту** x86 DLL.
   Клиент x64 может не обнаружить 32-битный J2534.
   Для обработки журналов должен быть установлен Python 3.

## Контролируемое сравнение A/B/C (рекомендуется)

Чтобы найти, на каком ответе SectorV/VDASH прекращает обнаружение,
используйте **три разных сеанса с одним клиентом**. Перед сменой
профиля обязательно закройте диагностический клиент и VirtualCarControl.

Профили лежат в `profiles/`:

- **A_NoD2**: нет B9FB/B9F0, проверка подключения и запросов.
- **B_PublicB9FB**: 13 кадров B9FB исторического XC70 с заменённым
  лабораторным VIN. **Не XC90 V8 MY2009**.
- **C_MixedB9FB_B9F0**: B9FB + B9F0 из разных опубликованных примеров.
  Происхождение одного автомобиля **не доказано**. По умолчанию ответ
  заблокирован, для исследования нужен отдельный `-EnableCompositeReplay`.

Для теста A (PowerShell без прав администратора):

    & .\scripts\Select-P2ClientTrialProfile.ps1 -Variant A_NoD2 -IConfirmClientsClosed
    $session = "$env:USERPROFILE\Desktop\VirtualCar-A-001"
    & .\scripts\Capture-P2ClientRun.ps1 -Phase Begin -SessionDirectory $session

Затем **вручную** запустите SectorV или VDASH, выберите виртуальный
J2534, выполните только чтение и закройте программу. После закрытия:

    & .\scripts\Capture-P2ClientRun.ps1 -Phase Finish -SessionDirectory $session -IConfirmClientClosed

Повторите для B с `-Variant B_PublicB9FB` и дополнительным
`-IUnderstandExperimentalDonorData`, используя новый каталог
`VirtualCar-B-001`. При необходимости проведите C:

    & .\scripts\Select-P2ClientTrialProfile.ps1 -Variant C_MixedB9FB_B9F0 -IConfirmClientsClosed -IUnderstandExperimentalDonorData -EnableCompositeReplay

Для C также используйте **новый** каталог `VirtualCar-C-001`.
Никогда не переключайте профиль между Begin и Finish одного запуска.

Когда готовы два или три каталога, сравните только безопасные JSON:

    python .\tools\compare_p2_client_trials.py --a "$env:USERPROFILE\Desktop\VirtualCar-A-001\SAFE-JSON-REPORTS\client-boundary.json" --b "$env:USERPROFILE\Desktop\VirtualCar-B-001\SAFE-JSON-REPORTS\client-boundary.json" --output "$env:USERPROFILE\Desktop\VirtualCar-trial-comparison.json"

Если есть C, добавьте `--c` с аналогичным путём к его
`client-boundary.json`. Сравнение показывает только изменения
транспортных этапов, а **не факт принятия автомобиля клиентом**.

Резервные копии исходного INI сохраняются локально в
`%LOCALAPPDATA%\VirtualCar\TrialProfileBackups`; **не публикуйте** их.

Подробности: `docs/research/P2_CLIENT_TRIAL_ABC_RU.md`.

## Запуск одного теста

Не меняйте INI и не переустанавливайте DLL во время одного теста.

**До запуска SectorV или VDASH:**

    $session = "$env:USERPROFILE\Desktop\VirtualCar-Session-001"
    & .\scripts\Capture-P2ClientRun.ps1 -Phase Begin -SessionDirectory $session

Вручную откройте **одну** диагностическую программу, выберите
«SectorV Virtual Car (J2534)», выполните только обнаружение/чтение
и полностью закройте клиент.

**После закрытия:**

    & .\scripts\Capture-P2ClientRun.ps1 -Phase Finish -SessionDirectory $session -IConfirmClientClosed

Дополнительно разрешён операторский JSON по шаблону
samples/p2-client-ui-observation.template.json, передаваемый
параметром -UiObservation. Не вводите в этот файл реальный VIN,
серийные номера, пути или данные ECU. Не создавайте этот файл,
если интерфейс клиента не удалось изучить.

Результат:
- SAFE-JSON-REPORTS: обезличенные JSON после ручной проверки можно
  передать на анализ.
- PRIVATE-DO-NOT-SHARE: приватные снимки состояния и исходные пути;
  **никому не отправлять**.
- Исходный журнал остаётся там, где его создала DLL, и не копируется
  в общедоступную папку.

Если не появилось новых J2534-записей, Finish создаст безопасный
отчёт с результатом no_new_native_j2534_records_observed.
Он не доказывает, что клиент вообще загрузил DLL или что ECU
отсутствует.

Для следующего теста создавайте новый каталог сеанса. Ни одна
успешная проверка CI не подтверждает реальный XC90 V8 MY2009,
VIN, список ECU или принятие ответа CEM сторонним клиентом.

Подробная инструкция:
docs/research/P2_REAL_CLIENT_CAPTURE_WORKFLOW_RU.md

Для удаления регистрации только виртуального адаптера запустите
PowerShell от администратора:

    & 'C:\VirtualCar-LAB\scripts\uninstall.ps1'
