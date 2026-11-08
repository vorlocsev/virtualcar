"""Entirely synthetic and privacy-checked static VIDA service catalog tests."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_readvin_service_catalog import audit_sources, main, MAX_CSV_BYTES


def xml(props='<property name="ServiceId" class="Int" value="100"/>', setter='', nodes=''):
    return (f'<script><content><nodes><node nodeid="Reader" class="X.ReadVinComponent">'
            f'{props}</node>{nodes}</nodes><handlers><eventhandler node="Reader" '
            f'name="OnPositiveResponse"/>{setter}</handlers></content></script>').encode()


def csv(rows='100,ReadVin,0\n'):
    return ('id,service,mode\n' + rows).encode()


class ServiceCatalogTests(unittest.TestCase):
    def test_01_unique_static_candidate_is_never_runtime_proof(self):
        r = audit_sources(xml(), csv())
        self.assertTrue(r['static_unique_catalog_candidate_present'])
        self.assertEqual(r['counts']['literal_ids_with_unique_catalog_row_no_declared_override'], 1)
        for key in ('same_installation_provenance_verified',
                    'original_getscript_runtime_selection_verified',
                    'runtime_serviceid_or_propertyhandler_value_verified',
                    'accepted_vin_verified', 'emulator_replay_approved'):
            self.assertFalse(r[key])

    def test_02_missing_catalog_row(self):
        r = audit_sources(xml(), csv('101,Other,0\n'))
        self.assertEqual(r['counts']['literal_ids_without_catalog_row'], 1)
        self.assertFalse(r['static_unique_catalog_candidate_present'])

    def test_03_duplicate_catalog_id_is_ambiguous(self):
        r = audit_sources(xml(), csv('100,One,0\n100,Two,1\n'))
        self.assertEqual(r['counts']['catalog_duplicate_numeric_id_rows'], 1)
        self.assertEqual(r['counts']['literal_ids_with_duplicate_catalog_rows'], 1)
        self.assertFalse(r['static_unique_catalog_candidate_present'])

    def test_04_enabled_propertyhandler_blocks_literal_promotion(self):
        setter = '<propertyhandler node="Source" name="Output"><set node="Reader" property="ServiceId"/></propertyhandler>'
        r = audit_sources(xml(setter=setter), csv())
        self.assertEqual(r['counts']['readvin_nodes_with_enabled_serviceid_setter'], 1)
        self.assertEqual(r['counts']['literal_ids_with_declared_override'], 1)
        self.assertFalse(r['static_unique_catalog_candidate_present'])
        setter = setter.replace('property="ServiceId"/>', 'property="ServiceId" disabled="false"/>')
        r = audit_sources(xml(setter=setter), csv())
        self.assertTrue(r['static_unique_catalog_candidate_present'])

    def test_05_literal_parser_excludes_non_int_dynamic_and_ambiguous(self):
        for property_xml in (
            '<property name="ServiceId" class="String" value="100"/>',
            '<property name="ServiceId" class="Int"/>',
            '<property name="ServiceId" class="Int" value="0x64"/>',
            '<property name="ServiceId" class="Int" value="0100"/>',
            '<property name="ServiceId" class="Int" value="2147483648"/>',
        ):
            with self.subTest(p=property_xml):
                r = audit_sources(xml(property_xml), csv())
                self.assertFalse(r['static_unique_catalog_candidate_present'])
                self.assertEqual(r['counts']['readvin_nodes_with_missing_or_nonliteral_serviceid'], 1)
        r = audit_sources(xml('<property name="ServiceId" class="Int" value="100"/>' * 2), csv())
        self.assertEqual(r['counts']['readvin_nodes_with_duplicate_serviceid_properties'], 1)
        self.assertFalse(r['static_unique_catalog_candidate_present'])

    def test_06_invalid_rows_headers_and_xml_duplicates(self):
        report = audit_sources(xml(), csv('garbage,X,0\n100,A,0\n'))
        self.assertEqual(report['counts']['catalog_invalid_id_rows'], 1)
        with self.assertRaises(ValueError):
            audit_sources(xml(), b'service,mode\nFoo,0\n')
        with self.assertRaises(ValueError):
            audit_sources(xml(nodes='<node nodeid="Reader" class="X.ReadVinComponent"/>'), csv())
        with self.assertRaises(ValueError):
            audit_sources(b'<!DOCTYPE script [<!ENTITY x "SECRET">]>' + xml(), csv())

    def test_07_privacy_does_not_emit_ids_vin_can_or_csv_rows(self):
        source = xml('<property name="ServiceId" class="Int" value="19991"/>'
                     '<property name="Identifier" class="String" value="SENSITIVE_VIN"/>')
        report = json.dumps(audit_sources(source, csv('19991,SENSITIVE_MODE,CFB9FB\n')))
        for secret in ('19991', 'SENSITIVE_VIN', 'SENSITIVE_MODE', 'CFB9FB', 'Reader'):
            self.assertNotIn(secret, report)

    def test_08_cli_exclusive_output_no_private_path_or_content(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            z = root / 'readvin.zip'
            catalog = root / 'T111_Service.csv'
            out = root / 'report.json'
            with zipfile.ZipFile(z, 'w', compression=zipfile.ZIP_DEFLATED) as a:
                a.writestr('script.xml', xml())
            catalog.write_bytes(csv('100,SENSITIVE_ROW,0\n'))
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(z), str(catalog), '--output', str(out)])
            value = out.read_text(encoding='utf8')
            self.assertTrue(json.loads(value)['static_unique_catalog_candidate_present'])
            for secret in (str(z), str(catalog), 'SENSITIVE_ROW'):
                self.assertNotIn(secret, value)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(z), str(catalog), '--output', str(out)])

    def test_09_limits_and_csv_structure_fail_closed(self):
        with self.assertRaises(ValueError):
            audit_sources(xml(), b'A' * (MAX_CSV_BYTES + 1))
        with self.assertRaises(ValueError):
            audit_sources(xml(), b'id,service\n100,A,extra\n')
        with self.assertRaises(ValueError):
            audit_sources(xml(), b'id,id\n100,100\n')


    def test_10_t111_schema_requires_service_and_mode_headers(self):
        for raw in (b'id,mode\n100,0\n', b'id,service\n100,ReadVin\n',
                    b'id,service,mode,mode\n100,ReadVin,0,1\n'):
            with self.subTest(csv=raw):
                with self.assertRaises(ValueError):
                    audit_sources(xml(), raw)

    def test_11_incomplete_csv_row_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_sources(xml(), b'id,service,mode\n100,ReadVin\n')
        with self.assertRaises(ValueError):
            audit_sources(xml(), b'id,service,mode\n100,ReadVin,0,extra\n')

    def test_12_complete_metadata_is_shape_only(self):
        r = audit_sources(xml(), csv('100,ReadVin,0\n'))
        self.assertTrue(r['single_readvin_with_service_mode_metadata_candidate_present'])
        self.assertEqual(r['counts']['literal_ids_with_unique_catalog_row_and_nonempty_service_mode'], 1)
        for f in ('carcom_service_definition_or_mode_verified', 'same_installation_provenance_verified',
                  'original_getscript_runtime_selection_verified', 'accepted_vin_verified',
                  'emulator_replay_approved'):
            self.assertFalse(r[f])

    def test_13_blank_service_or_mode_stays_nonpromotable(self):
        for row in ('100,,0\n', '100,ReadVin,\n', '100, ,  \n'):
            with self.subTest(row=row):
                r = audit_sources(xml(), csv(row))
                self.assertTrue(r['static_unique_catalog_candidate_present'])
                self.assertFalse(r['single_readvin_with_service_mode_metadata_candidate_present'])
                self.assertEqual(r['counts']['catalog_rows_with_empty_service_or_mode'], 1)

    def test_14_multiple_readvin_nodes_not_one_static_service(self):
        extra = '<node nodeid="Reader2" class="X.ReadVinComponent">' + (
            '<property name="ServiceId" class="Int" value="101"/></node>')
        r = audit_sources(xml(nodes=extra), csv('100,First,0\n101,Second,0\n'))
        self.assertEqual(r['counts']['readvin_nodes'], 2)
        self.assertEqual(r['counts']['literal_ids_with_unique_catalog_row_and_nonempty_service_mode'], 2)
        self.assertTrue(r['static_unique_catalog_candidate_present'])
        self.assertFalse(r['single_readvin_with_service_mode_metadata_candidate_present'])

    def test_15_dynamic_setter_blocks_complete_metadata_candidate(self):
        setter = '<propertyhandler node="Input" name="Result">' + (
            '<set node="Reader" property="ServiceId"/></propertyhandler>')
        r = audit_sources(xml(setter=setter), csv())
        self.assertFalse(r['single_readvin_with_service_mode_metadata_candidate_present'])
        self.assertEqual(r['counts']['literal_ids_with_declared_override'], 1)

    def test_16_excessively_deep_xml_fails_closed(self):
        raw = xml().replace(b'</content>', b'<x>' * 100 + b'</x>' * 100 + b'</content>')
        with self.assertRaises(ValueError):
            audit_sources(raw, csv())

    def test_17_metadata_values_never_appear_in_report(self):
        secret = 'SENSITIVE_SERVICE_METADATA_TOKEN'
        report = json.dumps(audit_sources(xml(), csv('100,' + secret + ',0\n')))
        self.assertTrue(json.loads(report)['single_readvin_with_service_mode_metadata_candidate_present'])
        self.assertNotIn(secret, report)
        self.assertNotIn('ReadVin', report)


if __name__ == '__main__':
    unittest.main()
