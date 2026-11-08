#!/usr/bin/env python3
"""Static, privacy-safe XML dispatch classification for SHA-pinned original VIDA IL.

Original BizServices.Scripting.DLL IL is *not* executed. A lexical XML
classification is NOT a verified runtime callback, VIN or CEM response.
"""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

SCHEMA = 'virtualcar-vida-readvin-clr-dispatch-static-v1'
MAX_ZIP_BYTES = 2 * 1024 * 1024
MAX_XML_BYTES = 1024 * 1024
MAX_ELEMENTS = 20_000
MAX_DEPTH = 96
MAX_ID_LENGTH = 128
METHODS = {'AddVIN': 'add_vin', 'SetX40Serial': 'set_x40_serial'}
PINNED_ASSEMBLY_SHA256 = 'd93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028'


def _tag(e):
    return e.tag.rsplit('}', 1)[-1] if isinstance(e.tag, str) else ''


def _load_private_zip(path):
    path = Path(path)
    if path.is_symlink() or path.suffix.lower() != '.zip' or not path.is_file():
        raise ValueError('unsafe input')
    size = path.stat().st_size
    if not 30 <= size <= MAX_ZIP_BYTES:
        raise ValueError('archive size outside limits')
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        if len(entries) != 1:
            raise ValueError('one entry required')
        member = entries[0]
        if (member.is_dir() or member.flag_bits & 1 or not member.compress_size
                or member.file_size > MAX_XML_BYTES
                or member.file_size > 100 * member.compress_size
                or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', member.filename)):
            raise ValueError('unsupported member')
        with z.open(member) as stream:
            data = stream.read(MAX_XML_BYTES + 1)
        if len(data) != member.file_size or len(data) > MAX_XML_BYTES:
            raise ValueError('invalid XML length')
    if (data.startswith((b'\xff\xfe', b'\xfe\xff')) or b'\x00' in data[:256]
            or re.search(rb'<!\s*(DOCTYPE|ENTITY)\b', data, re.I)):
        raise ValueError('unsafe XML markup')
    return data


def audit_bytes(data):
    if not isinstance(data, bytes) or len(data) > MAX_XML_BYTES:
        raise ValueError('unsupported XML bytes')
    if (data.startswith((b'\xff\xfe', b'\xfe\xff')) or b'\x00' in data[:256]
            or re.search(rb'<!\s*(DOCTYPE|ENTITY)\b', data, re.I)):
        raise ValueError('unsafe XML markup')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError('invalid XML') from exc
    if _tag(root) != 'script':
        raise ValueError('unexpected root')
    queue = [(root, 0)]
    count = 0
    while queue:
        e, depth = queue.pop()
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise ValueError('excessive XML complexity')
        queue.extend((c, depth + 1) for c in e)
    parents = {e: p for p in root.iter() for e in p}
    nodes = [e for p in root.iter() if _tag(p) == 'nodes'
             for e in p if _tag(e) == 'node']
    by_id = {}
    for e in nodes:
        node_id = e.attrib.get('nodeid', '')
        if not node_id or len(node_id) > MAX_ID_LENGTH or node_id in by_id:
            raise ValueError('missing or duplicate node ID')
        by_id[node_id] = e
    handlers = [e for p in root.iter() if _tag(p) == 'handlers'
                for e in p if _tag(e) == 'eventhandler']
    if not nodes or not handlers:
        raise ValueError('missing direct child node/handler sections')
    all_calls = [e for e in root.iter() if _tag(e) == 'call']
    recognized_calls = [e for h in handlers for e in h if _tag(e) == 'call']
    unrecognized_calls = len(all_calls) - len(recognized_calls)
    if unrecognized_calls < 0:
        raise ValueError('ambiguous duplicate handler section')
    reader_ids = {i for i, e in by_id.items()
                  if e.attrib.get('class', '').rsplit('.', 1)[-1] == 'ReadVinComponent'}
    group = {label: {
        'direct_identity_call_declarations': 0,
        'parser_enabled_by_absent_disabled_attribute': 0,
        'parser_disabled_by_present_disabled_attribute': 0,
        'direct_parameter_declarations': 0,
        'source_node_property_parameters': 0,
        'source_node_ref_matching_declared_node': 0,
        'source_node_ref_matching_readvin_node': 0,
        'source_node_ref_missing_or_empty': 0,
        'source_node_parameters_with_property_attribute': 0,
        'constant_value_class_parameters': 0,
        'constant_parameters_with_value_attribute': 0,
        'constant_parameters_with_class_attribute': 0,
        'non_direct_parameters_ignored': 0,
    } for label in METHODS.values()}
    for handler in handlers:
        for call in handler:
            if _tag(call) != 'call':
                continue
            method = METHODS.get(call.attrib.get('method'))
            target = by_id.get(call.attrib.get('node', ''))
            if method is None or target is None or (
                target.attrib.get('class', '').rsplit('.', 1)[-1] != 'VehicleIdentityOutput'
            ):
                continue
            g = group[method]
            g['direct_identity_call_declarations'] += 1
            # Original EventHandlerCall.ctor starts Enabled=true; Parse flips
            # the field to false on ATTRIBUTE PRESENCE, regardless of text.
            presence = 'disabled' in call.attrib
            key = ('parser_disabled_by_present_disabled_attribute' if presence
                   else 'parser_enabled_by_absent_disabled_attribute')
            g[key] += 1
            direct_params = [p for p in call if _tag(p) == 'parameter']
            any_params = [p for p in call.iter() if _tag(p) == 'parameter']
            g['non_direct_parameters_ignored'] += len(any_params) - len(direct_params)
            g['direct_parameter_declarations'] += len(direct_params)
            for p in direct_params:
                # CallParameter.Parse branches on presence of 'node' alone.
                if 'node' in p.attrib:
                    g['source_node_property_parameters'] += 1
                    node_id = p.attrib['node']
                    g['source_node_ref_matching_declared_node'] += int(node_id in by_id)
                    g['source_node_ref_matching_readvin_node'] += int(node_id in reader_ids)
                    g['source_node_ref_missing_or_empty'] += int(node_id not in by_id)
                    g['source_node_parameters_with_property_attribute'] += int('property' in p.attrib)
                else:
                    g['constant_value_class_parameters'] += 1
                    g['constant_parameters_with_value_attribute'] += int('value' in p.attrib)
                    g['constant_parameters_with_class_attribute'] += int('class' in p.attrib)
    return {
        'schema_version': SCHEMA,
        'analysis_kind': 'static_xml_plus_pinned_original_managed_il_contract',
        'original_binary_executed': False,
        'xml_elements_examined': count,
        'declared_node_count': len(nodes),
        'declared_readvin_node_count': len(reader_ids),
        'direct_eventhandler_count': len(handlers),
        'direct_event_call_declarations': len(recognized_calls),
        'call_tags_not_direct_child_of_eventhandler_ignored': unrecognized_calls,
        'identity_method_classifications': group,
        'only_direct_parameter_children_selected': True,
        'presence_of_disabled_attribute_disables_original_parser_call': True,
        'node_attribute_selects_property_reference_mode': True,
        'absence_of_node_attribute_selects_constant_value_class_mode': True,
        'parameter_runtime_value_computed': False,
        'reflection_method_invoked': False,
        'selected_readvin_script_runtime_verified': False,
        'vehicle_vin_accepted': False,
        'xc90_v8_my2009_verified': False,
        'replay_approved': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Private VIDA ReadVin CLR dispatch static audit')
    parser.add_argument('private_zip', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if (output == args.private_zip.resolve() or output == repo_root
            or repo_root in output.parents or args.output.parent.is_symlink()):
        parser.error('unsafe output location')
    try:
        report = audit_bytes(_load_private_zip(args.private_zip))
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error('private static source rejected: ' + type(exc).__name__)
    print('ReadVin dispatch declarations classified; runtime VIN remains unverified.')


if __name__ == '__main__':
    main()
