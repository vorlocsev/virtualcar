"""Synthetic-only tests for unmasked VIDA original FK value comparisons."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_vida_original_schema_reader import TABLES, COLUMNS, INDEXES, FKS
import vida_original_schema_reader as schema_tool
import vida_original_fk_value_audit as audit_tool


def fixture():
    schema = schema_tool.parse('CarCom', TABLES, COLUMNS, INDEXES, FKS)
    tablemap = {(t['schema'], t['name']): t for t in schema['tables']}
    def make(table_name, rows):
        table = tablemap[('dbo', table_name)]
        return {
            'schema_version': 'virtualcar-vida-original-table-capture-v1',
            'source_database': 'CarCom', 'source_schema': 'dbo', 'source_table': table_name,
            'columns': [{key: c[key] for key in ('column_id','name','sql_type')}
                        for c in table['columns']],
            'rows': rows, 'row_count': len(rows),
            'original_names_and_driver_values_not_anonymized': True,
            'full_table_extracted_within_row_limit': True,
            'raw_sql_server_type_roundtrip_verified': False,
            'transactional_snapshot_verified': False,
            'same_installation_provenance_verified': False,
            'vehicle_runtime_verified': False,
        }
    source = make('T136_InitHw_Profile',
                  [[7, 'Вольво'], [8, 'Неизвестно'], [None, 'XC90']])
    target = make('T161_Profile',
                  [[7, 'Вольво'], [8, 'XC90']])
    return schema, source, target


def hashes():
    return {'schema': 'a'*64, 'tables': ['b'*64, 'c'*64]}


class OriginalFKValueTests(unittest.TestCase):
    def test_01_original_fk_and_key_values_not_anonymized(self):
        sch, source, target = fixture()
        report = audit_tool.audit(sch, [source,target], hashes())
        self.assertEqual(report['source_database'], 'CarCom')
        self.assertEqual(report['evaluated_fk_count'], 1)
        fk = report['fk_literal_value_comparisons'][0]
        self.assertEqual(fk['original_fk_name'], 'FK_InitHw_Profile ОРИГИНАЛ')
        self.assertEqual(fk['column_mapping'][1]['source'], 'fk_Profile_B')
        self.assertEqual(fk['literal_driver_value_matches'][0]['original_key_values'], [7,'Вольво'])
        self.assertEqual(fk['literal_driver_value_unmatched'][0]['original_key_values'], [8,'Неизвестно'])
        self.assertEqual(fk['source_null_key_rows'],1)
        self.assertEqual(fk['referenced_rows_examined'], 2)
        self.assertFalse(report['database_row_join_verified'])
        self.assertFalse(report['sql_collation_equivalence_verified'])
        self.assertFalse(report['d2_baud_verified'])
        self.assertIn('Вольво', json.dumps(report, ensure_ascii=False))

    def test_02_input_capture_order_does_not_change_matches(self):
        sch, s, t = fixture()
        a = audit_tool.audit(sch,[s,t],hashes())
        b = audit_tool.audit(sch,[t,s],hashes())
        self.assertEqual(a['fk_literal_value_comparisons'],b['fk_literal_value_comparisons'])

    def test_03_case_differences_are_not_false_sql_collation_proof(self):
        sch, s, t = fixture()
        s['rows'][0][1]='ВОЛЬВО'
        r=audit_tool.audit(sch,[s,t],hashes())
        fk=r['fk_literal_value_comparisons'][0]
        self.assertEqual(len(fk['literal_driver_value_matches']),0)
        self.assertEqual(len(fk['literal_driver_value_unmatched']),2)
        self.assertFalse(fk['sql_collation_equivalence_verified'])

    def test_04_duplicate_referenced_key_rejected(self):
        sch, s, t = fixture()
        t['rows'].append([7,'Вольво'])
        t['row_count'] += 1
        with self.assertRaisesRegex(audit_tool.OriginalFKError,'duplicate referenced key'):
            audit_tool.audit(sch,[s,t],hashes())

    def test_05_false_provenance_or_row_completion_rejected(self):
        sch, s, t = fixture()
        for field, value in (('full_table_extracted_within_row_limit',False),
                             ('transactional_snapshot_verified',True),
                             ('original_names_and_driver_values_not_anonymized',False)):
            bad=copy.deepcopy(s)
            bad[field]=value
            with self.subTest(field=field),self.assertRaises(audit_tool.OriginalFKError):
                audit_tool.audit(sch,[bad,t],hashes())
        sch['complete_catalog_visibility_verified']=True
        with self.assertRaises(audit_tool.OriginalFKError):
            audit_tool.audit(sch,[s,t],hashes())

    def test_06_modified_original_column_name_rejected(self):
        sch,s,t=fixture()
        s['columns'][0]['name']='FAKE_PRIVATE'
        with self.assertRaisesRegex(audit_tool.OriginalFKError,'disagrees'):
            audit_tool.audit(sch,[s,t],hashes())

    def test_07_wrong_database_or_duplicate_source_rejected(self):
        sch,s,t=fixture()
        t['source_database']='DiceTiming'
        with self.assertRaises(audit_tool.OriginalFKError):
            audit_tool.audit(sch,[s,t],hashes())
        with self.assertRaises(audit_tool.OriginalFKError):
            audit_tool.audit(sch,[s,s],hashes())

    def test_08_typed_values_are_not_lossily_string_coerced(self):
        sch,s,t=fixture()
        s['rows'][0][0]=True
        r=audit_tool.audit(sch,[s,t],hashes())
        self.assertEqual(len(r['fk_literal_value_comparisons'][0]['literal_driver_value_matches']),0)
        self.assertEqual(r['fk_literal_value_comparisons'][0]['literal_driver_value_unmatched'][0]['original_key_values'],[True,'Вольво'])

    def test_09_invalid_typed_binary_value_rejected(self):
        sch,s,t=fixture()
        s['rows'][0][1]={'format':'binary-base64','value':'AQ==','unexpected':'leak'}
        with self.assertRaises(audit_tool.OriginalFKError):
            audit_tool.audit(sch,[s,t],hashes())

    def test_10_no_declared_fk_does_not_invent_any(self):
        sch,s,t=fixture()
        sch['foreign_keys']=[]
        r=audit_tool.audit(sch,[s,t],hashes())
        self.assertEqual(r['evaluated_fk_count'],0)
        self.assertEqual(r['fk_literal_value_comparisons'],[])
        self.assertFalse(r['database_row_join_verified'])

    def test_11_cli_preserves_original_values_and_file_is_owner_local(self):
        sch,s,t=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            paths=[]
            for i, value in enumerate((sch,s,t)):
                p=root/f'original-{i}.json'
                p.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
                paths.append(p)
            out=root/'audit.json'
            args=['--schema-report',str(paths[0]),'--table-report',str(paths[1]),
                  '--table-report',str(paths[2]),'--output',str(out)]
            with contextlib.redirect_stdout(io.StringIO()) as stdout,contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit_tool.main(args),0)
                self.assertEqual(audit_tool.main(args),2)
            content=out.read_text()
            self.assertIn('Вольво',content)
            self.assertIn('FK_InitHw_Profile ОРИГИНАЛ',content)
            self.assertNotIn('Вольво',stdout.getvalue())
            report=json.loads(content)
            self.assertEqual(report['source_schema_sha256'],hashlib.sha256(paths[0].read_bytes()).hexdigest())
            if sys.platform!='win32':
                self.assertEqual(out.stat().st_mode & 0o777,0o600)

    def test_12_sha256_changes_when_input_bytes_change_no_claim_of_origin(self):
        sch,s,t=fixture()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.json'
            path.write_text(json.dumps(s,ensure_ascii=False),encoding='utf-8')
            a=audit_tool._read(path)[1]
            path.write_bytes(path.read_bytes()+b'\n')
            b=audit_tool._read(path)[1]
            self.assertNotEqual(a,b)
            r=audit_tool.audit(sch,[s,t],hashes())
            self.assertFalse(r['same_installation_provenance_verified'])

    def test_13_symlink_and_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            raw=root/'x.json'
            raw.write_text('{"a":1,"a":2}',encoding='utf-8')
            with self.assertRaisesRegex(audit_tool.OriginalFKError,'invalid original JSON'):
                audit_tool._read(raw)
            raw.write_text('{}',encoding='utf-8')
            link=root/'link.json'
            try:
                link.symlink_to(raw)
            except OSError:
                self.skipTest('symlinks unsupported')
            with self.assertRaisesRegex(audit_tool.OriginalFKError,'unsafe'):
                audit_tool._read(link)

    def test_14_incomplete_captured_rows_fail_before_join(self):
        sch,s,t=fixture()
        t['row_count']=1
        with self.assertRaisesRegex(audit_tool.OriginalFKError,'incomplete'):
            audit_tool.audit(sch,[s,t],hashes())


if __name__=='__main__':
    unittest.main()
