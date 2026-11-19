"""Synthetic CLR PE/metadata fixtures; tests never open original VIDA DLLs."""
from contextlib import redirect_stderr
from io import StringIO
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_2015a_inithw_metadata as tool


def _synthetic_cli() -> bytes:
    strings = bytearray(b"\x00")
    ids = {}
    for name in ("CarComRepository", "GetInitHwSettings",
                 "GetHwSettings", "vadis_GetHwSettings"):
        ids[name] = len(strings)
        strings.extend(name.encode("utf-8") + b"\x00")
    # Table order: Module(0), TypeDef(2), MethodDef(6), MemberRef(10).
    valid = sum(1 << tid for tid in (0, 2, 6, 10))
    tables = bytearray(struct.pack("<IBBBBQQ", 0, 2, 0, 0, 1, valid, 0))
    tables.extend(struct.pack("<IIII", 1, 1, 3, 2))
    tables.extend(struct.pack("<HHHHH", 0, 0, 0, 0, 0))
    tables.extend(struct.pack("<IHHHHH", 0, ids["CarComRepository"], 0, 0, 1, 1))
    for method in ("GetInitHwSettings", "GetHwSettings", "vadis_GetHwSettings"):
        tables.extend(struct.pack("<IHHHHH", 0, 0, 0, ids[method], 0, 1))
    for member in ("GetInitHwSettings", "GetHwSettings"):
        # MemberRefParent coded index: TypeDef row 1 tagged 0 => 8.
        tables.extend(struct.pack("<HHH", 8, ids[member], 0))
    version = b"v4.0.30319\x00"
    version += b"\x00" * (-len(version) % 4)
    root = bytearray(b"BSJB" + struct.pack("<HHII", 1, 1, 0, len(version)) +
                     version + struct.pack("<HH", 0, 2))
    names = []
    for name in (b"#~", b"#Strings"):
        name += b"\x00"
        name += b"\x00" * (-len(name) % 4)
        names.append(name)
    header_size = sum(8 + len(name) for name in names)
    first = len(root) + header_size
    for off, data, name in (
        (first, tables, names[0]),
        (first + len(tables), strings, names[1]),
    ):
        root.extend(struct.pack("<II", off, len(data)) + name)
    root.extend(tables)
    root.extend(strings)

    # Minimal, unexecutable one-section managed PE32 metadata shape.
    binary = bytearray(0x1200)
    binary[:2] = b"MZ"
    struct.pack_into("<I", binary, 0x3C, 0x80)
    binary[0x80:0x84] = b"PE\x00\x00"
    coff = 0x84
    struct.pack_into("<H", binary, coff + 2, 1)
    struct.pack_into("<H", binary, coff + 16, 0xE0)
    opt = coff + 20
    struct.pack_into("<H", binary, opt, 0x10B)
    struct.pack_into("<II", binary, opt + 96 + 14 * 8, 0x2000, 72)
    section = opt + 0xE0
    struct.pack_into("<IIII", binary, section + 8, 0x1000, 0x2000, 0x1000, 0x200)
    struct.pack_into("<IHHII", binary, 0x200, 72, 2, 5, 0x2100, len(root))
    binary[0x300:0x300 + len(root)] = root
    return bytes(binary)


class VidaOriginalMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pe = _synthetic_cli()

    def test_01_real_methoddefs_distinct_from_memberrefs(self):
        r = tool.parse_metadata(self.pe)
        self.assertEqual(r["carcom_repository_typedef_count"], 1)
        self.assertEqual(r["target_methoddef_counts"], {
            "GetInitHwSettings": 1,
            "GetHwSettings": 1,
            "vadis_GetHwSettings": 1,
        })
        self.assertEqual(r["target_memberref_name_counts"], {
            "GetInitHwSettings": 1,
            "GetHwSettings": 1,
            "vadis_GetHwSettings": 0,
        })
        self.assertEqual(r["target_methoddefs_in_carcom_repository"]["GetInitHwSettings"], 1)

    def test_02_ascii_string_alone_is_not_methoddef(self):
        with self.assertRaises(tool.MetadataError):
            tool.parse_metadata(b"MZ" + b"\x00" * 400 + b"GetInitHwSettings")

    def test_03_pe_signature_required(self):
        bad = bytearray(self.pe)
        bad[0x80:0x84] = b"fake"
        with self.assertRaises(tool.MetadataError):
            tool.parse_metadata(bytes(bad))

    def test_04_metadata_magic_required(self):
        bad = bytearray(self.pe)
        bad[0x300:0x304] = b"nope"
        with self.assertRaises(tool.MetadataError):
            tool.parse_metadata(bytes(bad))

    def test_05_truncated_pe_rejected(self):
        with self.assertRaises(tool.MetadataError):
            tool.parse_metadata(self.pe[:0x330])

    def test_06_no_directory_scan_of_original_via_parser(self):
        self.assertNotIn(str(self.root), repr(tool.parse_metadata(self.pe)))

    def _mock_pins(self):
        digest = hashlib.sha256(self.pe).hexdigest()
        return {
            "bizservices.carcom.db.dll": ("BizServices.CarCom.DB.DLL", digest),
            "bizservices.vehiclecommprovider.dll":
                ("BizServices.VehicleCommProvider.DLL", digest),
            "workflow.dll": ("Workflow.DLL", digest),
        }

    def _create_pinned_files(self):
        for _, (name, _) in self._mock_pins().items():
            (self.root / name).write_bytes(self.pe)

    def test_07_three_pinned_managed_sources_verified(self):
        self._create_pinned_files()
        with patch.object(tool, "EXPECTED", self._mock_pins()):
            r = tool.audit(self.root)
        self.assertEqual(r["pinned_original_assemblies_verified"], 3)
        self.assertEqual(len(r["results"]), 3)
        self.assertTrue(all(x["target_methoddefs_in_carcom_repository"]["GetInitHwSettings"] == 1
                            for x in r["results"]))
        self.assertFalse(r["assemblies_loaded_or_executed"])
        self.assertFalse(r["il_call_instructions_inspected"])
        self.assertFalse(r["memberref_name_proves_actual_callsite"])

    def test_08_unauthorized_hash_fails_closed(self):
        self._create_pinned_files()
        wrong = dict(self._mock_pins())
        name, _ = wrong["workflow.dll"]
        wrong["workflow.dll"] = (name, "0" * 64)
        with patch.object(tool, "EXPECTED", wrong):
            with self.assertRaises(tool.MetadataError):
                tool.audit(self.root)

    def test_09_missing_pinned_dll_fails_closed(self):
        self._create_pinned_files()
        (self.root / "Workflow.DLL").unlink()
        with patch.object(tool, "EXPECTED", self._mock_pins()):
            with self.assertRaises(tool.MetadataError):
                tool.audit(self.root)

    def test_10_duplicate_basename_fails_closed(self):
        self._create_pinned_files()
        folder = self.root / "other"
        folder.mkdir()
        (folder / "Workflow.DLL").write_bytes(self.pe)
        with patch.object(tool, "EXPECTED", self._mock_pins()):
            with self.assertRaises(tool.MetadataError):
                tool.audit(self.root)

    def test_11_synthetic_hashes_and_paths_do_not_leak_directory(self):
        self._create_pinned_files()
        with patch.object(tool, "EXPECTED", self._mock_pins()):
            s = json.dumps(tool.audit(self.root))
        self.assertNotIn(str(self.root), s)
        self.assertNotIn("BSJB", s)
        self.assertNotIn('"folder":"', s)

    def test_12_invalid_folder_cli_error_contains_only_class(self):
        output = StringIO()
        with redirect_stderr(output):
            status = tool.main(["--folder", str(self.root / "missing")])
        self.assertEqual(status, 2)
        self.assertEqual(set(json.loads(output.getvalue())), {"status", "error_class"})
        self.assertNotIn(str(self.root), output.getvalue())

    def test_13_never_equates_memberref_to_callsite_or_runtime(self):
        self._create_pinned_files()
        with patch.object(tool, "EXPECTED", self._mock_pins()):
            r = tool.audit(self.root)
        self.assertFalse(r["memberref_name_proves_actual_callsite"])
        self.assertFalse(r["original_vida_2015a_profile_list_callers_verified"])
        self.assertFalse(r["original_vida_2015a_inheritance_verified"])
        self.assertFalse(r["d2_baudrate_verified"])
        self.assertFalse(r["original_vida_readvin_accepted"])


if __name__ == "__main__":
    unittest.main()
