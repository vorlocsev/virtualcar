"""Synthetic-only original VIDA ResultGet candidate-route regressions."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_readvin_resultget_route import audit_xml, main


def xml(gets='<get property="Decoded"><getbyid key="101"/><getbyname key="VIN"/></get>',
        invalue='<property name="InValue" class="Response"/>',
        identity_param='<parameter node="Extractor" property="Decoded"/>',
        disabled='', reader_call=True, output_method='AddVIN', ext=''):
    reader = '<eventhandler node="Reader"><call node="Extractor" method="Execute"/></eventhandler>' if reader_call else ''
    output = ('<eventhandler node="Extractor"><call node="Identity" method="' + output_method + '"' +
              disabled + '>' + identity_param + '</call></eventhandler>')
    return ('<script><content><nodes>'
            '<node nodeid="Reader" class="X.ReadVinComponent"><property name="Result" class="Response"/></node>'
            '<node nodeid="Extractor" class="X.ResultGet">' + invalue + '<extension>' + gets + ext + '</extension></node>'
            '<node nodeid="Identity" class="X.VehicleIdentityOutput"/>'
            '</nodes><handlers>' + reader + output + '</handlers></content></script>').encode()


def counts(b):
    return audit_xml(b)['categorical_declarations']


class ReadVinResultGetRouteTests(unittest.TestCase):
    def test_01_candidate_two_event_route_is_not_runtime_identity(self):
        r = audit_xml(xml())
        c = r['categorical_declarations']
        self.assertEqual(c['resultget_node_declarations'], 1)
        self.assertEqual(c['getbyid_steps_with_key'], 1)
        self.assertEqual(c['getbyname_steps_with_key'], 1)
        self.assertEqual(c['identity_calls_using_declared_resultget_get_output'], 1)
        self.assertTrue(r['candidate_route_lexically_present'])
        self.assertFalse(r['vin_accepted_by_client'])
        self.assertFalse(r['resultget_setproperties_was_executed'])

    def test_02_no_explicit_readvin_event_does_not_make_complete_route(self):
        r = audit_xml(xml(reader_call=False))
        self.assertFalse(r['candidate_route_lexically_present'])
        self.assertEqual(r['categorical_declarations']['identity_calls_using_declared_resultget_get_output'], 1)

    def test_03_missing_declared_get_output_kept_separate(self):
        r = audit_xml(xml(identity_param='<parameter node="Extractor" property="Unknown"/>'))
        self.assertEqual(r['categorical_declarations']['identity_calls_using_resultget_non_get_property'], 1)
        self.assertFalse(r['candidate_route_lexically_present'])

    def test_04_identity_constant_cannot_masquerade_as_resultget_reference(self):
        r = audit_xml(xml(identity_param='<parameter value="Extractor" class="String"/>'))
        self.assertEqual(r['categorical_declarations']['identity_calls_using_resultget_property_reference'], 0)
        self.assertEqual(r['categorical_declarations']['other_identity_parameter_declarations'], 1)
        self.assertFalse(r['candidate_route_lexically_present'])

    def test_05_disabled_false_attribute_disables_identity_call(self):
        r = audit_xml(xml(disabled=' disabled="false"'))
        self.assertEqual(r['categorical_declarations']['identity_calls_using_declared_resultget_get_output'], 1)
        self.assertEqual(r['categorical_declarations']['enabled_identity_calls_using_resultget_get_output'], 0)
        self.assertFalse(r['candidate_route_lexically_present'])

    def test_06_wrapped_get_is_not_immediate_selector(self):
        r = audit_xml(xml(gets='<wrapper><get property="Decoded"><getbyid key="101"/></get></wrapper>'))
        self.assertEqual(r['categorical_declarations']['direct_get_property_declarations'], 0)
        self.assertFalse(r['candidate_route_lexically_present'])

    def test_07_class_or_invalue_missing_are_declared_only_not_false_runtime(self):
        r = audit_xml(xml(invalue=''))
        self.assertEqual(r['categorical_declarations']['resultget_nodes_with_direct_invalue_property'], 0)
        self.assertFalse(r['runtime_parameter_value_verified'])
        r = audit_xml(xml(invalue='<property name="InValue" class="String"/>'))
        self.assertEqual(r['categorical_declarations']['resultget_nodes_with_direct_invalue_class_response'], 0)

    def test_08_invalid_and_missing_getby_keys_do_not_leak_values(self):
        r = audit_xml(xml(gets='<get property="Decoded"><getbyid/><getbyname key=""/><other key="PRIVATE"/></get>'))
        self.assertEqual(r['categorical_declarations']['getbyid_steps_missing_key'], 1)
        self.assertEqual(r['categorical_declarations']['getbyname_steps_missing_key'], 1)
        self.assertEqual(r['categorical_declarations']['unrecognized_extension_selection_steps'], 1)
        self.assertNotIn('PRIVATE', json.dumps(r))

    def test_09_x40_separate_callback_not_vin(self):
        r = audit_xml(xml(output_method='SetX40Serial'))
        self.assertEqual(r['categorical_declarations']['identity_calls_using_declared_resultget_get_output'], 1)
        self.assertFalse(r['vin_accepted_by_client'])
        self.assertFalse(r['xc90_v8_my2009_verified'])

    def test_10_private_zip_safe_new_json_exclusive_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            z, out = p / 'private.zip', p / 'redacted.json'
            with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as f:
                f.writestr('synthetic.xml', xml().replace(b'VIN', b'SECRET_KEY'))
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(z), '--output', str(out)])
            data = out.read_text()
            self.assertNotIn('SECRET_KEY', data)
            self.assertNotIn(str(z), data)
            self.assertFalse(json.loads(data)['runtime_parameter_value_verified'])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(z), '--output', str(out)])


if __name__ == '__main__':
    unittest.main()
