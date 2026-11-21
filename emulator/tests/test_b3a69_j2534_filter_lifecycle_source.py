"""B3A69: source-only metadata instrumentation contract checks.

These tests NEVER load or build a DLL and do not prove native ABI behavior.
"""
from pathlib import Path
import re
import unittest

SRC = (Path(__file__).resolve().parents[1] / "src" /
       "virtualcar.c").read_text(encoding="utf-8")


class FilterLifecycleSourceTests(unittest.TestCase):
    def test_01_accepted_filter_metadata_is_five_u32_be(self):
        match = re.search(
            r'\{U8 lifecycle\[20\];(.*?)'
            r'logline\("J2534 filter accepted channel/type/id/protocol/baud \(BE\)",lifecycle,20\);',
            SRC, re.S)
        self.assertIsNotNone(match)
        for x in ("u32_be(lifecycle,id);",
                  "u32_be(lifecycle+4,type);",
                  "u32_be(lifecycle+8,*filter_id);",
                  "u32_be(lifecycle+12,c->api_protocol?c->api_protocol:c->protocol);",
                  "u32_be(lifecycle+16,c->baud);"):
            self.assertIn(x, match.group(1))

    def test_02_metadata_after_filter_is_accepted(self):
        begin = SRC.index("EXPORT U32 WINCALL PassThruStartMsgFilter(")
        end = SRC.index("EXPORT U32 WINCALL PassThruStopMsgFilter(", begin)
        section = SRC[begin:end]
        self.assertLess(section.index("*filter_id=g_filter_counter++"),
                        section.index("J2534 filter accepted channel/type/id/protocol/baud (BE)"))
        self.assertIn("if(c->filters_count>=MAX_FILTERS)", section)
        self.assertIn("if(g_strict_j2534_filters)", section)

    def test_03_old_filter_markers_unchanged(self):
        self.assertIn('logline("PassThruStartMsgFilter type / id (BE)",descriptor,8);', SRC)
        self.assertIn('logline("  filter mask",mask->Data,mask->DataSize);', SRC)
        self.assertIn('logline("  filter pattern",pattern->Data,pattern->DataSize);', SRC)
        self.assertIn('logline("  flow control",flow->Data,flow->DataSize);', SRC)

    def test_04_stop_reports_only_successfully_removed_filter(self):
        start = SRC.index("EXPORT U32 WINCALL PassThruStopMsgFilter(")
        stop = SRC.index("EXPORT U32 WINCALL PassThruStartPeriodicMsg(", start)
        part = SRC[start:stop]
        self.assertIn("c->filters_count--;", part)
        self.assertIn('logline("J2534 filter stopped channel/id (BE)",released,8);', part)
        self.assertLess(part.index("c->filters_count--;"),
                        part.index("J2534 filter stopped channel/id (BE)"))
        self.assertLess(part.index("J2534 filter stopped channel/id (BE)"),
                        part.index("unlock_state();return error(ERR_OK);"))
        self.assertIn("unlock_state();return error(ERR_INVALID_FILTER_ID);", part)

    def test_05_stop_metadata_two_u32_fields(self):
        pattern = (r"\{U8 released\[8\];"
                   r"u32_be\(released,id\);u32_be\(released\+4,filter_id\);"
                   r'\s*logline\("J2534 filter stopped channel/id \(BE\)",released,8\);\}')
        self.assertIsNotNone(re.search(pattern, SRC))

    def test_06_strict_policy_records_loaded_bit_without_change(self):
        self.assertIn(
            'GetPrivateProfileStringA("Diagnostics","StrictJ2534Filters","0",v,sizeof(v),g_profile_path);',
            SRC)
        self.assertIn("g_strict_j2534_filters=parse_num(v,0)==1u?1u:0u;", SRC)
        self.assertIn("u32_be(strict_be,g_strict_j2534_filters);", SRC)
        self.assertIn('logline("J2534 native strict RX filter policy (BE)",strict_be,4);', SRC)

    def test_07_tx_rx_and_disconnect_channel_evidence_retained(self):
        for literal in (
            "TX context channel/protocol/flags/baud/time-us (BE)",
            "RX context channel/protocol/status/baud/time-us (BE)",
            "PassThruDisconnect channel (BE)",
            "PassThruClose",
            "P2 D2 request target/opcode/baud/flags (BE)",
        ):
            self.assertIn(literal, SRC)

    def test_08_no_new_source_label_includes_raw_identity(self):
        for label in (
            "J2534 filter accepted channel/type/id/protocol/baud (BE)",
            "J2534 filter stopped channel/id (BE)",
            "J2534 native strict RX filter policy (BE)",
        ):
            self.assertEqual(SRC.count('logline("' + label + '"'), 1)
            self.assertNotIn("VIN", label)
            self.assertNotIn("raw", label.lower())

    def test_09_filter_state_dispatch_remains_source_present(self):
        self.assertIn("static int strict_filter_matches(", SRC)
        self.assertIn("static int filter_allows(", SRC)
        self.assertIn("if(!filter_allows(c,response_id,payload,len))", SRC)
        self.assertIn("return c->protocol==PROTO_CAN?matched_pass:0;", SRC)


if __name__ == "__main__":
    unittest.main()
