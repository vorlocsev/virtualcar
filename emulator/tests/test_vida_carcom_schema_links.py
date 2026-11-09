"""Eight synthetic tests for private VIDA metadata-only preflight boundaries."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools' / 'audit_vida_carcom_schema_links.py'
spec = importlib.util.spec_from_file_location('carcom_schema_preflight', TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class VidaCarcomSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        for name, tables in mod.TABLES.items():
            self.build(name, tables)

    def build(self, database, tables, override=None):
        path = self.folder / (database + '.sqlite')
        if path.exists():
            path.unlink()
        with contextlib.closing(sqlite3.connect(path)) as db:
            db.executescript('''
                CREATE TABLE _vida_meta ("key" TEXT, "value" TEXT);
                CREATE TABLE _vida_tables ("schema_name" TEXT, "table_name" TEXT, "rows_exported" INTEGER);
                CREATE TABLE _vida_columns ("schema_name" TEXT, "table_name" TEXT, "column_name" TEXT, "system_type_id" INTEGER);
                CREATE TABLE _vida_foreign_keys ("source" TEXT);
                CREATE TABLE "PRIVATE_VIN_PAYLOAD" ("dont_read" TEXT);
                INSERT INTO "PRIVATE_VIN_PAYLOAD" VALUES ('PRIVATE_VIN_S3CRET_1234567');
            ''')
            for key, val in [('schema_version', mod.EXPORT_SCHEMA),
                             ('source_database', database), ('scope', 'all_user_tables')]:
                db.execute('INSERT INTO _vida_meta VALUES (?,?)', (key,val))
            for tbl, cols in (tables or {"UnrelatedBaseData": ("id",)}).items():
                db.execute('INSERT INTO _vida_tables VALUES (?,?,?)', ('dbo', tbl, 7))
                for col in cols:
                    db.execute('INSERT INTO _vida_columns VALUES (?,?,?,?)', ('dbo',tbl,col,56))
            if override:
                override(db)
            db.commit()

    def test_01_all_fixed_names_and_edges_are_schema_only(self):
        result = mod.audit(self.folder)
        self.assertEqual(result['status'], 'schema_only')
        self.assertTrue(result['read_only'])
        self.assertEqual(len(result['edge_shape_candidates']), 6)
        self.assertTrue(all(x['column_shape_present'] for x in result['edge_shape_candidates']))
        self.assertFalse(result['xc90_v8_my2009_profile_verified'])
        self.assertFalse(result['getscript_runtime_selection_verified'])
        self.assertFalse(result['client_vin_accepted'])
        self.assertFalse(result['replay_approved'])
        self.assertNotIn('PRIVATE_VIN_S3CRET',json.dumps(result))
        self.assertEqual(result['databases']['CarCom']['fixed_tables']['T111_Service']['declared_rows'],7)

    def test_02_missing_table_is_not_assumed_present(self):
        self.build('CarCom', {'T111_Service':mod.TABLES['CarCom']['T111_Service']})
        r = mod.audit(self.folder)
        self.assertFalse(r['databases']['CarCom']['fixed_tables']['T122_Protocol']['present'])
        self.assertFalse(r['edge_shape_candidates'][0]['column_shape_present'])
        self.assertTrue(r['databases']['CarCom']['fixed_tables']['T111_Service']['present'])

    def test_03_missing_expected_column_fails_edge_gate(self):
        altered = dict(mod.TABLES['CarCom'])
        altered['T111_Service'] = ('id','service','mode')
        self.build('CarCom',altered)
        r=mod.audit(self.folder)
        self.assertFalse(r['edge_shape_candidates'][0]['column_shape_present'])
        self.assertIn('fkT122_Protocol',r['databases']['CarCom']['fixed_tables']['T111_Service']['expected_columns_missing'])

    def test_04_duplicate_target_across_schemas_rejected(self):
        def add(db):
            db.execute('INSERT INTO _vida_tables VALUES (?,?,?)',('other','T111_Service',3))
        self.build('CarCom',mod.TABLES['CarCom'],override=add)
        with self.assertRaises(mod.PreflightError): mod.audit(self.folder)

    def test_05_ambiguous_column_or_metadata_rejected(self):
        def dup(db):
            db.execute('INSERT INTO _vida_columns VALUES (?,?,?,?)',('dbo','T111_Service','ID',56))
        self.build('CarCom',mod.TABLES['CarCom'],override=dup)
        with self.assertRaises(mod.PreflightError): mod.audit(self.folder)
        def bad(db):
            db.execute('INSERT INTO _vida_meta VALUES (?,?)',('source_database','CarCom'))
        self.build('CarCom',mod.TABLES['CarCom'],override=bad)
        with self.assertRaises(mod.PreflightError): mod.audit(self.folder)

    def test_06_wrong_database_identity_and_missing_file_fail_closed(self):
        self.build('CarCom',mod.TABLES['CarCom'],override=lambda db:db.execute(
            "UPDATE _vida_meta SET value='DiagSwdlRepository' WHERE key='source_database'"))
        with self.assertRaises(mod.PreflightError): mod.audit(self.folder)
        self.build('CarCom',mod.TABLES['CarCom'])
        (self.folder/'BaseData.sqlite').unlink()
        with self.assertRaises(mod.PreflightError): mod.audit(self.folder)

    def test_07_unknown_column_and_table_not_exported(self):
        def add(db):
            db.execute('INSERT INTO _vida_tables VALUES (?,?,?)',('dbo','PERSONAL_CUSTOMER_RECORD_XYZ',1))
            db.execute('INSERT INTO _vida_columns VALUES (?,?,?,?)',('dbo','PERSONAL_CUSTOMER_RECORD_XYZ','MY_SECRET_NAME',165))
            db.execute('INSERT INTO _vida_columns VALUES (?,?,?,?)',('dbo','T111_Service','ORIGINAL_SECRET_PAYLOAD',165))
        self.build('CarCom',mod.TABLES['CarCom'],override=add)
        r=mod.audit(self.folder)
        result=json.dumps(r)
        self.assertNotIn('PERSONAL_CUSTOMER_RECORD_XYZ',result)
        self.assertNotIn('ORIGINAL_SECRET_PAYLOAD',result)
        self.assertNotIn('MY_SECRET_NAME',result)
        self.assertEqual(r['databases']['CarCom']['fixed_tables']['T111_Service']['column_count'],5)

    def test_08_cli_exclusive_new_output_and_no_source_modification(self):
        out=self.folder/'redacted.json'
        source=self.folder/'CarCom.sqlite'
        before=source.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(['--folder',str(self.folder),'--output',str(out)]),0)
            self.assertEqual(mod.main(['--folder',str(self.folder),'--output',str(out)]),2)
            self.assertEqual(mod.main(['--folder',str(self.folder),'--output',str(source)]),2)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(json.loads(out.read_text(encoding='utf-8'))['status'],'schema_only')
        self.assertNotIn('PRIVATE_VIN_S3CRET_1234567',out.read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()
