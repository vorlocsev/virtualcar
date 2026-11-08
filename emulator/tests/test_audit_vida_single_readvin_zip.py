"""Eight synthetic tests: one local VIDA ReadVin ZIP, no original data or SQL."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools"))
import audit_vida_single_readvin_zip as tool

POWER_SHELL = BASE / "scripts" / "Export-VidaSingleReadVinZip.ps1"
SAMPLE_XML = b"""<script><nodes>
<node nodeid="R" class="Components.ReadVinComponent"/>
<node nodeid="Output" class="Components.VehicleIdentityOutput"/>
</nodes><handlers><eventhandler node="R" name="Next">
<call node="Output" method="AddVIN" disabled="false"/>
</eventhandler></handlers><data id="F114">B9 FB</data></script>"""


def make_zip(folder, data=SAMPLE_XML, name="readvin", extra=None):
    path = Path(folder, "private.zip")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, data)
        if extra is not None:
            z.writestr("extra.xml", extra)
    return path


class SingleReadVinZipTests(unittest.TestCase):
    def test_01_bounded_positive_synthetic_graph_cannot_verify_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_zip(d)
            x = tool.audit(p)
            self.assertTrue(x["lexical_tokens_present_not_execution"]["b9fb"])
            self.assertTrue(x["lexical_tokens_present_not_execution"]["f114"])
            self.assertEqual(x["identity_xml_graph_declarations"]["readvin_component_count"], 1)
            self.assertEqual(x["identity_xml_graph_declarations"]["declared_identity_edges"]
                             ["add_vin"]["declared"], 1)
            self.assertFalse(x["vin_accepted_by_client"])
            self.assertFalse(x["script_selected_by_getscript_runtime"])
            self.assertFalse(x["replay_approved"])

    def test_02_no_identity_method_is_not_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_zip(d, b"<script><nodes/><handlers/></script>")
            x = tool.audit(p)
            self.assertFalse(any(x["lexical_tokens_present_not_execution"].values()))
            self.assertEqual(x["identity_xml_graph_declarations"]["declared_identity_edges"]
                             ["add_vin"]["declared"], 0)
            self.assertFalse(x["b9fb_to_vin_runtime_flow_verified"])

    def test_03_reject_multiple_zip_entries(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_zip(d, extra=b"<script/>")
            with self.assertRaises(ValueError):
                tool.audit(p)

    def test_04_reject_zip_path_traversal_and_bad_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_zip(d, name="../vin.xml")
            with self.assertRaises(ValueError):
                tool.audit(p)
            p.unlink()
            p = make_zip(d, name="manifest.exe")
            with self.assertRaises(ValueError):
                tool.audit(p)

    def test_05_reject_dtd_and_malformed_xml(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_zip(d, b'<!DOCTYPE script [<!ENTITY t "VIN">]><script>&t;</script>')
            with self.assertRaises(ValueError):
                tool.audit(p)
            p.unlink()
            p = make_zip(d, b"<script>")
            with self.assertRaises(ValueError):
                tool.audit(p)

    def test_06_bounded_decompression_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_zip(d, b"<script>" + b"A" * (1024 * 1024 + 1) + b"</script>")
            with self.assertRaises(ValueError):
                tool.audit(p)
            with self.assertRaises(ValueError):
                tool.audit(Path(d, "nonexistent.zip"))

    def test_07_cli_exclusive_output_and_identifier_privacy(self):
        with tempfile.TemporaryDirectory() as d:
            original = SAMPLE_XML.replace(b"</script>",
                b"<literal>YV1CZ0002A0000001</literal></script>")
            p = make_zip(d, original)
            output = Path(d, "report.json")
            with contextlib.redirect_stdout(io.StringIO()):
                tool.main([str(p), "--output", str(output)])
            raw = output.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.assertTrue(data["xml_zip_structure_validated"])
            for private in ("YV1CZ0002A0000001", str(p), "ReadVin.xml", "R"):
                if private == "R":
                    continue
                self.assertNotIn(private, raw)
            self.assertFalse(data["xc90_v8_my2009_identity_verified"])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                tool.main([str(p), "--output", str(output)])

    def test_08_sql_script_is_read_only_exactly_one_bounded_candidate(self):
        s = POWER_SHELL.read_text(encoding="utf-8")
        for required in ("COUNT_BIG(*)", "DATALENGTH(sc.XmlDataCompressed)",
                         "MaxBinaryLength = $maxArchive", "$maxArchive = 1048576",
                         "st.id = 7", "st.Description = N'ReadVin'",
                         "sc.fkLanguage =", "$count -ne 1",
                         "$bytes.Length -ne $length",
                         "[System.IO.FileMode]::CreateNew",
                         "Refusing original script export into Git repository.",
                         "Expected exactly one bounded ReadVin archive"):
            self.assertIn(required, s)
        self.assertEqual(s.count("Invoke-Sqlcmd @params -Query"), 2)
        self.assertNotIn("EXEC dbo.GetScript", s)
        self.assertNotIn("UPDATE dbo.", s)
        self.assertNotIn("Export-Csv", s)
        self.assertNotIn("WriteAllText", s)


if __name__ == "__main__":
    unittest.main()
