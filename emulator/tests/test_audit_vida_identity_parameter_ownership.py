"""Eight synthetic regressions for VIDA identity call parameter ownership.

No real VIDA XML, VIN, script IDs, SQL, diagnostic frames or credentials.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_readvin_xml_graph import audit_xml_bytes


def script(body, nodes=None):
    if nodes is None:
        nodes = ('<node nodeid="R" class="Components.ReadVinComponent"/>'
                 '<node nodeid="M" class="Components.Parser"/>'
                 '<node nodeid="Output" class="Components.VehicleIdentityOutput"/>')
    return ('<script><wrapper><nodes>' + nodes + '</nodes>'
            '<handlers>' + body + '</handlers></wrapper></script>').encode()


def handler(source, target="Output", method="AddVIN", params="", disabled=""):
    return ('<eventhandler node="' + source + '"><call node="' + target +
            '" method="' + method + '"' + disabled + '>' + params +
            '</call></eventhandler>')


def param_counts(result, method="add_vin"):
    return result["declared_identity_method_edges"][method]["parameter_declarations_only"]


class ReadVinNearestCallParameterTests(unittest.TestCase):
    def test_01_identity_argument_owned_by_call(self):
        result = audit_xml_bytes(script(handler("M", params='<parameter source="R"/>')))
        self.assertEqual(param_counts(result)["declared_parameter_children"], 1)
        self.assertEqual(param_counts(result)["calls_with_reference_like_key_matching_reader_id"], 1)
        self.assertFalse(result["observed_event_callback_executed"])

    def test_02_nested_unrelated_call_must_not_loan_parameter_to_addvin(self):
        nested = '<call node="M" method="Other"><parameter source="R"/></call>'
        result = audit_xml_bytes(script(handler("R", params=nested)))
        self.assertEqual(param_counts(result)["declared_parameter_children"], 0)
        self.assertEqual(param_counts(result)["calls_with_reference_like_key_matching_reader_id"], 0)
        self.assertEqual(result["declared_call_count"], 2)
        self.assertEqual(result["graph_layout"]["status"], "unresolved_or_partial")
        self.assertEqual(result["graph_layout"]["call_elements_nested_under_call_not_promoted"], 1)

    def test_03_name_value_and_class_keys_are_not_reference_declarations(self):
        params = '<parameter name="R" value="M" class="Output"/>'
        result = audit_xml_bytes(script(handler("M", params=params)))
        self.assertEqual(param_counts(result)["declared_parameter_children"], 1)
        self.assertEqual(param_counts(result)["calls_with_reference_like_key_matching_node_id"], 0)
        self.assertFalse(result["actual_vida_client_identity_verified"])

    def test_04_lexical_reference_under_explicit_key_is_not_runtime_data_flow(self):
        params = '<parameter ref="R" value="YV1_PRIVATE_SYNTHETIC"/>'
        result = audit_xml_bytes(script(handler("M", params=params)))
        self.assertEqual(param_counts(result)["calls_with_reference_like_key_matching_reader_id"], 1)
        self.assertNotIn("YV1_PRIVATE_SYNTHETIC", json.dumps(result))
        self.assertFalse(result["observed_vehicle_identity_returned"])

    def test_05_disabled_absent_does_not_mean_explicit_enabled(self):
        result = audit_xml_bytes(script(handler("M", params="<parameter>PRIVATE</parameter>")))
        addvin = result["declared_identity_method_edges"]["add_vin"]
        self.assertEqual(addvin["absent_disabled_attribute"], 1)
        self.assertEqual(addvin["not_disabled_literal"], 0)
        self.assertEqual(param_counts(result)["calls_with_parameter_text"], 1)
        self.assertFalse(result["replay_approved"])

    def test_06_nested_parameter_wrapper_owned_by_identity_call(self):
        nested = '<arguments><parameter node="R">SYNTHETIC_SECRET</parameter></arguments>'
        result = audit_xml_bytes(script(handler("R", params=nested)))
        self.assertEqual(param_counts(result)["declared_parameter_children"], 1)
        self.assertEqual(param_counts(result)["calls_with_parameter_text"], 1)
        self.assertNotIn("SYNTHETIC_SECRET", json.dumps(result))

    def test_07_multiple_methods_keep_separate_parameter_counts(self):
        body = (handler("M", params='<parameter source="R"/>') +
                handler("M", method="SetX40Serial", params="<parameter/>"))
        result = audit_xml_bytes(script(body))
        self.assertEqual(param_counts(result)["declared_parameter_children"], 1)
        self.assertEqual(param_counts(result, "set_x40_serial")["declared_parameter_children"], 1)
        self.assertEqual(param_counts(result, "set_x40_serial")[
                         "calls_with_reference_like_key_matching_reader_id"], 0)

    def test_08_namespaced_xml_parameter_and_unknown_target_fail_safe(self):
        xml = (b'<script xmlns:v="urn:synthetic"><v:nodes>'
               b'<v:node nodeid="R" class="ReadVinComponent"/>'
               b'<v:node nodeid="Output" class="VehicleIdentityOutput"/>'
               b'</v:nodes><v:handlers><v:eventhandler node="R">'
               b'<v:call node="Output" method="AddVIN"><v:parameter v:source="R"/>'
               b'</v:call></v:eventhandler></v:handlers></script>')
        result = audit_xml_bytes(xml)
        self.assertEqual(param_counts(result)["declared_parameter_children"], 1)
        self.assertEqual(param_counts(result)["calls_with_reference_like_key_matching_reader_id"], 1)
        self.assertFalse(result["actual_vida_client_identity_verified"])


    def test_09_nested_identity_call_not_promoted_as_event_evidence(self):
        foreign = '<call node="Output" method="AddVIN"><parameter source="R"/></call>'
        result = audit_xml_bytes(script(handler("R", target="M", method="Forward", params=foreign)))
        self.assertEqual(result["declared_call_count"], 2)
        self.assertEqual(result["declared_identity_method_edges"]["add_vin"]["declared"], 0)
        self.assertEqual(result["graph_layout"]["call_elements_nested_under_call_not_promoted"], 1)
        self.assertEqual(result["graph_layout"]["status"], "unresolved_or_partial")
        self.assertFalse(result["actual_vida_client_identity_verified"])

    def test_10_wrapped_sibling_call_remains_separate_and_classifiable(self):
        body = ('<eventhandler node="R"><calls>'
                '<call node="M" method="Forward"/>'
                '<call node="Output" method="AddVIN"><parameter source="R"/></call>'
                '</calls></eventhandler>')
        result = audit_xml_bytes(script(body))
        self.assertEqual(result["declared_call_count"], 2)
        self.assertEqual(result["declared_identity_method_edges"]["add_vin"]["declared"], 1)
        self.assertEqual(param_counts(result)["declared_parameter_children"], 1)
        self.assertEqual(result["graph_layout"]["call_elements_nested_under_call_not_promoted"], 0)
        self.assertNotEqual(result["graph_layout"]["status"], "unresolved_or_partial")
        self.assertFalse(result["replay_approved"])


if __name__ == "__main__":
    unittest.main()
