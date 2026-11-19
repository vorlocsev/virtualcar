# Regression: CEM metadata classifier must see D2 CD/A6, without ECU responses.
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include "p2_cem_router.h"

#define ASSERT_TRUE(cond) do { \
  if (!(cond)) { fprintf(stderr, "failed line %d: %s\\n", __LINE__, #cond); return 1; } \
} while (0)

int main(void) {
  uint8_t a6_hs[8] = {0xCD, 0x50, 0xA6, 0x1A, 0x04, 0x01, 0, 0};
  uint8_t a6_ls[8] = {0xCD, 0x40, 0xA6, 0x1A, 0x04, 0x01, 0, 0};
  uint8_t b9fb[8] = {0xCB, 0x50, 0xB9, 0xFB, 0, 0, 0, 0};
  uint8_t b9f0[8] = {0xCB, 0x50, 0xB9, 0xF0, 0, 0, 0, 0};
  uint8_t a3[8] = {0xCF, 0x50, 0xA3, 0x02, 0x03, 0xA5, 0xA5, 0};
  p2_cem_result r;
  int checks = 0;

  r=p2_cem_classify(0x000FFFFE, 500000, a6_hs, 8);
  ASSERT_TRUE(r.request==P2_CEM_A6_REF6660_CANDIDATE &&
              r.decision==P2_CEM_NEED_EVIDENCE && r.is_expected_bus); checks++;
  r=p2_cem_classify(0x000FFFFE, 125000, a6_ls, 8);
  ASSERT_TRUE(r.request==P2_CEM_A6_REF6660_CANDIDATE &&
              r.decision==P2_CEM_NEED_EVIDENCE); checks++;
  r=p2_cem_classify(0x000FFFFE, 125000, a6_hs, 8);
  ASSERT_TRUE(r.request==P2_CEM_A6_REF6660_CANDIDATE &&
              r.decision==P2_CEM_ROUTE_MISMATCH); checks++;
  a6_hs[5] = 2;
  r=p2_cem_classify(0x000FFFFE, 500000, a6_hs, 8);
  ASSERT_TRUE(r.request==P2_CEM_UNKNOWN); checks++;
  a6_hs[5] = 1;
  a6_hs[0] = 0xCF;
  r=p2_cem_classify(0x000FFFFE, 500000, a6_hs, 8);
  ASSERT_TRUE(r.request==P2_CEM_UNKNOWN); checks++;
  a6_hs[0] = 0xCD;
  r=p2_cem_classify(0x000FFFFE, 500000, a6_hs, 7);
  ASSERT_TRUE(r.request==P2_CEM_UNKNOWN); checks++;
  r=p2_cem_classify(0x000FFFFD, 500000, a6_hs, 8);
  ASSERT_TRUE(r.request==P2_CEM_NOT_D2); checks++;
  r=p2_cem_classify(0x000FFFFE, 500000, b9fb, 8);
  ASSERT_TRUE(r.request==P2_CEM_B9FB && r.decision==P2_CEM_KEEP_EXISTING); checks++;
  r=p2_cem_classify(0x000FFFFE, 500000, b9f0, 8);
  ASSERT_TRUE(r.request==P2_CEM_B9F0 && r.decision==P2_CEM_NEED_EVIDENCE); checks++;
  r=p2_cem_classify(0x000FFFFE, 500000, a3, 8);
  ASSERT_TRUE(r.request==P2_CEM_A3_SHAPE && r.decision==P2_CEM_NEED_EVIDENCE); checks++;
  printf("PASS %d/10 D2 A6 metadata classifications\\n", checks);
  return 0;
}
'''


class D2A6ClassifierNativeTests(unittest.TestCase):
    def test_pure_c_d2_a6_classifier(self):
        compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler not available")
        with tempfile.TemporaryDirectory(prefix="p2-d2-a6-") as temp:
            temp_dir = pathlib.Path(temp)
            harness = temp_dir / "d2_a6_classifier_test.c"
            binary = temp_dir / "d2_a6_classifier_test"
            harness.write_text(HARNESS, encoding="utf-8")
            source = ROOT / "src" / "p2core"
            subprocess.run([
                compiler, "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror",
                "-I", str(source), str(harness), str(source / "p2_cem_router.c"),
                "-o", str(binary),
            ], check=True, capture_output=True, text=True, timeout=35)
            result = subprocess.run([str(binary)], check=True, capture_output=True,
                                    text=True, timeout=20)
            self.assertIn("PASS 10/10", result.stdout)


if __name__ == "__main__":
    unittest.main()
