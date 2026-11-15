#!/usr/bin/env python3
"""Prepare PRIVATE offline B9FB parser input from one explicit CarCom variant.

Does not select the vehicle's ECU variant or activate a profile. Uses immutable
SQLite exports, preserving original block/value/scaling rows and T111 XML.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

import build_b3a146_cem40_lab_profile as lab


def snapshot(db, variant, profile, identity):
    lab.validate_profile(profile, identity)
    db.row_factory = sqlite3.Row
    ecu = db.execute('''SELECT e.identifier,e.name,v.inheritance
        FROM "dbo.T100_EcuVariant" v JOIN "dbo.T101_Ecu" e ON e.id=v.fkT101_Ecu
        WHERE v.id=?''', (variant,)).fetchone()
    if not ecu or ecu['identifier'] != 'CEM' or '(D2)' not in ecu['name'] or ecu['inheritance']:
        raise ValueError('explicit_noninherited_CEM_D2_variant_required')
    sections = db.execute('''SELECT DISTINCT b.id,b.length FROM "dbo.T141_Block" b
        JOIN "dbo.T144_BlockChild" x ON x.fkT141_Block_Child=b.id
        JOIN "dbo.T150_BlockValue" v ON v.fkT141_Block=b.id
        JOIN "dbo.T142_BlockType" t ON t.id=b.fkT142_BlockType
        WHERE x.fkT100_EcuVariant=? AND x.fkT141_Block_Parent=1
        AND t.identifier='BLOFF' AND v.CompareValue='0xFB' AND v.Operator=1''', (variant,)).fetchall()
    if len(sections) != 1:
        raise ValueError('unique_direct_FB_section_required')
    section = sections[0]
    edges = [dict(r) for r in db.execute('''SELECT x.* FROM "dbo.T144_BlockChild" x
        JOIN "dbo.T141_Block" b ON b.id=x.fkT141_Block_Child
        JOIN "dbo.T142_BlockType" t ON t.id=b.fkT142_BlockType
        WHERE x.fkT100_EcuVariant=? AND
        ((x.fkT141_Block_Parent=1 AND x.fkT141_Block_Child=?) OR
         (x.fkT141_Block_Parent=? AND t.identifier='PARAM'))
        ORDER BY x.SortOrder,x.fkT141_Block_Child''', (variant, section['id'], section['id']))]
    blocks = []
    for edge in edges:
        block = dict(db.execute('SELECT * FROM "dbo.T141_Block" WHERE id=?',
                                (edge['fkT141_Block_Child'],)).fetchone())
        if block['composite'] or block['exclude'] or block['offset'] < 0 or block['length'] <= 0:
            raise ValueError('unsupported_composite_excluded_or_empty_block')
        values = [dict(r) for r in db.execute('''SELECT v.*,s.definition AS scaling
            FROM "dbo.T150_BlockValue" v JOIN "dbo.T155_Scaling" s ON s.id=v.fkT155_Scaling
            WHERE v.fkT141_Block=? ORDER BY v.SortOrder,v.Id''', (block['id'],))]
        if not values:
            raise ValueError('missing_original_value_or_scaling')
        block['values'] = values
        blocks.append(block)
    vins = [b for b in blocks if b['name'] == 'VIN']
    if len(vins) != 1 or vins[0]['fkT143_BlockDataType'] != 51:
        raise ValueError('unique_original_ASCII_VIN_field_required')
    definitions = db.execute('SELECT definition FROM "dbo.T111_Service" WHERE service=?', ('B9',)).fetchall()
    if len(definitions) != 1:
        raise ValueError('unique_original_B9_definition_required')
    definition = definitions[0][0]
    if isinstance(definition, bytes):
        definition = definition.decode('utf-8')
    cfg = lab._normalized(lab._parse(profile))['d2_40']
    frames = [bytes.fromhex(cfg[f'b9fbframe{i:x}']) for i in range(int(cfg['b9fbframecount']))]
    payload = lab.decode_d2(frames, service=0xF9, selector=0xFB)
    # RawResponse begins with the selector; address/service belong to transport.
    raw = payload[2:]
    return {'contract': 'private-original-b9fb-parser-v1', 'variant': variant,
            'selection': 'explicit_catalog_comparison_not_vehicle_identification',
            'profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
            'definition': definition, 'blocks': blocks, 'edges': edges,
            'types': [dict(r) for r in db.execute('SELECT * FROM "dbo.T142_BlockType"')],
            'section_bits': section['length'], 'vin_block': vins[0]['id'],
            'body_bytes': len(raw)-1, 'raw': list(raw), 'expected_vin': lab._identity(identity)}


def write_private(path, data):
    path = Path(os.path.abspath(path))
    if path.name != 'b9fb-parser-input.json' or 'lab' not in path.parent.name.casefold() or not path.parent.is_dir():
        raise ValueError('dedicated_existing_lab_directory_required')
    if path.is_symlink() or any(p.is_symlink() or (p / '.git').exists() for p in (path.parent, *path.parent.parents)):
        raise ValueError('private_output_must_be_outside_checkout')
    with path.open('x', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--carcom', type=Path, required=True)
    p.add_argument('--variant', type=int, required=True)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--identity-json', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.profile.stat().st_size > lab.MAX_BYTES:
            raise ValueError('oversized_profile')
        uri = args.carcom.resolve(strict=True).as_uri() + '?mode=ro&immutable=1'
        with sqlite3.connect(uri, uri=True) as db:
            data = snapshot(db, args.variant, args.profile.read_text(encoding='utf-8-sig'),
                            lab._read_identity_file(args.identity_json))
        write_private(args.output, data)
        print('PASS: private original catalog snapshot; ECU variant selection NOT_VERIFIED')
        return 0
    except (OSError, ValueError, sqlite3.Error, configparser.Error):
        print('REJECTED: private parser input; details withheld', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
