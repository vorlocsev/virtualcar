#!/usr/bin/env python3
"""Offline inspection of public spnda VIN-decode cross-product semantics.

Owner-private JSON only. This is NOT original VIDA, VIN acceptance, an
identity assertion, SQL access, a J2534 provider, or ECU simulation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

CANDIDATE_SCHEMA = 'virtualcar-vida-vin-model-variant-candidates-v1'
TABLE_SCHEMA = 'virtualcar-vida-original-table-capture-v1'
OUTPUT_SCHEMA = 'virtualcar-vida-public-vin-disambiguation-review-v1'
REQUIRED_CANDIDATE_KEYS = ('fkVehicleModel_original', 'fkModelYear_original',
                           'fkPartnerGroup_original', 'fkEngine_original',
                           'fkTransmission_original')
REQUIRED_PROFILE_KEYS = ('Id', 'fkVehicleModel', 'fkModelYear',
                         'fkEngine', 'fkTransmission')
MAX_BYTES = 50 * 1024 * 1024
MAX_INPUT_ROWS = 5000
MAX_CANDIDATES = 1000
MAX_COMBINATIONS = 20000
MAX_OUTPUT = 8 * 1024 * 1024


class OfflineEvidenceError(ValueError):
    """An error category; never include original VIN or row values."""


def _int(x):
    return type(x) is int


def _optional_int(x):
    return x is None or _int(x)


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise OfflineEvidenceError('duplicate JSON key')
        result[name] = value
    return result


def _nonfinite(_):
    raise OfflineEvidenceError('nonfinite JSON constant')


def read_json(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise OfflineEvidenceError('unsafe input file')
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise OfflineEvidenceError('oversized input file')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=_unique,
                          parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        raise OfflineEvidenceError('invalid JSON source') from None


def _candidates(report):
    if (type(report) is not dict or report.get('schema_version') != CANDIDATE_SCHEMA
            or report.get('source_database') != 'BaseData'
            or report.get('source_tables') != ['dbo.VINDecodeModel', 'dbo.VINDecodeVariant']
            or report.get('original_values_preserved') is not True
            or report.get('sql_snapshot_or_runtime_provenance_verified') is not False
            or report.get('actual_vida_decoder_algorithm_verified') is not False
            or report.get('vehicle_profile_engine_transmission_filter_applied') is not False
            or report.get('client_vin_acceptance_verified') is not False
            or report.get('ecu_identity_verified') is not False
            or type(report.get('vin_original')) is not str
            or not re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}', report['vin_original'])
            or not _int(report.get('partner_group_original'))
            or type(report.get('model_variant_candidate_pairs')) is not list
            or len(report['model_variant_candidate_pairs']) > MAX_CANDIDATES
            or not _int(report.get('model_variant_candidate_pair_count'))
            or report['model_variant_candidate_pair_count'] != len(report['model_variant_candidate_pairs'])
            or report.get('model_capture_scope') not in ('full_within_limit', 'filtered_subset_only')
            or report.get('variant_capture_scope') not in ('full_within_limit', 'filtered_subset_only')):
        raise OfflineEvidenceError('invalid B3A300 candidate report')
    incomplete = (report['model_capture_scope'] != 'full_within_limit' or
                  report['variant_capture_scope'] != 'full_within_limit')
    if report.get('partial_capture_cannot_exclude_missing_rows') is not incomplete:
        raise OfflineEvidenceError('inconsistent source subset scope')
    result = []
    for row in report['model_variant_candidate_pairs']:
        if (type(row) is not dict or not set(REQUIRED_CANDIDATE_KEYS).issubset(row)
                or not all(_int(row[k]) for k in REQUIRED_CANDIDATE_KEYS[:3])
                or not all(_optional_int(row[k]) for k in REQUIRED_CANDIDATE_KEYS[3:])
                or row['fkPartnerGroup_original'] != report['partner_group_original']):
            raise OfflineEvidenceError('invalid model-variant candidate')
        result.append(tuple(row[k] for k in REQUIRED_CANDIDATE_KEYS))
    return result, incomplete


def _profiles(source):
    if (type(source) is not dict or source.get('schema_version') != TABLE_SCHEMA
            or source.get('source_database') != 'BaseData'
            or source.get('source_schema') != 'dbo'
            or source.get('source_table') != 'VehicleProfile'
            or source.get('original_names_and_driver_values_not_anonymized') is not True
            or source.get('same_installation_provenance_verified') is not False
            or source.get('vehicle_runtime_verified') is not False
            or type(source.get('columns')) is not list
            or type(source.get('rows')) is not list
            or len(source['rows']) > MAX_INPUT_ROWS
            or not _int(source.get('row_count')) or source['row_count'] != len(source['rows'])):
        raise OfflineEvidenceError('invalid original VehicleProfile capture')
    columns = [entry.get('name') if type(entry) is dict else None for entry in source['columns']]
    if (any(type(name) is not str for name in columns)
            or len(columns) != len(set(columns))
            or not set(REQUIRED_PROFILE_KEYS).issubset(columns)):
        raise OfflineEvidenceError('unsupported original profile columns')
    full = source.get('full_table_extracted_within_row_limit')
    partial = source.get('selection_scope') == 'filtered_subset_only'
    if (type(full) is not bool or (full and partial)
            or (not full and not (partial
                and source.get('filtered_subset_complete_within_row_limit') is True
                and source.get('full_table_row_count_verified') is False))):
        raise OfflineEvidenceError('unknown profile capture scope')
    rows = []
    ids = set()
    for values in source['rows']:
        if type(values) is not list or len(values) != len(columns):
            raise OfflineEvidenceError('invalid profile row width')
        row = dict(zip(columns, values))
        if (not _int(row['Id']) or row['Id'] <= 0 or row['Id'] in ids
                or not all(_optional_int(row[k]) for k in REQUIRED_PROFILE_KEYS[1:])):
            raise OfflineEvidenceError('invalid source profile key')
        ids.add(row['Id'])
        rows.append(row)
    return rows, 'full_within_limit' if full else 'filtered_subset_only'


def analyze(candidate_report, profile_capture):
    candidates, candidate_incomplete = _candidates(candidate_report)
    profiles, profile_scope = _profiles(profile_capture)
    # Public spnda/vin_decoder.py: c1 for engine, c2 for transmission;
    # no c1↔c2 model/year/group predicate in its CROSS JOIN.
    engines = [c for c in candidates if c[3] is not None]
    transmissions = [c for c in candidates if c[4] is not None]
    source_pair_count = len(engines) * len(transmissions) if transmissions else len(engines) * len(candidates)
    if source_pair_count > 250000:
        raise OfflineEvidenceError('unbounded source pair product')
    generated = {}
    cross_key_pairs = 0
    if transmissions:
        for engine in engines:
            for transmission in transmissions:
                if engine[:3] != transmission[:3]:
                    cross_key_pairs += 1
                key = engine[:4] + (transmission[4],)
                generated.setdefault(key, set()).add(engine[:3] == transmission[:3])
                if len(generated) > MAX_COMBINATIONS:
                    raise OfflineEvidenceError('too many generated distinct candidates')
    else:
        # The public query can select c2 transmissions NULL only if *no*
        # component in the entire table has a non-NULL transmission.
        for engine in engines:
            for _ in candidates:
                key = engine[:4] + (None,)
                generated.setdefault(key, set()).add(True)
                if len(generated) > MAX_COMBINATIONS:
                    raise OfflineEvidenceError('too many generated distinct candidates')
    needs_filter = len(generated) > 1
    outcomes = []
    for key in sorted(generated, key=lambda t: tuple(-1 if x is None else x for x in t)):
        model, year, group, engine, transmission = key
        matching = []
        if needs_filter:
            for profile in profiles:
                if (profile['fkVehicleModel'] == model and
                        profile['fkModelYear'] == year and
                        (transmission is None or
                         (profile['fkEngine'] == engine and
                          profile['fkTransmission'] == transmission))):
                    matching.append(profile['Id'])
        survives = not needs_filter or bool(matching)
        outcomes.append({
            'fkVehicleModel_original': model,
            'fkModelYear_original': year,
            'fkPartnerGroup_original': group,
            'fkEngine_original': engine,
            'fkTransmission_original': transmission,
            'source_key_consistent_origin_observed': True in generated[key],
            'only_cross_key_origin_observed': True not in generated[key],
            'public_extra_filter_applied': needs_filter,
            'profile_match_ids_original': matching,
            'survives_public_approximation': survives,
        })
    survived = [r for r in outcomes if r['survives_public_approximation']]
    model_ids = {r['fkVehicleModel_original'] for r in survived}
    if not survived:
        public_branch = 'no_remaining_candidate_in_available_inputs'
    elif len(model_ids) > 1:
        public_branch = 'multiple_vehicle_models_in_remaining_candidates'
    else:
        public_branch = 'single_vehicle_model_in_remaining_candidates'
    return {
        'schema_version': OUTPUT_SCHEMA,
        'vin_original': candidate_report['vin_original'],
        'partner_group_original': candidate_report['partner_group_original'],
        'raw_model_variant_pair_count': len(candidates),
        'source_cross_join_pair_count': source_pair_count,
        'source_cross_key_pair_count': cross_key_pairs,
        'distinct_cross_join_candidate_count': len(outcomes),
        'public_profile_filter_triggered': needs_filter,
        'public_filtered_candidate_count': len(survived),
        'public_branch_in_available_inputs': public_branch,
        'candidate_combinations_original': outcomes,
        'model_variant_capture_incomplete': candidate_incomplete,
        'vehicle_profile_capture_scope': profile_scope,
        'source_same_snapshot_verified': False,
        'body_style_discarded_upstream': True,
        'public_decoder_equivalence_verified': False,
        'original_vida_decoder_runtime_verified': False,
        'readvin_gui_acceptance_verified': False,
        'ecu_identification_verified': False,
        'limitations': [
            'Independent simulation of the published spnda cross-product and second profile filter, not Volvo VIDA code',
            'Upstream B3A300 has already projected out original fkBodyStyle and duplicate source rows',
            'Public cross join has no c1-c2 model/year/Partner Group equality and may mix unrelated sources',
            'Public zero-transmission branch is global across candidates, not grouped by model',
            'Public profile filter runs only if distinct cross-product candidates exceed one',
            'Public profile filter matches exact engine/transmission, not generic NULL wildcards; NULL transmission is special',
            'Original SQL collation, FK meaning, runtime caches and profile inheritance not attested',
            'No source capture proves original VIN, Partner Group, GUI decoding or physical ECU presence',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', required=True, type=Path)
    parser.add_argument('--profiles', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.is_symlink() or any(
                args.output.resolve() == source.resolve()
                for source in (args.candidates, args.profiles)):
            raise OfflineEvidenceError('unsafe output destination')
        result = analyze(read_json(args.candidates), read_json(args.profiles))
        data = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if len(data) > MAX_OUTPUT:
            raise OfflineEvidenceError('report size limit')
        with args.output.open('xb') as output:
            output.write(data)
        return 0
    except (OfflineEvidenceError, OSError, ValueError, UnicodeError, RecursionError):
        print('VIDA public decoder comparison failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
