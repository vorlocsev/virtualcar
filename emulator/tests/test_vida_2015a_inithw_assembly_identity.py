"""Synthetic SHA-pinned CLR AssemblyRef/InterfaceImpl/MemberRef provenance."""
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
import audit_vida_2015a_inithw_assembly_identity as tool


def synthetic_pe(*, repo=False, assembly_name="Demo.Contracts",
                 namespace="Demo.Diagnostics", version=(1, 2, 3, 4),
                 key=b"\xAB\xCD", typeref_assembly_row=1,
                 with_manifest=False, local_interface=False):
    names = bytearray(b"\x00")
    indices = {}
    for s in ("ICarComRepository", "CarComRepository", "GetInitHwSettings",
              namespace, assembly_name):
        if s in indices:
            continue
        indices[s] = len(names)
        names.extend(s.encode("utf-8") + b"\x00")
    # Bounded synthetic compressed #Blob length, one-based first blob index.
    if not 0 < len(key) < 128:
        raise ValueError("fixture public key extent")
    blobs = b"\x00" + bytes([len(key)]) + key + b"\x03\x20\x01\x01"
    # Module 0, TypeRef 1, TypeDef 2, InterfaceImpl 9,
    # MemberRef 10, AssemblyRef 35. Tests use only a few real tables.
    tables_present = [1, 35]
    if repo:
        tables_present += [2, 9]
    else:
        tables_present += [10]
    if with_manifest:
        tables_present += [32]
    valid = sum(1 << t for t in tables_present)
    data = bytearray(struct.pack("<IBBBBQQ", 0, 2, 0, 0, 1, valid, 0))
    for tab in sorted(tables_present):
        data.extend(struct.pack("<I", 2 if tab == 2 and local_interface else 1))
    for tab in sorted(tables_present):
        if tab == 1:
            ref_scope = (typeref_assembly_row << 2) | 2
            data.extend(struct.pack("<HHH", ref_scope,
                                    indices["ICarComRepository"],
                                    indices[namespace]))
        elif tab == 2:
            data.extend(struct.pack("<IHHHHH", 0,
                                    indices["CarComRepository"],
                                    indices[namespace], 0, 1, 1))
            if local_interface:
                data.extend(struct.pack("<IHHHHH", 0,
                                        indices["ICarComRepository"],
                                        indices[namespace], 0, 1, 1))
        elif tab == 9:
            data.extend(struct.pack("<HH", 1,
                                    (2 << 2) if local_interface else (1 << 2) | 1))
        elif tab == 10:
            data.extend(struct.pack("<HHH", (1 << 3) | 1,
                                    indices["GetInitHwSettings"], 5))
        elif tab == 32:
            data.extend(struct.pack("<IHHHHIHHH", 0, *version,
                                    1 if key else 0, 1,
                                    indices[assembly_name], 0))
        elif tab == 35:
            data.extend(struct.pack("<HHHHIHHHH",
                                    *version, 0, 1,
                                    indices[assembly_name], 0, 0))
    # Metadata root with three streams. All offsets relative to metadata.
    version_str = b"v4.0.30319\x00"
    version_str += b"\x00" * (-len(version_str) % 4)
    meta = bytearray(b"BSJB" + struct.pack("<HHII", 1, 1, 0,
                       len(version_str)) + version_str +
                     struct.pack("<HH", 0, 3))
    labels = []
    for x in (b"#~", b"#Strings", b"#Blob"):
        n = x + b"\x00"
        labels.append(n + b"\x00" * (-len(n) % 4))
    off = len(meta) + sum(8 + len(x) for x in labels)
    for buf, name in ((data, labels[0]), (names, labels[1]), (blobs, labels[2])):
        meta.extend(struct.pack("<II", off, len(buf)) + name)
        off += len(buf)
    meta.extend(data)
    meta.extend(names)
    meta.extend(blobs)

    pe = bytearray(0x1800)
    pe[:2] = b"MZ"
    struct.pack_into("<I", pe, 0x3C, 0x80)
    pe[0x80:0x84] = b"PE\x00\x00"
    coff = 0x84
    struct.pack_into("<H", pe, coff + 2, 1)
    struct.pack_into("<H", pe, coff + 16, 0xE0)
    opt = coff + 20
    struct.pack_into("<H", pe, opt, 0x10B)
    struct.pack_into("<II", pe, opt + 96 + 14 * 8, 0x2000, 72)
    sect = opt + 0xE0
    struct.pack_into("<IIII", pe, sect + 8, 0x1000, 0x2000, 0x1000, 0x200)
    struct.pack_into("<IHHII", pe, 0x200, 72, 2, 5, 0x2100, len(meta))
    pe[0x300:0x300 + len(meta)] = meta
    return bytes(pe)


def triplet(*, repo_name="Demo.Contracts", call1_name="Demo.Contracts",
            call2_name="Demo.Contracts", repo_namespace="Demo.Diagnostics",
            call_namespace="Demo.Diagnostics", versions=None):
    if versions is None:
        versions = ((1, 2, 3, 4),) * 3
    return {
        "bizservices.carcom.db.dll": tool._table_layout(
            synthetic_pe(repo=True, assembly_name=repo_name,
                         namespace=repo_namespace, version=versions[0])
        ),
        "bizservices.vehiclecommprovider.dll": tool._table_layout(
            synthetic_pe(assembly_name=call1_name,
                         namespace=call_namespace, version=versions[1])
        ),
        "workflow.dll": tool._table_layout(
            synthetic_pe(assembly_name=call2_name,
                         namespace=call_namespace, version=versions[2])
        ),
    }


class OriginalAssemblyRefTests(unittest.TestCase):
    def test_01_all_three_metadata_sources_match(self):
        counts = tool._compare_private(triplet())
        self.assertEqual(counts["repository_interfaceimpl_candidates"], 1)
        self.assertEqual(counts["caller_interface_memberref_candidates"], 2)
        self.assertEqual(counts["stored_full_typename_equal"], 2)
        self.assertEqual(counts["stored_assemblyref_identity_equal"], 2)
        self.assertEqual(counts["stored_assemblyref_identity_different"], 0)

    def test_02_same_fullname_different_assembly_name_detected(self):
        counts = tool._compare_private(triplet(call2_name="Other.Contracts"))
        self.assertEqual(counts["stored_full_typename_equal"], 2)
        self.assertEqual(counts["stored_assemblyref_identity_equal"], 1)
        self.assertEqual(counts["stored_assemblyref_identity_different"], 1)

    def test_03_same_fullname_different_version_detected(self):
        counts = tool._compare_private(triplet(
            versions=((1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 5))
        ))
        self.assertEqual(counts["stored_assemblyref_identity_equal"], 1)
        self.assertEqual(counts["stored_assemblyref_identity_different"], 1)

    def test_04_namespace_difference_explicitly_counted(self):
        counts = tool._compare_private(triplet(call_namespace="Alternate.Diagnostics"))
        self.assertEqual(counts["stored_full_typename_different"], 2)

    def test_05_assemblyref_not_exported(self):
        report = json.dumps(tool._compare_private(triplet()))
        for private_value in ("Demo.Contracts", "Demo.Diagnostics", "ICarComRepository",
                              "GetInitHwSettings", "ABCD", '"1, 2, 3, 4"'):
            self.assertNotIn(private_value, report)

    def test_06_assemblyref_public_key_byte_difference(self):
        metadata = triplet()
        metadata["workflow.dll"] = tool._table_layout(
            synthetic_pe(assembly_name="Demo.Contracts", key=b"\x12\x34")
        )
        counts = tool._compare_private(metadata)
        self.assertEqual(counts["stored_assemblyref_identity_different"], 1)

    def test_07_zero_or_unmapped_assemblyref_row_stops(self):
        meta = tool._table_layout(synthetic_pe(
            typeref_assembly_row=4
        ))
        with self.assertRaises(tool.MetadataError):
            tool._caller_interface_memberrefs(meta)

    def test_08_wrong_interface_typename_refuses_comparison(self):
        m = triplet()
        # Replace a unique known original name in synthetic #Strings,
        # preserving exact byte extent to keep PE layout stable.
        fake = synthetic_pe()
        self.assertEqual(len(b"ICarComRepository"), len(b"InvalidRepository"))
        fake = fake.replace(b"ICarComRepository", b"InvalidRepository", 1)
        m["workflow.dll"] = tool._table_layout(fake)
        with self.assertRaises(tool.MetadataError):
            tool._compare_private(m)

    def test_09_duplicate_local_interface_definition_rejected(self):
        repo = triplet()["bizservices.carcom.db.dll"]
        first_row = repo["row"](9, 1)
        old_row = repo["row"]
        repo["counts"][9] = 2
        repo["row"] = lambda tid, index: (
            first_row if tid == 9 and index == 2 else old_row(tid, index)
        )
        with self.assertRaises(tool.MetadataError):
            tool._repository_interface(repo)

    def test_10_no_runtime_interface_claims(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = {
                "BizServices.CarCom.DB.DLL": synthetic_pe(repo=True),
                "BizServices.VehicleCommProvider.DLL": synthetic_pe(),
                "Workflow.DLL": synthetic_pe(),
            }
            pins = {}
            for filename, content in data.items():
                (root / filename).write_bytes(content)
                pins[filename.casefold()] = (filename, hashlib.sha256(content).hexdigest())
            with patch.object(tool, "EXPECTED", pins):
                out = tool.audit(root)
            self.assertEqual(out["counts"]["stored_assemblyref_identity_equal"], 2)
            for k in ("original_assemblies_loaded_or_executed",
                      "assemblyref_tuple_equality_proves_loaded_assembly_identity",
                      "assemblyref_tuple_equality_proves_interface_method_dispatch",
                      "original_methodimpl_dispatch_verified",
                      "original_vida_2015a_profile_list_proven",
                      "original_vida_2015a_generic_profile_inheritance_verified",
                      "d2_baudrate_verified", "original_vida_readvin_accepted"):
                self.assertFalse(out[k])
            self.assertNotIn(str(root), json.dumps(out))

    def test_11_wrong_SHA_pin_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pins = {}
            for filename in ("BizServices.CarCom.DB.DLL",
                             "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / filename).write_bytes(synthetic_pe())
                pins[filename.casefold()] = (filename, "0" * 64)
            with patch.object(tool, "EXPECTED", pins):
                with self.assertRaisesRegex(tool.MetadataError, "SHA256 mismatch"):
                    tool.audit(root)

    def test_12_cli_error_sanitized(self):
        with tempfile.TemporaryDirectory() as d:
            err = StringIO()
            with redirect_stderr(err):
                code = tool.main(["--folder", str(Path(d) / "not-there")])
            self.assertEqual(code, 2)
            self.assertEqual(set(json.loads(err.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, err.getvalue())


if __name__ == "__main__":
    unittest.main()
