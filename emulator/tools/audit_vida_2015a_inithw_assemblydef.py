#!/usr/bin/env python3
"""Original VIDA 2015A AssemblyDef ↔ external AssemblyRef stored identity gate.

Exactly three SHA-256-pinned local DLLs are opened read-only; no CLR load,
assembly execution, network, VIDA, SQL, J2534, or original-file writes.

The original local TypeDef ICarComRepository in CarCom.DB must be compared
to the containing module's AssemblyDef, *not* to a nonexistent AssemblyRef.
Two external TypeRef→AssemblyRef identities are compared to that AssemblyDef
in memory, including normalization of full public keys to 8-byte tokens.
Output is only category counts. Stored identity != actual runtime binding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from audit_vida_2015a_inithw_metadata import EXPECTED, MAX_FILE, MAX_FILES_WALK, MetadataError
from audit_vida_2015a_inithw_assembly_identity import (
    _table_layout, _repository_interface, _caller_interface_memberrefs,
)

FLAG_PUBLIC_KEY = 0x0001
MAX_PUBLIC_KEY_BYTES = 8192


def _public_key_token(full_key: bytes) -> bytes:
    if not 1 <= len(full_key) <= MAX_PUBLIC_KEY_BYTES:
        raise MetadataError("invalid full assembly public key extent")
    return hashlib.sha1(full_key).digest()[-8:][::-1]


def _assemblydef(meta: dict) -> tuple:
    """Canonical in-memory AssemblyDef name/version/culture/public-key token."""
    if meta["counts"].get(32, 0) != 1:
        raise MetadataError("expected exactly one manifest AssemblyDef")
    p = meta["row"](32, 1)
    u = meta["u"]
    st, bl = meta["strsize"], meta["blobsize"]
    version = tuple(u(p + 4 + 2 * i, 2) for i in range(4))
    flags = u(p + 12, 4)
    key = meta["blob"](u(p + 16, bl))
    name = meta["typename"](u(p + 16 + bl, st))
    culture_idx = u(p + 16 + bl + st, st)
    culture = meta["typename"](culture_idx) if culture_idx else ""
    if not name or len(name) > 512:
        raise MetadataError("invalid original AssemblyDef name")
    if key:
        if not flags & FLAG_PUBLIC_KEY:
            raise MetadataError("AssemblyDef has key without public-key flag")
        token = _public_key_token(key)
        key_kind = "strong"
    else:
        if flags & FLAG_PUBLIC_KEY:
            raise MetadataError("AssemblyDef public-key flag without a key")
        token = b""
        key_kind = "unsigned"
    return (name.casefold(), version, culture.casefold(), token, flags & ~FLAG_PUBLIC_KEY, key_kind)


def _external_assemblyref(meta: dict, reference: tuple) -> tuple:
    """Canonical in-memory AssemblyRef identity; retain absent/invalid states."""
    full_type, kind, identity = reference
    if kind != "assemblyref" or identity is None:
        raise MetadataError("non-AssemblyRef interface TypeRef")
    name, version, culture, flags, key_or_token = identity
    if not name or len(name) > 512:
        raise MetadataError("invalid original AssemblyRef name")
    if flags & FLAG_PUBLIC_KEY:
        token = _public_key_token(key_or_token)
        key_kind = "strong"
    elif len(key_or_token) == 0:
        token = b""
        key_kind = "unsigned"
    elif len(key_or_token) == 8:
        token = key_or_token
        key_kind = "strong"
    else:
        raise MetadataError("original AssemblyRef invalid public key token length")
    return (name.casefold(), version, culture.casefold(), token, flags & ~FLAG_PUBLIC_KEY, key_kind)


def _compare_private(metadata: dict[str, dict]) -> dict:
    base = metadata["bizservices.carcom.db.dll"]
    local_interface = _repository_interface(base)
    if local_interface[1] != "local_typedef":
        raise MetadataError("repository interface is not a local TypeDef")
    repo_id = _assemblydef(base)
    callers = [
        _caller_interface_memberrefs(metadata["bizservices.vehiclecommprovider.dll"]),
        _caller_interface_memberrefs(metadata["workflow.dll"]),
    ]
    counts = {
        "original_repository_local_interface_typedef": 1,
        "original_repository_assemblydef_count": 1,
        "caller_typeref_assemblyref_candidates": len(callers),
        "caller_assemblyref_keys_are_token": 0,
        "caller_assemblyref_keys_are_full": 0,
        "caller_assemblyref_keys_are_unsigned": 0,
        "full_interface_typename_equal": 0,
        "full_interface_typename_different": 0,
        "assembly_simple_name_equal": 0,
        "assembly_simple_name_different": 0,
        "assembly_version_equal": 0,
        "assembly_version_different": 0,
        "assembly_culture_equal": 0,
        "assembly_culture_different": 0,
        "normalized_publickeytoken_equal": 0,
        "normalized_publickeytoken_different": 0,
        "non_publickey_assembly_flags_equal": 0,
        "non_publickey_assembly_flags_different": 0,
        "stored_canonical_name_version_culture_token_equal": 0,
        "stored_canonical_name_version_culture_token_different": 0,
    }
    for caller in callers:
        ref_id = _external_assemblyref(metadata, caller)
        # kind of key *stored in external assemblyref*, rather than canonical strong/unsigned type:
        raw_flags, raw_key = caller[2][3], caller[2][4]
        field = ("caller_assemblyref_keys_are_full" if raw_flags & FLAG_PUBLIC_KEY
                 else "caller_assemblyref_keys_are_token" if raw_key
                 else "caller_assemblyref_keys_are_unsigned")
        counts[field] += 1
        for label, expected, received in (
            ("full_interface_typename", local_interface[0], caller[0]),
            ("assembly_simple_name", repo_id[0], ref_id[0]),
            ("assembly_version", repo_id[1], ref_id[1]),
            ("assembly_culture", repo_id[2], ref_id[2]),
            ("normalized_publickeytoken", repo_id[3], ref_id[3]),
            ("non_publickey_assembly_flags", repo_id[4], ref_id[4]),
            ("stored_canonical_name_version_culture_token",
             repo_id[:4], ref_id[:4]),
        ):
            counts[label + ("_equal" if expected == received else "_different")] += 1
    if counts["caller_typeref_assemblyref_candidates"] != 2:
        raise MetadataError("expected exactly two external interface MemberRefs")
    for stem in (
        "full_interface_typename", "assembly_simple_name", "assembly_version",
        "assembly_culture", "normalized_publickeytoken",
        "non_publickey_assembly_flags", "stored_canonical_name_version_culture_token",
    ):
        if counts[stem + "_equal"] + counts[stem + "_different"] != 2:
            raise MetadataError("unreconciled original AssemblyDef comparison")
    if sum(counts[k] for k in (
        "caller_assemblyref_keys_are_token",
        "caller_assemblyref_keys_are_full",
        "caller_assemblyref_keys_are_unsigned",
    )) != 2:
        raise MetadataError("unreconciled original AssemblyRef public key encodings")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid owner-only VIDA source folder")
    found = {}
    seen = 0
    def fail_walk(_):
        raise MetadataError("unreadable owner-only VIDA source")
    for root, dirs, files in os.walk(folder, topdown=True, followlinks=False, onerror=fail_walk):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for filename in files:
            seen += 1
            if seen > MAX_FILES_WALK:
                raise MetadataError("bounded original binary search exceeded")
            key = filename.casefold()
            if key not in EXPECTED:
                continue
            file = Path(root) / filename
            if key in found or file.is_symlink() or not file.is_file():
                raise MetadataError("ambiguous pinned original DLL")
            found[key] = file
    if set(found) != set(EXPECTED):
        raise MetadataError("missing SHA-pinned original VIDA modules")
    metadata = {}
    for key, (_, expected_sha) in sorted(EXPECTED.items()):
        file = found[key]
        size = file.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("original DLL size outside approved limits")
        with file.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if (len(raw) != size or file.stat().st_size != size or
                hashlib.sha256(raw).hexdigest() != expected_sha):
            raise MetadataError("original DLL SHA256 mismatch")
        metadata[key] = _table_layout(raw)
    return {
        "schema_version": "virtualcar-vida-original-2015a-local-assemblydef-vs-assemblyref-v1",
        "status": "owner_private_sha_pinned_local_assemblydef_to_external_assemblyref_counts_only",
        "counts": _compare_private(metadata),
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_assembly_names_versions_keys_type_names_or_paths_emitted": False,
        "stored_assembly_identity_proves_runtime_binding": False,
        "stored_interface_typename_proves_methodimpl_dispatch": False,
        "caller_profile_identifiers_argument_verified": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Original VIDA static AssemblyDef vs AssemblyRef identity count-only")
    p.add_argument("--folder", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        print(json.dumps(audit(a.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
