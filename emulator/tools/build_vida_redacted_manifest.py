#!/usr/bin/env python3
"""Create a byte-binding manifest from owner-reviewed, already-redacted VIDA JSON.

Does not open proprietary VIDA databases, execute diagnostics, copy source reports,
attest their origin, or grant runtime acceptance. Manifest is NOT a signature.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from vida_evidence_summary import (BUNDLE_SCHEMA, EvidenceError, assemble,
                                   read_report_with_digest, verify_bundle_manifest)

INPUTS = {
    'catalog': 'catalog_report',
    'comparison': 'compare_report',
    'readvin': 'readvin_report',
    'dicetiming': 'dicetiming_report',
    'dicetiming_compare': 'dicetiming_compare_report',
}


def prepare_manifest(paths):
    """Reuse summary's schema and negative-claim checks before binding bytes."""
    if not paths or set(paths) - set(INPUTS) or any(not isinstance(p, Path) for p in paths.values()):
        raise EvidenceError('invalid report selection')
    loaded = {kind: read_report_with_digest(path) for kind, path in paths.items()}
    assemble(catalog=loaded['catalog'][0] if 'catalog' in loaded else None,
             comparison=loaded['comparison'][0] if 'comparison' in loaded else None,
             readvin=loaded['readvin'][0] if 'readvin' in loaded else None,
             dice_timing=loaded['dicetiming'][0] if 'dicetiming' in loaded else None,
             dice_timing_comparison=(loaded['dicetiming_compare'][0]
                                     if 'dicetiming_compare' in loaded else None))
    manifest = {
        'schema_version': BUNDLE_SCHEMA,
        'scope': 'redacted_report_bytes_only',
        'reports': {kind: pair[1] for kind, pair in sorted(loaded.items())},
        'same_installation_provenance_verified': False,
        'runtime_evidence_verified': False,
    }
    verify_bundle_manifest(manifest, {kind: pair[1] for kind, pair in loaded.items()})
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in INPUTS.values():
        parser.add_argument('--' + name.replace('_', '-'), type=Path)
    parser.add_argument('--output', required=True, type=Path,
                        help='New owner-local manifest path outside the Git checkout')
    args = parser.parse_args(argv)
    try:
        paths = {kind: getattr(args, option) for kind, option in INPUTS.items()
                 if getattr(args, option) is not None}
        checkout = Path(__file__).resolve().parents[2]
        target = args.output.resolve()
        resolved = [p.resolve() for p in paths.values()]
        if (not paths or not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or target == checkout or checkout in target.parents
                or target in resolved or len(resolved) != len(set(resolved))
                or any(path == checkout or checkout in path.parents for path in resolved)):
            raise EvidenceError('unsafe manifest location or input aliases')
        manifest = prepare_manifest(paths)
        # Avoid default world-readable permissions on POSIX systems. O_EXCL
        # also prevents silently replacing any pre-existing evidence.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(manifest, stream, sort_keys=True, indent=2)
            stream.write('\n')
        print('Redacted report byte manifest created; origin and runtime remain unverified.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
