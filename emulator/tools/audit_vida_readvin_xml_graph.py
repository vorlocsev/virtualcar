#!/usr/bin/env python3
"""Read-only, privacy-constrained structural audit of a locally owned VIDA XML script.

Never exports original XML, script IDs, node IDs, VIN, parameter values or
vehicle data. Edges are declarations, not evidence of executed methods.
"""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SCHEMA = "virtualcar-vida-readvin-xml-graph-v1"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ELEMENTS = 20000
MAX_ID_LENGTH = 128
MAX_DEPTH = 96
FORBIDDEN_MARKUP = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
IDENTITY_METHODS = ("AddVIN", "SetX40Serial")


def _kind(node):
    if node is None:
        return "unresolved"
    classname = node.attrib.get("class", "")
    if len(classname) > MAX_ID_LENGTH:
        return "unrecognized"
    end = classname.rsplit(".", 1)[-1]
    if end == "VehicleIdentityOutput":
        return "identity_output"
    if end == "ReadVinComponent":
        return "readvin_component"
    return "other_component"


def _disabled(attribute):
    # Missing/unknown literals must not imply that a callback was enabled.
    if attribute is None:
        return "absent_disabled_attribute"
    if attribute.strip().lower() in ("false", "0"):
        return "not_disabled_literal"
    if attribute.strip().lower() in ("true", "1"):
        return "disabled_literal"
    return "unrecognized_disabled_literal"


def audit_xml_bytes(xml_data):
    if not isinstance(xml_data, bytes) or len(xml_data) > MAX_FILE_BYTES:
        raise ValueError("invalid source length")
    # Fail closed on UTF-16/other wide encodings: the DTD scan is UTF-8 only.
    if xml_data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in xml_data[:256]:
        raise ValueError("only UTF-8 XML is supported")
    if FORBIDDEN_MARKUP.search(xml_data):
        raise ValueError("DTD and entities are unsupported")
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise ValueError("invalid XML") from exc
    if root.tag != "script":
        raise ValueError("unexpected document root")

    count = 0
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise ValueError("excessive XML structure")
        stack.extend((child, depth + 1) for child in node)

    # VIDA XML may nest sections under version/metadata wrappers. Resolve
    # by the semantic section ancestor, not only ./nodes and ./handlers.
    # Do not misclassify incidental <node>/<call> outside these sections.
    def local_name(element):
        return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""

    parent = {child: owner for owner in root.iter() for child in owner}

    def has_section_ancestor(element, section):
        current = parent.get(element)
        while current is not None:
            if local_name(current) == section:
                return True
            current = parent.get(current)
        return False

    def nearest_handler(element):
        current = parent.get(element)
        while current is not None:
            if local_name(current) in ("eventhandler", "propertyhandler"):
                return current
            current = parent.get(current)
        return None

    def nearest_call(element):
        # Attribute declarations under a nested child call must not be
        # promoted as parameters of the enclosing identity method call.
        current = parent.get(element)
        while current is not None:
            if local_name(current) == "call":
                return current
            current = parent.get(current)
        return None

    all_nodes = [e for e in root.iter() if local_name(e) == "node"]
    all_handlers = [e for e in root.iter() if local_name(e) == "eventhandler"]
    all_calls = [e for e in root.iter() if local_name(e) == "call"]
    # Nested <call> elements have ambiguous event-source semantics.
    # Count them for structural completeness, but never promote them to
    # a candidate executable identity event or potential VIN path.
    nested_calls = sum(nearest_call(e) is not None for e in all_calls)
    nodes = [e for e in all_nodes if has_section_ancestor(e, "nodes")]
    handlers = [e for e in all_handlers if has_section_ancestor(e, "handlers")]
    unclassified_nodes = len(all_nodes) - len(nodes)
    unclassified_handlers = len(all_handlers) - len(handlers)
    direct_path_matched = bool(root.findall("./nodes/node")) and bool(
        root.findall("./handlers/eventhandler"))
    graph_sections_found = any(local_name(e) == "nodes" for e in root.iter()) and any(
        local_name(e) == "handlers" for e in root.iter())
    node_by_id = {}
    for node in nodes:
        node_id = node.attrib.get("nodeid", "")
        if not node_id or len(node_id) > MAX_ID_LENGTH or node_id in node_by_id:
            raise ValueError("missing/duplicate/excessive node identifier")
        node_by_id[node_id] = node

    identity_nodes = sum(_kind(n) == "identity_output" for n in nodes)
    readvin_nodes = sum(_kind(n) == "readvin_component" for n in nodes)
    output_node = node_by_id.get("Output")
    output_is_identity = _kind(output_node) == "identity_output"
    calls = 0
    classified = {
        "AddVIN": {"declared": 0, "not_disabled_literal": 0, "disabled_literal": 0,
                   "absent_disabled_attribute": 0,
                   "unrecognized_disabled_literal": 0, "readvin_source_node": 0},
        "SetX40Serial": {"declared": 0, "not_disabled_literal": 0, "disabled_literal": 0,
                         "absent_disabled_attribute": 0,
                         "unrecognized_disabled_literal": 0, "readvin_source_node": 0},
    }
    # Only these *attribute names* can claim a lexical node reference.
    # Even a recognized key and exact ID match is NOT a runtime binding.
    reference_keys = {"node", "ref", "source"}
    reader_ids = {k for k, v in node_by_id.items() if _kind(v) == "readvin_component"}
    for group in classified.values():
        group["parameter_declarations_only"] = {
            "calls_with_parameter_child": 0,
            "declared_parameter_children": 0,
            "calls_with_reference_like_key_matching_node_id": 0,
            "calls_with_reference_like_key_matching_reader_id": 0,
            "calls_with_parameter_text": 0,
        }
    unresolved_target = 0
    other_target_identity_method = 0
    for handler in handlers:
        source = node_by_id.get(handler.attrib.get("node", ""))
        for call in handler.iter():
            if local_name(call) != "call" or nearest_handler(call) is not handler:
                continue
            calls += 1
            if nearest_call(call) is not None:
                # Its XML parameter belongs to this inner call, but its
                # event-source/dispatch semantics are NOT established.
                continue
            method_name = call.attrib.get("method")
            if method_name not in IDENTITY_METHODS:
                continue
            target = node_by_id.get(call.attrib.get("node", ""))
            kind = _kind(target)
            if kind == "unresolved":
                unresolved_target += 1
            if kind != "identity_output":
                other_target_identity_method += 1
                continue
            group = classified[method_name]
            group["declared"] += 1
            group[_disabled(call.attrib.get("disabled"))] += 1
            # Nearest-call ownership prevents one nested call's parameter
            # from being counted as a sibling/outer AddVIN argument.
            params = [e for e in call.iter()
                      if local_name(e) == "parameter" and nearest_call(e) is call]
            counts = group["parameter_declarations_only"]
            counts["calls_with_parameter_child"] += int(bool(params))
            counts["declared_parameter_children"] += len(params)
            has_ref = has_reader_ref = has_text = False
            for param in params:
                has_text |= any(bool((e.text or "").strip()) for e in param.iter())
                for key, value in param.attrib.items():
                    local_key = key.rsplit("}", 1)[-1]
                    has_ref |= local_key in reference_keys and value in node_by_id
                    has_reader_ref |= local_key in reference_keys and value in reader_ids
            counts["calls_with_reference_like_key_matching_node_id"] += int(has_ref)
            counts["calls_with_reference_like_key_matching_reader_id"] += int(has_reader_ref)
            counts["calls_with_parameter_text"] += int(has_text)
            if _kind(source) == "readvin_component":
                group["readvin_source_node"] += 1

    return {
        "schema_version": SCHEMA,
        "source_kind": "private_vida_xml_static_structure_only",
        "xml_structure_parsed": True,
        "xml_elements_examined": count,
        "graph_layout": {
            "status": ("unresolved_or_partial" if not graph_sections_found or
                       unclassified_nodes or unclassified_handlers or
                       len(all_calls) != calls or nested_calls else
                       "direct_sections" if direct_path_matched else "nested_sections"),
            "node_elements_any_depth": len(all_nodes),
            "eventhandler_elements_any_depth": len(all_handlers),
            "call_elements_any_depth": len(all_calls),
            "call_elements_nested_under_call_not_promoted": nested_calls,
            "node_elements_outside_nodes_section": unclassified_nodes,
            "eventhandler_elements_outside_handlers_section": unclassified_handlers,
            "call_elements_not_in_parsed_eventhandlers": len(all_calls) - calls,
            "section_anchors_present": graph_sections_found,
        },
        "node_count": len(nodes),
        "event_handler_count": len(handlers),
        "declared_call_count": calls,
        "readvin_component_node_count": readvin_nodes,
        "vehicle_identity_output_node_count": identity_nodes,
        "named_output_node_is_vehicle_identity_output": output_is_identity,
        "declared_identity_method_edges": {
            "add_vin": classified["AddVIN"],
            "set_x40_serial": classified["SetX40Serial"],
        },
        "identity_method_calls_with_unresolved_target": unresolved_target,
        "identity_method_calls_to_non_identity_target": other_target_identity_method,
        "all_edges_are_declarations_not_execution": True,
        "observed_script_was_selected_by_vida": False,
        "observed_event_callback_executed": False,
        "observed_vehicle_identity_returned": False,
        "actual_vida_client_identity_verified": False,
        "xc90_v8_my2009_verified": False,
        "replay_approved": False,
    }


def audit_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("invalid source file")
    return audit_xml_bytes(path.read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline VIDA XML event graph safety audit")
    parser.add_argument("private_xml", type=Path, help="Local authorized original XML, never uploaded")
    parser.add_argument("--output", required=True, type=Path, help="New categorical JSON outside the repository")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if out == repo or repo in out.parents or out == args.private_xml.resolve():
        parser.error("output path must be outside repository and different from source")
    try:
        result = audit_file(args.private_xml)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error("invalid local XML structure: " + type(exc).__name__)
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError as exc:
        parser.error("cannot create exclusive categorical report: " + type(exc).__name__)
    print("VIDA XML graph counted; execution, VIN and ECU acceptance UNKNOWN")


if __name__ == "__main__":
    main()
