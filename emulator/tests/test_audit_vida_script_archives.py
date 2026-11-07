"""Eight synthetic groups for read-only VIDA script lexical triage."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_script_archives import audit, main, _lexical_flags, MAX_XML_BYTES


def make_zip(path, xml, name="script.xml"):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, xml)


class VidaScriptArchiveAuditTests(unittest.TestCase):
    def test_01_valid_b9fb_only_cannot_prove_identity(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "one.xml").write_text("<script><send>B9 FB</send></script>")
            result = audit(d)
            self.assertEqual(result["script_counts_with_lexical_tokens"]["b9fb"], 1)
            self.assertFalse(result["b9fb_to_identity_control_flow_verified"])
            self.assertFalse(result["replay_approved"])

    def test_02_compressed_xml_and_addvin_only_lexical(self):
        with tempfile.TemporaryDirectory() as d:
            make_zip(Path(d, "one.zip"), '<s><a code="0xB9FB"/><f>AddVIN</f></s>', 'script-guid')
            result = audit(d)
            self.assertEqual(result["same_script_b9fb_addvin_lexical_cooccurrence"], 1)
            self.assertFalse(result["script_selection_verified"])

    def test_03_comment_does_not_trigger_marker(self):
        flags = _lexical_flags(b"<s><!-- B9FB AddVIN --><a>normal</a></s>")
        self.assertFalse(any(flags.values()))

    def test_04_other_services_and_x40_separate(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "one.xml").write_text("<s><a>B9F0</a><b>B9FC</b><c>SetX40Serial</c></s>")
            result = audit(d)
            counts = result["script_counts_with_lexical_tokens"]
            self.assertEqual((counts["b9f0"], counts["b9fc"], counts["setx40serial"]), (1, 1, 1))
            self.assertEqual(result["same_script_b9fb_x40_lexical_cooccurrence"], 0)

    def test_05_reject_unsafe_zip_structures(self):
        with tempfile.TemporaryDirectory() as d:
            one = Path(d, "test.zip")
            make_zip(one, "<a/>", "../script.xml")
            with self.assertRaises(ValueError): audit(d)
            one.unlink()
            with zipfile.ZipFile(one, "w") as z:
                z.writestr("a.xml", "<a/>")
                z.writestr("b.xml", "<b/>")
            with self.assertRaises(ValueError): audit(d)

    def test_06_reject_dtd_malformed_and_overlimit(self):
        with tempfile.TemporaryDirectory() as d:
            xml = Path(d, "script.xml")
            for payload in ('<!DOCTYPE s [<!ENTITY x "z">]><s>&x;</s>', '<s>', 'a' * (MAX_XML_BYTES + 1)):
                xml.write_text(payload)
                with self.assertRaises(ValueError): audit(d)

    def test_07_no_files_symlinks_and_too_many(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): audit(d)
            for n in range(257):
                Path(d, f"{n:03}.xml").write_text("<s/>")
            with self.assertRaises(ValueError): audit(d)

    def test_08_cli_privacy_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, "PRIVATE-DO-NOT-SHARE")
            src.mkdir()
            make_zip(src / "VIN_YV1CZ0002A0000001.zip", "<s><a>B9FB</a><b>YV1CZ0002A0000001</b></s>")
            dest = Path(d, "SAFE-ONLY.json")
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(src), "--output", str(dest)])
            content = dest.read_text()
            for token in ("YV1CZ", "PRIVATE", "VIN_", "script.xml", str(src)):
                self.assertNotIn(token, content)
            self.assertEqual(json.loads(content)["processed_script_count"], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(src), "--output", str(dest)])


if __name__ == "__main__":
    unittest.main()
