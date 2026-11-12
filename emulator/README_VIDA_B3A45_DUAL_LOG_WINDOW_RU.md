# B3A45: контрольное окно двух журналов VIDA и VirtualCar J2534

Инструмент `tools/audit_vida_j2534_session_window.py` работает **только на чтение**:
не запускает VIDA, не загружает DLL, не вызывает J2534, не меняет реестр,
не отправляет CAN-кадры и не создаёт ответы ECU. Входные журналы и приватный
baseline остаются в Windows/VMware у владельца.

## Почему нужны два файла

В исходниках Draft PR #319 виртуальная DLL получает временный каталог через
`GetTempPathA` **из контекста процесса-клиента** и пишет в файл
`SectorVVirtualCar.log`. Он не совпадает с исходным
`C:\Vida\System\Log\Diagnostics\VIDA.log`.

Важно: временная папка процесса VIDA может отличаться от `$env:TEMP`
PowerShell, особенно при разных учётных записях. Инструмент не пытается
угадать путь и не просматривает диски. Оба пути задаются явно.

## Запуск в той же гостевой Windows

Используйте проверенную копию исходников, содержащую этот инструмент
и соседний `audit_j2534_connect.py`. Сначала лично проверьте пути.

~~~powershell
$private = Join-Path $env:LOCALAPPDATA 'VirtualCar\OwnerPrivate\B3A45'
$vida = 'C:\Vida\System\Log\Diagnostics\VIDA.log'
$virtual = Join-Path $env:TEMP 'SectorVVirtualCar.log'
$tool = 'emulator\tools\audit_vida_j2534_session_window.py'
$baseline = Join-Path $private 'baseline.private.json'
$report = Join-Path $private 'delta-categorical.json'

py -3 $tool baseline --vida-log $vida --virtual-log $virtual --private-baseline $baseline
~~~

После контрольной точки владелец может отдельно выполнить **одну**
разрешённую проверку оригинальной VIDA в полностью изолированной
виртуальной среде: без автомобиля, физических адаптеров, SecurityAccess,
программирования или изменения конфигурации. Для этого должен быть
подтверждён выбор проверенного виртуального провайдера.

~~~powershell
py -3 $tool delta --vida-log $vida --virtual-log $virtual --private-baseline $baseline --output $report
~~~

Файлы baseline и отчёта создаются только заново, без перезаписи.
Повторный `delta` с новым именем отчёта учитывает **всё накопленное с
момента baseline**, а не отдельную новую сессию. Для другого запуска
нужна новая контрольная точка.

Проверяются SHA-256 исходных префиксов; обрезка, ротация и замена
исторических байтов отклоняются. Неполные строки на границах не
учитываются. Приращение более 16 МиБ на источник отклоняется.

## Пределы доказательств

- Счётчики `PassThru`, `GetScript`, `ReadVin` в оригинальном VIDA.log
  означают только наличие текстовых маркеров.
- События `PassThruOpen`, `Connect`, TX/RX в журнале VirtualCar более
  конкретны, но могут относиться к **другому процессу-клиенту**.
- Группы `iexplore`, `java`, `vidamonitor`, `other` не подтверждают
  идентичность PID или привязку к конкретному нажатию GUI.
- Локальный K-Line ACK с текстом `NO BUS/ECU TX/RX` не является ответом ECU.
  `PassThruReadMsgs -> delivered` может отражать синтетический RX.
- Отчёт не выводит исходные строки, VIN, байты CAN, PID, пути или хеши файлов.
  Оригинальные данные на компьютере владельца **не обезличиваются**.
- Успешная проверка не означает, что VIDA загрузила нужную DLL, приняла VIN
  или определила ECU XC90 V8 MY2009.

В отчёте статусы загрузки DLL, выбора провайдера VIDA, физического ECU RX
и принятия VIN остаются `false` до независимой проверки.
Не загружайте исходные логи и приватный baseline в GitHub.

Связанные блокеры: Issues #4 и #326.

## B3A47: безопасный выбор журнала по приватному manifest B3A46

Если B3A46 уже создал `candidate-paths.private.json`, не нужно копировать
сам путь `SectorVVirtualCar.log` в PowerShell. Локально проверьте manifest,
найдите подходящий элемент массива `candidates` с
`status=native_marker_in_tail` и выберите его **порядковый номер с 1**.
Не выбирайте путь только по счётчику: наличие маркера не доказывает,
что его создала оригинальная VIDA.

~~~powershell
$manifest = Join-Path $env:LOCALAPPDATA 'VirtualCar\OwnerPrivate\B3A46\candidate-paths.private.json'
$private = Join-Path $env:LOCALAPPDATA 'VirtualCar\OwnerPrivate\B3A47'
$vida = 'C:\Vida\System\Log\Diagnostics\VIDA.log'
$tool = 'emulator\tools\audit_vida_j2534_session_window.py'
$baseline = Join-Path $private 'baseline.private.json'
$report = Join-Path $private 'delta-categorical.json'

py -3 $tool baseline --vida-log $vida --candidate-manifest $manifest --candidate-index 1 --private-baseline $baseline
# После отдельной разрешённой read-only проверки оригинальной VIDA:
py -3 $tool delta --vida-log $vida --candidate-manifest $manifest --candidate-index 1 --private-baseline $baseline --output $report
~~~

Значение `1` здесь **пример**, а не рекомендация выбрать первый путь.
Если найдено несколько кандидатов, выбирайте только после локальной проверки.
При неверной схеме manifest, неподтверждённом маркере, подставленном имени
файла, неверном индексе или попытке совместить `--virtual-log` с manifest
аудитор откажет до создания baseline. Альтернативный режим
`--virtual-log` с явным путём сохранён.

Новый baseline создавайте для каждого независимого опыта; сам B3A47
не запускает VIDA, не подтверждает загрузку DLL и не устанавливает VIN.
