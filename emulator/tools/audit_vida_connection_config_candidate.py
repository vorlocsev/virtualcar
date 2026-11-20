#!/usr/bin/env python3
"""Read-only owner-selected VIDA diagnostic.config.xml candidate classification.

This is NOT an active-process settings probe. The original VIDA Core.DLL
GetValue/DiagnosticConnection source study distinguishes NoCommConnection,
J2534DiagnosticConnection, DiCEDiagnosticConnection and VirtualDiagnosticConnection.
The caller explicitly chooses one XML file; no installation, SQL, J2534,
running process, credential, diagnostic script or VIN is accessed.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

SCHEMA = "virtualcar-vida-connection-config-candidate-v1"
MAX_BYTES = 128 * 1024
MAX_ELEMENTS = 4096
KEYS = frozenset(("DiagnosticConnection", "UseClientSettings"))
MODES = frozenset((
    "J2534DiagnosticConnection", "DiCEDiagnosticConnection",
    "VirtualDiagnosticConnection", "NoCommConnection",
))
FORBIDDEN_DECLARATION = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.I)


class CandidateError(Exception):
    """Sanitized error: never echo an XML fragment or owner-local path."""


def _local_name(tag):
    if not isinstance(tag, str):
        raise CandidateError("invalid_xml_element")
    return tag.rsplit("}", 1)[-1]


def classify_bytes(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        raise CandidateError("invalid_input_size")
    if FORBIDDEN_DECLARATION.search(data):
        raise CandidateError("unsupported_xml_declaration")
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError, UnicodeError):
        raise CandidateError("invalid_xml") from None
    found = {}
    count = 0
    for element in root.iter():
        count += 1
        if count > MAX_ELEMENTS:
            raise CandidateError("xml_element_bound_exceeded")
        # Only GetValue-style value attributes. Never read element text
        # (potential credentials, VIN or serials) or arbitrary attributes.
        key = element.get("key")
        name = element.get("name")
        tag = _local_name(element.tag)
        candidates = set(x for x in (key, name, tag) if x in KEYS)
        if not candidates:
            continue
        if len(candidates) != 1:
            raise CandidateError("ambiguous_connection_key")
        selected = next(iter(candidates))
        # An explicit conflicting key/name is suspicious even if a tag also
        # happens to be named after an expected field.
        if key is not None and name is not None and key != name:
            raise CandidateError("ambiguous_connection_key")
        if selected in found:
            raise CandidateError("duplicate_connection_setting")
        value = element.get("value")
        if not isinstance(value, str) or not value or len(value) > 80:
            raise CandidateError("invalid_connection_setting")
        found[selected] = value

    if set(found) != KEYS:
        raise CandidateError("missing_connection_setting")
    mode = found["DiagnosticConnection"]
    if mode not in MODES:
        # Do not copy an unrecognized private value into the report.
        mode = "unrecognized_mode"
    setting = found["UseClientSettings"].strip().lower()
    if setting not in ("true", "false"):
        raise CandidateError("invalid_use_client_settings")
    return {
        "schema_version": SCHEMA,
        "source_scope": "one_owner_selected_diagnostic_config_xml_candidate",
        "xml_structure_read_only": True,
        "mode_candidate": mode,
        "use_client_settings_candidate": setting == "true",
        "mode_if_this_file_was_loaded": mode,
        "no_comm_candidate_if_loaded": mode == "NoCommConnection",
        "j2534_candidate_if_loaded": mode == "J2534DiagnosticConnection",
        "client_or_server_config_path_selected_at_runtime_verified": False,
        "original_vida_process_loaded_this_file_verified": False,
        "actual_diagnostic_connection_mode_verified": False,
        "j2534_connect_or_messages_verified": False,
        "original_vida_readvin_executed_verified": False,
        "original_vida_vin_accepted_verified": False,
        "ecu_identity_accepted_verified": False,
        "private_path_hash_xml_vin_exported": False,
        "next_gate": "independently_observe_active_vida_configuration_source_and_selected_tool",
        "limitations": [
            "A named candidate file is not proven to be the running client's effective configuration.",
            "UseClientSettings controls config selection logic; a file's value alone cannot attest its own selection.",
            "NoCommConnection would be a no-communication branch only if this configuration is actually active.",
            "No original J2534 process binding, D2 TX/RX, authentic CEM frame or GUI acceptance is inferred.",
        ],
    }


def classify_path(path):
    if (not isinstance(path, Path) or path.name.casefold() != "diagnostic.config.xml"
            or path.is_symlink() or not path.is_file()):
        raise CandidateError("unsupported_candidate_path")
    try:
        before = path.stat()
        if not 0 < before.st_size <= MAX_BYTES:
            raise CandidateError("invalid_input_size")
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise CandidateError("candidate_changed_during_read")
    except CandidateError:
        raise
    except OSError:
        raise CandidateError("candidate_unreadable") from None
    return classify_bytes(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline VIDA config candidate classification")
    parser.add_argument("--candidate", type=Path, required=True,
                        help="Explicit owner-local diagnostic.config.xml; no directory scan")
    args = parser.parse_args(argv)
    try:
        report = classify_path(args.candidate)
    except CandidateError:
        print("ERROR: VIDA_CONFIG_CANDIDATE_INVALID_OR_UNVERIFIED", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
