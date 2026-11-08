#!/usr/bin/env python3
"""Offline in-memory analysis of ONE private, original VIDA ReadVin ZIP.

Emits only bounded categories. Never exports original XML, node/script IDs,
VIN or filenames. This does not execute a VIDA script or produce ECU data.
"""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from audit_vida_script_archives import _read_xml, _lexical_flags
from audit_vida_readvin_xml_graph import audit_xml_bytes

SCHEMA = "virtualcar-vida-single-private-readvin-zip-v1"
ROOT = Path(__file__).resolve().parents[2]
F114_LITERAL = re.compile(r"(?i)(?<![0-9a-f])(?:0x)?f1\s*(?:0x)?14(?![0-9a-f])")


def audit(private_archive):
    archive = Path(private_archive)
    if archive.suffix.lower() != ".zip" or archive.is_symlink():
        raise ValueError("expected one private ZIP archive")
    # The existing loader enforces a single safe ZIP entry, 1 MiB XML limit,
    # no traversal/encryption, and bounded compression.
    xml = _read_xml(archive)
    flags = _lexical_flags(xml)  # Validates XML and rejects DTD/entities.
    graph = audit_xml_bytes(xml)  # Validates expected <script> event graph.
    root = ET.fromstring(xml)
    visible = []
    for node in root.iter():
        visible.extend(node.attrib.values())
        if node.text:
            visible.append(node.text)
        if node.tail:
            visible.append(node.tail)
    f114 = bool(F114_LITERAL.search("\n".join(visible)))
    del xml, root, visible
    return {
        "schema_version": SCHEMA,
        "source": "operator_supplied_private_zip_not_runtime_verified",
        "read_only": True,
        "contains_original_xml": False,
        "contains_vin_or_can": False,
        "contains_script_ids_or_paths": False,
        "xml_zip_structure_validated": True,
        "lexical_tokens_present_not_execution": {
            **flags,
            "f114": f114,
        },
        "identity_xml_graph_declarations": {
            "node_count": graph["node_count"],
            "readvin_component_count": graph["readvin_component_node_count"],
            "vehicle_identity_output_count": graph["vehicle_identity_output_node_count"],
            "declared_identity_edges": graph["declared_identity_method_edges"],
            "unresolved_identity_targets": graph["identity_method_calls_with_unresolved_target"],
        },
        "script_selected_by_getscript_runtime": False,
        "b9fb_to_vin_runtime_flow_verified": False,
        "vin_accepted_by_client": False,
        "xc90_v8_my2009_identity_verified": False,
        "replay_approved": False,
        "interpretation": (
            "Lexical tokens and declared XML events only, never proven branch "
            "reachability, protocol response, correct vehicle or runtime selection."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Redacted private VIDA ReadVin ZIP analysis")
    parser.add_argument("private_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    out = args.output.resolve()
    src = args.private_zip.resolve()
    if out == src or out == ROOT or ROOT in out.parents or args.output.parent.is_symlink():
        parser.error("unsafe local output location")
    try:
        report = audit(args.private_zip)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        parser.error("private archive audit failed: " + type(exc).__name__)
    print("ReadVin XML assessed in memory; no client VIN acceptance was established.")


if __name__ == "__main__":
    main()
