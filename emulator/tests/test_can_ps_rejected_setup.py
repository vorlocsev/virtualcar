"""Eight synthetic groups for PS setup arguments; no API success or ECU response."""
import json
from pathlib import Path
import tempfile
import unittest

from test_audit_j2534_connect import tool, be, conn
from test_can_ps_rejected_attempts import attempt


def filter_event(kind=1, protocols=1, sizes=1, flags=2, flow=0, mask=3, pattern=3, status=1, channel=1):
    return (f"[PID=1234ABCD PrivateClient.exe] {tool.PS_FILTER} "
            f"{be(channel, kind, protocols, sizes, flags, flow, mask, pattern, status)}\n")


def periodic_event(protocol=0x8004, interval=4000, check=0, status=1, channel=1):
    return (f"[PID=1234ABCD PrivateClient.exe] {tool.PS_PERIODIC} "
            f"{be(channel, protocol, interval, check, status)}\n")


class CanPsRejectedSetupTests(unittest.TestCase):
    def test_01_filter_and_periodic_are_separate_rejected_calls(self):
        result = tool.audit([filter_event(), periodic_event(), attempt(origin=2, shape=42)])
        setup = result['can_ps_rejected_setup']
        self.assertEqual((setup['filter_calls'], setup['periodic_registration_calls']), (1, 1))
        self.assertEqual(result['rejected_can_ps_attempts']['calls'], 1)
        self.assertEqual(setup['outcome'], 'rejected_not_registered')
        self.assertFalse(setup['read_only_reference_approved'])
        self.assertFalse(setup['periodic_firing_observed'])
        self.assertEqual(setup['periodic'][0]['interval_ms'], '4000')

    def test_02_filter_protocol_size_flags_and_flow_remain_categories(self):
        lines = [filter_event(kind=i, flow=i%2) for i in range(4)]
        lines += [filter_event(protocols=p, sizes=s, mask=0, pattern=0, flags=f)
                  for p, s, f in ((0,0,0), (1,2,1), (2,3,2), (3,1,3), (4,4,0))]
        data = tool.audit(lines)['can_ps_rejected_setup']
        self.assertEqual((data['filter_calls'], data['invalid_filter_events']), (9, 0))
        self.assertEqual({x['message_protocols'] for x in data['filters']}, set(tool.FILTER_PROTOCOLS.values()))
        self.assertEqual({x['flow'] for x in data['filters']}, {'absent', 'present_uninspected'})

    def test_03_full_mask_is_not_an_invalid_can_id(self):
        data = tool.audit([filter_event(mask=m, pattern=p) for m in range(1,6) for p in range(1,5)])[
            'can_ps_rejected_setup']
        self.assertEqual(data['filter_calls'], 20)
        self.assertTrue(any(x['mask']=='full_uint32' and x['pattern']=='outside_can_id_range'
                            for x in data['filters']))
        self.assertNotIn('FFFFFFFF', json.dumps(data))

    def test_04_uninspected_or_impossible_filter_combinations_fail_closed(self):
        bad = [filter_event(channel=0), filter_event(kind=4), filter_event(protocols=5),
               filter_event(sizes=5), filter_event(flags=4), filter_event(flow=2),
               filter_event(mask=6), filter_event(pattern=5), filter_event(status=0),
               filter_event(mask=0), filter_event(pattern=0), filter_event(protocols=3),
               filter_event(sizes=2), filter_event(protocols=4)]
        data = tool.audit(bad)['can_ps_rejected_setup']
        self.assertEqual((data['filter_calls'],data['invalid_filter_events']), (0,len(bad)))
        self.assertEqual(data['filters'], [])

    def test_05_periodic_allowlist_and_redacted_interval_ranges(self):
        lines = [periodic_event(interval=i) for i in tool.PERIODIC_INTERVALS]
        lines += [periodic_event(protocol=p, interval=0, check=check)
                  for p in (0,5,6,0x8004) for check in (1,2)]
        data = tool.audit(lines)['can_ps_rejected_setup']
        self.assertEqual(data['periodic_registration_calls'], len(lines))
        self.assertEqual(data['invalid_periodic_events'], 0)
        self.assertEqual({x['interval_check'] for x in data['periodic']}, set(tool.PERIODIC_CHECKS.values()))
        bad = [periodic_event(interval=0), periodic_event(interval=4001), periodic_event(interval=0xDEADBEEF),
               periodic_event(check=1), periodic_event(check=2), periodic_event(check=3),
               periodic_event(status=0), periodic_event(protocol=99), periodic_event(channel=0)]
        data = tool.audit(bad)['can_ps_rejected_setup']
        self.assertEqual((data['periodic_registration_calls'],data['invalid_periodic_events']), (0,len(bad)))

    def test_06_exact_word_counts_and_unknown_context_never_become_calls(self):
        f, p = filter_event().strip(), periodic_event().strip()
        bad_f = [f+' 00', f+' ZZ', f.rsplit(' ',1)[0], f.replace('00 00 00 01','0x00 00 00 01',1)]
        bad_p = [p+' 00', p+' ZZ', p.rsplit(' ',1)[0]]
        data = tool.audit(bad_f+bad_p+[f.replace('1234ABCD','no-pid')])['can_ps_rejected_setup']
        self.assertEqual((data['invalid_filter_events'],data['invalid_periodic_events']), (4,3))
        self.assertEqual((data['filter_calls'],data['periodic_registration_calls']), (0,0))

    def test_07_privacy_source_order_and_old_scope(self):
        lines = [filter_event(), 'unrelated\n', periodic_event(), filter_event(channel=2),
                 '[PID=1234ABCD PrivateClient.exe] filter mask PRIVATE_VIN_PARAMETER\n']
        data = tool.audit(lines)['can_ps_rejected_setup']
        self.assertEqual([x['line'] for x in data['source_order']], [1,3,4])
        self.assertFalse(data['state_correlation_performed'])
        for secret in ('PRIVATE','PrivateClient','1234ABCD','channel','PARAMETER'):
            self.assertNotIn(secret,json.dumps(data))
        self.assertNotIn('can_ps_rejected_setup', tool.audit([conn(5,0,500000,0), attempt()]))

    def test_08_limits_and_exclusive_output(self):
        self.assertNotIn('can_ps_rejected_setup', tool.audit([filter_event().strip()+' '*tool.MAX_LINE]))
        with self.assertRaisesRegex(ValueError,'rejected_setup_limit'):
            tool.audit(periodic_event() for _ in range(tool.MAX_REJECTED_ATTEMPTS+1))
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'source.log', Path(folder)/'audit.json'
            source.write_text(filter_event()+periodic_event(),encoding='utf-8')
            tool.main([str(source),'--output',str(output)])
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                tool.main([str(source),'--output',str(output)])
            self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
