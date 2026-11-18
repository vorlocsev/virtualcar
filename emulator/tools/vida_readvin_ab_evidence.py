#!/usr/bin/env python3
"""Read-only owner-local correlation of independent VIDA manual/J2534 GUI observations.

Validates local evidence file hashes, source identity, selected Partner Group,
VIDA installation fingerprint and observation dates. Never executes vendor code,
queries SQL, sends diagnostic traffic, or independently attests the GUI outcome.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

OBS_SCHEMA = 'virtualcar-vida-readvin-observation-v1'
REPORT_SCHEMA = 'virtualcar-vida-readvin-ab-correlation-v1'
CANDIDATE_SCHEMA = 'virtualcar-vida-public-vin-disambiguation-review-v1'
MODES = ('manual', 'j2534')
GUI_RESULTS = ('ACCEPTED', 'REJECTED', 'NOT_TESTED')
TRANSPORT = ('NOT_OBSERVED', 'TX_ONLY', 'RX_DEQUEUED')
MAX_JSON = 128 * 1024
MAX_OUTPUT = 512 * 1024
MAX_EVIDENCE = 200 * 1024 * 1024
SHA256_RE = re.compile(r'[0-9a-f]{64}\Z')
SHA_RE = re.compile(r'[0-9a-f]{40}\Z')
VIN_RE = re.compile(r'[A-HJ-NPR-Z0-9]{17}\Z')


class EvidenceError(ValueError):
    """Fixed error categories: no raw owner filename, VIN, or vendor text."""


def _unique(pairs):
    obj = {}
    for key, val in pairs:
        if key in obj:
            raise EvidenceError('duplicate JSON field')
        obj[key] = val
    return obj


def _nonfinite(_):
    raise EvidenceError('nonfinite JSON number')


def read_json(path: Path, limit: int = MAX_JSON):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise EvidenceError('unsafe JSON input')
    data = path.read_bytes()
    if len(data) > limit:
        raise EvidenceError('large JSON input')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=_unique,
                          parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceError('invalid JSON input') from None


def _string(value, max_length=255):
    return (type(value) is str and 1 <= len(value) <= max_length
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _timestamp(value):
    if not _string(value, 50):
        raise EvidenceError('missing observation time')
    try:
        instant = dt.datetime.fromisoformat(value)
    except ValueError:
        raise EvidenceError('invalid observation time') from None
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise EvidenceError('observation timezone missing')
    return instant.astimezone(dt.timezone.utc)


def _hash_local_file(raw_path, expected):
    if (not _string(raw_path, 2048) or type(expected) is not str
            or not SHA256_RE.fullmatch(expected)):
        raise EvidenceError('missing original source evidence reference')
    file = Path(raw_path)
    # Absolute filenames only: binding the evidence to a cwd is ambiguous.
    if (not file.is_absolute() or file.is_symlink() or not file.is_file()
            or file.stat().st_size > MAX_EVIDENCE):
        raise EvidenceError('source evidence unavailable')
    digest = hashlib.sha256()
    with file.open('rb') as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise EvidenceError('source evidence checksum mismatch')
    return {'sha256': expected, 'size_bytes': file.stat().st_size}


def validate_observation(raw, mode):
    if (type(raw) is not dict or raw.get('schema_version') != OBS_SCHEMA
            or raw.get('mode') != mode
            or type(raw.get('vin_original')) is not str
            or not VIN_RE.fullmatch(raw['vin_original'])
            or type(raw.get('partner_group_original')) is not int
            or raw['partner_group_original'] < 0
            or not _string(raw.get('vida_build'), 128)
            or type(raw.get('workflow_dll_sha256')) is not str
            or not SHA256_RE.fullmatch(raw['workflow_dll_sha256'])
            or raw.get('gui_result') not in GUI_RESULTS
            or type(raw.get('gui_result')) is not str
            or raw.get('transport') not in TRANSPORT
            or type(raw.get('transport')) is not str):
        raise EvidenceError('invalid original VIDA observation')
    timestamp = _timestamp(raw.get('observed_at'))
    # A manual entry and a diagnostic session must be independent.
    head = raw.get('virtualcar_head_sha')
    if mode == 'manual':
        if raw['transport'] != 'NOT_OBSERVED' or head is not None:
            raise EvidenceError('manual observation claims adapter activity')
    elif head is not None and (type(head) is not str or not SHA_RE.fullmatch(head)):
        raise EvidenceError('invalid virtual adapter commit identity')
    if raw['gui_result'] == 'NOT_TESTED':
        if (raw.get('evidence_path') is not None
                or raw.get('evidence_sha256') is not None
                or raw.get('gui_message_original') is not None
                or raw['transport'] != 'NOT_OBSERVED'):
            raise EvidenceError('not-tested observation contains result claims')
        verified_file = None
    else:
        if not _string(raw.get('gui_message_original'), 4096):
            raise EvidenceError('missing original GUI message')
        if mode == 'j2534' and head is None:
            raise EvidenceError('missing exact virtual adapter head')
        verified_file = _hash_local_file(raw.get('evidence_path'), raw.get('evidence_sha256'))
    return {
        'mode': mode,
        'vin_original': raw['vin_original'],
        'partner_group_original': raw['partner_group_original'],
        'vida_build': raw['vida_build'],
        'workflow_dll_sha256': raw['workflow_dll_sha256'],
        'observed_at': timestamp.isoformat(),
        'gui_result_owner_reported': raw['gui_result'],
        'gui_message_original': raw.get('gui_message_original'),
        'transport_owner_reported': raw['transport'],
        'virtualcar_head_sha': head,
        'local_evidence_verified_sha256': verified_file,
    }


def _candidate_metadata(report, vin, partner):
    if report is None:
        return None
    if (type(report) is not dict
            or report.get('schema_version') != CANDIDATE_SCHEMA
            or report.get('vin_original') != vin
            or type(report.get('partner_group_original')) is not int
            or report['partner_group_original'] != partner
            or report.get('original_vida_decoder_runtime_verified') is not False
            or report.get('readvin_gui_acceptance_verified') is not False
            or report.get('ecu_identification_verified') is not False
            or type(report.get('public_filtered_candidate_count')) is not int
            or report['public_filtered_candidate_count'] < 0
            or report.get('public_branch_in_available_inputs') not in (
                'no_remaining_candidate_in_available_inputs',
                'single_vehicle_model_in_remaining_candidates',
                'multiple_vehicle_models_in_remaining_candidates')
            or type(report.get('model_variant_capture_incomplete')) is not bool
            or report.get('vehicle_profile_capture_scope') not in (
                'filtered_subset_only', 'full_within_limit')):
        raise EvidenceError('untrusted offline candidate report')
    return {
        'source_schema_version': CANDIDATE_SCHEMA,
        'candidate_count_only': report['public_filtered_candidate_count'],
        'public_branch_only': report['public_branch_in_available_inputs'],
        'source_model_variant_partial': report['model_variant_capture_incomplete'],
        'source_profiles_partial': report['vehicle_profile_capture_scope'] == 'filtered_subset_only',
        'proof_of_original_vida_decode': False,
    }


def correlate(manual_raw, j2534_raw, candidate_report=None):
    manual = validate_observation(manual_raw, 'manual')
    adapter = validate_observation(j2534_raw, 'j2534')
    comparable_fields = ('vin_original', 'partner_group_original', 'vida_build',
                         'workflow_dll_sha256')
    consistent = all(manual[key] == adapter[key] for key in comparable_fields)
    if not consistent and candidate_report is not None:
        raise EvidenceError('cannot cross-reference mismatched sessions')
    candidate = _candidate_metadata(candidate_report, manual['vin_original'],
                                    manual['partner_group_original'])
    a, b = manual['gui_result_owner_reported'], adapter['gui_result_owner_reported']
    if not consistent:
        classification = 'NOT_COMPARABLE_SOURCE_CONTEXT'
        next_step = 'Use identical original VIN, Partner Group and VIDA Workflow.DLL build for both sessions'
    elif 'NOT_TESTED' in (a, b):
        classification = 'MISSING_OWNER_GUI_OBSERVATION'
        next_step = 'Collect missing independent GUI evidence before diagnosing the fault'
    elif a == 'REJECTED' and b == 'REJECTED':
        classification = 'DECODER_OR_PARTNER_COVERAGE_SUSPECTED'
        next_step = 'Review original Partner Group and BaseData decoder coverage; J2534 faults remain possible'
    elif a == 'ACCEPTED' and b == 'REJECTED':
        classification = 'J2534_OR_RESPONSEHANDLER_PATH_SUSPECTED'
        next_step = 'Compare original F114 response shape, ResponseHandler, AddVIN, and GUI session state'
    elif a == 'REJECTED' and b == 'ACCEPTED':
        classification = 'SESSION_OR_MANUAL_UI_PATH_DIFFERENCE'
        next_step = 'Repeat both scenarios with controlled session/cache and original Partner Group'
    else:
        classification = 'BOTH_GUI_OUTCOMES_OWNER_REPORTED_ACCEPTED'
        next_step = 'Validate independent runtime logs; then start a separate ECU identification acceptance gate'
    return {
        'schema_version': REPORT_SCHEMA,
        'vin_original': manual['vin_original'],
        'manual_observation': manual,
        'j2534_observation': adapter,
        'source_context_comparable': consistent,
        'classification': classification,
        'next_step': next_step,
        'offline_public_candidate_review': candidate,
        'evidence_provenance': 'owner-authored observations; attached file hashes verified locally only',
        'original_gui_log_interpretation_independently_verified': False,
        'j2534_transport_data_interpreted_independently': False,
        'original_vida_decoder_implementation_verified': False,
        'readvin_acceptance_independently_verified': False,
        'ecu_identification_verified': False,
        't111_t122_verified': False,
        'physical_j2534_verified': False,
        'limitations': [
            'Matching local evidence hashes confirms file integrity, not that its contents prove a GUI result',
            'Owner-reported GUI ACCEPTED must not be reclassified as independently verified ReadVin',
            'Manual and J2534 sessions can differ in cache and session state even with the same VIDA build',
            'No vehicle profile match or virtual ECU response is established from this correlation',
            'Offline public VIN candidate counts are not a substitute for original VIDA decoder behavior',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual', required=True, type=Path)
    parser.add_argument('--j2534', required=True, type=Path)
    parser.add_argument('--candidate-report', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        inputs = [args.manual, args.j2534]
        if args.candidate_report:
            inputs.append(args.candidate_report)
        if args.output.is_symlink() or any(args.output.resolve() == f.resolve() for f in inputs):
            raise EvidenceError('unsafe output destination')
        result = correlate(read_json(args.manual), read_json(args.j2534),
                           read_json(args.candidate_report) if args.candidate_report else None)
        data = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if len(data) > MAX_OUTPUT:
            raise EvidenceError('report exceeds size limit')
        with args.output.open('xb') as f:
            f.write(data)
        return 0
    except (EvidenceError, OSError, ValueError, UnicodeError, RecursionError, TypeError):
        print('VIDA manual/J2534 evidence comparison failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
