# B3A319 — доказанный клиентский маршрут Hardware в SectorV

Анализ основан на **предоставленном пользователем** SectorV.exe (SHA256 b418954b22355782920315692b75dd88af5fb839ff5c5b4a2c57e69a62b2d16f) и ограниченном журнале B3A285-VIN-Recognition.txt. Оригинальные бинарные файлы и логи в GitHub не добавлены.

## Статическая связь

Метод SectorV.PublicClient.Configuration.ClientP2HardwareJ2534Probe::ReadRoute — IL-токен 0x060012FA — содержит строку логирования P2 hardware CAN и вызывает ClientP2HardwareProtocol.Read. Отдельный путь SectorV.VehicleDiagnostics/CemM30855FIdentification.ReadHardware присутствует в клиентской базе, но тот же литерал в проверенной цепочке от него не происходит.

## Факты из клиентского журнала

- VIN D2 0x50/500k: транспорт SectorV принял 13 кадров, matched=13. Это не OEM acceptance автомобиля.
- Hardware 0x50/500k: protocol 0x8004 connect=25, затем raw CAN 0x5 connect=0.
- Hardware-session 0x50: no-reply; 0 observed, 0 matched, elapsed=5015 ms.
- Клиент сообщил о переходе на 0x40/125k после очистки.
- Hardware 0x40/125k: protocol 0x8004 connect=0, затем no-reply за 5003 ms.
- Завершение: automatic identification failed at Hardware.

Вывод: уникальный литерал приписывает Hardware CAN попытку методу ClientP2HardwareJ2534Probe.ReadRoute. Отсутствие собственного маркера для другого обработчика не означает, что M30855F не мог использоваться в *другой* операции. Мы не доказываем слияние событий разных процессов в одну физически удостоверенную сессию.

## Реализация

emulator/tools/audit_b3a319_sectorv_client_path.py анализирует локальный ограниченный client-log (без исходных данных в GitHub). Он извлекает только фиксированные счётчики маршрутов, protocol, успешности J2534 Connect и outcomes VIN/Hardware. Не выводит PID, VIN, CAN payload, flags, timestamps, путь к файлу или ключи.

Локальный запуск:

    python emulator/tools/audit_b3a319_sectorv_client_path.py --client "C:/private/B3A285-VIN-Recognition.txt"

Тесты:

    python -m unittest discover -s emulator/tests -p "test_b3a319_sectorv_client_path.py" -v

15 синтетических проверок: уникальность источника маркера, отсутствие ложной атрибуции M30855F, разные протоколы/скорости, таймауты, VIN транспорт, запрет Hardware PASS, приватность, границы строк и CLI.

Даже client hardware-session result=received автоматически не доказывает OEM hardware number или успешную Security Access. Положительный ответ E3, B9 E0/F0 не генерируется. Исходные J2534 DLL, правила фильтрации, конфигурации и VIDA не меняются.

Следующий этап — разрешённая трасса реального/эталонного ответа целевого CEM либо отдельно маркированная лабораторная симуляция с проверкой SectorV. Статусы Hardware Session / VIN acceptance / ECU identification остаются NOT_VERIFIED.
