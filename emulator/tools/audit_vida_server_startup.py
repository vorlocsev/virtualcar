#!/usr/bin/env python3
"""Privacy-safe, static audit of locally owned VIDA JBoss server.log.

This is NOT a test of GetScript, DiCE, the client or accepted vehicle identity.
"""
import argparse
import json
from pathlib import Path
import re

MAX_BYTES = 5 * 1024 * 1024
SCHEMA = 'virtualcar-vida-server-startup-v1'
START = re.compile(r'^\S+\s+\S+\s+INFO\s+\[org\.jboss\.as\].*WFLYSRV0049:')
MARKERS = {
    'vida_web_deployed': 'WFLYSRV0010: Deployed "VidaEar.ear"',
    'jboss_started': 'WFLYSRV0025:',
    'sql_jdbc_product_seen': 'Database Product: Microsoft SQL Server',
    'accessserver_datasource_loaded': 'DataSource Loaded(accessserver)',
    'basedata_datasource_loaded': 'DataSource Loaded(BaseData)',
    'carcom_datasource_bound': 'Bound data source [java:/jdbc/carcom]',
    'wsl_initialization_failed': 'Failed to initialize WSL validation framework',
    'wsl_self_integrity_error': 'The provider self-integrity check failed.',
    'last_installed_base_id_2014d': 'LastInstalledBaseId: VIDA2014D',
    'vida_web_stopped': 'Stopped deployment VidaEar.ear',
}
DIAGNOSTIC_TOKENS = ('GetScript', 'ReadVin', 'DiagSwdlRepository', 'J2534')


def audit_text(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('invalid log size')
    sessions = []
    orphaned = 0
    for line in text.splitlines():
        if START.match(line):
            sessions.append({'counters': {key: 0 for key in MARKERS},
                             'diagnostic_token_counts': {key: 0 for key in DIAGNOSTIC_TOKENS}})
        if not sessions:
            if line.strip():
                orphaned += 1
            continue
        counts = sessions[-1]['counters']
        for key, literal in MARKERS.items():
            if literal in line:
                counts[key] += 1
        for token in DIAGNOSTIC_TOKENS:
            if token in line:
                sessions[-1]['diagnostic_token_counts'][token] += 1

    result = []
    for session in sessions:
        counters = session['counters']
        result.append({
            'ordinal': len(result) + 1,
            'counts': counters,
            'diagnostic_token_counts': session['diagnostic_token_counts'],
            'web_server_ready_marker_seen': bool(counters['jboss_started'] and counters['vida_web_deployed']),
            'wsl_failure_marker_seen': bool(counters['wsl_initialization_failed'] or
                                            counters['wsl_self_integrity_error']),
            'readvin_selected_or_executed_verified': False,
            'sql_stored_procedure_executed_verified': False,
            'j2534_pass_thru_connect_verified': False,
            'vehicle_identity_accepted_verified': False,
        })
    return {
        'schema_version': SCHEMA,
        'log_kind': 'VIDA_JBoss_server_log_only',
        'observed_startup_sessions': len(result),
        'nonempty_lines_before_first_start': orphaned,
        'sessions': result,
        'server_log_not_equivalent_to_diagnostic_client_log': True,
        'db_product_marker_not_proof_of_DiagSwdlRepository_access': True,
        'web_deployed_not_proof_of_successful_readvin': True,
        'wsl_error_not_evidence_of_CAN_timeout': True,
        'identity_and_ecu_acceptance_unknown': True,
        'replay_approved': False,
    }


def audit_file(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError('invalid input file')
    return audit_text(p.read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline, read-only VIDA server log categorizer')
    parser.add_argument('private_log', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if out == repo or repo in out.parents or out == args.private_log.resolve():
        parser.error('output must be outside the repository and different from input')
    try:
        result = audit_file(args.private_log)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error('source could not be parsed: ' + type(exc).__name__)
    try:
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except OSError as exc:
        parser.error('cannot create new report: ' + type(exc).__name__)
    print('Server log checked; VIDA ReadVin, VIN and J2534 connection remain UNVERIFIED')


if __name__ == '__main__':
    main()
