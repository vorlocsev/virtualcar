#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
for cc in gcc clang; do
  "$cc" -std=c99 -pedantic -Wall -Wextra -Werror -Isrc \
     src/p2_cem_router.c src/p2_ls_observer.c src/p2_vehicle_core.c \
     tests/test_vehicle.c -o "build/test_${cc}"
  "build/test_${cc}"
done
clang -std=c99 -pedantic -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -Isrc \
     src/p2_cem_router.c src/p2_ls_observer.c src/p2_vehicle_core.c \
     tests/test_vehicle.c -o build/test_sanitized
ASAN_OPTIONS=detect_leaks=1 build/test_sanitized
