"""Eight synthetic regression groups, with no private startup-log content."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_server_startup import audit_text, audit_file, main, MAX_BYTES


def line(msg):
    return '2026-10-29 15:01:59,615 INFO [org.jboss.as] (thread) ' + msg + '\n'


def start():
    return line('WFLYSRV0049: JBoss starting')


class AuditVidaServerLogTests(unittest.TestCase):
    def test_01_two_startup_sessions_do_not_cross_count(self):
        result = audit_text(start() + line('WFLYSRV0010: Deployed "VidaEar.ear"') +
                            line('WFLYSRV0025: Started') + start() +
                            line('Failed to initialize WSL validation framework'))
        self.assertEqual(result['observed_startup_sessions'], 2)
        self.assertTrue(result['sessions'][0]['web_server_ready_marker_seen'])
        self.assertFalse(result['sessions'][0]['wsl_failure_marker_seen'])
        self.assertFalse(result['sessions'][1]['web_server_ready_marker_seen'])
        self.assertTrue(result['sessions'][1]['wsl_failure_marker_seen'])

    def test_02_sql_success_marker_does_not_claim_repo_procedure(self):
        result = audit_text(start() + line('Database Product: Microsoft SQL Server Version: 17') +
                            line('DataSource Loaded(accessserver) JNDI: jdbc/accessserver'))
        one = result['sessions'][0]
        self.assertEqual(one['counts']['sql_jdbc_product_seen'], 1)
        self.assertEqual(one['counts']['accessserver_datasource_loaded'], 1)
        self.assertFalse(one['sql_stored_procedure_executed_verified'])
        self.assertTrue(result['db_product_marker_not_proof_of_DiagSwdlRepository_access'])

    def test_03_wsl_failure_not_j2534_failure(self):
        result = audit_text(start() + line('The provider self-integrity check failed.'))
        self.assertTrue(result['sessions'][0]['wsl_failure_marker_seen'])
        self.assertFalse(result['sessions'][0]['j2534_pass_thru_connect_verified'])
        self.assertTrue(result['wsl_error_not_evidence_of_CAN_timeout'])

    def test_04_diagnostic_words_are_only_lexical_mentions(self):
        result = audit_text(start() + line('GetScript ReadVin J2534 DiagSwdlRepository'))
        seen = result['sessions'][0]['diagnostic_token_counts']
        self.assertEqual(seen, {'GetScript': 1, 'ReadVin': 1, 'DiagSwdlRepository': 1, 'J2534': 1})
        self.assertFalse(result['sessions'][0]['readvin_selected_or_executed_verified'])
        self.assertFalse(result['sessions'][0]['vehicle_identity_accepted_verified'])

    def test_05_orphaned_prefix_not_attached_to_future_session(self):
        result = audit_text(line('The provider self-integrity check failed.') + start())
        self.assertEqual(result['nonempty_lines_before_first_start'], 1)
        self.assertFalse(result['sessions'][0]['wsl_failure_marker_seen'])

    def test_06_empty_and_large_inputs(self):
        self.assertEqual(audit_text('')['observed_startup_sessions'], 0)
        with self.assertRaises(ValueError): audit_text('x' * (MAX_BYTES + 1))
        with self.assertRaises(ValueError): audit_text(None)

    def test_07_privacy_output_contains_only_fixed_keys(self):
        sample = start() + line('HOST_PRIVATE_VIN_PASSWORD USER_PRIVATE_BOB') + \
                 line('WFLYSRV0025: started')
        result = audit_text(sample)
        output = json.dumps(result)
        for token in ('HOST_PRIVATE_VIN_PASSWORD', 'USER_PRIVATE_BOB', '2026-10-29'):
            self.assertNotIn(token, output)
        self.assertFalse(result['replay_approved'])

    def test_08_cli_rejects_overwrite_and_symlink_source(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            src = p / 'PRIVATE_STARTUP.log'
            out = p / 'report.json'
            src.write_text(start() + line('WFLYSRV0025: started'), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(src), '--output', str(out)])
            self.assertEqual(json.loads(out.read_text())['observed_startup_sessions'], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(src), '--output', str(out)])
            link = p / 'other.log'
            try:
                link.symlink_to(src)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValueError):
                audit_file(link)


if __name__ == '__main__':
    unittest.main()
