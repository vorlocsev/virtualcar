"""Eight synthetic B9FB D2 matcher regressions grounded in VIDA VehCom2 IL.

Do not misrepresent these as running VIDA, as full vehicle identity checks,
or as evidence for genuine XC90 V8 MY2009 ECU responses.
No proprietary DLL bytes, real identifiers or VINs in this file.
"""
import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("import_p2_trace", BASE / "tools" / "import_p2_trace.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def synthetic_frames(target=0x50, offset=0xFB, service=0xF9, can=0x01200003):
    """91 bytes of invented diagnostic data: 3-byte D2 echo + 88 zero bytes."""
    stream = bytes((target, service, offset)) + bytes(88)
    chunks = [stream[i:i + 7] for i in range(0, len(stream), 7)]
    assert len(chunks) == 13 and all(len(x) == 7 for x in chunks)
    result = []
    for i, chunk in enumerate(chunks):
        fmt = 0x8F if i == 0 else 0x4F if i == len(chunks) - 1 else (0x08 | (i & 7))
        result.append((can, bytes((fmt,)) + chunk))
    return result


def synthetic_single(target=0x50, offset=0xFB, service=0xF9, can=0x01200003):
    return [(can, bytes((0xCB, target, service, offset, 0, 0, 0, 0)))]


class VidaB9FBEchoContractTests(unittest.TestCase):
    def test_01_13_frame_matched_echo(self):
        frames = synthetic_frames()
        self.assertEqual(len(frames), 13)
        self.assertEqual(frames[0][1][:4], bytes.fromhex("8f 50 f9 fb"))
        self.assertIsNone(tool.validate_response(frames, 0x50, 0xFB))

    def test_02_single_frame_matched_echo(self):
        self.assertIsNone(tool.validate_response(synthetic_single(), 0x50, 0xFB))
        self.assertIsNone(tool.validate_response(synthetic_single(target=0x40), 0x40, 0xFB))

    def test_03_wrong_b9_offset_single_frame_rejected(self):
        for wrong in (0xF0, 0xFC, 0x00):
            with self.subTest(offset=wrong), self.assertRaises(ValueError):
                tool.validate_response(synthetic_single(offset=wrong), 0x50, 0xFB)

    def test_04_wrong_b9_offset_multiframe_rejected(self):
        for wrong in (0xF0, 0xFC):
            with self.subTest(offset=wrong), self.assertRaises(ValueError):
                tool.validate_response(synthetic_frames(offset=wrong), 0x50, 0xFB)

    def test_05_wrong_positive_service_rejected(self):
        for make in (synthetic_single, synthetic_frames):
            with self.subTest(factory=make.__name__), self.assertRaises(ValueError):
                tool.validate_response(make(service=0xF8), 0x50, 0xFB)

    def test_06_wrong_ecu_target_rejected(self):
        for make in (synthetic_single, synthetic_frames):
            with self.subTest(factory=make.__name__), self.assertRaises(ValueError):
                tool.validate_response(make(target=0x40), 0x50, 0xFB)

    def test_07_wrong_continuation_and_no_final_rejected(self):
        frames = synthetic_frames()
        with self.assertRaises(ValueError):
            tool.validate_response(frames[:-1], 0x50, 0xFB)
        modified = list(frames)
        frame = bytearray(modified[1][1])
        frame[0] = 0x0B  # expected 0x09, invalid modulo-eight counter
        modified[1] = (modified[1][0], bytes(frame))
        with self.assertRaises(ValueError):
            tool.validate_response(modified, 0x50, 0xFB)
        modified = list(frames)
        frame = bytearray(modified[4][1]); frame[0] = 0x4F
        modified[4] = (modified[4][0], bytes(frame))
        with self.assertRaises(ValueError):
            tool.validate_response(modified, 0x50, 0xFB)

    def test_08_can_route_and_negative_reply_not_promoted(self):
        frames = synthetic_frames()
        modified = list(frames)
        modified[5] = (0x01200004, modified[5][1])
        with self.assertRaises(ValueError):
            tool.validate_response(modified, 0x50, 0xFB)
        # The importer is intentionally transport-only: a negative B9 reply
        # can be preserved as negative but is never an F9FB positive echo.
        neg = synthetic_single(service=0x7F, offset=0xB9)
        self.assertIsNone(tool.validate_response(neg, 0x50, 0xFB))
        self.assertNotEqual(neg[0][1][2:4], bytes.fromhex("f9 fb"))


if __name__ == "__main__":
    unittest.main()
