# Virtual Car: первый контролируемый A/B/C-тест с SectorV/VDASH

Этап: экспериментальный Windows x86 LAB. Не является подтверждением совместимости или эмуляцией подлинного CEM XC90 V8 MY2009. Все испытания выполняются на **виртуальном J2534**, без физического подключения к автомобилю и без команд программирования.

## Зачем нужны три варианта

Здесь цель не угадать ECU-фрагменты, а получить от **реального диагностического клиента** различимое наблюдение:

| Режим | B9FB | B9F0 | Что отличает |
| --- | --- | --- | --- |
| A_NoD2 | Нет | Нет | Видит ли клиент виртуальный J2534, открывает CAN, посылает B9FB? |
| B_PublicB9FB | 13 кадров | Нет | Меняется ли последовательность запросов после B9FB? |
| C_MixedB9FB_B9F0 | 13 кадров | 3 кадра | Появляется ли следующий запрос при добавлении НЕСОГЛАСОВАННОГО B9F0? |

Все три профиля имеют одинаковые исходные [Vehicle]/[ECU0]/[ECU1] и одинаковый синтетический VIN. У B источник B9FB: опубликованный пример эпохи XC70 2005 с заменённым тестовым VIN. Он содержит донорские признаки XC70 и не является настоящим XC90 V8 MY2009. У C трёхкадровый B9F0 получен из ДРУГОГО публичного примера; согласованность CEM/автомобиля не установлена. Не используйте B/C для программирования ECU, вычисления PIN или записи конфигурации.

## Последовательность на Windows

Распакуйте весь архив в C:\VirtualCar-LAB, зарегистрируйте 32-битную DLL из scripts/install.ps1 в PowerShell администратора. Затем без повышения прав откройте Windows PowerShell и запустите:

    cd C:\VirtualCar-LAB
    & .\scripts\Select-P2ClientTrialProfile.ps1 -Variant A_NoD2 -IConfirmClientsClosed

Скрипт сохранит прежний virtualcar.ini только в приватном каталоге локального пользователя и атомарно заменит INI в корне LAB. Он **не запускает** SectorV/VDASH, не изменяет реальный автомобиль, не загружает файлы в сеть, не трогает сторонние J2534-регистрации.

Начните сбор:

    $a = "$env:USERPROFILE\Desktop\VirtualCar-A-001"
    & .\scripts\Capture-P2ClientRun.ps1 -Phase Begin -SessionDirectory $a

Вручную откройте **одну** диагностическую программу и выберите «SectorV Virtual Car (J2534)» (видимое имя зависит от клиента). Выполните одно обнаружение/только чтение, зафиксируйте, появился ли список блоков/VIN в интерфейсе, закройте программу ПОЛНОСТЬЮ.

    & .\scripts\Capture-P2ClientRun.ps1 -Phase Finish -SessionDirectory $a -IConfirmClientClosed

Для B только ПОСЛЕ A используйте:

    & .\scripts\Select-P2ClientTrialProfile.ps1 -Variant B_PublicB9FB -IConfirmClientsClosed -IUnderstandExperimentalDonorData

Новый SessionDirectory, например VirtualCar-B-001. Повторите Begin → запуск клиента → Finish. Изменять INI между Begin и Finish **запрещено**: Capture проверяет его SHA256.

Для C (опционально и лишь для read-only совместимости):

    & .\scripts\Select-P2ClientTrialProfile.ps1 -Variant C_MixedB9FB_B9F0 -IConfirmClientsClosed -IUnderstandExperimentalDonorData -EnableCompositeReplay

Без -EnableCompositeReplay C остаётся **заблокирован** самой DLL: FixtureProvenance=local_composite_unverified_trace_import вместе с AllowCompositeReplay=0 препятствует выдаче D2-ответов. Скрипт меняет флаг только в установленной **локальной копии**. Исходный файл в profiles/ остаётся заблокирован.

## Сравнение только безопасных данных

Откройте PowerShell в LAB:

    python .\tools\compare_p2_client_trials.py --a "$a\SAFE-JSON-REPORTS\client-boundary.json" --b "$env:USERPROFILE\Desktop\VirtualCar-B-001\SAFE-JSON-REPORTS\client-boundary.json" --output "$env:USERPROFILE\Desktop\VirtualCar-trial-comparison.json"

Можно дополнить --c <путь-к-C\SAFE-JSON-REPORTS\client-boundary.json>. Сравнение выделяет изменение: native records, Connect, B9FB/B9F0, первый P3, отдельные сведения о завершённом UI-сканировании. Все они являются **наблюдаемыми статусами**: positive B9FB transport не доказывает, что SectorV/VDASH принял VIN или обнаружил ECU.

Если один из запусков не оставил новых J2534-записей, такой результат отмечается как отсутствие транспортного наблюдения. Это не доказательство отсутствия автомобиля или ошибки протокола.

Передать на исследование можно VirtualCar-trial-comparison.json и вручную проверенные файлы из SAFE-JSON-REPORTS. **НЕ отправляйте** сырые SectorVVirtualCar.log, каталоги PRIVATE-DO-NOT-SHARE, резервные INI, VIN реальных автомобилей, серийные номера, PIN, токены и снимки экрана с персональными данными.

После тестов можно восстановить исходный INI из приватной резервной копии вручную при полностью закрытых клиентах или вернуть базовый профиль через -Variant A_NoD2. Реальное принятие XC90 V8 MY2009 требует отдельного наблюдения клиентского интерфейса и подлинных данных CEM этого автомобиля.
