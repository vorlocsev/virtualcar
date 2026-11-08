#!/usr/bin/env python3
"""Private VIDA ReadVin XML property CLASS declarations, not VIN value flow.

Specific to original SHA-pinned BizServices.Scripting.DLL parsing conventions:
Script.Parse selects script/content/nodes/node and handlers/eventhandler;
ScriptNode.Parse selects child property; CallParameter.Parse selects either
node/property or value/class; Property.Parse takes class and type attributes.
Never runs the original DLL, VIDA, SQL, J2534 or a vehicle.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from audit_vida_readvin_clr_dispatch import _load_private_zip, audit_bytes

SCHEMA = 'virtualcar-vida-readvin-property-class-declarations-v1'
PROPERTY_CLASSES = ('Int', 'Double', 'String', 'PlotterlineList',
                    'Byte', 'Response', 'Parameter', 'PlotterValue')
CLASS_BINS = PROPERTY_CLASSES + ('unknown_or_missing',)


def _class_bin(value):
    return value if value in PROPERTY_CLASSES else 'unknown_or_missing'


def _bins():
    return {key: 0 for key in CLASS_BINS}


def audit_xml(data):
    # Validates source UTF-8, no DTD/ENTITY, bounded XML, node-ID uniqueness,
    # and direct event-call declarations. Never emits values or node IDs.
    baseline = audit_bytes(data)
    root = ET.fromstring(data)
    if root.tag != 'script':
        raise ValueError('expected script root')
    content_nodes = root.findall('./content')
    if len(content_nodes) != 1:
        raise ValueError('cannot establish original script/content selection')
    content = content_nodes[0]
    nodes = content.findall('./nodes/node')
    handlers = content.findall('./handlers/eventhandler')
    if not nodes or not handlers:
        raise ValueError('no original SelectNodes layout')
    # Fail closed if unrelated wrappers/duplicate sections caused the previous
    # broad lexical inspector to count more nodes/handlers than VIDA would.
    if (len(nodes) != baseline['declared_node_count'] or
            len(handlers) != baseline['direct_eventhandler_count']):
        raise ValueError('ambiguous source sections')
    by_id = {n.attrib['nodeid']: n for n in nodes}
    if len(by_id) != len(nodes):
        raise ValueError('duplicate or missing node identifier')
    properties = {}
    for node_id, node in by_id.items():
        properties[node_id] = {}
        for prop in node.findall('./property'):
            name = prop.attrib.get('name', '')
            if not name:
                continue
            if name in properties[node_id]:
                # A duplicate may be updated by script runtime; not safe to
                # choose one without observing execution.
                properties[node_id][name] = None
            else:
                properties[node_id][name] = prop.attrib.get('class', '')
    report = {}
    for method in ('AddVIN', 'SetX40Serial'):
        report[method.lower()] = {
            'direct_identity_call_declarations': 0,
            'parser_enabled_declarations': 0,
            'parser_disabled_declarations': 0,
            'direct_parameter_declarations': 0,
            'source_property_reference_parameters': 0,
            'source_property_class_bins': _bins(),
            'source_properties_not_in_xml': 0,
            'constant_value_class_parameters': 0,
            'constant_class_bins': _bins(),
            'parameter_declaration_is_not_runtime_value': True,
        }
    for handler in handlers:
        for call in handler.findall('./call'):
            method = call.attrib.get('method')
            if method not in ('AddVIN', 'SetX40Serial'):
                continue
            target = by_id.get(call.attrib.get('node', ''))
            if target is None or target.attrib.get('class', '').rsplit('.', 1)[-1] != 'VehicleIdentityOutput':
                continue
            out = report[method.lower()]
            out['direct_identity_call_declarations'] += 1
            if 'disabled' in call.attrib:
                out['parser_disabled_declarations'] += 1
            else:
                out['parser_enabled_declarations'] += 1
            for param in call.findall('./parameter'):
                out['direct_parameter_declarations'] += 1
                if 'node' in param.attrib:
                    out['source_property_reference_parameters'] += 1
                    source = properties.get(param.attrib.get('node', ''), {})
                    name = param.attrib.get('property', '')
                    if not name or name not in source:
                        out['source_properties_not_in_xml'] += 1
                        class_name = None
                    else:
                        class_name = source[name]
                    out['source_property_class_bins'][_class_bin(class_name)] += 1
                else:
                    out['constant_value_class_parameters'] += 1
                    out['constant_class_bins'][_class_bin(param.attrib.get('class', ''))] += 1
    return {
        'schema_version': SCHEMA,
        'source_kind': 'private_xml_static_declarations_only',
        'original_parser_content_child_layout_verified': True,
        'original_managed_assembly_sha256': 'd93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028',
        'property_class_enum_cases_verified_in_original_il': list(PROPERTY_CLASSES),
        'identity_method_parameter_declarations': report,
        'any_argument_runtime_value_computed': False,
        'getscript_selected_script_verified': False,
        'reflection_callback_executed': False,
        'vin_accepted_by_client': False,
        'xc90_v8_my2009_identified': False,
        'replay_approved': False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='Read-only VIDA ReadVin property CLASS audit')
    ap.add_argument('private_zip', type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(argv)
    src, dst = args.private_zip.resolve(), args.output.resolve()
    repo = Path(__file__).resolve().parents[2]
    if dst == src or dst == repo or repo in dst.parents or args.output.parent.is_symlink():
        ap.error('unsafe report destination')
    try:
        result = audit_xml(_load_private_zip(args.private_zip))
        with args.output.open('x', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write('\n')
    except (ValueError, OSError, ET.ParseError) as exc:
        ap.error('private XML classification refused: ' + type(exc).__name__)
    print('Property CLASS declarations classified; VIN flow remains UNVERIFIED')


if __name__ == '__main__':
    main()
