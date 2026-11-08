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
        disabled='', reader_call=True, output_method='AddVIN', ext='',
        binding=True, binding_disabled=''):
    reader = '<eventhandler node="Reader" name="OnPositiveResponse"><call node="Extractor" method="Execute"/></eventhandler>' if reader_call else ''
    output = ('<eventhandler node="Extractor" name="OnGet"><call node="Identity" method="' + output_method + '"' +
              disabled + '>' + identity_param + '</call></eventhandler>')
    binding_xml = ('<propertyhandler node="Reader" name="Result">'
                   '<set node="Extractor" property="InValue"' +
                   binding_disabled + '/></propertyhandler>') if binding else ''
    return ('<script><content><nodes>'
            '<node nodeid="Reader" class="X.ReadVinComponent"><property name="Result" class="Response"/></node>'
            '<node nodeid="Extractor" class="X.ResultGet">' + invalue + '<extension>' + gets + ext + '</extension></node>'
            '<node nodeid="Identity" class="X.VehicleIdentityOutput"/>'
            '</nodes><handlers>' + reader + output + binding_xml + '</handlers></content></script>').encode()


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
        self.assertTrue(r['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertTrue(r['candidate_addvin_route_with_event_names_lexically_present'])
        self.assertFalse(r['candidate_x40_route_with_event_names_lexically_present'])
        self.assertEqual(c['enabled_readvin_result_to_resultget_invalue_sets'], 1)
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

    def test_11_unrelated_resultget_nodes_cannot_make_false_path(self):
        raw = xml()
        raw = raw.replace(
            b'<node nodeid="Identity"',
            b'<node nodeid="OtherExtractor" class="X.ResultGet">'
            b'<property name="InValue" class="Response"/>'
            b'<extension><get property="Decoded"/></extension></node>'
            b'<node nodeid="Identity"',
        ).replace(b'<parameter node="Extractor" property="Decoded"/>',
                  b'<parameter node="OtherExtractor" property="Decoded"/>')
        r = audit_xml(raw)
        self.assertEqual(r['categorical_declarations']['resultget_node_declarations'], 2)
        self.assertEqual(r['categorical_declarations']['enabled_readvin_event_to_resultget_execute_declarations'], 1)
        self.assertEqual(r['categorical_declarations']['enabled_identity_calls_using_resultget_get_output'], 1)
        self.assertFalse(r['candidate_route_lexically_present'])
        self.assertTrue(r['candidate_route_same_resultget_node_required'])

    def test_12_without_propertyhandler_only_two_event_legs_are_present(self):
        result = audit_xml(xml(binding=False))
        self.assertTrue(result['candidate_route_lexically_present'])
        self.assertFalse(result['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'readvin_result_to_resultget_invalue_set_declarations'], 0)

    def test_13_disabled_false_property_setter_must_not_complete_route(self):
        result = audit_xml(xml(binding_disabled=' disabled="false"'))
        assert result['candidate_route_lexically_present']
        self.assertFalse(result['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'disabled_readvin_result_to_resultget_invalue_sets'], 1)

    def test_14_wrong_property_setter_cannot_bridge_result(self):
        raw = xml().replace(b'<set node="Extractor" property="InValue"/>',
                            b'<set node="Extractor" property="Other"/>')
        result = audit_xml(raw)
        self.assertFalse(result['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'readvin_result_setters_to_other_target_properties'], 1)

    def test_15_wrapped_set_ignored_like_original_parser(self):
        raw = xml().replace(b'<set node="Extractor" property="InValue"/>',
                            b'<wrapper><set node="Extractor" property="InValue"/></wrapper>')
        result = audit_xml(raw)
        self.assertEqual(result['categorical_declarations'][
            'readvin_result_to_resultget_invalue_set_declarations'], 0)
        self.assertFalse(result['candidate_three_leg_route_with_property_binding_lexically_present'])

    def test_16_propertyhandler_from_different_readvin_not_same_route(self):
        raw = xml().replace(
            b'<node nodeid="Extractor"',
            b'<node nodeid="Reader2" class="X.ReadVinComponent"/>'
            b'<node nodeid="Extractor"',
        ).replace(b'<propertyhandler node="Reader"',
                  b'<propertyhandler node="Reader2"')
        result = audit_xml(raw)
        self.assertEqual(result['categorical_declarations'][
            'enabled_readvin_result_to_resultget_invalue_sets'], 1)
        self.assertTrue(result['candidate_route_lexically_present'])
        self.assertFalse(result['candidate_three_leg_route_with_property_binding_lexically_present'])

    def test_17_propertyhandler_to_different_resultget_not_same_route(self):
        raw = xml().replace(
            b'<node nodeid="Identity"',
            b'<node nodeid="OtherExtractor" class="X.ResultGet"/>'
            b'<node nodeid="Identity"',
        ).replace(b'<set node="Extractor" property="InValue"/>',
                  b'<set node="OtherExtractor" property="InValue"/>')
        result = audit_xml(raw)
        self.assertTrue(result['candidate_route_lexically_present'])
        self.assertFalse(result['candidate_three_leg_route_with_property_binding_lexically_present'])

    def test_18_missing_event_names_cannot_make_verified_route(self):
        raw = xml().replace(b' name="OnPositiveResponse"', b'').replace(b' name="OnGet"', b'')
        report = audit_xml(raw)
        self.assertTrue(report['candidate_three_leg_without_event_name_validation_lexically_present'])
        self.assertFalse(report['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertEqual(report['categorical_declarations'][
            'reader_execute_calls_with_other_or_absent_event_name'], 1)
        self.assertEqual(report['categorical_declarations'][
            'resultget_to_identity_calls_with_other_or_absent_event_name'], 1)
        self.assertFalse(report['vin_accepted_by_client'])

    def test_19_no_response_event_not_positive_vin_route(self):
        raw = xml().replace(b' name="OnPositiveResponse"', b' name="OnNoResponse"')
        report = audit_xml(raw)
        self.assertTrue(report['candidate_three_leg_without_event_name_validation_lexically_present'])
        self.assertFalse(report['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertFalse(report['candidate_addvin_route_with_event_names_lexically_present'])

    def test_20_resultget_wrong_event_cannot_make_vin_route(self):
        raw = xml().replace(b' name="OnGet"', b' name="OnNoContact"')
        report = audit_xml(raw)
        self.assertTrue(report['candidate_three_leg_without_event_name_validation_lexically_present'])
        self.assertFalse(report['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertFalse(report['candidate_addvin_route_with_event_names_lexically_present'])

    def test_21_onget_x40_uses_separate_non_vin_gate(self):
        report = audit_xml(xml(output_method='SetX40Serial'))
        self.assertTrue(report['candidate_three_leg_route_with_property_binding_lexically_present'])
        self.assertTrue(report['candidate_x40_route_with_event_names_lexically_present'])
        self.assertFalse(report['candidate_addvin_route_with_event_names_lexically_present'])
        self.assertFalse(report['vin_accepted_by_client'])

    def test_22_no_promotion_when_disabled_positive_event(self):
        raw = xml().replace(b'method="Execute"/>', b'method="Execute" disabled="false"/>')
        report = audit_xml(raw)
        self.assertEqual(report['categorical_declarations'][
            'readvin_positive_response_to_resultget_execute_declarations'], 1)
        self.assertEqual(report['categorical_declarations'][
            'enabled_readvin_positive_response_to_resultget_execute_declarations'], 0)
        self.assertFalse(report['candidate_three_leg_route_with_property_binding_lexically_present'])

    def test_23_exact_original_zero_plus_one_arity_with_named_output(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        result = audit_xml(raw)
        self.assertTrue(result['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertFalse(result['candidate_x40_route_arity_and_output_shape_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'identity_calls_to_named_output_with_one_argument'], 1)
        self.assertFalse(result['identity_argument_string_type_verified'])
        self.assertFalse(result['vin_accepted_by_client'])

    def test_24_resultget_execute_with_one_arg_is_not_valid_void_call(self):
        raw = xml().replace(b'method="Execute"/>',
                            b'method="Execute"><parameter value="1" class="Int"/></call>')
        raw = raw.replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        result = audit_xml(raw)
        self.assertTrue(result['candidate_addvin_route_with_event_names_lexically_present'])
        self.assertFalse(result['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'reader_execute_calls_with_direct_arguments'], 1)

    def test_25_addvin_with_two_args_does_not_match_original_signature(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<parameter node="Extractor" property="Decoded"/>',
                          b'<parameter node="Extractor" property="Decoded"/>'
                          b'<parameter value="SYNTHETIC" class="String"/>')
        result = audit_xml(raw)
        self.assertTrue(result['candidate_addvin_route_with_event_names_lexically_present'])
        self.assertFalse(result['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'identity_calls_with_wrong_direct_argument_count'], 1)
        self.assertNotIn('SYNTHETIC', json.dumps(result))

    def test_26_identity_non_output_node_not_script_getoutput(self):
        result = audit_xml(xml())
        self.assertTrue(result['candidate_addvin_route_with_event_names_lexically_present'])
        self.assertFalse(result['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'identity_calls_to_non_output_node_id'], 1)

    def test_27_x40_stays_separate_with_matching_argument_shape(self):
        raw = xml(output_method='SetX40Serial').replace(
            b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        result = audit_xml(raw)
        self.assertTrue(result['candidate_x40_route_arity_and_output_shape_lexically_present'])
        self.assertFalse(result['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertFalse(result['vin_accepted_by_client'])

    def test_28_addvin_no_argument_not_callable(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<parameter node="Extractor" property="Decoded"/>', b'')
        result = audit_xml(raw)
        self.assertFalse(result['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'identity_calls_with_wrong_direct_argument_count'], 1)
        self.assertFalse(result['vin_accepted_by_client'])

    def test_29_wrapped_argument_not_selected_by_original_call_parser(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<parameter node="Extractor" property="Decoded"/>',
                          b'<parameters><parameter node="Extractor" property="Decoded"/></parameters>')
        result = audit_xml(raw)
        self.assertFalse(result['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertEqual(result['categorical_declarations'][
            'identity_calls_with_wrong_direct_argument_count'], 1)
        self.assertFalse(result['identity_argument_string_type_verified'])

    def test_30_get_name_without_direct_output_property_is_only_weaker_candidate(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        report = audit_xml(raw)
        self.assertTrue(report['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertFalse(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertEqual(report['categorical_declarations']['get_outputs_without_direct_property'], 1)
        self.assertFalse(report['resultget_property_lookup_at_runtime_verified'])

    def test_31_direct_string_property_can_form_stronger_static_candidate(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<extension>', b'<property name="Decoded" class="String"/><extension>')
        report = audit_xml(raw)
        self.assertTrue(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertFalse(report['candidate_x40_route_direct_declared_string_output_lexically_present'])
        self.assertEqual(report['categorical_declarations']['get_outputs_with_unique_direct_string_property'], 1)
        self.assertFalse(report['vin_accepted_by_client'])
        self.assertFalse(report['identity_argument_string_type_verified'])

    def test_32_byte_class_is_not_declared_string_compatible(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<extension>', b'<property name="Decoded" class="Byte"/><extension>')
        report = audit_xml(raw)
        self.assertFalse(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertEqual(report['categorical_declarations']['get_outputs_with_other_or_unknown_class'], 1)

    def test_33_wrapper_nested_property_is_not_direct_property(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<extension>', b'<wrapper><property name="Decoded" class="String"/></wrapper><extension>')
        report = audit_xml(raw)
        self.assertFalse(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertEqual(report['categorical_declarations']['get_outputs_without_direct_property'], 1)

    def test_34_duplicate_output_property_is_ambiguous(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<extension>',
                          b'<property name="Decoded" class="String"/>'
                          b'<property name="Decoded" class="String"/><extension>')
        report = audit_xml(raw)
        self.assertFalse(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertEqual(report['categorical_declarations']['get_outputs_with_duplicate_property_declarations'], 1)

    def test_35_string_property_of_different_resultget_does_not_join(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<node nodeid="Output"',
                          b'<node nodeid="Extractor2" class="X.ResultGet">'
                          b'<property name="Decoded" class="String"/>'
                          b'<extension><get property="Decoded"/></extension></node>'
                          b'<node nodeid="Output"')
        report = audit_xml(raw)
        self.assertFalse(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertEqual(report['categorical_declarations']['get_outputs_with_unique_direct_string_property'], 1)

    def test_36_x40_has_own_string_property_candidate_not_vin(self):
        raw = xml(output_method='SetX40Serial').replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<extension>', b'<property name="Decoded" class="String"/><extension>')
        report = audit_xml(raw)
        self.assertTrue(report['candidate_x40_route_direct_declared_string_output_lexically_present'])
        self.assertFalse(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertFalse(report['vin_accepted_by_client'])

    def test_37_source_property_name_does_not_match_get_output(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        raw = raw.replace(b'<extension>', b'<property name="Unrelated" class="String"/><extension>')
        report = audit_xml(raw)
        self.assertFalse(report['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertEqual(report['categorical_declarations']['get_outputs_without_direct_property'], 1)

    def test_38_original_setpath_contract_is_not_scriptable(self):
        r = audit_xml(xml())
        self.assertEqual(r['original_resultget_setpath_signature'],
                         'void(string, ResponsePath, ResponseNodeType)')
        self.assertFalse(r['original_resultget_setpath_scriptable_attribute_present'])
        self.assertTrue(r['original_resultget_execute_scriptable_attribute_present'])
        self.assertEqual(r['original_setpath_primitive_response_node_enum_value'], 7)
        self.assertEqual(r['original_setpath_primitive_registers_property_class'], 'String')
        self.assertEqual(r['original_setpath_other_node_types_register_property_class'], 'Response')
        self.assertFalse(r['setpath_invoked_by_original_runtime_verified'])

    def test_39_three_arg_setpath_xml_call_cannot_promote_missing_string_property(self):
        raw = xml().replace(b'nodeid="Identity"', b'nodeid="Output"').replace(
            b'node="Identity"', b'node="Output"')
        insert = (b'<call node="Extractor" method="SetPath">'
                  b'<parameter class="String" value="Decoded"/>'
                  b'<parameter node="Reader" property="Result"/>'
                  b'<parameter class="Int" value="7"/>'
                  b'</call>')
        raw = raw.replace(b'<eventhandler node="Reader" name="OnPositiveResponse">',
                          b'<eventhandler node="Reader" name="OnPositiveResponse">' + insert)
        r = audit_xml(raw)
        self.assertEqual(r['categorical_declarations'][
            'resultget_setpath_event_calls_with_three_direct_args'], 1)
        self.assertTrue(r['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertFalse(r['candidate_addvin_route_direct_declared_string_output_lexically_present'])
        self.assertFalse(r['setpath_called_from_script_event_verified'])
        self.assertNotIn('Decoded', json.dumps(r))

    def test_40_setpath_wrong_arity_is_reported_without_executing_it(self):
        raw = xml().replace(b'<eventhandler node="Reader" name="OnPositiveResponse">',
                          b'<eventhandler node="Reader" name="OnPositiveResponse">'
                          b'<call node="Extractor" method="SetPath">'
                          b'<parameter value="X" class="String"/></call>')
        r = audit_xml(raw)
        self.assertEqual(r['categorical_declarations'][
            'resultget_setpath_event_call_declarations'], 1)
        self.assertEqual(r['categorical_declarations'][
            'resultget_setpath_event_calls_with_wrong_direct_arg_count'], 1)
        self.assertFalse(r['setpath_called_from_script_event_verified'])

    def test_41_setpath_disabled_literal_false_is_not_eligible(self):
        raw = xml().replace(b'<eventhandler node="Reader" name="OnPositiveResponse">',
                          b'<eventhandler node="Reader" name="OnPositiveResponse">'
                          b'<call node="Extractor" method="SetPath" disabled="false"/>')
        r = audit_xml(raw)
        self.assertEqual(r['categorical_declarations'][
            'resultget_setpath_event_calls_disabled_by_attribute'], 1)
        self.assertFalse(r['setpath_invoked_by_original_runtime_verified'])

    def test_42_setpath_call_on_unrelated_component_not_claimed(self):
        raw = xml().replace(b'<eventhandler node="Reader" name="OnPositiveResponse">',
                          b'<eventhandler node="Reader" name="OnPositiveResponse">'
                          b'<call node="Identity" method="SetPath"/>')
        r = audit_xml(raw)
        self.assertEqual(r['categorical_declarations'][
            'resultget_setpath_event_call_declarations'], 0)

    def test_43_setpath_xml_call_does_not_generate_get_or_runtime_output(self):
        raw = xml(gets='').replace(b'<eventhandler node="Reader" name="OnPositiveResponse">',
                          b'<eventhandler node="Reader" name="OnPositiveResponse">'
                          b'<call node="Extractor" method="SetPath">'
                          b'<parameter class="String" value="SECRET"/>'
                          b'<parameter class="Response" value="PATH"/>'
                          b'<parameter class="Int" value="7"/>'
                          b'</call>')
        r = audit_xml(raw)
        self.assertEqual(r['categorical_declarations'][
            'direct_get_property_declarations'], 0)
        self.assertFalse(r['candidate_addvin_route_arity_and_output_shape_lexically_present'])
        self.assertFalse(r['setpath_generated_get_selection_path_verified'])
        self.assertNotIn('SECRET', json.dumps(r))
        self.assertNotIn('PATH', json.dumps(r))

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
