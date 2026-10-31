#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p build
for CC in gcc clang; do
  "$CC" -std=c99 -Wall -Wextra -Werror -Wpedantic -O2 -Isrc src/p2_cem_router.c tests/test_cem_router.c -o "build/test_$CC"
  "build/test_$CC"
done
# Run runtime sanitizers as an independent memory check.
clang -std=c99 -Wall -Wextra -Werror -Wpedantic -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Isrc src/p2_cem_router.c tests/test_cem_router.c -o build/test_sanitized
build/test_sanitized
