#!/usr/bin/env python3
"""Owner-only VIDA 2015A GetInitHwSettings signature *shape* preflight.

Uses only the three owner-SHA-pinned original VIDA DLLs. Compares
structural CLR method-signature element categories, deliberately ignoring
local TypeDefOrRef coded row IDs and all actual type names/assembly
identities. This is not semantic type identity, signature equivalence,
CLR dispatch binding, caller arguments, profile selection or D2 bitrate.

No assembly load or execution, SQL/VIDA/J2534 access, source writes,
original signatures, token indices, type names or paths in JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from audit_vida_2015a_inithw_metadata import (
    EXPECTED, MAX_FILE, MAX_FILES_WALK, MetadataError,
)
from audit_vida_2015a_inithw_il_calls import (
    TARGET, _compressed_uint, _metadata_tables,
)

MAX_SIGNATURE_BYTES = 16384
MAX_TYPE_DEPTH = 16
MAX_TYPE_NODES = 256
MAX_GENERIC_ARGS = 64
MAX_PARAMS = 255


class UnsupportedSignature(MetadataError):
    pass


# ECMA-335 ELEMENT_TYPE leaf tags; represent categories, not original types.
_ATOMS = {
    0x01: "void", 0x02: "bool", 0x03: "char", 0x04: "i1",
    0x05: "u1", 0x06: "i2", 0x07: "u2", 0x08: "i4",
    0x09: "u4", 0x0A: "i8", 0x0B: "u8", 0x0C: "r4",
    0x0D: "r8", 0x0E: "string", 0x16: "typedbyref",
    0x18: "nativeint", 0x19: "nativeuint", 0x1C: "object",
}
_ELEMENT_NAMES = {
    0x0F: "pointer", 0x10: "byref",
    0x11: "valuetype", 0x12: "class",
    0x13: "generic_type_var", 0x1E: "generic_method_var",
    0x1D: "szarray", 0x15: "generic_instance",
}


class _SigReader:
    def __init__(self, blob: bytes):
        if not isinstance(blob, bytes) or not 2 <= len(blob) <= MAX_SIGNATURE_BYTES:
            raise MetadataError("invalid signature blob size")
        self.blob = blob
        self.pos = 0
        self.nodes = 0

    def byte(self):
        if self.pos >= len(self.blob):
            raise MetadataError("truncated CLR type signature")
        result = self.blob[self.pos]
        self.pos += 1
        return result

    def uint(self):
        value, self.pos = _compressed_uint(self.blob, self.pos)
        return value

    def typedef_or_ref(self):
        v = self.uint()
        tag, rowid = v & 3, v >> 2
        if not rowid or tag not in (0, 1, 2):
            raise MetadataError("invalid TypeDefOrRef encoded reference")
        # Return nothing: both metadata table tag and row ID are *local*
        # to each assembly and cannot be compared across DLLs.
        return None

    def typ(self, depth=0):
        self.nodes += 1
        if self.nodes > MAX_TYPE_NODES or depth > MAX_TYPE_DEPTH:
            raise UnsupportedSignature("unbounded nested CLR type")
        modifiers = []
        tag = self.byte()
        while tag in (0x1F, 0x20):  # cmod_reqd / cmod_opt
            if len(modifiers) >= 16:
                raise UnsupportedSignature("too many signature modifiers")
            modifiers.append("required_modifier" if tag == 0x1F else "optional_modifier")
            self.typedef_or_ref()
            tag = self.byte()
        if tag in _ATOMS:
            value = (_ATOMS[tag],)
        elif tag in (0x11, 0x12):
            self.typedef_or_ref()
            value = (_ELEMENT_NAMES[tag], "scope_local_type_token_ignored")
        elif tag in (0x13, 0x1E):
            # VAR/MVAR slot indexes refer to different generic contexts.
            # Include slot count class but not the raw value.
            self.uint()
            value = (_ELEMENT_NAMES[tag], "slot_index_ignored")
        elif tag in (0x0F, 0x10, 0x1D):
            value = (_ELEMENT_NAMES[tag], self.typ(depth + 1))
        elif tag == 0x15:  # GENERICINST followed by class/valuetype token
            base = self.byte()
            if base not in (0x11, 0x12):
                raise MetadataError("invalid GENERICINST owner type tag")
            self.typedef_or_ref()
            argc = self.uint()
            if argc > MAX_GENERIC_ARGS:
                raise UnsupportedSignature("unbounded generic signature arguments")
            args = tuple(self.typ(depth + 1) for _ in range(argc))
            value = ("generic_instance", _ELEMENT_NAMES[base], argc, args)
        elif tag in (0x14, 0x1B, 0x41, 0x45):
            # ARRAY, FNPTR, SENTINEL and PINNED require more contextual
            # rules; refuse classification rather than guessing.
            raise UnsupportedSignature("unsupported complex CLR type shape")
        else:
            raise UnsupportedSignature("unknown CLR type element")
        return ("modified", tuple(modifiers), value) if modifiers else value


def decode_shape(signature: bytes) -> tuple:
    """Token-neutral *shape*, not semantic CLR signature identity."""
    r = _SigReader(signature)
    cc = r.byte()
    kind = cc & 0x0F
    if kind not in (0, 5):
        raise UnsupportedSignature("unsupported target method convention")
    if cc & 0x80:
        raise UnsupportedSignature("reserved CLR method signature bit")
    arity = r.uint() if cc & 0x10 else 0
    if arity > MAX_GENERIC_ARGS:
        raise UnsupportedSignature("unbounded method generic arity")
    argc = r.uint()
    if argc > MAX_PARAMS:
        raise UnsupportedSignature("unbounded method parameter count")
    returns = r.typ()
    args = tuple(r.typ() for _ in range(argc))
    if r.pos != len(r.blob):
        raise UnsupportedSignature("unparsed signature tail")
    return ((kind, bool(cc & 0x20), bool(cc & 0x40), arity, argc),
            returns, args)


def _compare_private(metadata: dict[str, dict]) -> dict:
    """Only aggregates are returned; raw signature/type data remain local."""
    exact = metadata["bizservices.carcom.db.dll"]
    repo = [
        m["signature_bytes_private"]
        for m in exact["methods"].values()
        if m["name"] == TARGET and m["repository_owner"]
    ]
    if len(repo) != 1 or exact[
        "carcom_repository_direct_icarcomrepository_interfaceimpl_rows"
    ] != 1:
        raise MetadataError("original repository target is not unambiguous")
    candidates = []
    for key in ("bizservices.vehiclecommprovider.dll", "workflow.dll"):
        m = metadata[key]
        for tok, family in m["target_reference_parent_type_families"].items():
            if family == "icarcom_repository":
                candidates.append(m["target_reference_signature_bytes_private"].get(tok))
    if len(candidates) != 2:
        raise MetadataError("original interface reference set is not two candidates")

    counts = {
        "repository_methoddef_candidates": 1,
        "interface_memberref_candidates": len(candidates),
        "signatures_shape_compared": 0,
        "signatures_structurally_equal_ignoring_type_tokens": 0,
        "signatures_structurally_different": 0,
        "signatures_unclassified": 0,
        "returns_structurally_equal_ignoring_type_tokens": 0,
        "returns_structurally_different": 0,
        "parameters_structurally_equal_ignoring_type_tokens": 0,
        "parameters_structurally_different": 0,
        "calling_conventions_equal": 0,
        "calling_conventions_different": 0,
    }
    try:
        repo_shape = decode_shape(repo[0]) if repo[0] is not None else None
    except (MetadataError, UnsupportedSignature):
        repo_shape = None
    for sig in candidates:
        try:
            other = decode_shape(sig) if sig is not None else None
        except (MetadataError, UnsupportedSignature):
            other = None
        if repo_shape is None or other is None:
            counts["signatures_unclassified"] += 1
            continue
        counts["signatures_shape_compared"] += 1
        counts["signatures_structurally_equal_ignoring_type_tokens"] += int(
            repo_shape == other
        )
        counts["signatures_structurally_different"] += int(repo_shape != other)
        for same, different, x, y in (
            ("returns_structurally_equal_ignoring_type_tokens",
             "returns_structurally_different", repo_shape[1], other[1]),
            ("parameters_structurally_equal_ignoring_type_tokens",
             "parameters_structurally_different", repo_shape[2], other[2]),
            ("calling_conventions_equal",
             "calling_conventions_different", repo_shape[0], other[0]),
        ):
            counts[same if x == y else different] += 1
    n = len(candidates)
    if (counts["signatures_shape_compared"] +
            counts["signatures_unclassified"] != n or
            counts["signatures_structurally_equal_ignoring_type_tokens"] +
            counts["signatures_structurally_different"] !=
            counts["signatures_shape_compared"] or
            any(counts[a] + counts[b] != counts["signatures_shape_compared"]
                for a, b in (
                    ("returns_structurally_equal_ignoring_type_tokens",
                     "returns_structurally_different"),
                    ("parameters_structurally_equal_ignoring_type_tokens",
                     "parameters_structurally_different"),
                    ("calling_conventions_equal", "calling_conventions_different"),
                ))):
        raise MetadataError("inconsistent count-only CLR signature shape audit")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA source folder")
    found = {}
    visited = 0
    def failure(_):
        raise MetadataError("original source folder cannot be traversed")
    for root, dirs, files in os.walk(folder, followlinks=False, onerror=failure):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for filename in files:
            visited += 1
            if visited > MAX_FILES_WALK:
                raise MetadataError("bounded source walk exceeded")
            key = filename.casefold()
            if key not in EXPECTED:
                continue
            path = Path(root) / filename
            if key in found or path.is_symlink() or not path.is_file():
                raise MetadataError("ambiguous source file path")
            found[key] = path
    if set(found) != set(EXPECTED):
        raise MetadataError("missing original SHA-pinned VIDA module")
    metadata = {}
    for key, (_, expected_sha) in sorted(EXPECTED.items()):
        f = found[key]
        n = f.stat().st_size
        if n < 128 or n > MAX_FILE:
            raise MetadataError("original source size out of bounds")
        with f.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if len(raw) != n or f.stat().st_size != n or hashlib.sha256(raw).hexdigest() != expected_sha:
            raise MetadataError("original source hash mismatch")
        metadata[key] = _metadata_tables(raw)
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-sig-shapes-v1",
        "status": "owner_original_static_token_neutral_signature_shape_only",
        "counts": _compare_private(metadata),
        "source": "sha256_pinned_owner_original_vida_2015a_dlls",
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_type_names_signatures_paths_or_tokens_exported": False,
        "structural_signature_shape_proves_type_identity": False,
        "token_neutral_shape_proves_memberref_methoddef_binding": False,
        "original_assemblyref_identity_verified": False,
        "original_methodimpl_dispatch_verified": False,
        "callsite_arguments_or_profile_list_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Owner-only original VIDA GetInitHwSettings token-neutral signature shape categories"
    )
    parser.add_argument("--folder", type=Path, required=True)
    opts = parser.parse_args(argv)
    try:
        print(json.dumps(audit(opts.folder), sort_keys=True, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"status": "failed", "error_class": type(e).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
