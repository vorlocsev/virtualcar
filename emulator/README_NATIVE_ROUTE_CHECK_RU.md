# Проверка настоящей x86 DLL без регистрации адаптера

В новом пользовательском сеансе после PR #22 наблюдались 13 запросов:
10 B9FB no_fixture, два P3 F114 unsupported и один unsupported_bus.
Неатрибутированных запросов и конфликтов не было, но прежние молчаливые
ECM запросы в этот сеанс не попали. Поэтому отсутствие конфликтов само по
себе не проверило исправленный путь. Полный пользовательский журнал и
профили не входят в репозиторий.

`tools/verify_native_routes.ps1` загружает реальную x86 DLL в отдельном
32-битном процессе Windows через LoadLibrary/PInvoke со stdcall. Это
прямые вызовы DLL, не C HOST_TEST со stub Win32 API. Скрипт копирует DLL
в новую папку и создаёт отдельный synthetic профиль с одним ECM, без CEM
фикстур. LOCALAPPDATA/TEMP/TMP меняются только в дочернем процессе;
установленная регистрация J2534, профиль и пользовательский журнал не
изменяются. Существующая выходная папка отклоняется без перезаписи.

Восемь групп: x86 ABI и 14 экспортов; шесть молчаливых ECM запросов на
двух одновременно открытых HS/LS каналах; ISO15765 suppression; B9FB без
фикстур; strict 250 kbit/s rejection; P3 F114 без узла по CAN/ISO15765;
functional suppression; READ128 на четырёх пустых каналах. Ни один из
запросов не требует новых ECU ответов или физического адаптера.

Из папки emulator, без прав администратора:

```powershell
.\tools\verify_native_routes.ps1 -DllPath 'C:\lab\VirtualCarJ2534.dll' -OutputDirectory 'C:\lab\native-check-new'
py -3 .\tools\verify_native_routes.py 'C:\lab\native-check-new\VirtualCar\dev47-backend.jsonl' --output 'C:\lab\native-check-new\audit.json'
```

Нужны обе команды: native runner проверяет API и отсутствие RX, Python
проверяет точные 13 транзакций, их маршруты/каналы/скорости, lifecycle и
статусы. Ожидаются 8 unverified/explicit_no_response, 2 no_fixture и
3 unsupported, без conflicts. `native_route_regression_verified=true`
относится только к synthetic DLL regression. Identity/client acceptance
остаются false. Ошибка анализа не создаёт положительный отчёт; существующий
отчёт не перезаписывается. Для повторного запуска выбрать новую папку.

Emulator CI теперь скачивает собственный cross-built артефакт и выполняет
эту проверку в Windows x86 процессе. Публикуется только обезличенный audit;
полные журналы, скопированная DLL и профиль в новый артефакт не включаются.
Новый VMware prerelease не выпускается.

Локально: настоящая DLL PR #22 прошла; исходная опубликованная DLL
в отдельном synthetic запуске отклонена Python-проверкой из-за старых
меток ECM/ECU_OTHER. Дополнительно выполнены failure-injection проверки
маршрутов, channel/protocol/baud, пропусков/дубликатов/некорректных событий,
неожиданного RX, приватных полей и отказа от перезаписи. Эта проверка не
заменяет сеанс SectorV/VDASH в VMware и не подтверждает обнаружение CEM.
