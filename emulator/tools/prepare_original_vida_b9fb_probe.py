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
import xml.etree.ElementTree as ET

import build_b3a146_cem40_lab_profile as lab


def readvin_binding(db, xml, node_name):
    """Resolve a static, non-relay CEM40 ReadVin -> ResultGet -> AddVIN path.

    Deliberately fails closed on unsupported/dynamic/ambiguous bindings. The
    EcuVariant is a script parser template, NOT an OEM number to reply in B9F0.
    """
    if len(xml) > 512 * 1024 or b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise ValueError('unsupported_XML')
    root = ET.fromstring(xml)

    def one(items):
        items = list(items)
        if len(items) != 1:
            raise ValueError('ambiguous_or_missing_script_binding')
        return items[0]

    nodes = {}
    for n in root.iter('node'):
        key = n.get('nodeid')
        if not key or key in nodes:
            raise ValueError('duplicate_or_missing_node_id')
        nodes[key] = n
    node = nodes.get(node_name)
    if node is None or node.get('class') != 'Components.ReadVinComponent':
        raise ValueError('ReadVin_node_required')
    props = {}
    for p in node.findall('property'):
        key = p.get('name')
        if key in props:
            raise ValueError('duplicate_property')
        props[key] = p.get('value')
    required = {'Mode': 'EcuVariant', 'Identifier': 'FB', 'BusId': '0',
                'UseRelay': '0', 'EcuAddress': '64'}
    if any(props.get(k) != v for k, v in required.items()):
        raise ValueError('explicit_nonrelay_CEM40_B9FB_required')
    service = one(db.execute('SELECT service FROM "dbo.T111_Service" WHERE id=?',
                             (int(props['ServiceId']),)))
    if service[0] != 'B9':
        raise ValueError('service_is_not_B9')
    variant = one(db.execute('SELECT id FROM "dbo.T100_EcuVariant" WHERE identifier=?',
                             (props.get('EcuVariant'),)))[0]

    def event(source, name, method):
        h = one(n for n in root.iter('eventhandler') if n.get('node') == source and n.get('name') == name)
        call = one(h)
        if call.tag != 'call' or call.get('method') != method:
            raise ValueError('unsupported_event_binding')
        return call

    positive = event(node_name, 'OnPositiveResponse', 'Execute')
    result_name = positive.get('node')
    result = nodes.get(result_name)
    if result is None or result.get('class') != 'Components.ResultGet':
        raise ValueError('ResultGet_required')
    binding = one(n for n in root.iter('propertyhandler') if n.get('node') == node_name and n.get('name') == 'Result')
    setter = one(binding)
    if setter.tag != 'set' or setter.get('node') != result_name or setter.get('property') != 'InValue':
        raise ValueError('response_binding_mismatch')
    get = one(result.findall('./extension/get'))
    path = list(get)
    if (get.get('property') != 'VIN' or len(path) != 3 or
            [(p.tag, p.get('key')) for p in (path[0], path[2])] !=
            [('getbyname', 'Parameters'), ('getbyname', 'value')] or path[1].tag != 'getbyid'):
        raise ValueError('unsupported_VIN_result_path')
    text_id = int(path[1].get('key'))
    add = event(result_name, 'OnGet', 'AddVIN')
    output = nodes.get(add.get('node'))
    parameter = one(add)
    if (output is None or output.get('class') != 'Components.VehicleIdentityOutput' or
            parameter.tag != 'parameter' or parameter.get('node') != result_name or parameter.get('property') != 'VIN'):
        raise ValueError('AddVIN_binding_mismatch')
    # Any extra input assignment could override the literals above at runtime.
    if any(n.get('node') == node_name for n in root.iter('set')):
        raise ValueError('dynamic_ReadVin_inputs_not_supported')
    return variant, {'source_sha256': hashlib.sha256(xml).hexdigest(),
                     'result_text_id': text_id, 'node': node_name,
                     'result_path': ['Parameters', text_id, 'value'],
                     'output_method': 'AddVIN',
                     'selection': 'original_script_static_binding_not_runtime_execution'}


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


def script_snapshot(db, xml, node_name, profile, identity):
    variant, binding = readvin_binding(db, xml, node_name)
    data = snapshot(db, variant, profile, identity)
    vin = next(b for b in data['blocks'] if b['id'] == data['vin_block'])
    if vin['fkT190_Text'] != binding['result_text_id']:
        raise ValueError('script_result_key_does_not_select_catalog_VIN')
    data['readvin_binding'] = binding
    data['selection'] = binding['selection']
    return data


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
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument('--variant', type=int)
    selection.add_argument('--readvin-xml', type=Path)
    p.add_argument('--readvin-node')
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--identity-json', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.profile.stat().st_size > lab.MAX_BYTES:
            raise ValueError('oversized_profile')
        uri = args.carcom.resolve(strict=True).as_uri() + '?mode=ro&immutable=1'
        with sqlite3.connect(uri, uri=True) as db:
            profile = args.profile.read_text(encoding='utf-8-sig')
            identity = lab._read_identity_file(args.identity_json)
            if args.readvin_xml:
                if not args.readvin_node or args.readvin_xml.stat().st_size > 512 * 1024:
                    raise ValueError('bounded_ReadVin_XML_and_explicit_node_required')
                data = script_snapshot(db, args.readvin_xml.read_bytes(), args.readvin_node, profile, identity)
            elif args.readvin_node:
                raise ValueError('ReadVin_XML_required')
            else:
                data = snapshot(db, args.variant, profile, identity)
        write_private(args.output, data)
        print('PASS: private original catalog snapshot; ECU variant selection NOT_VERIFIED')
        return 0
    except (OSError, ValueError, KeyError, ET.ParseError, sqlite3.Error, configparser.Error):
        print('REJECTED: private parser input; details withheld', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
