#!/usr/bin/env python3
"""Owner-local candidate-to-VehicleProfile cross-check for original VIDA exports.

Consumes B3A300's offline *candidate* report and PR #317's original
BaseData.dbo.VehicleProfile table capture. Does not query SQL, execute VIDA,
operate J2534, infer missing inheritance, or attest VIN/ECU acceptance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

CANDIDATE_SCHEMA = 'virtualcar-vida-vin-model-variant-candidates-v1'
CAPTURE_SCHEMA = 'virtualcar-vida-original-table-capture-v1'
OUTPUT_SCHEMA = 'virtualcar-vida-vin-vehicle-profile-candidates-v1'
SOURCE_DATABASE = 'BaseData'
SOURCE_TABLE = 'VehicleProfile'
CAPTURE_COLUMNS = ('Id', 'FolderLevel', 'fkVehicleModel', 'fkModelYear',
                   'fkPartnerGroup', 'fkEngine', 'fkTransmission', 'fkBodyStyle',
                   'fkSteering', 'fkNodeECU', 'fkSpecialVehicle')
CANDIDATE_COLUMNS = ('fkVehicleModel_original', 'fkModelYear_original',
                     'fkPartnerGroup_original', 'fkEngine_original',
                     'fkTransmission_original')
MAX_CANDIDATES = 1000
MAX_ROWS = 5000
MAX_MATCHES = 20000
MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


class ProfileEvidenceError(ValueError):
    """Fail closed on ambiguous input; no original identifiers in error messages."""


def _pairs_unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ProfileEvidenceError('duplicate JSON key')
        obj[key] = value
    return obj


def _nonfinite(_):
    raise ProfileEvidenceError('nonfinite JSON value')


def read_json(path: Path):
    if (path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES):
        raise ProfileEvidenceError('unsafe input path')
    data = path.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        raise ProfileEvidenceError('oversized input')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=_pairs_unique,
                          parse_constant=_nonfinite)
    except (ValueError, UnicodeError, RecursionError):
        raise ProfileEvidenceError('invalid JSON input') from None


def _int(value):
    return type(value) is int


def _optional_int(value):
    return value is None or _int(value)


def _scope(obj):
    full = obj.get('full_table_extracted_within_row_limit')
    subset = obj.get('selection_scope') == 'filtered_subset_only'
    if type(full) is not bool or (full and subset):
        raise ProfileEvidenceError('unsupported capture scope')
    if not full and not (subset and
                         obj.get('filtered_subset_complete_within_row_limit') is True and
                         obj.get('full_table_row_count_verified') is False):
        raise ProfileEvidenceError('incomplete capture')
    return 'full_within_capture_limit' if full else 'filtered_subset_only'


def _validate_candidates(report):
    if (type(report) is not dict or report.get('schema_version') != CANDIDATE_SCHEMA
            or report.get('source_database') != SOURCE_DATABASE
            or report.get('source_tables') != ['dbo.VINDecodeModel', 'dbo.VINDecodeVariant']
            or report.get('original_values_preserved') is not True
            or report.get('sql_snapshot_or_runtime_provenance_verified') is not False
            or report.get('actual_vida_decoder_algorithm_verified') is not False
            or report.get('client_vin_acceptance_verified') is not False
            or report.get('ecu_identity_verified') is not False
            or report.get('vehicle_profile_engine_transmission_filter_applied') is not False
            or type(report.get('vin_original')) is not str
            or not re.fullmatch('[A-HJ-NPR-Z0-9]{17}', report['vin_original'])
            or not _int(report.get('partner_group_original'))
            or type(report.get('model_variant_candidate_pairs')) is not list
            or len(report['model_variant_candidate_pairs']) > MAX_CANDIDATES
            or not _int(report.get('model_variant_candidate_pair_count'))
            or report['model_variant_candidate_pair_count'] != len(report['model_variant_candidate_pairs'])
            or report.get('model_capture_scope') not in ('full_within_limit', 'filtered_subset_only')
            or report.get('variant_capture_scope') not in ('full_within_limit', 'filtered_subset_only')):
        raise ProfileEvidenceError('untrusted B3A300 candidate report')
    incomplete = (report['model_capture_scope'] != 'full_within_limit' or
                  report['variant_capture_scope'] != 'full_within_limit')
    if report.get('partial_capture_cannot_exclude_missing_rows') is not incomplete:
        raise ProfileEvidenceError('contradictory candidate capture scope')
    candidates = report['model_variant_candidate_pairs']
    for item in candidates:
        if (type(item) is not dict or not set(CANDIDATE_COLUMNS).issubset(item)
                or not all(_int(item[name]) for name in CANDIDATE_COLUMNS[:3])
                or not all(_optional_int(item[name]) for name in CANDIDATE_COLUMNS[3:])
                or item['fkPartnerGroup_original'] != report['partner_group_original']):
            raise ProfileEvidenceError('invalid model/variant candidate')
    return candidates, incomplete


def _validate_profiles(capture):
    if (type(capture) is not dict or capture.get('schema_version') != CAPTURE_SCHEMA
            or capture.get('source_database') != SOURCE_DATABASE
            or capture.get('source_schema') != 'dbo'
            or capture.get('source_table') != SOURCE_TABLE
            or capture.get('original_names_and_driver_values_not_anonymized') is not True
            or capture.get('same_installation_provenance_verified') is not False
            or capture.get('vehicle_runtime_verified') is not False
            or type(capture.get('columns')) is not list
            or type(capture.get('rows')) is not list
            or len(capture['rows']) > MAX_ROWS
            or not _int(capture.get('row_count'))
            or capture['row_count'] != len(capture['rows'])):
        raise ProfileEvidenceError('untrusted original VehicleProfile capture')
    columns = [c.get('name') if type(c) is dict else None for c in capture['columns']]
    if (any(type(name) is not str for name in columns)
            or len(columns) != len(set(columns))
            or not set(CAPTURE_COLUMNS).issubset(columns)):
        raise ProfileEvidenceError('unsupported original VehicleProfile columns')
    scope = _scope(capture)
    rows = []
    ids = set()
    for raw in capture['rows']:
        if type(raw) is not list or len(raw) != len(columns):
            raise ProfileEvidenceError('invalid original VehicleProfile row')
        row = dict(zip(columns, raw))
        ident, level = row['Id'], row['FolderLevel']
        if not _int(ident) or ident <= 0 or ident in ids or not _int(level) or level < 0:
            raise ProfileEvidenceError('invalid VehicleProfile key or folder level')
        if not _int(row['fkVehicleModel']) or not all(
                _optional_int(row[name]) for name in CAPTURE_COLUMNS[3:]):
            raise ProfileEvidenceError('unsupported original profile values')
        ids.add(ident)
        rows.append(row)
    return rows, scope


def analyze(candidate_report, profile_capture, *, body_style=None):
    if body_style is not None and not _int(body_style):
        raise ProfileEvidenceError('invalid original body style')
    candidates, candidate_incomplete = _validate_candidates(candidate_report)
    profiles, scope = _validate_profiles(profile_capture)
    compatible = []
    requires_context = []
    explicit_pair_matches = 0
    excluded_advanced = 0
    for i, candidate in enumerate(candidates):
        for profile in profiles:
            if profile['fkVehicleModel'] != candidate['fkVehicleModel_original']:
                continue
            if any(profile[key] is not None for key in ('fkSteering', 'fkNodeECU', 'fkSpecialVehicle')):
                excluded_advanced += 1
                continue
            unknown = []
            mismatch = False
            for field, observed in (
                    ('fkModelYear', candidate['fkModelYear_original']),
                    ('fkPartnerGroup', candidate['fkPartnerGroup_original']),
                    ('fkEngine', candidate['fkEngine_original']),
                    ('fkTransmission', candidate['fkTransmission_original']),
                    ('fkBodyStyle', body_style)):
                value = profile[field]
                if value is None:
                    continue  # Source-public helper interprets NULL as wildcard.
                if observed is None:
                    unknown.append(field)
                elif value != observed:
                    mismatch = True
                    break
            if mismatch:
                continue
            exact_engine_trans = (
                profile['fkEngine'] is not None and
                profile['fkTransmission'] is not None and
                candidate['fkEngine_original'] is not None and
                candidate['fkTransmission_original'] is not None)
            if exact_engine_trans:
                explicit_pair_matches += 1
            entry = {
                'candidate_index': i,
                'original_profile_id': profile['Id'],
                'original_folder_level': profile['FolderLevel'],
                'original_profile_engine': profile['fkEngine'],
                'original_profile_transmission': profile['fkTransmission'],
                'original_profile_body_style': profile['fkBodyStyle'],
                'explicit_engine_transmission_match': exact_engine_trans,
                'unresolved_fields': unknown,
                'classification': 'candidate_compatible' if not unknown else 'requires_more_context',
            }
            (requires_context if unknown else compatible).append(entry)
            if len(compatible) + len(requires_context) > MAX_MATCHES:
                raise ProfileEvidenceError('too many candidate matches')
    compatible.sort(key=lambda x: (x['candidate_index'], x['original_folder_level'], x['original_profile_id']))
    requires_context.sort(key=lambda x: (x['candidate_index'], x['original_folder_level'], x['original_profile_id']))
    return {
        'schema_version': OUTPUT_SCHEMA,
        'vin_original': candidate_report['vin_original'],
        'partner_group_original': candidate_report['partner_group_original'],
        'source_candidate_count': len(candidates),
        'source_model_variant_scope_incomplete': candidate_incomplete,
        'source_vehicle_profile_scope': scope,
        'source_vehicle_profile_row_count': len(profiles),
        'profile_capture_incomplete': scope == 'filtered_subset_only',
        'candidate_compatible_profile_count': len(compatible),
        'candidate_requires_context_profile_count': len(requires_context),
        'explicit_engine_transmission_pair_matches': explicit_pair_matches,
        'advanced_dimension_rows_excluded': excluded_advanced,
        'candidate_compatible_profile_links': compatible,
        'candidate_requires_context_profile_links': requires_context,
        'body_style_supplied_from_owner_context': body_style is not None,
        'original_body_style_value': body_style,
        'original_values_preserved_owner_local': True,
        'cross_export_transactional_consistency_verified': False,
        'full_original_vida_profile_inheritance_verified': False,
        'original_vida_decoder_runtime_verified': False,
        'client_readvin_accepted': False,
        'ecu_identification_verified': False,
        'limitations': [
            'Candidate-compatible profile means only that the audited subset agrees with nullable filters',
            'Body style unknown leaves matching specialized profiles in requires_more_context',
            'Rows with steering, node-ECU or special-vehicle constraints are excluded by the reviewed public helper',
            'The reviewed public decoder has a separate multi-candidate disambiguation path not reproduced here',
            'A filtered table capture cannot establish absence of applicable profiles',
            'Original profiles may be inherited or combined by rules not reproduced here',
            'IDs are original SQL foreign keys: VehicleModel.Cid 275 must not substitute for VehicleModel.Id',
            'J2534 RX, VIDA GUI VIN acceptance, ECU presence and T111/T122 are not attested',
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidates', required=True, type=Path)
    ap.add_argument('--profiles', required=True, type=Path)
    ap.add_argument('--body-style-id', type=int, default=None)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        if args.output.is_symlink() or any(
                p.resolve() == args.output.resolve() for p in (args.candidates, args.profiles)):
            raise ProfileEvidenceError('unsafe output path')
        result = analyze(read_json(args.candidates), read_json(args.profiles),
                         body_style=args.body_style_id)
        data = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if len(data) > MAX_OUTPUT_BYTES:
            raise ProfileEvidenceError('oversized report')
        with args.output.open('xb') as file:
            file.write(data)
        return 0
    except (ProfileEvidenceError, OSError, ValueError, UnicodeError, RecursionError):
        print('VIDA VehicleProfile offline evidence check failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
