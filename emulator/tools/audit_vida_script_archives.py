#!/usr/bin/env python3
"""Offline, read-only lexical triage of locally exported VIDA script XML/ZIP.

Only categorical counts are emitted. This is NOT VIDA script execution or evidence
of a B9FB->VIN control flow. Keep all original archives and XML private.
"""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

MAX_FILES = 256
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_XML_BYTES = 1024 * 1024
SCHEMA = "virtualcar-vida-script-lexical-audit-v1"
PATTERNS = {
    "b9fb": re.compile(r"(?i)(?<![0-9a-f])(?:0x)?b9\s*(?:0x)?fb(?![0-9a-f])"),
    "b9f0": re.compile(r"(?i)(?<![0-9a-f])(?:0x)?b9\s*(?:0x)?f0(?![0-9a-f])"),
    "b9fc": re.compile(r"(?i)(?<![0-9a-f])(?:0x)?b9\s*(?:0x)?fc(?![0-9a-f])"),
    "addvin": re.compile(r"(?i)\bAddVIN\b"),
    "setx40serial": re.compile(r"(?i)\bSetX40Serial\b"),
}


def _read_xml(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("unsupported input file")
    if path.suffix.lower() == ".xml":
        if path.stat().st_size > MAX_XML_BYTES:
            raise ValueError("XML too large")
        return path.read_bytes()
    if path.suffix.lower() != ".zip":
        raise ValueError("unsupported extension")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) != 1:
                raise ValueError("expected exactly one XML entry")
            info = members[0]
            # Do not extract to a filesystem, even for apparently safe names.
            if (info.is_dir() or info.flag_bits & 1 or info.file_size > MAX_XML_BYTES
                    or info.compress_size == 0 or info.file_size > 100 * info.compress_size
                    or info.filename.startswith(("/", "\\"))
                    or "/" in info.filename or "\\" in info.filename
                    or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", info.filename)
                    or ("." in info.filename and not info.filename.lower().endswith(".xml"))):
                raise ValueError("unsafe ZIP entry")
            with archive.open(info) as stream:
                data = stream.read(MAX_XML_BYTES + 1)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError("invalid ZIP") from exc
    if len(data) > MAX_XML_BYTES:
        raise ValueError("unbounded XML")
    return data


def _lexical_flags(data):
    # No XML entities/DTD/external resource resolution. Reject their syntax.
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", data, flags=re.IGNORECASE):
        raise ValueError("DTD/entities prohibited")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("invalid XML") from exc
    # Comments and processing instructions are not examined by ElementTree.
    texts = []
    for element in root.iter():
        texts.extend(element.attrib.values())
        if element.text:
            texts.append(element.text)
        if element.tail:
            texts.append(element.tail)
    joined = "\n".join(texts)
    return {name: bool(regex.search(joined)) for name, regex in PATTERNS.items()}


def audit(directory):
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("input must be an existing non-symlink directory")
    paths = sorted(p for p in directory.iterdir() if p.suffix.lower() in (".xml", ".zip"))
    if not paths or len(paths) > MAX_FILES:
        raise ValueError("expected 1..256 XML/ZIP scripts")
    counts = {name: 0 for name in PATTERNS}
    same_script_b9fb_addvin = 0
    same_script_b9fb_x40 = 0
    for path in paths:
        flags = _lexical_flags(_read_xml(path))
        for name in counts:
            counts[name] += int(flags[name])
        same_script_b9fb_addvin += int(flags["b9fb"] and flags["addvin"])
        same_script_b9fb_x40 += int(flags["b9fb"] and flags["setx40serial"])
    return {
        "schema_version": SCHEMA,
        "input_kind": "local_authorized_vida_script_exports",
        "processed_script_count": len(paths),
        "script_counts_with_lexical_tokens": counts,
        "same_script_b9fb_addvin_lexical_cooccurrence": same_script_b9fb_addvin,
        "same_script_b9fb_x40_lexical_cooccurrence": same_script_b9fb_x40,
        "evidence_level": "lexical_tokens_only_not_executed_or_bound_to_runtime",
        "script_selection_verified": False,
        "b9fb_to_identity_control_flow_verified": False,
        "genuine_xc90_my2009_identity_verified": False,
        "replay_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private VIDA script lexical triage; safe JSON counts only")
    parser.add_argument("input_dir", type=Path, help="local exported script XML/ZIP directory")
    parser.add_argument("--output", type=Path, required=True, help="NEW JSON output; no overwrite")
    args = parser.parse_args(argv)
    if args.input_dir.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    try:
        result = audit(args.input_dir)
    except (OSError, ValueError) as exc:
        parser.error("invalid script export: " + type(exc).__name__)
    try:
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
            target.write("\n")
    except OSError as exc:
        parser.error("cannot create exclusive report: " + type(exc).__name__)
    print("VIDA script lexical audit completed; runtime B9FB-to-VIN mapping UNVERIFIED")


if __name__ == "__main__":
    main()
