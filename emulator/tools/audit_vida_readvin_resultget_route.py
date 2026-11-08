#!/usr/bin/env python3
"""Safe declaration-only audit of potential VIDA ReadVin -> ResultGet -> AddVIN.

This classifies owner-supplied XML but never evaluates any parameter, service,
response, or callback. It must not create a replay fixture or accepted VIN.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from audit_vida_readvin_clr_dispatch import _load_private_zip
from audit_vida_readvin_property_classes import audit_xml as audit_property_classes

SCHEMA = 'virtualcar-vida-readvin-resultget-candidate-route-v2'
SCRIPT_DLL_SHA256 = 'd93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028'
CARCOM_DLL_SHA256 = '1735d8ac20d63a20afe13742ea5156cce5a5328392bd3e44d9ec3cd8ae0dbd07'
IDENTITY_METHODS = ('AddVIN', 'SetX40Serial')


def _class_is(node, classname):
    return node is not None and node.attrib.get('class', '').rsplit('.', 1)[-1] == classname


def audit_xml(xml_bytes):
    # Preserve the more restrictive original-IL XML selection checks and
    # bounded/DTD-safe parsing. Do not output its raw XML or dynamic IDs.
    base = audit_property_classes(xml_bytes)
    root = ET.fromstring(xml_bytes)
    content = root.find('./content')
    nodes = content.findall('./nodes/node')
    handlers = content.findall('./handlers/eventhandler')
    by_id = {n.attrib['nodeid']: n for n in nodes}
    readvin_ids = {i for i, node in by_id.items() if _class_is(node, 'ReadVinComponent')}
    resultget_nodes = {i: n for i, n in by_id.items() if _class_is(n, 'ResultGet')}
    resultget_ids = set(resultget_nodes)
    identity_ids = {i for i, node in by_id.items() if _class_is(node, 'VehicleIdentityOutput')}

    direct_gets = {}  # private IDs used locally only, never emitted
    readvin_event_target_ids = set()
    readvin_event_pairs = set()
    result_to_invalue_set_pairs = set()
    identity_get_source_ids = set()
    positive_readvin_event_pairs = set()
    onget_identity_source_ids = set()
    onget_addvin_source_ids = set()
    onget_x40_source_ids = set()
    stats = {
        'resultget_node_declarations': len(resultget_nodes),
        'resultget_nodes_with_direct_invalue_property': 0,
        'resultget_nodes_with_direct_invalue_class_response': 0,
        'resultget_nodes_with_extension_get': 0,
        'direct_get_property_declarations': 0,
        'direct_get_with_nonempty_output_property_key': 0,
        'getbyid_steps_with_key': 0,
        'getbyname_steps_with_key': 0,
        'getbyid_steps_missing_key': 0,
        'getbyname_steps_missing_key': 0,
        'unrecognized_extension_selection_steps': 0,
        'direct_propertyhandler_declarations': 0,
        'readvin_result_propertyhandler_declarations': 0,
        'readvin_result_to_resultget_invalue_set_declarations': 0,
        'enabled_readvin_result_to_resultget_invalue_sets': 0,
        'disabled_readvin_result_to_resultget_invalue_sets': 0,
        'readvin_result_setters_to_other_target_properties': 0,
        'readvin_event_to_resultget_execute_declarations': 0,
        'enabled_readvin_event_to_resultget_execute_declarations': 0,
        'readvin_positive_response_to_resultget_execute_declarations': 0,
        'enabled_readvin_positive_response_to_resultget_execute_declarations': 0,
        'reader_execute_calls_with_other_or_absent_event_name': 0,
        'resultget_onget_to_identity_declarations': 0,
        'enabled_resultget_onget_to_identity_declarations': 0,
        'resultget_to_identity_calls_with_other_or_absent_event_name': 0,
        'identity_calls_using_resultget_property_reference': 0,
        'identity_calls_using_declared_resultget_get_output': 0,
        'identity_calls_using_undeclared_resultget_output': 0,
        'identity_calls_using_resultget_non_get_property': 0,
        'enabled_identity_calls_using_resultget_get_output': 0,
        'other_identity_parameter_declarations': 0,
    }
    for node_id, node in resultget_nodes.items():
        prop = [p for p in node.findall('./property') if p.attrib.get('name') == 'InValue']
        stats['resultget_nodes_with_direct_invalue_property'] += int(bool(prop))
        stats['resultget_nodes_with_direct_invalue_class_response'] += int(
            len(prop) == 1 and prop[0].attrib.get('class') == 'Response')
        declared_outputs = set()
        direct_gets[node_id] = declared_outputs
        for extension in node.findall('./extension'):
            for get in extension.findall('./get'):
                stats['direct_get_property_declarations'] += 1
                outprop = get.attrib.get('property', '')
                if outprop:
                    declared_outputs.add(outprop)
                    stats['direct_get_with_nonempty_output_property_key'] += 1
                for child in get:
                    if child.tag in ('getbyid', 'getbyname'):
                        suffix = 'with_key' if child.attrib.get('key', '') else 'missing_key'
                        stats[child.tag + '_steps_' + suffix] += 1
                    else:
                        stats['unrecognized_extension_selection_steps'] += 1
        stats['resultget_nodes_with_extension_get'] += int(bool(declared_outputs))

    # Original Script.Parse selects handlers/propertyhandler. The original
    # ScriptPropertyHandler.Parse selects direct 'set' children and stores
    # source node/name; PropertyHandlerSet.Parse stores target node/property.
    # PropertyHandlerSet.ctor initializes Enabled=True, then *presence* of
    # disabled sets it false. Do not infer callback execution from XML.
    for ph in content.findall('./handlers/propertyhandler'):
        stats['direct_propertyhandler_declarations'] += 1
        source_id = ph.attrib.get('node', '')
        if source_id not in readvin_ids or ph.attrib.get('name') != 'Result':
            continue
        stats['readvin_result_propertyhandler_declarations'] += 1
        for setter in ph.findall('./set'):
            target_id = setter.attrib.get('node', '')
            if target_id in resultget_ids and setter.attrib.get('property') == 'InValue':
                stats['readvin_result_to_resultget_invalue_set_declarations'] += 1
                if 'disabled' in setter.attrib:
                    stats['disabled_readvin_result_to_resultget_invalue_sets'] += 1
                else:
                    stats['enabled_readvin_result_to_resultget_invalue_sets'] += 1
                    result_to_invalue_set_pairs.add((source_id, target_id))
            else:
                stats['readvin_result_setters_to_other_target_properties'] += 1

    for handler in handlers:
        event_source_id = handler.attrib.get('node', '')
        for call in handler.findall('./call'):
            target_id = call.attrib.get('node', '')
            parser_enabled = 'disabled' not in call.attrib
            if (event_source_id in readvin_ids and target_id in resultget_ids and
                    call.attrib.get('method') == 'Execute'):
                stats['readvin_event_to_resultget_execute_declarations'] += 1
                stats['enabled_readvin_event_to_resultget_execute_declarations'] += int(parser_enabled)
                if parser_enabled:
                    readvin_event_target_ids.add(target_id)
                    readvin_event_pairs.add((event_source_id, target_id))
                if handler.attrib.get('name') == 'OnPositiveResponse':
                    stats['readvin_positive_response_to_resultget_execute_declarations'] += 1
                    if parser_enabled:
                        stats['enabled_readvin_positive_response_to_resultget_execute_declarations'] += 1
                        positive_readvin_event_pairs.add((event_source_id, target_id))
                else:
                    stats['reader_execute_calls_with_other_or_absent_event_name'] += 1
            if not (target_id in identity_ids and call.attrib.get('method') in IDENTITY_METHODS):
                continue
            for param in call.findall('./parameter'):
                source_id = param.attrib.get('node', '')
                if 'node' not in param.attrib or source_id not in resultget_ids:
                    stats['other_identity_parameter_declarations'] += 1
                    continue
                stats['identity_calls_using_resultget_property_reference'] += 1
                prop_name = param.attrib.get('property', '')
                if prop_name in direct_gets[source_id]:
                    stats['identity_calls_using_declared_resultget_get_output'] += 1
                    stats['enabled_identity_calls_using_resultget_get_output'] += int(parser_enabled)
                    if parser_enabled:
                        identity_get_source_ids.add(source_id)
                    if handler.attrib.get('node', '') == source_id and handler.attrib.get('name') == 'OnGet':
                        stats['resultget_onget_to_identity_declarations'] += 1
                        if parser_enabled:
                            stats['enabled_resultget_onget_to_identity_declarations'] += 1
                            onget_identity_source_ids.add(source_id)
                            if call.attrib.get('method') == 'AddVIN':
                                onget_addvin_source_ids.add(source_id)
                            elif call.attrib.get('method') == 'SetX40Serial':
                                onget_x40_source_ids.add(source_id)
                    else:
                        stats['resultget_to_identity_calls_with_other_or_absent_event_name'] += 1
                elif not prop_name:
                    stats['identity_calls_using_undeclared_resultget_output'] += 1
                else:
                    # It could be another declared or dynamic property. Do not
                    # assume it came from ResultGet.setProperties.
                    stats['identity_calls_using_resultget_non_get_property'] += 1

    return {
        'schema_version': SCHEMA,
        'source': 'private_XML_static_declarations_only',
        'original_scripting_dll_sha256': SCRIPT_DLL_SHA256,
        'original_carcom_dll_sha256': CARCOM_DLL_SHA256,
        'script_content_layout_verified': base['original_parser_content_child_layout_verified'],
        'categorical_declarations': stats,
        # Historical two-event lexical gate is kept for compatibility. It
        # is NOT proof that the response object reached ResultGet.InValue.
        'candidate_route_lexically_present': bool(
            readvin_event_target_ids & identity_get_source_ids),
        # This legacy flag is only the 3 structural legs; it does not
        # ensure that the ORIGINAL event source names match real delegates.
        'candidate_three_leg_without_event_name_validation_lexically_present': bool(
            {extractor for _, extractor in
             (readvin_event_pairs & result_to_invalue_set_pairs)} &
            identity_get_source_ids),
        # Original VehCommBase exposes OnPositiveResponse, and ResultGet
        # exposes OnGet. ScriptNode callback indexes by (node, event NAME).
        # Requiring actual fields prevents three generic/missing-name
        # handlers from being promoted to a plausible route. Still static.
        'candidate_three_leg_route_with_property_binding_lexically_present': bool(
            {extractor for _, extractor in
             (positive_readvin_event_pairs & result_to_invalue_set_pairs)} &
            onget_identity_source_ids),
        'candidate_addvin_route_with_event_names_lexically_present': bool(
            {extractor for _, extractor in
             (positive_readvin_event_pairs & result_to_invalue_set_pairs)} &
            onget_addvin_source_ids),
        'candidate_x40_route_with_event_names_lexically_present': bool(
            {extractor for _, extractor in
             (positive_readvin_event_pairs & result_to_invalue_set_pairs)} &
            onget_x40_source_ids),
        'source_event_name_required': 'OnPositiveResponse',
        'resultget_event_name_required': 'OnGet',
        'event_delegates_were_observed_at_runtime': False,
        'candidate_three_leg_requires_same_readvin_and_resultget_nodes': True,
        'property_set_was_observed_at_runtime': False,
        'candidate_route_same_resultget_node_required': True,
        'declared_get_path_is_not_proven_response_value': True,
        'response_component_was_executed': False,
        'resultget_setproperties_was_executed': False,
        'methodbase_invoke_was_observed': False,
        'runtime_parameter_value_verified': False,
        'script_selected_by_runtime_getscript': False,
        'vin_accepted_by_client': False,
        'xc90_v8_my2009_verified': False,
        'replay_approved': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only VIDA ResultGet potential-route audit')
    parser.add_argument('private_zip', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if (out == args.private_zip.resolve() or out == repo_root or repo_root in out.parents or
            args.output.parent.is_symlink()):
        parser.error('unsafe output location')
    try:
        report = audit_xml(_load_private_zip(args.private_zip))
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        parser.error('private XML audit refused: ' + type(exc).__name__)
    print('ResultGet candidate XML declarations classified; no VIN response or callback verified')


if __name__ == '__main__':
    main()
