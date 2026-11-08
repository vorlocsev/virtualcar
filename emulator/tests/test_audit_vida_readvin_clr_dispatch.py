"""Eight completely synthetic, source-contract ReadVin XML dispatch regressions."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_readvin_clr_dispatch import audit_bytes, main


def xml(calls, reader=True):
    nodes = '<node nodeid="Output" class="X.VehicleIdentityOutput"/>'
    if reader:
        nodes += '<node nodeid="R" class="X.ReadVinComponent"/>'
    return ('<script><nodes>' + nodes + '</nodes><handlers>'
            '<eventhandler node="R">' + calls + '</eventhandler>'
            '</handlers></script>').encode()


def call(params='', disabled='', method='AddVIN'):
    return ('<call node="Output" method="' + method + '"' + disabled + '>'
            + params + '</call>')


def metrics(report, kind='add_vin'):
    return report['identity_method_classifications'][kind]


class ClrDispatchContractTests(unittest.TestCase):
    def test_01_node_property_reference_is_known_not_resolved_value(self):
        r = audit_bytes(xml(call('<parameter node="R" property="Result"/>')))
        g = metrics(r)
        self.assertEqual(g['source_node_property_parameters'], 1)
        self.assertEqual(g['source_node_ref_matching_readvin_node'], 1)
        self.assertEqual(g['constant_value_class_parameters'], 0)
        self.assertFalse(r['parameter_runtime_value_computed'])

    def test_02_no_node_attribute_means_constant_even_with_ref_source(self):
        r = audit_bytes(xml(call('<parameter value="PRIVATE_VIN_X" class="Text" ref="R" source="R"/>')))
        g = metrics(r)
        self.assertEqual(g['source_node_property_parameters'], 0)
        self.assertEqual(g['constant_value_class_parameters'], 1)
        self.assertEqual(g['constant_parameters_with_value_attribute'], 1)
        self.assertNotIn('PRIVATE_VIN_X', json.dumps(r))

    def test_03_disabled_presence_disables_even_when_false_literal(self):
        r = audit_bytes(xml(call() + call(disabled=' disabled="false"') + call(disabled=' disabled="true"')))
        g = metrics(r)
        self.assertEqual(g['parser_enabled_by_absent_disabled_attribute'], 1)
        self.assertEqual(g['parser_disabled_by_present_disabled_attribute'], 2)
        self.assertFalse(r['reflection_method_invoked'])

    def test_04_nested_or_wrapped_calls_are_not_parser_calls(self):
        r = audit_bytes(xml('<wrapper>' + call('<parameter node="R"/>') + '</wrapper>' +
                            '<call node="Output" method="Other">' + call() + '</call>'))
        self.assertEqual(r['direct_event_call_declarations'], 1)
        self.assertEqual(r['call_tags_not_direct_child_of_eventhandler_ignored'], 2)
        self.assertEqual(metrics(r)['direct_identity_call_declarations'], 0)

    def test_05_parameter_must_be_direct_child_of_call(self):
        r = audit_bytes(xml(call('<parameters><parameter node="R"/></parameters>'
                                 '<parameter node="R" property="Result"/>')))
        g = metrics(r)
        self.assertEqual(g['direct_parameter_declarations'], 1)
        self.assertEqual(g['non_direct_parameters_ignored'], 1)

    def test_06_empty_node_still_reference_branch_not_constant(self):
        r = audit_bytes(xml(call('<parameter node="" value="PRIVATE"/>')))
        g = metrics(r)
        self.assertEqual(g['source_node_property_parameters'], 1)
        self.assertEqual(g['source_node_ref_missing_or_empty'], 1)
        self.assertEqual(g['constant_value_class_parameters'], 0)
        self.assertNotIn('PRIVATE', json.dumps(r))

    def test_07_separate_x40_and_xml_injection_rejected(self):
        r = audit_bytes(xml(call('<parameter class="C" value="SERIAL"/>', method='SetX40Serial')))
        self.assertEqual(metrics(r)['direct_identity_call_declarations'], 0)
        self.assertEqual(metrics(r, 'set_x40_serial')['constant_value_class_parameters'], 1)
        self.assertFalse(r['vehicle_vin_accepted'])
        with self.assertRaises(ValueError):
            audit_bytes(xml(call('<parameter node="R"/>')).replace(b'<handlers>',
                        b'<!DOCTYPE script [<!ENTITY x "private">]><handlers>'))

    def test_08_cli_privacy_exclusive_output_and_bad_zip(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d, 'source.zip'), Path(d, 'summary.json')
            with zipfile.ZipFile(src, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('script.xml', xml(call('<parameter value="PRIVATE_DUMMY" class="X"/>')))
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(src), '--output', str(out)])
            raw = out.read_text()
            self.assertNotIn('PRIVATE_DUMMY', raw)
            self.assertNotIn(str(src), raw)
            self.assertFalse(json.loads(raw)['selected_readvin_script_runtime_verified'])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(src), '--output', str(out)])
            src.unlink()
            with zipfile.ZipFile(src, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('one.xml', b'<script/>')
                z.writestr('two.xml', b'<script/>')
            with self.assertRaises(ValueError):
                from audit_vida_readvin_clr_dispatch import _load_private_zip
                _load_private_zip(src)


if __name__ == '__main__':
    unittest.main()
