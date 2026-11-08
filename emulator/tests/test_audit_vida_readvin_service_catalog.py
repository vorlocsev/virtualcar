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


    def test_18_matching_original_service_definition_wrapper_is_shape_only(self):
        source = xml()
        cat = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<?xml version="1.0" encoding="utf-8"?><service id="100"><definition/></service>'
        result = audit_sources(source, cat, definition)
        self.assertTrue(result['service_definition_xml_supplied'])
        self.assertTrue(result['single_readvin_with_matching_service_definition_root_candidate_present'])
        self.assertFalse(result['original_service_definition_runtime_verified'])
        self.assertFalse(result['accepted_vin_verified'])
        self.assertFalse(result['emulator_replay_approved'])

    def test_19_wrong_definition_id_and_no_definition_not_promoted(self):
        cat = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        self.assertFalse(audit_sources(xml(), cat)['single_readvin_with_matching_service_definition_root_candidate_present'])
        result = audit_sources(xml(), cat, b'<service id="101"><component/></service>')
        self.assertFalse(result['single_readvin_with_matching_service_definition_root_candidate_present'])

    def test_20_missing_protocol_column_or_value_blocks_definition_shape(self):
        definition = b'<service id="100"><definition/></service>'
        for cat in (b'id,service,mode\n100,ReadVin,0\n',
                    b'id,fkT122_Protocol,service,mode\n100,,ReadVin,0\n',
                    b'id,fkT122_Protocol,service,mode\n100,NULL,ReadVin,0\n',
                    b'id,fkT122_Protocol,service,mode\n100,-1,ReadVin,0\n'):
            with self.subTest(cat=cat):
                result = audit_sources(xml(), cat, definition)
                self.assertTrue(result['single_readvin_with_service_mode_metadata_candidate_present'])
                self.assertFalse(result['single_readvin_with_matching_service_definition_root_candidate_present'])

    def test_21_duplicate_rows_and_override_are_not_promoted(self):
        definition = b'<service id="100"><command/></service>'
        cat = b'id,fkT122_Protocol,service,mode\n100,7,X,0\n100,7,Y,0\n'
        self.assertFalse(audit_sources(xml(), cat, definition)['single_readvin_with_matching_service_definition_root_candidate_present'])
        setter = '<propertyhandler node="Input" name="Out"><set node="Reader" property="ServiceId"/></propertyhandler>'
        cat = b'id,fkT122_Protocol,service,mode\n100,7,X,0\n'
        self.assertFalse(audit_sources(xml(setter=setter), cat, definition)['single_readvin_with_matching_service_definition_root_candidate_present'])

    def test_22_definition_rejects_malformed_unsafe_and_empty_sources(self):
        cat = b'id,fkT122_Protocol,service,mode\n100,7,X,0\n'
        for definition in (b'', b'<service id="100"/>', b'<script id="100"><x/></script>',
                           b'<service id="0100"><x/></service>', b'<service><x/></service>',
                           b'<!DOCTYPE service [<!ENTITY vin "SENSITIVE">]><service id="100">&vin;</service>',
                           b'<service id="100"><x></service>'):
            with self.subTest(definition=definition[:30]):
                with self.assertRaises(ValueError):
                    audit_sources(xml(), cat, definition)

    def test_23_definition_depth_and_size_bounds(self):
        cat = b'id,fkT122_Protocol,service,mode\n100,7,X,0\n'
        deep = b'<service id="100">' + b'<x>' * 100 + b'</x>' * 100 + b'</service>'
        with self.assertRaises(ValueError):
            audit_sources(xml(), cat, deep)
        from audit_vida_readvin_service_catalog import MAX_SERVICE_DEFINITION_BYTES
        with self.assertRaises(ValueError):
            audit_sources(xml(), cat, b' ' * (MAX_SERVICE_DEFINITION_BYTES + 1))

    def test_24_private_definition_and_metadata_never_emitted(self):
        secret = 'SENSITIVE_SERVICE_XML_PAYLOAD'
        cat = b'id,fkT122_Protocol,service,mode\n100,707,SECRET_SVC,0\n'
        definition = ('<service id="100"><data>' + secret + '</data></service>').encode()
        result = json.dumps(audit_sources(xml(), cat, definition))
        self.assertTrue(json.loads(result)['single_readvin_with_matching_service_definition_root_candidate_present'])
        for token in (secret, '707', 'SECRET_SVC', '100', 'Reader'):
            self.assertNotIn(token, result)

    def test_25_optional_cli_service_definition_keeps_private_file_local(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            z = root / 'readvin.zip'
            cat = root / 'T111_Service.csv'
            definition = root / '100.xml'
            out = root / 'result.json'
            with zipfile.ZipFile(z, 'w', compression=zipfile.ZIP_DEFLATED) as a:
                a.writestr('script.xml', xml())
            cat.write_bytes(b'id,fkT122_Protocol,service,mode\n100,7,X,0\n')
            definition.write_bytes(b'<service id="100"><secret>SECRET_SERVICE_DEFINITION</secret></service>')
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(z), str(cat), '--service-definition', str(definition), '--output', str(out)])
            content = out.read_text(encoding='utf-8')
            self.assertTrue(json.loads(content)['single_readvin_with_matching_service_definition_root_candidate_present'])
            self.assertNotIn('SECRET_SERVICE_DEFINITION', content)
            self.assertNotIn(str(definition), content)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(z), str(cat), '--service-definition', str(definition), '--output', str(out)])


    def test_26_valid_t122_foreign_key_is_still_declaration_only(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        t122 = b'id,identifier\n7,D2\n9,P3\n'
        r = audit_sources(xml(), t111, definition, t122)
        self.assertTrue(r['protocol_catalog_csv_supplied'])
        self.assertTrue(r['single_readvin_with_matching_t122_protocol_reference_candidate_present'])
        self.assertFalse(r['actual_protocol_transport_verified'])
        self.assertFalse(r['j2534_tx_or_ecu_rx_verified'])
        self.assertFalse(r['accepted_vin_verified'])

    def test_27_missing_t122_key_does_not_match_even_with_definition(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        missing = b'id,identifier\n8,OTHER_PROTOCOL\n'
        r = audit_sources(xml(), t111, definition, missing)
        self.assertTrue(r['single_readvin_with_matching_service_definition_root_candidate_present'])
        self.assertFalse(r['single_readvin_with_matching_t122_protocol_reference_candidate_present'])
        self.assertFalse(audit_sources(xml(), t111, definition)[
            'single_readvin_with_matching_t122_protocol_reference_candidate_present'])

    def test_28_missing_service_definition_prevents_t122_promotion(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        t122 = b'id,identifier\n7,D2\n'
        r = audit_sources(xml(), t111, protocol_catalog_bytes=t122)
        self.assertFalse(r['single_readvin_with_matching_t122_protocol_reference_candidate_present'])
        self.assertTrue(r['protocol_catalog_csv_supplied'])

    def test_29_t122_requires_unique_id_and_identifier_headers(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        for raw in (b'id,other\n7,D2\n', b'identifier\nD2\n',
                    b'id,id,identifier\n7,7,D2\n', b''):
            with self.subTest(data=raw):
                with self.assertRaises(ValueError):
                    audit_sources(xml(), t111, definition, raw)

    def test_30_t122_duplicate_and_invalid_rows_fail_closed(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        for raw in (b'id,identifier\n7,D2\n7,OTHER\n',
                    b'id,identifier\n7,\n', b'id,identifier\ninvalid,D2\n',
                    b'id,identifier\n7\n', b'id,identifier\n7,D2,EXTRA\n',
                    b'id,identifier\n'):
            with self.subTest(data=raw):
                with self.assertRaises(ValueError):
                    audit_sources(xml(), t111, definition, raw)

    def test_31_t122_private_protocol_names_never_emitted(self):
        secret = 'SENSITIVE_T122_PROTOCOL_LABEL'
        t111 = b'id,fkT122_Protocol,service,mode\n100,7345,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        raw = ('id,identifier\n7345,' + secret + '\n').encode()
        r = json.dumps(audit_sources(xml(), t111, definition, raw))
        self.assertTrue(json.loads(r)['single_readvin_with_matching_t122_protocol_reference_candidate_present'])
        for token in (secret, '7345', 'ReadVin', '100'):
            self.assertNotIn(token, r)

    def test_32_optional_t122_cli_stays_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            z = root / 'readvin.zip'
            cat = root / 'T111_Service.csv'
            definition = root / '100.xml'
            protocols = root / 'T122_Protocol.csv'
            out = root / 'result.json'
            with zipfile.ZipFile(z, 'w', compression=zipfile.ZIP_DEFLATED) as a:
                a.writestr('script.xml', xml())
            cat.write_bytes(b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n')
            definition.write_bytes(b'<service id="100"><command/></service>')
            protocols.write_bytes(b'id,identifier\n7,PRIVATE_D2_NAME\n')
            args = [str(z), str(cat), '--service-definition', str(definition),
                    '--protocol-catalog', str(protocols), '--output', str(out)]
            with contextlib.redirect_stdout(io.StringIO()):
                main(args)
            saved = out.read_text(encoding='utf-8')
            self.assertTrue(json.loads(saved)['single_readvin_with_matching_t122_protocol_reference_candidate_present'])
            self.assertNotIn('PRIVATE_D2_NAME', saved)
            self.assertNotIn(str(protocols), saved)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)

    def test_33_t122_bounded_size_and_unsupported_format_rejected(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        for raw in (b'A' * (MAX_CSV_BYTES + 1),
                    b'id,identifier\n7,D2\x00\n',
                    b'id,identifier\n7,\xff\n'):
            with self.subTest(size=len(raw)):
                with self.assertRaises(ValueError):
                    audit_sources(xml(), t111, definition, raw)


    def test_34_t110_explicit_variant_and_service_join_is_static_only(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        t122 = b'id,identifier\n7,D2\n'
        definition = b'<service id="100"><command/></service>'
        t110 = b'id,fkT100_EcuVariant,fkT111_Service\n1,55,100\n2,56,100\n'
        r = audit_sources(xml(), t111, definition, t122, t110, '55')
        self.assertTrue(r['t110_service_ecu_variant_csv_supplied'])
        self.assertTrue(r['single_readvin_with_matching_t110_service_ecu_variant_candidate_present'])
        for name in ('actual_ecu_variant_identity_verified',
                     'actual_ecu_variant_service_support_verified',
                     'accepted_vin_verified', 'emulator_replay_approved'):
            self.assertFalse(r[name])

    def test_35_t110_wrong_variant_and_service_do_not_match(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        t122 = b'id,identifier\n7,D2\n'
        definition = b'<service id="100"><command/></service>'
        for entries, selected in ((b'55,101\n', '55'), (b'56,100\n', '55'),
                                  (b'55,101\n56,100\n', '55')):
            with self.subTest(selected=selected, entries=entries):
                t110 = b'fkT100_EcuVariant,fkT111_Service\n' + entries
                r = audit_sources(xml(), t111, definition, t122, t110, selected)
                self.assertTrue(r['single_readvin_with_matching_t122_protocol_reference_candidate_present'])
                self.assertFalse(r['single_readvin_with_matching_t110_service_ecu_variant_candidate_present'])

    def test_36_t110_requires_complete_source_chain(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        t122 = b'id,identifier\n7,D2\n'
        definition = b'<service id="100"><command/></service>'
        t110 = b'fkT100_EcuVariant,fkT111_Service\n55,100\n'
        for xml_source, catalog, service_def, protocols in (
                (xml(), t111, None, t122),
                (xml(), t111, definition, None),
                (xml(), b'id,service,mode\n100,ReadVin,0\n', definition, t122),
                (xml('<property name="ServiceId" class="Int" value="101"/>'),
                 t111, definition, t122)):
            with self.subTest(has_definition=service_def is not None):
                r = audit_sources(xml_source, catalog, service_def, protocols, t110, '55')
                self.assertFalse(r['single_readvin_with_matching_t110_service_ecu_variant_candidate_present'])

    def test_37_t110_rejects_duplicate_invalid_and_missing_links(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        t122 = b'id,identifier\n7,D2\n'
        rows = (b'55,100\n55,100\n', b'55,NULL\n', b'-1,100\n',
                b'0,100\n', b'55,0\n', b'55,100,EXTRA\n', b'55\n',
                b'INVALID,100\n')
        for row in rows:
            with self.subTest(row=row):
                t110 = b'fkT100_EcuVariant,fkT111_Service\n' + row
                with self.assertRaises(ValueError):
                    audit_sources(xml(), t111, definition, t122, t110, '55')

    def test_38_t110_rejects_ambiguous_headers_and_empty_table(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        t122 = b'id,identifier\n7,D2\n'
        bad = (b'', b'fkT100_EcuVariant\n55\n',
               b'fkT111_Service\n100\n',
               b'fkT100_EcuVariant,fkT111_Service,fkT111_Service\n55,100,100\n',
               b'fkT100_EcuVariant,fkT111_Service\n',
               b'fkT100_EcuVariant,fkT111_Service\n55,100\x00\n',
               b'fkT100_EcuVariant,fkT111_Service\n55,\xff\n',
               b'fkT100_EcuVariant,fkT111_Service\n55,100\n' + b' ' * (MAX_CSV_BYTES + 1))
        for t110 in bad:
            with self.subTest(length=len(t110)):
                with self.assertRaises(ValueError):
                    audit_sources(xml(), t111, definition, t122, t110, '55')

    def test_39_t110_requires_both_catalog_and_canonical_variant_id(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><command/></service>'
        t122 = b'id,identifier\n7,D2\n'
        t110 = b'fkT100_EcuVariant,fkT111_Service\n55,100\n'
        with self.assertRaises(ValueError):
            audit_sources(xml(), t111, definition, t122, t110)
        with self.assertRaises(ValueError):
            audit_sources(xml(), t111, definition, t122, selected_ecu_variant_id='55')
        for selected in ('055', '0', '-55', '0x37', '', '2147483648', 55, None):
            with self.subTest(selected=selected):
                with self.assertRaises(ValueError):
                    audit_sources(xml(), t111, definition, t122, t110, selected)

    def test_40_t110_private_ecu_and_service_ids_never_reported(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        definition = b'<service id="100"><secret>PRIVATE_XML</secret></service>'
        t122 = b'id,identifier\n7,PRIVATE_PROTOCOL\n'
        t110 = b'fkT100_EcuVariant,fkT111_Service,annotation\n7345,100,PRIVATE_ECU_VARIANT\n'
        result = json.dumps(audit_sources(xml(), t111, definition, t122, t110, '7345'))
        self.assertTrue(json.loads(result)['single_readvin_with_matching_t110_service_ecu_variant_candidate_present'])
        for token in ('7345', 'PRIVATE_ECU_VARIANT', 'PRIVATE_PROTOCOL', 'PRIVATE_XML', '100'):
            self.assertNotIn(token, result)

    def test_41_t110_optional_cli_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            z = folder / 'readvin.zip'
            catalog = folder / 'T111_Service.csv'
            definition = folder / '100.xml'
            protocol = folder / 'T122_Protocol.csv'
            t110 = folder / 'T110_Service_EcuVariant.csv'
            result = folder / 'redacted.json'
            with zipfile.ZipFile(z, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('script.xml', xml())
            catalog.write_bytes(b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n')
            definition.write_bytes(b'<service id="100"><command/></service>')
            protocol.write_bytes(b'id,identifier\n7,PRIVATE_PROTOCOL_NAME\n')
            t110.write_bytes(b'fkT100_EcuVariant,fkT111_Service\n55,100\n')
            args = [str(z), str(catalog), '--service-definition', str(definition),
                    '--protocol-catalog', str(protocol), '--t110-catalog', str(t110),
                    '--ecu-variant-id', '55', '--output', str(result)]
            with contextlib.redirect_stdout(io.StringIO()):
                main(args)
            saved = result.read_text(encoding='utf-8')
            self.assertTrue(json.loads(saved)['single_readvin_with_matching_t110_service_ecu_variant_candidate_present'])
            for secret in ('PRIVATE_PROTOCOL_NAME', '55', str(t110), str(definition)):
                self.assertNotIn(secret, saved)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)


    def test_42_t100_t160_t161_profile_join_stays_static_only(self):
        t111 = b'id,fkT122_Protocol,service,mode\n100,7,ReadVin,0\n'
        t122 = b'id,identifier\n7,D2\n'
        definition = b'<service id="100"><command/></service>'
        t110 = b'fkT100_EcuVariant,fkT111_Service\n55,100\n'
        t100 = b'id,identifier,fkT101_Ecu\n55,PRIVATE_VARIANT,99\n'
        t160 = b'fkT161_Profile,fkT100_EcuVariant\n10,55\n'
        t161 = b'id,identifier\n10,PROFILE_XC90_SYNTHETIC\n'
        r = audit_sources(xml(), t111, definition, t122, t110, '55',
                          t100, t160, t161, 'PROFILE_XC90_SYNTHETIC')
        self.assertTrue(r['ecu_profile_catalogs_supplied'])
        self.assertTrue(r['single_readvin_with_selected_default_ecu_variant_profile_candidate_present'])
        for key in ('selected_profile_is_target_vehicle_verified',
                    'actual_ecu_variant_identity_verified',
                    'actual_ecu_variant_service_support_verified',
                    'accepted_vin_verified', 'emulator_replay_approved'):
            self.assertFalse(r[key])

    def test_43_t100_missing_selected_variant_prevents_profile_join(self):
        base = (xml(), b'id,fkT122_Protocol,service,mode\n100,7,X,0\n',
                b'<service id="100"><command/></service>', b'id,identifier\n7,D2\n',
                b'fkT100_EcuVariant,fkT111_Service\n55,100\n', '55')
        t100 = b'id,identifier,fkT101_Ecu\n56,DIFFERENT,99\n'
        t160 = b'fkT161_Profile,fkT100_EcuVariant\n10,55\n'
        t161 = b'id,identifier\n10,PROFILE_MATCH\n'
        r = audit_sources(*base, t100, t160, t161, 'PROFILE_MATCH')
        self.assertTrue(r['single_readvin_with_matching_t110_service_ecu_variant_candidate_present'])
        self.assertFalse(r['single_readvin_with_selected_default_ecu_variant_profile_candidate_present'])

    def test_44_wrong_profile_and_wrong_t160_relation_are_not_promoted(self):
        base = (xml(), b'id,fkT122_Protocol,service,mode\n100,7,X,0\n',
                b'<service id="100"><command/></service>', b'id,identifier\n7,D2\n',
                b'fkT100_EcuVariant,fkT111_Service\n55,100\n', '55',
                b'id,identifier,fkT101_Ecu\n55,SYNTHETIC_VARIANT,99\n')
        t161 = b'id,identifier\n10,PROFILE_A\n11,PROFILE_B\n'
        for t160, identifier in (
            (b'fkT161_Profile,fkT100_EcuVariant\n10,55\n', 'PROFILE_B'),
            (b'fkT161_Profile,fkT100_EcuVariant\n10,56\n', 'PROFILE_A'),
            (b'fkT161_Profile,fkT100_EcuVariant\n10,55\n', 'UNKNOWN_PROFILE')):
            with self.subTest(identifier=identifier):
                r = audit_sources(*base, t160, t161, identifier)
                self.assertFalse(r['single_readvin_with_selected_default_ecu_variant_profile_candidate_present'])

    def test_45_profile_catalog_arguments_must_be_complete(self):
        base = (xml(), b'id,fkT122_Protocol,service,mode\n100,7,X,0\n',
                b'<service id="100"><command/></service>', b'id,identifier\n7,D2\n',
                b'fkT100_EcuVariant,fkT111_Service\n55,100\n', '55')
        t100 = b'id,identifier,fkT101_Ecu\n55,SYNTHETIC_VARIANT,99\n'
        t160 = b'fkT161_Profile,fkT100_EcuVariant\n10,55\n'
        t161 = b'id,identifier\n10,PROFILE_A\n'
        for extras in ((t100, None, t161, 'PROFILE_A'),
                       (t100, t160, None, 'PROFILE_A'),
                       (t100, t160, t161, None),
                       (t100, t160, t161, ''),
                       (t100, t160, t161, 'A\nB')):
            with self.subTest(mask=[v is None for v in extras]):
                with self.assertRaises(ValueError):
                    audit_sources(*base, *extras)
        with self.assertRaises(ValueError):
            audit_sources(*base[:4], None, None, t100, t160, t161, 'PROFILE_A')

    def test_46_t100_malformed_and_duplicate_rows_fail_closed(self):
        base = (xml(), b'id,fkT122_Protocol,service,mode\n100,7,X,0\n',
                b'<service id="100"><command/></service>', b'id,identifier\n7,D2\n',
                b'fkT100_EcuVariant,fkT111_Service\n55,100\n', '55')
        t160 = b'fkT161_Profile,fkT100_EcuVariant\n10,55\n'
        t161 = b'id,identifier\n10,PROFILE_A\n'
        for t100 in (b'id,identifier\n55,X\n', b'id,identifier,fkT101_Ecu\n55,X,99\n55,Y,99\n',
                     b'id,identifier,fkT101_Ecu\n55,,99\n',
                     b'id,identifier,fkT101_Ecu\n55,X,\n',
                     b'id,identifier,fkT101_Ecu\ninvalid,X,99\n',
                     b'id,identifier,fkT101_Ecu\n55,X,0\n',
                     b'id,identifier,fkT101_Ecu\n'):
            with self.subTest(t100=t100[:40]):
                with self.assertRaises(ValueError):
                    audit_sources(*base, t100, t160, t161, 'PROFILE_A')

    def test_47_t161_duplicate_identifier_and_ambiguous_id_fail_closed(self):
        base = (xml(), b'id,fkT122_Protocol,service,mode\n100,7,X,0\n',
                b'<service id="100"><command/></service>', b'id,identifier\n7,D2\n',
                b'fkT100_EcuVariant,fkT111_Service\n55,100\n', '55',
                b'id,identifier,fkT101_Ecu\n55,X,99\n',
                b'fkT161_Profile,fkT100_EcuVariant\n10,55\n')
        for t161 in (b'id,identifier\n10,PROFILE_A\n11,PROFILE_A\n',
                     b'id,identifier\n10,PROFILE_A\n10,PROFILE_B\n',
                     b'id,identifier\n10,\n',
                     b'id,id,identifier\n10,10,PROFILE_A\n',
                     b'id,identifier\n'):
            with self.subTest(t161=t161[:35]):
                with self.assertRaises(ValueError):
                    audit_sources(*base, t161, 'PROFILE_A')

    def test_48_t160_ambiguous_and_invalid_links_fail_closed(self):
        base = (xml(), b'id,fkT122_Protocol,service,mode\n100,7,X,0\n',
                b'<service id="100"><command/></service>', b'id,identifier\n7,D2\n',
                b'fkT100_EcuVariant,fkT111_Service\n55,100\n', '55',
                b'id,identifier,fkT101_Ecu\n55,X,99\n')
        t161 = b'id,identifier\n10,PROFILE_A\n'
        for t160 in (b'fkT161_Profile\n10\n',
                     b'fkT161_Profile,fkT100_EcuVariant\n10,55\n10,55\n',
                     b'fkT161_Profile,fkT100_EcuVariant\n10,0\n',
                     b'fkT161_Profile,fkT100_EcuVariant\n10,INVALID\n',
                     b'fkT161_Profile,fkT100_EcuVariant\n10,55,EXTRA\n',
                     b'fkT161_Profile,fkT100_EcuVariant\n'):
            with self.subTest(t160=t160[:45]):
                with self.assertRaises(ValueError):
                    audit_sources(*base, t160, t161, 'PROFILE_A')

    def test_49_profile_input_privacy_and_optional_cli(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            z = root / 'selected-readvin.zip'
            t111 = root / 'T111_Service.csv'
            definition = root / '100.xml'
            t122 = root / 'T122_Protocol.csv'
            t110 = root / 'T110_Service_EcuVariant.csv'
            t100 = root / 'T100_EcuVariant.csv'
            t160 = root / 'T160_DefaultEcuVariant.csv'
            t161 = root / 'T161_Profile.csv'
            output = root / 'private-summary.json'
            with zipfile.ZipFile(z, 'w', compression=zipfile.ZIP_DEFLATED) as a:
                a.writestr('readvin.xml', xml())
            t111.write_bytes(b'id,fkT122_Protocol,service,mode\n100,7,X,0\n')
            definition.write_bytes(b'<service id="100"><command/></service>')
            t122.write_bytes(b'id,identifier\n7,SECRET_PROTOCOL_NAME\n')
            t110.write_bytes(b'fkT100_EcuVariant,fkT111_Service\n55,100\n')
            t100.write_bytes(b'id,identifier,fkT101_Ecu\n55,SECRET_ECU_VARIANT,99\n')
            t160.write_bytes(b'fkT161_Profile,fkT100_EcuVariant\n10,55\n')
            t161.write_bytes(b'id,identifier\n10,SECRET_PROFILE_IDENTIFIER\n')
            argv = [str(z), str(t111), '--service-definition', str(definition),
                    '--protocol-catalog', str(t122), '--t110-catalog', str(t110),
                    '--ecu-variant-id', '55', '--t100-catalog', str(t100),
                    '--t160-catalog', str(t160), '--t161-catalog', str(t161),
                    '--profile-identifier', 'SECRET_PROFILE_IDENTIFIER',
                    '--output', str(output)]
            with contextlib.redirect_stdout(io.StringIO()):
                main(argv)
            text = output.read_text(encoding='utf-8')
            self.assertTrue(json.loads(text)['single_readvin_with_selected_default_ecu_variant_profile_candidate_present'])
            for secret in ('SECRET_PROFILE_IDENTIFIER', 'SECRET_ECU_VARIANT',
                           'SECRET_PROTOCOL_NAME', '55', '100', str(t161)):
                self.assertNotIn(secret, text)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(argv)


if __name__ == '__main__':
    unittest.main()
