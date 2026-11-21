"""Synthetic-only CarCom tests: no original VIDA installation required."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from audit_vida_cem_d2_variant import CANDIDATE, VariantAuditError, inspect, main

TABLES = {
    "T111_Service": ("id","service","mode","fkT122_Protocol"),
    "T122_Protocol": ("id","identifier"),
    "T110_Service_EcuVariant": ("fkT100_EcuVariant","fkT111_Service"),
    "T100_EcuVariant": ("id","identifier","fkT101_Ecu"),
    "T101_Ecu": ("id",),
    "T160_DefaultEcuVariant": ("fkT161_Profile","fkT100_EcuVariant"),
    "T161_Profile": ("id","identifier"),
    "T120_Config_EcuVariant": ("fkT100_EcuVariant","fkT121_Config"),
    "T121_Config": ("id","commAddress","busRate","canIdTX","canIdRX","fkT122_Protocol","fkT123_Bus"),
    "T123_Bus": ("id","identifier"),
}


def dataset(folder, *, with_candidate=True, extra=None, bad_source=False):
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / "CarCom.sqlite"
    with closing(sqlite3.connect(file)) as db:
        db.execute("CREATE TABLE _vida_meta (key TEXT,value TEXT)")
        db.execute("CREATE TABLE _vida_tables (schema_name TEXT,table_name TEXT,rows_exported INTEGER)")
        db.execute("CREATE TABLE _vida_columns (schema_name TEXT,table_name TEXT,column_name TEXT,system_type_id INTEGER)")
        db.executemany("INSERT INTO _vida_meta VALUES (?,?)", (
            ("schema_version","virtualcar-vida-offline-sqlite-v1"),
            ("source_database","Wrong" if bad_source else "CarCom"),
            ("scope","all_user_tables"),
        ))
        for name, cols in TABLES.items():
            db.execute('CREATE TABLE "'+name+'" ('+
                       ','.join('"'+c+'" '+("TEXT" if c == "identifier" else "INTEGER") for c in cols)+')')
        def add(name,*rows):
            db.executemany('INSERT INTO "'+name+'" VALUES ('+
                           ','.join("?" for _ in rows[0])+')', rows)
        add("T101_Ecu",(9,))
        add("T122_Protocol",(11,"D2"),(12,"GGD"))
        add("T123_Bus",(1,"HS"),(2,"LS"))
        add("T100_EcuVariant",(33,CANDIDATE if with_candidate else "OTHER",9),
            (34,"30682825 A",9))
        add("T161_Profile",(14,"PRIVATE_PROFILE"))
        add("T160_DefaultEcuVariant",(14,33),(14,34))
        add("T111_Service",(21,166,1,11),(22,185,0,11),(23,163,0,11))
        add("T110_Service_EcuVariant",(33,21),(33,22),(33,23),(34,21))
        add("T121_Config",(70,80,None,1048574,18874371,11,1),
            (71,64,125000,1048574,8388611,11,2))
        add("T120_Config_EcuVariant",(33,70),(33,71),(34,70))
        for name, rows in (extra or {}).items():
            add(name,*rows)
        for name in TABLES:
            count=db.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0]
            db.execute("INSERT INTO _vida_tables VALUES (?,?,?)",("dbo",name,count))
            for column in db.execute('PRAGMA table_xinfo("'+name+'")'):
                db.execute("INSERT INTO _vida_columns VALUES (?,?,?,?)",
                           ("dbo",name,column[1],56))
        db.commit()
    return file


class D2CemVariantCatalogTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="cem-d2-synthetic-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.folder=self.root/"private"

    def test_01_exact_routes_and_services(self):
        dataset(self.folder)
        report=inspect(self.folder)
        self.assertTrue(report["variant_found_in_export"])
        self.assertEqual([x["comm_address"] for x in report["routes"]],[80,64])
        self.assertIsNone(report["routes"][0]["bus_rate"])
        self.assertEqual([x["service"] for x in report["services"]],[166,185,163])
        self.assertEqual(report["default_profile_link_count"],1)
        self.assertFalse(report["selected_by_live_vida"])
        self.assertFalse(report["replay_approved"])

    def test_02_absent_variant_not_vehicle_absence(self):
        dataset(self.folder,with_candidate=False)
        report=inspect(self.folder)
        self.assertFalse(report["variant_found_in_export"])
        self.assertEqual(report["routes"],[])
        self.assertFalse(report["exact_vehicle_variant_verified"])

    def test_03_duplicate_variant_rejected(self):
        dataset(self.folder,extra={"T100_EcuVariant":[(35,CANDIDATE,9)]})
        with self.assertRaises(VariantAuditError):
            inspect(self.folder)

    def test_04_duplicate_protocol_key_rejected(self):
        dataset(self.folder,extra={"T122_Protocol":[(11,"D2")]})
        with self.assertRaises(VariantAuditError):
            inspect(self.folder)

    def test_05_missing_physical_column_rejected(self):
        file=dataset(self.folder)
        with closing(sqlite3.connect(file)) as db:
            db.execute("ALTER TABLE T121_Config DROP COLUMN busRate")
            db.commit()
        with self.assertRaises(VariantAuditError):
            inspect(self.folder)

    def test_06_wrong_source_identity_rejected(self):
        dataset(self.folder,bad_source=True)
        with self.assertRaises(Exception):
            inspect(self.folder)

    def test_07_sqlite_sidecar_rejected(self):
        file=dataset(self.folder)
        Path(str(file)+"-wal").write_bytes(b"synthetic")
        with self.assertRaises(VariantAuditError):
            inspect(self.folder)

    def test_08_source_bytes_unchanged(self):
        file=dataset(self.folder)
        previous=hashlib.sha256(file.read_bytes()).digest()
        inspect(self.folder)
        self.assertEqual(previous,hashlib.sha256(file.read_bytes()).digest())

    def test_09_no_output_overwrite(self):
        dataset(self.folder)
        output=self.root/"existing.json"
        output.write_text("keep")
        self.assertEqual(main(["--folder",str(self.folder),"--output",str(output)]),2)
        self.assertEqual(output.read_text(),"keep")

    def test_10_exact_metadata_without_private_profile(self):
        dataset(self.folder)
        output=self.root/"report.json"
        self.assertEqual(main(["--folder",str(self.folder),"--output",str(output)]),0)
        data=output.read_text()
        self.assertIn(CANDIDATE,data)
        self.assertIn('"comm_address": 80',data)
        self.assertNotIn("PRIVATE_PROFILE",data)
        self.assertTrue(json.loads(data)["read_only"])

    def test_11_bulk_binary_value_rejected(self):
        file=dataset(self.folder)
        with closing(sqlite3.connect(file)) as db:
            db.execute("UPDATE T111_Service SET service=? WHERE id=21",
                       (sqlite3.Binary(b"\xff"*1024),))
            db.commit()
        with self.assertRaises(VariantAuditError):
            inspect(self.folder)

    def test_12_other_ggd_variant_not_in_report(self):
        dataset(self.folder)
        self.assertNotIn("GGD",json.dumps(inspect(self.folder)))

    def test_13_symlink_source_rejected(self):
        original=self.root/"original"
        dataset(original)
        self.folder.mkdir()
        try:
            (self.folder/"CarCom.sqlite").symlink_to(original/"CarCom.sqlite")
        except OSError as exc:
            if sys.platform == "win32" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("Symlinks unavailable without Windows privilege")
            raise
        with self.assertRaises(VariantAuditError):
            inspect(self.folder)

    def test_14_excessive_route_links_rejected(self):
        dataset(self.folder,extra={"T120_Config_EcuVariant":[(33,70)]*64})
        with self.assertRaises(VariantAuditError):
            inspect(self.folder)


if __name__ == "__main__":
    unittest.main()
