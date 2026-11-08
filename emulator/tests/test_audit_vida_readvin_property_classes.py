"""8 synthetic original-IL property class, privacy, parsing regressions."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_readvin_property_classes import audit_xml, main, PROPERTY_CLASSES


def build(node_props='<property name="Result" class="String" value="PRIVATE"/>',
          params='<parameter node="Reader" property="Result"/>',
          extra='', disabled='', wrapped=False):
    call = '<call node="Output" method="AddVIN"' + disabled + '>' + params + '</call>'
    if wrapped:
        call = '<wrap>' + call + '</wrap>'
    return ('<script><content><nodes>'
            '<node nodeid="Reader" class="X.ReadVinComponent">' + node_props + '</node>'
            '<node nodeid="Output" class="X.VehicleIdentityOutput"/>'
            '</nodes><handlers><eventhandler node="Reader">' + call + extra +
            '</eventhandler></handlers></content></script>').encode()


def group(data):
    return audit_xml(data)['identity_method_parameter_declarations']['addvin']


class OriginalPropertyClassTests(unittest.TestCase):
    def test_01_source_string_property_is_declaration_not_propagated_vin(self):
        r = audit_xml(build())
        g = r['identity_method_parameter_declarations']['addvin']
        self.assertEqual(g['source_property_class_bins']['String'], 1)
        self.assertTrue(r['original_parser_content_child_layout_verified'])
        self.assertFalse(r['any_argument_runtime_value_computed'])
        self.assertFalse(r['vin_accepted_by_client'])

    def test_02_int_double_byte_and_other_categories_are_distinct(self):
        for name in PROPERTY_CLASSES:
            with self.subTest(name=name):
                g = group(build(node_props=f'<property name="Result" class="{name}"/>'))
                self.assertEqual(g['source_property_class_bins'][name], 1)
                self.assertEqual(g['source_property_reference_parameters'], 1)

    def test_03_constant_class_branch_and_private_value_never_emitted(self):
        r = audit_xml(build(params='<parameter class="Int" value="PRIVATE-000"/>'))
        g = r['identity_method_parameter_declarations']['addvin']
        self.assertEqual(g['constant_class_bins']['Int'], 1)
        self.assertEqual(g['source_property_reference_parameters'], 0)
        self.assertNotIn('PRIVATE-000', json.dumps(r))

    def test_04_unknown_source_property_not_runtime_validation_failure(self):
        g = group(build(params='<parameter node="Reader" property="DynamicResult"/>'))
        self.assertEqual(g['source_properties_not_in_xml'], 1)
        self.assertEqual(g['source_property_class_bins']['unknown_or_missing'], 1)

    def test_05_disabled_presence_and_sibling_handler_classification(self):
        g = group(build(disabled=' disabled="false"'))
        self.assertEqual(g['parser_disabled_declarations'], 1)
        self.assertEqual(g['parser_enabled_declarations'], 0)
        g = group(build())
        self.assertEqual(g['parser_enabled_declarations'], 1)

    def test_06_wrapped_call_and_property_are_not_direct_in_original_parser(self):
        g = group(build(wrapped=True))
        self.assertEqual(g['direct_identity_call_declarations'], 0)
        g = group(build(node_props='<wrapper><property name="Result" class="String"/></wrapper>'))
        self.assertEqual(g['source_properties_not_in_xml'], 1)

    def test_07_original_script_content_layout_is_required(self):
        with self.assertRaises(ValueError):
            audit_xml(build().replace(b'<content>', b'<wrapper><content>').replace(b'</content>', b'</content></wrapper>'))
        with self.assertRaises(ValueError):
            audit_xml(build().replace(b'<content>', b'').replace(b'</content>', b''))

    def test_09_readvin_result_response_object_requires_another_conversion(self):
        r = audit_xml(build(node_props='<property name="Result" class="Response"/>'))
        g = r['identity_method_parameter_declarations']['addvin']
        self.assertEqual(g['references_from_readvin_component'], 1)
        self.assertEqual(g['readvin_result_response_object_references'], 1)
        self.assertEqual(g['readvin_result_declared_response_class'], 1)
        self.assertEqual(g['readvin_result_class_unresolved_or_other'], 0)
        self.assertEqual(r['readvin_result_original_il_getter_contract'], 'ResponseComponent')
        self.assertFalse(r['readvin_result_is_accepted_vin'])

    def test_10_other_readvin_property_is_not_a_response_result(self):
        r = audit_xml(build(node_props='<property name="Result" class="Response"/>',
                            params='<parameter node="Reader" property="CanHiSpeedValue"/>'))
        g = r['identity_method_parameter_declarations']['addvin']
        self.assertEqual(g['references_from_readvin_component'], 1)
        self.assertEqual(g['readvin_result_response_object_references'], 0)
        self.assertEqual(g['source_properties_not_in_xml'], 1)

    def test_11_missing_or_mismatched_result_class_must_not_claim_vin(self):
        for declared in ('String', ''):
            with self.subTest(declared=declared):
                props = '<property name="Result" class="String"/>' if declared else ''
                r = audit_xml(build(node_props=props))
                g = r['identity_method_parameter_declarations']['addvin']
                self.assertEqual(g['readvin_result_response_object_references'], 1)
                self.assertEqual(g['readvin_result_declared_response_class'], 0)
                self.assertEqual(g['readvin_result_class_unresolved_or_other'], 1)
                self.assertFalse(r['readvin_result_is_accepted_vin'])

    def test_12_other_component_and_missing_node_reference_separated(self):
        r = audit_xml(build(params='<parameter node="Output" property="Result"/>'))
        g = r['identity_method_parameter_declarations']['addvin']
        self.assertEqual(g['references_from_other_declared_components'], 1)
        self.assertEqual(g['references_to_missing_nodes'], 0)
        self.assertEqual(g['references_from_readvin_component'], 0)
        r = audit_xml(build(params='<parameter node="Missing" property="Result"/>'))
        g = r['identity_method_parameter_declarations']['addvin']
        self.assertEqual(g['references_from_other_declared_components'], 0)
        self.assertEqual(g['references_to_missing_nodes'], 1)

    def test_13_identity_string_signature_does_not_convert_response(self):
        result = audit_xml(build(node_props='<property name="Result" class="Response"/>'))
        self.assertEqual(result['addvin_original_il_argument_type'], 'System.String')
        self.assertEqual(result['setx40serial_original_il_argument_type'], 'System.String')
        self.assertEqual(result['readvin_result_original_il_getter_contract'], 'ResponseComponent')
        self.assertFalse(result['direct_readvin_result_to_identity_string_flow_verified'])
        self.assertFalse(result['vin_accepted_by_client'])

    def test_08_bounded_zip_cli_redacted_and_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            z, out = Path(d, 'private.zip'), Path(d, 'safe.json')
            with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as f:
                f.writestr('script.xml', build())
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(z), '--output', str(out)])
            raw = out.read_text()
            self.assertTrue(json.loads(raw)['original_parser_content_child_layout_verified'])
            self.assertNotIn('PRIVATE', raw)
            self.assertNotIn(str(z), raw)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(z), '--output', str(out)])


if __name__ == '__main__':
    unittest.main()
