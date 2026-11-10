#!/usr/bin/env python3
"""Cross-check public CarCom profile/init column hints against redacted DiceTiming metadata.

Never assert a row join, selected profile, real timing, baud, or VIDA execution.
Only fixed, previously researched table/column hints may appear in output.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

from audit_vida_carcom_schema_links import CANDIDATE_EDGES, HARDWARE_CANDIDATE_EDGES, TABLES
from vida_evidence_summary import EvidenceError, _catalog, _dice_timing, read_report_with_digest

SCHEMA = 'virtualcar-vida-profile-init-metadata-bridge-v1'
_DIGEST = re.compile(r'[0-9a-f]{64}\Z')
REQUIRED_EDGES = {
    'profile_init': tuple(HARDWARE_CANDIDATE_EDGES[:4]),
    'service_protocol': (CANDIDATE_EDGES[0], *HARDWARE_CANDIDATE_EDGES[4:]),
}
REQUIRED_FIELDS = {
    'profile_init': (('T161_Profile', 'folderLevel'),
                     ('T131_InitValue', 'initValue'),
                     ('T132_InitValueType', 'name')),
    'service_protocol': (('T121_Config', 'busRate'),
                         ('T121_Config', 'addressSize')),
}


def _table_shape(carcom, name):
    entry = carcom.get(name)
    expected = set(TABLES['CarCom'][name])
    if type(entry) is not dict or type(entry.get('present')) is not bool:
        raise EvidenceError('invalid public CarCom table hint')
    present = entry['present']
    supplied = entry.get('known_columns_present')
    missing = entry.get('known_columns_missing')
    size = entry.get('column_count')
    if (type(supplied) is not list or type(missing) is not list or
            type(size) is not int or size < 0 or size > 30000):
        raise EvidenceError('invalid CarCom column hints')
    if (any(type(v) is not str for v in supplied + missing) or
            len(set(supplied)) != len(supplied) or len(set(missing)) != len(missing)
            or set(supplied) & set(missing) or set(supplied) | set(missing) != expected
            or size < len(supplied) or (not present and (supplied or size))
            or (present and size == 0)):
        raise EvidenceError('contradictory public CarCom column hints')
    return present, set(supplied)


def bridge(catalog, dice_timing, source_digests=None):
    # Reuse exact current redacted-source preflight, including forbidden positive flags.
    _catalog(catalog)
    _dice_timing(dice_timing)
    if source_digests is not None and (
            type(source_digests) is not dict or set(source_digests) != {'catalog', 'dicetiming'}
            or any(type(v) is not str or not _DIGEST.fullmatch(v)
                   for v in source_digests.values())):
        raise EvidenceError('invalid source report byte digests')
    carcom = catalog['databases']['CarCom']['known_tables']
    if type(carcom) is not dict or not set(TABLES['CarCom']).issubset(carcom):
        raise EvidenceError('incomplete public CarCom research hints')
    shapes = {name: _table_shape(carcom, name) for name in TABLES['CarCom']}
    observed_edges = {}
    if type(catalog['edges']) is not list:
        raise EvidenceError('invalid CarCom edge list')
    for edge in catalog['edges']:
        if type(edge) is not dict:
            raise EvidenceError('invalid CarCom edge')
        if edge.get('evidence') not in ('hardware_shape', 'service_shape'):
            # Other declared SQL FK rows are separate, not required candidate hints.
            continue
        parts = (edge.get('database'), edge.get('source'), edge.get('source_column'),
                 edge.get('target'), edge.get('target_column'))
        category = edge['evidence']
        key = category, parts
        if key in observed_edges:
            raise EvidenceError('duplicate CarCom candidate evidence')
        if (edge.get('referential_rows_verified') is not False or
                type(edge.get('column_shape_present')) is not bool):
            raise EvidenceError('forged CarCom candidate edge evidence')
        observed_edges[key] = edge['column_shape_present']
    states = {}
    missing_count = {}
    for path_id, edges in REQUIRED_EDGES.items():
        misses = 0
        for hint in edges:
            category = 'service_shape' if hint in CANDIDATE_EDGES else 'hardware_shape'
            key = category, hint
            if key not in observed_edges:
                raise EvidenceError('missing CarCom candidate evidence')
            _, src, src_col, dst, dst_col = hint
            expected = (shapes[src][0] and shapes[dst][0] and
                        src_col in shapes[src][1] and dst_col in shapes[dst][1])
            if observed_edges[key] is not expected:
                raise EvidenceError('contradictory CarCom candidate edge shape')
            misses += int(not expected)
        for table, col in REQUIRED_FIELDS[path_id]:
            misses += int(not (shapes[table][0] and col in shapes[table][1]))
        states[path_id] = 'candidate_shape' if misses == 0 else 'incomplete_shape'
        missing_count[path_id] = misses
    return {
        'source_report_sha256': source_digests,
        'schema_version': SCHEMA,
        'status': 'static_metadata_hypotheses_only',
        'profile_init_shape': states['profile_init'],
        'service_protocol_shape': states['service_protocol'],
        'missing_public_hints': missing_count,
        'dicetiming_metadata_checked': True,
        'dicetiming_to_carcom_join_verified': False,
        'selected_ecu_profile_verified': False,
        'inherited_init_hw_values_verified': False,
        'd2_baud_verified': False,
        'getscript_readvin_runtime_verified': False,
        'client_vin_accepted': False,
        'physical_j2534_verified': False,
        'replay_approved': False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalog-report', required=True, type=Path)
    ap.add_argument('--dicetiming-report', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        inputs = (args.catalog_report, args.dicetiming_report)
        output = args.output.resolve()
        checkout = Path(__file__).resolve().parents[2]
        resolved = [p.resolve() for p in inputs]
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink() or
                output == checkout or checkout in output.parents or
                output in resolved or resolved[0] == resolved[1]):
            raise EvidenceError('unsafe profile bridge output')
        cat, cat_hash = read_report_with_digest(inputs[0])
        timing, timing_hash = read_report_with_digest(inputs[1])
        report = bridge(cat, timing,
                        {'catalog': cat_hash, 'dicetiming': timing_hash})
        with args.output.open('x', encoding='utf-8') as f:
            json.dump(report, f, sort_keys=True, indent=2)
            f.write('\n')
        print('Profile/InitHw metadata shape checked; DiceTiming join and runtime unverified.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
