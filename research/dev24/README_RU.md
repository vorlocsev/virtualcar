# Virtual Car: passive LS-CAN decoder based on olegel/VolvoCan (reference)

Это **не** J2534 DLL, не CEM gateway, не эмулятор иммобилайзера. Это компактный, самостоятельный C99 модуль, который **только декодирует** пять наблюдаемых типов 29-битных CAN кадров на 125 кбит/с.

Источник для сверки:
- https://github.com/olegel/VolvoCan/blob/master/VolvoCan/include/VolvoCan.h
- https://github.com/olegel/VolvoCan/blob/master/doc/VolvoModules/cem.txt
- https://github.com/olegel/VolvoCan/blob/master/doc/VolvoModules/swm.txt
- https://github.com/olegel/VolvoCan/blob/master/doc/VolvoModules/ccm.txt
- https://github.com/olegel/VolvoCan/blob/master/doc/VolvoModules/rem.txt
- https://github.com/olegel/VolvoCan/blob/master/doc/VolvoModules/gearbox.txt

В исходнике автора — Arduino Nano + MCP2515, слушающий CAN_LS в режиме Listen Only, а не диагностический шлюз. Для XC90 V8 MY2009 совместимость именно этих CAN IDs ещё не проверена; сам автор предупреждает, что CAN module ID индивидуален для автомобиля.

## Сигналы и ограничения

| ID | Интерпретация в коде автора |
| --- | --- |
| 0x00617FF8 | CEM ignition: data[6] бит 7 = ключ присутствует, биты 6-5 = положение 0..3 |
| 0x03003028 | gearbox: data[2] & 7 = выбранная передача; сырые биты 4..6 сохранены без интерпретации |
| 0x00E00442 | CCM: data[2] bit 6 = кнопка парктроника; data[3] low nibble = датчик освещения |
| 0x01E0522E | REM: 31 - (data[3] >> 3) = код расстояния |
| 0x00404066 | SWM: кнопки в data[6] и инверсных data[7] |

Не добавлять без проверки периодические кадры для этих ID. Они не подтверждают диагностический запрос A6 (Reference 6660) и не устраняют отсутствие ответа A3/B9F0.

## Тестирование

```
gcc -std=c99 -Wall -Wextra -Werror -pedantic src/p2_ls_observer.c tests/test_ls.c -o test_ls && ./test_ls
clang -std=c99 -Wall -Wextra -Werror -pedantic src/p2_ls_observer.c tests/test_ls.c -o test_ls_clang && ./test_ls_clang
```

Без копирования исходников проекта, код написан заново по наблюдаемым сигналам, с проверкой длины, типа CAN ID и скорости. Оригинальный проект распространяется с LICENSE LGPL-2.1. При прямом заимствовании исходников проверяйте условия лицензии.
