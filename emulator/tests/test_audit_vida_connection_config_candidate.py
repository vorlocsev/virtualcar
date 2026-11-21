"""Synthetic tests for offline VIDA connection-mode config candidate; no original client."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_connection_config_candidate as tool
sys.path.pop(0)


def document(mode="NoCommConnection", client="false", *, attr="key"):
    return (f'<diagnostic><settings>'
            f'<add {attr}="UseClientSettings" value="{client}"/>'
            f'<add {attr}="DiagnosticConnection" value="{mode}"/>'
            f'<add key="PrivateToken" value="SENSITIVE_SHOULD_NEVER_LEAK"/>'
            f'</settings></diagnostic>').encode("utf-8")


class VidaConnectionConfigCandidateTests(unittest.TestCase):
    def test_01_no_comm_is_only_a_conditional_hazard(self):
        report = tool.classify_bytes(document())
        self.assertEqual(report["mode_candidate"], "NoCommConnection")
        self.assertTrue(report["no_comm_candidate_if_loaded"])
        self.assertFalse(report["j2534_candidate_if_loaded"])
        self.assertFalse(report["use_client_settings_candidate"])
        for field in (
            "client_or_server_config_path_selected_at_runtime_verified",
            "original_vida_process_loaded_this_file_verified",
            "actual_diagnostic_connection_mode_verified",
            "j2534_connect_or_messages_verified",
            "original_vida_readvin_executed_verified",
            "original_vida_vin_accepted_verified",
            "ecu_identity_accepted_verified",
        ):
            self.assertIs(report[field], False)
        self.assertNotIn("SENSITIVE_SHOULD_NEVER_LEAK", json.dumps(report))

    def test_02_j2534_candidate_not_promoted_to_runtime(self):
        report = tool.classify_bytes(document("J2534DiagnosticConnection", "true"))
        self.assertTrue(report["j2534_candidate_if_loaded"])
        self.assertTrue(report["use_client_settings_candidate"])
        self.assertFalse(report["actual_diagnostic_connection_mode_verified"])
        self.assertFalse(report["original_vida_vin_accepted_verified"])

    def test_03_other_known_modes_and_value_named_tags(self):
        for mode in ("DiCEDiagnosticConnection", "VirtualDiagnosticConnection"):
            with self.subTest(mode=mode):
                xml = (f'<diag><UseClientSettings value="false"/>'
                       f'<DiagnosticConnection value="{mode}"/></diag>').encode()
                report = tool.classify_bytes(xml)
                self.assertEqual(report["mode_candidate"], mode)
                self.assertFalse(report["no_comm_candidate_if_loaded"])
                self.assertFalse(report["j2534_candidate_if_loaded"])

    def test_04_duplicate_and_conflicting_keys_rejected(self):
        for raw in (
            document().replace(b"</settings>", b'<add key="DiagnosticConnection" value="NoCommConnection"/></settings>'),
            b'<diag><add key="DiagnosticConnection" name="UseClientSettings" value="NoCommConnection"/></diag>',
            b'<diag><UseClientSettings value="false"/><add key="UseClientSettings" value="true"/>'
            b'<DiagnosticConnection value="NoCommConnection"/></diag>',
        ):
            with self.subTest(case=raw[:24]):
                with self.assertRaises(tool.CandidateError):
                    tool.classify_bytes(raw)

    def test_05_missing_or_invalid_settings_fail_closed(self):
        for raw in (
            b'<diag><add key="DiagnosticConnection" value="NoCommConnection"/></diag>',
            document(client="maybe"),
            document(client=""),
            b'broken XML>',
            b'',
            b'<diag><DiagnosticConnection>NoCommConnection</DiagnosticConnection>'
            b'<UseClientSettings>true</UseClientSettings></diag>',
        ):
            with self.subTest(case=raw[:15]):
                with self.assertRaises(tool.CandidateError):
                    tool.classify_bytes(raw)

    def test_06_unknown_mode_stays_redacted_not_accepted(self):
        raw = document(mode="REAL_VIN_SECRET_UNSUPPORTED_MODE")
        report = tool.classify_bytes(raw)
        serial = json.dumps(report)
        self.assertEqual(report["mode_candidate"], "unrecognized_mode")
        self.assertNotIn("REAL_VIN_SECRET", serial)
        self.assertFalse(report["j2534_candidate_if_loaded"])

    def test_07_xml_dtd_entities_and_node_limit_rejected(self):
        raw = b'<!DOCTYPE x [<!ENTITY foo SYSTEM "file:///private">]>' + document()
        with self.assertRaises(tool.CandidateError):
            tool.classify_bytes(raw)
        oversized_nodes = (b'<diag>' + b'<x/>' * (tool.MAX_ELEMENTS + 1)
                           + b'<UseClientSettings value="false"/>'
                           + b'<DiagnosticConnection value="NoCommConnection"/></diag>')
        with self.assertRaises(tool.CandidateError):
            tool.classify_bytes(oversized_nodes)

    def test_08_explicit_named_file_only_and_no_stdout_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            cfg = folder / "diagnostic.config.xml"
            cfg.write_bytes(document(attr="name"))
            r = tool.classify_path(cfg)
            self.assertEqual(r["mode_candidate"], "NoCommConnection")
            out = io.StringIO()
            err = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(tool.main(["--candidate", str(cfg)]), 0)
            output = out.getvalue()
            self.assertNotIn(str(folder), output)
            self.assertNotIn("SENSITIVE_SHOULD_NEVER_LEAK", output)
            self.assertIn('"original_vida_vin_accepted_verified": false', output)
            wrong = folder / "private.ini"
            wrong.write_bytes(document())
            with self.assertRaises(tool.CandidateError):
                tool.classify_path(wrong)
            link = folder / "other" / "diagnostic.config.xml"
            link.parent.mkdir()
            try:
                link.symlink_to(cfg)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(tool.CandidateError):
                    tool.classify_path(link)

    def test_09_big_candidate_rejected_without_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "diagnostic.config.xml"
            cfg.write_bytes(b"x" * (tool.MAX_BYTES + 1))
            with self.assertRaises(tool.CandidateError):
                tool.classify_path(cfg)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = tool.main(["--candidate", str(cfg)])
            self.assertEqual(code, 2)
            self.assertNotIn(str(cfg), err.getvalue())

    def test_10_xml_namespaces_do_not_hide_duplicates(self):
        raw = (b'<root xmlns:x="urn:x">'
               b'<x:UseClientSettings value="false"/>'
               b'<x:DiagnosticConnection value="NoCommConnection"/>'
               b'<DiagnosticConnection value="J2534DiagnosticConnection"/></root>')
        with self.assertRaises(tool.CandidateError):
            tool.classify_bytes(raw)


if __name__ == "__main__":
    unittest.main()
