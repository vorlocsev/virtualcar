#!/usr/bin/env python3
"""Read-only CarCom default-CEM audit; emits counts, never diagnostic numbers.

Models GetCompatibleProfiles + vadis_GetDefaultEcuVariants and the first-entry
DefaultEcuVariantCache rule. Checks EVERY catalog profile with the exact requested
model/year/engine. Does not resolve VIN, select VIDA's runtime profile, generate
B9F0, or assert that a catalog default is the car's actual ECU.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

DIMENSIONS = ('Model', 'Year', 'Engine', 'Transmission', 'Body', 'Steering',
              'Market', 'ControlUnit', 'ChassisFrom', 'ChassisTo')
COLUMNS = tuple('fkT162_ProfileValue_' + dim for dim in DIMENSIONS)


def compatible(candidate, selected):
    # Source SQL uses equality, not range comparisons, even for chassis columns.
    return candidate['folderLevel'] > 1 and all(
        candidate[c] is None or selected[c] is None or candidate[c] == selected[c]
        for c in COLUMNS)


def value_id(db, kind, label):
    rows = db.execute('''SELECT id FROM "dbo.T162_ProfileValue"
        WHERE fkT163_ProfileValueType=? AND (identifier=? OR description=?)''',
                      (kind, label, label)).fetchall()
    if len(rows) != 1:
        raise ValueError('missing_or_ambiguous_profile_value')
    return rows[0][0]


def audit(db, model, year, engine):
    db.row_factory = sqlite3.Row
    wanted = tuple(value_id(db, kind, label) for kind, label in
                   ((1, model), (2, year), (3, engine)))
    profiles = list(db.execute('SELECT * FROM "dbo.T161_Profile"'))
    selected = [p for p in profiles if tuple(p[c] for c in COLUMNS[:3]) == wanted]
    if not selected:
        raise ValueError('no_exact_model_year_engine_profiles')
    # The original function selects t2 by identifier, not by numeric primary key.
    identifiers = Counter(p['identifier'] for p in profiles)
    if any(not p['identifier'] or identifiers[p['identifier']] != 1 for p in selected):
        raise ValueError('ambiguous_condensed_profile_identifier')
    groups = db.execute('''SELECT DISTINCT e.fkT102_EcuType FROM "dbo.T101_Ecu" e
        WHERE e.identifier='CEM' AND e.name LIKE '%(D2)%' ''').fetchall()
    if len(groups) != 1:
        raise ValueError('missing_or_ambiguous_CEM_D2_group')
    # Match the function group, not just a particular ECU name; the original
    # cache keys on T102.identifier and can contain other names in that group.
    mappings = list(db.execute('''SELECT p.*, v.id AS variant_id,
        e.identifier AS ecu_identifier, e.name AS ecu_name
        FROM "dbo.T161_Profile" p
        JOIN "dbo.T160_DefaultEcuVariant" d ON d.fkT161_Profile=p.id
        JOIN "dbo.T100_EcuVariant" v ON v.id=d.fkT100_EcuVariant
        JOIN "dbo.T101_Ecu" e ON e.id=v.fkT101_Ecu
        WHERE e.fkT102_EcuType=?''', (groups[0][0],)))
    missing = ambiguous = wrong_family = 0
    top_ids = set()
    levels = Counter()
    for profile in selected:
        matches = [m for m in mappings if compatible(m, profile)]
        if not matches:
            missing += 1
            continue
        level = max(m['folderLevel'] for m in matches)
        top = [m for m in matches if m['folderLevel'] == level]
        variants = {m['variant_id'] for m in top}
        # SQL sorts by level only. Never silently break ties by row/variant id.
        ambiguous += len(variants) != 1
        wrong_family += any(m['ecu_identifier'] != 'CEM' or '(D2)' not in m['ecu_name'] for m in top)
        top_ids.update(variants)
        levels[level] += 1
    return {
        'contract': 'cem-default-catalog-audit-v1',
        'selection': 'all_exact_model_year_engine_catalog_profiles_not_runtime',
        'profile_count': len(selected),
        'profiles_without_default': missing,
        'profiles_with_ambiguous_top_default': ambiguous,
        'profiles_with_other_top_ecu_family': wrong_family,
        'distinct_top_variants': len(top_ids),
        'top_folder_level_counts': dict(sorted(levels.items())),
        'all_profiles_same_cem_d2_default': not (missing or ambiguous or wrong_family) and len(top_ids) == 1,
        'runtime_profile_verified': False,
        'oem_b9f0_verified': False,
        'vida_gui_acceptance_verified': False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--carcom', type=Path, required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--year', required=True)
    p.add_argument('--engine', required=True)
    args = p.parse_args(argv)
    try:
        uri = args.carcom.resolve(strict=True).as_uri() + '?mode=ro&immutable=1'
        with closing(sqlite3.connect(uri, uri=True)) as db:
            result = audit(db, args.model, args.year, args.engine)
        print(json.dumps(result, sort_keys=True))
        return 0 if result['all_profiles_same_cem_d2_default'] else 1
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print('REJECTED: catalog default audit; private details withheld', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
