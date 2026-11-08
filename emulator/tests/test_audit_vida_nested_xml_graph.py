"""Eight synthetic regressions for nested/wrapped VIDA XML graphs.

No original VIDA XML, private VIN or live SQL is included.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_readvin_xml_graph import audit_xml_bytes
import audit_vida_single_readvin_zip as zip_tool


def wrapped_xml(nodes="", handlers="", prefix=""):
    if not nodes:
        nodes = ('<node nodeid="Reader" class="X.ReadVinComponent"/>'
                 '<node nodeid="Output" class="X.VehicleIdentityOutput"/>')
    if not handlers:
        handlers = ('<eventhandler node="Reader" name="done"><calls>'
                    '<call node="Output" method="AddVIN" disabled="false"/>'
                    '</calls></eventhandler>')
    return (f'<script>{prefix}<unknown_container><nodes>{nodes}</nodes>'
            f'<handlers>{handlers}</handlers></unknown_container></script>').encode()


class VidaNestedReadVinGraphTests(unittest.TestCase):
    def test_01_real_layout_shape_14_27_27_synthetic(self):
        nodes = (
            '<node nodeid="Output" class="X.VehicleIdentityOutput"/>' +
            ''.join(f'<node nodeid="R{i}" class="X.ReadVinComponent"/>'
                    for i in range(7)) +
            ''.join(f'<node nodeid="Other{i}" class="X.Other"/>'
                    for i in range(6))
        )
        handlers = ''.join(
            f'<eventhandler node="R0" name="N{i}"><calls>'
            f'<call node="Output" method="{("AddVIN" if i < 2 else "SetX40Serial" if i == 2 else "Other")}"'
            ' disabled="false"/></calls></eventhandler>'
            for i in range(27)
        )
        x = audit_xml_bytes(wrapped_xml(nodes, handlers))
        self.assertEqual(x["node_count"], 14)
        self.assertEqual(x["event_handler_count"], 27)
        self.assertEqual(x["declared_call_count"], 27)
        self.assertEqual(x["readvin_component_node_count"], 7)
        self.assertEqual(x["declared_identity_method_edges"]["add_vin"]["declared"], 2)
        self.assertEqual(x["declared_identity_method_edges"]["set_x40_serial"]["declared"], 1)
        self.assertEqual(x["graph_layout"]["status"], "nested_sections")
        self.assertFalse(x["observed_event_callback_executed"])

    def test_02_namespaced_sections_are_localname_matched(self):
        xml = (b'<script xmlns:v="urn:synthetic"><wrapper><v:nodes>'
               b'<v:node nodeid="Output" class="X.VehicleIdentityOutput"/>'
               b'<v:node nodeid="Reader" class="X.ReadVinComponent"/>'
               b'</v:nodes><v:handlers><v:eventhandler node="Reader" name="on">'
               b'<v:calls><v:call node="Output" method="AddVIN" disabled="0"/>'
               b'</v:calls></v:eventhandler></v:handlers></wrapper></script>')
        x = audit_xml_bytes(xml)
        self.assertEqual(x["node_count"], 2)
        self.assertEqual(x["declared_identity_method_edges"]["add_vin"]["declared"], 1)
        self.assertEqual(x["graph_layout"]["status"], "nested_sections")

    def test_03_outside_nodes_section_not_promoted(self):
        xml = (b'<script><metadata><node nodeid="Fake" class="X.ReadVinComponent"/>'
               b'</metadata><container><nodes><node nodeid="Output" '
               b'class="X.VehicleIdentityOutput"/></nodes>'
               b'<handlers/></container></script>')
        x = audit_xml_bytes(xml)
        self.assertEqual(x["node_count"], 1)
        self.assertEqual(x["readvin_component_node_count"], 0)
        self.assertEqual(x["graph_layout"]["node_elements_outside_nodes_section"], 1)
        self.assertEqual(x["graph_layout"]["status"], "unresolved_or_partial")

    def test_04_propertyhandler_call_not_conflated_with_events(self):
        xml = (b'<script><payload><nodes>'
               b'<node nodeid="Output" class="VehicleIdentityOutput"/>'
               b'<node nodeid="Reader" class="ReadVinComponent"/></nodes>'
               b'<handlers><propertyhandler node="Reader">'
               b'<call node="Output" method="AddVIN"/></propertyhandler>'
               b'</handlers></payload></script>')
        x = audit_xml_bytes(xml)
        self.assertEqual(x["declared_identity_method_edges"]["add_vin"]["declared"], 0)
        self.assertEqual(x["declared_call_count"], 0)
        self.assertEqual(x["graph_layout"]["call_elements_not_in_parsed_eventhandlers"], 1)
        self.assertEqual(x["graph_layout"]["status"], "unresolved_or_partial")

    def test_05_nested_duplicate_node_identifier_rejected(self):
        xml = wrapped_xml(nodes='<node nodeid="Duplicate" class="ReadVinComponent"/>'
                                '<node nodeid="Duplicate" class="VehicleIdentityOutput"/>')
        with self.assertRaises(ValueError):
            audit_xml_bytes(xml)

    def test_06_no_implicit_runtime_or_enabled_claim(self):
        xml = wrapped_xml(handlers=(
            '<eventhandler node="Reader" name="done"><calls>'
            '<call node="Output" method="AddVIN" disabled="maybe"/>'
            '<call node="Output" method="SetX40Serial"/>'
            '</calls></eventhandler>'
        ))
        x = audit_xml_bytes(xml)
        self.assertEqual(x["declared_identity_method_edges"]["add_vin"]
                         ["unrecognized_disabled_literal"], 1)
        self.assertEqual(x["declared_identity_method_edges"]["set_x40_serial"]
                         ["absent_disabled_attribute"], 1)
        self.assertFalse(x["observed_vehicle_identity_returned"])
        self.assertFalse(x["actual_vida_client_identity_verified"])

    def test_07_nested_zip_report_is_privacy_safe(self):
        with tempfile.TemporaryDirectory() as d:
            zipfile_path = Path(d, "private.zip")
            private = wrapped_xml(prefix="<private>YV1CZ0002A0000001</private>")
            with zipfile.ZipFile(zipfile_path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("private-script", private)
            result = zip_tool.audit(zipfile_path)
            graph = result["identity_xml_graph_declarations"]
            self.assertEqual(graph["node_count"], 2)
            self.assertEqual(graph["event_handler_count"], 1)
            self.assertEqual(graph["declared_call_count"], 1)
            self.assertEqual(graph["graph_layout"]["status"], "nested_sections")
            text = json.dumps(result)
            self.assertNotIn("YV1CZ0002A0000001", text)
            self.assertNotIn(str(zipfile_path), text)
            self.assertFalse(result["script_selected_by_getscript_runtime"])
            self.assertFalse(result["replay_approved"])

    def test_08_exact_legacy_paths_still_recognized(self):
        xml = (b'<script><nodes>'
               b'<node nodeid="Reader" class="ReadVinComponent"/>'
               b'<node nodeid="Output" class="VehicleIdentityOutput"/>'
               b'</nodes><handlers><eventhandler node="Reader" name="on">'
               b'<call node="Output" method="AddVIN" disabled="false"/>'
               b'</eventhandler></handlers></script>')
        x = audit_xml_bytes(xml)
        self.assertEqual(x["graph_layout"]["status"], "direct_sections")
        self.assertEqual(x["declared_identity_method_edges"]["add_vin"]["declared"], 1)
        self.assertFalse(x["replay_approved"])


if __name__ == "__main__":
    unittest.main()
