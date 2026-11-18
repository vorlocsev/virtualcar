#!/usr/bin/env python3
"""Owner-local offline candidate match from original BaseData VIN tables.

This is an independent, bounded approximation of the public spnda VIN decoder
predicate, NOT VIDA's proprietary runtime decoder or acceptance proof.
No SQL, VIDA, J2534, network, pickle or vehicle operations.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys

SCHEMA = 'virtualcar-vida-original-table-capture-v1'
RESULT = 'virtualcar-vida-vin-model-variant-candidates-v1'
BASE = 'BaseData'
REQUIRED = {
    'VINDecodeModel': ('VinStartPos', 'VinEndPos', 'VinCompare', 'fkVehicleModel',
                       'fkModelYear', 'fkPartnerGroup', 'ChassisNoFrom',
                       'ChassisNoTo', 'YearCodePos', 'YearCode'),
    'VINDecodeVariant': ('VinStartPos', 'VinEndPos', 'VinCompare', 'fkVehicleModel',
                         'fkModelYear', 'fkPartnerGroup', 'fkEngine', 'fkTransmission'),
}
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_ROWS = 5000
MAX_PAIRS = 20000


class EvidenceError(ValueError):
    pass


def _unique(pairs):
    obj = {}
    for name, value in pairs:
        if name in obj:
            raise EvidenceError('duplicate JSON key')
        obj[name] = value
    return obj


def _read(path: Path, limit: int):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise EvidenceError('unsafe input')
    try:
        return json.loads(path.read_bytes().decode('utf-8'), object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(EvidenceError('nonfinite JSON')))
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceError('invalid input JSON') from None


def _table(obj, name):
    if (type(obj) is not dict or obj.get('schema_version') != SCHEMA
            or obj.get('source_database') != BASE or obj.get('source_schema') != 'dbo'
            or obj.get('source_table') != name
            or obj.get('original_names_and_driver_values_not_anonymized') is not True
            or obj.get('vehicle_runtime_verified') is not False
            or obj.get('same_installation_provenance_verified') is not False
            or type(obj.get('columns')) is not list or type(obj.get('rows')) is not list
            or len(obj['rows']) > MAX_ROWS
            or type(obj.get('row_count')) is not int or obj['row_count'] != len(obj['rows'])):
        raise EvidenceError('untrusted original table capture')
    cols = [c.get('name') if type(c) is dict else None for c in obj['columns']]
    if any(type(c) is not str for c in cols) or len(cols) != len(set(cols)):
        raise EvidenceError('invalid original columns')
    if not set(REQUIRED[name]).issubset(cols):
        raise EvidenceError('original table lacks required columns')
    full = obj.get('full_table_extracted_within_row_limit')
    partial = obj.get('selection_scope') == 'filtered_subset_only'
    if type(full) is not bool or (full and partial) or (not full and not (
            partial and obj.get('filtered_subset_complete_within_row_limit') is True
            and obj.get('full_table_row_count_verified') is False)):
        raise EvidenceError('unknown table capture scope')
    rows = []
    for v in obj['rows']:
        if type(v) is not list or len(v) != len(cols):
            raise EvidenceError('invalid row width')
        row = dict(zip(cols, v))
        rows.append(row)
    return rows, 'full_within_limit' if full else 'filtered_subset_only'


def _int(x):
    return type(x) is int


def _slice_matches(vin, row):
    lo, hi, expected = row['VinStartPos'], row['VinEndPos'], row['VinCompare']
    if not (_int(lo) and _int(hi) and 1 <= lo <= hi <= 17
            and type(expected) is str and len(expected) == hi - lo + 1):
        raise EvidenceError('unsupported VIN comparison shape')
    # SQL SUBSTRING positions in the public implementation are 1-based.
    return vin[lo - 1:hi] == expected


def _key(row):
    key = tuple(row[f] for f in ('fkVehicleModel', 'fkModelYear', 'fkPartnerGroup'))
    if not all(_int(x) for x in key):
        raise EvidenceError('unsupported original model/year/partner types')
    return key


def analyze(vin, partner_group, model_capture, variant_capture):
    if (type(vin) is not str or re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}', vin) is None
            or not vin[-6:].isdigit() or not _int(partner_group)):
        raise EvidenceError('invalid VIN or Partner Group source')
    models, model_scope = _table(model_capture, 'VINDecodeModel')
    variants, variant_scope = _table(variant_capture, 'VINDecodeVariant')
    chassis = int(vin[-6:])
    eligible_models = []
    stats = {'model_rows': len(models), 'model_vin_substring': 0,
             'model_chassis_range': 0, 'model_year_code': 0,
             'model_partner_group': 0, 'variant_rows': len(variants),
             'variant_vin_substring': 0, 'variant_partner_group': 0}
    for m in models:
        if not _slice_matches(vin, m):
            continue
        stats['model_vin_substring'] += 1
        lo, hi = m['ChassisNoFrom'], m['ChassisNoTo']
        if not (_int(lo) and _int(hi) and 0 <= lo <= hi <= 999999):
            raise EvidenceError('unsupported chassis range')
        if not lo <= chassis <= hi:
            continue
        stats['model_chassis_range'] += 1
        year, position = m['YearCode'], m['YearCodePos']
        if year is not None and (type(year) is not str or len(year) != 1
                                 or not _int(position) or not 1 <= position <= 17):
            raise EvidenceError('unsupported year-code metadata')
        if year is not None and vin[position - 1] != year:
            continue
        stats['model_year_code'] += 1
        k = _key(m)
        if k[2] != partner_group:
            continue
        stats['model_partner_group'] += 1
        eligible_models.append(k)
    candidates = defaultdict(list)
    model_set = set(eligible_models)
    for v in variants:
        if not _slice_matches(vin, v):
            continue
        stats['variant_vin_substring'] += 1
        k = _key(v)
        if k[2] != partner_group:
            continue
        stats['variant_partner_group'] += 1
        if k in model_set:
            engine, transmission = v['fkEngine'], v['fkTransmission']
            if not (engine is None or _int(engine)) or not (transmission is None or _int(transmission)):
                raise EvidenceError('unsupported engine or transmission type')
            candidates[k].append((engine, transmission))
    joined = []
    for k, combos in sorted(candidates.items()):
        for engine, transmission in combos:
            joined.append({'fkVehicleModel_original': k[0], 'fkModelYear_original': k[1],
                           'fkPartnerGroup_original': k[2], 'fkEngine_original': engine,
                           'fkTransmission_original': transmission})
            if len(joined) > MAX_PAIRS:
                raise EvidenceError('too many candidate pairs')
    return {'schema_version': RESULT, 'vin_original': vin,
            'partner_group_original': partner_group, 'source_database': BASE,
            'source_tables': ['dbo.VINDecodeModel', 'dbo.VINDecodeVariant'],
            'model_capture_scope': model_scope, 'variant_capture_scope': variant_scope,
            'filter_stage_counts_in_given_captures': stats,
            'model_variant_candidate_pair_count': len(joined),
            'model_variant_candidate_pairs': joined,
            'partial_capture_cannot_exclude_missing_rows': model_scope != 'full_within_limit' or variant_scope != 'full_within_limit',
            'predicate_origin': 'independent approximation of spnda/volvo_vida_db scripts/vin_decoder.py',
            'original_values_preserved': True,
            'sql_snapshot_or_runtime_provenance_verified': False,
            'vehicle_profile_engine_transmission_filter_applied': False,
            'actual_vida_decoder_algorithm_verified': False,
            'original_responsehandler_addvin_verified': False,
            'client_vin_acceptance_verified': False,
            'ecu_identity_verified': False,
            'limitations': ['SQL Server collation and type coercion may differ from Python exact comparisons',
                            'Missing optional VehicleProfile and VINDecodeVariantCodes behavior is not modeled',
                            'Candidate pair does not prove successful VIDA GUI decoding, ECU presence, or vehicle identity']}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vin-file', required=True, type=Path)
    p.add_argument('--partner-group', required=True, type=int)
    p.add_argument('--model-rows', required=True, type=Path)
    p.add_argument('--variant-rows', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args(argv)
    try:
        sources = (args.vin_file, args.model_rows, args.variant_rows)
        if args.output.is_symlink() or any(x.resolve() == args.output.resolve() for x in sources):
            raise EvidenceError('unsafe output')
        if args.vin_file.is_symlink() or args.vin_file.stat().st_size > 64:
            raise EvidenceError('unsafe VIN input')
        vin = args.vin_file.read_bytes().decode('ascii').strip()
        r = analyze(vin, args.partner_group, _read(args.model_rows, MAX_SOURCE_BYTES),
                    _read(args.variant_rows, MAX_SOURCE_BYTES))
        with args.output.open('x', encoding='utf-8') as out:
            json.dump(r, out, ensure_ascii=False, indent=2)
            out.write('\n')
    except (OSError, ValueError, UnicodeError, RecursionError):
        print('VIDA offline model/variant candidate audit failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
