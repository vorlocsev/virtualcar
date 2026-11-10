#!/usr/bin/env python3
"""Bind independent, redacted Profile/InitHw and ReadVin static prerequisites.

No script-selection evidence, cross-database row join, VIN, original VIDA or
J2534 traffic is read or inferred by this research-only tool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from vida_evidence_summary import (EvidenceError, _catalog, _dice_timing,
                                   _profile_bridge, _readvin,
                                   read_report_with_digest)

SCHEMA = 'virtualcar-vida-profile-readvin-static-coverage-v1'
INPUTS = ('catalog', 'dicetiming', 'profile_init', 'readvin')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


def analyze(catalog, dicetiming, profile_init, readvin, source_digests):
    """Confirm only independent static prerequisites, never an actual handoff."""
    if (type(source_digests) is not dict or set(source_digests) != set(INPUTS)
            or any(type(digest) is not str or not DIGEST.fullmatch(digest)
                   for digest in source_digests.values())):
        raise EvidenceError('invalid static-coverage source digests')
    _catalog(catalog)
    _dice_timing(dicetiming)
    profile = _profile_bridge(profile_init, source_digests, catalog, dicetiming)
    _readvin(readvin)
    prerequisites = {
        'profile_init_columns': profile['profile_init_shape'] == 'candidate_shape',
        'profile_service_columns': profile['profile_service_shape'] == 'candidate_shape',
        'service_protocol_columns': profile['service_protocol_shape'] == 'candidate_shape',
        'readvin_declared_identity_graph': True,
    }
    missing = [key for key, present in prerequisites.items() if not present]
    return {
        'schema_version': SCHEMA,
        'status': 'independent_redacted_static_prerequisites_only',
        'source_report_sha256': {key: source_digests[key] for key in INPUTS},
        'static_prerequisites': prerequisites,
        'missing_static_prerequisites': missing,
        'static_coverage': 'present' if not missing else 'incomplete',
        'source_row_joins_verified': False,
        'same_vida_installation_verified': False,
        'profile_to_getscript_binding_verified': False,
        'getscript_to_readvin_selection_verified': False,
        'original_dice_timing_values_verified': False,
        'd2_baud_verified': False,
        'runtime_readvin_execution_verified': False,
        'client_vin_accepted': False,
        'physical_j2534_verified': False,
        'replay_approved': False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalog-report', required=True, type=Path)
    ap.add_argument('--dicetiming-report', required=True, type=Path)
    ap.add_argument('--profile-init-report', required=True, type=Path)
    ap.add_argument('--readvin-report', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        sources = {'catalog': args.catalog_report,
                   'dicetiming': args.dicetiming_report,
                   'profile_init': args.profile_init_report,
                   'readvin': args.readvin_report}
        checkout = Path(__file__).resolve().parents[2]
        output = args.output.resolve()
        resolved = [path.resolve() for path in sources.values()]
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or output == checkout or checkout in output.parents
                or output in resolved or len(set(resolved)) != len(resolved)):
            raise EvidenceError('unsafe static-coverage source or output')
        loaded = {key: read_report_with_digest(path) for key, path in sources.items()}
        report = analyze(*(loaded[key][0] for key in INPUTS),
                         {key: loaded[key][1] for key in INPUTS})
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write('\n')
        print('Independent static prerequisites checked; GetScript/ReadVin handoff not verified.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
