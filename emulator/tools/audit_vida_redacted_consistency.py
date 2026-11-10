#!/usr/bin/env python3
"""Cross-check *already redacted* original VIDA ReadVin graph v2/v3 reports.

Never reads original ZIP/XML or exports input IDs, paths or field values.
Reports static declaration consistency only, not execution or client VIN.
"""
import argparse
import json
from pathlib import Path

SCHEMA = 'virtualcar-vida-redacted-readvin-crosscheck-v1'
MAX_BYTES = 128 * 1024


def _unique_json_keys(pairs):
    # Duplicate keys can hide conflicting evidence flags or schemas.
    # Reject them at every nesting level instead of taking the last value.
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate redacted JSON key')
        result[key] = value
    return result


def _no_nonfinite_json(value):
    # Python's json parser otherwise accepts NaN and Infinity extensions.
    raise ValueError('nonfinite redacted JSON value')


def _read(path, expected):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError('unsupported input')
    obj = json.loads(path.read_text(encoding='utf-8'),
                     object_pairs_hook=_unique_json_keys,
                     parse_constant=_no_nonfinite_json)
    if not isinstance(obj, dict) or obj.get('schema_version') != expected:
        raise ValueError('wrong report schema')
    return obj


def _uint(value):
    if type(value) is not int or not 0 <= value <= 20000:
        raise ValueError('invalid bounded count')
    return value


def _yes(value):
    if type(value) is not bool:
        raise ValueError('invalid boolean')
    return value


def analyze(v2, v3):
    if v2.get('schema_version') != 'virtualcar-vida-single-private-readvin-zip-v1' or \
       v3.get('schema_version') != 'virtualcar-vida-readvin-static-topology-v1':
        raise ValueError('wrong report schemas')
    g = v2['identity_xml_graph_declarations']
    layout = g['graph_layout']
    groups = v3['identity_output_method_topology']
    flags = v2['lexical_tokens_present_not_execution']
    if layout['status'] not in ('nested_sections', 'direct_sections'):
        raise ValueError('incomplete graph layout')
    if not _yes(v2['xml_zip_structure_validated']) or not _yes(v3['all_node_and_call_sections_resolved']):
        raise ValueError('incomplete input verification')
    # Fail closed if either upstream report claimed runtime identity from a static audit.
    for obj, key in ((v2, 'script_selected_by_getscript_runtime'),
                     (v2, 'vin_accepted_by_client'),
                     (v2, 'b9fb_to_vin_runtime_flow_verified'),
                     (v3, 'actual_runtime_graph_execution_verified'),
                     (v3, 'client_vin_accepted'),
                     (v3, 'replay_approved')):
        if _yes(obj[key]):
            raise ValueError('unexpected runtime claim in static report')
    checks = {
        'node_count': (_uint(g['node_count']), _uint(v3['node_count'])),
        'readvin_nodes': (_uint(g['readvin_component_count']),
                          _uint(v3['node_role_counts']['readvin'])),
        'identity_output_nodes': (_uint(g['vehicle_identity_output_count']),
                                  _uint(v3['node_role_counts']['identity_output'])),
        'event_handlers': (_uint(g['event_handler_count']), _uint(v3['eventhandler_count'])),
        'declared_calls': (_uint(g['declared_call_count']),
                           _uint(v3['declared_event_call_count'])),
        'add_vin_declarations': (
            _uint(g['declared_identity_edges']['add_vin']['declared']),
            _uint(groups['add_vin']['total_targeting_identity_output'])),
        'x40_declarations': (
            _uint(g['declared_identity_edges']['set_x40_serial']['declared']),
            _uint(groups['set_x40_serial']['total_targeting_identity_output'])),
    }
    mismatches = sorted(key for key, (a, b) in checks.items() if a != b)
    if mismatches:
        # Do not print original source values, fields or paths.
        raise ValueError('redacted reports disagree on structural counters')
    # The claimed ReadVin identity graph must not be vacuously "consistent"
    # when the redacted reports have no reader or no identity output.
    if (checks['readvin_nodes'][0] == 0
            or checks['identity_output_nodes'][0] == 0
            or checks['add_vin_declarations'][0] + checks['x40_declarations'][0] == 0):
        raise ValueError('incomplete ReadVin identity declarations')
    total_nodes = checks['node_count'][0]
    roles = v3['node_role_counts']
    if sum(_uint(roles[k]) for k in ('readvin', 'identity_output', 'other', 'unresolved')) != total_nodes:
        raise ValueError('role total mismatch')
    for key in ('f114', 'b9fb', 'addvin', 'setx40serial'):
        _yes(flags[key])
    distances = {}
    binding_declarations = {}
    for label in ('add_vin', 'set_x40_serial'):
        item = groups[label]
        n = checks['add_vin_declarations' if label == 'add_vin' else 'x40_declarations'][0]
        bins = item['possible_declared_chain_distance_to_identity']
        if sum(_uint(bins[k]) for k in ('one_edge', 'two_edges','three_or_more_edges',
                                       'no_path_in_event_call_graph',
                                       'explicitly_disabled_call')) != n:
            raise ValueError('chain partition mismatch')
        distances[label] = {
            k: _uint(bins[k]) for k in ('one_edge', 'two_edges', 'three_or_more_edges',
                                        'no_path_in_event_call_graph', 'explicitly_disabled_call')
        }
        old = g['declared_identity_edges'][label]
        newer = item['disabled_attribute_counts']
        aligned = (
            ('absent_disabled_attribute', 'unspecified'),
            ('not_disabled_literal', 'not_disabled_literal'),
            ('disabled_literal', 'disabled_literal'),
            ('unrecognized_disabled_literal', 'unrecognized_literal'),
        )
        categories = {}
        for source_key, target_key in aligned:
            v2_count, v3_count = _uint(old[source_key]), _uint(newer[target_key])
            if v2_count != v3_count:
                raise ValueError('identity disabled-attribute categories disagree')
            categories[target_key] = v3_count
        if sum(categories.values()) != n:
            raise ValueError('identity disabled categories do not partition calls')
        calls_with_params = _uint(item['calls_with_declared_parameter_child'])
        total_params = _uint(item['declared_parameter_child_total'])
        if calls_with_params > n or total_params < calls_with_params:
            raise ValueError('invalid declared parameter counts')
        binding_declarations[label] = {
            'call_count': n,
            'disabled_attribute_categories': categories,
            'calls_with_declared_parameter_child': calls_with_params,
            'declared_parameter_child_total': total_params,
            'explicitly_not_disabled_does_not_prove_execution': True,
        }
    return {
        'schema_version': SCHEMA,
        'input_kind': 'two_redacted_static_vida_reports',
        'structural_counters_consistent': True,
        'crosschecked_fields': len(checks),
        'nodes': total_nodes,
        'readvin_nodes': checks['readvin_nodes'][0],
        'identity_output_nodes': checks['identity_output_nodes'][0],
        'event_handlers': checks['event_handlers'][0],
        'declared_calls': checks['declared_calls'][0],
        'identity_methods': {k: checks[k][0] for k in ('add_vin_declarations','x40_declarations')},
        'declared_chain_length_counts': distances,
        'identity_parameter_declarations': binding_declarations,
        'all_identity_calls_have_parameter_child': all(
            x['calls_with_declared_parameter_child'] == x['call_count']
            for x in binding_declarations.values()),
        'identity_disabled_unspecified_total': sum(
            x['disabled_attribute_categories']['unspecified']
            for x in binding_declarations.values()),
        'lexical_f114_present': flags['f114'],
        'lexical_b9fb_present': flags['b9fb'],
        'original_xml_included': False,
        'runtime_readvin_selected': False,
        'vin_accepted_by_client': False,
        'xc90_v8_my2009_verified': False,
        'replay_approved': False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph_v2', type=Path)
    ap.add_argument('topology_v3', type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(argv)
    output = args.output.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    if (output in (args.graph_v2.resolve(), args.topology_v3.resolve()) or
            output == repo_root or repo_root in output.parents or
            args.output.parent.is_symlink()):
        ap.error('unsafe output')
    try:
        result = analyze(_read(args.graph_v2, 'virtualcar-vida-single-private-readvin-zip-v1'),
                         _read(args.topology_v3, 'virtualcar-vida-readvin-static-topology-v1'))
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        ap.error('redacted report crosscheck failed: ' + type(exc).__name__)
    print('Redacted VIDA v2/v3 static counters consistent; no VIN/runtime proof.')


if __name__ == '__main__':
    main()
