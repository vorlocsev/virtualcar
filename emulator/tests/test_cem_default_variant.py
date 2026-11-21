"""Synthetic catalog regressions; no proprietary profile or ECU numbers."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_cem_default_variant as probe
sys.path.pop(0)


class DefaultVariantTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
            CREATE TABLE "dbo.T162_ProfileValue" (id,identifier,description,fkT163_ProfileValueType);
            INSERT INTO "dbo.T162_ProfileValue" VALUES
                (1,'model-code','SyntheticModel',1),(2,'2099','SyntheticYear',2),
                (3,'engine-code','SyntheticEngine',3);
            CREATE TABLE "dbo.T101_Ecu" (id,identifier,name,fkT102_EcuType);
            INSERT INTO "dbo.T101_Ecu" VALUES (1,'CEM','Synthetic (D2)',11);
            CREATE TABLE "dbo.T100_EcuVariant" (id,fkT101_Ecu,identifier);
            INSERT INTO "dbo.T100_EcuVariant" VALUES
                (101,1,'PRIVATE-SENTINEL-A'),(102,1,'PRIVATE-SENTINEL-B');
            CREATE TABLE "dbo.T160_DefaultEcuVariant" (fkT161_Profile,fkT100_EcuVariant);
        ''')
        self.db.execute('CREATE TABLE "dbo.T161_Profile" (id,identifier,folderLevel,' +
                        ','.join(probe.COLUMNS) + ')')
        self.profile(1, 8, (1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
        self.profile(2, 3, (1, 2))
        self.mapping(2, 101)

    def profile(self, row_id, level, values=()):
        values = tuple(values) + (None,) * (10 - len(values))
        self.db.execute('INSERT INTO "dbo.T161_Profile" VALUES (' + ','.join('?' * 13) + ')',
                        (row_id, 'private-profile-' + str(row_id), level, *values))

    def mapping(self, profile, variant):
        self.db.execute('INSERT INTO "dbo.T160_DefaultEcuVariant" VALUES (?,?)', (profile, variant))

    def audit(self):
        return probe.audit(self.db, 'SyntheticModel', '2099', 'SyntheticEngine')

    def test_all_profiles_and_redaction(self):
        self.profile(3, 9, (1, 2, 3))
        result = self.audit()
        self.assertEqual(result['profile_count'], 2)
        self.assertTrue(result['all_profiles_same_cem_d2_default'])
        text = json.dumps(result)
        self.assertNotIn('PRIVATE-SENTINEL', text)
        self.assertNotIn('private-profile', text)
        for key in ('runtime_profile_verified', 'oem_b9f0_verified', 'vida_gui_acceptance_verified'):
            self.assertFalse(result[key])

    def test_all_ten_dimensions_and_bilateral_nulls(self):
        selected = dict(zip(probe.COLUMNS, range(10)))
        candidate = dict(selected, folderLevel=3)
        self.assertTrue(probe.compatible(candidate, selected))
        for column in probe.COLUMNS:
            with self.subTest(column=column):
                mismatch = dict(candidate, **{column: 999})
                self.assertFalse(probe.compatible(mismatch, selected))
                self.assertTrue(probe.compatible(dict(candidate, **{column: None}), selected))
                self.assertTrue(probe.compatible(mismatch, dict(selected, **{column: None})))

    def test_excluded_root_and_missing_default(self):
        self.db.execute('UPDATE "dbo.T161_Profile" SET folderLevel=1 WHERE id=2')
        result = self.audit()
        self.assertEqual(result['profiles_without_default'], 1)
        self.assertFalse(result['all_profiles_same_cem_d2_default'])

    def test_priority_and_unordered_ties(self):
        self.profile(3, 4, (1, 2))
        self.mapping(3, 102)
        result = self.audit()
        self.assertTrue(result['all_profiles_same_cem_d2_default'])
        self.assertEqual(result['top_folder_level_counts'], {4: 1})
        self.db.execute('UPDATE "dbo.T161_Profile" SET folderLevel=3 WHERE id=3')
        result = self.audit()
        self.assertEqual(result['profiles_with_ambiguous_top_default'], 1)
        self.assertFalse(result['all_profiles_same_cem_d2_default'])
        self.db.execute('UPDATE "dbo.T160_DefaultEcuVariant" SET fkT100_EcuVariant=101')
        self.assertTrue(self.audit()['all_profiles_same_cem_d2_default'])

    def test_partial_profile_cannot_prove_consistency(self):
        self.profile(3, 8, (1, 2, 3, 999))
        self.profile(4, 5, (1, 2, None, 999))
        self.mapping(4, 102)
        result = self.audit()
        self.assertEqual(result['profile_count'], 2)
        self.assertEqual(result['distinct_top_variants'], 2)
        self.assertFalse(result['all_profiles_same_cem_d2_default'])

    def test_missing_and_ambiguous_selection_rejected(self):
        with self.assertRaises(ValueError):
            probe.audit(self.db, 'missing', '2099', 'SyntheticEngine')
        self.db.execute('INSERT INTO "dbo.T162_ProfileValue" VALUES (9,?,NULL,1)', ('SyntheticModel',))
        with self.assertRaises(ValueError):
            self.audit()
        self.db.execute('DELETE FROM "dbo.T162_ProfileValue" WHERE id=9')
        self.db.execute('UPDATE "dbo.T161_Profile" SET identifier=? WHERE id=2', ('private-profile-1',))
        with self.assertRaises(ValueError):
            self.audit()

    def test_other_ecu_in_same_function_group_not_filtered_away(self):
        self.db.execute('INSERT INTO "dbo.T101_Ecu" VALUES (2,?, ?,11)', ('OTHER', 'Synthetic other family'))
        self.db.execute('INSERT INTO "dbo.T100_EcuVariant" VALUES (103,2,?)', ('PRIVATE-SENTINEL-C',))
        self.profile(3, 4, (1, 2))
        self.mapping(3, 103)
        result = self.audit()
        self.assertEqual(result['profiles_with_other_top_ecu_family'], 1)
        self.assertFalse(result['all_profiles_same_cem_d2_default'])

    def test_cli_immutable_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.sqlite'
            self.db.commit()
            with contextlib.closing(sqlite3.connect(path)) as dest:
                self.db.backup(dest)
            original = path.read_bytes()
            argv = ['--carcom', str(path), '--model', 'SyntheticModel', '--year', '2099', '--engine', 'SyntheticEngine']
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(probe.main(argv), 0)
                self.assertEqual(probe.main(argv[:-1] + ['PRIVATE-SENTINEL-NOT-FOUND']), 2)
            self.assertEqual(path.read_bytes(), original)
            self.assertNotIn('PRIVATE-SENTINEL', out.getvalue() + err.getvalue())
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ['synthetic.sqlite'])


if __name__ == '__main__':
    unittest.main()
