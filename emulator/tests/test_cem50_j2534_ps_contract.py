"""Static source/fixture contracts for isolated J2534-2 CEM50 implementation.

This file cannot certify Windows J2534 ABI correctness, PS native runtime,
VIDA ReadVin, ECU identity, or hardware. Native C host tests are separate.
"""
import configparser
import re
from pathlib import Path
import unittest

EMULATOR = Path(__file__).resolve().parents[1]
SOURCE = EMULATOR / "src" / "virtualcar.c"
TEST_SOURCE = EMULATOR / "tests" / "virtualcar_test.c"
PROFILE = EMULATOR / "adapters" / "cem50" / "virtualcar.ini"
INSTALLER = EMULATOR / "adapters" / "cem50" / "Install-J2534CEM50.ps1"

class CEM50PSContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = SOURCE.read_text(encoding="utf-8")
        cls.ct = TEST_SOURCE.read_text(encoding="utf-8")
        cls.ini = PROFILE.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")

    def test_01_explicit_opt_in_in_single_cem50_profile(self):
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(self.ini)
        self.assertEqual(ini.get("J2534_2", "Enabled"), "1")
        self.assertEqual(ini.get("Vehicle", "VIN"), "YV1CR855691511566")
        self.assertEqual(ini.get("D2_50", "B9FBFrameCount"), "13")
        self.assertEqual(ini.get("D2_50", "ResponseId"), "01200003")
        self.assertIn('"J2534_2","Enabled","0"', self.c)
        self.assertIn("g_j2534_ps_enabled=0;", self.c)

    def test_02_verified_standard_ps_constants(self):
        for token in (
            "#define PROTO_CAN_PS 0x8004u",
            "#define PROTO_ISO15765_PS 0x8005u",
            "#define CONFIG_J1962_PINS 0x8001u",
            "#define PINS_CAN_HS 0x060Eu",
            "#define PINS_CAN_MS 0x030Bu",
        ):
            self.assertIn(token, self.c)

    def test_03_legacy_transport_and_ps_external_protocol_ids_are_distinct(self):
        self.assertIn("g_ch[i].protocol=canonical_protocol(protocol);", self.c)
        self.assertIn("g_ch[i].api_protocol=protocol;", self.c)
        self.assertIn("msg->ProtocolID=c->api_protocol?c->api_protocol:c->protocol;", self.c)
        self.assertIn("m->ProtocolID!=(c->api_protocol?c->api_protocol:c->protocol)", self.c)
        self.assertIn("pattern->ProtocolID!=(c->api_protocol?c->api_protocol:c->protocol)", self.c)

    def test_04_ps_rejected_without_explicit_profile(self):
        self.assertIn("g_j2534_ps_enabled && is_ps_protocol(protocol)", self.c)
        self.assertIn("PassThruConnect(dev,PROTO_CAN_PS,0,500000u,&can)==ERR_INVALID_PROTOCOL_ID", self.ct)
        self.assertIn("PassThruConnect(dev,PROTO_ISO15765_PS,0,500000u,&iso)==ERR_INVALID_PROTOCOL_ID", self.ct)

    def test_05_no_ps_tx_without_j1962_pins(self):
        self.assertIn("if(is_ps_protocol(c->api_protocol) && !c->ps_pins)return ERR_PIN_INVALID;", self.c)
        self.assertIn("PassThruWriteMsgs(can,&tx,&n,0)==ERR_PIN_INVALID", self.ct)
        self.assertIn("if(is_ps_protocol(c->api_protocol) && !c->ps_pins)return;", self.c)

    def test_06_invalid_pins_and_baud_fail_atomically(self):
        self.assertIn("cfg->Value!=PINS_CAN_HS && cfg->Value!=PINS_CAN_MS", self.c)
        self.assertIn("desired_pins==PINS_CAN_HS && desired_baud!=500000u", self.c)
        self.assertIn("desired_pins==PINS_CAN_MS && desired_baud!=125000u", self.c)
        self.assertLess(self.c.index("U32 initial_baud=c->baud,desired_baud=c->baud"), self.c.index("c->ps_pins=cfg->Value;"))
        self.assertIn("if(c->ps_pins && desired_pins!=c->ps_pins)", self.c)
        self.assertIn("ERR_CHANNEL_IN_USE", self.ct)

    def test_07_exact_13_frame_ps_fixture_and_no_ms_leak(self):
        self.assertIn("d->frame_count=13u;d->baud=500000u", self.ct)
        self.assertIn("g_d2[2]=old_fixture", self.ct)
        self.assertIn("rx.ProtocolID==PROTO_CAN_PS && rx.DataSize==12u", self.ct)
        self.assertIn("PassThruReadMsgs(ms,&rx,&n,0)==ERR_BUFFER_EMPTY", self.ct)
        self.assertIn("test_j2534_ps_cem50(dev);", self.ct)

    def test_08_iso15765_ps_keeps_external_id(self):
        self.assertIn("PassThruConnect(dev,PROTO_ISO15765_PS,0,500000u,&iso)==ERR_OK", self.ct)
        self.assertIn("rx.ProtocolID==PROTO_ISO15765_PS", self.ct)
        self.assertIn("rx.Data[4]==0x62u && rx.Data[5]==0xF1u && rx.Data[6]==0x90u", self.ct)

    def test_09_existing_provider_not_falsely_relabelled_as_ps(self):
        # Current installed CEM50 registration deliberately remains J2534-1
        # until a separate PS-native Windows proof and new installer are reviewed.
        self.assertNotIn("$key.SetValue('CAN_PS'", self.installer)
        self.assertNotIn("$key.SetValue('ISO15765_PS'", self.installer)
        self.assertIn("J2534 Diagnostic Interface CEM50", self.installer)

    def test_10_readonly_boundaries_remain(self):
        self.assertIn("PassThruSetProgrammingVoltage", self.c)
        self.assertIn("(void)voltage;return error(ERR_NOT_SUPPORTED)", self.c)
        self.assertIn("B9FBFrameCount = 0", self.ini)
        self.assertIn("FixtureAuthority = synthetic_lab_not_oem_attested", self.ini)
        self.assertIn("Enabled = 0", self.ini)

    def test_11_native_ps_smoke_exact_matrix_equals_published_ini(self):
        native = (EMULATOR / "adapters" / "cem50" /
                  "Verify-J2534CEM50-PS.ps1").read_text(encoding="utf-8")
        self.assertIn("PassThruConnect(dev,0x8004u", native)
        self.assertIn("Pins(can,0x060Eu)", native)
        self.assertIn("Pins(ms,0x030Bu)", native)
        self.assertIn("r.ProtocolID==0x8004u", native)
        self.assertIn("CEM50_PS_NATIVE_PASS", native)
        self.assertNotIn("CreateSubKey", native)
        matrix_match = re.search(
            r"Frames=new byte\[13,8\] \{([\s\S]*?)\n \};", native)
        self.assertIsNotNone(matrix_match, "Expected literal native 13x8 fixture")
        matrix = [
            bytes(int(part.strip(), 16) for part in row.split(","))
            for row in re.findall(r"\{([^{}]+)\}", matrix_match.group(1))
        ]
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        config.read_string(self.ini)
        expected = [
            bytes.fromhex(config.get("D2_50", "B9FBFrame" + format(i, "X")))
            for i in range(13)
        ]
        self.assertEqual(matrix, expected)

    def test_12_ps_filters_never_accept_legacy_protocol_id(self):
        self.assertIn("mask->ProtocolID!=c->api_protocol", self.c)
        self.assertIn("pattern->ProtocolID!=c->api_protocol", self.c)
        self.assertIn("PassThruStartMsgFilter(can,1,&mask,&pattern,0,&fid)==ERR_MSG_PROTOCOL_ID", self.ct)
        self.assertIn("mask.ProtocolID=PROTO_CAN_PS;pattern.ProtocolID=PROTO_CAN_PS;", self.ct)
        self.assertIn("PassThruStopMsgFilter(can,fid)==ERR_OK", self.ct)

    def test_13_owner_windows_exact_head_full_suite_runner_is_isolated(self):
        runner = (EMULATOR / "adapters" / "cem50" /
                  "run_cem50_ps_validation.py").read_text(encoding="utf-8")
        self.assertIn('"git", "clone", "--no-local", "--no-checkout"', runner)
        self.assertIn('if branch != BRANCH:', runner)
        self.assertIn('"status", "--porcelain"', runner)
        self.assertIn('"-p", "test_*.py"', runner)
        self.assertIn('"virtualcar-host-test.exe"', runner)
        self.assertIn('["bash", "./build-cross.sh"]', runner)
        self.assertIn("Verify-J2534CEM50-PS.ps1", runner)
        self.assertIn("ps-native-check.json", runner)
        self.assertIn('"vida_readvin_verified": False', runner)
        self.assertIn('"installed_provider_modified": False', runner)
        self.assertNotIn("CreateSubKey", runner)
        self.assertNotIn("reg add", runner)

if __name__ == "__main__":
    unittest.main()
