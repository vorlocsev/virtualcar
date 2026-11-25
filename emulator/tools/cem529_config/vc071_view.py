"""Versioned local UI preview contract. Never exports or activates a profile."""
import argparse
import json
import sys
from pathlib import Path
from vc059 import load_gate
from vc0592 import canonical, require, sha, strict_json

SCHEMA = 'vc071-ui-preview-v1'
MAX_REQUEST = 32768


def preview(gate, request):
    require(isinstance(request, dict) and set(request) == {'schema', 'edits'}, 'invalid request keys')
    require(request['schema'] == SCHEMA, 'unsupported request schema')
    editor = gate.editor
    draft = editor.draft(request['edits'])
    audit = gate.audit(draft)
    changed = {r['offset']: r for r in draft['edits']}
    rows = []
    for offset, base in sorted(editor.rows.items()):
        entry = editor.options(offset)
        edit = changed.get(offset)
        entry.update(baseline_text=base['as_text'], selected_code=edit['new_code'] if edit else base['raw_hex'],
                     selected_text=edit['new_text'] if edit else base['as_text'], changed=edit is not None)
        rows.append(entry)
    return dict(schema=SCHEMA, rows=rows, draft=draft, audit=audit,
                audit_sha256=sha(canonical(audit)), can_export=False, lab_only=True,
                vida_verified=False, oem_verified=False, physical_j2534_verified=False)


def run(argv=None, *, stdin=None, stdout=None, stderr=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, required=True)
    args = p.parse_args(argv)
    stdin = sys.stdin.buffer if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        raw = stdin.read(MAX_REQUEST + 1)
        require(0 < len(raw) <= MAX_REQUEST, 'request size')
        request = strict_json(raw.decode('utf-8'))
        report = preview(load_gate(args.data), request)
        stdout.write(json.dumps(report, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n')
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError, RecursionError):
        # No paths, vehicle data or traceback in the error stream.
        stderr.write('VC071_PREVIEW_REJECTED\n')
        return 2


if __name__ == '__main__':
    raise SystemExit(run())
