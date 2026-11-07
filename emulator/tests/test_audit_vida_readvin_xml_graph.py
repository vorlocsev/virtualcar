"""Eight offline synthetic tests for VIDA XML method-graph evidence only."""
import contextlib
import io
import json
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_readvin_xml_graph import audit_xml_bytes, audit_file, main, MAX_ELEMENTS


def xml(calls='', nodes='', handlers=''):
    basic = ('<node nodeid="Reader" class="ReadVinComponent"/>'
             '<node nodeid="Output" class="VehicleIdentityOutput"/>')
    if not handlers:
        handlers = '<eventhandler node="Reader" name="OnComplete">' + calls + '</eventhandler>'
    return ('<script><nodes>' + basic + nodes + '</nodes><handlers>' + handlers + '</handlers></script>').encode()


def call(name, target='Output', disabled='0', payload=''):
    return ('<call method="' + name + '" node="' + target + '" disabled="' + disabled + '">' + payload + '</call>')


class VidaXmlGraphAuditTests(unittest.TestCase):
    def test_01_declared_vin_edge_is_not_execution(self):
        report = audit_xml_bytes(xml(call('AddVIN')))
        self.assertTrue(report['named_output_node_is_vehicle_identity_output'])
        self.assertEqual(report['declared_identity_method_edges']['add_vin']['declared'], 1)
        self.assertEqual(report['declared_identity_method_edges']['add_vin']['readvin_source_node'], 1)
        self.assertFalse(report['observed_event_callback_executed'])
        self.assertFalse(report['observed_vehicle_identity_returned'])
        self.assertFalse(report['replay_approved'])

    def test_02_distinct_x40_and_disabled_categories(self):
        report = audit_xml_bytes(xml(call('SetX40Serial', disabled='true') + call('AddVIN', disabled='false')))
        self.assertEqual(report['declared_identity_method_edges']['set_x40_serial']['disabled_literal'], 1)
        self.assertEqual(report['declared_identity_method_edges']['add_vin']['not_disabled_literal'], 1)
        self.assertFalse(report['actual_vida_client_identity_verified'])

    def test_03_unknown_disabled_literal_not_inferred_enabled(self):
        report = audit_xml_bytes(xml(call('AddVIN', disabled='perhaps')))
        g = report['declared_identity_method_edges']['add_vin']
        self.assertEqual(g['unrecognized_disabled_literal'], 1)
        self.assertEqual(g['not_disabled_literal'], 0)
        implicit = audit_xml_bytes(xml('<call node="Output" method="AddVIN"/>'))
        self.assertEqual(implicit['declared_identity_method_edges']['add_vin']['absent_disabled_attribute'], 1)

    def test_04_wrong_target_does_not_create_identity_edge(self):
        payload = call('AddVIN', target='Other') + call('SetX40Serial', target='Missing')
        report = audit_xml_bytes(xml(payload, nodes='<node nodeid="Other" class="ReadVinComponent"/>'))
        self.assertEqual(report['identity_method_calls_with_unresolved_target'], 1)
        self.assertEqual(report['identity_method_calls_to_non_identity_target'], 2)
        self.assertEqual(report['declared_identity_method_edges']['add_vin']['declared'], 0)
        self.assertEqual(report['declared_identity_method_edges']['set_x40_serial']['declared'], 0)

    def test_05_duplicate_id_and_missing_root_rejected(self):
        with self.assertRaises(ValueError): audit_xml_bytes(xml(nodes='<node nodeid="Output" class="VehicleIdentityOutput"/>'))
        with self.assertRaises(ValueError): audit_xml_bytes(b'<private><script/></private>')
        with self.assertRaises(ValueError): audit_xml_bytes(b'<script><nodes><node class="VehicleIdentityOutput"/></nodes></script>')

    def test_06_dtd_and_entity_are_rejected(self):
        malicious = b'<!DOCTYPE script [ <!ENTITY private "SYNTHETIC_VIN"> ]><script>&private;</script>'
        with self.assertRaises(ValueError): audit_xml_bytes(malicious)
        with self.assertRaises(ValueError): audit_xml_bytes(b"\xff\xfe" + malicious.decode().encode("utf-16le"))
        with self.assertRaises(ValueError): audit_xml_bytes(b'<script><missing></script>')

    def test_07_bounded_input_and_nested_structure(self):
        with self.assertRaises(ValueError): audit_xml_bytes(b'A' * (2 * 1024 * 1024 + 1))
        huge = b'<script>' + b'<a>' * 99 + b'</a>' * 99 + b'</script>'
        with self.assertRaises(ValueError): audit_xml_bytes(huge)
        self.assertGreater(MAX_ELEMENTS, 1000)

    def test_08_cli_redaction_exclusive_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            private = base / 'PRIVATE_VIN_AND_SCRIPT.xml'
            text = xml(call('AddVIN', payload='<parameter value="PRIVATE_YV1_SYNTHETIC"/>'))
            private.write_bytes(text)
            output = base / 'report.json'
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(private), '--output', str(output)])
            contents = output.read_text()
            for forbidden in ('PRIVATE_YV1_SYNTHETIC', 'PRIVATE_VIN', str(private), 'Reader', 'Output'):
                self.assertNotIn(forbidden, contents)
            self.assertEqual(json.loads(contents)['declared_identity_method_edges']['add_vin']['declared'], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): main([str(private), '--output', str(output)])
            other = base / 'symlink.xml'
            try:
                other.symlink_to(private)
            except (OSError, NotImplementedError):
                # Windows runners can disable creating symlinks without elevation.
                # CLI safety and redaction assertions above still ran.
                return
            with self.assertRaises(ValueError): audit_file(other)


if __name__ == '__main__':
    unittest.main()
