#!/usr/bin/env python3
"""Offline, allowlisted summary of REA .NET evidence for VDASH research.

Input: a *private local* complete REA inspect-managed-members --json response.
Output deliberately excludes paths, hashes, MVID, method names, CIL,
constants, user strings, VINs, and source metadata beyond fixed flags.
The script does not execute assemblies and cannot establish runtime success.
"""
import argparse
import json
from pathlib import Path
import re
import sys

FORMAT = "virtualcar-vdash-rea-static-audit-v1"
MODULE = "frontend.client.core.dll"
MAX_INPUT = 64 * 1024 * 1024
_SHA = re.compile(r"[a-fA-F0-9]{64}\Z")
_STATUS = {"present", "partial", "absent", "malformed"}
_SITES = {
    "methodspec_string_candidate": ("0x2b000002", "method-spec", (0x0124, 0x0423)),
    "opaque_predicate": ("0x06001359", "method-def", (0x0129, 0x0428)),
}
_STRUCTURAL_EDGES = {
    # Source-grounded in the private, earlier recovered IL for 2.5.115.79.
    # These anchors are not dynamic paths, constructor success, or ECU acceptance.
    "detect_to_detect_result_ctor":
        ("0x0600132b", "0x060011bb", "newobj", 0x017f),
    "detect_to_ecus_ctor":
        ("0x0600132b", "0x0600126d", "newobj", 0x0268),
    "execute_to_parse_data":
        ("0x0600115d", "0x06001160", "call", 0x025e),
}
_BODIES = {
    "execute": "0x0600115d",
    "detect": "0x0600132b",
    "predicate": "0x06001359",
    "parse_data": "0x06001160",
    "detect_result_constructor": "0x060011bb",
    "ecus_constructor": "0x0600126d",
}


def _token(value):
    return isinstance(value, str) and bool(re.fullmatch(r"0x[0-9a-fA-F]{8}", value))


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError("invalid_" + name)
    return value


def _identity(data):
    artifact = _object(data.get("artifact"), "artifact")
    module = _object(data.get("module"), "module")
    scope = _object(data.get("identity_scope"), "identity_scope")
    cov = _object(data.get("coverage"), "coverage")
    sha = artifact.get("sha256")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ValueError("missing_artifact_digest")
    name = module.get("name")
    if not isinstance(name, str) or name.casefold() != MODULE:
        raise ValueError("wrong_module")
    if scope.get("token_identity") != "build-local":
        raise ValueError("unattested_token_scope")
    if scope.get("requires_artifact_sha256") != sha:
        raise ValueError("artifact_identity_conflict")
    mvid = module.get("mvid")
    required = scope.get("requires_mvid")
    if required is not None and (not mvid or str(required).casefold() != str(mvid).casefold()):
        raise ValueError("module_identity_conflict")
    if cov.get("state") not in ("complete", "partial", "unavailable"):
        raise ValueError("invalid_coverage")
    return {
        "module_matched": True,
        "artifact_sha256_attested": True,
        "mvid_present": bool(mvid),
        "mvid_scope_attested": required is not None,
        "coverage": cov["state"],
    }




def _inspection_scope(data, coverage):
    """Report source bounds without exporting selected declaring-type names.

    REA's method_rows is the examined zero-based MethodDef interval BEFORE
    type selection. Missing method_rows is unknown, not all rows examined.
    """
    selection = data.get("selection")
    if selection is None:
        type_scope = "all_types"
    elif (isinstance(selection, dict)
          and isinstance(selection.get("type_names"), list)
          and len(selection["type_names"]) > 0
          and all(isinstance(n, str) and n for n in selection["type_names"])
          and isinstance(selection.get("unmatched_type_names"), list)):
        type_scope = "selected_types"
    else:
        raise ValueError("invalid_type_selection")
    rows = data.get("method_rows")
    if rows is None:
        row_scope = "unreported"
    elif isinstance(rows, dict):
        coords = [rows.get(k) for k in ("offset", "count", "total")]
        if (any(type(x) is not int or x < 0 for x in coords)
                or coords[0] + coords[1] > coords[2]):
            raise ValueError("invalid_method_row_scope")
        row_scope = ("all_rows" if coords[0] == 0 and coords[1] == coords[2]
                     else "page_only")
    else:
        raise ValueError("invalid_method_row_scope")
    return {
        "declaring_types": type_scope,
        "method_rows": row_scope,
        "all_members_examined": (coverage == "complete"
                                and type_scope == "all_types"
                                and row_scope == "all_rows"),
    }


def _cil_decode_attestation(body):
    """Return only a bounded status, never an IL digest or instruction bytes.

    A 'present' body is not on its own proof of a complete decoded CIL
    instruction stream; all decode counters and its normalized digest must
    be present and internally consistent.
    """
    fields = ("instruction_count", "decoded_instruction_count",
              "truncated_instructions", "normalized_il_sha256", "issue")
    if any(key not in body for key in fields):
        return "unreported"
    n, decoded, truncated = (body[key] for key in fields[:3])
    if (any(type(v) is not int or v < 0 for v in (n, decoded, truncated))
            or decoded > n):
        raise ValueError("invalid_cil_decode_counts")
    digest = body["normalized_il_sha256"]
    if digest is not None and (not isinstance(digest, str)
                               or not _SHA.fullmatch(digest)):
        raise ValueError("invalid_normalized_il_digest")
    issue = body["issue"]
    if issue is not None and not isinstance(issue, str):
        raise ValueError("invalid_cil_decode_issue")
    if (body["status"] == "present" and truncated == 0 and
            decoded == n and digest is not None and issue is None):
        return "complete_decode_attested"
    return "partial_or_unavailable"

def audit(document):
    outer = _object(document, "document")
    data = _object(outer.get("normalized_result"), "complete_rea_result")
    identity = _identity(data)
    inspection_scope = _inspection_scope(data, identity["coverage"])
    methods = data.get("methods")
    edges = data.get("call_edges")
    if not isinstance(methods, list) or not isinstance(edges, list):
        raise ValueError("complete_member_rows_required")
    if len(methods) > 100000 or len(edges) > 300000:
        raise ValueError("row_limit")
    bodies = {}
    decodes = {}
    for method in methods:
        if not isinstance(method, dict) or not _token(method.get("token")):
            raise ValueError("malformed_method")
        token = method["token"].lower()
        if token not in _BODIES.values():
            continue
        if token in bodies:
            raise ValueError("duplicate_method_token")
        body = _object(method.get("body"), "method_body")
        status = body.get("status")
        if status not in _STATUS:
            raise ValueError("invalid_body_status")
        bodies[token] = status
        decodes[token] = _cil_decode_attestation(body)
    observed = {key: [] for key in _SITES}
    structural = {key: [] for key in _STRUCTURAL_EDGES}
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("malformed_call_edge")
        caller = edge.get("caller_token")
        if not _token(caller):
            raise ValueError("malformed_caller_token")
        if caller.lower() not in {"0x0600132b", "0x0600115d"}:
            continue
        target = edge.get("target_token")
        if not _token(target):
            raise ValueError("malformed_target_token")
        for key, (expected_caller, expected_target, opcode, _) in _STRUCTURAL_EDGES.items():
            if (caller.lower() == expected_caller and
                    target.lower() == expected_target and
                    edge.get("target_kind") == "method-def" and
                    edge.get("opcode") == opcode):
                offset = edge.get("il_offset")
                if type(offset) is not int or offset < 0:
                    raise ValueError("invalid_il_offset")
                structural[key].append(offset)
        if caller.lower() != "0x0600132b":
            continue
        for key, (expected, kind, _) in _SITES.items():
            if target.lower() != expected:
                continue
            if edge.get("target_kind") != kind or edge.get("opcode") != "call":
                continue
            offset = edge.get("il_offset")
            if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
                raise ValueError("invalid_il_offset")
            observed[key].append(edge)
    sites = {}
    for key, (_, _, expected) in _SITES.items():
        items = observed[key]
        offsets = sorted(e["il_offset"] for e in items)
        # Untrusted source fields may be null or unexpected JSON values.
        identities = [(e.get("target_name"), e.get("target_declaring_type"))
                      for e in items]
        resolved = (bool(identities) and
                    all(identity == identities[0] for identity in identities) and
                    all(isinstance(value, str) and bool(value.strip())
                        for value in identities[0]))
        sites[key] = {
            "observed_call_count": len(items),
            "exact_expected_sites": offsets == list(expected),
            "target_identity_resolved": bool(resolved),
        }
    relationships = {}
    for key, (_, _, _, expected_offset) in _STRUCTURAL_EDGES.items():
        seen = sorted(structural[key])
        relationships[key] = {
            "observed_call_count": len(seen),
            "exact_expected_site": seen == [expected_offset],
        }
    return {
        "format": FORMAT,
        "contains_private_metadata": False,
        "client_acceptance_verified": False,
        "ecu_identity_verified": False,
        "assembly": identity,
        "inspection_scope": inspection_scope,
        "call_sites": sites,
        "structural_edges": relationships,
        "method_bodies": {
            name: {
                "inspected": token in bodies,
                "status": bodies.get(token, "not_inspected"),
                "cil_decode": decodes.get(token, "not_inspected"),
            } for name, token in _BODIES.items()
        },
        "limitations": [
            "Tokens and IL offsets are valid only for the attested assembly build",
            "Unselected or missing methods are not proof of absent methods",
            "Complete CIL decode is a static parser property, not a reachable or executed method",
            "Historical or paged REA member reports may not attest inspection of every method row",
            "Resolved metadata names do not reveal predicate semantics or runtime reachability",
            "newobj and call edges do not prove object construction succeeded, ParseData executed, or branches are reachable",
            "The MethodSpec type argument is known from separate private IL evidence, not inferred here",
            "Static CIL evidence is not VDASH ECU acceptance or an OEM CEM response",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local private complete REA JSON")
    parser.add_argument("--output", required=True, type=Path,
                        help="New sanitized JSON path (must not already exist)")
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("same_file")
        if args.source.stat().st_size > MAX_INPUT:
            raise ValueError("input_limit")
        with args.source.open(encoding="utf-8-sig") as handle:
            report = audit(json.load(handle))
        # Never overwrite a user's private REA evidence or an existing report.
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        print("VDASH REA evidence audit failed (no source details disclosed)", file=sys.stderr)
        return 2
    print("PASS: sanitized REA static evidence; VDASH ECU acceptance unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
