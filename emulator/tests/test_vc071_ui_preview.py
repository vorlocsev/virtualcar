"""Public contract tests use only artificial values, never the private catalog."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools' / 'cem529_config'
sys.path.insert(0, str(TOOLS))
import vc071_view as v
from vc0592 import canonical, sha


class TestUiPreview(unittest.TestCase):
    def setUp(self):
        self.g = Mock()
        self.g.editor.rows = {65: {'as_text': 'Original  value', 'raw_hex': '01'}}
        self.g.editor.options.return_value = {'offset': 65, 'locked': False, 'options': []}
        self.g.editor.draft.return_value = {'edits': []}
        self.g.audit.return_value = {'status': 'pass'}

    def request(self, edits=None):
        return {'schema': v.SCHEMA, 'edits': [] if edits is None else edits}

    def call(self, raw):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(v, 'load_gate', return_value=self.g):
            code = v.run(['--data', 'unused'], stdin=io.BytesIO(raw), stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def test_baseline(self):
        report = v.preview(self.g, self.request())
        self.assertEqual(report['rows'][0]['selected_text'], 'Original  value')
        self.assertFalse(report['rows'][0]['changed'])
        self.assertFalse(report['can_export'])
        self.assertFalse(report['vida_verified'])

    def test_changed_row(self):
        edit = {'offset': 65, 'code': '02'}
        self.g.editor.draft.return_value = {'edits': [{'offset': 65, 'new_code': '02', 'new_text': 'New'}]}
        r = v.preview(self.g, self.request([edit]))
        self.g.editor.draft.assert_called_once_with([edit])
        self.assertTrue(r['rows'][0]['changed'])
        self.assertEqual(r['rows'][0]['selected_code'], '02')

    def test_audit_binding(self):
        self.g.audit.return_value = {'status': 'blocked', 'policy': {'errors': ['TEST']}}
        r = v.preview(self.g, self.request())
        self.assertEqual(r['audit_sha256'], sha(canonical(r['audit'])))
        self.assertEqual(r['audit']['status'], 'blocked')
        self.g.compile.assert_not_called()

    def test_wrong_schema_and_extra_key(self):
        for r in ({'schema': 'other', 'edits': []}, dict(self.request(), action='export'), []):
            with self.assertRaises(ValueError):
                v.preview(self.g, r)
        self.g.editor.draft.assert_not_called()

    def test_utf8_json_response(self):
        code, out, err = self.call(json.dumps(self.request()).encode())
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out)['schema'], v.SCHEMA)

    def test_malformed_and_duplicate_json(self):
        for raw in (b'{', b'\xff', b'{"schema":"x","schema":"y","edits":[]}'):
            self.assertEqual(self.call(raw), (2, '', 'VC071_PREVIEW_REJECTED\n'))

    def test_bounded_input(self):
        self.assertEqual(self.call(b' ' * (v.MAX_REQUEST + 1)), (2, '', 'VC071_PREVIEW_REJECTED\n'))

    def test_editor_rejection_propagates_without_data(self):
        self.g.editor.draft.side_effect = ValueError('private value')
        self.assertEqual(self.call(json.dumps(self.request()).encode()), (2, '', 'VC071_PREVIEW_REJECTED\n'))
        self.g.audit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
