"""Eight synthetic groups for VIDA J2534 text; no real identities or captured payloads."""
import importlib.util
import json
from pathlib import Path
import unittest

script = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_vida", script)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

REQUEST = bytes.fromhex("00 00 07 26 22 F1 14")
RESPONSE = bytes.fromhex("00 00 07 2E 62 F1 14") + b"SYNTHETIC_RECORD"


def line(message, time="12:00:00,000", thread="00A", level="VehCom"):
    prefix = (time + " ") if time else ""
    return f"{prefix}[J2534ChannelMana][{thread}][{level}]  {message}"


def connect(ch=2, protocol=6, flags=0, baud=500000, device=0, **kw):
    return line(f"PassThruConnect({device}, 0x{protocol:02X}, 0x{flags:02X}, {baud}, {ch})", **kw)


def call(direction, ch=2, count=1, wait=100, **kw):
    name = "Write" if direction == "tx" else "Read"
    return line(f"PassThru{name}Msgs({ch}, PASSTHRU_MSG, {count}, {wait} ) - SyntheticThread ->SYNTHETIC_ADAPTER<-", **kw)


def packet(direction, raw, index=0, **kw):
    arrow = "--->" if direction == "tx" else "<---"
    data = ",".join(f"{x:02X}" for x in raw) + ","
    return line(f"{arrow}\t({index}) {data}", **kw)


def tx(raw=REQUEST, ch=2, **kw):
    return [call("tx", ch, **kw), packet("tx", raw, **kw)]


def rx(raw=RESPONSE, ch=2, **kw):
    return [call("rx", ch, **kw), packet("rx", raw, **kw)]


def records(lines):
    return tool.audit(lines)["transactions"]


class VidaTextTests(unittest.TestCase):
    def test_01_reassembled_cem_read_metadata_and_client_duplicate(self):
        lines = [connect()] + tx(time="12:00:00,001")
        lines += rx(bytes.fromhex("00 00 07 2E"),time="12:00:00,005")
        lines += rx(time="12:00:00,017")
        lines += ["12:00:00,017 [DiagConnection  ][00A][VehCom]  VehComm response: '62F114'"]
        report = tool.audit(lines)
        self.assertEqual(len(report["transactions"]), 1)
        item = report["transactions"][0]
        self.assertEqual((item["service"], item["status"], item["rx_frames"]), ("22F114", "delivered", 1))
        self.assertEqual((item["channel"], item["protocol"], item["baud_bps"], item["id_format"]), (2, "ISO15765", 500000, "11bit"))
        self.assertEqual(item["window_ms"], 16)
        self.assertFalse(report["parse_errors"])
        self.assertFalse(report["replay_approved"])
        header_only = records([connect()] + tx() + rx(bytes.fromhex("00 00 07 2E")))[0]
        self.assertEqual((header_only["status"],header_only["rx_frames"]),("unverified",0))
        long_reply = bytes.fromhex("00 00 07 2E 62 F1 14") + bytes([0xA5])*255
        self.assertEqual(records([connect()]+tx()+rx(long_reply))[0]["rx_frames"],1)

    def test_02_d2_multiframe_a6_and_opaque_probe(self):
        cases = [
            (bytes.fromhex("00 0F FF FE CB 40 B9 FB 00 00 00 00"),
             [bytes.fromhex("8F 40 F9 FB 00 00 00 00")] +
             [bytes((h,)) + bytes(7) for h in [9,10,11,12,13,14,15,8,9,10,11,0x4F]], "delivered", 13),
            (bytes.fromhex("00 0F FF FE CD 40 A6 1A 04 01 00 00"),
             [bytes.fromhex("CD 40 E6 1A 04 01 00 00")], "delivered", 1),
            (bytes.fromhex("00 0F FF FE CF 40 A3 00 00 00 00 00"),
             [bytes.fromhex("CB 40 E3 02 00 00 00 00")], "unverified", 0),
        ]
        for request, frames, status, count in cases:
            with self.subTest(service=request[6:7].hex()):
                lines = [connect(protocol=5, flags=0x100, baud=125000)] + tx(request)
                lines += [call("rx", count=len(frames))]
                lines += [packet("rx", bytes.fromhex("00 80 00 03") + frame, index=i) for i, frame in enumerate(frames)]
                item = records(lines)[0]
                self.assertEqual((item["status"], item["rx_frames"]), (status, count))
                self.assertEqual((item["protocol"], item["baud_bps"], item["target"]), ("CAN", 125000, "0x40"))

    def test_03_threads_channels_and_addressing_do_not_cross(self):
        request29 = bytes.fromhex("18 DA 50 F1 22 F1 14")
        response29 = bytes.fromhex("18 DA F1 50 62 F1 14 01")
        lines = [connect(ch=2), connect(ch=3, flags=0x100)]
        lines += [call("tx", ch=2, thread="00A"), call("tx", ch=3, thread="00B")]
        lines += [packet("tx", request29, thread="00B"), packet("tx", REQUEST, thread="00A")]
        lines += [call("rx", ch=2, thread="00A"), call("rx", ch=3, thread="00B")]
        lines += [packet("rx", response29, thread="00A"), packet("rx", RESPONSE, thread="00B")]
        lines += rx(response29, ch=3, thread="00B") + rx(RESPONSE, ch=2, thread="00A")
        items = {x["channel"]:x for x in records(lines)}
        self.assertEqual(set(items), {2,3})
        self.assertEqual([items[i]["status"] for i in [2,3]], ["delivered","delivered"])
        self.assertEqual([items[i]["off_route_rx"] for i in [2,3]], [1,1])
        self.assertEqual([items[i]["id_format"] for i in [2,3]], ["11bit","29bit"])
        tester_present = bytes.fromhex("00 00 07 26 3E 80")
        item = records([connect()]+tx()+tx(tester_present)+rx())[0]
        self.assertNotEqual(item["status"],"delivered")
        collision = records([connect(device=0),connect(device=1)]+tx()+rx())[0]
        self.assertEqual((collision["protocol"],collision["status"]),("unknown","unverified"))

    def test_04_missing_metadata_and_timestamps_are_not_filled(self):
        item = records(tx() + rx())[0]
        self.assertEqual((item["channel"],item["protocol"],item["baud_bps"],item["id_format"]), (2,"unknown",None,"unknown"))
        self.assertNotEqual(item["status"], "delivered")
        self.assertEqual(item["reason"], "vida_unknown_transport")
        missing = [connect(time=None)] + tx(time=None) + rx(time=None)
        item = records(missing)[0]
        self.assertEqual(item["status"], "delivered")
        self.assertIsNone(item["window_ms"])
        other = [connect(protocol=0x8004)] + tx() + rx()
        self.assertNotEqual(records(other)[0]["status"], "delivered")

    def test_05_malformed_or_unbound_payloads_never_complete(self):
        variants = [
            [packet("rx", RESPONSE)],
            [call("rx", thread="00B"), packet("rx", RESPONSE, thread="00A")],
            [call("rx"), packet("rx", RESPONSE, index=1)],
            [call("rx"), packet("tx", RESPONSE)],
            [call("rx"), line("<--- (0) 00,00,07,2E,62,F1,14,GG,")],
            [call("rx"), line("<--- (0) 00,00,07,2E,62,F1,14,0,")],
        ]
        for suffix in variants:
            with self.subTest(suffix=suffix):
                report = tool.audit([connect()] + tx() + suffix)
                self.assertNotEqual(report["transactions"][0]["status"], "delivered")
                self.assertTrue(any(k.startswith("vida_") for k in report["parse_errors"]))
        self.assertFalse(records([packet("tx", REQUEST), packet("rx", RESPONSE)]))
        broken_tx = [connect()] + tx() + [call("tx"), line("---> (0) 00,00,07,26,22,F1,14,GG,")] + rx()
        self.assertNotEqual(records(broken_tx)[0]["status"], "delivered")
        broken_rx = [connect()] + tx() + [call("rx"), line("<--- (0) 00,00,07,2E,62,F1,14,GG,")] + rx()
        self.assertNotEqual(records(broken_rx)[0]["status"], "delivered")
        for count in (0,4097):
            with self.subTest(count=count):
                self.assertFalse(records([connect(),call("tx",count=count),packet("tx",REQUEST)]))

    def test_06_observed_read_errors_and_negative_pending(self):
        for err in ["ERR_TIMEOUT","ERR_BUFFER_EMPTY","ERR_DEVICE_NOT_CONNECTED"]:
            with self.subTest(error=err):
                lines = [connect()] + tx() + [call("rx"), line("J2534 function:PassThruReadMsgs failed with return value:"+err, level="Error")]
                item = records(lines)[0]
                self.assertEqual(item["status"], "timeout" if err in ("ERR_TIMEOUT","ERR_BUFFER_EMPTY") else "unverified")
        pending = bytes.fromhex("00 00 07 2E 7F 22 78")
        final = bytes.fromhex("00 00 07 2E 7F 22 31")
        item = records([connect()] + tx() + rx(pending) + rx(final))[0]
        self.assertEqual((item["status"], item["response_pending_frames"]), ("negative_response",1))
        failed = [connect()] + tx() + [line("J2534 function:PassThruWriteMsgs failed with return value:ERR_FAILED",level="Error")] + rx()
        self.assertNotEqual(records(failed)[0]["status"], "delivered")
        empty_now = [connect()]+tx()+[call("rx",wait=0),line("J2534 function:PassThruReadMsgs failed with return value:ERR_BUFFER_EMPTY",level="Error")]
        self.assertEqual(records(empty_now)[0]["status"],"unverified")

    def test_07_boundaries_and_reused_channel_drop_stale_state(self):
        for boundary in [
            line("PassThruDisconnect(2)"),
            line("PassThruClose(0)"),
            "Starting new logsession: 2026-01-01 12:01:00",
            connect(ch=2,protocol=5,flags=0x100,baud=125000),
            line("PassThruIoctl(2, CLEAR_RX_BUFFER, 0, 0)"),
            line("PassThruIoctl(2, 0x08, 0, 0)"),
            line("J2534Channel::ClearRxBuffer()"),
        ]:
            with self.subTest(boundary=boundary):
                items = records([connect()] + tx() + [call("rx"), boundary, packet("rx",RESPONSE)])
                self.assertEqual(len(items),1)
                self.assertNotEqual(items[0]["status"],"delivered")
        failed_connect = [connect(),line("J2534 function:PassThruConnect failed with return value:ERR_NOT_SUPPORTED",level="Error")]
        item = records(failed_connect+tx()+rx())[0]
        self.assertEqual(item["protocol"],"unknown")
        self.assertNotEqual(item["status"],"delivered")
        invalid = [connect(), connect(protocol=0x100000000)] + tx() + rx()
        self.assertEqual(records(invalid)[0]["protocol"],"unknown")
        malformed = [connect(), line("PassThruConnect(0, 6, 0, 500000, 2")] + tx() + rx()
        self.assertEqual(records(malformed)[0]["protocol"],"unknown")
        after_clear = [connect()]+tx()+[line("PassThruIoctl(2, 8, 0, 0)")]+tx()+rx()
        self.assertEqual([x["status"] for x in records(after_clear)],["unverified","delivered"])

    def test_08_privacy_native_format_and_no_invented_client_success(self):
        sentinel=b"SYNTH_PRIVATE_123"
        report=tool.audit([connect()]+tx()+rx(bytes.fromhex("00 00 07 2E 62 F1 14")+sentinel))
        text=json.dumps(report)
        for private in [sentinel.decode(),sentinel.hex(), "SYNTHETIC_ADAPTER","SyntheticThread","J2534ChannelMana"]:
            self.assertNotIn(private,text)
        self.assertFalse(report["replay_approved"])
        self.assertFalse(report["contains_payload_data"])
        client_echo = "12:00:00,000 [DiagConnection  ][00A][Info]  TX (app request) 00 00 07 26 22 F1 14"
        self.assertFalse(records([client_echo]))
        native=["10:00:00,001 TX (app request) 00 0F FF FE CB 40 B9 F0 00 00 00 00",
                "10:00:00,003 PassThruReadMsgs -> delivered 00 80 00 03 CC 40 F9 F0 01 00 00 00"]
        self.assertEqual(records(native)[0]["status"],"delivered")
        mixed=records(native+[connect()]+tx()+rx())
        self.assertEqual([x["status"] for x in mixed],["delivered","delivered"])


if __name__ == "__main__":
    unittest.main()
