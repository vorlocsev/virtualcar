"""Synthetic SQLite catalog tests; no original VIDA data is distributed."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_original_vida_b9fb_probe as probe
sys.path.pop(0)

IDENTITY = json.dumps({'Vehicle': {'VIN': 'YV1CZ000290000001', 'ModelYear': 2009}})


class OriginalProbeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
        CREATE TABLE "dbo.T100_EcuVariant" (id, fkT101_Ecu, inheritance);
        CREATE TABLE "dbo.T101_Ecu" (id, identifier, name);
        CREATE TABLE "dbo.T141_Block" (id, fkT142_BlockType, fkT143_BlockDataType,
            name, fkT190_Text, offset, length, exclude, composite);
        CREATE TABLE "dbo.T142_BlockType" (id, identifier);
        CREATE TABLE "dbo.T144_BlockChild" (fkT100_EcuVariant, fkT141_Block_Child,
            fkT141_Block_Parent, SortOrder);
        CREATE TABLE "dbo.T150_BlockValue" (Id, fkT141_Block, SortOrder,
            CompareValue, Operator, fkT155_Scaling);
        CREATE TABLE "dbo.T155_Scaling" (id, definition);
        CREATE TABLE "dbo.T111_Service" (service, definition);
        INSERT INTO "dbo.T100_EcuVariant" VALUES (7,9,NULL);
        INSERT INTO "dbo.T101_Ecu" VALUES (9,'CEM','Synthetic CEM (D2)');
        INSERT INTO "dbo.T142_BlockType" VALUES (3,'BLOFF'),(8,'PARAM');
        INSERT INTO "dbo.T141_Block" VALUES (10,3,50,'Synthetic Section',0,0,704,0,0),
            (11,8,51,'VIN',0,88,136,0,0);
        INSERT INTO "dbo.T144_BlockChild" VALUES (7,10,1,0),(7,11,10,0);
        INSERT INTO "dbo.T150_BlockValue" VALUES (20,10,0,'0xFB',1,1),(21,11,0,'',0,1);
        INSERT INTO "dbo.T155_Scaling" VALUES (1,'x*1');
        INSERT INTO "dbo.T111_Service" VALUES ('B9','<request/><response/>');
        ''')
        self.profile = probe.lab.build_profile(IDENTITY)

    def build(self):
        return probe.snapshot(self.db, 7, self.profile, IDENTITY)

    def test_exact_profile_reconstruction_and_original_metadata(self):
        s = self.build()
        self.assertEqual(s['raw'][0], 0xFB)
        self.assertEqual(bytes(s['raw'][12:29]).decode(), s['expected_vin'])
        self.assertEqual(s['body_bytes'], 88)
        self.assertEqual(s['blocks'][0]['values'][0]['CompareValue'], '0xFB')
        self.assertEqual(s['selection'], 'explicit_catalog_comparison_not_vehicle_identification')

    def test_invalid_profile_rejected_before_catalog(self):
        self.profile = self.profile.replace('BaudRate = 125000', 'BaudRate = 500000')
        # Make the mutation independent of INI key casing.
        self.profile += '\n[Unexpected]\nEnabled=1\n'
        with self.assertRaises(ValueError): self.build()

    def test_non_d2_or_inherited_variant_rejected(self):
        self.db.execute('UPDATE "dbo.T101_Ecu" SET name=?', ('CEM GGD',))
        with self.assertRaises(ValueError): self.build()
        self.db.execute('UPDATE "dbo.T101_Ecu" SET name=?', ('CEM (D2)',))
        self.db.execute('UPDATE "dbo.T100_EcuVariant" SET inheritance=?', ('parent',))
        with self.assertRaises(ValueError): self.build()

    def test_no_fb_match_or_ambiguous_section_rejected(self):
        self.db.execute('UPDATE "dbo.T150_BlockValue" SET CompareValue=? WHERE Id=20', ('0xFA',))
        with self.assertRaises(ValueError): self.build()
        self.db.execute('UPDATE "dbo.T150_BlockValue" SET CompareValue=? WHERE Id=20', ('0xFB',))
        self.db.executescript('''INSERT INTO "dbo.T141_Block" SELECT 12,fkT142_BlockType,
            fkT143_BlockDataType,name,fkT190_Text,offset,length,exclude,composite
            FROM "dbo.T141_Block" WHERE id=10;
            INSERT INTO "dbo.T144_BlockChild" VALUES (7,12,1,1);
            INSERT INTO "dbo.T150_BlockValue" VALUES (22,12,0,'0xFB',1,1);''')
        with self.assertRaises(ValueError): self.build()

    def test_missing_scaling_or_vin_rejected(self):
        self.db.execute('DELETE FROM "dbo.T155_Scaling"')
        with self.assertRaises(ValueError): self.build()
        self.db.execute('INSERT INTO "dbo.T155_Scaling" VALUES (1,?)', ('x*1',))
        self.db.execute('UPDATE "dbo.T141_Block" SET name=? WHERE id=11', ('unknown',))
        with self.assertRaises(ValueError): self.build()

    def test_no_automatic_payload_extension_to_catalog_length(self):
        self.db.execute('UPDATE "dbo.T141_Block" SET length=784 WHERE id=10')
        s = self.build()
        self.assertEqual(s['section_bits'], 784)
        self.assertEqual(s['body_bytes'], 88)

    def test_private_exclusive_output_outside_git(self):
        with tempfile.TemporaryDirectory(suffix='-lab') as tmp:
            p = Path(tmp) / 'b9fb-parser-input.json'
            probe.write_private(p, self.build())
            with self.assertRaises(FileExistsError): probe.write_private(p, {})
            (Path(tmp) / '.git').mkdir()
            with self.assertRaises(ValueError): probe.write_private(p, {})


if __name__ == '__main__':
    unittest.main()
