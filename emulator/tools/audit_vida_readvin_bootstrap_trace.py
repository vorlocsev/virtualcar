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
_SCRIPT = re.compile(r"\bSP:\s*GetScript\b.*?\bType:\s*['\"]ReadVin['\"]", re.I)
_EMPTY = re.compile(r"\bProfile:\s*['\"]EMPTYPROFILE,?['\"]", re.I)
_FETCHED = re.compile(r"\bFetched script:.*?(?:VCC-225200-1|Read VIN first readout)", re.I)
_RUNNING = re.compile(r"\bRunning script:.*?(?:VCC-225200-1|Read VIN first readout)", re.I)
_REQUEST = re.compile(r"\bVehComm request:\s*Ecu\s*['\"]([0-9A-Fa-f]{1,3})['\"]\s*,\s*Message\s*['\"]([0-9A-Fa-f]{4,16})['\"]", re.I)
_HEXBYTE = re.compile(r'(?<![0-9A-Za-z])[0-9A-Fa-f]{2}(?![0-9A-Za-z])')
_SESSION = re.compile(r'\bStarting new logsession\b', re.I)
_COUNTER_NAMES = (
    'readvin_getscript_declarations', 'readvin_emptyprofile_selections',
    'bootstrap_readvin_fetched', 'bootstrap_readvin_running',
    'vehcomm_p3_f114_requests', 'vehcomm_p2_b9fb_target40_requests',
    'vehcomm_p2_b9fb_target50_requests', 'j2534_p3_f114_tx_frames',
    'j2534_p2_b9fb_target40_tx_frames', 'j2534_p2_b9fb_target50_tx_frames',
    'j2534_rx_direction_lines', 'j2534_rx_id_only_or_short_lines',
    'j2534_rx_p3_positive_prefix_candidates', 'j2534_rx_p2_b9fb_positive_prefix_candidates',
    'j2534_transmitted_frame_indications', 'j2534_err_buffer_empty',
)

def _fresh():
    return {name: 0 for name in _COUNTER_NAMES}


def _can_frame(hextext):
    vals = [int(tok, 16) for tok in _HEXBYTE.findall(hextext)]
    if len(vals) < 5 or len(vals) > 32:
        return None
    can_id = int.from_bytes(bytes(vals[:4]), 'big')
    return can_id, vals[4:]


def audit_text(logtext):
    if not isinstance(logtext, str) or len(logtext.encode('utf-8')) > MAX_BYTES:
        raise ValueError('log is too large')
    summaries = []
    current = _fresh()
    tracked = False
    line_count = 0
    for line in logtext.splitlines():
        line_count += 1
        if len(line) > MAX_LINE_LENGTH:
            raise ValueError('oversized log line')
        if _SESSION.search(line):
            if tracked or any(current.values()):
                summaries.append(current)
            if len(summaries) >= MAX_SESSIONS:
                raise ValueError('too many sessions')
            current = _fresh()
            tracked = False
        if _SCRIPT.search(line):
            current['readvin_getscript_declarations'] += 1
            if _EMPTY.search(line):
                current['readvin_emptyprofile_selections'] += 1
                tracked = True
            continue
        # Forbid unrelated sections in a log file from creating evidence.
        if not tracked:
            continue
        if _FETCHED.search(line):
            current['bootstrap_readvin_fetched'] += 1
        if _RUNNING.search(line):
            current['bootstrap_readvin_running'] += 1
        req = _REQUEST.search(line)
        if req:
            ecu, service = req.group(1).lower(), req.group(2).lower()
            if ecu == '726' and service == '22f114':
                current['vehcomm_p3_f114_requests'] += 1
            elif ecu in ('40', '50') and service == 'b9fb':
                current[f'vehcomm_p2_b9fb_target{ecu}_requests'] += 1
        if 'ERR_BUFFER_EMPTY' in line.upper():
            current['j2534_err_buffer_empty'] += 1
        if 'TRANSMITTED FRAME indication' in line:
            current['j2534_transmitted_frame_indications'] += 1
        if '--->' in line:
            frame = _can_frame(line.split('--->', 1)[1])
            if frame is None:
                continue
            canid, payload = frame
            if canid == 0x726 and payload[:3] == [0x22, 0xf1, 0x14]:
                current['j2534_p3_f114_tx_frames'] += 1
            elif canid == 0xffffe and len(payload) >= 4 and payload[0] == 0xcb and payload[1] in (0x40, 0x50) and payload[2:4] == [0xb9, 0xfb]:
                current[f'j2534_p2_b9fb_target{payload[1]:02x}_tx_frames'] += 1
        if '<---' in line:
            current['j2534_rx_direction_lines'] += 1
            frame = _can_frame(line.split('<---', 1)[1])
            if frame is None:
                current['j2534_rx_id_only_or_short_lines'] += 1
                continue
            _, payload = frame
            # Prefix only, not a complete/validated ECU response or VIN.
            if payload[:3] == [0x62, 0xf1, 0x14]:
                current['j2534_rx_p3_positive_prefix_candidates'] += 1
            if (len(payload) >= 4 and (payload[0] in (0x8f, 0x97) or 0xc8 <= payload[0] <= 0xcf)
                    and payload[1] in (0x40, 0x50) and payload[2:4] == [0xf9, 0xfb]):
                current['j2534_rx_p2_b9fb_positive_prefix_candidates'] += 1
    if tracked or any(current.values()):
        summaries.append(current)
    if len(summaries) > MAX_SESSIONS:
        raise ValueError('too many sessions')
    totals = {name: sum(s[name] for s in summaries) for name in _COUNTER_NAMES}
    sessions_with_all_published_request_families = sum(
        bool(s['readvin_emptyprofile_selections'] and s['vehcomm_p3_f114_requests']
             and s['vehcomm_p2_b9fb_target40_requests'] and s['vehcomm_p2_b9fb_target50_requests'])
        for s in summaries
    )
    return {
        'schema_version': SCHEMA,
        'analysis_source': 'local_text_log_only_not_a_diagnostic_capture',
        'session_count': len(summaries),
        'sessions_with_all_three_request_families': sessions_with_all_published_request_families,
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
        result = audit_text(raw.decode('utf-8-sig', errors='replace'))
        with out.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except (OSError, ValueError) as exc:
        ap.error('private log classification failed: ' + type(exc).__name__)
    print('VIDA bootstrap request categories recorded; no client VIN has been verified')

if __name__ == '__main__':
    main()
