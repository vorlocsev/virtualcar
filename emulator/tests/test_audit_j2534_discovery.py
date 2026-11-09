"""Eight synthetic regression groups for J2534 CEM evidence audit."""
import importlib.util
import json
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_j2534_discovery", path)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def event(name, data=b"", pid="DEADBEEF", host="DiagnosticClient.exe"):
    return f"[PID={pid} {host}] {name}" + ((" " + data.hex(" ").upper()) if data else "")


def be(*words):
    return b"".join(word.to_bytes(4, "big") for word in words)


def tx(can, payload, ch=None, proto=5, flags=0, baud=500000, time_us=100000):
    out = []
    if ch is not None:
        out.append(event("TX context channel/protocol/flags/baud/time-us (BE)",
                         be(ch, proto, flags, baud, time_us)))
    out.append(event("TX (app request)", can.to_bytes(4, "big") + payload))
    return out


def rx(can, payload, ch=None, proto=5, flags=0, baud=500000, time_us=102000):
    out = []
    if ch is not None:
        out.append(event("RX context channel/protocol/status/baud/time-us (BE)",
                         be(ch, proto, flags, baud, time_us)))
    out.append(event("PassThruReadMsgs -> delivered", can.to_bytes(4, "big") + payload))
    return out


D2FB = bytes.fromhex("CB 50 B9 FB 00 00 00 00")
D2F0 = bytes.fromhex("CB 50 B9 F0 00 00 00 00")
A3 = bytes.fromhex("A3 02 03 A5 A5 00 00 00")
P3 = bytes.fromhex("03 22 F1 14 00 00 00 00")
FIRST = bytes.fromhex("8F 50 F9 FB 57 00 30 66")
F0FIRST = bytes.fromhex("8F 50 F9 F0 00 00 00 00")


def frames13(ch=1, time_us=102000):
    hdr = [9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F]
    payloads = [FIRST] + [bytes((h,)) + b"\x00" * 7 for h in hdr]
    out = []
    for i, data in enumerate(payloads):
        out.extend(rx(0x01200003, data, ch=ch, time_us=time_us + i * 1000))
    return out


class J2534EvidenceTests(unittest.TestCase):
    def test_01_d2_13_frame_complete_and_timing(self):
        lines = tx(0xFFFFE, D2FB, ch=1) + frames13()
        data = tool.audit(lines)
        item = data["transactions"][0]
        self.assertEqual((item["status"], item["rx_frames"]), ("delivered", 13))
        self.assertEqual(item["reason"], "complete_d2_transport_only")
        self.assertEqual((item["channel"], item["protocol"], item["baud_bps"]), (1, "CAN", 500000))
        self.assertEqual(item["window_ms"], 14)
        self.assertFalse(data["replay_approved"])

    def test_02_partial_wrong_sequence_and_missing_final(self):
        wrong = tx(0xFFFFE, D2FB, ch=1)
        wrong += rx(0x01200003, FIRST, ch=1)
        wrong += rx(0x01200003, bytes.fromhex("0B 00 00 00 00 00 00 00"), ch=1)
        wrong += rx(0x01200003, bytes.fromhex("4F 00 00 00 00 00 00 00"), ch=1)
        wrong += tx(0xFFFFE, D2FB, ch=1)
        wrong += rx(0x01200003, FIRST, ch=1)
        wrong += rx(0x01200003, bytes.fromhex("09 00 00 00 00 00 00 00"), ch=1)
        states = tool.audit(wrong)["transactions"]
        self.assertEqual([x["status"] for x in states], ["partial_rx", "partial_rx"])
        self.assertEqual(states[0]["reason"], "invalid_d2_sequence")
        self.assertEqual(states[1]["reason"], "incomplete_or_unverified_transport")

    def test_03_explicit_no_fixture_unsupported_and_timeout(self):
        lines = tx(0xFFFFE, D2F0, ch=1)
        lines += [event("P2 D2 read command: no validated response fixture", D2F0[:4])]
        lines += tx(0xFFFFE, D2FB, ch=1)
        lines += [event("P2 D2 strict route rejected (no fixture emitted)", D2FB[:4])]
        lines += tx(0xFFFFE, A3, ch=1)
        lines += [event("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                        be(1, 500, 1))]
        states = tool.audit(lines)["transactions"]
        self.assertEqual([x["status"] for x in states], ["no_fixture", "unsupported", "timeout"])
        self.assertNotIn("delivered", [x["status"] for x in states])

    def test_04_multichannel_and_11_vs_29bit_routing(self):
        lines = tx(0x726, P3, ch=1, proto=6, flags=0, baud=500000)
        lines += tx(0x18DA50F1, P3, ch=2, proto=6, flags=0x100, baud=500000)
        lines += rx(0x18DAF150, bytes.fromhex("62 F1 14 00 00 00 00"),
                    ch=2, proto=6, flags=0x100)
        lines += rx(0x72E, bytes.fromhex("62 F1 14 00 00 00 00"),
                    ch=1, proto=6)
        states = tool.audit(lines)["transactions"]
        self.assertEqual([(x["channel"], x["id_format"]) for x in states],
                         [(1, "11bit"), (2, "29bit")])
        self.assertEqual([x["status"] for x in states], ["delivered", "delivered"])
        self.assertTrue(all(x["reason"] == "p3_uds_transport_only" for x in states))
        self.assertIn("does not prove", tool.audit(lines)["notes"][0])
        # Concurrent probes: a fixture diagnosis belongs to the latest TX channel.
        other = tx(0xFFFFE, D2FB, ch=1) + tx(0xFFFFE, D2F0, ch=2)
        other.append(event("P2 D2 read command: no validated response fixture", D2F0[:4]))
        diagnosed = tool.audit(other)["transactions"]
        self.assertEqual([(x["channel"], x["status"]) for x in diagnosed],
                         [(1, "unverified"), (2, "no_fixture")])

    def test_05_off_route_does_not_complete_d2(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200004, FIRST, ch=1)
        lines += rx(0x01200003, FIRST, ch=1)
        lines += rx(0x01200004, bytes.fromhex("09 00 00 00 00 00 00 00"), ch=1)
        lines += rx(0x01200003, bytes.fromhex("09 00 00 00 00 00 00 00"), ch=1)
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"]),
                         ("partial_rx", 2, 2))

    def test_06_clear_rx_prevents_stale_generation_completion(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200003, FIRST, ch=1)
        lines += [event("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)",
                        be(1, 5, 0, 500000, 110000))]
        lines += [event("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
        lines += tx(0xFFFFE, D2FB, ch=1)
        lines += frames13(ch=1)
        states = tool.audit(lines)["transactions"]
        self.assertEqual([x["rx_frames"] for x in states], [1, 13])
        self.assertEqual([x["status"] for x in states], ["partial_rx", "delivered"])
        # Disconnecting channel 1 must not terminate channel 2.
        concurrent = tx(0xFFFFE, D2FB, ch=1)
        concurrent += tx(0xFFFFE, D2FB, ch=2)
        concurrent += [event("PassThruDisconnect channel (BE)", be(1)),
                       event("PassThruDisconnect")]
        concurrent += frames13(ch=2)
        received = tool.audit(concurrent)["transactions"]
        self.assertEqual([(x["channel"], x["status"]) for x in received],
                         [(1, "unverified"), (2, "delivered")])
        self.assertEqual(received[0]["reason"], "channel_disconnected")

    def test_07_legacy_timestamp_and_unknown_channel(self):
        lines = [
            "02:42:50,578 0100 000004 PassThruWriteMsgs() msg[0].Data = [" +
            ", ".join(f"0x{x:02x}" for x in (0xFFFFE).to_bytes(4, "big") + D2FB) + "]",
            "02:42:50,640 0100 000004 PassThruReadMsgs() msg[0].Data = [" +
            ", ".join(f"0x{x:02x}" for x in (0x01200003).to_bytes(4, "big") + FIRST) + "]",
            "02:42:50,655 0100 000004 PassThruReadMsgs() msg[0].Data = [" +
            ", ".join(f"0x{x:02x}" for x in (0x01200003).to_bytes(4, "big") +
                      bytes.fromhex("4F 00 00 00 00 00 00 00")) + "]",
        ]
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual((one["channel"], one["id_format"], one["protocol"]), (None, "29bit", "unknown"))
        self.assertEqual((one["status"], one["window_ms"]), ("delivered", 77))

    def test_08_no_private_identifiers_or_client_acceptance(self):
        vin = b"YV1CZ0002A0000001"  # synthetic test only
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200003, FIRST, ch=1, time_us=102000)
        for i, h in enumerate((9, 10, 11)):
            lines += rx(0x01200003, bytes([h]) + vin[i*7:i*7+7].ljust(7, b"0"),
                        ch=1, time_us=103000+i*1000)
        lines += [event("PassThruClose")]
        raw = json.dumps(tool.audit(lines))
        self.assertNotIn(vin.decode(), raw)
        self.assertNotIn("DEADBEEF", raw)
        self.assertNotIn("DiagnosticClient", raw)
        self.assertNotIn("59 56 31", raw)
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual(one["status"], "partial_rx")
        self.assertFalse(tool.audit(lines)["contains_payload_data"])


class PrefixedD2ProbeTests(unittest.TestCase):
    """Eight groups; all bytes are synthetic, never vehicle response fixtures."""

    def test_09_a6_targets_and_declared_length(self):
        for target in (0x40, 0x50):
            for padded in (False, True):
                data = bytes((0xCD, target, 0xA6, 0x1A, 0x04, 1))
                if padded:
                    data = data.ljust(8, b"\0")
                with self.subTest(target=target, padded=padded):
                    self.assertEqual(tool._request(be(0xFFFFE) + data),
                                     ("D2", "A6", target, 0xFFFFE))

    def test_10_a3_length_prefixes(self):
        for service in (0xA3, 0xA6):
            for target in (0x40, 0x50):
                for prefix in range(0xCA, 0xD0):
                    data = bytes((prefix, target, service))
                    data = data.ljust(prefix - 0xC8 + 1, b"\0")
                    with self.subTest(service=service, target=target, prefix=prefix):
                        self.assertEqual(tool._request(be(0xFFFFE) + data),
                                         ("D2", f"{service:02X}", target, 0xFFFFE))

    def test_11_truncated_or_invalid_prefix(self):
        for prefix in range(0xCA, 0xD0):
            data = bytes((prefix, 0x40, 0xA6)).ljust(prefix - 0xC8 + 1, b"\0")
            for size in range(len(data)):
                with self.subTest(prefix=prefix, size=size):
                    self.assertIsNone(tool._request(be(0xFFFFE) + data[:size]))
        for prefix in (0x80, 0x8F, 0xC0, 0xC8, 0xC9, 0xD0, 0xD8):
            self.assertIsNone(tool._request(be(0xFFFFE) + bytes((prefix, 0x50, 0xA3, 0, 0, 0, 0, 0))))

    def test_12_foreign_route_opcode_and_oversize(self):
        data = bytes.fromhex("CD 40 A6 1A 04 01 00 00")
        for can in (0xFFFFD, 0x726, 0x18DA50F1):
            result = tool._request(be(can) + data)
            self.assertTrue(result is None or result[0] != "D2")
        for target in (0, 0x11, 0x51, 0xFF):
            self.assertIsNone(tool._request(be(0xFFFFE) + bytes((0xCD, target)) + data[2:]))
        for service in (0xA1, 0xAF, 0xB1, 0xE3, 0xE6):
            self.assertIsNone(tool._request(be(0xFFFFE) + data[:2] + bytes((service,)) + data[3:]))
        self.assertIsNone(tool._request(be(0xFFFFE) + data + b"\0"))

    def test_13_legacy_opaque_probe_and_timestamp(self):
        self.assertEqual(tool._request(be(0xFFFFE) + A3), ("D2", "A3", None, 0xFFFFE))
        raw = be(0xFFFFE) + bytes.fromhex("CD 50 A6 1A 04 01 00 00")
        line = "12:00:01,000 PassThruWriteMsgs() msg[0].Data = [" + ", ".join(f"0x{x:02x}" for x in raw) + "]"
        item = tool.audit([line])["transactions"][0]
        self.assertEqual((item["service"], item["target"], item["protocol"], item["channel"]),
                         ("A6", "0x50", "unknown", None))
        self.assertEqual(item["status"], "unverified")

    def test_14_channels_and_b9_delivery_remain_independent(self):
        lines = tx(0xFFFFE, D2FB, ch=1, flags=0x100)
        lines += tx(0xFFFFE, bytes.fromhex("CB 40 A3 00 00 00 00 00"),
                    ch=2, flags=0x100, baud=125000)
        lines += frames13(ch=1)
        states = {x["channel"]: x for x in tool.audit(lines)["transactions"]}
        self.assertEqual((states[1]["status"], states[1]["rx_frames"]), ("delivered", 13))
        self.assertEqual((states[2]["service"], states[2]["target"], states[2]["baud_bps"]),
                         ("A3", "0x40", 125000))
        self.assertEqual(states[2]["status"], "unverified")

    def test_15_reply_is_not_a_validated_response_or_identity(self):
        for service, reply in ((0xA3, 0xE3), (0xA6, 0xE6)):
            lines = tx(0xFFFFE, bytes((0xCB, 0x50, service, 0, 0, 0, 0, 0)), ch=1)
            lines += rx(0x01200003, bytes((0xCB, 0x50, reply, 0, 0, 0, 0, 0)), ch=1)
            item = tool.audit(lines)["transactions"][0]
            self.assertEqual((item["status"], item["rx_frames"], item["off_route_rx"]),
                             ("unverified", 0, 1))
            lines += [event("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)", be(1, 500, 1))]
            self.assertEqual(tool.audit(lines)["transactions"][0]["status"], "timeout")

    def test_16_cli_metadata_only(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "private.log", Path(directory) / "audit.json"
            # Arbitrary parameter bytes are not copied to the report.
            lines = tx(0xFFFFE, bytes.fromhex("CF 50 A6 59 56 31 41 42"), ch=2)
            source.write_text("\n".join(lines), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                tool.main([str(source), "--output", str(output)])
            report = json.loads(output.read_text(encoding="utf-8"))
            item = report["transactions"][0]
            self.assertEqual((item["service"], item["target"], item["channel"]), ("A6", "0x50", 2))
            text = output.read_text(encoding="utf-8")
            for private in ("DEADBEEF", "DiagnosticClient", "59 56 31", "YV1AB", str(source)):
                self.assertNotIn(private, text)
            self.assertFalse(report["contains_payload_data"])
            self.assertFalse(report["replay_approved"])



def periodic(can, payload, ch=1, proto=5, flags=0, baud=500000, time_us=100000):
    """Native scheduler-origin records, not direct client WriteMsgs."""
    return [
        event("Periodic TX context channel/protocol/flags/baud/time-us (BE)",
              be(ch, proto, flags, baud, time_us)),
        event("J2534 periodic TX (read-only simulator)",
              can.to_bytes(4, "big") + payload),
    ]


class PeriodicTextOriginTests(unittest.TestCase):
    """Eight synthetic groups. Delivered RX never asserts OEM ECU identity."""

    def test_17_scheduled_b9fb_thirteen_frames_are_counted_not_gui_attributed(self):
        lines = periodic(0xFFFFE, D2FB, ch=2, flags=0x100)
        lines += frames13(ch=2)
        data = tool.audit(lines)
        self.assertEqual(len(data["transactions"]), 1)
        item = data["transactions"][0]
        self.assertEqual((item["service"], item["channel"], item["request_origin"]),
                         ("B9FB", 2, "periodic_scheduler"))
        self.assertEqual((item["status"], item["rx_frames"]), ("delivered", 13))
        self.assertEqual(item["reason"], "complete_d2_transport_only")
        self.assertFalse(data["replay_approved"])

    def test_18_periodic_request_does_not_steal_other_direct_channel(self):
        lines = tx(0xFFFFE, D2FB, ch=1, time_us=100000)
        lines += periodic(0xFFFFE, D2F0, ch=2, time_us=100500)
        lines += [event("P2 D2 read command: no validated response fixture")]
        lines += frames13(ch=1)
        results = {r["channel"]: r for r in tool.audit(lines)["transactions"]}
        self.assertEqual(results[1]["request_origin"], "direct_write")
        self.assertEqual((results[1]["status"], results[1]["rx_frames"]),
                         ("delivered", 13))
        self.assertEqual(results[2]["request_origin"], "periodic_scheduler")
        self.assertEqual((results[2]["status"], results[2]["reason"]),
                         ("no_fixture", "explicit_missing_fixture"))

    def test_19_scheduled_a3_a6_stay_opaque_and_do_not_prove_ecu(self):
        for sid in (0xA3, 0xA6):
            data = bytes((0xCF, 0x50, sid, 0x02, 0x03, 0xA5, 0xA5, 0x00))
            lines = periodic(0xFFFFE, data, ch=3)
            item = tool.audit(lines)["transactions"][0]
            self.assertEqual((item["service"], item["target"], item["rx_frames"]),
                             (f"{sid:02X}", "0x50", 0))
            self.assertEqual(item["request_origin"], "periodic_scheduler")
            self.assertEqual(item["status"], "unverified")

    def test_20_scheduled_flow_control_never_supersedes_existing_request(self):
        lines = tx(0x726, P3, ch=1)
        lines += periodic(0x726, bytes.fromhex("30 00 00 00 00 00 00 00"),
                          ch=1, time_us=101000)
        lines += rx(0x72E, bytes.fromhex("04 62 F1 14 01 00 00 00"),
                    ch=1, time_us=103000)
        result = tool.audit(lines)["transactions"]
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["status"], result[0]["request_origin"]),
                         ("delivered", "direct_write"))

    def test_21_missing_and_malformed_periodic_contexts_never_infer_route(self):
        raw = event("J2534 periodic TX (read-only simulator)",
                    (0xFFFFE).to_bytes(4, "big") + D2FB)
        invalid = event("Periodic TX context channel/protocol/flags/baud/time-us (BE)",
                        be(1, 5, 0, 500000))  # four words, never five
        report = tool.audit([raw, invalid, raw])
        self.assertEqual(report["transactions"], [])
        self.assertEqual(report["parse_errors"].get("unattributed_periodic_tx"), 2)
        self.assertEqual(report["parse_errors"].get("malformed_periodic_context"), 1)

    def test_22_invalid_transport_and_payloads_do_not_create_evidence(self):
        raw = (0xFFFFE).to_bytes(4, "big") + D2FB
        cases = (
            # A D2 raw-CAN request cannot be attributed to ISO15765.
            periodic(0xFFFFE, D2FB, proto=6),
            # Nine-byte classic CAN payload is invalid.
            periodic(0xFFFFE, D2FB + b"\0", proto=5),
            # Unexpected trailing text must not be parsed into a request.
            [periodic(0xFFFFE, D2FB)[0],
             event("J2534 periodic TX (read-only simulator) " +
                   raw.hex(" ").upper() + " PRIVATE VIN")],
            # A zero channel cannot be attributed to a J2534 session.
            periodic(0xFFFFE, D2FB, ch=0),
        )
        for lines in cases:
            with self.subTest(lines=lines[0][:50]):
                report = tool.audit(lines)
                self.assertEqual(report["transactions"], [])
                self.assertTrue(report["parse_errors"])

    def test_23_periodic_context_does_not_leak_into_later_direct_write(self):
        context = periodic(0xFFFFE, D2FB, ch=5)[0]
        raw = periodic(0xFFFFE, D2FB, ch=5)[1]
        lines = [context, event("some unrelated native diagnostic event"), raw]
        lines += tx(0xFFFFE, D2FB, ch=1)
        lines += frames13(ch=1)
        data = tool.audit(lines)
        self.assertEqual(len(data["transactions"]), 1)
        self.assertEqual(data["transactions"][0]["channel"], 1)
        self.assertEqual(data["transactions"][0]["request_origin"], "direct_write")
        self.assertEqual(data["parse_errors"].get("unattributed_periodic_tx"), 1)

    def test_24_redacted_periodic_source_ignores_private_payload_and_pid(self):
        vin = b"YV1LAB00000000001"  # synthetic, never a donor
        lines = periodic(0xFFFFE, D2FB, ch=6)
        lines += rx(0x01200003, FIRST, ch=6)
        lines += rx(0x01200003, b"\x09" + vin[:7], ch=6)
        report = tool.audit(lines, include_obd=True)
        data = json.dumps(report)
        self.assertEqual(report["transactions"][0]["request_origin"],
                         "periodic_scheduler")
        self.assertEqual(report["transactions"][0]["status"], "partial_rx")
        self.assertEqual(report["observed_event_markers"]
                         ["periodic_scheduler_tx_record"], 1)
        for secret in ("DEADBEEF", "DiagnosticClient", "YV1LAB", "59 56 31",
                       "PRIVATE"):
            self.assertNotIn(secret, data)
        self.assertFalse(report["contains_payload_data"])
        self.assertFalse(report["replay_approved"])




def _d2_series_13(first=FIRST, final=0x4F, ch=1, baud=500000):
    """Synthetic 13-frame D2 0x08 or 0x10 series; no donor/vehicle bytes.

    Preserve the same bus speed for TX and each RX. A CEM 0x40
    route at 125 kbit/s must never borrow the 500 kbit/s default.
    """
    base = 0x10 if first[0] == 0x97 else 0x08
    seq = [(base | i) for i in (1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3)]
    payloads = [first] + [bytes([h]) + b"\0" * 7 for h in seq]
    payloads.append(bytes([final]) + b"\0" * 7)
    return [line for i, payload in enumerate(payloads)
            for line in rx(0x01200003, payload, ch=ch, baud=baud,
                           time_us=102000+i*1000)]


class D2ThirteenFrameTerminalEvidenceTests(unittest.TestCase):
    """Narrow parser parity with the native C D2 fixture validator."""

    def test_25_exact_08_series_13_frame_4f_is_delivered(self):
        result = tool.audit(tx(0xFFFFE, D2FB, ch=1) + _d2_series_13())
        one = result["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"]),
                         ("delivered", 13))
        self.assertEqual(one["reason"], "complete_d2_transport_only")
        self.assertFalse(result["replay_approved"])

    def test_26_08_series_13_frame_short_terminal_markers_rejected(self):
        for marker in (0x48, 0x49, 0x4A, 0x4C, 0x4E):
            with self.subTest(marker=marker):
                report = tool.audit(tx(0xFFFFE, D2FB, ch=1)
                                    + _d2_series_13(final=marker))
                one = report["transactions"][0]
                self.assertEqual((one["rx_frames"], one["status"]),
                                 (13, "partial_rx"))
                self.assertEqual(one["reason"],
                                 "d2_13frame_final_marker_mismatch")
                self.assertEqual(report["counts"], {"partial_rx": 1})
                self.assertFalse(report["replay_approved"])

    def test_27_d2_terminal_guard_does_not_infer_target_or_opcode_identity(self):
        first = bytes.fromhex("8F 40 F9 F0 00 00 00 00")
        request = bytes.fromhex("CB 40 B9 F0 00 00 00 00")
        one = tool.audit(tx(0xFFFFE, request, ch=4, baud=125000)
                         + _d2_series_13(first=first, final=0x4E,
                                         ch=4, baud=125000)
                         )["transactions"][0]
        self.assertEqual((one["target"], one["service"]), ("0x40", "B9F0"))
        self.assertEqual((one["rx_frames"], one["status"]),
                         (13, "partial_rx"))
        self.assertEqual(one["reason"], "d2_13frame_final_marker_mismatch")
        self.assertNotEqual(one["status"], "delivered")

    def test_28_periodic_08_series_13_frame_rejected_without_gui_claim(self):
        report = tool.audit(periodic(0xFFFFE, D2FB, ch=2)
                            + _d2_series_13(final=0x4B, ch=2))
        one = report["transactions"][0]
        self.assertEqual(one["request_origin"], "periodic_scheduler")
        self.assertEqual(one["status"], "partial_rx")
        self.assertEqual(one["reason"], "d2_13frame_final_marker_mismatch")
        self.assertIn("not proof", report["notes"][-2])

    def test_29_10_series_13_frame_terminal_is_not_overrestricted(self):
        first = bytes.fromhex("97 50 F9 FB 00 00 00 00")
        report = tool.audit(tx(0xFFFFE, D2FB, ch=3)
                            + _d2_series_13(first=first, final=0x4E, ch=3))
        one = report["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"]), ("delivered", 13))
        self.assertEqual(one["reason"], "complete_d2_transport_only")

    def test_30_shorter_08_series_remains_valid_without_13_frame_assumption(self):
        for terminal in (0x48, 0x4C, 0x4F):
            with self.subTest(terminal=terminal):
                short = tx(0xFFFFE, D2FB, ch=1)
                short += rx(0x01200003, FIRST, ch=1)
                short += rx(0x01200003, bytes.fromhex(
                    "09 00 00 00 00 00 00 00"), ch=1)
                short += rx(0x01200003, bytes([terminal]) + b"\0" * 7, ch=1)
                one = tool.audit(short)["transactions"][0]
                self.assertEqual((one["status"], one["rx_frames"]),
                                 ("delivered", 3))

    def test_31_missing_final_stays_partial_without_fabricated_terminal(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += _d2_series_13()[:-2]
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"]), ("partial_rx", 12))
        self.assertEqual(one["reason"], "incomplete_or_unverified_transport")

    def test_32_rejected_terminal_and_independent_valid_channel_stay_separate(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += tx(0xFFFFE, D2FB, ch=2)
        lines += _d2_series_13(final=0x49, ch=1)
        lines += _d2_series_13(final=0x4F, ch=2)
        report = tool.audit(lines)
        states = {t["channel"]: t for t in report["transactions"]}
        self.assertEqual((states[1]["status"], states[2]["status"]),
                         ("partial_rx", "delivered"))
        self.assertEqual(states[1]["reason"],
                         "d2_13frame_final_marker_mismatch")
        serial = json.dumps(report)
        for secret in ("DEADBEEF", "DiagnosticClient",
                       "00 0F FF FE", "YV1LAB"):
            self.assertNotIn(secret, serial)
        self.assertFalse(report["contains_payload_data"])





class D2ClassicCanRxEvidenceTests(unittest.TestCase):
    """Eight synthetic cases; no real VIN, donor frame or GUI acceptance."""

    def test_33_short_final_4f_must_not_complete_b9_transport(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200003, FIRST, ch=1)
        lines += rx(0x01200003, b"\x4F", ch=1)
        report = tool.audit(lines)
        one = report["transactions"][0]
        self.assertEqual((one["status"], one["reason"], one["rx_frames"]),
                         ("partial_rx", "d2_classic_can_rx_size_invalid", 2))
        self.assertEqual(report["parse_errors"]["d2_classic_can_rx_size_invalid"], 1)
        self.assertFalse(report["replay_approved"])

    def test_34_truncated_first_frame_cannot_be_rehabilitated_by_final(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200003, FIRST[:4], ch=1)
        lines += rx(0x01200003, FIRST, ch=1)
        lines += rx(0x01200003, b"\x4F" + b"\0" * 7, ch=1)
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual(one["status"], "partial_rx")
        self.assertEqual(one["reason"], "d2_classic_can_rx_size_invalid")
        self.assertEqual(one["rx_frames"], 3)

    def test_35_oversized_b9_can_payload_does_not_pass_as_first_frame(self):
        for length in (9, 12, 16):
            with self.subTest(length=length):
                lines = tx(0xFFFFE, D2FB, ch=1)
                lines += rx(0x01200003, FIRST + b"\0" * (length - 8), ch=1)
                item = tool.audit(lines)["transactions"][0]
                self.assertEqual(item["reason"], "d2_classic_can_rx_size_invalid")
                self.assertEqual(item["status"], "partial_rx")

    def test_36_mismatched_rx_protocol_is_not_the_d2_response(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200003, FIRST, ch=1, proto=6)
        lines += frames13(ch=1)
        report = tool.audit(lines)
        one = report["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"]),
                         ("delivered", 13, 1))
        self.assertEqual(report["parse_errors"]["d2_rx_protocol_mismatch"], 1)

    def test_37_wrong_bus_speed_does_not_contribute_to_b9_frames(self):
        lines = tx(0xFFFFE, D2FB, ch=1, baud=500000)
        lines += rx(0x01200003, FIRST, ch=1, baud=125000)
        lines += frames13(ch=1)
        report = tool.audit(lines)
        one = report["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"]),
                         ("delivered", 13, 1))
        self.assertEqual(report["parse_errors"]["d2_rx_baud_mismatch"], 1)

    def test_38_rx_indications_and_echoes_are_not_vehicle_data(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        for status in (0x01, 0x02, 0x08):
            lines += rx(0x01200003, FIRST, ch=1, flags=status)
        lines += frames13(ch=1)
        result = tool.audit(lines)
        one = result["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"]),
                         ("delivered", 13, 3))
        self.assertEqual(result["parse_errors"]["d2_rx_indication_not_payload"], 3)

    def test_39_direct_d2_tx_on_iso15765_remains_unverified(self):
        lines = tx(0xFFFFE, D2FB, ch=1, proto=6)
        lines += frames13(ch=1)
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual(one["protocol"], "ISO15765")
        self.assertEqual(one["status"], "unverified")
        self.assertEqual(one["reason"], "d2_request_non_can_transport")
        self.assertNotEqual(one["status"], "delivered")

    def test_40_concurrent_b9_channels_and_redaction_remain_independent(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += tx(0xFFFFE, D2FB, ch=2)
        lines += rx(0x01200003, FIRST, ch=1)
        lines += rx(0x01200003, b"\x4F", ch=1)
        # A malformed but unrelated CAN ID on the other channel is
        # off-route, not evidence that its valid B9 response is corrupt.
        lines += rx(0x01200004, b"\x4F", ch=2)
        lines += frames13(ch=2)
        report = tool.audit(lines)
        states = {x["channel"]: x for x in report["transactions"]}
        self.assertEqual((states[1]["status"], states[2]["status"]),
                         ("partial_rx", "delivered"))
        self.assertEqual(states[2]["off_route_rx"], 1)
        self.assertEqual(states[1]["reason"], "d2_classic_can_rx_size_invalid")
        result = json.dumps(report)
        for sensitive in ("DEADBEEF", "DiagnosticClient", "00 0F FF FE",
                          "YV1LAB", "0x01200003"):
            self.assertNotIn(sensitive, result)
        self.assertFalse(report["contains_payload_data"])
        self.assertFalse(report["replay_approved"])



if __name__ == "__main__":
    unittest.main()
