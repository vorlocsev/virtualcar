import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from scan_cem_ids import scan,SIZE
class ModuleIDScanTests(unittest.TestCase):
 def test_safe_scan_candidates(self):
  with tempfile.TemporaryDirectory() as d:
   b=bytearray(SIZE)
   b[0x4ff40:0x4ff48]=b'30728539'
   b[0x4ff68:0x4ff70]=b'30728541'
   b[0x472e:0x4738]=bytes.fromhex('f0 00 64 21 00 00 0f 00 07 00')
   b[0x4a00a:0x4a01b]=b'YV1CZ0002A0000001'
   file=Path(d)/'cem.bin';file.write_bytes(b)
   result=scan(file)
   self.assertEqual(result['ascii_number_candidates'][0]['number'],'30728539')
   self.assertEqual(result['f0_table_entries'][0]['address'],'0x00002164')
   self.assertNotIn('YV1CZ',str(result))
 def test_wrong_size_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'short.bin';p.write_bytes(b'hi')
   with self.assertRaises(ValueError): scan(p)
if __name__=='__main__':unittest.main()
