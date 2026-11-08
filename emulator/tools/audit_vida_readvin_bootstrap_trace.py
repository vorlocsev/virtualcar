#!/usr/bin/env python3
"""Offline, bounded and privacy-safe VIDA ReadVin bootstrap log audit.

Separates public-style ReadVin GetScript selections, diagnostic requests,
J2534 TX and raw RX-looking text. Never interprets TX indication as RX, and
never infers real VIN, successful ECU communication or XC90 identification.
The input log remains private and no raw line, VIN, profile, ID or path is emitted.
"""
import argparse
import json
from pathlib import Path
import re

SCHEMA = 'virtualcar-vida-readvin-bootstrap-log-evidence-v1'
MAX_BYTES = 8 * 1024 * 1024
MAX_SESSIONS = 100
MAX_LINE_LENGTH = 8192
_GETSCRIPT = re.compile(r'\bSP:\s*GetScript\b', re.I)
_SCRIPT = re.compile(r"\bSP:\s*GetScript\b.*?\bType:\s*['\"]ReadVin['\"]", re.I)
_EMPTY = re.compile(r"\bProfile:\s*['\"]EMPTYPROFILE,?['\"]", re.I)
_FETCHED = re.compile(r"\bFetched script:.*?(?:VCC-225200-1|Read VIN first readout)", re.I)
_RUNNING = re.compile(r"\bRunning script:.*?(?:VCC-225200-1|Read VIN first readout)", re.I)
_RUNNING_ANY = re.compile(r"\bRunning script\s*:", re.I)
_FETCHED_ANY = re.compile(r"\bFetched script\s*:", re.I)
_FETCHED_LABEL = re.compile(r"\bFetched script:\s*['\"]([^'\"]{1,160})['\"]", re.I)
_RUNNING_LABEL = re.compile(r"\bRunning script:\s*['\"]([^'\"]{1,160})['\"]", re.I)
_EXPECTED_SCRIPT_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z')
_VERSION = re.compile(r'[0-9]+(?:\.[0-9]+){0,3}\Z')

_REQUEST = re.compile(r"\bVehComm request:\s*Ecu\s*['\"]([0-9A-Fa-f]{1,3})['\"]\s*,\s*Message\s*['\"]([0-9A-Fa-f]{4,16})['\"]", re.I)
_HEXBYTE = re.compile(r'(?<![0-9A-Za-z])[0-9A-Fa-f]{2}(?![0-9A-Za-z])')
_SESSION = re.compile(r'\bStarting new logsession\b', re.I)
_RX_FAMILIES = frozenset(('p3_f114', 'p2_b9fb_40', 'p2_b9fb_50'))
_HEX_CAN_ID = re.compile(r'0[xX][0-9A-Fa-f]{1,8}\Z')
_COUNTER_NAMES = (
    'readvin_getscript_declarations', 'readvin_emptyprofile_selections',
    'bootstrap_readvin_fetched', 'bootstrap_readvin_running',
    'vehcomm_p3_f114_requests', 'vehcomm_p2_b9fb_target40_requests',
    'vehcomm_p2_b9fb_target50_requests', 'j2534_p3_f114_tx_frames',
    'j2534_p2_b9fb_target40_tx_frames', 'j2534_p2_b9fb_target50_tx_frames',
    'j2534_rx_direction_lines', 'j2534_rx_id_only_or_short_lines',
    'j2534_rx_p3_positive_prefix_candidates', 'j2534_rx_p2_b9fb_positive_prefix_candidates',
    'j2534_transmitted_frame_indications', 'j2534_err_buffer_empty',
    'rx_p3_prefix_after_ordered_request_tx_candidates',
    'rx_p2_target40_prefix_after_ordered_request_tx_candidates',
    'rx_p2_target50_prefix_after_ordered_request_tx_candidates',
)

def _fresh():
    return {name: 0 for name in _COUNTER_NAMES}


def _can_frame(hextext):
    vals = [int(tok, 16) for tok in _HEXBYTE.findall(hextext)]
    if len(vals) < 5 or len(vals) > 32:
        return None
    can_id = int.from_bytes(bytes(vals[:4]), 'big')
    return can_id, vals[4:]


def _rx_response_prefix_candidate_family(canid, payload):
    """Recognize response-shaped prefixes on non-transmit CAN IDs only.

    Without J2534 RxStatus and protocol metadata, this is a lexical candidate,
    NOT proof of ECU delivery, successful decoding or response correlation.
    """
    if (canid != 0x726 and canid <= 0x7ff and
            payload[:3] == [0x62, 0xf1, 0x14]):
        return 'p3_f114'
    if (canid != 0xffffe and canid <= 0x1fffffff and canid & 1 and
            len(payload) >= 4 and
            (payload[0] in (0x8f, 0x97) or 0xc8 <= payload[0] <= 0xcf) and
            payload[1] in (0x40, 0x50) and payload[2:4] == [0xf9, 0xfb]):
        return 'p2_b9fb_' + f'{payload[1]:02x}'
    return None


def _matched_script_version(line, pattern, expected):
    """Return exact version (empty if unversioned), or None for nonmatch."""
    match = pattern.search(line)
    if match is None:
        return None
    label = match.group(1)
    if label == expected:
        return ''
    prefix = expected + ' '
    if label.startswith(prefix) and _VERSION.fullmatch(label[len(prefix):]):
        return label[len(prefix):]
    return None


def _parse_rx_can_id(value):
    if not isinstance(value, str) or _HEX_CAN_ID.fullmatch(value) is None:
        raise ValueError('RX source CAN ID must be a hexadecimal 0x-prefixed value')
    return int(value, 16)


def _validate_rx_can_ids(rx_can_ids):
    # User-provided source addresses, NEVER automatically inferred from a log.
    if not isinstance(rx_can_ids, dict) or rx_can_ids.keys() != _RX_FAMILIES:
        raise ValueError('all three explicit RX source CAN IDs are required')
    if any(type(n) is not int for n in rx_can_ids.values()):
        raise ValueError('RX IDs must be integers, not booleans or raw strings')
    p3, p240, p250 = (rx_can_ids[k] for k in ('p3_f114', 'p2_b9fb_40', 'p2_b9fb_50'))
    if not 0 < p3 <= 0x7ff or p3 == 0x726:
        raise ValueError('invalid 11-bit P3 response source CAN ID')
    if (any(not 0x7ff < n <= 0x1fffffff or not (n & 1) or n == 0xffffe
            for n in (p240, p250)) or len({p3, p240, p250}) != 3):
        raise ValueError('invalid or duplicate 29-bit P2 response source CAN IDs')


def audit_text(logtext, expected_script_id=None, expected_rx_can_ids=None):
    # Optional strict label matching only. A log line is not proof of
    # database selection, native execution or a positive ECU response.
    if expected_script_id is not None and (
            not isinstance(expected_script_id, str) or
            _EXPECTED_SCRIPT_ID.fullmatch(expected_script_id) is None):
        raise ValueError('invalid expected script identifier')
    if expected_rx_can_ids is not None:
        if expected_script_id is None:
            raise ValueError('explicit RX CAN IDs require a selected script ID')
        _validate_rx_can_ids(expected_rx_can_ids)
    if not isinstance(logtext, str) or len(logtext.encode('utf-8')) > MAX_BYTES:
        raise ValueError('log is too large')
    summaries = []
    complete_windows_by_session = []
    ordered_run_by_session = []
    ordered_run_with_requests_by_session = []
    ordered_run_with_requests_and_tx_by_session = []
    ordered_req_before_tx_by_session = []
    ordered_request_tx_rx_by_session = []
    exact_source_rx_by_session = []
    current = _fresh()
    tracked = False
    request_families_in_window = set()
    request_families_after_run = set()
    tx_families_after_run = set()
    request_waiting_for_tx = set()
    ordered_request_tx_families = set()
    pending_tx_rx_families = set()
    rx_prefix_families_in_window = set()
    exact_source_rx_families_in_window = set()
    expected_fetched = False
    fetched_version = None
    expected_running = False
    session_has_ordered_run = False
    session_has_ordered_run_with_requests = False
    session_has_ordered_run_with_requests_and_tx = False
    session_has_ordered_req_before_tx = False
    session_has_ordered_request_tx_rx = False
    session_has_exact_source_rx = False
    session_has_complete_window = False
    line_count = 0
    for line in logtext.splitlines():
        line_count += 1
        if len(line) > MAX_LINE_LENGTH:
            raise ValueError('oversized log line')
        if _SESSION.search(line):
            if tracked or any(current.values()):
                summaries.append(current)
                complete_windows_by_session.append(session_has_complete_window)
                ordered_run_by_session.append(session_has_ordered_run)
                ordered_run_with_requests_by_session.append(session_has_ordered_run_with_requests)
                ordered_run_with_requests_and_tx_by_session.append(session_has_ordered_run_with_requests_and_tx)
                ordered_req_before_tx_by_session.append(session_has_ordered_req_before_tx)
                ordered_request_tx_rx_by_session.append(session_has_ordered_request_tx_rx)
                exact_source_rx_by_session.append(session_has_exact_source_rx)
            if len(summaries) >= MAX_SESSIONS:
                raise ValueError('too many sessions')
            current = _fresh()
            tracked = False
            request_families_in_window.clear()
            request_families_after_run.clear()
            tx_families_after_run.clear()
            request_waiting_for_tx.clear()
            ordered_request_tx_families.clear()
            pending_tx_rx_families.clear()
            rx_prefix_families_in_window.clear()
            exact_source_rx_families_in_window.clear()
            expected_fetched = False
            fetched_version = None
            expected_running = False
            session_has_complete_window = False
            session_has_ordered_run = False
            session_has_ordered_run_with_requests = False
            session_has_ordered_run_with_requests_and_tx = False
            session_has_ordered_req_before_tx = False
            session_has_ordered_request_tx_rx = False
            session_has_exact_source_rx = False
        if _GETSCRIPT.search(line):
            # A new selected script closes the previous bootstrap window,
            # even when it is a different type or a profiled ReadVin.
            request_families_in_window.clear()
            request_families_after_run.clear()
            tx_families_after_run.clear()
            request_waiting_for_tx.clear()
            ordered_request_tx_families.clear()
            pending_tx_rx_families.clear()
            rx_prefix_families_in_window.clear()
            exact_source_rx_families_in_window.clear()
            expected_fetched = False
            fetched_version = None
            expected_running = False
            is_readvin = bool(_SCRIPT.search(line))
            tracked = is_readvin and bool(_EMPTY.search(line))
            if is_readvin:
                current['readvin_getscript_declarations'] += 1
                if tracked:
                    current['readvin_emptyprofile_selections'] += 1
            continue
        # A different script can start without an intervening GetScript log line
        # (for example, a cached script). Close this bootstrap window rather
        # than attributing its later diagnostic traffic to ReadVin.
        if _RUNNING_ANY.search(line):
            if expected_script_id is not None:
                running_version = _matched_script_version(
                    line, _RUNNING_LABEL, expected_script_id)
                if (running_version is None or
                        (expected_fetched and running_version != fetched_version)):
                    # Even the same script ID with a different version is a
                    # different fetched artifact; close this evidence window.
                    tracked = False
                    request_families_in_window.clear()
                    request_families_after_run.clear()
                    tx_families_after_run.clear()
                    request_waiting_for_tx.clear()
                    ordered_request_tx_families.clear()
                    pending_tx_rx_families.clear()
                    rx_prefix_families_in_window.clear()
                    exact_source_rx_families_in_window.clear()
                    expected_fetched = False
                    fetched_version = None
                    expected_running = False
                    continue
                if tracked and expected_fetched:
                    session_has_ordered_run = True
                    expected_running = True
                else:
                    # A matching Running line without an earlier Fetched line
                    # cannot establish this window's expected script chain.
                    expected_running = False
                    request_families_after_run.clear()
                    tx_families_after_run.clear()
                    request_waiting_for_tx.clear()
                    ordered_request_tx_families.clear()
                    pending_tx_rx_families.clear()
                    rx_prefix_families_in_window.clear()
                    exact_source_rx_families_in_window.clear()
                expected_fetched = False
                fetched_version = None
            elif not _RUNNING.search(line):
                tracked = False
                request_families_in_window.clear()
                continue
        # Forbid unrelated sections in a log file from creating evidence.
        if not tracked:
            continue
        if expected_script_id is not None and _FETCHED_ANY.search(line):
            # Any new fetch supersedes the previous candidate. Do not join
            # a Fetched line for one script with a Running line for another.
            fetched_version = _matched_script_version(
                line, _FETCHED_LABEL, expected_script_id)
            expected_fetched = fetched_version is not None
            expected_running = False
            request_families_after_run.clear()
            tx_families_after_run.clear()
            request_waiting_for_tx.clear()
            ordered_request_tx_families.clear()
            pending_tx_rx_families.clear()
            rx_prefix_families_in_window.clear()
            exact_source_rx_families_in_window.clear()
        if _FETCHED.search(line):
            current['bootstrap_readvin_fetched'] += 1
        if _RUNNING.search(line):
            current['bootstrap_readvin_running'] += 1
        req = _REQUEST.search(line)
        if req:
            ecu, service = req.group(1).lower(), req.group(2).lower()
            if ecu == '726' and service == '22f114':
                current['vehcomm_p3_f114_requests'] += 1
                request_families_in_window.add('p3_f114')
            elif ecu in ('40', '50') and service == 'b9fb':
                current[f'vehcomm_p2_b9fb_target{ecu}_requests'] += 1
                request_families_in_window.add('p2_b9fb_' + ecu)
            if len(request_families_in_window) == 3:
                session_has_complete_window = True
            if expected_running:
                if ecu == '726' and service == '22f114':
                    request_families_after_run.add('p3_f114')
                elif ecu in ('40', '50') and service == 'b9fb':
                    request_families_after_run.add('p2_b9fb_' + ecu)
                if ecu == '726' and service == '22f114':
                    new_family = 'p3_f114'
                elif ecu in ('40', '50') and service == 'b9fb':
                    new_family = 'p2_b9fb_' + ecu
                else:
                    new_family = None
                if new_family is not None:
                    # An RX after a new request must not reuse a prior TX.
                    pending_tx_rx_families.discard(new_family)
                    request_waiting_for_tx.add(new_family)
                if len(request_families_after_run) == 3:
                    session_has_ordered_run_with_requests = True
                    if len(tx_families_after_run) == 3:
                        session_has_ordered_run_with_requests_and_tx = True
        if 'ERR_BUFFER_EMPTY' in line.upper():
            current['j2534_err_buffer_empty'] += 1
        if 'TRANSMITTED FRAME indication' in line:
            current['j2534_transmitted_frame_indications'] += 1
        if '--->' in line:
            frame = _can_frame(line.split('--->', 1)[1])
            if frame is None:
                continue
            canid, payload = frame
            tx_family = None
            if canid == 0x726 and payload[:3] == [0x22, 0xf1, 0x14]:
                current['j2534_p3_f114_tx_frames'] += 1
                tx_family = 'p3_f114'
            elif (canid == 0xffffe and len(payload) >= 4 and
                  payload[0] == 0xcb and payload[1] in (0x40, 0x50) and
                  payload[2:4] == [0xb9, 0xfb]):
                current[f'j2534_p2_b9fb_target{payload[1]:02x}_tx_frames'] += 1
                tx_family = 'p2_b9fb_' + f'{payload[1]:02x}'
            if expected_running and tx_family:
                tx_families_after_run.add(tx_family)
                # Only prefix-order evidence. This does not establish a J2534
                # transaction ID, transmission success, or an ECU response.
                if tx_family in request_waiting_for_tx:
                    ordered_request_tx_families.add(tx_family)
                    request_waiting_for_tx.discard(tx_family)
                    pending_tx_rx_families.add(tx_family)
                    if len(ordered_request_tx_families) == 3:
                        session_has_ordered_req_before_tx = True
                if (len(request_families_after_run) == 3 and
                        len(tx_families_after_run) == 3):
                    session_has_ordered_run_with_requests_and_tx = True
        if '<---' in line:
            current['j2534_rx_direction_lines'] += 1
            frame = _can_frame(line.split('<---', 1)[1])
            if frame is None:
                current['j2534_rx_id_only_or_short_lines'] += 1
                continue
            canid, payload = frame
            # Prefix only, not a complete/validated ECU response or VIN.
            # Do not promote TX echoes or explicit J2534 transmit indications.
            if (expected_running and '--->' not in line and
                    'TRANSMITTED FRAME INDICATION' not in line.upper() and
                    'TX_MSG_TYPE' not in line.upper()):
                rx_family = _rx_response_prefix_candidate_family(canid, payload)
                if rx_family in pending_tx_rx_families:
                    pending_tx_rx_families.remove(rx_family)
                    rx_prefix_families_in_window.add(rx_family)
                    if (expected_rx_can_ids is not None and
                            canid == expected_rx_can_ids[rx_family]):
                        exact_source_rx_families_in_window.add(rx_family)
                        if len(exact_source_rx_families_in_window) == 3:
                            session_has_exact_source_rx = True
                    key = {
                        'p3_f114': 'rx_p3_prefix_after_ordered_request_tx_candidates',
                        'p2_b9fb_40': 'rx_p2_target40_prefix_after_ordered_request_tx_candidates',
                        'p2_b9fb_50': 'rx_p2_target50_prefix_after_ordered_request_tx_candidates',
                    }[rx_family]
                    current[key] += 1
                    if len(rx_prefix_families_in_window) == 3:
                        session_has_ordered_request_tx_rx = True
            if payload[:3] == [0x62, 0xf1, 0x14]:
                current['j2534_rx_p3_positive_prefix_candidates'] += 1
            if (len(payload) >= 4 and (payload[0] in (0x8f, 0x97) or 0xc8 <= payload[0] <= 0xcf)
                    and payload[1] in (0x40, 0x50) and payload[2:4] == [0xf9, 0xfb]):
                current['j2534_rx_p2_b9fb_positive_prefix_candidates'] += 1
    if tracked or any(current.values()):
        summaries.append(current)
        complete_windows_by_session.append(session_has_complete_window)
        ordered_run_by_session.append(session_has_ordered_run)
        ordered_run_with_requests_by_session.append(session_has_ordered_run_with_requests)
        ordered_run_with_requests_and_tx_by_session.append(session_has_ordered_run_with_requests_and_tx)
        ordered_req_before_tx_by_session.append(session_has_ordered_req_before_tx)
        ordered_request_tx_rx_by_session.append(session_has_ordered_request_tx_rx)
        exact_source_rx_by_session.append(session_has_exact_source_rx)
    if len(summaries) > MAX_SESSIONS:
        raise ValueError('too many sessions')
    totals = {name: sum(s[name] for s in summaries) for name in _COUNTER_NAMES}
    # Only a single uninterrupted EMPTYPROFILE GetScript selection may
    # satisfy the three-family gate. Never join separate scripts/windows.
    sessions_with_all_published_request_families = sum(complete_windows_by_session)
    return {
        'schema_version': SCHEMA,
        'analysis_source': 'local_text_log_only_not_a_diagnostic_capture',
        'session_count': len(summaries),
        'sessions_with_all_three_request_families': sessions_with_all_published_request_families,
        'expected_script_id_filter_supplied': expected_script_id is not None,
        'sessions_with_ordered_expected_script_fetch_run_lines': sum(ordered_run_by_session),
        'sessions_with_ordered_expected_script_run_and_three_request_families': sum(
            ordered_run_with_requests_by_session),
        'sessions_with_ordered_expected_script_requests_and_tx': sum(
            ordered_run_with_requests_and_tx_by_session),
        'sessions_with_ordered_expected_script_request_before_tx_all_families': sum(
            ordered_req_before_tx_by_session),
        'sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates': sum(
            ordered_request_tx_rx_by_session),
        'rx_expected_can_id_filter_supplied': expected_rx_can_ids is not None,
        'sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates': sum(
            exact_source_rx_by_session),
        'runtime_getscript_selection_verified': False,
        'session_counters': summaries,
        'totals': totals,
        'readvin_selected_from_actual_getscript_database_verified': False,
        'candidate_positive_rx_prefix_is_not_verified_ecu_payload': True,
        'j2534_tx_indication_is_not_ecu_rx': True,
        'actual_positive_ecu_reply_correlated': False,
        'original_readvin_xml_binding_verified': False,
        'real_vin_value_seen_or_emitted': False,
        'client_vin_accepted': False,
        'xc90_v8_my2009_identified': False,
        'replay_approved': False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='Privacy-safe VIDA bootstrap ReadVin log classifier')
    ap.add_argument('private_log', type=Path)
    ap.add_argument('--expected-script-id', help='private exact script ID for log-only sequence classification')
    ap.add_argument('--rx-p3-can-id', help='optional expected P3 response source CAN ID (hex 0x...)')
    ap.add_argument('--rx-p2-40-can-id', help='optional expected P2 0x40 response source CAN ID (hex 0x...)')
    ap.add_argument('--rx-p2-50-can-id', help='optional expected P2 0x50 response source CAN ID (hex 0x...)')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv)
    source = args.private_log.resolve()
    out = args.output.resolve()
    repository = Path(__file__).resolve().parents[2]
    if out == source or out == repository or repository in out.parents or args.output.parent.is_symlink():
        ap.error('unsafe output destination')
    try:
        if not source.is_file() or args.private_log.is_symlink() or source.stat().st_size > MAX_BYTES:
            raise ValueError('source is unsupported')
        raw = source.read_bytes()
        if b'\x00' in raw[:256]:
            raise ValueError('binary or UTF-16 log unsupported')
        supplied_rx = (args.rx_p3_can_id, args.rx_p2_40_can_id, args.rx_p2_50_can_id)
        rx_source_filter = None
        if any(value is not None for value in supplied_rx):
            if any(value is None for value in supplied_rx):
                raise ValueError('all three expected RX source CAN IDs are required')
            rx_source_filter = dict(zip(
                ('p3_f114', 'p2_b9fb_40', 'p2_b9fb_50'),
                (_parse_rx_can_id(value) for value in supplied_rx)))
        result = audit_text(raw.decode('utf-8-sig', errors='replace'),
                            args.expected_script_id, rx_source_filter)
        with out.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except (OSError, ValueError) as exc:
        ap.error('private log classification failed: ' + type(exc).__name__)
    print('VIDA bootstrap request categories recorded; no client VIN has been verified')

if __name__ == '__main__':
    main()
